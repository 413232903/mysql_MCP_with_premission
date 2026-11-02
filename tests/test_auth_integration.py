"""鉴权集成测试：真实 FastMCP SSE 服务 + AuthMiddleware 端到端验证

在本地空闲端口启动真实的 uvicorn + FastMCP SSE 服务器（组装方式与
src/server.py:_build_asgi_app 一致），用 mcp SDK 客户端验证：

1. 未携带鉴权 Header → 连接被拒绝（401）
2. Bearer Token 鉴权通过 → MCP 会话建立、工具可调用
3. 鉴权身份（contextvar）传播到工具执行内部，resolve_user_id 生效
4. 工具入参伪造 user_id → 被拒绝（行级权限身份绑定）
5. HMAC 签名的 GET /sse2 → 真实传输层验签通过并返回 SSE 流
6. /health 探活无需鉴权

依赖 mcp/uvicorn/httpx（mcp SDK 自带），无数据库依赖。
运行: python -m pytest tests/test_auth_integration.py -v
"""
import asyncio
import json
import socket
import threading
import time
import uuid

import pytest

mcp_pkg = pytest.importorskip('mcp', reason='集成测试需要 mcp SDK')
uvicorn = pytest.importorskip('uvicorn')
httpx = pytest.importorskip('httpx')

from src.security.auth import (AuthMiddleware, HealthApp, AuthSettings,
                               build_string_to_sign, compute_signature,
                               get_current_identity, get_session_registry,
                               hash_token, resolve_user_id)

# --------------------------------------------------------------------------
# 测试凭据与配置
# --------------------------------------------------------------------------
TOKEN_A = 'integration-token-aaa-PLAINTEXT'
HASH_A = hash_token(TOKEN_A)
APP_KEY = 'ak_integration'
APP_SECRET = 'integration-secret'

SETTINGS = AuthSettings(
    enabled=True,
    mode='both',
    enforce_mode='enforce',
    token_backend='env',
    tokens_str=f"client-a:{HASH_A}:user_a",
    hmac_keys_str=f"{APP_KEY}:{APP_SECRET}:client-h",
    max_failures=1000,
    block_seconds=1,
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture(scope='module')
def server_url():
    """启动带鉴权中间件的真实 FastMCP SSE 服务器（与 server.py 组装一致）"""
    import inspect
    from mcp.server.fastmcp import FastMCP

    port = _free_port()
    mcp_server = FastMCP("AuthIntegrationServer", host='127.0.0.1', port=port,
                         sse_path='/sse2')

    @mcp_server.tool()
    async def whoami(user_id: str = None) -> str:
        """返回当前鉴权身份与 resolve_user_id 结果（模拟业务工具的身份消费）"""
        identity = get_current_identity()
        result = {
            'client_id': identity.client_id if identity else None,
            'auth_mode': identity.auth_mode if identity else None,
            'identity_user_id': identity.user_id if identity else None,
            'resolved_user_id': None,
            'error': None,
        }
        try:
            result['resolved_user_id'] = resolve_user_id(user_id)
        except Exception as exc:
            result['error'] = str(exc)
        return json.dumps(result)

    # 与 src/server.py:_build_asgi_app 相同的组装逻辑
    if 'mount_path' in inspect.signature(mcp_server.sse_app).parameters:
        app = mcp_server.sse_app('/')
    else:  # pragma: no cover
        app = mcp_server.sse_app()
    app = HealthApp(AuthMiddleware(app, settings=SETTINGS))

    config = uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error')
    http_server = uvicorn.Server(config)
    thread = threading.Thread(target=http_server.run, daemon=True)
    thread.start()

    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), 0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:  # pragma: no cover
        raise RuntimeError("测试服务器启动超时")

    yield f"http://127.0.0.1:{port}"

    http_server.should_exit = True
    thread.join(timeout=10)
    get_session_registry().clear()


# --------------------------------------------------------------------------
# 客户端辅助
# --------------------------------------------------------------------------
async def _mcp_call_tool(url: str, headers: dict, tool: str, arguments: dict):
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    async with sse_client(f"{url}/sse2", headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool, arguments)


def _tool_payload(result) -> dict:
    """解析 CallToolResult 中 whoami 返回的 JSON"""
    assert not result.isError, f"工具调用失败: {result.content}"
    return json.loads(result.content[0].text)


# --------------------------------------------------------------------------
# 集成用例
# --------------------------------------------------------------------------
class TestSseEndToEnd:
    def test_unauthenticated_connection_rejected(self, server_url):
        """未携带鉴权 Header：SSE 建连直接 401，无法进入 MCP 会话

        注: mcp 客户端经 anyio TaskGroup 抛出，401 错误包在 ExceptionGroup 中
        """
        def _contains_401(exc) -> bool:
            if isinstance(exc, httpx.HTTPStatusError):
                return exc.response.status_code == 401
            if isinstance(exc, BaseExceptionGroup):
                return any(_contains_401(e) for e in exc.exceptions)
            return False

        with pytest.raises(BaseException) as exc_info:
            asyncio.run(_mcp_call_tool(server_url, {}, 'whoami', {}))
        assert _contains_401(exc_info.value), f"预期 401 拒绝，实际: {exc_info.value!r}"

    def test_bearer_auth_full_session(self, server_url):
        """Bearer 鉴权 → 会话建立 → 工具执行 → 身份 contextvar 传播到工具内部"""
        headers = {'Authorization': f'Bearer {TOKEN_A}'}
        result = asyncio.run(_mcp_call_tool(server_url, headers, 'whoami', {}))
        payload = _tool_payload(result)
        assert payload['client_id'] == 'client-a'
        assert payload['auth_mode'] == 'token'
        assert payload['identity_user_id'] == 'user_a'
        # 关键：SSE 建连请求上注入的身份对会话内所有工具调用可见
        assert payload['resolved_user_id'] == 'user_a'

    def test_spoofed_user_id_param_rejected(self, server_url):
        """工具入参伪造他人 user_id → resolve_user_id 拒绝（防水平越权）"""
        headers = {'Authorization': f'Bearer {TOKEN_A}'}
        result = asyncio.run(
            _mcp_call_tool(server_url, headers, 'whoami', {'user_id': 'mallory'}))
        payload = _tool_payload(result)
        assert payload['error'] and '身份不匹配' in payload['error']
        assert payload['resolved_user_id'] is None

    def test_consistent_user_id_param_accepted(self, server_url):
        """入参与凭据绑定 user_id 一致 → 正常放行"""
        headers = {'Authorization': f'Bearer {TOKEN_A}'}
        result = asyncio.run(
            _mcp_call_tool(server_url, headers, 'whoami', {'user_id': 'user_a'}))
        payload = _tool_payload(result)
        assert payload['error'] is None
        assert payload['resolved_user_id'] == 'user_a'

    def test_invalid_token_rejected(self, server_url):
        headers = {'Authorization': 'Bearer not-a-valid-token'}
        with pytest.raises(Exception):
            asyncio.run(_mcp_call_tool(server_url, headers, 'whoami', {}))

    def test_hmac_signed_sse_stream(self, server_url):
        """HMAC 签名的 GET /sse2：真实传输层验签通过并建立 SSE 流"""
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())
        string_to_sign = build_string_to_sign('GET', '/sse2', '', timestamp, nonce, b'')
        signature = compute_signature(APP_SECRET, string_to_sign)
        headers = {
            'X-Auth-Key': APP_KEY,
            'X-Auth-Timestamp': timestamp,
            'X-Auth-Nonce': nonce,
            'X-Auth-Signature': signature,
        }
        with httpx.stream('GET', f"{server_url}/sse2", headers=headers,
                          timeout=5) as response:
            assert response.status_code == 200
            assert response.headers['content-type'].startswith('text/event-stream')
            # 读到 MCP 传输层下发的 endpoint 事件即证明会话已建立
            first_event = ''
            for line in response.iter_lines():
                if line.startswith('event:'):
                    first_event = line
                    break
            assert 'endpoint' in first_event

    def test_hmac_replayed_request_rejected(self, server_url):
        """同一签名的 SSE 建连请求重放 → Nonce 防重放拦截"""
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())
        string_to_sign = build_string_to_sign('GET', '/sse2', '', timestamp, nonce, b'')
        signature = compute_signature(APP_SECRET, string_to_sign)
        headers = {
            'X-Auth-Key': APP_KEY,
            'X-Auth-Timestamp': timestamp,
            'X-Auth-Nonce': nonce,
            'X-Auth-Signature': signature,
        }
        with httpx.stream('GET', f"{server_url}/sse2", headers=headers,
                          timeout=5) as response:
            assert response.status_code == 200
        # 完全相同的请求重放
        with httpx.stream('GET', f"{server_url}/sse2", headers=headers,
                          timeout=5) as response:
            assert response.status_code == 401

    def test_health_endpoint_no_auth(self, server_url):
        response = httpx.get(f"{server_url}/health", timeout=5)
        assert response.status_code == 200
        assert response.json() == {'status': 'ok'}

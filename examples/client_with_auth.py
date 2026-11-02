"""MCP 客户端鉴权调用示例（安全整改：Header 鉴权，禁止明文参数校验）

示例 1: Bearer Token 模式 —— 适用于百炼平台及 mcp SDK 客户端
        （SDK 的 sse_client 只支持静态 Header，无法逐请求动态签名）
        百炼控制台配置方法: MCP 服务 → 自定义 Header →
            Authorization: Bearer <token>

示例 2: HMAC-SHA256 签名模式 —— 适用于自研后端 / 网关等可动态签名的调用方
        AppSecret 永不离开客户端，网络上不出现任何明文密钥；
        签名串规范必须与服务端 src/security/auth/hmac_verifier.py 完全一致。

凭据由管理员用 scripts/gen_token.py 签发，通过线下安全渠道交付。
"""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from urllib.parse import parse_qsl, urlencode
from urllib.request import Request, urlopen

# 服务地址与凭据（从环境变量读取，禁止硬编码到代码库）
BASE_URL = os.getenv("MCP_BASE_URL", "http://127.0.0.1:3000")
SSE_URL = os.getenv("MCP_SSE_URL", f"{BASE_URL}/sse2")
BEARER_TOKEN = os.getenv("MCP_AUTH_TOKEN", "")
APP_KEY = os.getenv("MCP_APP_KEY", "")
APP_SECRET = os.getenv("MCP_APP_SECRET", "")


# =====================================================================
# 示例 1: Bearer Token + mcp SDK（SSE 客户端）
# =====================================================================
async def bearer_example():
    """携带 Authorization Header 建立 MCP 会话并调用工具"""
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    async with sse_client(SSE_URL, headers=headers) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("可用工具:", [t.name for t in tools.tools])

            # 注意: 启用 AUTH_BIND_USER 后，行级权限 user_id 以 Token 绑定值为准，
            # 无需（也不能）再通过入参伪造 user_id
            result = await session.call_tool(
                "mysql_query",
                arguments={"query": "SELECT 1 AS ok"},
            )
            print("查询结果:", result)


# =====================================================================
# 示例 2: HMAC-SHA256 动态签名
# =====================================================================
def canonical_query_string(query_string: str) -> str:
    """按 key 字典序规范化 query string（与服务端一致）"""
    if not query_string:
        return ''
    return urlencode(sorted(parse_qsl(query_string, keep_blank_values=True)))


def sign_headers(method: str, path: str, query_string: str = '', body: bytes = b'',
                 app_key: str = APP_KEY, app_secret: str = APP_SECRET) -> dict:
    """构建 HMAC 签名请求头

    StringToSign = METHOD + "\\n" + Path + "\\n" + SortedQuery + "\\n"
                 + Timestamp + "\\n" + Nonce + "\\n" + SHA256Hex(Body)
    Signature    = Base64(HMAC-SHA256(AppSecret, StringToSign))
    """
    timestamp = str(int(time.time()))
    nonce = str(uuid.uuid4())
    body_hash = hashlib.sha256(body or b'').hexdigest()
    string_to_sign = '\n'.join([
        method.upper(), path, canonical_query_string(query_string),
        timestamp, nonce, body_hash,
    ])
    signature = base64.b64encode(
        hmac.new(app_secret.encode('utf-8'), string_to_sign.encode('utf-8'),
                 hashlib.sha256).digest()
    ).decode('ascii')
    return {
        "X-Auth-Key": app_key,
        "X-Auth-Timestamp": timestamp,
        "X-Auth-Nonce": nonce,
        "X-Auth-Signature": signature,
    }


def hmac_request_example():
    """演示对一个 POST 请求签名并发送（REST 化调用 / 网关转发场景）

    路径、query、body 均参与签名：任何一处被篡改，服务端验签都会失败。
    """
    path = "/messages/"
    query = "session_id=demo-session"
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/list",
    }).encode('utf-8')

    headers = sign_headers("POST", path, query, body)
    headers["Content-Type"] = "application/json"

    req = Request(f"{BASE_URL}{path}?{query}", data=body, headers=headers, method="POST")
    with urlopen(req, timeout=10) as resp:
        print("HTTP", resp.status, resp.read()[:200])


if __name__ == "__main__":
    if BEARER_TOKEN:
        print(">>> 示例 1: Bearer Token 模式")
        asyncio.run(bearer_example())
    elif APP_KEY and APP_SECRET:
        print(">>> 示例 2: HMAC 签名模式")
        hmac_request_example()
    else:
        print("请设置环境变量后运行:")
        print("  Bearer 模式: MCP_AUTH_TOKEN=<token>  (可选 MCP_SSE_URL)")
        print("  HMAC 模式:   MCP_APP_KEY=<ak> MCP_APP_SECRET=<secret>  (可选 MCP_BASE_URL)")

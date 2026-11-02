"""MCP 服务传输层鉴权中间件（纯 ASGI，无框架依赖）

在请求到达 MCP 路由之前完成 Header 凭据校验，覆盖 SSE 流端点（GET /sse2）
与消息端点（POST /messages/）在内的全部 HTTP 请求：

    HTTP 请求 → AuthMiddleware（Bearer Token / HMAC 签名）
                  ├─ 校验失败 → 401（audit 模式仅告警放行）
                  └─ 校验通过 → 注入 AuthIdentity（scope + contextvar）→ MCP 应用

审计原则：日志只记录凭据指纹（SHA-256 前 8 位），严禁出现 Token/签名原文。
"""
import json
import logging
import threading
import time
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs

from .hmac_verifier import HEADER_SIGNATURE, HmacVerifier
from .identity import (AuthIdentity, credential_fingerprint, get_session_registry,
                       reset_identity, set_identity)
from .settings import AuthSettings
from .token_store import TokenStore

logger = logging.getLogger("mysql_server")

# 请求体缓冲上限（HMAC 签名校验需要读 body；MCP JSON-RPC 消息远小于此值）
MAX_BUFFERED_BODY_BYTES = 5 * 1024 * 1024


class _ReplayReceive:
    """重放已缓冲请求体的 ASGI receive 包装"""

    def __init__(self, body: bytes):
        self._body = body
        self._sent = False

    async def __call__(self):
        if not self._sent:
            self._sent = True
            return {'type': 'http.request', 'body': self._body, 'more_body': False}
        # body 已交付；下游若再次调用（不应发生）返回断开事件
        return {'type': 'http.disconnect'}


class _FailureLimiter:
    """IP 维度连续认证失败限速（防在线爆破）"""

    def __init__(self, max_failures: int, block_seconds: int, max_tracked: int = 10000):
        self._max_failures = max(1, max_failures)
        self._block_seconds = block_seconds
        self._max_tracked = max_tracked
        self._state: Dict[str, Tuple[int, float]] = {}  # ip -> (连续失败数, 封禁截止时刻)
        self._lock = threading.Lock()

    def is_blocked(self, ip: str) -> bool:
        with self._lock:
            entry = self._state.get(ip)
            if entry is None:
                return False
            if entry[1] > time.time():
                return True
            if entry[1] != 0:
                # 封禁已到期，重置状态
                self._state.pop(ip, None)
            return False

    def record_failure(self, ip: str) -> None:
        now = time.time()
        with self._lock:
            count, blocked_until = self._state.get(ip, (0, 0.0))
            count += 1
            if count >= self._max_failures:
                blocked_until = now + self._block_seconds
                count = 0
                logger.warning("AUTH BLOCK ip=%s 连续失败达阈值，封禁 %d 秒", ip, self._block_seconds)
            self._state[ip] = (count, blocked_until)
            if len(self._state) > self._max_tracked:
                self._prune(now)

    def record_success(self, ip: str) -> None:
        with self._lock:
            self._state.pop(ip, None)

    def _prune(self, now: float) -> None:
        expired = [ip for ip, (_, until) in self._state.items() if until and until <= now]
        for ip in expired:
            self._state.pop(ip, None)


async def _send_json_response(send, status: int, payload: dict,
                              extra_headers: Optional[list] = None) -> None:
    body = json.dumps(payload).encode('utf-8')
    headers = [
        (b'content-type', b'application/json; charset=utf-8'),
        (b'content-length', str(len(body)).encode('ascii')),
    ]
    headers.extend(extra_headers or [])
    await send({'type': 'http.response.start', 'status': status, 'headers': headers})
    await send({'type': 'http.response.body', 'body': body})


class AuthMiddleware:
    """纯 ASGI 鉴权中间件

    Args:
        app: 被包装的 ASGI 应用（FastMCP 的 sse_app() Starlette 实例）
        settings: AuthSettings 配置快照（AuthConfig.get_config() 构建）
    """

    def __init__(self, app, settings: Optional[AuthSettings] = None):
        self.app = app
        self.settings = settings or AuthSettings()
        self.token_store = TokenStore(self.settings)
        self.hmac_verifier = HmacVerifier(self.settings)
        self.limiter = _FailureLimiter(self.settings.max_failures,
                                       self.settings.block_seconds)
        self.registry = get_session_registry()

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'http' or self.settings.enforce_mode == 'off':
            return await self.app(scope, receive, send)

        path = scope.get('path', '/')
        if path in self.settings.exempt_paths:
            return await self.app(scope, receive, send)

        method = scope.get('method', 'GET')
        client_ip = self._client_ip(scope)
        headers = self._headers_dict(scope)
        session_id = self._session_id(scope)

        if self.limiter.is_blocked(client_ip):
            logger.warning("AUTH THROTTLED ip=%s path=%s 封禁期内拒绝", client_ip, path)
            return await _send_json_response(send, 429, {"error": "too_many_requests"})

        # HMAC 签名校验需要请求体；仅在 POST 且携带签名头时缓冲（GET/SSE 不触碰 receive）
        body: Optional[bytes] = None
        if method != 'GET' and self.settings.hmac_enabled and HEADER_SIGNATURE in headers:
            body, receive, disconnected = await self._buffer_body(receive)
            if disconnected:
                return

        identity, reason = await self._authenticate(scope, method, path, headers, body)

        if identity is None:
            self.limiter.record_failure(client_ip)
            self._audit('AUTH FAILED', scope, client_ip, reason=reason,
                        headers=headers, session_id=session_id)
            if self.settings.enforce_mode == 'audit':
                # 灰度观察模式：记录未鉴权调用但按旧行为放行（不注入身份）
                return await self.app(scope, receive, send)
            return await _send_json_response(
                send, 401, {"error": "unauthorized"},
                extra_headers=[(b'www-authenticate', b'Bearer realm="mysql-mcp"')])

        # 会话绑定：同一 session_id 只允许最初使用它的 client_id 继续投递消息
        if session_id and not self.registry.bind_or_verify(session_id, identity.client_id):
            self._audit('AUTH SESSION-MISMATCH', scope, client_ip,
                        identity=identity, session_id=session_id)
            return await _send_json_response(send, 403, {"error": "forbidden"})

        self.limiter.record_success(client_ip)
        self._audit('AUTH OK', scope, client_ip, identity=identity, session_id=session_id)
        scope['auth_identity'] = identity
        ctx_token = set_identity(identity)
        try:
            return await self.app(scope, receive, send)
        finally:
            reset_identity(ctx_token)

    # ------------------------------------------------------------------
    # 认证
    # ------------------------------------------------------------------
    async def _authenticate(self, scope, method: str, path: str,
                            headers: Dict[str, str],
                            body: Optional[bytes]) -> Tuple[Optional[AuthIdentity], str]:
        """按 Bearer → HMAC 顺序尝试启用的认证方式，返回 (身份, 失败原因码)"""
        reason = 'missing_credentials'

        # 1) Bearer Token
        auth_header = headers.get('authorization', '')
        if self.settings.token_enabled and auth_header[:7].lower() == 'bearer ':
            token = auth_header[7:].strip()
            if token:
                record = await self.token_store.lookup(token)
                if record is not None:
                    identity = AuthIdentity(
                        client_id=record.client_id,
                        auth_mode='token',
                        user_id=record.user_id,
                        scopes=record.scopes,
                        credential_fingerprint=credential_fingerprint(token),
                    )
                    return identity, ''
                reason = 'invalid_or_expired_token'

        # 2) HMAC 签名
        if self.settings.hmac_enabled and HEADER_SIGNATURE in headers:
            identity, hmac_reason = await self.hmac_verifier.verify(
                method=method,
                path=path,
                query_string=scope.get('query_string', b'').decode('latin-1'),
                body=body if body is not None else b'',
                headers=headers,
            )
            if identity is not None:
                return identity, ''
            reason = hmac_reason

        return None, reason

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    @staticmethod
    def _headers_dict(scope) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        for raw_key, raw_value in scope.get('headers') or []:
            key = raw_key.decode('latin-1').lower()
            value = raw_value.decode('latin-1')
            if key in headers:
                headers[key] = headers[key] + ', ' + value
            else:
                headers[key] = value
        return headers

    @staticmethod
    def _session_id(scope) -> Optional[str]:
        query = scope.get('query_string', b'').decode('latin-1')
        if not query:
            return None
        values = parse_qs(query).get('session_id')
        return values[0] if values else None

    @staticmethod
    def _client_ip(scope) -> str:
        # 经 SLB/网关转发时优先取 X-Forwarded-For 首跳（仅用于限速与审计，
        # 直接暴露公网时 XFF 可伪造，不作为安全判定依据）
        for raw_key, raw_value in scope.get('headers') or []:
            if raw_key == b'x-forwarded-for':
                first = raw_value.decode('latin-1').split(',')[0].strip()
                if first:
                    return first
        client = scope.get('client')
        return client[0] if client else '-'

    @staticmethod
    async def _buffer_body(receive) -> Tuple[Optional[bytes], object, bool]:
        """读取并缓冲完整请求体，返回 (body, 重放receive, 是否断开)"""
        chunks = []
        total = 0
        while True:
            message = await receive()
            if message.get('type') == 'http.disconnect':
                return None, receive, True
            chunk = message.get('body', b'')
            total += len(chunk)
            if total > MAX_BUFFERED_BODY_BYTES:
                logger.warning("请求体超过缓冲上限 %d 字节，拒绝", MAX_BUFFERED_BODY_BYTES)
                return None, receive, True
            chunks.append(chunk)
            if not message.get('more_body', False):
                break
        body = b''.join(chunks)
        return body, _ReplayReceive(body), False

    def _audit(self, event: str, scope, client_ip: str, *,
               identity: Optional[AuthIdentity] = None,
               reason: Optional[str] = None,
               headers: Optional[Dict[str, str]] = None,
               session_id: Optional[str] = None) -> None:
        """审计日志：只记录凭据指纹，严禁记录 Token/签名原文"""
        fingerprint = identity.credential_fingerprint if identity else '-'
        if not identity and headers:
            auth_header = headers.get('authorization', '')
            if auth_header[:7].lower() == 'bearer ':
                fingerprint = credential_fingerprint(auth_header[7:].strip())
            elif HEADER_SIGNATURE in headers:
                fingerprint = credential_fingerprint(headers.get('x-auth-key', ''))
        level = logging.INFO if event == 'AUTH OK' else logging.WARNING
        logger.log(
            level,
            "%s method=%s path=%s ip=%s client_id=%s fp=%s session=%s reason=%s",
            event, scope.get('method'), scope.get('path'), client_ip,
            identity.client_id if identity else '-', fingerprint,
            session_id or '-', reason or '-',
        )

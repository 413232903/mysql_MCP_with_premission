"""MCP 服务传输层鉴权包（安全整改：Header 鉴权，禁止明文参数校验）

- AuthMiddleware: 纯 ASGI 鉴权中间件，Bearer Token + HMAC 签名双模式，
  在 MCP 会话建立前拦截未授权请求（覆盖 GET /sse2 与 POST /messages/）
- HealthApp: 鉴权外置的探活路由
- AuthIdentity / get_current_identity / resolve_user_id: 鉴权身份上下文，
  行级权限 user_id 以凭据绑定值为准（防明文入参伪造）
- TokenStore / HmacVerifier: 凭据校验（只存哈希 / 密钥不上网，fail-closed）
- NonceCache: 防重放

本包仅依赖标准库（aiomysql 仅在 db 凭据后端内部延迟导入），
可独立于数据库环境进行单元测试。
"""
from .health import HealthApp
from .hmac_verifier import (HmacVerifier, build_string_to_sign,
                            canonical_query_string, compute_signature)
from .identity import (AuthIdentity, SessionIdentityRegistry,
                       UserIdentityMismatchError, credential_fingerprint,
                       get_current_identity, get_session_registry,
                       reset_identity, resolve_user_id, set_identity)
from .middleware import AuthMiddleware
from .nonce_cache import NonceCache
from .settings import AuthSettings
from .token_store import TokenRecord, TokenStore, hash_token, parse_env_tokens

__all__ = [
    'AuthMiddleware',
    'HealthApp',
    'AuthSettings',
    'AuthIdentity',
    'UserIdentityMismatchError',
    'SessionIdentityRegistry',
    'get_session_registry',
    'get_current_identity',
    'set_identity',
    'reset_identity',
    'resolve_user_id',
    'credential_fingerprint',
    'TokenStore',
    'TokenRecord',
    'hash_token',
    'parse_env_tokens',
    'HmacVerifier',
    'build_string_to_sign',
    'compute_signature',
    'canonical_query_string',
    'NonceCache',
]

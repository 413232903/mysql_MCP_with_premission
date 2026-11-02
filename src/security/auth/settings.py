"""鉴权配置快照数据结构

与 src/config.py 的环境变量解析解耦：AuthConfig.get_config() 构建本对象，
中间件与测试代码均只依赖 AuthSettings，便于单元测试直接构造。
"""
from dataclasses import dataclass, field
from typing import FrozenSet


@dataclass(frozen=True)
class AuthSettings:
    """鉴权中间件运行参数"""
    enabled: bool = True
    # token | hmac | both
    mode: str = 'both'
    # off | audit | enforce
    enforce_mode: str = 'enforce'
    # env | db
    token_backend: str = 'env'
    # client_id:token_sha256_hex[:user_id][:expires_at][:scopes]，分号分隔
    tokens_str: str = ''
    token_table: str = 'mcp_auth_token'
    # app_key:app_secret[:client_id][:user_id][:scopes]，分号分隔
    hmac_keys_str: str = ''
    hmac_key_table: str = 'mcp_auth_key'
    timestamp_tolerance: int = 300
    nonce_ttl: int = 600
    exempt_paths: FrozenSet[str] = field(default_factory=lambda: frozenset({'/health'}))
    bind_user: bool = True
    max_failures: int = 10
    block_seconds: int = 600
    credential_cache_ttl: int = 60

    @property
    def token_enabled(self) -> bool:
        return self.mode in ('token', 'both')

    @property
    def hmac_enabled(self) -> bool:
        return self.mode in ('hmac', 'both')

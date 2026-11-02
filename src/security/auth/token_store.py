"""Bearer Token 凭据存储与校验

安全原则：
- 服务端只存 Token 的 SHA-256 哈希，永不存明文（.env / DB 均如此）
- 比对使用 hmac.compare_digest 恒定时间比较，防时序侧信道
- db 后端查询异常时 fail-closed（按认证失败处理），绝不放行
"""
import hashlib
import hmac as _hmac
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .settings import AuthSettings

logger = logging.getLogger("mysql_server")

_IDENT_RE = re.compile(r'^[A-Za-z0-9_]+$')           # SQL 标识符（表名）
_CLIENT_ID_RE = re.compile(r'^[A-Za-z0-9_.\-]+$')    # 调用方标识（允许连字符，如 bailian-prod）


@dataclass(frozen=True)
class TokenRecord:
    """一条有效的 Token 凭据记录"""
    client_id: str
    token_hash: str
    user_id: Optional[str] = None
    scopes: Tuple[str, ...] = ('query',)
    # unix 时间戳；None 表示不过期（建议配置有效期并定期轮换）
    expires_at: Optional[float] = None

    def is_valid(self, now: Optional[float] = None) -> bool:
        if self.expires_at is not None and (time.time() if now is None else now) >= self.expires_at:
            return False
        return True


def hash_token(token: str) -> str:
    """Token 明文 → SHA-256 hex（服务端存储/比对的唯一形态）"""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _parse_expires(value: str) -> Optional[float]:
    """支持 unix 时间戳或 YYYY-MM-DD[ HH:MM:SS] 格式"""
    value = value.strip()
    if not value:
        return None
    if value.isdigit():
        return float(value)
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, fmt).timestamp()
        except ValueError:
            continue
    raise ValueError(f"无法识别的过期时间格式: {value}")


def _parse_scopes(value: str) -> Tuple[str, ...]:
    scopes = tuple(s.strip() for s in value.split(',') if s.strip())
    return scopes or ('query',)


def parse_env_tokens(tokens_str: str) -> List[TokenRecord]:
    """解析 AUTH_TOKENS 环境配置

    格式: client_id:token_sha256_hex[:user_id][:expires_at][:scopes]
    多组用分号分隔；user_id/expires_at 留空表示不配置（注意保留冒号占位）。
    """
    records: List[TokenRecord] = []
    for entry in (e.strip() for e in tokens_str.split(';')):
        if not entry:
            continue
        parts = entry.split(':')
        if len(parts) < 2:
            logger.warning("AUTH_TOKENS 配置项格式错误(缺少哈希)，已忽略: %s", entry.split(':')[0])
            continue
        client_id = parts[0].strip()
        token_hash = parts[1].strip().lower()
        if not _CLIENT_ID_RE.match(client_id) or len(token_hash) != 64 or not all(
                c in '0123456789abcdef' for c in token_hash):
            logger.warning("AUTH_TOKENS 配置项非法(client_id 或 64位SHA-256哈希不合法)，已忽略: %s", client_id)
            continue
        user_id = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
        try:
            expires_at = _parse_expires(parts[3]) if len(parts) > 3 else None
        except ValueError as exc:
            logger.warning("AUTH_TOKENS 配置项 %s 过期时间非法，已忽略: %s", client_id, exc)
            continue
        scopes = _parse_scopes(parts[4]) if len(parts) > 4 else ('query',)
        records.append(TokenRecord(client_id, token_hash, user_id, scopes, expires_at))
    return records


class TokenStore:
    """Bearer Token 存储：env / db 两种后端，带 TTL 缓存"""

    def __init__(self, settings: AuthSettings):
        self.settings = settings
        self._env_records: List[TokenRecord] = parse_env_tokens(settings.tokens_str)
        # db 后端缓存: token_hash -> (缓存过期时刻, 记录|None)；None 为负缓存，防无效token打库
        self._cache: Dict[str, Tuple[float, Optional[TokenRecord]]] = {}
        if settings.token_backend == 'env' and settings.enabled:
            logger.info("Token 存储(env后端)已加载 %d 条凭据", len(self._env_records))

    async def lookup(self, token: str) -> Optional[TokenRecord]:
        """按 Token 明文查找有效记录；不存在/过期返回 None"""
        if not token:
            return None
        digest = hash_token(token)
        if self.settings.token_backend == 'db':
            record = await self._db_lookup(digest)
        else:
            record = self._env_lookup(digest)
        if record is not None and not record.is_valid():
            logger.info("Token 已过期: client=%s fp=%s", record.client_id, digest[:8])
            return None
        return record

    def _env_lookup(self, digest: str) -> Optional[TokenRecord]:
        for record in self._env_records:
            if _hmac.compare_digest(record.token_hash, digest):
                return record
        return None

    async def _db_lookup(self, digest: str) -> Optional[TokenRecord]:
        now = time.time()
        cached = self._cache.get(digest)
        if cached is not None and cached[0] > now:
            return cached[1]
        record = await self._db_fetch(digest)
        self._cache[digest] = (now + self.settings.credential_cache_ttl, record)
        if len(self._cache) > 10000:
            self._prune_cache(now)
        return record

    def _prune_cache(self, now: float) -> None:
        for key in [k for k, (exp, _) in self._cache.items() if exp <= now]:
            self._cache.pop(key, None)

    async def _db_fetch(self, digest: str) -> Optional[TokenRecord]:
        table = self.settings.token_table
        if not _IDENT_RE.match(table):
            logger.error("AUTH_TOKEN_TABLE 表名非法: %s", table)
            return None
        try:
            import aiomysql  # 延迟导入：env 后端无需 aiomysql
            from src.db.mysql_operations import get_db_connection
            sql = (f"SELECT client_id, user_id, scopes, expires_at, revoked "
                   f"FROM `{table}` WHERE token_hash = %s LIMIT 1")
            async with get_db_connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(sql, (digest,))
                    row = await cur.fetchone()
        except Exception as exc:
            # fail-closed：DB 异常按认证失败处理，服务返回401而不是放行
            logger.error("查询 Token 表失败，按认证失败处理: %s", exc)
            return None
        if not row:
            return None
        if row.get('revoked'):
            logger.info("Token 已吊销: client=%s fp=%s", row.get('client_id'), digest[:8])
            return None
        expires_at = row['expires_at'].timestamp() if row.get('expires_at') else None
        return TokenRecord(
            client_id=row['client_id'],
            token_hash=digest,
            user_id=row.get('user_id') or None,
            scopes=_parse_scopes(row.get('scopes') or ''),
            expires_at=expires_at,
        )

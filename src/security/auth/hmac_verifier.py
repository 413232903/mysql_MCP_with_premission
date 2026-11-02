"""HMAC-SHA256 签名校验（时间窗 + Nonce 防重放）

签名规范（客户端必须严格一致，参见 examples/client_with_auth.py）：

    StringToSign = METHOD + "\\n"          # 大写，如 GET / POST
                 + Path + "\\n"            # 不含 query，如 /sse2
                 + SortedQuery + "\\n"     # query 按 key 字典序规范化 k=v&k=v，无则空串
                 + Timestamp + "\\n"       # unix 秒
                 + Nonce + "\\n"           # 单次随机串（建议 UUID）
                 + SHA256Hex(Body)         # 无 body 时对空串取哈希
    Signature    = Base64(HMAC-SHA256(AppSecret, StringToSign))

请求头：X-Auth-Key / X-Auth-Timestamp / X-Auth-Nonce / X-Auth-Signature
AppSecret 永不离开客户端，网络上不出现任何明文密钥。
"""
import base64
import binascii
import hashlib
import hmac as _hmac
import logging
import re
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qsl, urlencode

from .identity import AuthIdentity, credential_fingerprint
from .nonce_cache import NonceCache
from .settings import AuthSettings

logger = logging.getLogger("mysql_server")

HEADER_KEY = 'x-auth-key'
HEADER_TIMESTAMP = 'x-auth-timestamp'
HEADER_NONCE = 'x-auth-nonce'
HEADER_SIGNATURE = 'x-auth-signature'

_IDENT_RE = re.compile(r'^[A-Za-z0-9_]+$')
_TIMESTAMP_RE = re.compile(r'^\d{1,20}$')


@dataclass(frozen=True)
class HmacKeyRecord:
    """一条 HMAC 签名密钥记录"""
    app_key: str
    secret: str
    client_id: str
    user_id: Optional[str] = None
    scopes: Tuple[str, ...] = ('query',)


def canonical_query_string(query_string: str) -> str:
    """按 key 字典序规范化 query string（签名用，空则返回空串）"""
    if not query_string:
        return ''
    pairs = parse_qsl(query_string, keep_blank_values=True)
    return urlencode(sorted(pairs))


def build_string_to_sign(method: str, path: str, query_string: str,
                         timestamp: str, nonce: str, body: bytes) -> str:
    """构建规范化签名串（客户端与服务端共用同一规范）"""
    body_hash = hashlib.sha256(body or b'').hexdigest()
    return '\n'.join([
        method.upper(),
        path,
        canonical_query_string(query_string),
        str(timestamp),
        nonce,
        body_hash,
    ])


def compute_signature(secret: str, string_to_sign: str) -> str:
    digest = _hmac.new(secret.encode('utf-8'),
                       string_to_sign.encode('utf-8'),
                       hashlib.sha256).digest()
    return base64.b64encode(digest).decode('ascii')


def parse_env_keys(keys_str: str) -> Dict[str, HmacKeyRecord]:
    """解析 AUTH_HMAC_KEYS 环境配置

    格式: app_key:app_secret[:client_id][:user_id][:scopes]，多组用分号分隔；
    client_id 缺省时使用 app_key。
    """
    records: Dict[str, HmacKeyRecord] = {}
    for entry in (e.strip() for e in keys_str.split(';')):
        if not entry:
            continue
        parts = entry.split(':')
        if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
            logger.warning("AUTH_HMAC_KEYS 配置项格式错误，已忽略: %s", entry[:16] + '...')
            continue
        app_key = parts[0].strip()
        secret = parts[1].strip()
        client_id = parts[2].strip() if len(parts) > 2 and parts[2].strip() else app_key
        user_id = parts[3].strip() if len(parts) > 3 and parts[3].strip() else None
        scopes: Tuple[str, ...] = ('query',)
        if len(parts) > 4 and parts[4].strip():
            scopes = tuple(s.strip() for s in parts[4].split(',') if s.strip()) or ('query',)
        records[app_key] = HmacKeyRecord(app_key, secret, client_id, user_id, scopes)
    return records


class HmacVerifier:
    """HMAC 签名校验器：时间窗检查 → 密钥查找 → 签名比对 → Nonce 登记"""

    def __init__(self, settings: AuthSettings, nonce_cache: Optional[NonceCache] = None):
        self.settings = settings
        self._env_keys = parse_env_keys(settings.hmac_keys_str)
        self._nonce_cache = nonce_cache or NonceCache(ttl=settings.nonce_ttl)
        # db 后端密钥缓存: app_key -> (缓存过期时刻, 记录|None)
        self._key_cache: Dict[str, Tuple[float, Optional[HmacKeyRecord]]] = {}
        if settings.token_backend == 'env' and settings.enabled and self._env_keys:
            logger.info("HMAC 密钥(env后端)已加载 %d 条", len(self._env_keys))

    async def verify(self, *, method: str, path: str, query_string: str,
                     body: bytes, headers: Dict[str, str]) -> Tuple[Optional[AuthIdentity], str]:
        """校验请求签名，返回 (身份, '') 或 (None, 失败原因码)

        失败原因码仅用于内部审计日志，不返回给客户端（避免反馈信道）。
        """
        app_key = headers.get(HEADER_KEY, '').strip()
        timestamp = headers.get(HEADER_TIMESTAMP, '').strip()
        nonce = headers.get(HEADER_NONCE, '').strip()
        signature = headers.get(HEADER_SIGNATURE, '').strip()

        if not (app_key and timestamp and nonce and signature):
            return None, 'hmac_headers_incomplete'
        if not _TIMESTAMP_RE.match(timestamp):
            return None, 'invalid_timestamp_format'
        if len(nonce) > 128:
            return None, 'invalid_nonce'

        # 1) 时间窗检查（防重放第一道）
        now = time.time()
        try:
            ts = int(timestamp)
        except ValueError:
            return None, 'invalid_timestamp_format'
        if abs(now - ts) > self.settings.timestamp_tolerance:
            return None, 'timestamp_out_of_window'

        # 2) 查找密钥
        record = await self._lookup_key(app_key)
        if record is None:
            return None, 'unknown_or_revoked_app_key'

        # 3) 重算签名并恒定时间比对（签名为 Base64 字符串，直接比对编码结果）
        string_to_sign = build_string_to_sign(method, path, query_string, timestamp, nonce, body)
        expected = compute_signature(record.secret, string_to_sign)
        try:
            base64.b64decode(signature, validate=True)
        except (binascii.Error, ValueError):
            return None, 'malformed_signature'
        if not _hmac.compare_digest(expected, signature):
            return None, 'signature_mismatch'

        # 4) 签名通过后才登记 Nonce（防止攻击者用伪造签名抢占消耗合法 Nonce）
        if not self._nonce_cache.check_and_add(f"{app_key}:{nonce}", now=now):
            return None, 'nonce_replayed'

        identity = AuthIdentity(
            client_id=record.client_id,
            auth_mode='hmac',
            user_id=record.user_id,
            scopes=record.scopes,
            credential_fingerprint=credential_fingerprint(app_key),
        )
        return identity, ''

    async def _lookup_key(self, app_key: str) -> Optional[HmacKeyRecord]:
        if self.settings.token_backend == 'db':
            return await self._db_lookup(app_key)
        return self._env_keys.get(app_key)

    async def _db_lookup(self, app_key: str) -> Optional[HmacKeyRecord]:
        now = time.time()
        cached = self._key_cache.get(app_key)
        if cached is not None and cached[0] > now:
            return cached[1]
        record = await self._db_fetch(app_key)
        if len(self._key_cache) < 10000:
            self._key_cache[app_key] = (now + self.settings.credential_cache_ttl, record)
        return record

    async def _db_fetch(self, app_key: str) -> Optional[HmacKeyRecord]:
        table = self.settings.hmac_key_table
        if not _IDENT_RE.match(table):
            logger.error("AUTH_HMAC_KEY_TABLE 表名非法: %s", table)
            return None
        try:
            import aiomysql  # 延迟导入
            from src.db.mysql_operations import get_db_connection
            sql = (f"SELECT app_key, app_secret, client_id, user_id, scopes, revoked "
                   f"FROM `{table}` WHERE app_key = %s LIMIT 1")
            async with get_db_connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(sql, (app_key,))
                    row = await cur.fetchone()
        except Exception as exc:
            # fail-closed：DB 异常按认证失败处理
            logger.error("查询 HMAC 密钥表失败，按认证失败处理: %s", exc)
            return None
        if not row or row.get('revoked'):
            return None
        scopes: Tuple[str, ...] = ('query',)
        if row.get('scopes'):
            scopes = tuple(s.strip() for s in row['scopes'].split(',') if s.strip()) or ('query',)
        return HmacKeyRecord(
            app_key=row['app_key'],
            secret=row['app_secret'],
            client_id=row.get('client_id') or row['app_key'],
            user_id=row.get('user_id') or None,
            scopes=scopes,
        )

"""鉴权模块单元测试（安全整改：传输层 Header 鉴权）

仅依赖标准库 + pytest，无需数据库、无需真实启动服务器。
运行: python -m pytest tests/test_auth.py -v

覆盖:
- Bearer Token: 有效/缺失/错误/过期/审计模式/off模式/豁免路径
- HMAC 签名: 有效/篡改body/时间戳超窗/Nonce重放/错误密钥/未知Key/非法签名
- 会话绑定: session_id 与 client_id 强绑定，防会话混用
- 防爆破: 连续失败封禁 429
- 身份解析: resolve_user_id 凭据优先，入参伪造被拒绝
- 审计安全: 日志不出现凭据明文
- db 后端 fail-closed: 数据库不可用时按认证失败处理
"""
import asyncio
import hashlib
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from src.security.auth import (AuthIdentity, AuthMiddleware, AuthSettings, HealthApp,
                               NonceCache, UserIdentityMismatchError,
                               build_string_to_sign, canonical_query_string,
                               compute_signature, credential_fingerprint,
                               get_current_identity, get_session_registry,
                               hash_token, parse_env_tokens, reset_identity,
                               resolve_user_id, set_identity)
from src.security.auth.hmac_verifier import (HEADER_KEY, HEADER_NONCE,
                                             HEADER_SIGNATURE, HEADER_TIMESTAMP,
                                             HmacVerifier, parse_env_keys)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# 测试凭据
# --------------------------------------------------------------------------
TOKEN_A = 'test-token-aaa-PLAINTEXT-do-not-log'
TOKEN_B = 'test-token-bbb-PLAINTEXT-do-not-log'
HASH_A = hash_token(TOKEN_A)
HASH_B = hash_token(TOKEN_B)

APP_KEY = 'ak_test'
APP_SECRET = 'secret_test'


@pytest.fixture(autouse=True)
def _clear_session_registry():
    get_session_registry().clear()
    yield
    get_session_registry().clear()


def make_settings(**overrides) -> AuthSettings:
    base = dict(
        enabled=True,
        mode='both',
        enforce_mode='enforce',
        token_backend='env',
        tokens_str=f"client-a:{HASH_A}:user_a;client-b:{HASH_B}",
        hmac_keys_str=f"{APP_KEY}:{APP_SECRET}:client-h:user_h",
        max_failures=100,
        block_seconds=60,
    )
    base.update(overrides)
    return AuthSettings(**base)


# --------------------------------------------------------------------------
# 纯 ASGI 测试挂具
# --------------------------------------------------------------------------
def make_scope(method='GET', path='/sse2', query_string=b'', headers=None,
               client=('9.9.9.9', 40000)):
    raw_headers = [(k.lower().encode('latin-1'), v.encode('latin-1'))
                   for k, v in (headers or {}).items()]
    return {
        'type': 'http', 'http_version': '1.1', 'method': method,
        'path': path, 'raw_path': path.encode(), 'query_string': query_string,
        'headers': raw_headers, 'client': client,
        'server': ('127.0.0.1', 3000), 'scheme': 'http', 'root_path': '',
    }


class FakeReceive:
    def __init__(self, body=b''):
        self._pending = [{'type': 'http.request', 'body': body, 'more_body': False}]

    async def __call__(self):
        if self._pending:
            return self._pending.pop(0)
        return {'type': 'http.disconnect'}


class FakeSend:
    def __init__(self):
        self.messages = []

    async def __call__(self, message):
        self.messages.append(message)

    @property
    def status(self):
        for m in self.messages:
            if m['type'] == 'http.response.start':
                return m['status']
        return None

    def json_body(self):
        for m in self.messages:
            if m['type'] == 'http.response.body':
                return json.loads(m.get('body') or b'{}')
        return None

    def header(self, name):
        for m in self.messages:
            if m['type'] == 'http.response.start':
                for k, v in m.get('headers') or []:
                    if k.decode('latin-1').lower() == name.lower():
                        return v.decode('latin-1')
        return None


def echo_app():
    """下游应用: 记录可见身份并读取请求体（验证 receive 重放）"""
    seen = {}

    async def app(scope, receive, send):
        seen['scope_identity'] = scope.get('auth_identity')
        seen['ctx_identity'] = get_current_identity()
        message = await receive()
        seen['body'] = message.get('body', b'')
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'ok'})

    return app, seen


class Harness:
    """固定中间件实例，支持多次请求（重放/封禁等跨请求场景）"""

    def __init__(self, settings=None):
        self.downstream, self.seen = echo_app()
        self.mw = AuthMiddleware(self.downstream, settings=settings or make_settings())

    def request(self, scope, body=b''):
        self.seen.clear()
        send = FakeSend()
        asyncio.run(self.mw(scope, FakeReceive(body), send))
        return send


def hmac_headers(method='GET', path='/sse2', query='', body=b'',
                 timestamp=None, nonce=None, key=APP_KEY, secret=APP_SECRET,
                 signature=None):
    timestamp = str(int(time.time())) if timestamp is None else timestamp
    nonce = str(uuid.uuid4()) if nonce is None else nonce
    if signature is None:
        string_to_sign = build_string_to_sign(method, path, query, timestamp, nonce, body)
        signature = compute_signature(secret, string_to_sign)
    return {
        HEADER_KEY: key,
        HEADER_TIMESTAMP: timestamp,
        HEADER_NONCE: nonce,
        HEADER_SIGNATURE: signature,
    }


def bearer(token):
    return {'Authorization': f'Bearer {token}'}


# ==========================================================================
# Bearer Token 模式
# ==========================================================================
class TestBearerToken:
    def test_valid_token_passes_and_injects_identity(self):
        h = Harness()
        send = h.request(make_scope(headers=bearer(TOKEN_A)))
        assert send.status == 200
        identity = h.seen['ctx_identity']
        assert isinstance(identity, AuthIdentity)
        assert identity.client_id == 'client-a'
        assert identity.user_id == 'user_a'
        assert identity.auth_mode == 'token'
        # scope 中也注入了身份（供框架层使用）
        assert h.seen['scope_identity'] is identity

    def test_missing_credentials_401_with_www_authenticate(self):
        h = Harness()
        send = h.request(make_scope())
        assert send.status == 401
        assert send.json_body() == {'error': 'unauthorized'}
        assert 'Bearer' in (send.header('WWW-Authenticate') or '')
        # 下游应用未被调用
        assert 'ctx_identity' not in h.seen

    def test_invalid_token_401(self):
        h = Harness()
        send = h.request(make_scope(headers=bearer('totally-wrong-token')))
        assert send.status == 401

    def test_expired_token_401(self):
        expired = f"client-x:{hash_token('tok-x')}::1000000000"  # 2001年过期
        h = Harness(make_settings(tokens_str=expired))
        send = h.request(make_scope(headers=bearer('tok-x')))
        assert send.status == 401

    def test_audit_mode_allows_without_credentials(self):
        h = Harness(make_settings(enforce_mode='audit'))
        send = h.request(make_scope())
        assert send.status == 200
        # 放行但不注入身份（保持旧行为）
        assert h.seen['ctx_identity'] is None

    def test_off_mode_bypasses(self):
        h = Harness(make_settings(enforce_mode='off'))
        send = h.request(make_scope())
        assert send.status == 200

    def test_exempt_path_passthrough(self):
        h = Harness()
        send = h.request(make_scope(path='/health'))
        assert send.status == 200

    def test_token_mode_ignores_hmac_headers(self):
        h = Harness(make_settings(mode='token'))
        headers = hmac_headers()
        send = h.request(make_scope(headers=headers))
        assert send.status == 401


# ==========================================================================
# HMAC 签名模式
# ==========================================================================
class TestHmacSignature:
    def test_valid_signature_get(self):
        h = Harness()
        send = h.request(make_scope(headers=hmac_headers()))
        assert send.status == 200
        identity = h.seen['ctx_identity']
        assert identity.client_id == 'client-h'
        assert identity.user_id == 'user_h'
        assert identity.auth_mode == 'hmac'

    def test_valid_signature_post_body_replayed_to_downstream(self):
        h = Harness()
        body = b'{"jsonrpc":"2.0","id":1}'
        query = 'session_id=s-post'
        headers = hmac_headers(method='POST', path='/messages/', query=query, body=body)
        send = h.request(make_scope(method='POST', path='/messages/',
                                    query_string=query.encode(), headers=headers),
                         body=body)
        assert send.status == 200
        # 中间件缓冲验签后，下游仍能完整读到请求体
        assert h.seen['body'] == body

    def test_tampered_body_401(self):
        h = Harness()
        # 用原始 body 签名，实际发送被篡改的 body → 验签失败
        headers = hmac_headers(method='POST', path='/messages/', body=b'{"q":"original"}')
        send = h.request(make_scope(method='POST', path='/messages/', headers=headers),
                         body=b'{"q":"TAMPERED"}')
        assert send.status == 401

    def test_expired_timestamp_401(self):
        h = Harness()
        stale = str(int(time.time()) - 3600)  # 超出默认 ±300s 窗口
        headers = hmac_headers(timestamp=stale)
        send = h.request(make_scope(headers=headers))
        assert send.status == 401

    def test_nonce_replay_401(self):
        h = Harness()
        nonce = str(uuid.uuid4())
        first = hmac_headers(nonce=nonce)
        assert h.request(make_scope(headers=first)).status == 200
        # 完全相同的请求重放（时间戳仍在窗口内）
        replay = dict(first)
        send = h.request(make_scope(headers=replay))
        assert send.status == 401

    def test_failed_signature_does_not_consume_nonce(self):
        """伪造签名的请求不能抢占消耗合法 Nonce"""
        h = Harness()
        nonce = str(uuid.uuid4())
        forged = hmac_headers(nonce=nonce, secret='wrong-secret')
        assert h.request(make_scope(headers=forged)).status == 401
        legit = hmac_headers(nonce=nonce)
        assert h.request(make_scope(headers=legit)).status == 200

    def test_wrong_secret_401(self):
        h = Harness()
        send = h.request(make_scope(headers=hmac_headers(secret='wrong')))
        assert send.status == 401

    def test_unknown_app_key_401(self):
        h = Harness()
        send = h.request(make_scope(headers=hmac_headers(key='ak_unknown')))
        assert send.status == 401

    def test_malformed_signature_401(self):
        h = Harness()
        headers = hmac_headers(signature='!!!not-valid-base64!!!')
        send = h.request(make_scope(headers=headers))
        assert send.status == 401

    def test_query_string_participates_in_signature(self):
        h = Harness()
        query = 'session_id=abc'
        headers = hmac_headers(method='POST', path='/messages/', query=query)
        # 用别的 query 发起请求 → 验签失败
        send = h.request(make_scope(method='POST', path='/messages/',
                                    query_string=b'session_id=other', headers=headers))
        assert send.status == 401

    def test_hmac_mode_ignores_bearer(self):
        h = Harness(make_settings(mode='hmac'))
        send = h.request(make_scope(headers=bearer(TOKEN_A)))
        assert send.status == 401


# ==========================================================================
# 会话绑定
# ==========================================================================
class TestSessionBinding:
    def test_same_client_same_session_allowed(self):
        h = Harness()
        scope = make_scope(method='POST', path='/messages/',
                           query_string=b'session_id=s-1', headers=bearer(TOKEN_A))
        assert h.request(scope).status == 200
        assert h.request(scope).status == 200

    def test_other_client_same_session_forbidden(self):
        h = Harness()
        scope_a = make_scope(method='POST', path='/messages/',
                             query_string=b'session_id=s-2', headers=bearer(TOKEN_A))
        assert h.request(scope_a).status == 200
        # client-b 持有效凭据向 client-a 的会话投递消息 → 403
        scope_b = make_scope(method='POST', path='/messages/',
                             query_string=b'session_id=s-2', headers=bearer(TOKEN_B))
        send = h.request(scope_b)
        assert send.status == 403
        assert send.json_body() == {'error': 'forbidden'}

    def test_session_without_id_not_bound(self):
        h = Harness()
        scope = make_scope(method='POST', path='/messages/', headers=bearer(TOKEN_A))
        assert h.request(scope).status == 200


# ==========================================================================
# 防爆破
# ==========================================================================
class TestRateLimit:
    def test_blocked_after_max_failures(self):
        h = Harness(make_settings(max_failures=3, block_seconds=600))
        for _ in range(3):
            send = h.request(make_scope(headers=bearer('bad-token'),
                                        client=('7.7.7.7', 1)))
            assert send.status == 401
        # 封禁期内即使携带有效凭据也被拒绝
        send = h.request(make_scope(headers=bearer(TOKEN_A), client=('7.7.7.7', 1)))
        assert send.status == 429
        assert send.json_body() == {'error': 'too_many_requests'}
        # 其他 IP 不受影响
        send = h.request(make_scope(headers=bearer(TOKEN_A), client=('8.8.8.8', 1)))
        assert send.status == 200

    def test_success_resets_failure_counter(self):
        h = Harness(make_settings(max_failures=3, block_seconds=600))
        ip = ('6.6.6.6', 1)
        h.request(make_scope(headers=bearer('bad'), client=ip))
        h.request(make_scope(headers=bearer('bad'), client=ip))
        assert h.request(make_scope(headers=bearer(TOKEN_A), client=ip)).status == 200
        # 计数已重置：再失败 2 次不会触发封禁
        h.request(make_scope(headers=bearer('bad'), client=ip))
        h.request(make_scope(headers=bearer('bad'), client=ip))
        assert h.request(make_scope(headers=bearer(TOKEN_A), client=ip)).status == 200


# ==========================================================================
# db 后端 fail-closed
# ==========================================================================
class TestDbBackendFailClosed:
    def test_db_unavailable_denies_access(self):
        """db 后端查询异常（含依赖缺失/连不上库）时按认证失败处理，绝不放行"""
        h = Harness(make_settings(token_backend='db'))
        send = h.request(make_scope(headers=bearer(TOKEN_A)))
        assert send.status == 401


# ==========================================================================
# 纯函数单元测试
# ==========================================================================
class TestPureFunctions:
    def test_canonical_query_string_sorted(self):
        assert canonical_query_string('b=2&a=1') == 'a=1&b=2'
        assert canonical_query_string('') == ''
        assert canonical_query_string('a=&b=1') == 'a=&b=1'

    def test_build_string_to_sign_layout(self):
        sts = build_string_to_sign('post', '/messages/', 'b=2&a=1',
                                   '1700000000', 'n1', b'body')
        lines = sts.split('\n')
        assert lines[0] == 'POST'
        assert lines[1] == '/messages/'
        assert lines[2] == 'a=1&b=2'
        assert lines[3] == '1700000000'
        assert lines[4] == 'n1'
        assert lines[5] == hashlib.sha256(b'body').hexdigest()

    def test_nonce_cache_ttl_and_replay(self):
        cache = NonceCache(ttl=100)
        assert cache.check_and_add('n1', now=1000.0) is True
        assert cache.check_and_add('n1', now=1050.0) is False   # 窗口内重放
        assert cache.check_and_add('n1', now=1200.0) is True    # 已过期

    def test_parse_env_tokens_skips_malformed(self):
        records = parse_env_tokens(f"good:{HASH_A}:u1;nohash;short:notahash;{''}")
        assert len(records) == 1
        assert records[0].client_id == 'good'
        assert records[0].user_id == 'u1'

    def test_parse_env_tokens_scopes(self):
        records = parse_env_tokens(f"c:{HASH_A}:::query,admin")
        assert records[0].scopes == ('query', 'admin')

    def test_parse_env_keys(self):
        keys = parse_env_keys(f"{APP_KEY}:{APP_SECRET}:cid:uid;bad-entry")
        assert APP_KEY in keys
        assert keys[APP_KEY].client_id == 'cid'
        assert keys[APP_KEY].user_id == 'uid'
        assert len(keys) == 1

    def test_credential_fingerprint_is_safe(self):
        fp = credential_fingerprint(TOKEN_A)
        assert len(fp) == 8
        assert TOKEN_A not in fp
        assert fp == credential_fingerprint(TOKEN_A)  # 确定性

    def test_compute_signature_deterministic(self):
        s1 = compute_signature('sec', 'data')
        s2 = compute_signature('sec', 'data')
        assert s1 == s2
        assert compute_signature('other', 'data') != s1


# ==========================================================================
# 身份解析（行级权限 user_id 防伪）
# ==========================================================================
class TestResolveUserId:
    def test_no_identity_falls_back_to_param(self):
        assert resolve_user_id('param_user') == 'param_user'
        assert resolve_user_id(None) is None

    def test_identity_user_id_wins(self, monkeypatch):
        import src.config as config
        monkeypatch.setattr(config.AuthConfig, 'BIND_USER', True)
        identity = AuthIdentity(client_id='c', auth_mode='token', user_id='bound_user')
        token = set_identity(identity)
        try:
            assert resolve_user_id(None) == 'bound_user'
            assert resolve_user_id('bound_user') == 'bound_user'
        finally:
            reset_identity(token)

    def test_spoofed_user_id_rejected(self, monkeypatch):
        import src.config as config
        monkeypatch.setattr(config.AuthConfig, 'BIND_USER', True)
        identity = AuthIdentity(client_id='c', auth_mode='token', user_id='bound_user')
        token = set_identity(identity)
        try:
            with pytest.raises(UserIdentityMismatchError):
                resolve_user_id('other_user')
        finally:
            reset_identity(token)

    def test_bind_disabled_param_wins(self, monkeypatch):
        import src.config as config
        monkeypatch.setattr(config.AuthConfig, 'BIND_USER', False)
        identity = AuthIdentity(client_id='c', auth_mode='token', user_id='bound_user')
        token = set_identity(identity)
        try:
            assert resolve_user_id('other_user') == 'other_user'
            assert resolve_user_id(None) == 'bound_user'
        finally:
            reset_identity(token)

    def test_identity_without_user_id_falls_back(self, monkeypatch):
        import src.config as config
        monkeypatch.setattr(config.AuthConfig, 'BIND_USER', True)
        identity = AuthIdentity(client_id='c', auth_mode='token', user_id=None)
        token = set_identity(identity)
        try:
            assert resolve_user_id('param_user') == 'param_user'
        finally:
            reset_identity(token)


# ==========================================================================
# 健康检查路由
# ==========================================================================
class TestHealthApp:
    def test_health_bypasses_auth(self):
        downstream, _ = echo_app()
        app = HealthApp(AuthMiddleware(downstream, settings=make_settings()))
        send = FakeSend()
        asyncio.run(app(make_scope(path='/health'), FakeReceive(), send))
        assert send.status == 200
        assert send.json_body() == {'status': 'ok'}

    def test_other_paths_still_require_auth(self):
        downstream, _ = echo_app()
        app = HealthApp(AuthMiddleware(downstream, settings=make_settings()))
        send = FakeSend()
        asyncio.run(app(make_scope(path='/sse2'), FakeReceive(), send))
        assert send.status == 401


# ==========================================================================
# 审计日志安全
# ==========================================================================
class TestAuditSafety:
    def test_failed_auth_log_has_no_plaintext(self, caplog):
        with caplog.at_level('DEBUG', logger='mysql_server'):
            h = Harness()
            h.request(make_scope(headers=bearer(TOKEN_A.replace('aaa', 'zzz'))))
        text = caplog.text
        assert 'AUTH FAILED' in text
        assert TOKEN_A.replace('aaa', 'zzz') not in text  # 明文凭据不落日志
        assert HASH_A not in text

    def test_successful_auth_log_has_fingerprint_only(self, caplog):
        with caplog.at_level('DEBUG', logger='mysql_server'):
            h = Harness()
            h.request(make_scope(headers=bearer(TOKEN_A)))
        text = caplog.text
        assert 'AUTH OK' in text
        assert TOKEN_A not in text
        assert credential_fingerprint(TOKEN_A) in text  # 指纹可用于审计关联


# ==========================================================================
# 凭据生成脚本
# ==========================================================================
class TestGenTokenScript:
    @staticmethod
    def _run_script(*args):
        # Windows 控制台默认 GBK，显式统一子进程与解码为 UTF-8
        import os
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        return subprocess.run(
            [sys.executable, str(PROJECT_ROOT / 'scripts' / 'gen_token.py'), *args],
            capture_output=True, text=True, encoding='utf-8', env=env, timeout=30)

    def test_hash_subcommand(self):
        result = self._run_script('hash', 'abc')
        assert result.returncode == 0
        assert result.stdout.strip() == hash_token('abc')

    def test_token_subcommand_outputs_hash_not_storing_plaintext(self):
        result = self._run_script(
            'token', '--client-id', 'unit-test', '--user-id', 'u1',
            '--expires', '2099-01-01')
        assert result.returncode == 0
        out = result.stdout
        assert 'unit-test' in out and 'AUTH_TOKENS' in out
        # env 配置行中只包含 64 位哈希
        import re
        env_line = [l.strip() for l in out.splitlines() if l.strip().startswith('unit-test:')]
        assert env_line, "应输出 .env 配置行"
        assert re.match(r'^unit-test:[0-9a-f]{64}:u1:2099-01-01$', env_line[0])

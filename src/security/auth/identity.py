"""鉴权身份上下文与会话绑定

- AuthIdentity: 鉴权通过后解析出的调用方身份（client_id + 绑定的 user_id）
- contextvar 注入: 中间件在 SSE 建连请求（GET /sse2）上设置身份，
  会话任务由该请求上下文派生，工具执行时可通过 get_current_identity() 读取
- SessionIdentityRegistry: session_id ↔ client_id 绑定，防止会话被其他凭据混用
- resolve_user_id: 数据库操作层解析行级权限 user_id 的唯一入口，
  凭据绑定的 user_id 优先，杜绝明文入参伪造（AUTH_BIND_USER）
"""
from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger("mysql_server")


class UserIdentityMismatchError(PermissionError):
    """工具入参 user_id 与鉴权凭据绑定的 user_id 不一致（疑似越权）"""
    pass


@dataclass(frozen=True)
class AuthIdentity:
    """鉴权通过的调用方身份"""
    client_id: str
    # 'token' | 'hmac'
    auth_mode: str
    # 绑定的行级权限用户（对应 fr_user_role.username），可为空
    user_id: Optional[str] = None
    scopes: Tuple[str, ...] = ('query',)
    # 凭据 SHA-256 前 8 位，仅用于审计日志关联，禁止记录凭据原文
    credential_fingerprint: str = ''

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


def credential_fingerprint(credential: str) -> str:
    """计算凭据审计指纹（SHA-256 前 8 位）。任何日志不得出现凭据原文。"""
    return hashlib.sha256(credential.encode('utf-8')).hexdigest()[:8]


# ---------------------------------------------------------------------------
# 请求上下文身份注入（contextvar 会传播到由当前请求派生的子任务，
# 因此 SSE 建连请求上设置的身份对该会话内所有工具调用可见）
# ---------------------------------------------------------------------------
_current_identity: ContextVar[Optional[AuthIdentity]] = ContextVar(
    'mcp_auth_identity', default=None)


def set_identity(identity: AuthIdentity) -> Token:
    return _current_identity.set(identity)


def reset_identity(token: Token) -> None:
    _current_identity.reset(token)


def get_current_identity() -> Optional[AuthIdentity]:
    """获取当前请求/会话的鉴权身份；无鉴权上下文（本地调试等）时返回 None"""
    return _current_identity.get()


# ---------------------------------------------------------------------------
# 会话身份绑定
# ---------------------------------------------------------------------------
class SessionIdentityRegistry:
    """session_id ↔ client_id 绑定表（LRU 容量上限，防止内存无限增长）

    MCP SSE 的 session_id 只是会话句柄而非凭据；本表确保同一会话
    只能由最初使用它的 client_id 继续投递消息，防止凭据 B 向
    凭据 A 的会话注入工具调用（水平越权/会话混用）。
    """

    def __init__(self, maxsize: int = 10000):
        self._maxsize = maxsize
        self._bindings: "OrderedDict[str, str]" = OrderedDict()
        self._lock = threading.Lock()

    def bind_or_verify(self, session_id: str, client_id: str) -> bool:
        """首次出现则绑定并返回 True；已绑定时仅同一 client_id 返回 True"""
        with self._lock:
            existing = self._bindings.get(session_id)
            if existing is None:
                self._bindings[session_id] = client_id
                while len(self._bindings) > self._maxsize:
                    self._bindings.popitem(last=False)
                return True
            if existing == client_id:
                self._bindings.move_to_end(session_id)
                return True
            return False

    def get(self, session_id: str) -> Optional[str]:
        with self._lock:
            return self._bindings.get(session_id)

    def unbind(self, session_id: str) -> None:
        with self._lock:
            self._bindings.pop(session_id, None)

    def clear(self) -> None:
        with self._lock:
            self._bindings.clear()


_registry = SessionIdentityRegistry()


def get_session_registry() -> SessionIdentityRegistry:
    return _registry


# ---------------------------------------------------------------------------
# 行级权限身份解析（供 src/db/mysql_operations.py:execute_query 调用）
# ---------------------------------------------------------------------------
def resolve_user_id(param_user_id: Optional[str]) -> Optional[str]:
    """解析实际用于权限过滤的 user_id

    规则（AUTH_BIND_USER=true，生产默认）：
    1. 凭据绑定了 user_id → 一律以凭据为准；入参不一致视为越权，抛异常
    2. 凭据未绑定 user_id → 回落入参（过渡期兼容，记审计日志）
    3. 无鉴权上下文（本地调试/鉴权关闭）→ 回落入参（旧行为）
    """
    identity = get_current_identity()
    if identity is None or not identity.user_id:
        return param_user_id

    from src.config import AuthConfig  # 延迟导入，避免循环依赖
    if not AuthConfig.BIND_USER:
        # 未启用绑定：入参优先，凭据身份仅作兜底与审计
        if param_user_id and param_user_id != identity.user_id:
            logger.info(
                "AUTH-BIND 未启用绑定: client=%s 入参user_id=%s 与凭据绑定user_id=%s 不一致",
                identity.client_id, param_user_id, identity.user_id)
        return param_user_id or identity.user_id

    if param_user_id and param_user_id != identity.user_id:
        logger.warning(
            "AUTH-BIND 用户身份不一致(已拒绝): client=%s 凭据user_id=%s 入参user_id=%s",
            identity.client_id, identity.user_id, param_user_id)
        raise UserIdentityMismatchError(
            f"用户身份不匹配: 凭据绑定用户为 {identity.user_id}，禁止以 {param_user_id} 身份查询")
    return identity.user_id

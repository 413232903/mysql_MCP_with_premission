"""
用户上下文管理模块
使用 contextvars 实现请求级别的用户身份存储
"""
import logging
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger("mysql_server")

# 使用 ContextVar 存储当前请求的用户ID
# ContextVar 是协程安全的，每个请求都有独立的上下文
_current_user_id: ContextVar[Optional[str]] = ContextVar('current_user_id', default=None)


def set_current_user_id(user_id: Optional[str]) -> None:
    """
    设置当前请求的用户ID

    Args:
        user_id: 用户ID（工号）
    """
    _current_user_id.set(user_id)
    if user_id:
        logger.debug(f"已设置当前用户上下文: {user_id}")


def get_current_user_id() -> Optional[str]:
    """
    获取当前请求的用户ID

    Returns:
        当前用户ID，如果未设置则返回 None
    """
    return _current_user_id.get()


def clear_current_user_id() -> None:
    """
    清除当前请求的用户ID
    """
    _current_user_id.set(None)
    logger.debug("已清除当前用户上下文")

"""
用户身份中间件
从 SSE 连接的 URL 参数中提取用户身份
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable

from .user_context import set_current_user_id, clear_current_user_id

logger = logging.getLogger("mysql_server")


class UserIdentityMiddleware(BaseHTTPMiddleware):
    """
    用户身份中间件

    从 SSE 连接的 URL 参数中提取 user_id 并存储到上下文中

    使用方式：
        AI 软件在建立 SSE 连接时传递用户工号：
        http://your-server:3000/sse2?user_id=工号
    """

    def __init__(self, app, user_id_param: str = "user_id"):
        """
        初始化中间件

        Args:
            app: Starlette 应用
            user_id_param: URL 参数名称，默认为 "user_id"
        """
        super().__init__(app)
        self.user_id_param = user_id_param

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求，提取用户身份
        """
        # 从 URL 查询参数中获取 user_id
        user_id = request.query_params.get(self.user_id_param)

        if user_id:
            # 记录用户身份
            logger.info(f"检测到用户身份: {user_id}, 路径: {request.url.path}")
            # 设置到上下文中
            set_current_user_id(user_id)
        else:
            # 清除上下文（确保不会污染）
            clear_current_user_id()
            logger.debug(f"未检测到用户身份, 路径: {request.url.path}")

        try:
            # 继续处理请求
            response = await call_next(request)
            return response
        finally:
            # 请求结束后清除上下文
            # 注意：对于 SSE 长连接，这个清除会在连接关闭时执行
            pass  # 不在这里清除，因为 SSE 是长连接

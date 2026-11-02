"""健康检查路由（纯 ASGI）

包在鉴权中间件最外层：/health 直接应答，供 SLB / 部署平台探活使用，
不进入鉴权流程，也不暴露任何内部信息。
"""
import json


class HealthApp:
    """GET /health → 200 {"status":"ok"}；其余请求转发内层应用"""

    def __init__(self, inner, path: str = '/health'):
        self.inner = inner
        self.path = path

    async def __call__(self, scope, receive, send):
        if (scope.get('type') == 'http'
                and scope.get('path') == self.path
                and scope.get('method') == 'GET'):
            body = json.dumps({"status": "ok"}).encode('utf-8')
            await send({
                'type': 'http.response.start',
                'status': 200,
                'headers': [
                    (b'content-type', b'application/json; charset=utf-8'),
                    (b'content-length', str(len(body)).encode('ascii')),
                ],
            })
            await send({'type': 'http.response.body', 'body': body})
            return
        await self.inner(scope, receive, send)

# MySQL MCP 服务鉴权整改开发方案

> 背景：网络安全团队整改要求——部署在百炼上的 MCP 服务必须**鉴权后使用**；鉴权必须在 **HTTP Header 校验**中完成；**禁止直接明文携带参数**做校验。
>
> 适用项目：`mysql_MCP_with_premission`（FastMCP + SSE，`/sse2` 端点）
>
> 文档版本：v1.0（2026-11-01）

---

## 一、现状与风险分析

### 1.1 现状

| 项 | 现状 | 位置 |
|---|---|---|
| 传输层鉴权 | **无**。SSE 端点裸奔，知道 URL 即可建立会话、调用全部工具 | `src/server.py:241` |
| 消息端点 | `POST /messages/?session_id=...`，session_id 为查询串明文参数，是目前唯一的"访问凭据" | mcp SDK SSE transport |
| 行级权限身份 | `user_id` 由调用方作为**工具入参明文传入**，服务端无条件信任 | `src/tools/mysql_tool.py:36` |
| 调试模式 | `FastMCP(..., debug=True)` 硬编码开启 | `src/server.py:101` |
| 安全层 | SQL 拦截器 / 数据库隔离 / 角色权限均在**工具层之后**，无法阻止未授权连接 | `src/security/` |

### 1.2 风险

1. **未授权访问（高危）**：服务暴露公网（百炼托管必然公网可达）后，任何人可执行 SQL 查询、读取元数据。
2. **水平越权（高危）**：`user_id` 可伪造——攻击者传入他人 `user_id` 即可绕过 `gssq` 行级权限过滤，拿到他人权限范围的数据；不传 `user_id` 甚至完全不触发权限过滤。这正是安全同事所说"明文携带参数校验"的典型问题。
3. **重放风险**：若只用 URL 查询串或明文 token，凭据会进入网关/代理访问日志，泄露后可无限重放。

---

## 二、方案总体设计

### 2.1 架构：在传输层新增统一鉴权中间件

鉴权必须发生在 **MCP 会话建立之前**（HTTP 层），而不是工具层。新增一个**纯 ASGI 中间件**包在 FastMCP 的 Starlette 应用外层，覆盖 SSE 流（`GET /sse2`）和消息端点（`POST /messages/`）两条路由：

```
HTTP 请求（携带鉴权 Header）
    ↓
┌─────────────────────────────────────┐
│ AuthMiddleware（新增）               │  ← 401 拒绝 / 放行并注入身份
│  · Bearer Token 校验（哈希比对）      │
│  · HMAC 签名校验（时间戳+Nonce 防重放）│
└─────────────────────────────────────┘
    ↓
FastMCP SSE 应用（GET /sse2, POST /messages/）
    ↓
tools/（MCP 工具层）→ 身份取自鉴权上下文，不再信任明文 user_id 入参
    ↓
security/（SQL 拦截器、数据库隔离、角色权限）
    ↓
db/（连接池执行）
```

选择纯 ASGI 中间件而非 mcp SDK 自带 auth 的原因：

- `requirements.txt` 目前为 `mcp>=1.4.1`，官方 `TokenVerifier`/OAuth 体系在 1.8+ 才有且偏重（面向 OAuth2.1）；纯 ASGI 中间件**与 SDK 版本解耦**，且能同时支持静态 Token 与动态 HMAC 两种模式。
- 长期若公司接入统一 IdP，可再升级 SDK 平滑迁移到官方 OAuth（见 §7 演进路线）。

### 2.2 双鉴权模式

安全要求"禁止直接明文携带参数校验"，落地为两条腿：

#### 模式 A：Bearer Token（API Key）——面向百炼平台等"只能配置静态 Header"的调用方

百炼托管 MCP 服务时支持为服务配置**自定义静态请求 Header**，无法做每请求动态签名，因此平台侧调用采用高熵 Bearer Token：

```
Authorization: Bearer <64位随机token>
```

- Token 由服务端工具脚本生成（`secrets.token_urlsafe(48)`），**服务端只存 SHA-256 哈希**，明文仅通过线下安全渠道发给调用方一次。
- 校验用 `hmac.compare_digest` 恒定时间比较，防时序侧信道。
- 每个 Token 绑定一个 `client_id`（调用方系统标识）和可选的 `user_id`（用于行级权限映射）、过期时间、吊销标记。
- **强制 HTTPS**：Token 明文只存在于 TLS 信道内（百炼公网端点本身要求 HTTPS，由 SLB/网关终结 TLS）。
- 支持**轮换**：同一 client_id 允许新旧两个 Token 并行生效，切换后吊销旧值。

#### 模式 B：HMAC 签名——面向自研后端 / 网关等"可动态签名"的调用方

密钥（AppSecret）**永不上网**，每次请求签名，天然防窃听、防篡改、防重放：

```
X-Auth-Key:       <AppKey，公开标识>
X-Auth-Timestamp: <Unix 秒>
X-Auth-Nonce:     <UUID，单次随机>
X-Auth-Signature: Base64(HMAC-SHA256(AppSecret, StringToSign))
```

签名串规范（客户端与服务端必须严格一致）：

```
StringToSign =
    HTTPMethod + "\n"            # 大写，如 GET / POST
  + Path + "\n"                  # 不含 query，如 /api/sse2
  + SortedQueryString + "\n"     # 按 key 字典序拼接 k=v&k=v，无则为空串
  + Timestamp + "\n"
  + Nonce + "\n"
  + SHA256Hex(RequestBody)       # GET/SSE 无 body 时对空串取哈希
```

服务端校验顺序（任一失败即 401，返回统一错误，不透露失败细节）：

1. `X-Auth-Key` 存在且未吊销；
2. `|now - Timestamp| ≤ AUTH_TIMESTAMP_TOLERANCE`（默认 300s）；
3. Nonce 在 `AUTH_NONCE_TTL`（默认 600s）窗口内未出现过（内存 TTL 缓存；多实例部署换 Redis）；
4. 重算签名并 `hmac.compare_digest` 比对；
5. 校验通过后 Nonce 写入缓存。

> 说明：mcp Python SDK 的 `sse_client` 只支持静态 headers，无法逐请求重签 HMAC，因此 SSE 类客户端默认走模式 A；模式 B 服务于 REST 化调用方、API 网关前置校验、以及未来 Streamable HTTP 传输。中间件按 `AUTH_MODE=token|hmac|both` 配置启用。

### 2.3 身份绑定：消灭 user_id 伪造（本次整改的核心增值项）

鉴权通过后，中间件把身份写入请求上下文，并做**会话级绑定**：

1. 中间件解析出 `AuthIdentity(client_id, user_id, scopes)`；
2. `GET /sse2` 建立会话后，首次出现的 `POST /messages/?session_id=X` 将 `session_id → client_id` 登记进会话身份表；后续该 session 的请求若换了 Token（client_id 不一致）直接 403，防止会话劫持/混用；
3. 工具层通过 `get_current_identity()` 从上下文取身份：
   - `AUTH_BIND_USER=true`（生产默认）时，**权限过滤使用的 user_id 一律取 Token 绑定的 user_id**，忽略/校验工具入参 `user_id`（不一致即拒绝并审计告警）；
   - 入参 `user_id` 保留向后兼容（`AUTH_BIND_USER=false` 或 Token 未绑定 user_id 时才生效），过渡期后废弃。

这样行级权限（`gssq` 过滤）的信任根从"调用方自觉传参"升级为"服务端签发的凭据"，同时满足"禁止明文参数校验"的要求。

### 2.4 审计与防爆破

- **审计日志**：认证成功/失败均记录 `时间、client IP、path、client_id（或失败原因码）、session_id`；**严禁**记录 Token/签名原文（日志脱敏：只记前 8 位指纹哈希）。
- **失败限速**：同一 IP 连续失败 `AUTH_MAX_FAILURES`（默认 10）次后临时封禁 `AUTH_BLOCK_SECONDS`（默认 600s），返回 429，防在线爆破。
- **401 响应**：统一 `{"error":"unauthorized"}` + `WWW-Authenticate: Bearer realm="mysql-mcp"`，不区分"token 不存在/过期/签名错"，避免给攻击者反馈信道。
- **健康检查豁免**：新增 `GET /health`（仅返回 `{"status":"ok"}`）供 SLB/百炼探活，列入 `AUTH_EXEMPT_PATHS`。

---

## 三、具体实现设计

### 3.1 新增文件

```
src/security/auth/
├── __init__.py          # 导出 AuthMiddleware, AuthConfig 辅助
├── middleware.py        # 纯 ASGI 鉴权中间件（路由覆盖、401/403/429 响应、会话绑定）
├── token_store.py       # Bearer Token 存储：env/DB 两种后端，SHA-256 哈希比对、TTL 缓存、吊销
├── hmac_verifier.py     # HMAC 签名重建与校验（StringToSign 规范化）
├── nonce_cache.py       # Nonce 防重放 TTL 缓存（单实例内存版；接口预留 Redis 实现）
├── identity.py          # AuthIdentity 数据类 + contextvar + session_id 绑定表 + get_current_identity()
scripts/
└── gen_token.py         # 运维脚本：生成随机 token、输出哈希配置行、支持吊销/轮换
examples/
└── client_with_auth.py  # mcp SDK sse_client 携带 Authorization 头的调用示例 + HMAC 签名示例
```

### 3.2 `middleware.py` 核心骨架

```python
class AuthMiddleware:
    """纯 ASGI 鉴权中间件：在请求到达 MCP 路由前完成 Header 校验"""

    def __init__(self, app, *, config: "AuthConfig"):
        self.app = app
        self.config = config
        self.token_store = TokenStore(config)
        self.hmac_verifier = HmacVerifier(config)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":                     # lifespan/websocket 直通
            return await self.app(scope, receive, send)

        path = scope["path"]
        if path in self.config.exempt_paths:            # /health 豁免
            return await self.app(scope, receive, send)

        headers = Headers(scope=scope)
        identity, err = await self._authenticate(headers, scope)  # Bearer 优先，其次 HMAC

        if identity is None:
            await self._audit_failure(scope, err)       # 审计 + 失败计数/封禁
            if self.config.enforce_mode == "audit":     # 灰度观察模式：只告警放行
                logger.warning("AUTH-AUDIT 未鉴权请求放行: %s %s ip=%s reason=%s", ...)
                return await self.app(scope, receive, send)
            return await self._respond_401(send, err)

        await self._audit_success(scope, identity)
        scope["auth_identity"] = identity
        token = set_identity(identity)                  # contextvar 注入
        try:
            await self._bind_session(scope, identity)   # session_id ↔ client_id 绑定校验
            return await self.app(scope, receive, send)
        finally:
            reset_identity(token)
```

### 3.3 `server.py` 改造点

```python
# 1) FastMCP 实例化：debug 改为配置驱动（生产必须 False）
mcp = FastMCP("MySQL Query Server", host=host, port=port,
              debug=ServerConfig.DEBUG, mount_path=mount_path, sse_path=sse_path)

# 2) start_server() 中不再直接 mcp.run('sse')，改为显式组装 + 中间件：
def _build_app():
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from src.security.auth import AuthMiddleware

    sse = mcp.sse_app()                          # GET /sse2 + POST /messages/
    app = AuthMiddleware(sse, config=AuthConfig.get_config())
    routes = [Mount(mount_path, app=app)] if mount_path != "/" else []
    health = Route("/health", endpoint=_health)  # 探活豁免路由
    return Starlette(routes=[health, *routes])

def start_server():
    ...
    if SecurityConfig.ENV_TYPE == EnvironmentType.PRODUCTION and not AuthConfig.ENABLED:
        raise RuntimeError("生产环境必须启用鉴权（ENABLE_AUTH=true），拒绝启动")
    uvicorn.run(_build_app(), host=host, port=port)
```

> 注意：`sse_app()` 的入参签名在 mcp 不同小版本间有差异，实施时将 `requirements.txt` 收敛为 `mcp>=1.9,<2` 并按安装版本联调确认；连接池初始化、atexit/信号清理逻辑全部保持不变。

### 3.4 Token 存储设计

**开发/小规模（env 后端）**——`.env`：

```env
# 格式：client_id:token_sha256_hex[:user_id][:expires_at]，多组用分号分隔
AUTH_TOKENS=bailian-prod:<sha256hex>:report_user:2027-01-01;bi-system:<sha256hex>::
```

**生产（DB 后端，推荐）**——与项目现有 DB 中心化管理一致，支持热吊销/轮换，无需重启：

```sql
CREATE TABLE mcp_auth_token (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  client_id   VARCHAR(64)  NOT NULL,
  token_hash  CHAR(64)     NOT NULL COMMENT 'SHA-256 hex',
  user_id     VARCHAR(64)  NULL     COMMENT '绑定的行级权限用户',
  scopes      VARCHAR(255) NOT NULL DEFAULT 'query',
  expires_at  DATETIME     NULL,
  revoked     TINYINT(1)   NOT NULL DEFAULT 0,
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_token_hash (token_hash),
  KEY idx_client (client_id)
);
```

HMAC 密钥表 `mcp_auth_key(app_key, secret_cipher, client_id, ...)` 同理；Secret 建议 KMS/加密列存储，最低要求不进代码库。TokenStore 带 30~60s TTL 内存缓存，避免每请求打库。

### 3.5 `config.py` 新增 `AuthConfig`

```python
class AuthConfig:
    """MCP 服务鉴权配置"""
    ENABLED = os.getenv('ENABLE_AUTH', 'false').lower() in ('true', 'yes', '1')
    # token | hmac | both
    MODE = os.getenv('AUTH_MODE', 'both').lower()
    # off | audit(只记录不拦截) | enforce
    ENFORCE_MODE = os.getenv('AUTH_ENFORCE_MODE', 'enforce').lower()
    TOKENS_STR = os.getenv('AUTH_TOKENS', '')                 # env 后端
    TOKEN_STORE_BACKEND = os.getenv('AUTH_TOKEN_BACKEND', 'env')  # env | db
    TIMESTAMP_TOLERANCE = int(os.getenv('AUTH_TIMESTAMP_TOLERANCE', '300'))
    NONCE_TTL = int(os.getenv('AUTH_NONCE_TTL', '600'))
    EXEMPT_PATHS = set(filter(None, (p.strip() for p in
                     os.getenv('AUTH_EXEMPT_PATHS', '/health').split(','))))
    BIND_USER = os.getenv('AUTH_BIND_USER', 'true').lower() in ('true', 'yes', '1')
    MAX_FAILURES = int(os.getenv('AUTH_MAX_FAILURES', '10'))
    BLOCK_SECONDS = int(os.getenv('AUTH_BLOCK_SECONDS', '600'))

    # 与现有 SecurityConfig 风格一致：生产环境自动收紧
    # ENV_TYPE=production 时：ENABLED 强制为 True，ENFORCE_MODE 强制为 enforce
```

### 3.6 工具层 / 权限层小改动

- `src/tools/mysql_tool.py`（及其他带 `user_id` 的工具）：执行前调用 `resolve_user_id(param_user_id)`——`AUTH_BIND_USER=true` 且身份含 user_id 时以身份为准（入参不一致直接抛错并审计），否则回落入参。
- `src/db/mysql_operations.py::execute_query` 不改签名，`user_id` 语义由上游保证。

---

## 四、灰度上线与运维流程

| 阶段 | 动作 | 通过标准 |
|---|---|---|
| ① 观察期（1~2 天） | `AUTH_ENFORCE_MODE=audit` 上线，所有调用照常放行但记录"未鉴权请求"审计日志 | 摸清全部存量调用方清单 |
| ② 发凭据 | 用 `scripts/gen_token.py` 为每个调用方（含百炼控制台 Header 配置）签发 Token/密钥，登记 client_id、绑定 user_id | 凭据经线下安全渠道送达，明文不落库不进 git |
| ③ 测试环境强制 | `AUTH_ENFORCE_MODE=enforce`，回归全部 MCP 工具 + 权限过滤 | 无 Token 一律 401；越权用例全部拦截 |
| ④ 生产强制 | enforce + `AUTH_BIND_USER=true`；生产未启用鉴权则拒绝启动 | 安全团队复测通过 |
| ⑤ 常态运维 | Token 到期前轮换（新旧并行→吊销旧值）；泄露应急：DB 置 `revoked=1` 即时生效（≤缓存 TTL）；审计日志留存 ≥180 天 | — |

**百炼侧配置**：在百炼控制台该 MCP 服务的自定义 Header 中加入 `Authorization: Bearer <token>`；服务端点必须为 HTTPS。

---

## 五、测试方案（pytest，新增 `tests/test_auth.py` 等）

1. **Bearer**：缺 Header→401；错 Token→401；过期→401；已吊销→401；正确→SSE 握手成功。
2. **HMAC**：正确签名→通过；篡改 body/query→401；时间戳超窗→401；**Nonce 重放→401**；错误 Secret→401。
3. **会话绑定**：Token A 建会话后，Token B 用同一 session_id POST /messages/→403。
4. **身份绑定**：Token 绑定 user_a，工具入参传 user_b→拒绝；`AUTH_BIND_USER=false` 时兼容旧行为。
5. **灰度**：audit 模式未鉴权请求放行且产生 WARNING 审计日志；生产 + `ENABLE_AUTH=false`→启动抛错。
6. **防爆破**：连续失败达阈值→429；封禁到期自动恢复。
7. **集成**：mcp SDK `sse_client(url, headers=...)` 端到端跑通 `mysql_query`；`/health` 无鉴权可探活。
8. **脱敏断言**：所有失败路径日志中不出现 Token/Secret 原文。

---

## 六、工作量估算

| 任务 | 估时 |
|---|---|
| auth 模块 + ASGI 中间件 + Bearer 模式 + AuthConfig + server.py 改造 | 1.5 人日 |
| HMAC 模式 + Nonce 防重放 + 防爆破 | 1 人日 |
| 身份绑定（session/user_id）+ 审计日志 + gen_token 脚本 + DB Token 表 | 1 人日 |
| 测试（单测 + 集成 + 攻击模拟） | 1 人日 |
| 文档（.env.example / README / CLAUDE.md / 客户端示例）+ 灰度上线 | 0.5 人日 |
| **合计** | **约 5 人日** |

---

## 七、配套整改与后续演进

**顺手修复（本次一并处理）**：

- `FastMCP(debug=True)` 改为 `ServerConfig.DEBUG` 环境变量驱动，生产关闭；
- 实例第二位置参数占位串 `"cccccccccc"` 清理；
- README/CLAUDE.md 增补鉴权配置章节。

**纵深防御建议（视网络条件推进）**：

- 源站不对公网直接开放：百炼 → SLB/API 网关（TLS 终结 + IP 白名单）→ 源站，中间件鉴权作为最后一道防线；
- Nonce 缓存多实例共享（Redis），支撑水平扩容。

**演进路线**：若公司建设统一身份（IdP），可升级 `mcp>=1.8` 后迁移到 SDK 官方 OAuth2.1 `TokenVerifier` 体系，本方案的 `AuthIdentity`/会话绑定/审计接口保持复用。

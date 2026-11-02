# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于 FastMCP 框架的 MySQL 查询服务器，通过 SSE 协议提供实时数据库操作能力。该项目具备多层安全机制、连接池管理、数据库隔离等企业级特性。

## 核心架构

### 1. 分层架构设计

```
HTTP 请求 (携带鉴权 Header)
    ↓
security/auth/ (传输层鉴权 - AuthMiddleware: Bearer Token / HMAC 签名)
    ↓
server.py (主入口 - FastMCP SSE 应用组装)
    ↓
tools/ (MCP工具层 - 自动注册机制)
    ↓
db/mysql_operations.py (数据库操作层 - 连接池管理 + 鉴权身份解析 resolve_user_id)
    ↓
security/ (安全拦截层 - SQL检查、数据库隔离、行级权限)
```

### 2. 关键组件

**服务器入口** (`src/server.py`):
- 使用 FastMCP 框架创建 SSE 服务器
- **SSE 路径配置**: 使用 `sse_path='/sse2'` 参数配置 SSE 端点路径
- **传输协议**: `_build_asgi_app()` 显式组装 `HealthApp(AuthMiddleware(sse_app))` 后用 uvicorn 启动（替代 `mcp.run('sse')` 直跑，为插入鉴权中间件；通过 inspect 自动兼容新旧 mcp 版本的 `sse_app` 签名）
- **生产 fail-fast**: `ENV_TYPE=production` 且未启用鉴权时拒绝启动
- **自动工具注册**: 通过 `auto_register_tools()` 扫描 `src/tools/` 目录，自动注册所有 `register_*_tool(s)` 函数
- 新增工具时只需在 `src/tools/` 下实现 `register_xxx_tool(s)` 函数，无需修改 server.py
- 启动连接池定时回收任务（每5分钟）
- 注册退出处理函数和信号处理器以确保资源正确释放

**连接池管理** (`src/db/mysql_operations.py`):
- **事件循环隔离**: 每个事件循环维护独立的连接池，支持多环境并发
- **自动回收机制**: `_cleanup_unused_pools()` 定期回收无效或失效的连接池
- **弱引用清理**: 使用 `weakref.finalize()` 在事件循环关闭时自动关闭连接池
- 支持流式查询结果处理（大数据集分批获取）
- 支持事务管理和自动回滚

**安全系统** (`src/security/`):
- **服务鉴权** (`auth/`): 传输层 Header 鉴权中间件（详见"MCP服务鉴权"章节）
  - `middleware.py`: 纯 ASGI 鉴权中间件，覆盖 SSE 流与消息端点，未鉴权一律 401
  - `token_store.py`: Bearer Token 校验（只存 SHA-256 哈希，env/db 后端，fail-closed）
  - `hmac_verifier.py`: HMAC-SHA256 签名校验（时间窗 + Nonce 防重放，密钥不上网）
  - `identity.py`: 鉴权身份上下文（contextvar）与会话绑定，`resolve_user_id()` 防入参伪造
- **SQL拦截器** (`interceptor.py`): SQL风险等级检查、长度限制、格式验证
- **数据库隔离** (`database_scope_checker.py`): 防止跨数据库访问，支持三级访问控制
  - `strict`: 仅允许访问指定数据库
  - `restricted`: 允许指定数据库 + 系统库
  - `permissive`: 允许所有数据库（默认）
- **角色权限控制** (`role_permission.py`): 基于 gssq 字段的行级权限过滤
- **SQL分析器** (`sql_analyzer.py`): 风险等级评估（LOW/MEDIUM/HIGH/CRITICAL）
- **SQL解析器** (`sql_parser.py`): 使用 sqlparse 解析 SQL 语句

**配置系统** (`src/config.py`):
- 所有配置通过环境变量管理
- 生产环境自动启用严格安全策略（数据库隔离、低风险操作）
- 支持连接池参数动态配置

### 3. 工具注册机制

所有 MCP 工具必须放在 `src/tools/` 目录下，并实现注册函数：

```python
def register_xxx_tool(mcp: FastMCP):
    """注册xxx工具"""
    @mcp.tool()
    async def tool_name(...):
        # 工具实现
        pass
```

注册函数命名规则：
- 必须以 `register_` 开头
- 必须以 `tool` 或 `tools` 结尾
- 例如: `register_mysql_tool`, `register_metadata_tools`

## 开发指南

### 启动服务器

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件设置 MySQL 连接信息

# 启动服务器
python -m src.server
```

服务器将监听在 `http://{HOST}:{PORT}{MOUNT_PATH.rstrip('/')}{SSE_PATH}`，默认 `http://127.0.0.1:3000/sse2`

**SSE 路径配置说明**：
- `SSE_PATH`: SSE 推送端点路径（默认 `/sse2`），可通过环境变量修改
- `MOUNT_PATH`: MCP 基础挂载路径（默认 `/`），用于设置基础路由前缀
- 最终访问路径会自动拼接：`http://HOST:PORT{MOUNT_PATH.rstrip('/')}{SSE_PATH}`
- 例如：`MOUNT_PATH=/api`, `SSE_PATH=/sse3` → 最终路径为 `http://127.0.0.1:3000/api/sse3`

**注意**: FastMCP 框架使用 `sse_path` 参数配置 SSE 路径，不是 `endpoint`。

### Docker 部署

```bash
# 构建镜像
docker build -t mysql-mcp-server-sse .

# 运行容器
docker run -d \
  --name mysql-mcp-server-sse \
  -e MYSQL_HOST=your_host \
  -e MYSQL_USER=your_user \
  -e MYSQL_PASSWORD=your_password \
  -e MYSQL_DATABASE=your_database \
  -p 3000:3000 \
  mysql-mcp-server-sse:latest
```

### 测试

测试框架为 pytest，测试文件在 `tests/` 目录：

```bash
pip install pytest httpx   # 测试依赖
python -m pytest tests/ -v
```

- `tests/test_auth.py`: 鉴权单元测试（纯 stdlib 依赖，无需数据库/真实服务器）——Bearer/HMAC 校验、Nonce 重放、会话绑定、防爆破、身份解析、审计日志脱敏
- `tests/test_auth_integration.py`: 集成测试——真实 uvicorn + FastMCP SSE 端到端（验证身份 contextvar 传播到工具执行、伪造 user_id 拦截、签名 SSE 建连）

新增测试时重点覆盖：安全机制、连接池管理、SQL 拦截器、鉴权中间件

## 重要技术细节

### MySQL 8.0 认证支持

- 默认使用 `mysql_native_password` 认证插件
- 支持 `caching_sha2_password` (需要 `cryptography` 依赖)
- 通过 `DB_AUTH_PLUGIN` 环境变量配置
- 错误处理包含详细的认证插件故障排查信息 (见 `mysql_operations.py:186-210`)

### 连接池生命周期管理

1. **初始化**: `init_db_pool()` 为每个事件循环创建独立池
2. **存储**: 池存储在线程本地存储 `_pools.pools[loop_id]`
3. **获取**: `get_pool_for_current_loop()` 自动检查池状态并清理失效池
4. **回收**: 后台线程每5分钟执行 `_cleanup_unused_pools()`
5. **关闭**:
   - 事件循环关闭时通过 `weakref.finalize()` 自动关闭
   - 进程退出时通过 `atexit.register()` 关闭所有池
   - 信号处理器 (SIGINT/SIGTERM) 确保优雅关闭

### 安全检查流程

完整检查链路（鉴权在 SQL 检查之前，HTTP 层完成）：
0. **传输层鉴权** (AuthMiddleware: Header 凭据校验、会话绑定、防爆破)
0.5 **身份解析** (execute_query: resolve_user_id 以凭据绑定 user_id 为准)
1. SQL 非空和长度检查
2. SQL 格式解析和验证
3. **数据库隔离检查** (如果启用)
4. SQL 风险等级分析
5. 危险操作检测
6. 允许风险等级检查

### 数据库隔离实现

- 使用正则表达式检测 `database.table` 语法
- 检测 `SHOW TABLES FROM`, `USE`, `JOIN` 等跨数据库操作
- 特殊查询处理：`SHOW DATABASES`, 系统表访问
- 生产环境自动启用 `restricted` 模式

## 环境变量重点配置

| 变量 | 用途 | 默认值 | 注意事项 |
|------|------|--------|----------|
| `MYSQL_DATABASE` | 数据库名称 | (空) | **必须设置**，否则无法连接 |
| `ENABLE_AUTH` | 服务鉴权开关 | `false` | **生产环境必须 `true`**，否则拒绝启动 |
| `AUTH_MODE` | 鉴权模式 | `both` | `token`(Bearer) / `hmac`(签名) / `both` |
| `AUTH_ENFORCE_MODE` | 执行模式 | `enforce` | `audit` 用于灰度观察；生产强制 `enforce` |
| `AUTH_TOKENS` | Token 凭据(env后端) | (空) | 只存 SHA-256 哈希，用 `scripts/gen_token.py` 生成 |
| `AUTH_BIND_USER` | 身份绑定 | `true` | 凭据 user_id 优先于工具入参，防越权 |
| `SERVER_DEBUG` | 调试模式 | `false` | 生产环境强制关闭 |
| `DB_AUTH_PLUGIN` | 认证插件 | `mysql_native_password` | MySQL 8.0 使用 `caching_sha2_password` 需安装 cryptography |
| `DB_POOL_ENABLED` | 启用连接池 | `true` | 生产环境建议启用 |
| `ENABLE_DATABASE_ISOLATION` | 数据库隔离 | `false` | 生产环境自动启用 |
| `DATABASE_ACCESS_LEVEL` | 访问级别 | `permissive` | 生产环境自动设为 `restricted` |
| `ENV_TYPE` | 环境类型 | `development` | 设为 `production` 启用严格安全策略 |
| `ALLOWED_RISK_LEVELS` | 允许的风险等级 | `LOW,MEDIUM` | 生产环境默认只允许 `LOW` |

## 常见开发任务

### 添加新的 MCP 工具

1. 在 `src/tools/` 下创建新文件 `xxx_tool.py`
2. 实现注册函数：
   ```python
   def register_xxx_tool(mcp: FastMCP):
       @mcp.tool()
       async def your_tool_name(...):
           async with get_db_connection() as conn:
               # 工具逻辑
               pass
   ```
3. 无需修改 `server.py`，工具将自动注册

### 修改安全策略

- 编辑 `src/security/sql_analyzer.py` 修改风险等级规则
- 编辑 `src/security/interceptor.py` 添加新的拦截规则
- 编辑 `src/security/database_scope_checker.py` 调整数据库隔离规则

### 扩展连接池配置

- 在 `src/config.py` 的 `ConnectionPoolConfig` 类中添加新配置项
- 在 `src/db/mysql_operations.py` 的 `init_db_pool()` 中使用新配置
- 通过环境变量 `DB_POOL_*` 前缀暴露配置

## 代码规范

- 所有异步数据库操作必须使用 `async with get_db_connection()` 上下文管理器
- 修改操作（INSERT/UPDATE/DELETE）必须在事务中执行
- 新增工具必须使用 `@MetadataToolBase.handle_query_error` 装饰器统一错误处理
- 日志使用统一的 logger，级别通过 `LOG_LEVEL` 环境变量控制
- 安全检查必须在数据库操作前执行，不能绕过 `SQLInterceptor`

## 依赖版本要求

- Python >= 3.12.3
- mcp >= 1.9, < 2（`server.py` 通过 inspect 兼容新旧 `sse_app` 签名，已在 1.27.x / 1.30.x 验证）
- aiomysql >= 0.2.0
- sqlparse >= 0.5.3
- cryptography >= 3.4.8 (MySQL 8.0 认证支持)
- starlette >= 0.27, uvicorn >= 0.23（server.py 组装鉴权中间件时直接依赖）

## MCP服务鉴权（传输层 Header 鉴权）

> 背景：网络安全整改要求——所有 MCP 服务必须**鉴权后使用**，鉴权在 **HTTP Header 校验**中完成，**禁止直接明文携带参数校验**。完整方案见 `docs/MCP服务鉴权整改开发方案.md`。

### 架构

鉴权发生在 **MCP 会话建立之前**（HTTP 传输层），由纯 ASGI 中间件 `src/security/auth/middleware.py:AuthMiddleware` 完成，覆盖 `GET /sse2`（SSE 流）与 `POST /messages/`（消息端点）全部路由。应用组装结构（`server.py:_build_asgi_app`）：

```
HealthApp( AuthMiddleware( FastMCP sse_app ) )
```

`/health` 探活在鉴权之外直接应答（`{"status":"ok"}`，不暴露内部信息）。

### 双鉴权模式

**模式 A - Bearer Token**（百炼平台等只能配置静态 Header 的调用方）：

```
Authorization: Bearer <64位随机token>
```

- 服务端**只存 SHA-256 哈希**（env 配置或 DB 表），恒定时间比较防时序侧信道
- 每个 Token 绑定 `client_id`（审计）与可选 `user_id`（行级权限身份），支持过期/吊销/轮换
- 百炼控制台配置：MCP 服务 → 自定义 Header → `Authorization: Bearer <token>`
- 必须全链路 HTTPS

**模式 B - HMAC 签名**（自研后端/网关等可动态签名的调用方，密钥永不上网）：

```
X-Auth-Key: <AppKey>  X-Auth-Timestamp: <unix秒>  X-Auth-Nonce: <UUID>  X-Auth-Signature: <Base64签名>

StringToSign = METHOD + "\n" + Path + "\n" + SortedQuery + "\n" + Timestamp + "\n" + Nonce + "\n" + SHA256Hex(Body)
Signature    = Base64(HMAC-SHA256(AppSecret, StringToSign))
```

- 服务端校验：时间窗（±`AUTH_TIMESTAMP_TOLERANCE`）→ 密钥查找 → 签名比对 → Nonce 登记（`AUTH_NONCE_TTL` 窗口内重放拒绝）
- Nonce 只在**签名验证通过后**登记，伪造请求无法抢占消耗合法 Nonce
- 规范实现：`src/security/auth/hmac_verifier.py`；客户端示例：`examples/client_with_auth.py`
- 注意：mcp SDK 的 `sse_client` 只支持静态 Header，SSE 类客户端走模式 A

### 凭据签发与管理

```bash
# 生成 Bearer Token（明文只显示一次；输出 .env 配置行与 DB INSERT 语句）
python scripts/gen_token.py token --client-id bailian-prod --user-id report_user --expires 2027-01-01

# 生成 HMAC 密钥对
python scripts/gen_token.py hmac-key --client-id bi-system --user-id bi_user

# 核对哈希 / 计算审计日志指纹
python scripts/gen_token.py hash <token>
python scripts/gen_token.py fingerprint <凭据>
```

- env 后端：`AUTH_TOKENS=client_id:sha256hex[:user_id][:expires][:scopes]`（分号分隔多组）
- db 后端：`AUTH_TOKEN_BACKEND=db`，建表见 `docs/sql/auth_tables.sql`，支持热吊销（`revoked=1`，最迟 `AUTH_CREDENTIAL_CACHE_TTL` 秒生效）与免重启轮换
- **凭据查询 fail-closed**：DB 异常按认证失败处理（401），绝不放行

### 身份绑定（防 user_id 伪造越权）

`execute_query` 在执行权限过滤前调用 `resolve_user_id()`（`src/security/auth/identity.py`）：

1. 凭据绑定了 `user_id` → **一律以凭据为准**；工具入参 `user_id` 不一致直接抛 `UserIdentityMismatchError` 拒绝（`AUTH_BIND_USER=true` 时，生产默认）
2. 凭据未绑定 / 无鉴权上下文 → 回落入参（过渡期兼容）
3. 会话绑定：`session_id` 首次出现即绑定 `client_id`，其他凭据向同一会话投递消息返回 403（防会话混用/劫持）

身份传播机制：中间件在 SSE 建连请求（GET /sse2）上通过 contextvar 注入 `AuthIdentity`，会话任务由该请求上下文派生，因此**该会话内所有工具执行都能读到身份**（已由集成测试验证）。

### 审计与防爆破

- 审计日志（logger `mysql_server`）：`AUTH OK/FAILED/SESSION-MISMATCH/BLOCK`，含 method/path/ip/client_id/session/失败原因码
- **日志只记凭据指纹**（SHA-256 前 8 位，`fp=` 字段），严禁出现 Token/签名原文；用 `gen_token.py fingerprint` 可反查对应凭据
- 401 响应统一 `{"error":"unauthorized"}` + `WWW-Authenticate: Bearer`，不区分失败细节（避免反馈信道）
- 同 IP 连续失败 `AUTH_MAX_FAILURES` 次 → 封禁 `AUTH_BLOCK_SECONDS` 秒（429）

### 灰度上线

1. `AUTH_ENFORCE_MODE=audit` 上线观察 1~2 天（未鉴权请求放行但记 WARNING 日志，摸清存量调用方）
2. 用 `gen_token.py` 为各调用方签发凭据（百炼在控制台配置 Header）
3. 测试环境 `enforce` 回归 → 生产 `enforce` + `AUTH_BIND_USER=true`
4. 生产未启用鉴权（`ENABLE_AUTH=false`）时 `start_server()` **拒绝启动**；`AUTH_ENFORCE_MODE` 在生产强制为 `enforce`

### 开发注意事项

- 鉴权模块**仅依赖标准库**（aiomysql 仅 db 后端内部延迟导入），修改后可直接跑 `pytest tests/test_auth.py`
- 新增豁免路径务必慎重（`AUTH_EXEMPT_PATHS` 仅限探活类端点）
- 多实例部署时 Nonce 缓存需换 Redis 共享实现（接口保持 `check_and_add` 语义）
- 修改签名规范时，`hmac_verifier.py` 与 `examples/client_with_auth.py` 必须同步更新

## 角色权限控制系统

### 功能概述

角色权限控制系统基于数据库表中的 `gssq` 字段实现行级权限过滤。当启用后，系统会自动向 SELECT 查询注入权限过滤条件，确保用户只能查询到其有权限访问的数据。

### 工作原理

**权限规则**：
```sql
WHERE gssq IN (
    SELECT REPLACE(extend1, 'RX', '') FROM fr_user_role WHERE username='[userId]'
)
OR '[userId]' NOT IN (SELECT USERNAME FROM fr_user_role)
```

**逻辑说明**：
1. 如果用户在 `fr_user_role` 表中有记录，只能查询 `gssq` 在其 `extend1` 字段定义的权限范围内的数据
2. 如果用户不在 `fr_user_role` 表中，可以查询所有数据（默认全部权限）
3. 超级管理员（配置在 `SUPER_ADMIN_USERS`）豁免权限检查

### 配置说明

在 `.env` 文件中添加以下配置：

```env
# 启用角色权限控制
ENABLE_ROLE_PERMISSION=true

# 需要权限过滤的表（逗号分隔）
PERMISSION_TABLES=orders,products,customers,invoices

# 权限字段名称（默认 gssq）
PERMISSION_FIELD=gssq

# 用户角色表配置
USER_ROLE_TABLE=fr_user_role
USER_ROLE_USERNAME_FIELD=username
USER_ROLE_EXTEND_FIELD=extend1
USER_ROLE_PREFIX=RX

# 超级管理员（逗号分隔，豁免权限检查）
SUPER_ADMIN_USERS=admin,system
```

### 使用方式

> **鉴权联动**：启用服务鉴权且凭据绑定了 `user_id` 时（`AUTH_BIND_USER=true`，生产默认），权限过滤**一律使用凭据绑定的 user_id**，入参 `user_id` 与凭据不一致会被直接拒绝；入参仅用于未绑定凭据的过渡期兼容。

调用 MCP 工具时传入 `user_id` 参数：

**示例 1 - 基础查询**：
```python
result = await mysql_query(
    query="SELECT * FROM orders WHERE status='pending'",
    user_id="zhang_san"
)
```

系统会自动将查询转换为：
```sql
SELECT * FROM orders
WHERE status='pending'
AND (
    gssq IN (SELECT REPLACE(extend1, 'RX', '') FROM fr_user_role WHERE username='zhang_san')
    OR 'zhang_san' NOT IN (SELECT USERNAME FROM fr_user_role)
)
```

**示例 2 - 带 ORDER BY 的查询**：
```python
result = await mysql_query(
    query="SELECT * FROM products ORDER BY created_at DESC",
    user_id="li_si"
)
```

转换后：
```sql
SELECT * FROM products
WHERE (
    gssq IN (SELECT REPLACE(extend1, 'RX', '') FROM fr_user_role WHERE username='li_si')
    OR 'li_si' NOT IN (SELECT USERNAME FROM fr_user_role)
)
ORDER BY created_at DESC
```

### 安全特性

1. **SQL 注入防护**：`user_id` 经过单引号转义处理
2. **智能 SQL 解析**：正确识别 WHERE/ORDER BY/GROUP BY/LIMIT 子句，精确插入权限条件
3. **表白名单机制**：只对配置的表应用权限过滤，避免影响系统表查询
4. **超级管理员豁免**：配置的超级用户跳过权限检查
5. **身份防伪**：启用鉴权后，权限过滤的 `user_id` 以服务端签发的凭据绑定值为准，工具入参不可伪造他人身份（见"MCP服务鉴权"章节）
6. **向后兼容**：`user_id` 为可选参数；未启用鉴权或凭据未绑定用户时保持旧行为

### 实现层级

权限过滤在**数据库操作层**实现（`src/db/mysql_operations.py:execute_query`），在 SQL 执行前自动注入权限条件。执行顺序：

```
0. HTTP 请求通过传输层鉴权（AuthMiddleware，身份注入 contextvar）
   ↓
1. 用户调用 MCP 工具（可选传入 user_id）
   ↓
2. execute_query 接收原始 SQL 和 user_id
   ↓
2.5 resolve_user_id()：凭据绑定的 user_id 优先，入参伪造直接拒绝
   ↓
3. RolePermissionManager.inject_permission_filter()
   - 检查是否需要应用权限（表白名单、超级管理员）
   - 构建权限过滤条件
   - 智能注入到 SQL 语句
   ↓
4. SQL 安全检查（SQL 拦截器）
   ↓
5. 执行过滤后的 SQL
```

### 日志追踪

权限过滤操作会产生详细日志：

```
INFO - 已为用户 zhang_san 注入权限过滤条件
DEBUG - 原始 SQL: SELECT * FROM orders WHERE status='pending'
DEBUG - 修改后 SQL: SELECT * FROM orders WHERE status='pending' AND (gssq IN ...)
```

### 扩展开发

**添加新的 MCP 工具并支持权限控制**：

```python
@mcp.tool()
@MetadataToolBase.handle_query_error
async def my_custom_query(query: str, user_id: Optional[str] = None) -> str:
    """自定义查询工具"""
    async with get_db_connection() as connection:
        # execute_query 会自动应用权限过滤
        results = await execute_query(connection, query, user_id=user_id)
        return json.dumps(results, default=str)
```

**修改权限字段或表配置**：

如果数据库使用不同的权限字段或角色表结构，修改 `.env` 配置：

```env
# 使用自定义权限字段
PERMISSION_FIELD=dept_id

# 使用自定义角色表
USER_ROLE_TABLE=sys_user_permissions
USER_ROLE_USERNAME_FIELD=user_name
USER_ROLE_EXTEND_FIELD=permission_scope
USER_ROLE_PREFIX=DEPT_
```

### 注意事项

- 仅对 **SELECT 查询**应用权限过滤（UPDATE/DELETE/INSERT 不受影响）
- 权限过滤在 SQL 安全检查**之前**执行，过滤后的 SQL 仍需通过安全检查
- `user_id` 必须与 `fr_user_role.username` 字段匹配
- 表白名单为空时，不会应用任何权限过滤
- 生产环境建议配合数据库隔离功能一起使用

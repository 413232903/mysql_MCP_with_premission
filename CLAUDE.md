# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于 FastMCP 框架的 MySQL 查询服务器，通过 SSE 协议提供实时数据库操作能力。该项目具备多层安全机制、连接池管理、数据库隔离等企业级特性。

## 核心架构

### 1. 分层架构设计

```
server.py (主入口)
    ↓
tools/ (MCP工具层 - 自动注册机制)
    ↓
db/mysql_operations.py (数据库操作层 - 连接池管理)
    ↓
security/ (安全拦截层 - SQL检查、数据库隔离)
```

### 2. 关键组件

**服务器入口** (`src/server.py`):
- 使用 FastMCP 框架创建 SSE 服务器
- **SSE 路径配置**: 使用 `sse_path='/sse2'` 参数配置 SSE 端点路径
- **传输协议**: 使用 `mcp.run('sse')` 启动 SSE 传输模式
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

服务器将监听在 `http://127.0.0.1:3000/sse2` (默认配置)

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

目前项目没有配置测试框架。添加测试时：
- 在 `tests/` 目录下创建测试文件
- 建议使用 pytest 作为测试框架
- 重点测试安全机制、连接池管理、SQL 拦截器

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

每个 SQL 查询的安全检查顺序：
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
- mcp >= 1.4.1
- aiomysql >= 0.2.0
- sqlparse >= 0.5.3
- cryptography >= 3.4.8 (MySQL 8.0 认证支持)

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
5. **向后兼容**：`user_id` 为可选参数，不传入时不应用权限过滤

### 实现层级

权限过滤在**数据库操作层**实现（`src/db/mysql_operations.py:execute_query`），在 SQL 执行前自动注入权限条件。执行顺序：

```
1. 用户调用 MCP 工具（传入 user_id）
   ↓
2. execute_query 接收原始 SQL 和 user_id
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

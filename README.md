# MySQL查询服务器 / MySQL Query Server

---

## 1. 项目简介 / Project Introduction

本项目是基于MCP框架的MySQL查询服务器，支持通过SSE协议进行实时数据库操作，具备完善的安全、日志、配置和敏感信息保护机制，适用于开发、测试和生产环境下的安全MySQL数据访问。

This project is a MySQL query server based on the MCP framework, supporting real-time database operations via SSE protocol. It features comprehensive security, logging, configuration, and sensitive information protection mechanisms, suitable for secure MySQL data access in development, testing, and production environments.

---

## 2. 主要特性 / Key Features

- 基于FastMCP框架，异步高性能
- 支持高并发的数据库连接池，参数灵活可调
- 支持SSE实时推送
- 丰富的MySQL元数据与结构查询API
- 自动事务管理与回滚
- 多级SQL风险控制与注入防护
- **数据库隔离安全**：防止跨数据库访问，支持三级访问控制
- 敏感信息自动隐藏与自定义
- 灵活的环境变量配置
- 完善的日志与错误处理
- Docker支持，快速部署

- Built on FastMCP framework, high-performance async
- Connection pool for high concurrency, with flexible parameter tuning
- SSE real-time push support
- Rich MySQL metadata & schema query APIs
- Automatic transaction management & rollback
- Multi-level SQL risk control & injection protection
- **Database Isolation Security**: Prevents cross-database access with 3-level access control
- Automatic and customizable sensitive info masking
- Flexible environment variable configuration
- Robust logging & error handling
- Docker support for quick deployment

---

## 3. 快速开始 / Quick Start

### Docker 方式 / Docker Method

```bash
# 拉取镜像
docker pull mangooer/mysql-mcp-server-sse:latest

# 运行容器
docker run -d \
  --name mysql-mcp-server-sse \
  -e HOST=0.0.0.0 \
  -e PORT=3000 \
  -e MYSQL_HOST=your_mysql_host \
  -e MYSQL_PORT=3306 \
  -e MYSQL_USER=your_mysql_user \
  -e MYSQL_PASSWORD=your_mysql_password \
  -e MYSQL_DATABASE=your_database \
  -p 3000:3000 \
  mangooer/mysql-mcp-server-sse:latest
```

Windows PowerShell 格式：
```powershell
docker run -d `
  --name mysql-mcp-server-sse `
  -e HOST=0.0.0.0 `
  -e PORT=3000 `
  -e MYSQL_HOST=your_mysql_host `
  -e MYSQL_PORT=3306 `
  -e MYSQL_USER=your_mysql_user `
  -e MYSQL_PASSWORD=your_mysql_password `
  -e MYSQL_DATABASE=your_database `
  -p 3000:3000 `
  mangooer/mysql-mcp-server-sse:latest
```

### 源码方式 / Source Code Method

#### 安装依赖 / Install Dependencies
```bash
pip install -r requirements.txt
```

#### 配置环境变量 / Configure Environment Variables
复制`.env.example`为`.env`，并根据实际情况修改。
Copy `.env.example` to `.env` and modify as needed.

#### 启动服务 / Start the Server
```bash
python -m src.server
```
默认监听地址：`http://{HOST}:{PORT}{MOUNT_PATH.rstrip('/')}{SSE_PATH}`（默认 `http://127.0.0.1:3000/sse2`）
Default endpoint: `http://{HOST}:{PORT}{MOUNT_PATH.rstrip('/')}{SSE_PATH}` (defaults to `http://127.0.0.1:3000/sse2`)

---

## 4. 目录结构 / Project Structure

```
.
├── src/
│   ├── server.py           # 主服务器入口 / Main server entry
│   ├── config.py           # 配置项定义 / Config definitions
│   ├── validators.py       # 参数校验 / Parameter validation
│   ├── db/
│   │   └── mysql_operations.py # 数据库操作 / DB operations
│   ├── security/
│   │   ├── interceptor.py      # SQL拦截 / SQL interception
│   │   ├── query_limiter.py    # 风险控制 / Risk control
│   │   └── sql_analyzer.py     # SQL分析 / SQL analysis
│   └── tools/
│       ├── mysql_tool.py           # 基础查询 / Basic query
│       ├── mysql_metadata_tool.py  # 元数据查询 / Metadata query
│       ├── mysql_info_tool.py      # 信息查询 / Info query
│       ├── mysql_schema_tool.py    # 结构查询 / Schema query
│       └── metadata_base_tool.py   # 工具基类 / Tool base class
├── tests/                  # 测试 / Tests
├── .env.example            # 环境变量示例 / Env example
└── requirements.txt        # 依赖 / Requirements
```

---

## 5. 环境变量与配置 / Environment Variables & Configuration

| 变量名 / Variable         | 说明 / Description                                   | 默认值 / Default |
|--------------------------|------------------------------------------------------|------------------|
| HOST                     | 服务器监听地址 / Server listen address                | 127.0.0.1        |
| PORT                     | 服务器监听端口 / Server listen port                   | 3000             |
| MOUNT_PATH               | MCP基础挂载路径 / MCP base mount path                 | /                |
| SSE_PATH                 | SSE推送端点路径 / SSE endpoint path                   | /sse2            |
| MYSQL_HOST               | MySQL服务器地址 / MySQL server host                   | localhost        |
| MYSQL_PORT               | MySQL服务器端口 / MySQL server port                   | 3306             |
| MYSQL_USER               | MySQL用户名 / MySQL username                          | root             |
| MYSQL_PASSWORD           | MySQL密码 / MySQL password                            | (空/empty)       |
| MYSQL_DATABASE           | 要连接的数据库名 / Database name                      | (空/empty)       |
| DB_CONNECTION_TIMEOUT    | 连接超时时间(秒) / Connection timeout (seconds)       | 5                |
| DB_AUTH_PLUGIN           | 认证插件类型 / Auth plugin type                       | mysql_native_password |
| DB_POOL_ENABLED          | 是否启用连接池 / Enable connection pool (true/false)  | true             |
| DB_POOL_MIN_SIZE         | 连接池最小连接数 / Pool min size                      | 5                |
| DB_POOL_MAX_SIZE         | 连接池最大连接数 / Pool max size                      | 20               |
| DB_POOL_RECYCLE          | 连接回收时间(秒) / Pool recycle time (seconds)        | 300              |
| DB_POOL_MAX_LIFETIME     | 连接最大存活时间(秒, 0=不限制) / Max lifetime (sec)   | 0                |
| DB_POOL_ACQUIRE_TIMEOUT  | 获取连接超时时间(秒) / Acquire timeout (seconds)      | 10.0             |
| ENV_TYPE                 | 环境类型(development/production) / Env type           | development      |
| ALLOWED_RISK_LEVELS      | 允许的风险等级(逗号分隔) / Allowed risk levels        | LOW,MEDIUM       |
| ALLOW_SENSITIVE_INFO     | 允许查询敏感字段 / Allow sensitive info (true/false)  | false            |
| SENSITIVE_INFO_FIELDS    | 自定义敏感字段模式(逗号分隔) / Custom sensitive fields | (空/empty)       |
| MAX_SQL_LENGTH           | 最大SQL语句长度 / Max SQL length                      | 5000             |
| BLOCKED_PATTERNS         | 阻止的SQL模式(逗号分隔) / Blocked SQL patterns        | (空/empty)       |
| ENABLE_QUERY_CHECK       | 启用查询安全检查 / Enable query check (true/false)    | true             |
| **ENABLE_DATABASE_ISOLATION** | **启用数据库隔离 / Enable database isolation (true/false)** | **false** |
| **DATABASE_ACCESS_LEVEL** | **数据库访问级别 / Database access level (strict/restricted/permissive)** | **permissive** |
| **ENABLE_ROLE_PERMISSION** | **启用角色权限控制（行级权限）/ Enable role permission (true/false)** | **false** |
| **PERMISSION_TABLES** | **需要权限过滤的表（逗号分隔）/ Permission tables (comma-separated)** | **(空/empty)** |
| **PERMISSION_FIELD** | **权限字段名称 / Permission field name** | **gssq** |
| **USER_ROLE_TABLE** | **用户角色表名 / User role table name** | **fr_user_role** |
| **USER_ROLE_USERNAME_FIELD** | **用户角色表中的用户名字段 / Username field in user role table** | **username** |
| **USER_ROLE_EXTEND_FIELD** | **用户角色表中存储权限的字段 / Permission field in user role table** | **extend1** |
| **USER_ROLE_PREFIX** | **权限标识前缀 / Permission prefix** | **RX** |
| **SUPER_ADMIN_USERS** | **超级管理员列表（逗号分隔）/ Super admin users (comma-separated)** | **(空/empty)** |
| LOG_LEVEL                | 日志级别(DEBUG/INFO/...) / Log level                 | DEBUG            |

> 注/Note: 部分云MySQL需指定`DB_AUTH_PLUGIN`为`mysql_native_password`。

### SSE 路由配置说明 / SSE Route Configuration

1. 在 `.env` 中设置 `SSE_PATH`（如 `/sse3`）即可切换推送端点，必要时搭配 `MOUNT_PATH`（如 `/api`）组合完整访问路径。
2. 服务端会自动拼接 `http://HOST:PORT{MOUNT_PATH.rstrip('/')}{SSE_PATH}`，因此 `MOUNT_PATH=/api` 且 `SSE_PATH=/sse3` 时，最终地址为 `http://HOST:PORT/api/sse3`。
3. 所有启动脚本（`src/server.py`、`start_server_debug.py`、`test_actual_server.py`、`diagnose_and_fix.sh`）均通过 `ServerConfig` 读取同一配置，避免硬编码导致路由不一致。
4. 如需了解更多 FastMCP 运行方式与传输协议选择，可参考官方部署文档，掌握 `sse_path` 与 `run(transport='sse')` 的配置细节 [[FastMCP 路由配置指南](https://www.aidoczh.com/fastmcp/deployment/running-server.html)].

### MySQL 8.0 认证支持 / MySQL 8.0 Authentication Support

本系统完全支持 MySQL 8.0 的认证机制。MySQL 8.0 默认使用 `caching_sha2_password` 认证插件，提供更高的安全性。

This system fully supports MySQL 8.0 authentication mechanisms. MySQL 8.0 uses `caching_sha2_password` by default for enhanced security.

#### 认证插件对比 / Authentication Plugin Comparison

| 认证插件 / Plugin | 安全性 / Security | 兼容性 / Compatibility | 依赖要求 / Dependencies |
|------------------|-------------------|------------------------|------------------------|
| `mysql_native_password` | 中等 / Medium | 高 / High | 无 / None |
| `caching_sha2_password` | 高 / High | 中等 / Medium | cryptography |

#### 配置建议 / Configuration Recommendations

**生产环境 / Production**（推荐 / Recommended）：
```ini
DB_AUTH_PLUGIN=caching_sha2_password
```

**开发环境 / Development**（简化配置 / Simplified）：
```ini
DB_AUTH_PLUGIN=mysql_native_password
```

#### 依赖安装 / Dependency Installation

使用 `caching_sha2_password` 时需要安装 `cryptography` 包（已包含在 requirements.txt 中）：

When using `caching_sha2_password`, the `cryptography` package is required (already included in requirements.txt):

```bash
pip install cryptography
```


### 数据库隔离安全 / Database Isolation Security

本系统提供强大的数据库隔离功能，防止跨数据库访问，确保数据安全。

This system provides robust database isolation features to prevent cross-database access and ensure data security.

#### 访问级别 / Access Levels

| 级别 / Level | 允许访问 / Allowed Access | 适用场景 / Use Case |
|-------------|---------------------------|-------------------|
| **strict** | 仅指定数据库 / Only specified database | 生产环境 / Production |
| **restricted** | 指定数据库 + 系统库 / Specified + system databases | 开发环境 / Development |
| **permissive** | 所有数据库 / All databases | 测试环境 / Testing |

#### 启用数据库隔离 / Enable Database Isolation

```bash
# Docker 启用严格模式 / Docker with strict mode
docker run -d \
  -e MYSQL_DATABASE=your_database \
  -e ENABLE_DATABASE_ISOLATION=true \
  -e DATABASE_ACCESS_LEVEL=strict \
  mangooer/mysql-mcp-server-sse:latest

# 生产环境自动启用 / Auto-enable in production
docker run -d \
  -e ENV_TYPE=production \
  -e MYSQL_DATABASE=your_database \
  mangooer/mysql-mcp-server-sse:latest
```

**安全效果 / Security Effects**：
- ✅ 阻止 `SHOW DATABASES` / Blocks `SHOW DATABASES`
- ✅ 阻止 `SELECT * FROM mysql.user` / Blocks `SELECT * FROM mysql.user`
- ✅ 阻止 `SHOW TABLES FROM other_db` / Blocks `SHOW TABLES FROM other_db`
- ✅ 允许当前数据库操作 / Allows current database operations

> 🔒 **重要**：生产环境(`ENV_TYPE=production`)会自动启用数据库隔离，使用 `restricted` 模式。
> 
> 🔒 **Important**: Production environment (`ENV_TYPE=production`) automatically enables database isolation with `restricted` mode.

---

## 6. 自动化与资源管理优化 / Automation & Resource Management Enhancements

### 自动化工具注册 / Automated Tool Registration
- 所有MySQL相关API工具均采用自动注册机制：
  - 无需手动在主入口维护注册代码，新增/删除工具只需在`src/tools/`目录下实现`register_xxx_tool(s)`函数即可。
  - 系统启动时自动扫描并注册，极大提升可维护性和扩展性。
- All MySQL-related API tools are registered automatically:
  - No need to manually maintain registration code in the main entry. To add or remove a tool, simply implement a `register_xxx_tool(s)` function in the `src/tools/` directory.
  - The system scans and registers tools automatically at startup, greatly improving maintainability and extensibility.

### 连接池自动回收与资源管理 / Connection Pool Auto-Recycling & Resource Management
- 连接池采用事件循环隔离与自动回收机制：
  - 每个事件循环独立池，支持高并发与多环境。
  - 定期（默认每5分钟）自动回收无效或失效的连接池，防止资源泄漏。
  - 事件循环关闭时自动关闭对应连接池，确保资源彻底释放。
  - 支持多数据库/多租户场景扩展。
- 所有资源管理操作均有详细日志，便于追踪和排查。
- The connection pool uses event loop isolation and auto-recycling:
  - Each event loop has its own pool, supporting high concurrency and multi-environment deployment.
  - Unused or invalid pools are automatically recycled every 5 minutes (by default), preventing resource leaks.
  - When an event loop is closed, its pool is automatically closed to ensure complete resource release.
  - Ready for multi-database/multi-tenant scenarios.
- All resource management operations are logged in detail for easy tracking and troubleshooting.

---

## 7. 安全机制 / Security Mechanisms

- 多级SQL风险等级（LOW/MEDIUM/HIGH/CRITICAL）
- SQL注入与危险操作拦截
- WHERE子句强制检查
- **数据库隔离安全**：三级访问控制（strict/restricted/permissive）
- **跨数据库访问防护**：阻止未授权的数据库访问
- 敏感信息自动隐藏（支持自定义字段）
- 生产环境默认只允许低风险操作
- **生产环境自动启用数据库隔离**

- Multi-level SQL risk levels (LOW/MEDIUM/HIGH/CRITICAL)
- SQL injection & dangerous operation interception
- Mandatory WHERE clause check
- **Database Isolation Security**: 3-level access control (strict/restricted/permissive)
- **Cross-database Access Protection**: Blocks unauthorized database access
- Automatic sensitive info masking (customizable fields)
- Production allows only low-risk operations by default
- **Auto-enable database isolation in production**

---

## 8. 日志与错误处理 / Logging & Error Handling

- 日志级别可配置（LOG_LEVEL）
- 控制台与文件日志输出
- 详细记录运行状态与错误
- 完善的异常捕获与事务回滚

- Configurable log level (LOG_LEVEL)
- Console & file log output
- Detailed running status & error logs
- Robust exception capture & transaction rollback

---

## 9. 常见问题 / FAQ

### Q: DELETE操作未执行成功？
A: 检查是否有WHERE条件，无WHERE为高风险，需在ALLOWED_RISK_LEVELS中允许CRITICAL。

Q: Why does DELETE not work?
A: Check for WHERE clause. DELETE without WHERE is high risk (CRITICAL), must be allowed in ALLOWED_RISK_LEVELS.

### Q: 如何自定义敏感字段？
A: 设置SENSITIVE_INFO_FIELDS，如SENSITIVE_INFO_FIELDS=password,token

Q: How to customize sensitive fields?
A: Set SENSITIVE_INFO_FIELDS, e.g. SENSITIVE_INFO_FIELDS=password,token

### Q: 如何启用数据库隔离？
A: 设置ENABLE_DATABASE_ISOLATION=true和DATABASE_ACCESS_LEVEL=strict，或使用ENV_TYPE=production自动启用。

Q: How to enable database isolation?
A: Set ENABLE_DATABASE_ISOLATION=true and DATABASE_ACCESS_LEVEL=strict, or use ENV_TYPE=production for auto-enable.

### Q: 数据库隔离后无法查询系统表？
A: strict模式禁止系统表访问，可改为restricted模式，或检查是否确实需要系统表访问权限。

Q: Cannot query system tables after enabling database isolation?
A: strict mode blocks system table access. Use restricted mode or verify if system table access is actually needed.

### Q: limit参数报错？
A: limit必须为非负整数。

Q: limit parameter error?
A: limit must be a non-negative integer.

### Q: 行级权限没有生效？
A: 请按以下步骤排查：
1. 检查是否启用了权限控制：在 `.env` 中设置 `ENABLE_ROLE_PERMISSION=true`
2. 检查是否配置了权限表：设置 `PERMISSION_TABLES=表名1,表名2,...`
3. 检查调用时是否传入了 `user_id` 参数：`mysql_query(query='...', user_id='用户名')`
4. 检查 `user_id` 是否在 `SUPER_ADMIN_USERS` 中（超级管理员会跳过权限检查）
5. 检查查询的表名是否在 `PERMISSION_TABLES` 配置中
6. 检查 SQL 是否为 SELECT 查询（其他操作类型不应用权限过滤）
7. 运行诊断脚本：`python diagnose_permission.py` 查看详细配置信息
8. 查看服务器日志中的权限相关调试信息

Q: Row-level permission not working?
A: Please check:
1. Enable permission control: Set `ENABLE_ROLE_PERMISSION=true` in `.env`
2. Configure permission tables: Set `PERMISSION_TABLES=table1,table2,...`
3. Pass `user_id` parameter when calling: `mysql_query(query='...', user_id='username')`
4. Check if `user_id` is in `SUPER_ADMIN_USERS` (super admins skip permission check)
5. Check if query table is in `PERMISSION_TABLES`
6. Check if SQL is a SELECT query (other operations don't apply permission filter)
7. Run diagnostic script: `python diagnose_permission.py`
8. Check server logs for permission-related debug info

---

## 10. 贡献指南 / Contribution Guide

欢迎通过Issue和Pull Request参与改进。
Contributions via Issue and Pull Request are welcome.

---

## 11. 许可证 / License

MIT License

本软件按"原样"提供，不提供任何形式的明示或暗示的保证，包括但不限于对适销性、特定用途的适用性和非侵权性的保证。在任何情况下，作者或版权持有人均不对任何索赔、损害或其他责任负责，无论是在合同诉讼、侵权行为还是其他方面，产生于、源于或与本软件有关，或与本软件的使用或其他交易有关。  
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

## 12. 路由修改总结与反思 / Route Update Summary & Reflection

- **修改内容**：引入 `MOUNT_PATH`、`SSE_PATH` 环境变量，并让核心服务与辅助脚本统一读取配置，自动拼接最终访问路径，消除 `/sse` 与 `/sse2` 混用隐患。
- **验证要点**：启动日志、调试脚本与诊断脚本均输出同一 URL，使用 `curl http://HOST:PORT{MOUNT_PATH.rstrip('/')}{SSE_PATH}` 快速验证；若需更换后缀仅修改 `.env` 即可。
- **经验总结**：遵循 FastMCP 官方建议将路由定义在初始化参数中，同时保持 `mcp.run('sse')` 的传输协议不变，可避免回退到默认 `/sse`；集中化配置能减少多处修改带来的失误。
- **后续建议**：结合部署环境准备一键化脚本导出访问地址，并补充自动化测试覆盖不同 `SSE_PATH`/`MOUNT_PATH` 组合，进一步防止配置漂移。

---

## 13. 角色权限控制修复总结 / Role Permission Enforcement Summary

- **问题回顾**：生产环境中带库名前缀、CTE 或包含头部注释的查询未触发 `RolePermissionManager` 的过滤，导致行级权限未生效。
- **修复内容**：基于 `sqlparse` 精确解析 `SELECT` 语句与 `FROM/JOIN` 表名，支持 `database.table`、多表 JOIN、CTE 与注释场景，同时保留超级管理员豁免机制。
- **验证方式**：
  - 新增单元测试 `tests/test_role_permission.py`，覆盖前述复杂语句，运行 `python -m unittest tests.test_role_permission` 可快速回归。
  - 观察运行日志中"解析到的表名"调试信息，确认权限过滤命中目标表后才会注入条件。
- **排障建议**：若过滤未生效，优先检查环境变量 `ENABLE_ROLE_PERMISSION`、`PERMISSION_TABLES` 是否配置正确，并使用上述单元测试样例构造 SQL 在非生产环境复现问题。

---

## 14. 行级权限配置指南 / Row-Level Permission Configuration Guide

### 功能说明 / Function Description

行级权限控制基于数据库表中的权限字段（默认 `gssq`）实现数据访问控制。启用后，系统会自动向 SELECT 查询注入权限过滤条件，确保用户只能查询到其有权限访问的数据。

Row-level permission control is based on permission fields (default `gssq`) in database tables. When enabled, the system automatically injects permission filter conditions into SELECT queries to ensure users can only query data they have permission to access.

### 工作原理 / How It Works

**权限规则 / Permission Rule**：
```sql
WHERE gssq IN (
    SELECT REPLACE(extend1, 'RX', '') FROM fr_user_role WHERE username='[userId]'
)
OR '[userId]' NOT IN (SELECT username FROM fr_user_role)
```

**逻辑说明 / Logic**：
1. 如果用户在 `fr_user_role` 表中有记录，只能查询 `gssq` 在其 `extend1` 字段定义的权限范围内的数据
2. 如果用户不在 `fr_user_role` 表中，可以查询所有数据（默认全部权限）
3. 超级管理员（配置在 `SUPER_ADMIN_USERS`）豁免权限检查

### 配置步骤 / Configuration Steps

1. **启用权限控制 / Enable Permission Control**
   ```env
   ENABLE_ROLE_PERMISSION=true
   ```

2. **配置权限表 / Configure Permission Tables**
   ```env
   PERMISSION_TABLES=orders,products,customers,invoices
   ```

3. **（可选）自定义配置 / Optional Customization**
   ```env
   PERMISSION_FIELD=gssq                    # 权限字段名
   USER_ROLE_TABLE=fr_user_role           # 用户角色表
   USER_ROLE_USERNAME_FIELD=username       # 用户名字段
   USER_ROLE_EXTEND_FIELD=extend1         # 权限存储字段
   USER_ROLE_PREFIX=RX                     # 权限前缀
   SUPER_ADMIN_USERS=admin,system          # 超级管理员
   ```

4. **调用时传入 user_id / Pass user_id When Calling**
   ```python
   result = await mysql_query(
       query="SELECT * FROM orders WHERE status='pending'",
       user_id="zhang_san"  # 必须传入用户ID
   )
   ```

### 诊断工具 / Diagnostic Tool

运行诊断脚本检查配置：
```bash
python diagnose_permission.py
```

该脚本会检查：
- 权限控制是否启用
- 权限表是否配置
- 配置项是否正确
- SQL 解析是否正常

### 常见问题排查 / Troubleshooting

**问题：权限没有生效**

**排查步骤**：
1. ✅ 运行 `python diagnose_permission.py` 检查配置
2. ✅ 确认 `.env` 文件中 `ENABLE_ROLE_PERMISSION=true`
3. ✅ 确认 `PERMISSION_TABLES` 配置了查询的表名
4. ✅ 确认调用时传入了 `user_id` 参数
5. ✅ 确认 `user_id` 不在 `SUPER_ADMIN_USERS` 列表中
6. ✅ 确认 SQL 是 SELECT 查询（其他操作不应用权限）
7. ✅ 查看服务器日志中的权限相关调试信息

**日志示例 / Log Example**：
```
INFO - ✅ 角色权限控制已启用: 权限表=['orders', 'products'], 权限字段=gssq
INFO - ✅ 已为用户 zhang_san 注入权限过滤条件
INFO - 📝 原始 SQL: SELECT * FROM orders WHERE status='pending'
INFO - 🔒 修改后 SQL: SELECT * FROM orders WHERE status='pending' AND (gssq IN ...)
```

如果看到 "⚠️ 未提供 user_id 参数" 或 "查询不涉及权限控制表" 等警告，请根据提示修复配置。
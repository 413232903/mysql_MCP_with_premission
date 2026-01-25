---
marp: true
theme: gaia
paginate: true
size: 16:9
---

<!-- _class: lead -->
# MySQL MCP 服务器

## 基于 FastMCP 框架的安全数据库查询服务

---

# 目录

1. 项目概述
2. 核心架构
3. 主要特性
4. 安全机制
5. 部署方式
6. 行级权限控制

---

# 1. 项目概述

## 简介

基于 MCP (Model Context Protocol) 框架的 MySQL 查询服务器，通过 SSE (Server-Sent Events) 协议提供实时数据库操作能力。

### 技术栈
- **Python 3.12+**
- **FastMCP** - MCP 服务器框架
- **aiomysql** - 异步 MySQL 驱动
- **sqlparse** - SQL 解析与分析
- **SSE** - 实时推送协议

---

# 2. 核心架构

## 分层设计

```
┌─────────────────────────────────────┐
│   server.py (主入口)              │
│   - FastMCP 服务器               │
│   - SSE 路由配置                 │
│   - 工具自动注册                 │
└─────────────┬───────────────────┘
              │
┌─────────────▼───────────────────┐
│   tools/ (MCP 工具层)          │
│   - mysql_tool                  │
│   - mysql_metadata_tool         │
│   - mysql_schema_tool           │
│   - mysql_info_tool             │
└─────────────┬───────────────────┘
              │
┌─────────────▼───────────────────┐
│   db/mysql_operations.py         │
│   - 连接池管理                 │
│   - 事务管理                   │
│   - 流式查询                   │
└─────────────┬───────────────────┘
              │
┌─────────────▼───────────────────┐
│   security/ (安全拦截层)        │
│   - SQL 拦截器                │
│   - 数据库隔离                 │
│   - 角色权限控制               │
└─────────────────────────────────┘
```

---

# 3. 主要特性

## 核心功能

| 特性 | 描述 |
|-----|------|
| **异步高性能** | 基于 asyncio 的异步架构 |
| **连接池管理** | 事件循环隔离，自动回收 |
| **SSE 实时推送** | 支持 Server-Sent Events |
| **自动工具注册** | 无需手动维护注册代码 |
| **事务管理** | 自动提交与回滚 |
| **流式查询** | 大数据集分批获取 |

## 数据库操作

- SELECT 查询
- INSERT/UPDATE/DELETE
- 元数据查询 (SHOW, DESC)
- 结构查询 (Schema)
- 事务支持

---

# 4. 安全机制

## 多层安全防护

### 1. SQL 风险等级控制
```
LOW    → SELECT 查询
MEDIUM → 有 WHERE 的修改操作
HIGH    → 无 WHERE 的修改操作
CRITICAL → DROP/TRUNCATE 等
```

### 2. 数据库隔离
```
strict      → 仅指定数据库
restricted  → 指定数据库 + 系统库
permissive   → 所有数据库
```

### 3. SQL 注入防护
- 参数化查询支持
- 敏感信息自动隐藏
- 危险操作拦截

### 4. 行级权限控制
- 基于 gssq 字段的权限过滤
- 自动注入权限条件
- 超级管理员豁免

---

# 5. 部署方式

## Docker 部署（推荐）

```bash
# 拉取镜像
docker pull mangooer/mysql-mcp-server-sse:latest

# 运行容器
docker run -d \
  --name mysql-mcp-server-sse \
  -e MYSQL_HOST=your_host \
  -e MYSQL_USER=your_user \
  -e MYSQL_PASSWORD=your_password \
  -e MYSQL_DATABASE=your_database \
  -e ENABLE_ROLE_PERMISSION=true \
  -e PERMISSION_TABLES=table1,table2 \
  -p 3000:3000 \
  mangooer/mysql-mcp-server-sse:latest
```

## 源码部署

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env

# 启动服务
python -m src.server
```

---

# 6. 行级权限控制

## 工作原理

```
查询: SELECT * FROM orders WHERE status='pending'
         ↓
注入权限条件
         ↓
过滤后: SELECT * FROM orders
        WHERE status='pending'
        AND (
            gssq IN (
                SELECT REPLACE(extend1, 'RX', '')
                FROM fr_user_role
                WHERE username='user_id'
            )
            OR 'user_id' NOT IN (
                SELECT username FROM fr_user_role
            )
        )
```

## 配置示例

```env
# 启用角色权限控制
ENABLE_ROLE_PERMISSION=true

# 需要权限过滤的表
PERMISSION_TABLES=orders,products

# 权限字段
PERMISSION_FIELD=gssq

# 用户角色表
USER_ROLE_TABLE=fr_user_role
USER_ROLE_USERNAME_FIELD=username
USER_ROLE_EXTEND_FIELD=extend1
```

---

# 调用方式

## 方式 1: 通过参数传递

```python
mysql_query(
    query="SELECT * FROM orders",
    user_id="user123"
)
```

## 方式 2: 通过 SSE URL 传递（推荐）

```
连接: http://server:3000/sse2?user_id=user123
```

系统会自动从 URL 参数提取用户 ID。

---

# 环境变量配置

## 核心配置

| 变量 | 说明 | 默认值 |
|-----|------|-------|
| `HOST` | 服务器地址 | 127.0.0.1 |
| `PORT` | 服务器端口 | 3000 |
| `SSE_PATH` | SSE 路径 | /sse2 |
| `MYSQL_DATABASE` | 数据库名 | （必须设置）|
| `ENABLE_ROLE_PERMISSION` | 启用权限 | false |
| `PERMISSION_TABLES` | 权限表列表 | （空）|
| `ALLOWED_RISK_LEVELS` | 允许风险等级 | LOW,MEDIUM |
| `LOG_LEVEL` | 日志级别 | DEBUG |

---

# 故障排查

## 常见问题

### 1. 权限过滤未生效

```
检查清单:
✓ ENABLE_ROLE_PERMISSION=true
✓ PERMISSION_TABLES 配置正确
✓ 传递了 user_id 参数
✓ 查询的表在 PERMISSION_TABLES 中
✓ SQL 是 SELECT 查询
```

### 2. 连接池问题

```
检查:
✓ DB_POOL_ENABLED=true
✓ 数据库连接信息正确
✓ 事件循环正常
```

### 3. 查看详细日志

```bash
# 设置日志级别
LOG_LEVEL=DEBUG

# 查看权限提取日志
🔥 用户 ID 提取调试
🔐 权限控制检查开始
✅ 权限检查通过
```

---

# 工具注册机制

## 自动注册

所有 MCP 工具必须放在 `src/tools/` 目录下：

```python
def register_xxx_tool(mcp: FastMCP):
    @mcp.tool()
    async def tool_name(...):
        # 工具实现
        pass
```

命名规则：
- 必须以 `register_` 开头
- 必须以 `tool` 或 `tools` 结尾

无需修改 `server.py`，工具将自动注册！

---

# 总结

## 优势

✅ **安全可靠** - 多层安全机制，严格权限控制
✅ **高性能** - 异步架构，连接池管理
✅ **易部署** - Docker 一键部署
✅ **易扩展** - 自动工具注册
✅ **企业级** - 事务管理，流式查询

## 适用场景

- AI 数据库查询
- 企业内部数据访问
- 行级权限控制
- 安全的数据库 API

---

# 谢谢！

## Q & A

GitHub: https://github.com/413232903/mysql_MCP_with_premission

---

<!-- _class: lead -->
# MySQL MCP 服务器

## 安全 · 高效 · 易用

---

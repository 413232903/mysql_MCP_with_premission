# SSE2 路径修复说明

## 🔍 问题分析

### 原因
代码使用了错误的 FastMCP 参数名称，导致 SSE 路径配置未生效。

### 问题位置
在 `src/server.py` 文件中有两处错误：

1. **第 52 行** - 错误的参数名：
   ```python
   # ❌ 错误：使用了不存在的 endpoint 参数
   mcp = FastMCP(..., endpoint='/sse2')
   ```

2. **第 186 行** - 错误的 transport 参数值：
   ```python
   # ❌ 错误：'sse2' 不是有效的 transport 类型
   mcp.run('sse2')
   ```

### FastMCP 正确的参数说明

根据 FastMCP 框架的官方参数定义：

**FastMCP.__init__ 参数：**
- ✅ `sse_path: str = '/sse'` - SSE 路径配置（默认 '/sse'）
- ✅ `mount_path: str = '/'` - 挂载路径配置（默认 '/'）
- ❌ `endpoint` - 不存在此参数

**mcp.run() 参数：**
- `transport: Literal['stdio', 'sse', 'streamable-http']` - 传输协议类型
- 只能是以下三个值之一：
  - `'stdio'` - 标准输入输出
  - `'sse'` - Server-Sent Events（服务器推送事件）
  - `'streamable-http'` - 可流式传输的 HTTP

---

## ✅ 修复方案

### 修改 1：配置层新增可自定义路由

**位置：**`src/config.py`

```python
class ServerConfig:
    HOST = os.getenv('HOST', '127.0.0.1')
    PORT = int(os.getenv('PORT', '3000'))
    MOUNT_PATH = os.getenv('MOUNT_PATH', '/')
    SSE_PATH = os.getenv('SSE_PATH', '/sse2')
```

> 通过环境变量集中管理挂载路径与 SSE 端点，默认仍为 `/sse2`，但无需改动代码即可切换。

---

### 修改 2：服务器启动时统一归一化并写入 FastMCP

**位置：**`src/server.py`

```python
def _normalize_path(path: str, *, allow_root: bool = False) -> str:
    # 确保前导斜杠、去掉多余尾斜杠，禁止 SSE_PATH 为根路径
    ...

mount_path = _normalize_path(ServerConfig.MOUNT_PATH, allow_root=True)
sse_path = _normalize_path(ServerConfig.SSE_PATH)

mcp = FastMCP(
    "MySQL Query Server",
    "cccccccccc",
    host=host,
    port=port,
    debug=True,
    mount_path=mount_path,
    sse_path=sse_path,
)

mcp.run('sse', mount_path=mount_path)
```

> 这样既保留了 `transport='sse'` 协议，又确保运行时不会退回默认 `/sse`。

---

### 修改 3：调试脚本共用同一配置

**位置：**`start_server_debug.py`、`test_actual_server.py`、`diagnose_and_fix.sh`

```python
mount_path = _normalize_path(ServerConfig.MOUNT_PATH, allow_root=True)
sse_path = _normalize_path(ServerConfig.SSE_PATH)
```

> 所有辅助脚本都会打印当前挂载与 SSE 路径，方便排查环境变量与实际输出是否一致。

---

## 🎯 修复后的效果

### 启动服务器后：
```bash
$ python -m src.server
开始启动MySQL查询SSE服务器...
服务器监听在 127.0.0.1:3000/sse2  # 默认输出，若修改 .env 会显示新路径
```

### 访问地址：
- ✅ **正确访问地址：** `http://HOST:PORT{MOUNT_PATH.rstrip('/')}{SSE_PATH}`（默认 `http://127.0.0.1:3000/sse2`）
- ❌ **旧地址失效：** `http://127.0.0.1:3000/sse`

---

## 📚 技术原理说明

### 为什么会出现这个问题？

1. **参数名混淆：**
   - 代码作者可能以为参数名是 `endpoint`
   - 但 FastMCP 实际使用的是 `sse_path`
   - 当传入不存在的参数时，FastMCP 会忽略它并使用默认值 `'/sse'`
   - 现在通过 `ServerConfig.SSE_PATH` 统一管理，可避免再次填错参数名

2. **Transport 类型混淆：**
   - `mcp.run()` 的第一个参数是**传输协议类型**，不是路径
   - 路径已经在 `FastMCP()` 初始化时通过 `sse_path` 指定
   - `'sse2'` 不是有效的 transport 类型，应该用 `'sse'`

### FastMCP 的工作流程

```
1. 创建 FastMCP 实例
   └─> 读取并规范化 mount_path='/' 与 sse_path='/sse2'
       设置 host='127.0.0.1'，port=3000

2. 调用 mcp.run('sse', mount_path=mount_path)
   └─> 使用 'sse' 传输协议
       在地址 http://127.0.0.1:3000/sse2（或 .env 中自定义路径）启动服务
```

### 类比理解（用开餐厅的例子）

```
FastMCP 初始化 = 装修餐厅
├─ host = 餐厅街道地址
├─ port = 餐厅门牌号
└─ sse_path = 取餐窗口号码

mcp.run() = 开门营业
└─ transport = 营业方式（堂食/外卖/自提）
```

使用错误的参数名 `endpoint` 就像告诉装修工人一个不存在的指令，他们会按默认方案装修（使用 `/sse`）。

---

## 🔧 如何自定义 SSE 路径

假设你希望把接口改到 `/api/mysql`：

1. 在 `.env` 文件中写入：
   ```ini
   MOUNT_PATH=/api
   SSE_PATH=/mysql
   ```
2. 重启服务器，终端会打印新的完整地址（例如 `http://127.0.0.1:3000/api/mysql`）。
3. 调试脚本 `start_server_debug.py`、`diagnose_and_fix.sh` 会自动显示相同的 URL，方便核对是否配置成功。

---

## 📊 修复流程图

```mermaid
graph TD
    A[发现问题: /sse2 无法访问] --> B[新增 MOUNT_PATH/SSE_PATH 配置]
    B --> C[统一规范化路径]
    C --> D[FastMCP 注入 mount_path 与 sse_path]
    D --> E[mcp.run('sse', mount_path=mount_path)]
    E --> F[调试脚本输出完整 URL]
    F --> G[curl 测试新路径]
    G --> H{访问成功?}
    H -->|是| I[✅ 修复完成]
    J -->|否| L[检查防火墙/端口]
    
    style A fill:#ffcdd2
    style K fill:#c8e6c9
    style D fill:#fff9c4
    style E fill:#fff9c4
```

---

## ✅ 验证修复

### 1. 重启服务器
```bash
# 停止当前服务（如果正在运行）
# Ctrl+C 或 kill 进程

# 重新启动
python -m src.server
```

### 2. 查看启动日志
应该看到（若未修改 `.env`）：
```
开始启动MySQL查询SSE服务器...
服务器监听在 127.0.0.1:3000/sse2
```

### 3. 测试连接
使用浏览器或 curl 测试：
```bash
curl http://127.0.0.1:3000/sse2  # 如已修改 .env，请替换为新的完整路径
```

或在浏览器访问：`http://127.0.0.1:3000/sse2`

### 4. 如果仍无法访问
检查以下几点：
- ✅ 确认服务器已重启
- ✅ 检查端口 3000 是否被占用：`lsof -i :3000`
- ✅ 检查防火墙设置
- ✅ 确认 MySQL 连接配置正确（查看启动日志）

---

## 📝 总结

### 关键点
1. **FastMCP 使用 `sse_path` 而非 `endpoint`**
2. **`mcp.run()` 的参数是传输协议类型（'sse'），不是路径**
3. **路径在初始化时配置，run 时指定传输方式**

### 记忆口诀
```
创建时定路径 (sse_path)
运行时选协议 (transport='sse')
路径和协议，分清不混淆！
```

---

## 🎓 扩展知识

### SSE (Server-Sent Events) 是什么？

SSE 是一种服务器向客户端推送数据的技术：

**特点：**
- 单向通信（服务器 → 客户端）
- 基于 HTTP 协议
- 保持长连接
- 自动重连机制

**应用场景：**
- 实时日志推送
- 股票行情更新
- 聊天消息推送
- 数据库查询结果流式返回

**对比 WebSocket：**
| 特性 | SSE | WebSocket |
|------|-----|-----------|
| 通信方向 | 单向（服→客） | 双向 |
| 协议 | HTTP | WS/WSS |
| 复杂度 | 简单 | 复杂 |
| 适用场景 | 数据推送 | 实时交互 |

本项目使用 SSE 来推送数据库查询结果，非常适合这种场景！

---

## 🆘 常见问题

### Q1: 修改后还是无法访问 /sse2？
**A:** 确保服务器已完全重启。旧进程可能还在运行，使用 `ps aux | grep python` 查看并 kill 旧进程。

### Q2: 可以同时支持 /sse 和 /sse2 吗？
**A:** 不能。FastMCP 只支持一个 SSE 路径。如需多个路径，需要运行多个服务器实例。

### Q3: 为什么要用 /sse2 而不是默认的 /sse？
**A:** 这是项目的设计选择，可能是为了：
- 区分不同版本的 API
- 避免与其他服务冲突
- 自定义路由规范

### Q4: 如何添加路径前缀（如 /api/sse2）？
**A:** 使用 `mount_path` 和 `sse_path` 组合：
```python
mcp = FastMCP(..., mount_path='/api', sse_path='/sse2')
# 最终路径：/api/sse2
```

---

修复日期：2025-10-30
修复人：AI Assistant
文档版本：1.0


# SSE2 路径问题 - 完整解决方案

## 🔍 问题描述

修改代码后，服务器仍然只能通过 `/sse` 访问，而不是预期的 `/sse2`。

## ✅ 解决步骤

### 步骤1：确认配置与代码同步

1. `src/config.py` 中应包含新的环境变量：
   ```python
   class ServerConfig:
       HOST = os.getenv('HOST', '127.0.0.1')
       PORT = int(os.getenv('PORT', '3000'))
       MOUNT_PATH = os.getenv('MOUNT_PATH', '/')
       SSE_PATH = os.getenv('SSE_PATH', '/sse2')
   ```
2. `src/server.py` 需要读取并规范化路径：
   ```python
   mount_path = _normalize_path(ServerConfig.MOUNT_PATH, allow_root=True)
   sse_path = _normalize_path(ServerConfig.SSE_PATH)

   mcp = FastMCP(..., mount_path=mount_path, sse_path=sse_path)
   ...
   mcp.run('sse', mount_path=mount_path)
   ```
3. 辅助脚本（`start_server_debug.py`、`test_actual_server.py`、`diagnose_and_fix.sh`）也会调用相同的 `_normalize_path` 逻辑，启动后会打印实际监听地址。

### 步骤2：清除 Python 缓存

Python 可能在使用旧的编译缓存文件。运行以下命令清除缓存：

```bash
cd /Users/user/413232903.github.io/mysql-mcp-server-sse

# 清除所有缓存
rm -rf src/__pycache__ src/*/__pycache__
find . -name "*.pyc" -delete
```

### 步骤3：完全停止旧服务器

确保没有旧的服务器进程在运行：

```bash
# 查找运行中的 Python 进程
ps aux | grep "python.*server"

# 如果找到进程，kill 它
# kill <进程ID>

# 或者使用 pkill
pkill -f "python.*server"
```

### 步骤4：使用调试脚本启动

我为你创建了一个调试启动脚本 `start_server_debug.py`，它会显示详细的配置信息：

```bash
python start_server_debug.py
```

这个脚本会显示：
- 当前的 sse_path 配置
- 当前的 mount_path 配置
- 预期的访问地址

### 步骤5：重新启动服务器

使用正常的启动命令：

```bash
python -m src.server
```

## 📋 验证清单

启动服务器后，检查输出日志中是否包含：

```
Settings.sse_path: /sse2             # 若修改 .env 会显示新值
预期访问地址: http://127.0.0.1:3000/sse2  # 会根据 MOUNT_PATH/SSE_PATH 自动拼接
```

然后测试访问：

```bash
# 这个应该工作 ✅（如已自定义，请替换路径）
curl http://127.0.0.1:3000/sse2

# 这个应该失败 ❌
curl http://127.0.0.1:3000/sse
```

## 🐛 常见问题

### Q1: 仍然只能访问 /sse

**可能原因：**
1. Python 进程没有完全重启
2. 缓存没有清除
3. 代码没有保存

**解决方法：**
```bash
# 1. 强制杀死所有 Python 进程
pkill -9 python

# 2. 再次清除缓存
rm -rf src/__pycache__ src/*/__pycache__

# 3. 检查当前环境变量
grep SSE_PATH .env 2>/dev/null || echo "SSE_PATH 未在 .env 中显式设置（将使用默认 /sse2）"

# 4. 重新启动并观察输出
python start_server_debug.py
```

### Q2: 启动后没有显示 sse_path 信息

使用调试脚本 `start_server_debug.py` 可以看到详细信息。

### Q3: 修改代码后仍然不生效

检查是否在正确的目录：
```bash
pwd
# 应该显示: /Users/user/413232903.github.io/mysql-mcp-server-sse
```

检查是否修改了正确的文件：
```bash
cat src/server.py | grep -n "FastMCP.*host"
# 应该在第 52 行看到 sse_path='/sse2'
```

## 🎯 核心要点

### FastMCP 路径配置的正确方式

```python
# ✅ 正确
mcp = FastMCP(..., mount_path='/', sse_path='/sse2')  # 初始化时设置挂载与路径
mcp.run('sse', mount_path='/')                        # 运行时指定传输协议并保持同一路径

# ❌ 错误
mcp = FastMCP(..., endpoint='/sse2')  # endpoint 参数不存在
mcp.run('sse2')                       # 'sse2' 不是有效的传输协议
```

### 参数说明

- **sse_path**: SSE 端点路径（如 '/sse2', '/api/sse'）
- **mount_path**: 挂载路径（通常为 '/'）
- **transport**: 传输协议类型，必须是 'stdio', 'sse', 或 'streamable-http'

完整 URL = `http://{host}:{port}{mount_path.rstrip("/")}{sse_path}`

示例：
- host='127.0.0.1', port=3000, mount_path='/', sse_path='/sse2'
- 结果：`http://127.0.0.1:3000/sse2`

## 📝 测试脚本

### 快速测试命令

```bash
# 启动调试服务器（会显示配置信息）
python start_server_debug.py

# 在另一个终端测试
curl -v http://127.0.0.1:3000/sse2
```

## 🔧 最终检查

如果以上步骤都完成了但仍然不工作，请运行以下命令并将输出发给我：

```bash
# 检查代码
echo "=== 检查 FastMCP 初始化 ==="
grep -A2 "FastMCP.*host" src/server.py

echo ""
echo "=== 检查 mcp.run ==="
grep "mcp.run" src/server.py

echo ""
echo "=== 测试 FastMCP 配置 ==="
python -c "
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
load_dotenv()
from src.config import ServerConfig

def _normalize_path(path: str, allow_root: bool = False, fallback: str = '/sse'):
    if not path:
        return '/' if allow_root else fallback
    path = path.strip()
    if not path.startswith('/'):
        path = '/' + path
    if len(path) > 1:
        path = path.rstrip('/')
    if not allow_root and path == '/':
        raise ValueError("SSE 路径不能为根路径 '/', 请设置子路径")
    return path

mount_path = _normalize_path(ServerConfig.MOUNT_PATH, allow_root=True)
sse_path = _normalize_path(ServerConfig.SSE_PATH)

mcp = FastMCP('Test', host=ServerConfig.HOST, port=ServerConfig.PORT, mount_path=mount_path, sse_path=sse_path)
print(f'mount_path: {mcp.settings.mount_path}')
print(f'sse_path: {mcp.settings.sse_path}')
print(f'完整URL: http://{ServerConfig.HOST}:{ServerConfig.PORT}{mount_path.rstrip('/')}{sse_path}')
"
```

## 💡 提示

现在已经内置环境变量配置：直接在 `.env` 中调整 `MOUNT_PATH` 与 `SSE_PATH`，重启服务即可生效，无需再修改代码。

---

**创建日期**: 2025-10-30  
**最后更新**: 2025-11-05


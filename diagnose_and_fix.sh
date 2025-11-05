#!/bin/bash
# SSE2 问题诊断和修复脚本

echo "=========================================="
echo "SSE2 路径问题 - 自动诊断和修复"
echo "=========================================="
echo ""

# 切换到项目目录
cd "$(dirname "$0")"

echo "【当前配置】"
echo "---"
eval "$(python3 <<'PYEOF'
from dotenv import load_dotenv
load_dotenv()

from src.config import ServerConfig


def _normalize_path(path: str, allow_root: bool = False, fallback: str = '/sse') -> str:
    if not path:
        return '/' if allow_root else fallback
    path = path.strip()
    if not path.startswith('/'):
        path = '/' + path
    if len(path) > 1:
        path = path.rstrip('/')
    if not allow_root and path == '/':
        raise ValueError("SSE 路径不能为根路径 '/', 请在环境变量中设置具体子路径")
    return path


mount_path = _normalize_path(ServerConfig.MOUNT_PATH, allow_root=True)
sse_path = _normalize_path(ServerConfig.SSE_PATH)
full_endpoint = f"{mount_path.rstrip('/')}{sse_path}"
if not full_endpoint:
    full_endpoint = '/'

print(f"export HOST='{ServerConfig.HOST}'")
print(f"export PORT='{ServerConfig.PORT}'")
print(f"export MOUNT_PATH='{mount_path}'")
print(f"export SSE_PATH='{sse_path}'")
print(f"export FULL_ENDPOINT='{full_endpoint}'")
PYEOF
)"

echo "HOST: $HOST"
echo "PORT: $PORT"
echo "MOUNT_PATH: $MOUNT_PATH"
echo "SSE_PATH: $SSE_PATH"
echo "完整访问路径: http://$HOST:$PORT$FULL_ENDPOINT"
echo ""

echo "【步骤1】检查当前代码..."
echo "---"
echo "FastMCP 初始化:"
grep -n "FastMCP" src/server.py | head -1
echo ""
echo "mcp.run 调用:"
grep -n "mcp.run" src/server.py | head -1
echo ""

# 检查服务器是否读取配置
if grep -q "ServerConfig.SSE_PATH" src/server.py; then
    echo "✅ 服务器从配置加载 SSE 路径"
else
    echo "❌ 未检测到 ServerConfig.SSE_PATH，请检查 src/server.py 是否读取配置"
    exit 1
fi

if grep -q "mcp.run('sse'" src/server.py; then
    echo "✅ mcp.run 使用 SSE 传输"
else
    echo "❌ mcp.run 参数不正确！"
    echo "   请确保使用: mcp.run('sse')"
    exit 1
fi

echo ""
echo "【步骤2】停止所有旧的服务器进程..."
echo "---"
# 查找并显示相关进程
PIDS=$(pgrep -f "python.*server.py" 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "发现运行中的进程:"
    ps aux | grep "python.*server" | grep -v grep
    echo ""
    echo "正在停止这些进程..."
    pkill -f "python.*server.py" 2>/dev/null
    sleep 1
    echo "✅ 已停止旧进程"
else
    echo "✅ 没有发现运行中的服务器进程"
fi

echo ""
echo "【步骤3】清除 Python 缓存..."
echo "---"
rm -rf src/__pycache__ 2>/dev/null
rm -rf src/*/__pycache__ 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
echo "✅ 缓存已清除"

echo ""
echo "【步骤4】验证 FastMCP 配置..."
echo "---"
python3 << 'PYEOF'
try:
    from mcp.server.fastmcp import FastMCP
    from dotenv import load_dotenv
    load_dotenv()

    from src.config import ServerConfig

    def _normalize_path(path: str, allow_root: bool = False, fallback: str = '/sse') -> str:
        if not path:
            return '/' if allow_root else fallback
        path = path.strip()
        if not path.startswith('/'):
            path = '/' + path
        if len(path) > 1:
            path = path.rstrip('/')
        if not allow_root and path == '/':
            raise ValueError("SSE 路径不能为根路径 '/', 请设置具体子路径")
        return path

    mount_path = _normalize_path(ServerConfig.MOUNT_PATH, allow_root=True)
    sse_path = _normalize_path(ServerConfig.SSE_PATH)

    mcp = FastMCP('Test', host=ServerConfig.HOST, port=ServerConfig.PORT, mount_path=mount_path, sse_path=sse_path)
    full_url = f"http://{ServerConfig.HOST}:{ServerConfig.PORT}{mount_path.rstrip('/')}{sse_path}"
    print(f"mount_path: {mcp.settings.mount_path}")
    print(f"sse_path: {mcp.settings.sse_path}")
    print(f"完整访问地址: {full_url}")
    print("✅ FastMCP 配置验证成功")
except Exception as e:
    print(f"❌ FastMCP 配置验证失败: {e}")
    exit(1)
PYEOF

echo ""
echo "=========================================="
echo "诊断完成！"
echo "=========================================="
echo ""
echo "【下一步操作】"
echo ""
echo "1. 启动服务器："
echo "   python -m src.server"
echo ""
echo "   或使用调试模式："
echo "   python start_server_debug.py"
echo ""
echo "2. 测试访问："
echo "   curl http://$HOST:$PORT$FULL_ENDPOINT"
echo ""
echo "3. 预期结果："
echo "   ✅ $FULL_ENDPOINT 应该可以访问"
echo "   ❌ /sse 应该返回 404"
echo ""
echo "=========================================="


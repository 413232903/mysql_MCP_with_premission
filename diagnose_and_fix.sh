#!/bin/bash
# SSE2 问题诊断和修复脚本

echo "=========================================="
echo "SSE2 路径问题 - 自动诊断和修复"
echo "=========================================="
echo ""

# 切换到项目目录
cd "$(dirname "$0")"

echo "【步骤1】检查当前代码..."
echo "---"
echo "FastMCP 初始化:"
grep -n "FastMCP.*host" src/server.py | head -1
echo ""
echo "mcp.run 调用:"
grep -n "mcp.run" src/server.py | head -1
echo ""

# 检查代码是否正确
if grep -q "sse_path='/sse2'" src/server.py; then
    echo "✅ 代码已正确修改为 sse_path='/sse2'"
else
    echo "❌ 代码未正确修改！"
    echo "   请确保 src/server.py 第 52 行包含: sse_path='/sse2'"
    exit 1
fi

if grep -q "mcp.run('sse')" src/server.py; then
    echo "✅ mcp.run 参数正确"
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
    mcp = FastMCP('Test', host='127.0.0.1', port=3000, sse_path='/sse2')
    print(f"mount_path: {mcp.settings.mount_path}")
    print(f"sse_path: {mcp.settings.sse_path}")
    full_url = f"http://127.0.0.1:3000{mcp.settings.sse_path}"
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
echo "   curl http://127.0.0.1:3000/sse2"
echo ""
echo "3. 预期结果："
echo "   ✅ /sse2 应该可以访问"
echo "   ❌ /sse 应该返回 404"
echo ""
echo "=========================================="


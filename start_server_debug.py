#!/usr/bin/env python3
"""
启动服务器并打印详细的调试信息
"""

import sys
import os

# 确保使用项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 清理缓存
import py_compile
import importlib

print("="*80)
print("MySQL MCP Server - 调试启动")
print("="*80)

# 导入并检查配置
print("\n【步骤1】加载配置...")
from dotenv import load_dotenv
load_dotenv()

from src.config import ServerConfig
print(f"  HOST: {ServerConfig.HOST}")
print(f"  PORT: {ServerConfig.PORT}")

# 导入 FastMCP
print("\n【步骤2】导入 FastMCP...")
from mcp.server.fastmcp import FastMCP
print(f"  FastMCP 版本: {FastMCP.__module__}")

# 创建实例
print("\n【步骤3】创建 FastMCP 实例...")
mcp = FastMCP(
    "MySQL Query Server", 
    "debug_version",
    host=ServerConfig.HOST, 
    port=ServerConfig.PORT, 
    debug=True, 
    sse_path='/sse2'  # 设置为 /sse2
)

print(f"  ✅ FastMCP 实例已创建")
print(f"  Settings.mount_path: {mcp.settings.mount_path}")
print(f"  Settings.sse_path: {mcp.settings.sse_path}")

# 注册一个测试工具
print("\n【步骤4】注册测试工具...")
@mcp.tool()
def test_connection():
    """测试连接工具"""
    return "连接成功！服务器正在运行。"

print(f"  ✅ 已注册测试工具: test_connection")

# 打印访问信息
print("\n" + "="*80)
print("【服务器信息】")
print("="*80)
print(f"服务器地址: http://{ServerConfig.HOST}:{ServerConfig.PORT}")
print(f"SSE 路径配置: {mcp.settings.sse_path}")
print(f"挂载路径配置: {mcp.settings.mount_path}")
print(f"\n预期访问地址:")
print(f"  ✅ http://{ServerConfig.HOST}:{ServerConfig.PORT}{mcp.settings.sse_path}")
print(f"  ❌ http://{ServerConfig.HOST}:{ServerConfig.PORT}/sse (旧路径，不应该工作)")
print("\n" + "="*80)
print("按 Ctrl+C 停止服务器")
print("="*80 + "\n")

# 启动服务器
try:
    print("【步骤5】启动服务器...")
    mcp.run('sse')  # 使用 SSE 传输协议
except KeyboardInterrupt:
    print("\n\n服务器已停止")
except Exception as e:
    print(f"\n❌ 启动失败: {e}")
    import traceback
    traceback.print_exc()


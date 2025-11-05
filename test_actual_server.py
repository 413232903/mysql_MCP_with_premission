#!/usr/bin/env python3
"""测试 FastMCP 服务器的实际路径配置"""

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from src.config import ServerConfig
import logging


def _normalize_path(path: str, *, allow_root: bool = False, fallback: str = '/sse') -> str:
    if not path:
        return '/' if allow_root else fallback
    path = path.strip()
    if not path.startswith('/'):
        path = '/' + path
    if len(path) > 1:
        path = path.rstrip('/')
    if not allow_root and path == '/':
        raise ValueError("SSE 路径不能为根路径 '/'，请设置为 '/sse2' 等子路径")
    return path


load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_server")

DEFAULT_MOUNT_PATH = _normalize_path(ServerConfig.MOUNT_PATH, allow_root=True)
DEFAULT_SSE_PATH = _normalize_path(ServerConfig.SSE_PATH)

FULL_ENDPOINT = f"{DEFAULT_MOUNT_PATH.rstrip('/')}{DEFAULT_SSE_PATH}"

# 测试配置
TEST_CONFIGS = [
    {
        "name": f"配置1: sse_path='{DEFAULT_SSE_PATH}', mount_path='{DEFAULT_MOUNT_PATH}'",
        "init_params": {"mount_path": DEFAULT_MOUNT_PATH, "sse_path": DEFAULT_SSE_PATH},
        "run_params": {}
    },
    {
        "name": "配置2: 手动在 run() 中重复指定 mount_path",
        "init_params": {"mount_path": DEFAULT_MOUNT_PATH, "sse_path": DEFAULT_SSE_PATH},
        "run_params": {"mount_path": DEFAULT_MOUNT_PATH}
    },
]

def test_config(config):
    print(f"\n{'='*80}")
    print(f"测试: {config['name']}")
    print(f"{'='*80}")
    
    # 创建服务器实例
    mcp = FastMCP(
        "Test Server",
        host="127.0.0.1",
        port=3006,
        debug=True,
        **config['init_params']
    )
    
    # 注册一个简单的工具
    @mcp.tool()
    def hello():
        """简单的测试工具"""
        return "Hello World"
    
    # 打印配置信息
    print(f"\n初始化参数: {config['init_params']}")
    full_path = f"{mcp.settings.mount_path.rstrip('/')}{mcp.settings.sse_path}"
    print(f"Settings.mount_path: {mcp.settings.mount_path}")
    print(f"Settings.sse_path: {mcp.settings.sse_path}")
    print(f"预期访问地址: http://127.0.0.1:3006{full_path}")
    
    print(f"\nrun() 参数: {config['run_params']}")
    print(f"\n提示: 服务器启动后，请在浏览器或其他工具中测试访问：")
    print(f"  - http://127.0.0.1:3006{FULL_ENDPOINT}")
    print(f"\n按 Ctrl+C 停止服务器\n")
    
    # 启动服务器
    try:
        mcp.run('sse', **config['run_params'])
    except KeyboardInterrupt:
        print("\n服务器已停止")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        config_num = int(sys.argv[1]) - 1
        if 0 <= config_num < len(TEST_CONFIGS):
            test_config(TEST_CONFIGS[config_num])
        else:
            print(f"错误: 配置编号必须在 1-{len(TEST_CONFIGS)} 之间")
    else:
        print("用法: python test_actual_server.py <配置编号>")
        print("\n可用配置:")
        for i, config in enumerate(TEST_CONFIGS, 1):
            print(f"  {i}. {config['name']}")
        print("\n示例: python test_actual_server.py 1")


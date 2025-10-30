#!/usr/bin/env python3
"""测试 FastMCP 服务器的实际路径配置"""

from mcp.server.fastmcp import FastMCP
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_server")

# 测试配置
TEST_CONFIGS = [
    {
        "name": "配置1: sse_path='/sse2', mount_path 默认",
        "init_params": {"sse_path": "/sse2"},
        "run_params": {}
    },
    {
        "name": "配置2: sse_path='/sse2', run 时指定 mount_path='/'",
        "init_params": {"sse_path": "/sse2"},
        "run_params": {"mount_path": "/"}
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
    print(f"Settings.mount_path: {mcp.settings.mount_path}")
    print(f"Settings.sse_path: {mcp.settings.sse_path}")
    print(f"预期访问地址: http://127.0.0.1:3006{mcp.settings.sse_path}")
    
    print(f"\nrun() 参数: {config['run_params']}")
    print(f"\n提示: 服务器启动后，请在浏览器或其他工具中测试访问：")
    print(f"  - http://127.0.0.1:3006/sse")
    print(f"  - http://127.0.0.1:3006/sse2")
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


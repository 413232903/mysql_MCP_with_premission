"""
运行查询脚本 - 2025年9月超资信额排名前十的客户
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入查询函数
from query_top_customers import query_top_customers

if __name__ == "__main__":
    print("开始执行查询...")
    print()
    results = asyncio.run(query_top_customers())
    
    if results:
        print()
        print("查询完成!")
    else:
        print()
        print("查询失败,请检查:")
        print("1. 数据库连接配置是否正确(.env文件)")
        print("2. 数据库服务是否正在运行")
        print("3. 员工工号 01201811074 是否有相应的数据权限")


"""
查询2025年9月超资信额排名前十的客户名称
员工工号：01201811074
"""
import os
import sys
import asyncio
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.db.mysql_operations import get_db_connection, execute_query

async def query_top_customers():
    """查询2025年9月超资信额排名前十的客户名称"""
    
    # 员工工号
    user_id = "01201811074"
    
    # 构建查询语句：获取2025年9月超资信额排名前十的客户名称
    query = """
    SELECT customer_name, over_credit_amount, sales_region
    FROM cw_ai_customer_receivables_analysis 
    WHERE year = 2025 
      AND month = 9 
      AND over_credit_amount IS NOT NULL 
      AND over_credit_amount > 0 
    ORDER BY over_credit_amount DESC 
    LIMIT 10
    """
    
    print("=" * 80)
    print("查询2025年9月超资信额排名前十的客户名称")
    print(f"员工工号：{user_id}")
    print("=" * 80)
    print()
    print("执行查询...")
    print(f"SQL: {query.strip()}")
    print()
    
    try:
        async with get_db_connection() as connection:
            # 执行查询，传入user_id用于权限控制
            results = await execute_query(connection, query, user_id=user_id)
            
            if not results:
                print("⚠️  未找到符合条件的客户数据")
                return
            
            print(f"✅ 查询成功！共找到 {len(results)} 条记录")
            print()
            print("=" * 80)
            print("排名 | 客户名称 | 超资信额 | 销售区域")
            print("=" * 80)
            
            for idx, row in enumerate(results, 1):
                customer_name = row.get('customer_name', '未知')
                over_credit_amount = row.get('over_credit_amount', 0)
                sales_region = row.get('sales_region', '未知')
                
                # 格式化超资信额（如果是数字）
                if isinstance(over_credit_amount, (int, float)):
                    amount_str = f"{over_credit_amount:,.2f}"
                else:
                    amount_str = str(over_credit_amount)
                
                print(f"{idx:4d} | {customer_name:20s} | {amount_str:>15s} | {sales_region}")
            
            print("=" * 80)
            print()
            print("【客户名称列表】")
            print("-" * 80)
            for idx, row in enumerate(results, 1):
                customer_name = row.get('customer_name', '未知')
                print(f"{idx}. {customer_name}")
            
    except Exception as e:
        print(f"❌ 查询失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(query_top_customers())



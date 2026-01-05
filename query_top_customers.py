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
            # 执行查询，传入 user_id 以应用权限控制
            results = await execute_query(connection, query, user_id=user_id)
            
            print(f"查询成功！共返回 {len(results)} 条记录")
            print()
            print("=" * 80)
            print("排名前十的客户名称：")
            print("=" * 80)
            print()
            
            # 显示结果
            for i, row in enumerate(results, 1):
                customer_name = row.get('customer_name', '')
                over_credit_amount = row.get('over_credit_amount', 0)
                sales_region = row.get('sales_region', '')
                
                # 格式化金额
                if over_credit_amount:
                    amount_str = f"{float(over_credit_amount):,.2f}"
                else:
                    amount_str = "0.00"
                
                print(f"{i:2d}. {customer_name}")
                print(f"    超资信额：{amount_str} 元")
                if sales_region:
                    print(f"    销区：{sales_region}")
                print()
            
            # 只返回客户名称列表
            print("=" * 80)
            print("客户名称列表：")
            print("=" * 80)
            customer_names = [row.get('customer_name', '') for row in results]
            for i, name in enumerate(customer_names, 1):
                print(f"{i:2d}. {name}")
            
            return results
            
    except Exception as e:
        print(f"查询失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    results = asyncio.run(query_top_customers())


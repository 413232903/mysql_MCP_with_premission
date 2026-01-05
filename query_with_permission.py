"""
权限控制查询示例
演示如何正确调用MCP工具并传递user_id参数以应用权限控制
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

# 导入数据库操作函数
from src.db.mysql_operations import get_db_connection, execute_query
from src.config import RolePermissionConfig

async def query_without_permission():
    """查询无权限控制时的结果（全部数据）"""
    print("=" * 80)
    print("查询1: 无权限控制（全部数据）")
    print("=" * 80)
    
    query = """
    SELECT customer_name, gssq AS 销区, gssq AS 省区, over_credit_amount
    FROM cw_ai_customer_receivables_analysis 
    WHERE year = 2025 
      AND month = 9 
      AND over_credit_amount IS NOT NULL 
      AND over_credit_amount > 0 
    ORDER BY over_credit_amount DESC 
    LIMIT 10
    """
    
    print(f"SQL: {query.strip()}")
    print()
    
    try:
        async with get_db_connection() as connection:
            # 不传递 user_id，不应用权限控制
            results = await execute_query(connection, query, user_id=None)
            
            print(f"✅ 查询成功！共返回 {len(results)} 条记录")
            print()
            print("结果：")
            print("-" * 80)
            for i, row in enumerate(results, 1):
                customer_name = row.get('customer_name', '')
                sales_region = row.get('销区', '')
                province = row.get('省区', '')
                amount = row.get('over_credit_amount', 0)
                print(f"{i:2d}. {customer_name}")
                print(f"    省区/销区: {province}")
                print(f"    超资信额: {float(amount):,.2f} 元")
                print()
            
            return results
    except Exception as e:
        print(f"❌ 查询失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return None

async def query_with_permission(user_id: str):
    """查询有权限控制时的结果（仅权限范围内的数据）"""
    print("=" * 80)
    print(f"查询2: 有权限控制（用户: {user_id}）")
    print("=" * 80)
    
    query = """
    SELECT customer_name, gssq AS 销区, gssq AS 省区, over_credit_amount
    FROM cw_ai_customer_receivables_analysis 
    WHERE year = 2025 
      AND month = 9 
      AND over_credit_amount IS NOT NULL 
      AND over_credit_amount > 0 
    ORDER BY over_credit_amount DESC 
    LIMIT 10
    """
    
    print(f"SQL: {query.strip()}")
    print(f"用户ID: {user_id}")
    print()
    
    # 检查权限控制配置
    if not RolePermissionConfig.ENABLE_ROLE_PERMISSION:
        print("⚠️  警告：权限控制未启用！")
        print("   请在 .env 文件中设置 ENABLE_ROLE_PERMISSION=true")
        print()
    
    if not RolePermissionConfig.PERMISSION_TABLES:
        print("⚠️  警告：未配置权限表！")
        print("   请在 .env 文件中设置 PERMISSION_TABLES=cw_ai_customer_receivables_analysis")
        print()
    
    try:
        async with get_db_connection() as connection:
            # 传递 user_id，应用权限控制
            results = await execute_query(connection, query, user_id=user_id)
            
            print(f"✅ 查询成功！共返回 {len(results)} 条记录")
            print()
            
            if results:
                print("结果（仅显示权限范围内的数据）：")
                print("-" * 80)
                for i, row in enumerate(results, 1):
                    customer_name = row.get('customer_name', '')
                    sales_region = row.get('销区', '')
                    province = row.get('省区', '')
                    amount = row.get('over_credit_amount', 0)
                    print(f"{i:2d}. {customer_name}")
                    print(f"    省区/销区: {province}")
                    print(f"    超资信额: {float(amount):,.2f} 元")
                    print()
            else:
                print("⚠️  未返回任何结果")
                print("   可能原因：")
                print("   1. 该用户没有权限访问任何数据")
                print("   2. 权限配置不正确")
                print("   3. 数据中不存在符合权限条件的记录")
            
            return results
    except Exception as e:
        print(f"❌ 查询失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return None

async def compare_results():
    """对比权限控制前后的查询结果"""
    print("\n" + "=" * 80)
    print("对比分析")
    print("=" * 80)
    
    user_id = "01201811074"
    
    # 查询无权限控制的结果
    results_without = await query_without_permission()
    print()
    
    # 查询有权限控制的结果
    results_with = await query_with_permission(user_id)
    print()
    
    # 对比分析
    if results_without and results_with:
        print("=" * 80)
        print("结果对比")
        print("=" * 80)
        print(f"无权限控制: {len(results_without)} 条记录")
        print(f"有权限控制: {len(results_with)} 条记录")
        print()
        
        # 统计省区分布
        regions_without = {}
        regions_with = {}
        
        for row in results_without:
            region = row.get('销区', '未知')
            regions_without[region] = regions_without.get(region, 0) + 1
        
        for row in results_with:
            region = row.get('销区', '未知')
            regions_with[region] = regions_with.get(region, 0) + 1
        
        print("省区分布对比：")
        print("-" * 80)
        print("无权限控制:")
        for region, count in sorted(regions_without.items()):
            print(f"  {region}: {count} 条")
        print()
        print("有权限控制（用户权限范围）:")
        for region, count in sorted(regions_with.items()):
            print(f"  {region}: {count} 条")
        print()
        
        # 检查权限控制是否生效
        if len(results_with) < len(results_without):
            print("✅ 权限控制已生效！查询结果已被过滤")
        elif len(results_with) == len(results_without):
            print("⚠️  权限控制可能未生效，结果数量相同")
            print("   请检查：")
            print("   1. 权限控制是否已启用")
            print("   2. 权限表是否已配置")
            print("   3. 用户权限数据是否正确")
        else:
            print("❌ 异常：有权限控制的结果数量大于无权限控制的结果")
    
    print()
    print("=" * 80)

async def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("权限控制查询示例")
    print("=" * 80)
    print()
    print("本示例演示如何正确调用MCP工具并传递user_id参数以应用权限控制")
    print()
    
    # 显示配置状态
    print("当前配置状态：")
    print(f"  权限控制启用: {RolePermissionConfig.ENABLE_ROLE_PERMISSION}")
    print(f"  权限表: {list(RolePermissionConfig.PERMISSION_TABLES)}")
    print(f"  权限字段: {RolePermissionConfig.PERMISSION_FIELD}")
    print()
    
    # 运行对比查询
    await compare_results()
    
    print("\n" + "=" * 80)
    print("使用说明")
    print("=" * 80)
    print()
    print("在代码中调用MCP工具时，请确保传递user_id参数：")
    print()
    print("  # 方式1: 直接调用数据库操作函数")
    print("  results = await execute_query(connection, query, user_id='01201811074')")
    print()
    print("  # 方式2: 通过MCP工具调用（如果支持）")
    print("  results = await mysql_query(query='SELECT ...', user_id='01201811074')")
    print()
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())


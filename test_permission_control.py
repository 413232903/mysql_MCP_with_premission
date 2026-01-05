"""
权限控制快速测试脚本
用于验证权限控制是否正常工作
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.db.mysql_operations import get_db_connection, execute_query
from src.config import RolePermissionConfig
from src.security.role_permission import get_role_permission_manager

async def test_permission_control():
    """测试权限控制功能"""
    print("=" * 80)
    print("权限控制功能测试")
    print("=" * 80)
    print()
    
    # 1. 检查配置
    print("1. 检查配置状态")
    print("-" * 80)
    print(f"   权限控制启用: {RolePermissionConfig.ENABLE_ROLE_PERMISSION}")
    print(f"   权限表: {list(RolePermissionConfig.PERMISSION_TABLES)}")
    print(f"   权限字段: {RolePermissionConfig.PERMISSION_FIELD}")
    print()
    
    if not RolePermissionConfig.ENABLE_ROLE_PERMISSION:
        print("❌ 权限控制未启用！")
        print("   请运行: python setup_permission.py")
        return False
    
    if not RolePermissionConfig.PERMISSION_TABLES:
        print("❌ 未配置权限表！")
        print("   请运行: python setup_permission.py")
        return False
    
    print("✅ 配置检查通过")
    print()
    
    # 2. 测试SQL解析
    print("2. 测试SQL解析和权限判断")
    print("-" * 80)
    test_sql = """
    SELECT customer_name, gssq, over_credit_amount
    FROM cw_ai_customer_receivables_analysis 
    WHERE year = 2025 AND month = 9 
    AND over_credit_amount > 0 
    ORDER BY over_credit_amount DESC 
    LIMIT 10
    """
    
    manager = get_role_permission_manager()
    user_id = "01201811074"
    
    print(f"   测试SQL: {test_sql.strip()[:80]}...")
    print(f"   用户ID: {user_id}")
    
    should_apply = manager.should_apply_permission(test_sql, user_id)
    print(f"   应该应用权限: {should_apply}")
    
    if should_apply:
        filtered_sql = manager.inject_permission_filter(test_sql, user_id)
        print(f"   ✅ SQL已注入权限过滤条件")
        print(f"   修改后SQL长度: {len(filtered_sql)} 字符")
    else:
        print(f"   ⚠️  SQL未应用权限过滤")
    
    print()
    
    # 3. 测试无权限控制的查询
    print("3. 测试无权限控制的查询（全部数据）")
    print("-" * 80)
    try:
        async with get_db_connection() as connection:
            results_without = await execute_query(
                connection, 
                test_sql.strip(), 
                user_id=None
            )
            print(f"   ✅ 查询成功，返回 {len(results_without)} 条记录")
            
            if results_without:
                # 统计省区分布
                regions = {}
                for row in results_without:
                    region = row.get('gssq', '未知')
                    regions[region] = regions.get(region, 0) + 1
                
                print(f"   省区分布:")
                for region, count in sorted(regions.items()):
                    print(f"     {region}: {count} 条")
    except Exception as e:
        print(f"   ❌ 查询失败: {e}")
        return False
    
    print()
    
    # 4. 测试有权限控制的查询
    print("4. 测试有权限控制的查询（仅权限范围内的数据）")
    print("-" * 80)
    try:
        async with get_db_connection() as connection:
            results_with = await execute_query(
                connection, 
                test_sql.strip(), 
                user_id=user_id
            )
            print(f"   ✅ 查询成功，返回 {len(results_with)} 条记录")
            
            if results_with:
                # 统计省区分布
                regions = {}
                for row in results_with:
                    region = row.get('gssq', '未知')
                    regions[region] = regions.get(region, 0) + 1
                
                print(f"   省区分布（权限范围内）:")
                for region, count in sorted(regions.items()):
                    print(f"     {region}: {count} 条")
            else:
                print(f"   ⚠️  未返回任何结果")
    except Exception as e:
        print(f"   ❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    
    # 5. 结果对比
    print("5. 结果对比分析")
    print("-" * 80)
    if 'results_without' in locals() and 'results_with' in locals():
        count_without = len(results_without)
        count_with = len(results_with)
        
        print(f"   无权限控制: {count_without} 条记录")
        print(f"   有权限控制: {count_with} 条记录")
        print()
        
        if count_with < count_without:
            print("   ✅ 权限控制已生效！查询结果已被正确过滤")
            print(f"   过滤掉了 {count_without - count_with} 条记录")
            return True
        elif count_with == count_without:
            print("   ⚠️  权限控制可能未生效，结果数量相同")
            print("   可能原因：")
            print("   1. 所有数据都在权限范围内")
            print("   2. 权限配置不正确")
            print("   3. 权限过滤条件未正确注入")
            return False
        else:
            print("   ❌ 异常：有权限控制的结果数量大于无权限控制的结果")
            return False
    else:
        print("   ⚠️  无法进行对比分析")
        return False

async def main():
    """主函数"""
    try:
        success = await test_permission_control()
        print()
        print("=" * 80)
        if success:
            print("✅ 测试通过！权限控制功能正常工作")
        else:
            print("❌ 测试未通过，请检查配置和日志")
        print("=" * 80)
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())


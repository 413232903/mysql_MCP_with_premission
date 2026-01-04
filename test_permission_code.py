"""
测试行级权限控制代码
"""
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入配置
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.config import RolePermissionConfig
from src.security.role_permission import get_role_permission_manager

def test_permission_code():
    """测试权限控制代码"""
    print("=" * 80)
    print("行级权限控制代码排查测试")
    print("=" * 80)
    print()
    
    user_id = "01201811074"
    test_sql = """
    SELECT customer_name, sales_region, over_credit_amount 
    FROM cw_ai_customer_receivables_analysis 
    WHERE year = 2025 AND month = 9 
    AND over_credit_amount > 0 
    ORDER BY over_credit_amount DESC 
    LIMIT 10
    """
    
    # 1. 检查配置
    print("1. 检查权限配置")
    print(f"   ENABLE_ROLE_PERMISSION: {RolePermissionConfig.ENABLE_ROLE_PERMISSION}")
    print(f"   PERMISSION_TABLES: {list(RolePermissionConfig.PERMISSION_TABLES)}")
    print(f"   PERMISSION_FIELD: {RolePermissionConfig.PERMISSION_FIELD}")
    print(f"   USER_ROLE_TABLE: {RolePermissionConfig.USER_ROLE_TABLE}")
    print(f"   USER_ROLE_EXTEND_FIELD: {RolePermissionConfig.USER_ROLE_EXTEND_FIELD}")
    print(f"   USER_ROLE_PREFIX: {RolePermissionConfig.USER_ROLE_PREFIX}")
    print()
    
    # 2. 测试权限管理器
    manager = get_role_permission_manager()
    print("2. 测试权限管理器")
    print(f"   权限管理器启用: {manager.enabled}")
    print(f"   权限表列表: {list(manager.permission_tables)}")
    print(f"   权限字段: {manager.permission_field}")
    print()
    
    # 3. 测试是否需要应用权限
    print("3. 测试是否需要应用权限")
    should_apply = manager.should_apply_permission(test_sql, user_id)
    print(f"   是否需要应用权限: {should_apply}")
    print()
    
    if should_apply:
        # 4. 测试权限条件构建
        print("4. 测试权限条件构建")
        condition = manager._build_permission_condition(user_id)
        print(f"   构建的权限条件:")
        print(f"   {condition}")
        print()
        
        # 5. 测试 SQL 注入
        print("5. 测试 SQL 注入")
        filtered_sql = manager.inject_permission_filter(test_sql, user_id)
        print(f"   原始 SQL:")
        print(f"   {test_sql.strip()}")
        print()
        print(f"   过滤后 SQL:")
        print(f"   {filtered_sql}")
        print()
        
        # 6. 分析问题
        print("6. 问题分析")
        print("   ⚠️  发现的问题：")
        print("   1. 权限字段是 'gssq'，但表中没有这个字段（应该是 'sales_region'）")
        print("   2. 权限值格式不匹配：")
        print("      - 权限值：'Y两湖销区'、'Y湖北销区'、'Y湖南销区'")
        print("      - 表字段值：'湖北'、'湖南'、'湖南省'")
        print("   3. 权限值转换逻辑不完整：")
        print("      - 当前只去掉 'RX' 前缀")
        print("      - 需要处理 'Y两湖销区' -> '两湖' 或 '湖北,湖南'")
        print("      - 需要处理 'Y湖北销区' -> '湖北'")
    else:
        print("   ⚠️  权限未应用，原因：")
        if not manager.enabled:
            print("      - 权限控制未启用")
        if not manager.permission_tables:
            print("      - 权限表未配置")
        if user_id in manager.super_admins:
            print("      - 用户是超级管理员")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    test_permission_code()


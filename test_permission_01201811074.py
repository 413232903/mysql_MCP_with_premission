"""
测试员工工号 01201811074 的行级权限控制
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

def test_permission():
    """测试权限控制"""
    print("=" * 80)
    print("测试员工工号 01201811074 的行级权限控制")
    print("=" * 80)
    print()
    
    user_id = "01201811074"
    
    # 1. 检查配置
    print("1. 检查权限配置")
    print(f"   权限控制启用: {RolePermissionConfig.ENABLE_ROLE_PERMISSION}")
    print(f"   权限表列表: {list(RolePermissionConfig.PERMISSION_TABLES)}")
    print(f"   权限字段: {RolePermissionConfig.PERMISSION_FIELD}")
    print(f"   用户角色表: {RolePermissionConfig.USER_ROLE_TABLE}")
    print(f"   权限前缀: {RolePermissionConfig.USER_ROLE_PREFIX}")
    print()
    
    # 2. 测试 SQL 查询
    test_sql = """
    SELECT customer_name, sales_region, over_credit_amount, year, month 
    FROM cw_ai_customer_receivables_analysis 
    WHERE year = 2025 AND month = 9 
    AND over_credit_amount IS NOT NULL 
    AND over_credit_amount > 0 
    ORDER BY over_credit_amount DESC 
    LIMIT 10
    """
    
    print("2. 测试 SQL 查询")
    print(f"   原始 SQL: {test_sql.strip()}")
    print()
    
    # 3. 检查是否需要应用权限
    if RolePermissionConfig.ENABLE_ROLE_PERMISSION:
        manager = get_role_permission_manager()
        should_apply = manager.should_apply_permission(test_sql, user_id)
        print(f"   是否需要应用权限: {should_apply}")
        
        if should_apply:
            filtered_sql = manager.inject_permission_filter(test_sql, user_id)
            print(f"   过滤后 SQL:")
            print(f"   {filtered_sql}")
        else:
            print("   ⚠️  权限未应用，原因可能是：")
            print("      - 查询的表不在权限表列表中")
            print("      - 用户是超级管理员")
            print("      - SQL 不是 SELECT 查询")
    else:
        print("   ⚠️  权限控制未启用")
    
    print()
    
    # 4. 检查权限值
    print("3. 检查用户权限值")
    print(f"   用户ID: {user_id}")
    print(f"   权限字段: {RolePermissionConfig.PERMISSION_FIELD}")
    print(f"   权限前缀: {RolePermissionConfig.USER_ROLE_PREFIX}")
    print()
    print("   建议：")
    print("   1. 如果表中没有 gssq 字段，需要将权限字段改为 sales_region")
    print("   2. 确保 PERMISSION_TABLES 包含 cw_ai_customer_receivables_analysis")
    print("   3. 权限值格式应该是：去掉 RX 前缀后的值，例如 '两湖销区'、'湖北销区'、'湖南销区'")
    print()
    
    print("=" * 80)

if __name__ == "__main__":
    test_permission()


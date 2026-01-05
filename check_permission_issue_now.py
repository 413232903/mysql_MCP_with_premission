"""
权限问题排查脚本
用于快速诊断权限控制未生效的原因
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

def check_permission_issue():
    """检查权限问题"""
    print("=" * 80)
    print("权限控制问题排查")
    print("=" * 80)
    print()
    
    # 测试查询
    test_sql = "SELECT customer_name, gssq AS province_region, over_credit_amount, year, month FROM cw_ai_customer_receivables_analysis WHERE year = 2025 AND month = 9 AND over_credit_amount IS NOT NULL AND over_credit_amount > 0 ORDER BY over_credit_amount DESC LIMIT 10"
    test_user_id = "01201811074"
    
    print(f"测试 SQL: {test_sql}")
    print(f"测试 user_id: {test_user_id}")
    print()
    
    # 1. 检查权限控制是否启用
    print("1. 检查权限控制是否启用")
    print(f"   ENABLE_ROLE_PERMISSION = {RolePermissionConfig.ENABLE_ROLE_PERMISSION}")
    if not RolePermissionConfig.ENABLE_ROLE_PERMISSION:
        print("   ❌ 权限控制未启用！")
        print("   💡 解决方案：在 .env 文件中设置 ENABLE_ROLE_PERMISSION=true")
        print()
        return
    else:
        print("   ✅ 权限控制已启用")
    print()
    
    # 2. 检查权限表配置
    print("2. 检查权限表配置")
    print(f"   PERMISSION_TABLES = {list(RolePermissionConfig.PERMISSION_TABLES)}")
    if not RolePermissionConfig.PERMISSION_TABLES:
        print("   ❌ 未配置权限表！")
        print("   💡 解决方案：在 .env 文件中设置 PERMISSION_TABLES=cw_ai_customer_receivables_analysis")
        print()
        return
    else:
        print(f"   ✅ 已配置 {len(RolePermissionConfig.PERMISSION_TABLES)} 个权限表")
    print()
    
    # 3. 检查查询的表是否在权限表中
    print("3. 检查查询的表是否在权限表中")
    query_table = "cw_ai_customer_receivables_analysis"
    normalized_query_table = query_table.lower()
    normalized_permission_tables = {table.lower() for table in RolePermissionConfig.PERMISSION_TABLES}
    
    print(f"   查询的表: {query_table}")
    print(f"   配置的权限表: {list(normalized_permission_tables)}")
    
    if normalized_query_table not in normalized_permission_tables:
        print(f"   ❌ 查询的表 '{query_table}' 不在权限表配置中！")
        print(f"   💡 解决方案：在 .env 文件中添加该表到 PERMISSION_TABLES")
        print(f"   例如：PERMISSION_TABLES={','.join(RolePermissionConfig.PERMISSION_TABLES)},{query_table}")
        print()
        return
    else:
        print(f"   ✅ 查询的表在权限表配置中")
    print()
    
    # 4. 检查超级管理员配置
    print("4. 检查超级管理员配置")
    print(f"   SUPER_ADMIN_USERS = {list(RolePermissionConfig.SUPER_ADMIN_USERS)}")
    if test_user_id in RolePermissionConfig.SUPER_ADMIN_USERS:
        print(f"   ⚠️  用户 '{test_user_id}' 是超级管理员，将跳过权限检查！")
        print(f"   💡 解决方案：如果该用户不应该跳过权限检查，请从 SUPER_ADMIN_USERS 中移除")
        print()
        return
    else:
        print(f"   ✅ 用户不在超级管理员列表中")
    print()
    
    # 5. 测试权限管理器
    print("5. 测试权限管理器")
    try:
        manager = get_role_permission_manager()
        print(f"   ✅ 权限管理器初始化成功")
        print(f"   启用状态: {manager.enabled}")
        print(f"   权限表列表: {list(manager.permission_tables)}")
        print(f"   权限字段: {manager.permission_field}")
        print()
        
        # 测试 should_apply_permission
        print("6. 测试权限应用判断")
        should_apply = manager.should_apply_permission(test_sql, test_user_id)
        print(f"   should_apply_permission 返回: {should_apply}")
        
        if should_apply:
            print("   ✅ 权限应该被应用")
            # 测试注入权限过滤
            filtered_sql = manager.inject_permission_filter(test_sql, test_user_id)
            print(f"   原始 SQL: {test_sql[:150]}...")
            print(f"   过滤后 SQL: {filtered_sql[:200]}...")
            if filtered_sql != test_sql:
                print("   ✅ SQL 已被权限过滤修改")
            else:
                print("   ⚠️  SQL 未被修改（可能存在问题）")
        else:
            print("   ❌ 权限不应该被应用（请查看上面的日志了解原因）")
    except Exception as e:
        print(f"   ❌ 权限管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # 7. 总结
    print("=" * 80)
    print("排查总结")
    print("=" * 80)
    print()
    print("如果权限仍然未生效，请检查：")
    print("1. 服务器日志中是否有权限相关的 INFO 级别日志")
    print("2. 确认 .env 文件中的配置已正确加载（重启服务器）")
    print("3. 确认查询时传入了 user_id 参数")
    print("4. 查看服务器日志中的详细权限检查信息")
    print()

if __name__ == "__main__":
    check_permission_issue()


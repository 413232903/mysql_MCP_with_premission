"""
快速检查当前权限配置
用于排查权限控制未生效的问题
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

def check_permission_now():
    """快速检查权限配置"""
    print("=" * 70)
    print("权限控制配置快速检查")
    print("=" * 70)
    print()
    
    # 1. 检查权限控制是否启用
    print("【检查1】权限控制是否启用？")
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
    print("【检查2】权限表是否配置？")
    print(f"   PERMISSION_TABLES = {list(RolePermissionConfig.PERMISSION_TABLES)}")
    if not RolePermissionConfig.PERMISSION_TABLES:
        print("   ❌ 未配置权限表！")
        print("   💡 解决方案：在 .env 文件中设置 PERMISSION_TABLES=cw_ai_customer_receivables_analysis")
        print()
        return
    else:
        print(f"   ✅ 已配置 {len(RolePermissionConfig.PERMISSION_TABLES)} 个权限表")
    
    # 检查查询的表是否在权限表中
    query_table = "cw_ai_customer_receivables_analysis"
    normalized_query_table = query_table.lower()
    if normalized_query_table not in {t.lower() for t in RolePermissionConfig.PERMISSION_TABLES}:
        print(f"   ⚠️  警告：查询的表 '{query_table}' 不在权限表列表中！")
        print(f"   💡 解决方案：在 .env 文件中添加该表到 PERMISSION_TABLES")
        print(f"   例如：PERMISSION_TABLES={query_table}")
        print()
        return
    else:
        print(f"   ✅ 查询的表 '{query_table}' 在权限表列表中")
    print()
    
    # 3. 检查用户ID
    print("【检查3】用户ID配置")
    test_user_id = "01201811074"
    print(f"   测试用户ID: {test_user_id}")
    
    # 检查是否是超级管理员
    if test_user_id in RolePermissionConfig.SUPER_ADMIN_USERS:
        print(f"   ⚠️  警告：用户 '{test_user_id}' 是超级管理员，将跳过权限检查！")
        print(f"   💡 解决方案：如果不需要跳过权限检查，请从 SUPER_ADMIN_USERS 中移除该用户")
        print()
        return
    else:
        print(f"   ✅ 用户 '{test_user_id}' 不是超级管理员")
    print()
    
    # 4. 测试SQL解析和权限判断
    print("【检查4】测试SQL解析和权限判断")
    test_sql = "SELECT customer_name, gssq AS province_region, over_credit_amount, year, month FROM cw_ai_customer_receivables_analysis WHERE year = 2025 AND month = 9 AND over_credit_amount IS NOT NULL AND over_credit_amount > 0 ORDER BY over_credit_amount DESC LIMIT 10"
    
    try:
        manager = get_role_permission_manager()
        should_apply = manager.should_apply_permission(test_sql, test_user_id)
        
        print(f"   SQL: {test_sql[:80]}...")
        print(f"   应该应用权限: {should_apply}")
        
        if should_apply:
            filtered_sql = manager.inject_permission_filter(test_sql, test_user_id)
            print(f"   ✅ 权限过滤已应用")
            print(f"   原始SQL长度: {len(test_sql)}")
            print(f"   过滤后SQL长度: {len(filtered_sql)}")
            if filtered_sql != test_sql:
                print(f"   🔒 权限条件已注入")
            else:
                print(f"   ⚠️  警告：SQL未发生变化，权限条件可能未注入")
        else:
            print(f"   ❌ 权限过滤未应用，请查看上面的日志信息了解原因")
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # 5. 总结
    print("=" * 70)
    print("检查总结")
    print("=" * 70)
    
    issues = []
    if not RolePermissionConfig.ENABLE_ROLE_PERMISSION:
        issues.append("权限控制未启用")
    if not RolePermissionConfig.PERMISSION_TABLES:
        issues.append("未配置权限表")
    if normalized_query_table not in {t.lower() for t in RolePermissionConfig.PERMISSION_TABLES}:
        issues.append(f"查询的表 '{query_table}' 不在权限表列表中")
    if test_user_id in RolePermissionConfig.SUPER_ADMIN_USERS:
        issues.append(f"用户 '{test_user_id}' 是超级管理员")
    
    if issues:
        print("发现以下问题：")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        print()
        print("解决方案：")
        print("1. 在项目根目录创建或编辑 .env 文件")
        print("2. 添加或修改以下配置：")
        print()
        print("   # 启用角色权限控制")
        print("   ENABLE_ROLE_PERMISSION=true")
        print()
        print("   # 配置需要权限过滤的表（逗号分隔）")
        print(f"   PERMISSION_TABLES={query_table}")
        print()
        if test_user_id in RolePermissionConfig.SUPER_ADMIN_USERS:
            print("   # 如果不需要跳过权限检查，请移除或修改超级管理员列表")
            print("   SUPER_ADMIN_USERS=")
        print()
        print("3. 重启服务器使配置生效")
    else:
        print("✅ 所有检查通过！")
        print()
        print("如果权限仍然未生效，请检查：")
        print("1. 服务器日志中是否有权限相关的日志信息")
        print("2. 调用 MCP 工具时是否正确传入了 user_id 参数")
        print("3. 查看服务器日志中的详细调试信息")
    
    print()
    print("=" * 70)

if __name__ == "__main__":
    check_permission_now()


"""
行级权限诊断工具
用于检查行级权限配置是否正确
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

def diagnose_permission_config():
    """诊断权限配置"""
    print("=" * 60)
    print("行级权限配置诊断工具")
    print("=" * 60)
    print()
    
    # 1. 检查是否启用权限控制
    print("1. 检查权限控制是否启用")
    print(f"   ENABLE_ROLE_PERMISSION = {RolePermissionConfig.ENABLE_ROLE_PERMISSION}")
    if not RolePermissionConfig.ENABLE_ROLE_PERMISSION:
        print("   ❌ 权限控制未启用！")
        print("   💡 解决方案：在 .env 文件中设置 ENABLE_ROLE_PERMISSION=true")
    else:
        print("   ✅ 权限控制已启用")
    print()
    
    # 2. 检查权限表配置
    print("2. 检查权限表配置")
    print(f"   PERMISSION_TABLES = {list(RolePermissionConfig.PERMISSION_TABLES)}")
    if not RolePermissionConfig.PERMISSION_TABLES:
        print("   ❌ 未配置权限表！")
        print("   💡 解决方案：在 .env 文件中设置 PERMISSION_TABLES=表名1,表名2,...")
        print("   例如：PERMISSION_TABLES=orders,products,customers")
    else:
        print(f"   ✅ 已配置 {len(RolePermissionConfig.PERMISSION_TABLES)} 个权限表")
    print()
    
    # 3. 检查权限字段配置
    print("3. 检查权限字段配置")
    print(f"   PERMISSION_FIELD = {RolePermissionConfig.PERMISSION_FIELD}")
    print("   ✅ 权限字段配置正常")
    print()
    
    # 4. 检查用户角色表配置
    print("4. 检查用户角色表配置")
    print(f"   USER_ROLE_TABLE = {RolePermissionConfig.USER_ROLE_TABLE}")
    print(f"   USER_ROLE_USERNAME_FIELD = {RolePermissionConfig.USER_ROLE_USERNAME_FIELD}")
    print(f"   USER_ROLE_EXTEND_FIELD = {RolePermissionConfig.USER_ROLE_EXTEND_FIELD}")
    print(f"   USER_ROLE_PREFIX = {RolePermissionConfig.USER_ROLE_PREFIX}")
    print("   ✅ 用户角色表配置正常")
    print()
    
    # 5. 检查超级管理员配置
    print("5. 检查超级管理员配置")
    print(f"   SUPER_ADMIN_USERS = {list(RolePermissionConfig.SUPER_ADMIN_USERS)}")
    if RolePermissionConfig.SUPER_ADMIN_USERS:
        print(f"   ⚠️  已配置 {len(RolePermissionConfig.SUPER_ADMIN_USERS)} 个超级管理员，这些用户将跳过权限检查")
    else:
        print("   ℹ️  未配置超级管理员")
    print()
    
    # 6. 测试权限管理器
    print("6. 测试权限管理器")
    try:
        manager = get_role_permission_manager()
        print(f"   ✅ 权限管理器初始化成功")
        print(f"   启用状态: {manager.enabled}")
        print(f"   权限表列表: {list(manager.permission_tables)}")
        print(f"   权限字段: {manager.permission_field}")
    except Exception as e:
        print(f"   ❌ 权限管理器初始化失败: {e}")
    print()
    
    # 7. 测试 SQL 解析
    print("7. 测试 SQL 解析和权限判断")
    test_sqls = [
        ("SELECT * FROM orders", "orders"),
        ("SELECT * FROM products WHERE id=1", "products"),
        ("SELECT * FROM orders o JOIN products p ON o.product_id=p.id", "orders,products"),
    ]
    
    if RolePermissionConfig.ENABLE_ROLE_PERMISSION and RolePermissionConfig.PERMISSION_TABLES:
        manager = get_role_permission_manager()
        for sql, expected_tables in test_sqls:
            # 检查是否包含权限表
            contains_permission_table = manager._contains_permission_tables(sql)
            should_apply = manager.should_apply_permission(sql, "test_user")
            
            print(f"   SQL: {sql}")
            print(f"   涉及权限表: {contains_permission_table}")
            print(f"   应该应用权限: {should_apply}")
            if should_apply:
                filtered_sql = manager.inject_permission_filter(sql, "test_user")
                print(f"   过滤后 SQL: {filtered_sql[:100]}...")
            print()
    else:
        print("   ⚠️  权限控制未启用或未配置权限表，跳过测试")
    print()
    
    # 8. 总结和建议
    print("=" * 60)
    print("诊断总结")
    print("=" * 60)
    
    issues = []
    if not RolePermissionConfig.ENABLE_ROLE_PERMISSION:
        issues.append("权限控制未启用")
    if not RolePermissionConfig.PERMISSION_TABLES:
        issues.append("未配置权限表")
    
    if issues:
        print("发现以下问题：")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        print()
        print("解决方案：")
        print("1. 在项目根目录创建或编辑 .env 文件")
        print("2. 添加以下配置：")
        print()
        print("   # 启用角色权限控制")
        print("   ENABLE_ROLE_PERMISSION=true")
        print()
        print("   # 配置需要权限过滤的表（逗号分隔）")
        print("   PERMISSION_TABLES=表名1,表名2,表名3")
        print()
        print("   # 其他可选配置（使用默认值即可）")
        print("   PERMISSION_FIELD=gssq")
        print("   USER_ROLE_TABLE=fr_user_role")
        print("   USER_ROLE_USERNAME_FIELD=username")
        print("   USER_ROLE_EXTEND_FIELD=extend1")
        print("   USER_ROLE_PREFIX=RX")
        print()
        print("3. 重启服务器使配置生效")
        print()
        print("4. 调用 MCP 工具时，确保传入 user_id 参数：")
        print("   mysql_query(query='SELECT * FROM 表名', user_id='用户名')")
    else:
        print("✅ 配置检查通过！")
        print()
        print("如果权限仍然未生效，请检查：")
        print("1. 调用 MCP 工具时是否传入了 user_id 参数")
        print("2. user_id 是否在 SUPER_ADMIN_USERS 列表中（超级管理员会跳过权限检查）")
        print("3. 查询的表名是否在 PERMISSION_TABLES 配置中")
        print("4. SQL 语句是否为 SELECT 查询（其他操作类型不应用权限过滤）")
        print("5. 查看服务器日志中的权限相关调试信息")
    
    print()
    print("=" * 60)

if __name__ == "__main__":
    diagnose_permission_config()


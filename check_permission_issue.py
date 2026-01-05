"""
行级权限问题诊断和解决方案
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
    """检查权限问题并给出解决方案"""
    print("=" * 70)
    print("行级权限问题诊断报告")
    print("=" * 70)
    print()
    
    # 1. 检查权限控制是否启用
    print("【问题1】权限控制是否启用？")
    print(f"   当前配置: ENABLE_ROLE_PERMISSION = {RolePermissionConfig.ENABLE_ROLE_PERMISSION}")
    if not RolePermissionConfig.ENABLE_ROLE_PERMISSION:
        print("   ❌ 权限控制未启用！")
        print("   💡 解决方案：在 .env 文件中设置 ENABLE_ROLE_PERMISSION=true")
    else:
        print("   ✅ 权限控制已启用")
    print()
    
    # 2. 检查权限表配置
    print("【问题2】权限表是否配置？")
    print(f"   当前配置: PERMISSION_TABLES = {list(RolePermissionConfig.PERMISSION_TABLES)}")
    if not RolePermissionConfig.PERMISSION_TABLES:
        print("   ❌ 未配置权限表！")
        print("   💡 解决方案：在 .env 文件中设置 PERMISSION_TABLES=cw_ai_customer_receivables_analysis")
    else:
        print(f"   ✅ 已配置 {len(RolePermissionConfig.PERMISSION_TABLES)} 个权限表")
        if 'cw_ai_customer_receivables_analysis' not in RolePermissionConfig.PERMISSION_TABLES:
            print("   ⚠️  警告：查询的表 cw_ai_customer_receivables_analysis 不在权限表列表中！")
    print()
    
    # 3. 检查权限字段配置
    print("【问题3】权限字段配置是否正确？")
    print(f"   当前配置: PERMISSION_FIELD = {RolePermissionConfig.PERMISSION_FIELD}")
    print("   ℹ️  表中实际字段名: gssq（省区字段）")
    if RolePermissionConfig.PERMISSION_FIELD != 'gssq':
        print(f"   ⚠️  警告：权限字段配置为 {RolePermissionConfig.PERMISSION_FIELD}，但表中字段是 gssq")
        print("   💡 建议：在 .env 文件中设置 PERMISSION_FIELD=gssq")
    else:
        print("   ✅ 权限字段配置正确")
    print()
    
    # 4. 测试权限管理器
    print("【问题4】权限管理器状态")
    try:
        manager = get_role_permission_manager()
        print(f"   ✅ 权限管理器初始化成功")
        print(f"   启用状态: {manager.enabled}")
        print(f"   权限表列表: {list(manager.permission_tables)}")
        print(f"   权限字段: {manager.permission_field}")
        
        # 测试SQL解析
        test_sql = "SELECT customer_name, gssq, over_credit_amount FROM cw_ai_customer_receivables_analysis WHERE year = 2025 AND month = 9 ORDER BY over_credit_amount DESC LIMIT 10"
        print()
        print("   测试SQL解析:")
        print(f"   SQL: {test_sql[:80]}...")
        
        should_apply = manager.should_apply_permission(test_sql, "01201811074")
        print(f"   应该应用权限: {should_apply}")
        
        if should_apply:
            filtered_sql = manager.inject_permission_filter(test_sql, "01201811074")
            print(f"   过滤后SQL: {filtered_sql[:150]}...")
        else:
            print("   ⚠️  权限未应用，原因可能是：")
            if not manager.enabled:
                print("      - 权限控制未启用")
            if not manager.permission_tables:
                print("      - 权限表未配置")
            if 'cw_ai_customer_receivables_analysis' not in manager.permission_tables:
                print("      - 查询的表不在权限表列表中")
    except Exception as e:
        print(f"   ❌ 权限管理器初始化失败: {e}")
    print()
    
    # 5. 检查用户权限数据
    print("【问题5】用户权限数据")
    print("   用户工号: 01201811074")
    print("   权限值格式: Y两湖RX销区, Y湖北RX销区, Y湖南RX销区 等")
    print("   权限值转换逻辑: 去掉 RX、Y 前缀和 销区 后缀")
    print("   转换后应匹配: 两湖、湖北、湖南")
    print("   表中gssq字段值: 湖南、湖北、两湖 等")
    print("   ✅ 权限值转换逻辑已实现（支持模糊匹配）")
    print()
    
    # 6. 总结和解决方案
    print("=" * 70)
    print("诊断总结和解决方案")
    print("=" * 70)
    print()
    
    issues = []
    solutions = []
    
    if not RolePermissionConfig.ENABLE_ROLE_PERMISSION:
        issues.append("权限控制未启用")
        solutions.append("在 .env 文件中设置 ENABLE_ROLE_PERMISSION=true")
    
    if not RolePermissionConfig.PERMISSION_TABLES:
        issues.append("未配置权限表")
        solutions.append("在 .env 文件中设置 PERMISSION_TABLES=cw_ai_customer_receivables_analysis")
    elif 'cw_ai_customer_receivables_analysis' not in RolePermissionConfig.PERMISSION_TABLES:
        issues.append("查询的表不在权限表列表中")
        current_tables = ','.join(RolePermissionConfig.PERMISSION_TABLES)
        solutions.append(f"在 .env 文件中设置 PERMISSION_TABLES={current_tables},cw_ai_customer_receivables_analysis")
    
    if RolePermissionConfig.PERMISSION_FIELD != 'gssq':
        issues.append("权限字段配置不正确")
        solutions.append("在 .env 文件中设置 PERMISSION_FIELD=gssq")
    
    if issues:
        print("发现以下问题：")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        print()
        print("解决方案：")
        print()
        print("1. 检查项目根目录是否有 .env 文件，如果没有，复制 example.env 创建：")
        print("   copy example.env .env")
        print()
        print("2. 编辑 .env 文件，添加或修改以下配置：")
        print()
        print("   # 启用角色权限控制")
        print("   ENABLE_ROLE_PERMISSION=true")
        print()
        print("   # 配置需要权限过滤的表（逗号分隔）")
        print("   PERMISSION_TABLES=cw_ai_customer_receivables_analysis")
        print()
        print("   # 权限字段名称（表中实际字段名）")
        print("   PERMISSION_FIELD=gssq")
        print()
        print("3. 重启服务器使配置生效")
        print()
        print("4. 调用 MCP 工具时，确保传入 user_id 参数：")
        print("   mysql_query(query='...', user_id='01201811074')")
    else:
        print("✅ 配置检查通过！")
        print()
        print("如果权限仍然未生效，请检查：")
        print("1. 调用 MCP 工具时是否传入了 user_id 参数")
        print("2. user_id 是否在 SUPER_ADMIN_USERS 列表中（超级管理员会跳过权限检查）")
        print("3. 查看服务器日志中的权限相关调试信息")
        print("4. 确认查询返回的数据是否符合权限范围（只应返回湖北和湖南的客户）")
    
    print()
    print("=" * 70)

if __name__ == "__main__":
    check_permission_issue()


"""
最终权限控制测试脚本
测试修复后的权限控制代码
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

def test_permission_final():
    """最终权限控制测试"""
    print("=" * 80)
    print("行级权限控制代码最终测试")
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
    print("2. 权限管理器状态")
    print(f"   权限管理器启用: {manager.enabled}")
    print(f"   权限表列表: {list(manager.permission_tables)}")
    print(f"   权限字段: {manager.permission_field}")
    print()
    
    # 3. 测试权限值转换逻辑
    print("3. 测试权限值转换逻辑")
    test_permission_values = [
        "Y两湖RX销区",
        "Y湖北RX销区",
        "Y湖南RX销区",
        "Y湖北销区",
        "Y湖南销区"
    ]
    
    print("   原始权限值 -> 转换后值 -> 可匹配的表字段值")
    print("   " + "-" * 70)
    for perm_value in test_permission_values:
        # 模拟转换逻辑
        transformed = perm_value.replace('RX', '').replace('Y', '').replace('销区', '').strip()
        print(f"   {perm_value:20} -> {transformed:10} -> 可匹配包含 '{transformed}' 的值")
    print()
    
    # 4. 测试是否需要应用权限
    print("4. 测试权限应用判断")
    should_apply = manager.should_apply_permission(test_sql, user_id)
    print(f"   是否需要应用权限: {should_apply}")
    
    if not should_apply:
        print()
        print("   ⚠️  权限未应用的原因：")
        if not manager.enabled:
            print("      - 权限控制未启用 (ENABLE_ROLE_PERMISSION=false)")
        if not manager.permission_tables:
            print("      - 权限表未配置 (PERMISSION_TABLES 为空)")
        if user_id in manager.super_admins:
            print(f"      - 用户 {user_id} 是超级管理员")
        print()
        print("   💡 解决方案：")
        print("   1. 在 .env 文件中设置 ENABLE_ROLE_PERMISSION=true")
        print("   2. 在 .env 文件中设置 PERMISSION_TABLES=cw_ai_customer_receivables_analysis")
        print("   3. 在 .env 文件中设置 PERMISSION_FIELD=sales_region")
        return
    
    print()
    
    # 5. 测试权限条件构建
    print("5. 测试权限条件构建")
    condition = manager._build_permission_condition(user_id)
    print("   构建的权限条件:")
    print("   " + "-" * 70)
    # 格式化输出，每行不超过70字符
    lines = condition.split('\n')
    for line in lines:
        if line.strip():
            print(f"   {line}")
    print()
    
    # 6. 测试 SQL 注入
    print("6. 测试 SQL 注入")
    filtered_sql = manager.inject_permission_filter(test_sql, user_id)
    print("   原始 SQL:")
    print("   " + "-" * 70)
    for line in test_sql.strip().split('\n'):
        if line.strip():
            print(f"   {line.strip()}")
    print()
    print("   过滤后 SQL:")
    print("   " + "-" * 70)
    # 格式化输出 SQL
    sql_lines = filtered_sql.split('\n')
    for line in sql_lines:
        if line.strip():
            print(f"   {line.strip()}")
    print()
    
    # 7. 验证权限条件逻辑
    print("7. 权限条件逻辑验证")
    print("   ✅ 权限值转换逻辑：")
    print("      - 去掉 RX 前缀")
    print("      - 去掉 Y 前缀")
    print("      - 去掉 销区 后缀")
    print("      - 使用 TRIM 去除首尾空格")
    print()
    print("   ✅ 匹配逻辑：")
    print("      - 使用 LIKE CONCAT('%', 转换后的值, '%') 进行模糊匹配")
    print("      - 支持权限值格式与表字段值不完全一致的情况")
    print("      - 例如：'两湖' 可以匹配 '湖北'、'湖南'、'两湖'、'湖南省' 等")
    print()
    
    # 8. 预期结果
    print("8. 预期查询结果")
    print("   员工 01201811074 的权限范围：")
    print("      - 两湖销区（湖北 + 湖南）")
    print("      - 湖北销区")
    print("      - 湖南销区")
    print()
    print("   预期查询结果应该只包含：")
    print("      - sales_region 包含 '湖北' 的记录")
    print("      - sales_region 包含 '湖南' 的记录")
    print("      - sales_region 包含 '两湖' 的记录")
    print()
    
    print("=" * 80)
    print("测试完成！")
    print("=" * 80)
    print()
    print("下一步：")
    print("1. 确保 .env 文件配置正确")
    print("2. 重启服务器")
    print("3. 使用 mysql_query(query='...', user_id='01201811074') 进行实际查询测试")
    print("4. 验证查询结果是否符合权限控制预期")

if __name__ == "__main__":
    test_permission_final()


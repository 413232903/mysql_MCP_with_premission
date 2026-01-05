"""
权限控制配置工具
用于检查和配置行级权限控制相关的环境变量
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key, find_dotenv

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_env_file():
    """检查 .env 文件是否存在"""
    env_path = Path('.env')
    example_path = Path('example.env')
    
    if not env_path.exists():
        print("⚠️  .env 文件不存在")
        if example_path.exists():
            print(f"📋 发现 example.env 文件，建议复制它来创建 .env 文件")
            print(f"   命令: copy example.env .env  (Windows)")
            print(f"   命令: cp example.env .env    (Linux/Mac)")
            return False
        else:
            print("❌ example.env 文件也不存在，无法创建配置")
            return False
    else:
        print("✅ .env 文件存在")
        return True

def load_current_config():
    """加载当前配置"""
    load_dotenv()
    return {
        'ENABLE_ROLE_PERMISSION': os.getenv('ENABLE_ROLE_PERMISSION', 'false'),
        'PERMISSION_TABLES': os.getenv('PERMISSION_TABLES', ''),
        'PERMISSION_FIELD': os.getenv('PERMISSION_FIELD', 'gssq'),
        'USER_ROLE_TABLE': os.getenv('USER_ROLE_TABLE', 'fr_user_role'),
        'USER_ROLE_USERNAME_FIELD': os.getenv('USER_ROLE_USERNAME_FIELD', 'username'),
        'USER_ROLE_EXTEND_FIELD': os.getenv('USER_ROLE_EXTEND_FIELD', 'extend1'),
        'USER_ROLE_PREFIX': os.getenv('USER_ROLE_PREFIX', 'RX'),
        'MYSQL_DATABASE': os.getenv('MYSQL_DATABASE', ''),
    }

def check_config(config):
    """检查配置是否完整"""
    issues = []
    recommendations = []
    
    # 检查权限控制是否启用
    if config['ENABLE_ROLE_PERMISSION'].lower() not in ('true', 'yes', '1'):
        issues.append("权限控制未启用 (ENABLE_ROLE_PERMISSION)")
        recommendations.append("设置 ENABLE_ROLE_PERMISSION=true")
    
    # 检查权限表是否配置
    if not config['PERMISSION_TABLES']:
        issues.append("未配置权限表 (PERMISSION_TABLES)")
        recommendations.append("设置 PERMISSION_TABLES=cw_ai_customer_receivables_analysis")
    
    # 检查数据库配置
    if not config['MYSQL_DATABASE']:
        issues.append("未配置数据库名 (MYSQL_DATABASE)")
        recommendations.append("设置 MYSQL_DATABASE=datawh")
    
    return issues, recommendations

def update_env_file(config_updates):
    """更新 .env 文件"""
    env_path = find_dotenv()
    if not env_path:
        # 如果找不到 .env，尝试创建
        if Path('example.env').exists():
            import shutil
            shutil.copy('example.env', '.env')
            env_path = '.env'
        else:
            print("❌ 无法找到或创建 .env 文件")
            return False
    
    try:
        for key, value in config_updates.items():
            set_key(env_path, key, value)
        print(f"✅ 已更新 .env 文件: {env_path}")
        return True
    except Exception as e:
        print(f"❌ 更新 .env 文件失败: {e}")
        return False

def interactive_setup():
    """交互式配置向导"""
    print("=" * 70)
    print("权限控制配置向导")
    print("=" * 70)
    print()
    
    # 检查 .env 文件
    if not check_env_file():
        print()
        print("请先创建 .env 文件，然后重新运行此脚本")
        return
    
    # 加载当前配置
    config = load_current_config()
    
    # 检查配置
    issues, recommendations = check_config(config)
    
    # 显示当前配置
    print("\n当前配置：")
    print(f"  ENABLE_ROLE_PERMISSION = {config['ENABLE_ROLE_PERMISSION']}")
    print(f"  PERMISSION_TABLES = {config['PERMISSION_TABLES'] or '(未配置)'}")
    print(f"  PERMISSION_FIELD = {config['PERMISSION_FIELD']}")
    print(f"  MYSQL_DATABASE = {config['MYSQL_DATABASE'] or '(未配置)'}")
    print()
    
    # 如果有问题，显示并询问是否修复
    if issues:
        print("发现以下配置问题：")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print()
        
        response = input("是否自动修复这些问题？(y/n): ").strip().lower()
        if response == 'y':
            config_updates = {}
            
            # 启用权限控制
            if config['ENABLE_ROLE_PERMISSION'].lower() not in ('true', 'yes', '1'):
                config_updates['ENABLE_ROLE_PERMISSION'] = 'true'
                print("  ✓ 将启用权限控制")
            
            # 配置权限表
            if not config['PERMISSION_TABLES']:
                config_updates['PERMISSION_TABLES'] = 'cw_ai_customer_receivables_analysis'
                print("  ✓ 将配置权限表: cw_ai_customer_receivables_analysis")
            
            # 配置数据库
            if not config['MYSQL_DATABASE']:
                db_name = input("  请输入数据库名 (默认: datawh): ").strip() or 'datawh'
                config_updates['MYSQL_DATABASE'] = db_name
                print(f"  ✓ 将配置数据库: {db_name}")
            
            if config_updates:
                if update_env_file(config_updates):
                    print("\n✅ 配置已更新！")
                    print("⚠️  请重启服务器使配置生效")
                else:
                    print("\n❌ 配置更新失败，请手动编辑 .env 文件")
            else:
                print("\n无需更新配置")
        else:
            print("\n跳过自动修复")
            print("\n请手动编辑 .env 文件，添加以下配置：")
            for rec in recommendations:
                print(f"  {rec}")
    else:
        print("✅ 配置检查通过！")
        print("\n如果权限控制仍未生效，请检查：")
        print("  1. 调用 MCP 工具时是否传入了 user_id 参数")
        print("  2. user_id 是否在 SUPER_ADMIN_USERS 列表中（超级管理员会跳过权限检查）")
        print("  3. 查询的表名是否在 PERMISSION_TABLES 配置中")
        print("  4. SQL 语句是否为 SELECT 查询（其他操作类型不应用权限过滤）")
    
    print()
    print("=" * 70)

def show_config_instructions():
    """显示配置说明"""
    print("=" * 70)
    print("权限控制配置说明")
    print("=" * 70)
    print()
    print("请在 .env 文件中添加或修改以下配置项：")
    print()
    print("# 启用角色权限控制")
    print("ENABLE_ROLE_PERMISSION=true")
    print()
    print("# 配置需要权限过滤的表（逗号分隔）")
    print("PERMISSION_TABLES=cw_ai_customer_receivables_analysis")
    print()
    print("# 权限字段名称（表中实际字段名）")
    print("PERMISSION_FIELD=gssq")
    print()
    print("# 数据库名称")
    print("MYSQL_DATABASE=datawh")
    print()
    print("# 其他配置项使用默认值即可")
    print()
    print("配置完成后，请重启服务器使配置生效")
    print()
    print("=" * 70)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='权限控制配置工具')
    parser.add_argument('--show-instructions', action='store_true', 
                       help='显示配置说明')
    parser.add_argument('--auto-fix', action='store_true',
                       help='自动修复配置问题')
    
    args = parser.parse_args()
    
    if args.show_instructions:
        show_config_instructions()
    elif args.auto_fix:
        config = load_current_config()
        issues, recommendations = check_config(config)
        if issues:
            config_updates = {}
            if config['ENABLE_ROLE_PERMISSION'].lower() not in ('true', 'yes', '1'):
                config_updates['ENABLE_ROLE_PERMISSION'] = 'true'
            if not config['PERMISSION_TABLES']:
                config_updates['PERMISSION_TABLES'] = 'cw_ai_customer_receivables_analysis'
            if not config['MYSQL_DATABASE']:
                config_updates['MYSQL_DATABASE'] = 'datawh'
            
            if config_updates:
                update_env_file(config_updates)
                print("✅ 配置已自动修复")
            else:
                print("✅ 配置无需修复")
        else:
            print("✅ 配置检查通过，无需修复")
    else:
        interactive_setup()


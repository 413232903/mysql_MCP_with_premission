"""
修复配置文件语法错误
用于修复 src/config.py 中 os.getenv() 调用错误
"""
import re
import sys
from pathlib import Path

def fix_config_file():
    """修复配置文件中的语法错误"""
    config_file = Path('src/config.py')
    
    if not config_file.exists():
        print(f"❌ 文件不存在: {config_file}")
        return False
    
    # 读取文件内容
    content = config_file.read_text(encoding='utf-8')
    original_content = content
    
    # 查找并修复错误的 os.getenv() 调用
    # 错误模式: os.getenv('KEY', 'value1', 'value2')
    # 正确模式: os.getenv('KEY', 'value1,value2')
    
    # 修复 PERMISSION_TABLES_STR
    pattern1 = r"PERMISSION_TABLES_STR\s*=\s*os\.getenv\s*\(\s*['\"]PERMISSION_TABLES['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)"
    replacement1 = r"PERMISSION_TABLES_STR = os.getenv('PERMISSION_TABLES', '\1,\2')"
    content = re.sub(pattern1, replacement1, content)
    
    # 修复 SUPER_ADMIN_USERS_STR（如果也有类似问题）
    pattern2 = r"SUPER_ADMIN_USERS_STR\s*=\s*os\.getenv\s*\(\s*['\"]SUPER_ADMIN_USERS['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)"
    replacement2 = r"SUPER_ADMIN_USERS_STR = os.getenv('SUPER_ADMIN_USERS', '\1,\2')"
    content = re.sub(pattern2, replacement2, content)
    
    # 检查是否有修改
    if content != original_content:
        # 备份原文件
        backup_file = config_file.with_suffix('.py.bak')
        config_file.rename(backup_file)
        print(f"✅ 已备份原文件到: {backup_file}")
        
        # 写入修复后的内容
        config_file.write_text(content, encoding='utf-8')
        print(f"✅ 已修复文件: {config_file}")
        return True
    else:
        print("✅ 文件语法正确，无需修复")
        return True

def check_config_syntax():
    """检查配置文件语法"""
    config_file = Path('src/config.py')
    
    if not config_file.exists():
        print(f"❌ 文件不存在: {config_file}")
        return False
    
    content = config_file.read_text(encoding='utf-8')
    
    # 检查是否有错误的 os.getenv() 调用
    errors = []
    
    # 检查 PERMISSION_TABLES_STR
    if re.search(r"PERMISSION_TABLES_STR.*os\.getenv.*,.*,", content):
        errors.append("PERMISSION_TABLES_STR 的 os.getenv() 调用可能有语法错误")
    
    # 检查 SUPER_ADMIN_USERS_STR
    if re.search(r"SUPER_ADMIN_USERS_STR.*os\.getenv.*,.*,", content):
        errors.append("SUPER_ADMIN_USERS_STR 的 os.getenv() 调用可能有语法错误")
    
    if errors:
        print("⚠️  发现可能的语法错误：")
        for error in errors:
            print(f"   - {error}")
        return False
    else:
        print("✅ 配置文件语法检查通过")
        return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='修复配置文件语法错误')
    parser.add_argument('--check', action='store_true', help='仅检查，不修复')
    parser.add_argument('--fix', action='store_true', help='修复错误')
    
    args = parser.parse_args()
    
    if args.check:
        check_config_syntax()
    elif args.fix:
        if check_config_syntax():
            print("无需修复")
        else:
            print("\n开始修复...")
            fix_config_file()
    else:
        # 默认先检查，然后询问是否修复
        if not check_config_syntax():
            print("\n是否自动修复？(y/n): ", end='')
            response = input().strip().lower()
            if response == 'y':
                fix_config_file()
            else:
                print("跳过修复")


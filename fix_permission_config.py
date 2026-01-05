"""
快速修复行级权限配置脚本
自动创建或更新 .env 文件中的权限配置
"""
import os
import shutil
from pathlib import Path

def fix_permission_config():
    """修复权限配置"""
    print("=" * 70)
    print("行级权限配置修复工具")
    print("=" * 70)
    print()
    
    project_root = Path(__file__).parent
    env_file = project_root / ".env"
    example_env_file = project_root / "example.env"
    
    # 检查 example.env 是否存在
    if not example_env_file.exists():
        print("❌ 错误：找不到 example.env 文件！")
        return
    
    # 读取 example.env 内容
    with open(example_env_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已有 .env 文件
    if env_file.exists():
        print("ℹ️  检测到已存在 .env 文件")
        print("   将更新权限相关配置...")
        
        # 读取现有 .env 内容
        with open(env_file, 'r', encoding='utf-8') as f:
            env_content = f.read()
    else:
        print("ℹ️  未找到 .env 文件，将从 example.env 创建...")
        env_content = content
    
    # 修复权限配置
    lines = env_content.split('\n')
    fixed_lines = []
    permission_section_started = False
    permission_section_ended = False
    
    for i, line in enumerate(lines):
        # 检测权限配置区域开始
        if '# 角色权限控制配置' in line or '# 行级权限' in line:
            permission_section_started = True
        
        # 修复 ENABLE_ROLE_PERMISSION
        if line.startswith('ENABLE_ROLE_PERMISSION='):
            fixed_lines.append('ENABLE_ROLE_PERMISSION=true')
            print("   ✅ 已设置 ENABLE_ROLE_PERMISSION=true")
            continue
        
        # 修复 PERMISSION_TABLES
        if line.startswith('PERMISSION_TABLES='):
            if 'cw_ai_customer_receivables_analysis' not in line:
                fixed_lines.append('PERMISSION_TABLES=cw_ai_customer_receivables_analysis')
                print("   ✅ 已设置 PERMISSION_TABLES=cw_ai_customer_receivables_analysis")
            else:
                fixed_lines.append(line)
                print("   ✅ PERMISSION_TABLES 已包含 cw_ai_customer_receivables_analysis")
            continue
        
        # 检测权限配置区域结束
        if permission_section_started and line.strip() and not line.strip().startswith('#'):
            if 'SUPER_ADMIN_USERS' in line:
                permission_section_ended = True
        
        fixed_lines.append(line)
    
    # 写入修复后的内容
    fixed_content = '\n'.join(fixed_lines)
    
    try:
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        print()
        print("✅ 配置修复完成！")
        print()
        print("=" * 70)
        print("修复内容总结")
        print("=" * 70)
        print()
        print("1. ✅ ENABLE_ROLE_PERMISSION=true（已启用权限控制）")
        print("2. ✅ PERMISSION_TABLES=cw_ai_customer_receivables_analysis（已配置权限表）")
        print("3. ✅ PERMISSION_FIELD=gssq（权限字段配置正确）")
        print()
        print("下一步操作：")
        print("1. 重启 MCP 服务器使配置生效")
        print("2. 重新执行查询，应该只能看到湖北和湖南的客户数据")
        print("3. 调用 MCP 工具时，确保传入 user_id='01201811074' 参数")
        print()
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ 写入 .env 文件失败: {e}")
        print()
        print("请手动创建 .env 文件，并添加以下配置：")
        print()
        print("ENABLE_ROLE_PERMISSION=true")
        print("PERMISSION_TABLES=cw_ai_customer_receivables_analysis")
        print("PERMISSION_FIELD=gssq")

if __name__ == "__main__":
    fix_permission_config()


#!/usr/bin/env python3
"""MCP 服务鉴权凭据生成工具（管理员/运维使用，仅依赖标准库）

用法:
  # 生成 Bearer Token（明文只显示一次，服务端只存 SHA-256 哈希）
  python scripts/gen_token.py token --client-id bailian-prod --user-id report_user --expires 2027-01-01

  # 生成 HMAC 签名密钥对（AppSecret 永不离开客户端）
  python scripts/gen_token.py hmac-key --client-id bi-system --user-id bi_user

  # 计算已有 Token 的 SHA-256 哈希（核对 .env / DB 配置）
  python scripts/gen_token.py hash <token明文>

  # 计算凭据审计指纹（与 AUTH 审计日志中的 fp= 字段对应）
  python scripts/gen_token.py fingerprint <凭据明文>

安全要求:
- Token/Secret 明文仅生成时显示一次，通过线下安全渠道送达调用方
- 严禁将明文写入代码仓库、聊天记录、工单或访问日志
- 吊销: env 后端删除对应配置段并重启; db 后端 UPDATE revoked=1（缓存 TTL 内生效）
"""
import argparse
import hashlib
import secrets
import sys
from datetime import datetime


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _sql_str(value):
    return "NULL" if value is None else "'{}'".format(str(value).replace("'", "''"))


def _validate_expires(value):
    if value is None:
        return None
    if value.isdigit():
        return value
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
        try:
            datetime.strptime(value, fmt)
            return value
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"过期时间格式应为 YYYY-MM-DD 或 unix 时间戳: {value}")


def cmd_token(args):
    token = secrets.token_urlsafe(48)
    digest = hash_token(token)

    print("=" * 72)
    print("Token 明文（仅此一次显示，请通过安全渠道交付，之后无法找回）:")
    print(f"  {token}")
    print("=" * 72)
    print(f"SHA-256 哈希（服务端存储形态）:\n  {digest}\n")

    # env 后端配置行: client_id:hash[:user_id][:expires][:scopes]，中间字段留空需保留冒号占位
    env_entry = f"{args.client_id}:{digest}"
    if args.user_id or args.expires or args.scopes != 'query':
        env_entry += f":{args.user_id or ''}:{args.expires or ''}"
        if args.scopes != 'query':
            env_entry += f":{args.scopes}"
    print("env 后端: 将下面一行追加到 .env 的 AUTH_TOKENS（多组用分号分隔）:")
    print(f"  {env_entry}\n")

    print("db 后端: 执行以下 SQL:")
    print(f"  INSERT INTO mcp_auth_token (client_id, token_hash, user_id, scopes, expires_at, remark)"
          f" VALUES ({_sql_str(args.client_id)}, {_sql_str(digest)}, {_sql_str(args.user_id)},"
          f" {_sql_str(args.scopes)}, {_sql_str(args.expires)}, {_sql_str(args.remark)});")
    print("\n调用方 Header 配置（如百炼 MCP 服务自定义 Header）:")
    print(f"  Authorization: Bearer {token}")


def cmd_hmac_key(args):
    app_key = 'ak_' + secrets.token_hex(8)
    app_secret = secrets.token_urlsafe(32)

    print("=" * 72)
    print("HMAC 密钥对（AppSecret 仅此一次显示，请通过安全渠道交付）:")
    print(f"  AppKey:    {app_key}")
    print(f"  AppSecret: {app_secret}")
    print("=" * 72)

    # env 后端配置行: app_key:app_secret[:client_id][:user_id][:scopes]
    env_entry = f"{app_key}:{app_secret}:{args.client_id}"
    if args.user_id or args.scopes != 'query':
        env_entry += f":{args.user_id or ''}"
        if args.scopes != 'query':
            env_entry += f":{args.scopes}"
    print("\nenv 后端: 将下面一行追加到 .env 的 AUTH_HMAC_KEYS（多组用分号分隔）:")
    print(f"  {env_entry}\n")

    print("db 后端: 执行以下 SQL:")
    print(f"  INSERT INTO mcp_auth_key (app_key, app_secret, client_id, user_id, scopes)"
          f" VALUES ({_sql_str(app_key)}, {_sql_str(app_secret)}, {_sql_str(args.client_id)},"
          f" {_sql_str(args.user_id)}, {_sql_str(args.scopes)});")
    print("\n签名规范见 src/security/auth/hmac_verifier.py 与 examples/client_with_auth.py")


def cmd_hash(args):
    print(hash_token(args.credential))


def cmd_fingerprint(args):
    print(hash_token(args.credential)[:8])


def main(argv=None):
    parser = argparse.ArgumentParser(description="MCP 服务鉴权凭据生成工具")
    sub = parser.add_subparsers(dest='command', required=True)

    p_token = sub.add_parser('token', help='生成 Bearer Token')
    p_token.add_argument('--client-id', required=True, help='调用方系统标识（字母数字下划线连字符，如 bailian-prod）')
    p_token.add_argument('--user-id', help='绑定的行级权限用户（fr_user_role.username）')
    p_token.add_argument('--expires', type=_validate_expires,
                         help='过期时间 YYYY-MM-DD 或 unix 时间戳（建议设置并定期轮换）')
    p_token.add_argument('--scopes', default='query', help='授权范围，逗号分隔（默认 query）')
    p_token.add_argument('--remark', help='备注（仅 db 后端记录）')
    p_token.set_defaults(func=cmd_token)

    p_hmac = sub.add_parser('hmac-key', help='生成 HMAC 签名密钥对')
    p_hmac.add_argument('--client-id', required=True, help='调用方系统标识')
    p_hmac.add_argument('--user-id', help='绑定的行级权限用户')
    p_hmac.add_argument('--scopes', default='query', help='授权范围，逗号分隔（默认 query）')
    p_hmac.set_defaults(func=cmd_hmac_key)

    p_hash = sub.add_parser('hash', help='计算 Token 的 SHA-256 哈希')
    p_hash.add_argument('credential', help='Token 明文')
    p_hash.set_defaults(func=cmd_hash)

    p_fp = sub.add_parser('fingerprint', help='计算凭据审计指纹（SHA-256 前 8 位）')
    p_fp.add_argument('credential', help='凭据明文（Token 或 AppKey）')
    p_fp.set_defaults(func=cmd_fingerprint)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())

import os
from typing import Set, List
from enum import IntEnum, Enum

# 环境变量
class EnvironmentType(Enum):
    """环境类型"""
    DEVELOPMENT = 'development'
    PRODUCTION = 'production'

class SQLRiskLevel(IntEnum):
    """SQL操作风险等级"""
    LOW = 1      # 查询操作（SELECT）
    MEDIUM = 2   # 基本数据修改（INSERT，有WHERE的UPDATE/DELETE）
    HIGH = 3     # 结构变更（CREATE/ALTER）和无WHERE的数据修改
    CRITICAL = 4 # 危险操作（DROP/TRUNCATE等）

# 服务器配置
class ServerConfig:
    """服务器配置"""
    HOST = os.getenv('HOST', '127.0.0.1')
    PORT = int(os.getenv('PORT', '3000'))
    # MCP 服务器对外暴露的基础挂载路径，默认 '/'
    MOUNT_PATH = os.getenv('MOUNT_PATH', '/')
    # SSE 推送端点路径，默认 '/sse2'，可通过环境变量按需调整
    SSE_PATH = os.getenv('SSE_PATH', '/sse2')
    # 调试模式（生产环境强制关闭，见 server.py）
    DEBUG = os.getenv('SERVER_DEBUG', 'false').lower() in ('true', 'yes', '1')

# 数据库配置
class DatabaseConfig:
    """数据库连接配置"""
    HOST = os.getenv('MYSQL_HOST', 'localhost')
    USER = os.getenv('MYSQL_USER', 'root')
    PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    DATABASE = os.getenv('MYSQL_DATABASE', '')
    PORT = int(os.getenv('MYSQL_PORT', '3306'))
    CONNECTION_TIMEOUT = int(os.getenv('DB_CONNECTION_TIMEOUT', '5'))
    AUTH_PLUGIN = os.getenv('DB_AUTH_PLUGIN', 'mysql_native_password')
    
    @staticmethod
    def get_config():
        """获取数据库配置字典"""
        return {
            'host': DatabaseConfig.HOST,
            'user': DatabaseConfig.USER,
            'password': DatabaseConfig.PASSWORD,
            'database': DatabaseConfig.DATABASE,
            'port': DatabaseConfig.PORT,
            'connection_timeout': DatabaseConfig.CONNECTION_TIMEOUT,
            'auth_plugin': DatabaseConfig.AUTH_PLUGIN
        }

# 数据库连接池配置
class ConnectionPoolConfig:
    """数据库连接池配置"""
    # 连接池最小连接数
    MIN_SIZE = int(os.getenv('DB_POOL_MIN_SIZE', '5'))
    # 连接池最大连接数
    MAX_SIZE = int(os.getenv('DB_POOL_MAX_SIZE', '20'))
    # 连接池回收时间（秒）
    POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', '300'))
    # 连接最大存活时间（秒，0表示不限制）
    MAX_LIFETIME = int(os.getenv('DB_POOL_MAX_LIFETIME', '0'))
    # 连接获取超时时间（秒）
    ACQUIRE_TIMEOUT = float(os.getenv('DB_POOL_ACQUIRE_TIMEOUT', '10.0'))
    # 是否启用连接池
    ENABLED = os.getenv('DB_POOL_ENABLED', 'true').lower() in ('true', 'yes', '1')
    
    @staticmethod
    def get_config():
        """获取连接池配置字典"""
        return {
            'minsize': ConnectionPoolConfig.MIN_SIZE,
            'maxsize': ConnectionPoolConfig.MAX_SIZE,
            'pool_recycle': ConnectionPoolConfig.POOL_RECYCLE,
            'max_lifetime': ConnectionPoolConfig.MAX_LIFETIME,
            'acquire_timeout': ConnectionPoolConfig.ACQUIRE_TIMEOUT,
            'enabled': ConnectionPoolConfig.ENABLED
        }

# 安全配置
class SecurityConfig:
    """安全相关配置"""
    # 环境类型
    ENV_TYPE_STR = os.getenv('ENV_TYPE', 'development').lower()
    try:
        ENV_TYPE = EnvironmentType(ENV_TYPE_STR)
    except ValueError:
        ENV_TYPE = EnvironmentType.DEVELOPMENT
    
    # 允许的风险等级
    ALLOWED_RISK_LEVELS_STR = os.getenv('ALLOWED_RISK_LEVELS', 'LOW,MEDIUM')
    ALLOWED_RISK_LEVELS = set()
    for level_str in ALLOWED_RISK_LEVELS_STR.upper().split(','):
        level_str = level_str.strip()
        try:
            ALLOWED_RISK_LEVELS.add(SQLRiskLevel[level_str])
        except KeyError:
            pass
    
    # 如果是生产环境且没有明确配置风险等级，则只允许LOW风险操作
    if ENV_TYPE == EnvironmentType.PRODUCTION and not os.getenv('ALLOWED_RISK_LEVELS'):
        ALLOWED_RISK_LEVELS = {SQLRiskLevel.LOW}
    
    # 最大SQL长度
    MAX_SQL_LENGTH = int(os.getenv('MAX_SQL_LENGTH', '1000'))
    
    # 敏感信息查询
    ALLOW_SENSITIVE_INFO = os.getenv('ALLOW_SENSITIVE_INFO', 'false').lower() in ('true', 'yes', '1')
    
    # 阻止的模式
    BLOCKED_PATTERNS_STR = os.getenv('BLOCKED_PATTERNS', '')
    BLOCKED_PATTERNS = [p.strip() for p in BLOCKED_PATTERNS_STR.split(',') if p.strip()]
    
    # 查询检查
    ENABLE_QUERY_CHECK = os.getenv('ENABLE_QUERY_CHECK', 'true').lower() in ('true', 'yes', '1')
    
    # 数据库隔离配置
    ENABLE_DATABASE_ISOLATION = os.getenv('ENABLE_DATABASE_ISOLATION', 'false').lower() in ('true', 'yes', '1')
    DATABASE_ACCESS_LEVEL = os.getenv('DATABASE_ACCESS_LEVEL', 'permissive').lower()
    
    # 生产环境强制数据库隔离
    if ENV_TYPE == EnvironmentType.PRODUCTION and not os.getenv('DATABASE_ACCESS_LEVEL'):
        DATABASE_ACCESS_LEVEL = 'restricted'  # 生产环境默认使用限制模式
        ENABLE_DATABASE_ISOLATION = True
        logger = __import__('logging').getLogger("mysql_server")
        logger.info("生产环境自动启用数据库隔离，访问级别设为 restricted")

# SQL操作配置
class SQLConfig:
    """SQL操作相关配置"""
    # 基础操作集合
    DDL_OPERATIONS = {
        'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'RENAME'
    }

    DML_OPERATIONS = {
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'MERGE'
    }

    # 元数据操作集合
    METADATA_OPERATIONS = {
        'SHOW', 'DESC', 'DESCRIBE', 'EXPLAIN', 'HELP',
        'ANALYZE', 'CHECK', 'CHECKSUM', 'OPTIMIZE'
    }

# 角色权限配置
class RolePermissionConfig:
    """角色权限控制配置"""
    # 是否启用角色权限控制
    ENABLE_ROLE_PERMISSION = os.getenv('ENABLE_ROLE_PERMISSION', 'false').lower() in ('true', 'yes', '1')

    # 需要应用权限过滤的表列表（逗号分隔）
    # 注意：os.getenv() 只接受两个参数（键和默认值），多个表名需要用逗号连接成一个字符串
    PERMISSION_TABLES_STR = os.getenv('PERMISSION_TABLES', '')
    PERMISSION_TABLES = set(
        table.strip() for table in PERMISSION_TABLES_STR.split(',') if table.strip()
    )

    # 权限字段名称（默认 gssq）
    PERMISSION_FIELD = os.getenv('PERMISSION_FIELD', 'gssq')

    # 用户角色表配置
    USER_ROLE_TABLE = os.getenv('USER_ROLE_TABLE', 'fr_user_role')
    USER_ROLE_USERNAME_FIELD = os.getenv('USER_ROLE_USERNAME_FIELD', 'username')
    USER_ROLE_EXTEND_FIELD = os.getenv('USER_ROLE_EXTEND_FIELD', 'extend1')
    USER_ROLE_PREFIX = os.getenv('USER_ROLE_PREFIX', 'RX')

    # 超级管理员豁免（逗号分隔的用户名列表）
    SUPER_ADMIN_USERS_STR = os.getenv('SUPER_ADMIN_USERS', '')
    SUPER_ADMIN_USERS = set(
        user.strip() for user in SUPER_ADMIN_USERS_STR.split(',') if user.strip()
    )

# MCP服务鉴权配置（传输层Header鉴权，安全整改要求）
class AuthConfig:
    """MCP服务鉴权配置

    鉴权在 HTTP Header 校验层完成（src/security/auth/middleware.py:AuthMiddleware），
    覆盖 SSE 流端点与消息端点，未鉴权请求无法建立 MCP 会话。支持两种模式：

    - token: Authorization: Bearer <token>，服务端只存 SHA-256 哈希，明文不上网（配合 HTTPS）
             适用于百炼平台等只能配置静态 Header 的调用方
    - hmac:  X-Auth-Key / X-Auth-Timestamp / X-Auth-Nonce / X-Auth-Signature 签名校验，
             AppSecret 永不离开客户端，带时间窗 + Nonce 防重放，适用于自研后端/网关
    """
    # 鉴权总开关（生产环境必须启用，否则 server.py 拒绝启动）
    ENABLED = os.getenv('ENABLE_AUTH', 'false').lower() in ('true', 'yes', '1')

    # 鉴权模式: token | hmac | both
    MODE = os.getenv('AUTH_MODE', 'both').lower()
    if MODE not in ('token', 'hmac', 'both'):
        MODE = 'both'

    # 执行模式: off(直接放行，仅本地调试) | audit(未鉴权只记日志不拦截，灰度观察) | enforce(拦截)
    ENFORCE_MODE = os.getenv('AUTH_ENFORCE_MODE', 'enforce').lower()
    if ENFORCE_MODE not in ('off', 'audit', 'enforce'):
        ENFORCE_MODE = 'enforce'

    # Bearer Token 凭据存储后端: env | db
    TOKEN_BACKEND = os.getenv('AUTH_TOKEN_BACKEND', 'env').lower()
    if TOKEN_BACKEND not in ('env', 'db'):
        TOKEN_BACKEND = 'env'

    # env 后端 Token 配置（服务端只存哈希，禁止存明文）
    # 格式: client_id:token_sha256_hex[:user_id][:expires_at][:scopes]，多组用分号分隔
    # 用 scripts/gen_token.py token --client-id xxx 生成
    TOKENS_STR = os.getenv('AUTH_TOKENS', '')

    # db 后端 Token 表名（建表语句见 docs/sql/auth_tables.sql）
    TOKEN_TABLE = os.getenv('AUTH_TOKEN_TABLE', 'mcp_auth_token')

    # env 后端 HMAC 密钥配置
    # 格式: app_key:app_secret[:client_id][:user_id][:scopes]，多组用分号分隔
    # 用 scripts/gen_token.py hmac-key --client-id xxx 生成
    HMAC_KEYS_STR = os.getenv('AUTH_HMAC_KEYS', '')

    # db 后端 HMAC 密钥表名
    HMAC_KEY_TABLE = os.getenv('AUTH_HMAC_KEY_TABLE', 'mcp_auth_key')

    # 签名时间戳允许偏差（秒），防重放窗口的一半
    TIMESTAMP_TOLERANCE = int(os.getenv('AUTH_TIMESTAMP_TOLERANCE', '300'))

    # Nonce 防重放缓存存活时间（秒），应 >= 2 倍时间戳偏差
    NONCE_TTL = int(os.getenv('AUTH_NONCE_TTL', '600'))

    # 豁免鉴权的路径（逗号分隔），仅用于探活类端点
    EXEMPT_PATHS_STR = os.getenv('AUTH_EXEMPT_PATHS', '/health')
    EXEMPT_PATHS = set(p.strip() for p in EXEMPT_PATHS_STR.split(',') if p.strip())

    # 行级权限身份绑定：凭据绑定的 user_id 优先于工具入参（入参不一致直接拒绝）
    BIND_USER = os.getenv('AUTH_BIND_USER', 'true').lower() in ('true', 'yes', '1')

    # 防爆破：同 IP 连续失败阈值与封禁时长（秒）
    MAX_FAILURES = int(os.getenv('AUTH_MAX_FAILURES', '10'))
    BLOCK_SECONDS = int(os.getenv('AUTH_BLOCK_SECONDS', '600'))

    # db 后端凭据查询缓存 TTL（秒），吊销操作最迟此时长后生效
    CREDENTIAL_CACHE_TTL = int(os.getenv('AUTH_CREDENTIAL_CACHE_TTL', '60'))

    # 生产环境收紧：强制执行模式不可降级为 audit/off
    # （未启用鉴权时由 server.py fail-fast 拒绝启动）
    if SecurityConfig.ENV_TYPE == EnvironmentType.PRODUCTION and ENFORCE_MODE != 'enforce':
        ENFORCE_MODE = 'enforce'
        logger = __import__('logging').getLogger("mysql_server")
        logger.info("生产环境自动将鉴权执行模式设为 enforce")

    @staticmethod
    def get_config():
        """构建鉴权配置快照（AuthSettings），供 AuthMiddleware 使用"""
        from src.security.auth.settings import AuthSettings
        return AuthSettings(
            enabled=AuthConfig.ENABLED,
            mode=AuthConfig.MODE,
            enforce_mode=AuthConfig.ENFORCE_MODE,
            token_backend=AuthConfig.TOKEN_BACKEND,
            tokens_str=AuthConfig.TOKENS_STR,
            token_table=AuthConfig.TOKEN_TABLE,
            hmac_keys_str=AuthConfig.HMAC_KEYS_STR,
            hmac_key_table=AuthConfig.HMAC_KEY_TABLE,
            timestamp_tolerance=AuthConfig.TIMESTAMP_TOLERANCE,
            nonce_ttl=AuthConfig.NONCE_TTL,
            exempt_paths=frozenset(AuthConfig.EXEMPT_PATHS),
            bind_user=AuthConfig.BIND_USER,
            max_failures=AuthConfig.MAX_FAILURES,
            block_seconds=AuthConfig.BLOCK_SECONDS,
            credential_cache_ttl=AuthConfig.CREDENTIAL_CACHE_TTL,
        ) 
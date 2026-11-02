-- ============================================================
-- MCP 服务鉴权凭据表（安全整改：传输层 Header 鉴权）
-- 使用 db 凭据后端时执行：
--   .env 设置 AUTH_TOKEN_BACKEND=db
--   Token 表名可通过 AUTH_TOKEN_TABLE / 密钥表名通过 AUTH_HMAC_KEY_TABLE 调整
-- 建表位置：与业务库同实例（服务使用 MYSQL_DATABASE 连接的库）
-- ============================================================

-- Bearer Token 凭据表（只存 SHA-256 哈希，永不存明文）
CREATE TABLE IF NOT EXISTS mcp_auth_token (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  client_id   VARCHAR(64)  NOT NULL COMMENT '调用方系统标识（如 bailian-prod）',
  token_hash  CHAR(64)     NOT NULL COMMENT 'Token 的 SHA-256 hex（scripts/gen_token.py 生成）',
  user_id     VARCHAR(64)  NULL     COMMENT '绑定的行级权限用户（fr_user_role.username），AUTH_BIND_USER 生效时以此为准',
  scopes      VARCHAR(255) NOT NULL DEFAULT 'query' COMMENT '授权范围（逗号分隔）',
  expires_at  DATETIME     NULL     COMMENT '过期时间（NULL=不过期，建议设置并定期轮换）',
  revoked     TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '吊销标记：置1后最迟 AUTH_CREDENTIAL_CACHE_TTL 秒内生效',
  remark      VARCHAR(255) NULL     COMMENT '备注（用途/负责人）',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_token_hash (token_hash),
  KEY idx_client (client_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='MCP服务 Bearer Token 凭据';

-- HMAC 签名密钥表（AppSecret 建议加密存储或托管 KMS，至少不得进入代码仓库）
CREATE TABLE IF NOT EXISTS mcp_auth_key (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  app_key     VARCHAR(64)  NOT NULL COMMENT '公开密钥标识（请求头 X-Auth-Key）',
  app_secret  VARCHAR(255) NOT NULL COMMENT '签名密钥（HMAC-SHA256），永不通过网络传输',
  client_id   VARCHAR(64)  NOT NULL COMMENT '调用方系统标识',
  user_id     VARCHAR(64)  NULL     COMMENT '绑定的行级权限用户',
  scopes      VARCHAR(255) NOT NULL DEFAULT 'query' COMMENT '授权范围（逗号分隔）',
  revoked     TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '吊销标记',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_app_key (app_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='MCP服务 HMAC 签名密钥';

-- 常用运维语句 -------------------------------------------------

-- 吊销某个 Token（泄露应急，立即执行）
-- UPDATE mcp_auth_token SET revoked = 1 WHERE client_id = 'bailian-prod';

-- 查看全部有效凭据
-- SELECT client_id, user_id, scopes, expires_at, revoked, created_at FROM mcp_auth_token;

-- 轮换：先为同一 client_id 插入新 token_hash，调用方切换后再吊销旧记录

"""
角色权限管理器
基于 gssq 字段的行级权限控制
"""
import logging
import re
import sqlparse
from typing import Optional, Tuple
from ..config import RolePermissionConfig

logger = logging.getLogger(__name__)


class RolePermissionManager:
    """角色权限管理器 - 基于 gssq 字段的行级权限控制"""

    def __init__(self):
        self.enabled = RolePermissionConfig.ENABLE_ROLE_PERMISSION
        self.permission_tables = RolePermissionConfig.PERMISSION_TABLES
        self.permission_field = RolePermissionConfig.PERMISSION_FIELD
        self.user_role_table = RolePermissionConfig.USER_ROLE_TABLE
        self.username_field = RolePermissionConfig.USER_ROLE_USERNAME_FIELD
        self.extend_field = RolePermissionConfig.USER_ROLE_EXTEND_FIELD
        self.role_prefix = RolePermissionConfig.USER_ROLE_PREFIX
        self.super_admins = RolePermissionConfig.SUPER_ADMIN_USERS

        if self.enabled:
            logger.info(f"角色权限控制已启用: 权限表={list(self.permission_tables)}, 权限字段={self.permission_field}")
        else:
            logger.debug("角色权限控制未启用")

    def should_apply_permission(self, sql_query: str, user_id: Optional[str]) -> bool:
        """
        判断是否需要应用权限控制

        Args:
            sql_query: SQL 查询语句
            user_id: 用户 ID

        Returns:
            是否需要应用权限控制
        """
        if not self.enabled:
            return False

        if not user_id:
            logger.debug("未提供 user_id，跳过权限控制")
            return False

        # 超级管理员豁免
        if user_id in self.super_admins:
            logger.debug(f"用户 {user_id} 是超级管理员，跳过权限控制")
            return False

        # 只处理 SELECT 查询
        normalized_sql = sql_query.strip().upper()
        if not normalized_sql.startswith('SELECT'):
            logger.debug("非 SELECT 查询，跳过权限控制")
            return False

        # 检查查询是否涉及需要权限控制的表
        if not self._contains_permission_tables(sql_query):
            logger.debug("查询不涉及权限控制表，跳过权限控制")
            return False

        return True

    def _contains_permission_tables(self, sql_query: str) -> bool:
        """
        检查 SQL 是否包含需要权限控制的表

        Args:
            sql_query: SQL 查询语句

        Returns:
            是否包含权限控制表
        """
        if not self.permission_tables:
            return False

        # 解析 SQL 获取表名
        parsed = sqlparse.parse(sql_query)
        if not parsed:
            return False

        sql_str = str(parsed[0]).upper()

        for table in self.permission_tables:
            # 匹配表名（考虑别名、database.table 等情况）
            patterns = [
                rf'\bFROM\s+`?{re.escape(table.upper())}`?\b',
                rf'\bJOIN\s+`?{re.escape(table.upper())}`?\b',
                rf'\b`?{re.escape(table.upper())}`?\s+AS\b',
                rf'\b`?{re.escape(table.upper())}`?\s+\w+\b',
            ]
            for pattern in patterns:
                if re.search(pattern, sql_str, re.IGNORECASE):
                    logger.debug(f"SQL 涉及权限控制表: {table}")
                    return True

        return False

    def inject_permission_filter(self, sql_query: str, user_id: Optional[str]) -> str:
        """
        注入权限过滤条件到 SQL 语句

        Args:
            sql_query: 原始 SQL 查询语句
            user_id: 用户 ID

        Returns:
            注入权限过滤后的 SQL 语句
        """
        if not self.should_apply_permission(sql_query, user_id):
            return sql_query

        # 构建权限过滤条件
        permission_condition = self._build_permission_condition(user_id)

        # 解析 SQL
        parsed = sqlparse.parse(sql_query)
        if not parsed:
            logger.warning("SQL 解析失败，无法注入权限条件")
            return sql_query

        statement = parsed[0]

        # 注入权限条件
        modified_sql = self._inject_where_clause(str(statement), permission_condition)

        logger.info(f"已为用户 {user_id} 注入权限过滤条件")
        logger.debug(f"原始 SQL: {sql_query}")
        logger.debug(f"修改后 SQL: {modified_sql}")

        return modified_sql

    def _build_permission_condition(self, user_id: str) -> str:
        """
        构建权限过滤条件

        Args:
            user_id: 用户 ID

        Returns:
            权限过滤 SQL 条件
        """
        # 防止 SQL 注入 - 转义单引号
        safe_user_id = user_id.replace("'", "''")

        condition = f"""(
    {self.permission_field} IN (
        SELECT REPLACE({self.extend_field}, '{self.role_prefix}', '')
        FROM {self.user_role_table}
        WHERE {self.username_field} = '{safe_user_id}'
    )
    OR '{safe_user_id}' NOT IN (
        SELECT {self.username_field} FROM {self.user_role_table}
    )
)"""
        return condition

    def _inject_where_clause(self, sql_query: str, condition: str) -> str:
        """
        向 SQL 注入 WHERE 条件

        Args:
            sql_query: 原始 SQL 查询
            condition: 要注入的条件

        Returns:
            注入条件后的 SQL
        """
        # 移除末尾的分号
        sql_query = sql_query.rstrip(';').strip()

        # 检查是否已有 WHERE 子句
        has_where = re.search(r'\bWHERE\b', sql_query, re.IGNORECASE)

        if has_where:
            # 已有 WHERE，使用 AND 连接
            # 需要考虑 GROUP BY, HAVING, ORDER BY, LIMIT 等子句
            order_by_match = re.search(
                r'\b(ORDER\s+BY|GROUP\s+BY|HAVING|LIMIT)\b',
                sql_query,
                re.IGNORECASE
            )

            if order_by_match:
                # 在 ORDER BY 等子句之前插入
                insert_pos = order_by_match.start()
                modified_sql = (
                    sql_query[:insert_pos].rstrip() +
                    f" AND {condition} " +
                    sql_query[insert_pos:]
                )
            else:
                # 直接在末尾添加
                modified_sql = f"{sql_query} AND {condition}"
        else:
            # 没有 WHERE，添加 WHERE 子句
            order_by_match = re.search(
                r'\b(ORDER\s+BY|GROUP\s+BY|HAVING|LIMIT)\b',
                sql_query,
                re.IGNORECASE
            )

            if order_by_match:
                insert_pos = order_by_match.start()
                modified_sql = (
                    sql_query[:insert_pos].rstrip() +
                    f" WHERE {condition} " +
                    sql_query[insert_pos:]
                )
            else:
                modified_sql = f"{sql_query} WHERE {condition}"

        return modified_sql


# 全局单例
_role_permission_manager = None


def get_role_permission_manager() -> RolePermissionManager:
    """
    获取角色权限管理器单例

    Returns:
        RolePermissionManager 实例
    """
    global _role_permission_manager
    if _role_permission_manager is None:
        _role_permission_manager = RolePermissionManager()
    return _role_permission_manager

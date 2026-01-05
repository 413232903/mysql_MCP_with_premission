"""
角色权限管理器
基于 gssq 字段的行级权限控制
"""
import logging
import re
import sqlparse
from typing import Optional, Set
from sqlparse.sql import Identifier, IdentifierList, Parenthesis, TokenList
from sqlparse.tokens import Keyword, DML, Whitespace, Punctuation
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
        self._normalized_permission_tables = {
            table.lower() for table in self.permission_tables
        }

        if self.enabled:
            if not self.permission_tables:
                logger.warning(
                    "⚠️ 角色权限控制已启用，但未配置权限表！"
                    "请在环境变量中设置 PERMISSION_TABLES=表名1,表名2,..."
                )
            else:
                logger.info(
                    f"✅ 角色权限控制已启用: 权限表={list(self.permission_tables)}, 权限字段={self.permission_field}"
                )
        else:
            logger.info(
                "ℹ️ 角色权限控制未启用。"
                "要启用权限控制，请在环境变量中设置 ENABLE_ROLE_PERMISSION=true"
            )

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
            logger.info("❌ 权限控制未启用，跳过权限过滤。请在环境变量中设置 ENABLE_ROLE_PERMISSION=true")
            return False

        if not user_id:
            logger.warning("⚠️ 未提供 user_id 参数，跳过权限控制。请在调用时传入 user_id 参数")
            return False

        # 超级管理员豁免
        if user_id in self.super_admins:
            logger.info(f"ℹ️ 用户 {user_id} 是超级管理员，跳过权限控制")
            return False

        statement = self._parse_first_statement(sql_query)
        if statement is None:
            logger.warning(f"❌ SQL 解析失败，跳过权限控制。SQL: {sql_query[:100]}")
            return False

        if not self._is_select_statement(statement):
            logger.info("ℹ️ 非 SELECT 查询，跳过权限控制（仅 SELECT 查询应用行级权限）")
            return False

        # 检查查询是否涉及需要权限控制的表
        table_names = self._extract_table_names(statement)
        logger.info(f"🔍 解析到的表名: {list(table_names)}")
        if not self._statement_contains_permission_tables(statement):
            logger.info(
                f"⚠️ 查询不涉及权限控制表，跳过权限控制。"
                f"查询的表: {list(table_names)}, 配置的权限表: {list(self._normalized_permission_tables)}"
            )
            return False

        logger.info(f"✅ 权限检查通过，将应用权限过滤 - user_id: {user_id}, 涉及表: {list(table_names)}")
        return True

    def _parse_first_statement(self, sql_query: str) -> Optional[TokenList]:
        """
        解析 SQL 并返回首个 Statement

        Args:
            sql_query: SQL 查询语句

        Returns:
            首个解析后的 Statement 对象
        """
        parsed = sqlparse.parse(sql_query)
        if not parsed:
            return None
        return parsed[0]

    def _contains_permission_tables(self, sql_query: str) -> bool:
        """
        检查 SQL 是否包含需要权限控制的表

        Args:
            sql_query: SQL 查询语句

        Returns:
            是否包含权限控制表
        """
        statement = self._parse_first_statement(sql_query)
        if statement is None:
            return False
        return self._statement_contains_permission_tables(statement)

    def inject_permission_filter(self, sql_query: str, user_id: Optional[str]) -> str:
        """
        注入权限过滤条件到 SQL 语句

        Args:
            sql_query: 原始 SQL 查询语句
            user_id: 用户 ID

        Returns:
            注入权限过滤后的 SQL 语句
        """
        # 记录权限检查的详细信息（使用 INFO 级别确保可见）
        logger.info(f"🔍 开始权限检查 - user_id: {user_id}, SQL: {sql_query[:100]}...")
        logger.info(f"🔍 权限控制启用状态: {self.enabled}")
        logger.info(f"🔍 配置的权限表: {list(self._normalized_permission_tables)}")
        
        if not self.should_apply_permission(sql_query, user_id):
            logger.info(f"⚠️ 权限控制未应用 - user_id: {user_id}, SQL: {sql_query[:100]}...")
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

        logger.info(f"✅ 已为用户 {user_id} 注入权限过滤条件")
        logger.info(f"📝 原始 SQL: {sql_query}")
        logger.info(f"🔒 修改后 SQL: {modified_sql}")

        return modified_sql

    def _is_select_statement(self, statement: TokenList) -> bool:
        """
        判断语句是否为 SELECT
        """
        if statement is None:
            return False

        stmt_type = statement.get_type()
        if stmt_type and stmt_type.upper() == 'SELECT':
            return True

        first_token = statement.token_first(skip_cm=True, skip_ws=True)
        if not first_token:
            return False

        if first_token.ttype is DML:
            return first_token.value.upper() == 'SELECT'

        if first_token.ttype is Keyword and first_token.value.upper() == 'WITH':
            dml_token = self._find_first_dml_token(statement)
            return dml_token is not None and dml_token.value.upper() == 'SELECT'

        return False

    def _find_first_dml_token(self, token_list: TokenList):
        """
        在语句中查找首个 DML Token
        """
        if isinstance(token_list, TokenList):
            for token in token_list.tokens:
                if token.ttype is DML:
                    return token
                if token.is_group:
                    nested = self._find_first_dml_token(token)
                    if nested:
                        return nested
        return None

    def _statement_contains_permission_tables(self, statement: TokenList) -> bool:
        """
        检查 Statement 是否包含需要权限控制的表
        """
        if not self._normalized_permission_tables:
            return False

        table_names = self._extract_table_names(statement)
        if table_names:
            logger.debug(f"解析到的表名: {table_names}")

        has_permission_table = any(table in self._normalized_permission_tables for table in table_names)
        logger.debug(f"是否包含权限表: {has_permission_table}, 查询表: {list(table_names)}, 权限表: {list(self._normalized_permission_tables)}")
        return has_permission_table

    def _extract_table_names(self, token_list: TokenList) -> Set[str]:
        """
        从 TokenList 中提取表名集合
        """
        tables: Set[str] = set()
        from_context = False

        if not isinstance(token_list, TokenList):
            return tables

        for token in token_list.tokens:
            if token.is_group:
                tables.update(self._extract_table_names(token))

            if token.ttype is Keyword:
                keyword_value = token.value.upper()
                if keyword_value in {'FROM', 'JOIN'}:
                    from_context = True
                    continue
                if from_context and keyword_value in {
                    'ON', 'USING', 'WHERE', 'GROUP', 'ORDER', 'HAVING',
                    'LIMIT', 'UNION', 'EXCEPT', 'INTERSECT'
                }:
                    from_context = False
                    continue

            if not from_context:
                continue

            if isinstance(token, IdentifierList):
                for identifier in token.get_identifiers():
                    name = self._clean_identifier(identifier)
                    if name:
                        tables.add(name)
                continue

            if isinstance(token, Identifier):
                name = self._clean_identifier(token)
                if name:
                    tables.add(name)
                continue

            if isinstance(token, Parenthesis):
                # 子查询在递归时已经处理，这里跳过
                continue

            if token.ttype in (Whitespace, Punctuation):
                continue

            raw_name = self._clean_raw_token(token)
            if raw_name:
                tables.add(raw_name)

        return tables

    def _clean_identifier(self, identifier: Identifier) -> Optional[str]:
        """
        获取 Identifier 对应的真实表名
        """
        real_name = identifier.get_real_name()
        if real_name:
            return real_name.strip('`"').lower()

        name = identifier.get_name()
        if name:
            return name.strip('`"').lower()

        return self._clean_raw_token(identifier)

    def _clean_raw_token(self, token) -> Optional[str]:
        """
        从普通 Token 中提取表名
        """
        value = str(token).strip()
        if not value:
            return None

        first_part = value.split()[0]
        first_part = first_part.strip('`"')
        if '.' in first_part:
            first_part = first_part.split('.')[-1]

        if not first_part or first_part.upper() in {'(', ')'}:
            return None

        return first_part.lower()

    def _build_permission_condition(self, user_id: str) -> str:
        """
        构建权限过滤条件
        支持权限值格式转换：去掉 RX、Y 前缀和 销区 后缀，然后使用模糊匹配

        Args:
            user_id: 用户 ID

        Returns:
            权限过滤 SQL 条件
        """
        # 防止 SQL 注入 - 转义单引号
        safe_user_id = user_id.replace("'", "''")

        # 构建权限值转换逻辑：
        # 1. 去掉 RX 前缀
        # 2. 去掉 Y 前缀（如果存在）
        # 3. 去掉 销区 后缀（如果存在）
        # 4. 使用模糊匹配来匹配表中的值
        permission_value_transform = (
            f"TRIM(REPLACE(REPLACE(REPLACE({self.extend_field}, '{self.role_prefix}', ''), 'Y', ''), '销区', ''))"
        )

        # 使用 LIKE 模糊匹配，支持权限值格式与表字段值不完全一致的情况
        # 例如：权限值 "两湖" 可以匹配表中的 "湖北"、"湖南"、"两湖" 等
        # 使用 EXISTS 子查询，在子查询中计算转换后的权限值并匹配
        condition = f"""(
    EXISTS (
        SELECT 1
        FROM {self.user_role_table} ur
        WHERE ur.{self.username_field} = '{safe_user_id}'
        AND {self.permission_field} LIKE CONCAT('%', TRIM(REPLACE(REPLACE(REPLACE(ur.{self.extend_field}, '{self.role_prefix}', ''), 'Y', ''), '销区', '')), '%')
    )
    OR {self.permission_field} IN (
        SELECT {permission_value_transform}
        FROM {self.user_role_table}
        WHERE {self.username_field} = '{safe_user_id}'
        AND {permission_value_transform} IS NOT NULL
        AND {permission_value_transform} != ''
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

import json
import logging
from typing import Any, Dict, Optional
from mcp.server.fastmcp import FastMCP
from src.db.mysql_operations import get_db_connection, execute_query
from src.security.database_scope_checker import create_database_checker
from src.config import SecurityConfig, DatabaseConfig
import aiomysql

from .metadata_base_tool import MetadataToolBase

logger = logging.getLogger("mysql_server")

# MySQL可用性检查变量，默认认为aiomysql已可用
mysql_available = True

def register_mysql_tool(mcp: FastMCP):
    """
    注册MySQL查询工具到MCP服务器
    
    Args:
        mcp: FastMCP服务器实例
    """
    logger.debug("注册MySQL查询工具...")
    
    # 创建数据库范围检查器
    database_checker = None
    if SecurityConfig.ENABLE_DATABASE_ISOLATION and DatabaseConfig.DATABASE:
        database_checker = create_database_checker(
            allowed_database=DatabaseConfig.DATABASE,
            access_level=SecurityConfig.DATABASE_ACCESS_LEVEL
        )
    
    @mcp.tool()
    @MetadataToolBase.handle_query_error
    async def mysql_query(query: str, user_id: Optional[str] = None, userid: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> str:
        """
        执行MySQL查询并返回结果

        Args:
            query: SQL查询语句
            user_id: 用户ID，用于权限控制（可选）
            userid: 用户ID的别名，兼容不同调用方式（可选）
            params: 查询参数 (可选)

        Returns:
            查询结果的JSON字符串
        """
        # 兼容多种 user_id 传递方式（优先级：user_id > userid > params.userid）
        effective_user_id = user_id or userid
        if not effective_user_id and params:
            effective_user_id = params.pop('userid', None) or params.pop('user_id', None)

        logger.debug(f"执行MySQL查询: {query}, 用户: {effective_user_id}, 参数: {params}")

        # 检查数据库隔离限制
        if database_checker:
            is_allowed, violations = database_checker.check_query(query)
            if not is_allowed:
                violation_details = "; ".join(violations)
                raise ValueError(f"数据库隔离限制: {violation_details}")

        async with get_db_connection() as connection:
            # 传递 effective_user_id 到数据库操作层
            results = await execute_query(connection, query, params, user_id=effective_user_id)
            
            # 检查是否是修改操作返回的影响行数
            operation = query.strip().split()[0].upper()
            if operation in {'UPDATE', 'DELETE', 'INSERT'} and results and 'affected_rows' in results[0]:
                affected_rows = results[0]['affected_rows']
                logger.info(f"{operation}操作影响了{affected_rows}行数据")
                
            # 添加元数据信息
            metadata_info = {
                "metadata_info": {
                    "operation_type": operation,
                    "result_count": len(results)
                },
                "results": results
            }
            
            return json.dumps(metadata_info, default=str)
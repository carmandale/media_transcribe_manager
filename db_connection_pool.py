"""
Shim module to re-export DatabaseConnectionPool from core_modules.
"""
from core_modules.db_connection_pool import DatabaseConnectionPool
__all__ = ['DatabaseConnectionPool']
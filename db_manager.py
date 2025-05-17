"""
Shim module to re-export DatabaseManager from core_modules.
"""
from core_modules.db_manager import DatabaseManager
__all__ = ['DatabaseManager']
# config/__init__.py
"""
Configuration package initialization
Provides centralized configuration management for the application
"""

from .settings import Config
from .database import get_db_connection, init_db, close_db

__all__ = ['Config', 'get_db_connection', 'init_db', 'close_db']

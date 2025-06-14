"""
資料庫模組

提供 SQLite 資料庫管理、短檔名生成等功能。
"""

from .database_manager import DatabaseManager
from .short_key_generator import ShortKeyGenerator
from .models import FileRecord, ShortKeySequence, ReservedShortKey, FileOperationLog
from .exceptions import (
    DatabaseError,
    DuplicateFileError,
    ShortKeyExhaustedError,
    ShortKeyCollisionError,
    ConnectionPoolError,
    SchemaVersionError
)

__all__ = [
    "DatabaseManager",
    "ShortKeyGenerator",
    "FileRecord",
    "ShortKeySequence",
    "ReservedShortKey",
    "FileOperationLog",
    "DatabaseError",
    "DuplicateFileError",
    "ShortKeyExhaustedError",
    "ShortKeyCollisionError",
    "ConnectionPoolError",
    "SchemaVersionError"
]
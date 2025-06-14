"""
資料庫相關異常類別

定義資料庫操作中可能發生的各種異常。
"""


class DatabaseError(Exception):
    """資料庫錯誤基類"""
    pass


class DuplicateFileError(DatabaseError):
    """重複檔案錯誤"""
    pass


class ShortKeyExhaustedError(DatabaseError):
    """短檔名耗盡錯誤"""
    pass


class ShortKeyCollisionError(DatabaseError):
    """短檔名衝突錯誤"""
    pass


class ConnectionPoolError(DatabaseError):
    """連接池錯誤"""
    pass


class SchemaVersionError(DatabaseError):
    """資料庫架構版本錯誤"""
    pass
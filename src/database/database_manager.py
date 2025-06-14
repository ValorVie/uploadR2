"""
SQLite 資料庫管理器

提供資料庫連接管理、檔案記錄存儲、查詢等核心功能。
"""

import sqlite3
import threading
import json
import asyncio
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from .models import FileRecord, ShortKeySequence, ReservedShortKey, FileOperationLog
from .schema import (
    get_all_schema_sql, SCHEMA_VERSION, RESERVED_KEYS,
    CREATE_TABLES_SQL, CREATE_INDEXES_SQL, CREATE_TRIGGERS_SQL
)
from .exceptions import (
    DatabaseError, DuplicateFileError, ShortKeyCollisionError,
    ConnectionPoolError, SchemaVersionError
)
from ..utils.logger import get_logger


class DatabaseManager:
    """SQLite 資料庫管理器"""
    
    def __init__(self, db_path: str = "data/uploadr2.db", pool_size: int = 10):
        """
        初始化資料庫管理器
        
        Args:
            db_path: 資料庫檔案路徑
            pool_size: 連接池大小
        """
        self.db_path = Path(db_path)
        self.pool_size = pool_size
        self._local = threading.local()
        self._lock = threading.RLock()
        self.logger = get_logger(__name__)
        
        # 確保資料庫目錄存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化資料庫
        self._initialize_database()
        
        # 初始化短檔名生成器（在資料庫初始化之後）
        from .short_key_generator import ShortKeyGenerator
        self._short_key_generator = ShortKeyGenerator(self)
    
    @contextmanager
    def get_connection(self):
        """
        獲取資料庫連接（使用執行緒本地存儲）
        
        Yields:
            sqlite3.Connection: 資料庫連接
        """
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            try:
                self._local.connection = sqlite3.connect(
                    str(self.db_path),
                    timeout=30.0,
                    check_same_thread=False
                )
                self._local.connection.row_factory = sqlite3.Row
                
                # 啟用 SQLite 優化設定
                self._local.connection.execute("PRAGMA foreign_keys = ON")
                self._local.connection.execute("PRAGMA journal_mode = WAL")
                self._local.connection.execute("PRAGMA synchronous = NORMAL")
                self._local.connection.execute("PRAGMA cache_size = 10000")
                self._local.connection.execute("PRAGMA temp_store = MEMORY")
                
                self.logger.debug("建立新的資料庫連接")
                
            except sqlite3.Error as e:
                raise ConnectionPoolError(f"無法建立資料庫連接: {e}")
        
        try:
            yield self._local.connection
        except Exception as e:
            # 發生錯誤時回滾事務
            try:
                self._local.connection.rollback()
            except:
                pass
            raise
    
    def _initialize_database(self) -> None:
        """初始化資料庫結構"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 檢查並更新資料庫架構
                self._check_and_update_schema(cursor)
                
                # 創建所有表
                self._create_tables(cursor)
                
                # 創建索引
                self._create_indexes(cursor)
                
                # 創建觸發器
                self._create_triggers(cursor)
                
                # 初始化基礎數據
                self._initialize_base_data(cursor)
                
                conn.commit()
                self.logger.info("資料庫初始化完成")
                
        except Exception as e:
            self.logger.error(f"資料庫初始化失敗: {e}")
            raise DatabaseError(f"資料庫初始化失敗: {e}")
    
    def _check_and_update_schema(self, cursor: sqlite3.Cursor) -> None:
        """檢查並更新資料庫架構版本"""
        try:
            cursor.execute("SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1")
            row = cursor.fetchone()
            
            if row:
                current_version = row[0]
                if current_version > SCHEMA_VERSION:
                    raise SchemaVersionError(
                        f"資料庫版本 {current_version} 高於程式支援版本 {SCHEMA_VERSION}"
                    )
                elif current_version < SCHEMA_VERSION:
                    self.logger.info(f"需要升級資料庫版本: {current_version} -> {SCHEMA_VERSION}")
                    # 這裡可以添加資料庫遷移邏輯
            else:
                # 新的資料庫，記錄當前版本
                cursor.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,)
                )
                
        except sqlite3.OperationalError:
            # schema_version 表不存在，這是新資料庫
            pass
    
    def _create_tables(self, cursor: sqlite3.Cursor) -> None:
        """創建所有資料表"""
        for sql in CREATE_TABLES_SQL:
            cursor.execute(sql)
    
    def _create_indexes(self, cursor: sqlite3.Cursor) -> None:
        """創建所有索引"""
        for sql in CREATE_INDEXES_SQL:
            cursor.execute(sql)
    
    def _create_triggers(self, cursor: sqlite3.Cursor) -> None:
        """創建所有觸發器"""
        for sql in CREATE_TRIGGERS_SQL:
            cursor.execute(sql)
    
    def _initialize_base_data(self, cursor: sqlite3.Cursor) -> None:
        """初始化基礎數據"""
        # 初始化保留關鍵字
        for key, reason in RESERVED_KEYS:
            cursor.execute("""
                INSERT OR IGNORE INTO reserved_short_keys (short_key, reason)
                VALUES (?, ?)
            """, (key, reason))
        
        # 初始化4位長度序列
        # 使用硬編碼的字符集大小，避免在資料庫初始化時依賴短檔名生成器
        charset_size = 62  # digits + lowercase + uppercase = 10 + 26 + 26 = 62
        max_possible = int((charset_size ** 4) * 0.999)  # 預留0.1%
        
        cursor.execute("""
            INSERT OR IGNORE INTO short_key_sequences
            (key_length, current_sequence, max_possible)
            VALUES (4, 0, ?)
        """, (max_possible,))
    
    def store_file_record(self, record: FileRecord) -> int:
        """
        存儲檔案記錄
        
        Args:
            record: 檔案記錄
            
        Returns:
            int: 檔案記錄ID
            
        Raises:
            DuplicateFileError: 檔案已存在
            ShortKeyCollisionError: 短檔名衝突
        """
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                try:
                    # 生成短檔名（如果需要）
                    if record.short_key is None:
                        short_key, length, salt = self._short_key_generator.generate_short_key()
                        record.short_key = short_key
                        record.short_key_length = length
                        record.short_key_generation_salt = salt
                        record.short_key_created_at = datetime.now()
                    
                    # 插入記錄
                    cursor.execute("""
                        INSERT INTO file_records (
                            uuid_key, short_key, original_filename, file_extension,
                            file_size, mime_type, sha512_hash, hash_algorithm,
                            r2_object_key, upload_url, upload_timestamp,
                            short_key_length, short_key_generation_salt, short_key_created_at,
                            status, metadata, tags
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record.uuid_key, record.short_key, record.original_filename,
                        record.file_extension, record.file_size, record.mime_type,
                        record.sha512_hash, record.hash_algorithm, record.r2_object_key,
                        record.upload_url, record.upload_timestamp,
                        record.short_key_length, record.short_key_generation_salt,
                        record.short_key_created_at, record.status,
                        json.dumps(record.metadata) if record.metadata else None,
                        json.dumps(record.tags) if record.tags else None
                    ))
                    
                    file_id = cursor.lastrowid
                    conn.commit()
                    
                    # 記錄操作日誌
                    self._log_operation(cursor, file_id, "upload", {
                        "original_filename": record.original_filename,
                        "file_size": record.file_size,
                        "short_key": record.short_key
                    })
                    
                    conn.commit()
                    self.logger.info(f"檔案記錄已存儲: {record.original_filename} -> {record.short_key}")
                    return file_id
                    
                except sqlite3.IntegrityError as e:
                    conn.rollback()
                    error_msg = str(e).lower()
                    
                    if "uuid_key" in error_msg:
                        raise DuplicateFileError(f"檔案已存在: {record.uuid_key}")
                    elif "sha512_hash" in error_msg:
                        raise DuplicateFileError(f"檔案雜湊已存在: {record.sha512_hash}")
                    elif "short_key" in error_msg:
                        # 短檔名衝突，重試生成（限制重試次數）
                        retry_count = getattr(record, '_retry_count', 0)
                        if retry_count >= 3:  # 最多重試3次
                            raise DatabaseError(f"短檔名生成失敗，已重試 {retry_count} 次: {record.short_key}")
                        
                        self.logger.warning(f"短檔名衝突，重試生成 (第 {retry_count + 1} 次): {record.short_key}")
                        record.short_key = None  # 重置短檔名
                        record._retry_count = retry_count + 1  # 增加重試計數
                        return self.store_file_record(record)  # 遞迴重試
                    else:
                        raise DatabaseError(f"數據庫完整性錯誤: {e}")
                
                except Exception as e:
                    conn.rollback()
                    self.logger.error(f"存儲檔案記錄失敗: {e}")
                    raise DatabaseError(f"存儲檔案記錄失敗: {e}")
    
    def get_file_by_uuid(self, uuid_key: str) -> Optional[FileRecord]:
        """
        通過UUID鍵獲取檔案記錄
        
        Args:
            uuid_key: UUID鍵
            
        Returns:
            Optional[FileRecord]: 檔案記錄，不存在時返回None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM file_records WHERE uuid_key = ? AND status = 'active'
            """, (uuid_key,))
            
            row = cursor.fetchone()
            if row:
                return self._row_to_file_record(row)
            return None
    
    def get_file_by_short_key(self, short_key: str) -> Optional[FileRecord]:
        """
        通過短檔名獲取檔案記錄
        
        Args:
            short_key: 短檔名
            
        Returns:
            Optional[FileRecord]: 檔案記錄，不存在時返回None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM file_records WHERE short_key = ? AND status = 'active'
            """, (short_key,))
            
            row = cursor.fetchone()
            if row:
                # 記錄訪問日誌
                self._log_operation(cursor, row['id'], "access", {
                    "access_method": "short_key",
                    "short_key": short_key
                })
                conn.commit()
                
                return self._row_to_file_record(row)
            return None
    
    def check_duplicate_by_hash(self, sha512_hash: str) -> Optional[FileRecord]:
        """
        通過雜湊值檢查重複檔案
        
        Args:
            sha512_hash: SHA512雜湊值
            
        Returns:
            Optional[FileRecord]: 存在的檔案記錄，不存在時返回None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM file_records WHERE sha512_hash = ? AND status = 'active'
            """, (sha512_hash,))
            
            row = cursor.fetchone()
            if row:
                return self._row_to_file_record(row)
            return None
    
    def check_short_key_exists(self, short_key: str) -> bool:
        """
        檢查短檔名是否已存在
        
        Args:
            short_key: 要檢查的短檔名
            
        Returns:
            bool: 短檔名是否已存在
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 1 FROM file_records WHERE short_key = ? AND status = 'active'
                LIMIT 1
            """, (short_key,))
            
            return cursor.fetchone() is not None
    
    def update_file_record_upload_info(self, sha512_hash: str, r2_object_key: str, upload_url: str) -> bool:
        """
        更新檔案記錄的上傳資訊
        
        Args:
            sha512_hash: 檔案的 SHA512 雜湊值
            r2_object_key: R2 對象鍵
            upload_url: 上傳 URL
            
        Returns:
            bool: 是否更新成功
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # 更新檔案記錄的上傳資訊
                cursor.execute("""
                    UPDATE file_records
                    SET r2_object_key = ?, upload_url = ?, updated_at = ?
                    WHERE sha512_hash = ? AND status = 'active'
                """, (r2_object_key, upload_url, datetime.now().isoformat(), sha512_hash))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    self.logger.debug(f"更新檔案記錄上傳資訊成功: {sha512_hash} -> {r2_object_key}")
                    return True
                else:
                    self.logger.warning(f"找不到要更新的檔案記錄: {sha512_hash}")
                    return False
                    
            except Exception as e:
                conn.rollback()
                self.logger.error(f"更新檔案記錄失敗: {e}")
                return False
    
    def _row_to_file_record(self, row: sqlite3.Row) -> FileRecord:
        """
        將資料庫行轉換為 FileRecord 對象
        
        Args:
            row: 資料庫行
            
        Returns:
            FileRecord: 檔案記錄對象
        """
        return FileRecord(
            id=row['id'],
            uuid_key=row['uuid_key'],
            short_key=row['short_key'],
            original_filename=row['original_filename'],
            file_extension=row['file_extension'],
            file_size=row['file_size'],
            mime_type=row['mime_type'],
            sha512_hash=row['sha512_hash'],
            hash_algorithm=row['hash_algorithm'],
            r2_object_key=row['r2_object_key'],
            upload_url=row['upload_url'],
            upload_timestamp=datetime.fromisoformat(row['upload_timestamp']) if row['upload_timestamp'] else None,
            short_key_length=row['short_key_length'],
            short_key_generation_salt=row['short_key_generation_salt'],
            short_key_created_at=datetime.fromisoformat(row['short_key_created_at']) if row['short_key_created_at'] else None,
            status=row['status'],
            access_count=row['access_count'],
            last_accessed_at=datetime.fromisoformat(row['last_accessed_at']) if row['last_accessed_at'] else None,
            metadata=json.loads(row['metadata']) if row['metadata'] else None,
            tags=json.loads(row['tags']) if row['tags'] else None,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )
    
    def _log_operation(
        self, 
        cursor: sqlite3.Cursor, 
        file_record_id: int, 
        operation_type: str, 
        operation_details: Optional[Dict[str, Any]] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        記錄檔案操作日誌
        
        Args:
            cursor: 資料庫游標
            file_record_id: 檔案記錄ID
            operation_type: 操作類型
            operation_details: 操作詳情
            client_ip: 客戶端IP
            user_agent: 用戶代理
        """
        cursor.execute("""
            INSERT INTO file_operation_logs (
                file_record_id, operation_type, operation_details, client_ip, user_agent
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            file_record_id,
            operation_type,
            json.dumps(operation_details) if operation_details else None,
            client_ip,
            user_agent
        ))
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        獲取資料庫統計資訊
        
        Returns:
            Dict[str, Any]: 統計資訊
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 基本統計
            cursor.execute("SELECT COUNT(*) FROM file_records WHERE status = 'active'")
            total_files = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM file_records WHERE short_key IS NOT NULL AND status = 'active'")
            files_with_short_keys = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(file_size) FROM file_records WHERE status = 'active'")
            total_size = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(DISTINCT file_extension) FROM file_records WHERE status = 'active'")
            unique_extensions = cursor.fetchone()[0]
            
            # 檔案類型分布
            cursor.execute("""
                SELECT file_extension, COUNT(*) as count
                FROM file_records 
                WHERE status = 'active'
                GROUP BY file_extension 
                ORDER BY count DESC 
                LIMIT 10
            """)
            extension_distribution = [
                {"extension": row[0], "count": row[1]} 
                for row in cursor.fetchall()
            ]
            
            # 短檔名統計
            short_key_stats = self._short_key_generator.get_statistics()
            
            return {
                "total_files": total_files,
                "files_with_short_keys": files_with_short_keys,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "unique_extensions": unique_extensions,
                "extension_distribution": extension_distribution,
                "short_key_statistics": short_key_stats
            }
    
    def close(self) -> None:
        """關閉資料庫管理器"""
        if hasattr(self._local, 'connection') and self._local.connection:
            try:
                self._local.connection.close()
                self._local.connection = None
                self.logger.debug("資料庫連接已關閉")
            except Exception as e:
                self.logger.warning(f"關閉資料庫連接時發生錯誤: {e}")
    
    def __del__(self):
        """析構函數"""
        self.close()
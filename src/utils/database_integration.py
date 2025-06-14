"""
資料庫整合工具

將資料庫功能與現有的檔案處理流程整合。
"""

import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from ..config import Config
from ..database import DatabaseManager, FileRecord, DuplicateFileError
from .hash_utils import HashUtils
from .logger import get_logger


class DatabaseIntegration:
    """資料庫整合類別"""
    
    def __init__(self, config: Config):
        """
        初始化資料庫整合
        
        Args:
            config: 配置物件
        """
        self.config = config
        self.logger = get_logger(__name__)
        
        # 初始化資料庫管理器
        if config.enable_short_keys:
            self.db_manager = DatabaseManager(
                db_path=config.database_path,
                pool_size=config.database_pool_size
            )
        else:
            self.db_manager = None
    
    def create_file_record_from_path(
        self, 
        file_path: Path,
        r2_object_key: str,
        upload_url: str
    ) -> FileRecord:
        """
        從檔案路徑創建檔案記錄
        
        Args:
            file_path: 檔案路徑
            r2_object_key: R2對象鍵
            upload_url: 上傳URL
            
        Returns:
            FileRecord: 檔案記錄對象
        """
        # 計算檔案雜湊
        sha512_hash = HashUtils.calculate_file_hash(file_path, self.config.hash_algorithm)
        if not sha512_hash:
            raise ValueError(f"無法計算檔案雜湊: {file_path}")
        
        # 生成UUID鍵
        uuid_key = HashUtils.hash_to_uuid(sha512_hash)
        
        # 獲取檔案資訊
        file_stat = file_path.stat()
        mime_type, _ = mimetypes.guess_type(str(file_path))
        
        return FileRecord(
            uuid_key=uuid_key,
            original_filename=file_path.name,
            file_extension=file_path.suffix.lower(),
            file_size=file_stat.st_size,
            mime_type=mime_type or "application/octet-stream",
            sha512_hash=sha512_hash,
            hash_algorithm=self.config.hash_algorithm,
            r2_object_key=r2_object_key,
            upload_url=upload_url,
            upload_timestamp=datetime.now()
        )
    
    def check_duplicate_file(self, file_path: Path) -> Optional[FileRecord]:
        """
        檢查檔案是否重複
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            Optional[FileRecord]: 如果檔案重複，返回現有記錄；否則返回None
        """
        if not self.db_manager:
            return None
        
        # 計算檔案雜湊
        sha512_hash = HashUtils.calculate_file_hash(file_path, self.config.hash_algorithm)
        if not sha512_hash:
            return None
        
        # 檢查資料庫中是否存在
        return self.db_manager.check_duplicate_by_hash(sha512_hash)
    
    def store_file_record(self, record: FileRecord) -> int:
        """
        存儲檔案記錄到資料庫
        
        Args:
            record: 檔案記錄
            
        Returns:
            int: 檔案記錄ID
            
        Raises:
            DuplicateFileError: 檔案已存在
        """
        if not self.db_manager:
            self.logger.warning("資料庫管理器未啟用，跳過檔案記錄存儲")
            return -1
        
        try:
            file_id = self.db_manager.store_file_record(record)
            self.logger.info(f"檔案記錄已存儲: {record.original_filename} -> {record.short_key}")
            return file_id
        except DuplicateFileError as e:
            self.logger.warning(f"檔案重複: {e}")
            raise
        except Exception as e:
            self.logger.error(f"存儲檔案記錄失敗: {e}")
            raise
    
    def update_file_record_upload_info(self, sha512_hash: str, r2_object_key: str, upload_url: str) -> bool:
        """
        更新檔案記錄的上傳資訊
        
        Args:
            sha512_hash: 檔案的 SHA512 雜湊
            r2_object_key: R2 對象鍵
            upload_url: 上傳 URL
            
        Returns:
            bool: 是否更新成功
        """
        if not self.db_manager:
            self.logger.warning("資料庫管理器未啟用，跳過檔案記錄更新")
            return False
        
        try:
            # 使用資料庫管理器的更新方法
            success = self.db_manager.update_file_record_upload_info(sha512_hash, r2_object_key, upload_url)
            if success:
                self.logger.info(f"檔案記錄上傳資訊已更新: {r2_object_key}")
            return success
            
        except Exception as e:
            self.logger.error(f"更新檔案記錄失敗: {e}")
            return False
    
    def get_file_by_short_key(self, short_key: str) -> Optional[FileRecord]:
        """
        通過短檔名獲取檔案記錄
        
        Args:
            short_key: 短檔名
            
        Returns:
            Optional[FileRecord]: 檔案記錄
        """
        if not self.db_manager:
            return None
        
        return self.db_manager.get_file_by_short_key(short_key)
    
    def get_file_by_uuid(self, uuid_key: str) -> Optional[FileRecord]:
        """
        通過UUID鍵獲取檔案記錄
        
        Args:
            uuid_key: UUID鍵
            
        Returns:
            Optional[FileRecord]: 檔案記錄
        """
        if not self.db_manager:
            return None
        
        return self.db_manager.get_file_by_uuid(uuid_key)
    
    def get_statistics(self) -> Optional[dict]:
        """
        獲取資料庫統計資訊
        
        Returns:
            Optional[dict]: 統計資訊
        """
        if not self.db_manager:
            return None
        
        return self.db_manager.get_statistics()
    
    def close(self) -> None:
        """關閉資料庫連接"""
        if self.db_manager:
            self.db_manager.close()
    
    def __del__(self):
        """析構函數"""
        self.close()


def create_database_integration(config: Config) -> Optional[DatabaseIntegration]:
    """
    創建資料庫整合實例
    
    Args:
        config: 配置物件
        
    Returns:
        Optional[DatabaseIntegration]: 資料庫整合實例，如果未啟用則返回None
    """
    if config.enable_short_keys:
        return DatabaseIntegration(config)
    return None
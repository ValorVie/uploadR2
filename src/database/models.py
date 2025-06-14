"""
資料庫模型定義

定義資料庫中使用的數據結構。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List


@dataclass
class FileRecord:
    """檔案記錄數據類"""
    # 主鍵和基本標識
    id: Optional[int] = None
    uuid_key: str = ""
    short_key: Optional[str] = None
    
    # 檔案基本資訊
    original_filename: str = ""
    file_extension: str = ""
    file_size: int = 0
    mime_type: str = ""
    
    # 雜湊和校驗
    sha512_hash: str = ""
    hash_algorithm: str = "sha512"
    
    # 上傳資訊
    r2_object_key: str = ""
    upload_url: str = ""
    upload_timestamp: Optional[datetime] = None
    
    # 短檔名生成資訊
    short_key_length: Optional[int] = None
    short_key_generation_salt: Optional[str] = None
    short_key_created_at: Optional[datetime] = None
    
    # 檔案狀態
    status: str = "active"  # active, deleted, archived
    access_count: int = 0
    last_accessed_at: Optional[datetime] = None
    
    # 元數據
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    
    # 時間戳
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        """初始化後處理"""
        if self.upload_timestamp is None:
            self.upload_timestamp = datetime.now()
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


@dataclass
class ShortKeySequence:
    """短檔名序列記錄"""
    id: Optional[int] = None
    key_length: int = 4
    current_sequence: int = 0
    max_possible: int = 0
    exhausted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        """初始化後處理"""
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


@dataclass
class ReservedShortKey:
    """保留短檔名記錄"""
    id: Optional[int] = None
    short_key: str = ""
    reason: str = ""
    created_at: Optional[datetime] = None

    def __post_init__(self):
        """初始化後處理"""
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class FileOperationLog:
    """檔案操作日誌"""
    id: Optional[int] = None
    file_record_id: int = 0
    operation_type: str = ""  # upload, access, delete, update
    operation_details: Optional[Dict[str, Any]] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        """初始化後處理"""
        if self.timestamp is None:
            self.timestamp = datetime.now()
"""
配置管理模組

使用Pydantic進行環境變數驗證和配置管理。
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field, validator
import re
from dotenv import load_dotenv


class Config(BaseModel):
    """應用程式配置類別"""
    
    # Cloudflare R2 配置
    r2_endpoint_url: str = Field(..., description="R2端點URL")
    r2_access_key_id: str = Field(..., description="R2存取金鑰ID")
    r2_secret_access_key: str = Field(..., description="R2秘密存取金鑰")
    r2_bucket_name: str = Field(..., description="R2儲存桶名稱")
    
    # 應用程式配置
    max_concurrent_uploads: int = Field(default=5, ge=1, le=20, description="最大並發上傳數量")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重試次數")
    retry_delay: float = Field(default=1.0, ge=0.1, le=60.0, description="重試延遲時間(秒)")
    
    # 檔案處理配置
    supported_formats: List[str] = Field(
        default=["jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"],
        description="支援的圖片格式"
    )
    
    # 圖片壓縮配置
    enable_compression: bool = Field(default=True, description="是否啟用壓縮")
    compression_quality: int = Field(default=85, ge=1, le=100, description="壓縮品質")
    max_image_size: int = Field(default=2048, ge=128, le=8192, description="最大圖片尺寸")
    
    # 日誌配置
    log_level: str = Field(default="INFO", description="日誌等級")
    log_file: str = Field(default="logs/uploadr2.log", description="日誌檔案路徑")
    
    # 進度顯示配置
    show_progress: bool = Field(default=True, description="是否顯示進度")
    progress_update_interval: int = Field(default=1, ge=1, le=10, description="進度更新間隔(秒)")
    
    # 上傳配置
    filename_format: str = Field(default="original", description="檔案名稱格式")
    custom_prefix: str = Field(default="img_", description="自定義前綴")
    
    # 安全配置
    max_file_size_mb: int = Field(default=50, ge=1, le=500, description="最大檔案大小(MB)")
    validate_file_type: bool = Field(default=True, description="是否驗證檔案類型")
    
    # 防重複上傳配置
    check_duplicate: bool = Field(default=True, description="是否檢查重複檔案")
    hash_algorithm: str = Field(default="sha512", description="雜湊演算法")
    
    # 自定義域名配置
    custom_domain: Optional[str] = Field(default=None, description="自定義域名，用於生成完整的圖片URL")
    
    class Config:
        """Pydantic配置"""
        env_prefix = ""
        case_sensitive = False
        
    @validator('log_level')
    def validate_log_level(cls, v):
        """驗證日誌等級"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level must be one of {valid_levels}')
        return v.upper()
    
    @validator('filename_format')
    def validate_filename_format(cls, v):
        """驗證檔案名稱格式"""
        valid_formats = ['original', 'timestamp', 'uuid', 'custom']
        if v not in valid_formats:
            raise ValueError(f'filename_format must be one of {valid_formats}')
        return v
    
    @validator('supported_formats')
    def validate_supported_formats(cls, v):
        """驗證支援的檔案格式"""
        if isinstance(v, str):
            # 如果是字串，則以逗號分隔
            v = [fmt.strip().lower() for fmt in v.split(',')]
        return [fmt.lower() for fmt in v]
    
    @validator('custom_domain')
    def validate_custom_domain(cls, v):
        """驗證自定義域名格式"""
        if v is None or v.strip() == "":
            return None
        
        # 移除末尾的斜線
        v = v.rstrip('/')
        
        # 驗證URL格式
        url_pattern = re.compile(
            r'^https?://'  # http:// 或 https://
            r'(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)*'  # 域名
            r'[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?'  # 最後一級域名
            r'(?::\d+)?'  # 可選的端口號
            r'$', re.IGNORECASE
        )
        
        if not url_pattern.match(v):
            raise ValueError('custom_domain must be a valid URL (e.g., https://i.valorvie.net)')
        
        return v
    
    @property
    def max_file_size_bytes(self) -> int:
        """取得最大檔案大小（位元組）"""
        return self.max_file_size_mb * 1024 * 1024
    
    def ensure_directories(self) -> None:
        """確保所需的目錄存在"""
        directories = [
            Path(self.log_file).parent,
            Path("images/original"),
            Path("images/transfer"),
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


def load_config(env_file: Optional[str] = None) -> Config:
    """
    載入配置
    
    Args:
        env_file: 環境變數檔案路徑，預設為.env
        
    Returns:
        Config: 配置物件
    """
    # 載入環境變數
    if env_file is None:
        env_file = ".env"
    
    if os.path.exists(env_file):
        load_dotenv(env_file)
    
    # 建立配置物件
    config = Config(
        r2_endpoint_url=os.getenv("R2_ENDPOINT_URL", ""),
        r2_access_key_id=os.getenv("R2_ACCESS_KEY_ID", ""),
        r2_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", ""),
        r2_bucket_name=os.getenv("R2_BUCKET_NAME", ""),
        max_concurrent_uploads=int(os.getenv("MAX_CONCURRENT_UPLOADS", "5")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        retry_delay=float(os.getenv("RETRY_DELAY", "1.0")),
        supported_formats=[fmt.strip().lower() for fmt in os.getenv("SUPPORTED_FORMATS", "jpg,jpeg,png,gif,bmp,tiff,webp").split(',')],
        enable_compression=os.getenv("ENABLE_COMPRESSION", "true").lower() == "true",
        compression_quality=int(os.getenv("COMPRESSION_QUALITY", "85")),
        max_image_size=int(os.getenv("MAX_IMAGE_SIZE", "2048")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_file=os.getenv("LOG_FILE", "logs/uploadr2.log"),
        show_progress=os.getenv("SHOW_PROGRESS", "true").lower() == "true",
        progress_update_interval=int(os.getenv("PROGRESS_UPDATE_INTERVAL", "1")),
        filename_format=os.getenv("FILENAME_FORMAT", "original"),
        custom_prefix=os.getenv("CUSTOM_PREFIX", "img_"),
        max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "50")),
        validate_file_type=os.getenv("VALIDATE_FILE_TYPE", "true").lower() == "true",
        check_duplicate=os.getenv("CHECK_DUPLICATE", "true").lower() == "true",
        hash_algorithm=os.getenv("HASH_ALGORITHM", "sha512"),
        custom_domain=os.getenv("CUSTOM_DOMAIN"),
    )
    
    # 確保必要的目錄存在
    config.ensure_directories()
    
    return config
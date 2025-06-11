"""
日誌設定模組

提供統一的日誌配置和管理功能。
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "uploadr2",
    log_file: str = "logs/uploadr2.log",
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    設定日誌記錄器
    
    Args:
        name: 記錄器名稱
        log_file: 日誌檔案路徑
        log_level: 日誌等級
        max_bytes: 日誌檔案最大大小
        backup_count: 備份檔案數量
        
    Returns:
        logging.Logger: 配置好的記錄器
    """
    # 建立記錄器
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 避免重複添加處理器
    if logger.handlers:
        return logger
    
    # 確保日誌目錄存在
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 建立格式器
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 檔案處理器（輪轉日誌）
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 控制台處理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    取得記錄器實例
    
    Args:
        name: 記錄器名稱，預設為uploadr2
        
    Returns:
        logging.Logger: 記錄器實例
    """
    if name is None:
        name = "uploadr2"
    return logging.getLogger(name)
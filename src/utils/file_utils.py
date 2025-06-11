"""
檔案工具模組

提供檔案處理相關的輔助功能。
"""

import os
import mimetypes
from pathlib import Path
from typing import List, Optional, Set
from ..config import Config


class FileUtils:
    """檔案工具類別"""
    
    @staticmethod
    def is_image_file(file_path: Path, supported_formats: Optional[List[str]] = None) -> bool:
        """
        檢查檔案是否為支援的圖片格式
        
        Args:
            file_path: 檔案路徑
            supported_formats: 支援的格式列表
            
        Returns:
            bool: 是否為支援的圖片檔案
        """
        if supported_formats is None:
            supported_formats = ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"]
        
        # 檢查副檔名
        extension = file_path.suffix.lower().lstrip('.')
        if extension not in supported_formats:
            return False
        
        # 檢查MIME類型
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and not mime_type.startswith('image/'):
            return False
            
        return True
    
    @staticmethod
    def get_file_size(file_path: Path) -> int:
        """
        取得檔案大小（位元組）
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            int: 檔案大小
        """
        return file_path.stat().st_size
    
    @staticmethod
    def validate_file(file_path: Path, config: Config) -> tuple[bool, str]:
        """
        驗證檔案是否符合要求
        
        Args:
            file_path: 檔案路徑
            config: 配置物件
            
        Returns:
            tuple[bool, str]: (是否有效, 錯誤訊息)
        """
        # 檢查檔案是否存在
        if not file_path.exists():
            return False, f"檔案不存在: {file_path}"
        
        # 檢查是否為檔案
        if not file_path.is_file():
            return False, f"不是檔案: {file_path}"
        
        # 檢查檔案類型
        if config.validate_file_type and not FileUtils.is_image_file(file_path, config.supported_formats):
            return False, f"不支援的檔案格式: {file_path.suffix}"
        
        # 檢查檔案大小
        file_size = FileUtils.get_file_size(file_path)
        if file_size > config.max_file_size_bytes:
            size_mb = file_size / 1024 / 1024
            return False, f"檔案太大: {size_mb:.2f}MB (最大: {config.max_file_size_mb}MB)"
        
        return True, ""
    
    @staticmethod
    def scan_images(directory: Path, config: Config) -> List[Path]:
        """
        掃描目錄中的圖片檔案
        
        Args:
            directory: 目錄路徑
            config: 配置物件
            
        Returns:
            List[Path]: 有效的圖片檔案路徑列表
        """
        image_files = []
        
        if not directory.exists() or not directory.is_dir():
            return image_files
        
        # 遞迴掃描目錄
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                is_valid, _ = FileUtils.validate_file(file_path, config)
                if is_valid:
                    image_files.append(file_path)
        
        return sorted(image_files)
    
    @staticmethod
    def create_directory(directory: Path) -> None:
        """
        建立目錄（如果不存在）
        
        Args:
            directory: 目錄路徑
        """
        directory.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def get_unique_filename(file_path: Path) -> Path:
        """
        產生唯一的檔案名稱（避免覆蓋）
        
        Args:
            file_path: 原始檔案路徑
            
        Returns:
            Path: 唯一的檔案路徑
        """
        if not file_path.exists():
            return file_path
        
        base = file_path.stem
        suffix = file_path.suffix
        parent = file_path.parent
        counter = 1
        
        while True:
            new_name = f"{base}_{counter}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1
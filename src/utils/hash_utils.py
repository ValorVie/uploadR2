"""
檔案雜湊工具模組

提供檔案雜湊計算和基於雜湊的UUID生成功能。
"""

import hashlib
import uuid
from pathlib import Path
from typing import Optional

from .logger import get_logger


class HashUtils:
    """檔案雜湊工具類別"""
    
    @staticmethod
    def calculate_file_hash(file_path: Path, algorithm: str = "sha512") -> Optional[str]:
        """
        計算檔案雜湊值
        
        Args:
            file_path: 檔案路徑
            algorithm: 雜湊演算法 (預設: sha512)
            
        Returns:
            Optional[str]: 雜湊值（十六進制字串），失敗時返回None
        """
        logger = get_logger(__name__)
        
        try:
            # 建立雜湊物件
            hash_obj = hashlib.new(algorithm)
            
            # 分塊讀取檔案以節省記憶體
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):  # 8KB chunks
                    hash_obj.update(chunk)
            
            hash_value = hash_obj.hexdigest()
            logger.debug(f"檔案雜湊計算完成: {file_path.name} -> {hash_value[:16]}...")
            return hash_value
            
        except Exception as e:
            logger.error(f"計算檔案雜湊失敗: {file_path} - {str(e)}")
            return None
    
    @staticmethod
    def hash_to_uuid(hash_value: str) -> str:
        """
        將雜湊值轉換為UUID格式
        
        Args:
            hash_value: 雜湊值（十六進制字串）
            
        Returns:
            str: UUID字串
        """
        # 取雜湊值的前32個字符（128位）
        if len(hash_value) < 32:
            # 如果雜湊值太短，則用0補齊
            hash_value = hash_value.ljust(32, '0')
        else:
            hash_value = hash_value[:32]
        
        # 轉換為UUID格式 (8-4-4-4-12)
        uuid_str = f"{hash_value[:8]}-{hash_value[8:12]}-{hash_value[12:16]}-{hash_value[16:20]}-{hash_value[20:32]}"
        
        return uuid_str
    
    @staticmethod
    def generate_content_based_filename(file_path: Path, algorithm: str = "sha512") -> Optional[str]:
        """
        基於檔案內容生成檔案名稱
        
        Args:
            file_path: 檔案路徑
            algorithm: 雜湊演算法 (預設: sha512)
            
        Returns:
            Optional[str]: 新檔案名稱，失敗時返回None
        """
        # 計算檔案雜湊
        hash_value = HashUtils.calculate_file_hash(file_path, algorithm)
        if hash_value is None:
            return None
        
        # 轉換為UUID
        content_uuid = HashUtils.hash_to_uuid(hash_value)
        
        # 保持原始副檔名
        extension = file_path.suffix.lower()
        
        return f"{content_uuid}{extension}"
    
    @staticmethod
    def generate_filename_with_original_name(file_path: Path, algorithm: str = "sha512") -> Optional[str]:
        """
        基於檔案內容生成包含原始檔名的檔案名稱
        格式: {原始檔名}_{uuid}.{副檔名}
        
        Args:
            file_path: 檔案路徑
            algorithm: 雜湊演算法 (預設: sha512)
            
        Returns:
            Optional[str]: 新檔案名稱，失敗時返回None
        """
        # 計算檔案雜湊
        hash_value = HashUtils.calculate_file_hash(file_path, algorithm)
        if hash_value is None:
            return None
        
        # 轉換為UUID
        content_uuid = HashUtils.hash_to_uuid(hash_value)
        
        # 獲取原始檔名（不含副檔名）並清理特殊字元
        original_name = HashUtils._sanitize_filename(file_path.stem)
        
        # 保持原始副檔名
        extension = file_path.suffix.lower()
        
        return f"{original_name}_{content_uuid}{extension}"
    
    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        清理檔案名稱中的特殊字元
        
        Args:
            filename: 原始檔案名稱
            
        Returns:
            str: 清理後的檔案名稱
        """
        import re
        
        # 移除或替換檔案系統不安全的字元
        # 保留中文字元（包括CJK統一漢字）、英文字母、數字、連字號和底線
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # 替換多個連續的空格和特殊空白字元為單個底線
        sanitized = re.sub(r'\s+', '_', sanitized)
        
        # 移除其他控制字元，但保留中文字元
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
        
        # 移除開頭和結尾的空格、點號和底線
        sanitized = sanitized.strip(' ._')
        
        # 限制檔名長度，避免檔案系統限制問題
        if len(sanitized.encode('utf-8')) > 200:  # 使用UTF-8位元組長度
            # 如果太長，截取前部分
            sanitized = sanitized[:100]  # 保守截取
            sanitized = sanitized.rstrip('._')
        
        # 如果清理後為空，使用預設名稱
        if not sanitized:
            sanitized = "file"
        
        return sanitized
    
    @staticmethod
    def get_file_metadata(file_path: Path, algorithm: str = "sha512") -> dict:
        """
        取得檔案中繼資料
        
        Args:
            file_path: 檔案路徑
            algorithm: 雜湊演算法 (預設: sha512)
            
        Returns:
            dict: 檔案中繼資料
        """
        try:
            stat = file_path.stat()
            hash_value = HashUtils.calculate_file_hash(file_path, algorithm)
            
            metadata = {
                "original_name": file_path.name,
                "file_size": stat.st_size,
                "modified_time": stat.st_mtime,
                f"{algorithm}_hash": hash_value,
                "content_uuid": HashUtils.hash_to_uuid(hash_value) if hash_value else None,
                "algorithm": algorithm,
            }
            
            return metadata
            
        except Exception as e:
            logger = get_logger(__name__)
            logger.error(f"取得檔案中繼資料失敗: {file_path} - {str(e)}")
            return {}
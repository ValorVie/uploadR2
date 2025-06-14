"""
短檔名生成器

實現加密安全的短檔名生成算法，防止猜測且維持最短長度。
"""

import secrets
import string
import threading
from typing import Tuple, TYPE_CHECKING
import sqlite3

from .exceptions import ShortKeyExhaustedError, ShortKeyCollisionError
from ..utils.logger import get_logger

if TYPE_CHECKING:
    from .database_manager import DatabaseManager


class ShortKeyGenerator:
    """短檔名生成器"""
    
    # 字符集：數字 + 小寫字母 + 大寫字母 (62個字符)
    CHARSET = string.digits + string.ascii_lowercase + string.ascii_uppercase
    SALT_LENGTH = 16
    
    def __init__(self, db_manager: 'DatabaseManager'):
        """
        初始化短檔名生成器
        
        Args:
            db_manager: 資料庫管理器實例
        """
        self.db_manager = db_manager
        self._lock = threading.RLock()
        self.logger = get_logger(__name__)
    
    def generate_short_key(self) -> Tuple[str, int, str]:
        """
        生成短檔名
        
        Returns:
            Tuple[str, int, str]: (短檔名, 長度, 使用的鹽值)
            
        Raises:
            ShortKeyExhaustedError: 當所有長度都已耗盡時
            ShortKeyCollisionError: 當無法生成唯一短檔名時
        """
        with self._lock:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # 獲取當前應該使用的長度
                current_length = self._get_current_length(cursor)
                
                # 生成鹽值
                salt = secrets.token_hex(self.SALT_LENGTH)
                
                # 嘗試生成短檔名
                max_attempts = 100
                for attempt in range(max_attempts):
                    short_key = self._generate_key_with_length(current_length, salt, attempt)
                    
                    # 檢查是否被保留
                    if self._is_reserved_key(cursor, short_key):
                        continue
                    
                    # 檢查是否已存在
                    if not self._key_exists(cursor, short_key):
                        # 更新序列
                        self._increment_sequence(cursor, current_length)
                        conn.commit()
                        self.logger.debug(f"生成短檔名成功: {short_key} (長度: {current_length})")
                        return short_key, current_length, salt
                
                # 如果當前長度無法生成，升級到下一個長度
                self.logger.warning(f"長度 {current_length} 生成失敗，嘗試升級到下一長度")
                return self._upgrade_to_next_length(cursor, salt)
    
    def _generate_key_with_length(self, length: int, salt: str, attempt: int) -> str:
        """
        使用指定長度生成鍵
        
        Args:
            length: 鍵長度
            salt: 鹽值
            attempt: 嘗試次數
            
        Returns:
            str: 生成的短檔名
        """
        # 結合鹽值和嘗試次數創建種子
        seed_data = f"{salt}:{attempt}:{secrets.token_hex(8)}"
        
        # 使用加密安全的隨機生成
        result = ""
        for i in range(length):
            # 為每個位置生成獨立的隨機索引
            # 結合位置資訊增加隨機性
            position_seed = f"{seed_data}:{i}"
            random_bytes = secrets.token_bytes(4)
            
            # 使用種子和隨機位元組計算索引
            seed_hash = hash(position_seed) % (2**32)
            random_int = int.from_bytes(random_bytes, 'big')
            combined = (seed_hash ^ random_int) % len(self.CHARSET)
            
            result += self.CHARSET[combined]
        
        return result
    
    def _get_current_length(self, cursor: sqlite3.Cursor) -> int:
        """
        獲取當前應該使用的長度
        
        Args:
            cursor: 資料庫游標
            
        Returns:
            int: 當前長度
        """
        cursor.execute("""
            SELECT key_length FROM short_key_sequences 
            WHERE NOT exhausted 
            ORDER BY key_length ASC 
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        if row:
            return row[0]
        
        # 如果沒有可用長度，創建新的長度記錄
        return self._create_new_length_sequence(cursor, 4)  # 從4開始
    
    def _calculate_max_possible(self, length: int) -> int:
        """
        計算指定長度的最大可能組合數
        
        Args:
            length: 長度
            
        Returns:
            int: 最大可能組合數（扣除保留份額）
        """
        # 預留一些組合給系統保留字和未來擴展
        total_combinations = len(self.CHARSET) ** length
        reserved_ratio = 0.001  # 預留0.1%
        return int(total_combinations * (1 - reserved_ratio))
    
    def _create_new_length_sequence(self, cursor: sqlite3.Cursor, length: int) -> int:
        """
        創建新的長度序列記錄
        
        Args:
            cursor: 資料庫游標
            length: 新長度
            
        Returns:
            int: 創建的長度值
        """
        max_possible = self._calculate_max_possible(length)
        
        cursor.execute("""
            INSERT INTO short_key_sequences (key_length, current_sequence, max_possible)
            VALUES (?, 0, ?)
        """, (length, max_possible))
        
        self.logger.info(f"創建新的長度序列: {length} (最大組合數: {max_possible})")
        return length
    
    def _is_reserved_key(self, cursor: sqlite3.Cursor, key: str) -> bool:
        """
        檢查是否為保留關鍵字
        
        Args:
            cursor: 資料庫游標
            key: 要檢查的鍵
            
        Returns:
            bool: 是否為保留關鍵字
        """
        cursor.execute("""
            SELECT 1 FROM reserved_short_keys WHERE short_key = ?
        """, (key,))
        
        return cursor.fetchone() is not None
    
    def _key_exists(self, cursor: sqlite3.Cursor, key: str) -> bool:
        """
        檢查短檔名是否已存在
        
        Args:
            cursor: 資料庫游標
            key: 要檢查的鍵
            
        Returns:
            bool: 是否已存在
        """
        cursor.execute("""
            SELECT 1 FROM file_records WHERE short_key = ?
        """, (key,))
        
        return cursor.fetchone() is not None
    
    def _increment_sequence(self, cursor: sqlite3.Cursor, length: int) -> None:
        """
        增加序列計數
        
        Args:
            cursor: 資料庫游標
            length: 長度
        """
        cursor.execute("""
            UPDATE short_key_sequences 
            SET current_sequence = current_sequence + 1
            WHERE key_length = ?
        """, (length,))
    
    def _upgrade_to_next_length(self, cursor: sqlite3.Cursor, salt: str) -> Tuple[str, int, str]:
        """
        升級到下一個長度
        
        Args:
            cursor: 資料庫游標
            salt: 當前鹽值
            
        Returns:
            Tuple[str, int, str]: (短檔名, 長度, 鹽值)
            
        Raises:
            ShortKeyExhaustedError: 當達到最大長度限制時
        """
        # 獲取當前最大長度
        cursor.execute("""
            SELECT MAX(key_length) FROM short_key_sequences
        """)
        
        row = cursor.fetchone()
        current_max_length = row[0] if row and row[0] else 3  # 預設從3開始，下面會升級到4
        
        # 檢查是否達到合理的最大長度限制
        max_allowed_length = 12  # 設定合理的最大長度
        if current_max_length >= max_allowed_length:
            raise ShortKeyExhaustedError(f"已達到最大長度限制: {max_allowed_length}")
        
        # 創建下一個長度的序列
        next_length = current_max_length + 1
        self._create_new_length_sequence(cursor, next_length)
        
        # 使用新長度生成短檔名
        max_attempts = 100
        for attempt in range(max_attempts):
            short_key = self._generate_key_with_length(next_length, salt, attempt)
            
            if not self._is_reserved_key(cursor, short_key) and not self._key_exists(cursor, short_key):
                self._increment_sequence(cursor, next_length)
                self.logger.info(f"升級到長度 {next_length}，生成短檔名: {short_key}")
                return short_key, next_length, salt
        
        raise ShortKeyCollisionError(f"無法在長度 {next_length} 生成唯一短檔名")
    
    def get_statistics(self) -> dict:
        """
        獲取短檔名生成統計資訊
        
        Returns:
            dict: 統計資訊
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 獲取所有長度的統計
            cursor.execute("""
                SELECT 
                    key_length,
                    current_sequence,
                    max_possible,
                    exhausted,
                    ROUND(CAST(current_sequence AS FLOAT) / max_possible * 100, 2) as usage_percent
                FROM short_key_sequences
                ORDER BY key_length
            """)
            
            sequences = []
            for row in cursor.fetchall():
                sequences.append({
                    "length": row[0],
                    "current": row[1],
                    "max_possible": row[2],
                    "exhausted": bool(row[3]),
                    "usage_percent": row[4]
                })
            
            # 獲取保留關鍵字數量
            cursor.execute("SELECT COUNT(*) FROM reserved_short_keys")
            reserved_count = cursor.fetchone()[0]
            
            # 獲取已使用的短檔名數量
            cursor.execute("SELECT COUNT(*) FROM file_records WHERE short_key IS NOT NULL")
            used_count = cursor.fetchone()[0]
            
            return {
                "sequences": sequences,
                "reserved_keys_count": reserved_count,
                "used_short_keys_count": used_count,
                "charset_size": len(self.CHARSET),
                "charset": self.CHARSET
            }
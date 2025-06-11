"""
進度追蹤器模組

提供處理和上傳進度的追蹤功能。
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from tqdm import tqdm

from .utils.logger import get_logger


@dataclass
class ProgressStats:
    """進度統計資訊"""
    total_files: int = 0
    processed_files: int = 0
    uploaded_files: int = 0
    failed_files: int = 0
    skipped_files: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_bytes: int = 0
    processed_bytes: int = 0
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_files == 0:
            return 0.0
        return (self.uploaded_files / self.total_files) * 100
    
    @property
    def elapsed_time(self) -> float:
        """已用時間（秒）"""
        if self.start_time is None:
            return 0.0
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()
    
    @property
    def estimated_time_remaining(self) -> float:
        """預估剩餘時間（秒）"""
        if self.processed_files == 0 or self.elapsed_time == 0:
            return 0.0
        
        remaining_files = self.total_files - self.processed_files
        if remaining_files <= 0:
            return 0.0
        
        avg_time_per_file = self.elapsed_time / self.processed_files
        return avg_time_per_file * remaining_files


@dataclass
class FileProgress:
    """單個檔案的進度資訊"""
    file_path: Path
    status: str = "pending"  # pending, processing, uploading, completed, failed, skipped, duplicate
    error_message: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    file_size: int = 0
    new_filename: str = ""
    upload_url: str = ""


class ProgressTracker:
    """進度追蹤器"""
    
    def __init__(self, show_progress: bool = True, update_interval: int = 1):
        """
        初始化進度追蹤器
        
        Args:
            show_progress: 是否顯示進度條
            update_interval: 更新間隔（秒）
        """
        self.show_progress = show_progress
        self.update_interval = update_interval
        self.logger = get_logger(__name__)
        
        self.stats = ProgressStats()
        self.file_progress: Dict[str, FileProgress] = {}
        self.progress_bar: Optional[tqdm] = None
        self._last_update = 0.0
        
        # 記錄重複檔案的原始檔名清單
        self.duplicate_files: List[str] = []
    
    def initialize(self, files: List[Path]) -> None:
        """
        初始化追蹤器
        
        Args:
            files: 要處理的檔案清單
        """
        self.stats.total_files = len(files)
        self.stats.start_time = datetime.now()
        self.stats.total_bytes = sum(f.stat().st_size for f in files if f.exists())
        
        # 初始化檔案進度
        for file_path in files:
            file_key = str(file_path)
            self.file_progress[file_key] = FileProgress(
                file_path=file_path,
                file_size=file_path.stat().st_size if file_path.exists() else 0
            )
        
        # 設定進度條
        if self.show_progress:
            self.progress_bar = tqdm(
                total=self.stats.total_files,
                desc="處理進度",
                unit="檔案",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
            )
        
        self.logger.info(f"開始處理 {self.stats.total_files} 個檔案")
    
    def start_file_processing(self, file_path: Path) -> None:
        """
        開始處理檔案
        
        Args:
            file_path: 檔案路徑
        """
        file_key = str(file_path)
        if file_key in self.file_progress:
            progress = self.file_progress[file_key]
            progress.status = "processing"
            progress.start_time = datetime.now()
    
    def start_file_uploading(self, file_path: Path) -> None:
        """
        開始上傳檔案
        
        Args:
            file_path: 檔案路徑
        """
        file_key = str(file_path)
        if file_key in self.file_progress:
            self.file_progress[file_key].status = "uploading"
    
    def complete_file(self, file_path: Path, new_filename: str = "", upload_url: str = "") -> None:
        """
        完成檔案處理
        
        Args:
            file_path: 檔案路徑
            new_filename: 新檔案名稱
            upload_url: 上傳URL
        """
        file_key = str(file_path)
        if file_key in self.file_progress:
            progress = self.file_progress[file_key]
            progress.status = "completed"
            progress.end_time = datetime.now()
            progress.new_filename = new_filename
            progress.upload_url = upload_url
            
            self.stats.processed_files += 1
            self.stats.uploaded_files += 1
            self.stats.processed_bytes += progress.file_size
            
            self._update_progress()
    
    def fail_file(self, file_path: Path, error_message: str) -> None:
        """
        標記檔案處理失敗
        
        Args:
            file_path: 檔案路徑
            error_message: 錯誤訊息
        """
        file_key = str(file_path)
        if file_key in self.file_progress:
            progress = self.file_progress[file_key]
            progress.status = "failed"
            progress.end_time = datetime.now()
            progress.error_message = error_message
            
            self.stats.processed_files += 1
            self.stats.failed_files += 1
            
            self._update_progress()
            self.logger.error(f"檔案處理失敗: {file_path} - {error_message}")
    
    def skip_file(self, file_path: Path, reason: str) -> None:
        """
        跳過檔案
        
        Args:
            file_path: 檔案路徑
            reason: 跳過原因
        """
        file_key = str(file_path)
        if file_key in self.file_progress:
            progress = self.file_progress[file_key]
            progress.status = "skipped"
            progress.end_time = datetime.now()
            progress.error_message = reason
            
            self.stats.processed_files += 1
            self.stats.skipped_files += 1
            
            self._update_progress()
            self.logger.info(f"跳過檔案: {file_path} - {reason}")
    
    def duplicate_file(self, file_path: Path, upload_url: str = "") -> None:
        """
        標記檔案為重複（已存在）
        
        Args:
            file_path: 檔案路徑
            upload_url: 現有檔案的URL
        """
        file_key = str(file_path)
        if file_key in self.file_progress:
            progress = self.file_progress[file_key]
            progress.status = "duplicate"
            progress.end_time = datetime.now()
            progress.upload_url = upload_url
            progress.error_message = "檔案已存在，跳過上傳"
            
            # 記錄重複檔案的原始檔名
            self.duplicate_files.append(file_path.name)
            
            self.stats.processed_files += 1
            self.stats.uploaded_files += 1  # 算作成功，因為檔案已經存在
            self.stats.processed_bytes += progress.file_size
            
            self._update_progress()
            self.logger.info(f"檔案已存在: {file_path}")
    
    def _update_progress(self) -> None:
        """更新進度顯示"""
        current_time = time.time()
        
        # 檢查是否需要更新
        if current_time - self._last_update < self.update_interval:
            return
        
        self._last_update = current_time
        
        if self.progress_bar:
            self.progress_bar.n = self.stats.processed_files
            
            # 更新描述
            success_rate = self.stats.success_rate
            desc = f"處理進度 (成功率: {success_rate:.1f}%)"
            self.progress_bar.set_description(desc)
            
            self.progress_bar.refresh()
    
    def finalize(self) -> None:
        """完成追蹤"""
        self.stats.end_time = datetime.now()
        
        if self.progress_bar:
            self.progress_bar.close()
        
        # 記錄最終統計
        self.logger.info(f"處理完成！統計資訊:")
        self.logger.info(f"  總檔案數: {self.stats.total_files}")
        self.logger.info(f"  成功上傳: {self.stats.uploaded_files}")
        self.logger.info(f"  處理失敗: {self.stats.failed_files}")
        self.logger.info(f"  跳過檔案: {self.stats.skipped_files}")
        self.logger.info(f"  成功率: {self.stats.success_rate:.2f}%")
        self.logger.info(f"  總用時: {self.stats.elapsed_time:.2f} 秒")
    
    def get_failed_files(self) -> List[FileProgress]:
        """
        取得失敗的檔案清單
        
        Returns:
            List[FileProgress]: 失敗的檔案進度清單
        """
        return [
            progress for progress in self.file_progress.values()
            if progress.status == "failed"
        ]
    
    def get_duplicate_files(self) -> List[str]:
        """
        取得重複檔案的原始檔名清單
        
        Returns:
            List[str]: 重複檔案的原始檔名清單
        """
        return self.duplicate_files.copy()
    
    def get_uploaded_files_with_urls(self) -> List[tuple]:
        """
        取得成功上傳檔案的原始檔名與URL對應清單
        
        Returns:
            List[tuple]: (原始檔名, URL) 的列表
        """
        uploaded_files = []
        for progress in self.file_progress.values():
            if progress.status in ["completed", "duplicate"] and progress.upload_url:
                uploaded_files.append((progress.file_path.name, progress.upload_url))
        return uploaded_files
    
    def get_summary(self) -> Dict:
        """
        取得處理摘要
        
        Returns:
            Dict: 處理摘要資訊
        """
        return {
            "total_files": self.stats.total_files,
            "processed_files": self.stats.processed_files,
            "uploaded_files": self.stats.uploaded_files,
            "failed_files": self.stats.failed_files,
            "skipped_files": self.stats.skipped_files,
            "success_rate": self.stats.success_rate,
            "elapsed_time": self.stats.elapsed_time,
            "total_bytes": self.stats.total_bytes,
            "processed_bytes": self.stats.processed_bytes,
            "start_time": self.stats.start_time.isoformat() if self.stats.start_time else None,
            "end_time": self.stats.end_time.isoformat() if self.stats.end_time else None,
        }
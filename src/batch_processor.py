"""
批量處理器模組

協調整個圖片處理和上傳流程。
"""

import asyncio
import shutil
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from .config import Config
from .progress_tracker import ProgressTracker
from .r2_uploader import R2Uploader
from .utils.file_utils import FileUtils
from .utils.image_processor import ImageProcessor
from .utils.hash_utils import HashUtils
from .utils.logger import get_logger


class BatchProcessorError(Exception):
    """批量處理器錯誤"""
    pass


class BatchProcessor:
    """批量處理器"""
    
    def __init__(self, config: Config):
        """
        初始化批量處理器
        
        Args:
            config: 配置物件
        """
        self.config = config
        self.logger = get_logger(__name__)
        
        # 初始化組件
        self.image_processor = ImageProcessor(config)
        self.progress_tracker = ProgressTracker(
            show_progress=config.show_progress,
            update_interval=config.progress_update_interval
        )
        
        # 路徑設定
        self.original_dir = Path("images/original")
        self.transfer_dir = Path("images/transfer")
        
        # 確保目錄存在
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """確保所需目錄存在"""
        self.original_dir.mkdir(parents=True, exist_ok=True)
        self.transfer_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("目錄檢查完成")
    
    def scan_images(self) -> List[Path]:
        """
        掃描原始圖片目錄
        
        Returns:
            List[Path]: 找到的圖片檔案清單
        """
        self.logger.info(f"開始掃描圖片目錄: {self.original_dir}")
        
        images = FileUtils.scan_images(self.original_dir, self.config)
        
        self.logger.info(f"找到 {len(images)} 個有效圖片檔案")
        
        if not images:
            self.logger.warning("未找到任何圖片檔案，請確認圖片已放置在images/original目錄中")
        
        return images
    
    def _generate_new_filename(self, original_path: Path) -> str:
        """
        產生新的檔案名稱
        
        Args:
            original_path: 原始檔案路徑
            
        Returns:
            str: 新的檔案名稱
        """
        if self.config.filename_format == "uuid":
            # 使用基於內容的UUID命名
            content_filename = HashUtils.generate_content_based_filename(
                original_path,
                self.config.hash_algorithm
            )
            if content_filename:
                return content_filename
            else:
                # 如果雜湊計算失敗，使用隨機UUID
                extension = original_path.suffix.lower()
                return f"{uuid.uuid4().hex}{extension}"
        else:
            return self.image_processor.generate_filename(original_path)
    
    async def process_image(self, original_path: Path) -> Tuple[bool, Optional[Path], str]:
        """
        處理單個圖片
        
        Args:
            original_path: 原始檔案路徑
            
        Returns:
            Tuple[bool, Optional[Path], str]: (是否成功, 處理後路徑, 錯誤訊息)
        """
        try:
            # 驗證檔案
            is_valid, error_message = FileUtils.validate_file(original_path, self.config)
            if not is_valid:
                return False, None, error_message
            
            # 產生新檔案名稱
            new_filename = self._generate_new_filename(original_path)
            transfer_path = self.transfer_dir / new_filename
            
            # 確保檔案名稱唯一
            transfer_path = FileUtils.get_unique_filename(transfer_path)
            
            # 處理圖片（壓縮、調整大小等）
            success = await asyncio.get_event_loop().run_in_executor(
                None,
                self.image_processor.process_image,
                original_path,
                transfer_path
            )
            
            if not success:
                return False, None, "圖片處理失敗"
            
            self.logger.debug(f"圖片處理完成: {original_path} -> {transfer_path}")
            return True, transfer_path, ""
            
        except Exception as e:
            error_message = f"處理圖片時發生錯誤: {str(e)}"
            self.logger.error(error_message)
            return False, None, error_message
    
    async def process_and_upload_batch(
        self, 
        image_files: List[Path]
    ) -> None:
        """
        批量處理和上傳圖片
        
        Args:
            image_files: 圖片檔案清單
        """
        if not image_files:
            self.logger.warning("沒有圖片需要處理")
            return
        
        # 初始化進度追蹤
        self.progress_tracker.initialize(image_files)
        
        try:
            # 初始化R2上傳器
            async with R2Uploader(self.config) as uploader:
                # 測試R2連接
                if not await uploader.test_connection():
                    raise BatchProcessorError("無法連接到Cloudflare R2，請檢查配置")
                
                # 處理每個檔案
                upload_tasks = []
                semaphore = asyncio.Semaphore(self.config.max_concurrent_uploads)
                
                for original_path in image_files:
                    task = self._process_single_file(
                        original_path, uploader, semaphore
                    )
                    upload_tasks.append(task)
                
                # 並發執行所有任務
                await asyncio.gather(*upload_tasks, return_exceptions=True)
        
        except Exception as e:
            self.logger.error(f"批量處理失敗: {str(e)}")
            raise BatchProcessorError(f"批量處理失敗: {str(e)}")
        
        finally:
            # 完成進度追蹤
            self.progress_tracker.finalize()
    
    async def _process_single_file(
        self, 
        original_path: Path, 
        uploader: R2Uploader,
        semaphore: asyncio.Semaphore
    ) -> None:
        """
        處理單個檔案（處理 + 上傳）
        
        Args:
            original_path: 原始檔案路徑
            uploader: R2上傳器
            semaphore: 並發控制信號量
        """
        async with semaphore:
            try:
                # 開始處理
                self.progress_tracker.start_file_processing(original_path)
                
                # 處理圖片
                success, transfer_path, error_message = await self.process_image(original_path)
                
                if not success:
                    self.progress_tracker.fail_file(original_path, error_message)
                    return
                
                # 開始上傳
                self.progress_tracker.start_file_uploading(original_path)
                
                # 上傳到R2（使用基於內容的檔案名稱和重複檢查）
                upload_success, upload_result, is_duplicate = await uploader.upload_file(
                    transfer_path,
                    object_key=None,  # 讓上傳器自動生成基於內容的金鑰
                    check_duplicate=self.config.check_duplicate
                )
                
                if upload_success:
                    if is_duplicate:
                        # 檔案已存在，標記為重複
                        self.progress_tracker.duplicate_file(original_path, upload_result)
                    else:
                        # 上傳成功
                        self.progress_tracker.complete_file(
                            original_path,
                            transfer_path.name,
                            upload_result
                        )
                    
                    # 清理處理後的檔案（可選）
                    if self.config.filename_format != "original":
                        try:
                            transfer_path.unlink()
                            self.logger.debug(f"已清理暫存檔案: {transfer_path}")
                        except Exception as e:
                            self.logger.warning(f"清理暫存檔案失敗: {transfer_path} - {str(e)}")
                else:
                    # 上傳失敗
                    self.progress_tracker.fail_file(original_path, upload_result)
                    
                    # 清理失敗的檔案
                    if transfer_path and transfer_path.exists():
                        try:
                            transfer_path.unlink()
                        except Exception:
                            pass
                            
            except Exception as e:
                error_message = f"處理檔案時發生未預期錯誤: {str(e)}"
                self.progress_tracker.fail_file(original_path, error_message)
    
    def copy_images_to_transfer(self, image_files: List[Path]) -> List[Tuple[Path, Path]]:
        """
        將圖片複製到transfer目錄（同步版本）
        
        Args:
            image_files: 圖片檔案清單
            
        Returns:
            List[Tuple[Path, Path]]: (原始路徑, 複製後路徑) 的列表
        """
        copied_files = []
        
        for original_path in image_files:
            try:
                # 驗證檔案
                is_valid, error_message = FileUtils.validate_file(original_path, self.config)
                if not is_valid:
                    self.logger.warning(f"跳過無效檔案: {original_path} - {error_message}")
                    continue
                
                # 產生新檔案名稱
                new_filename = self._generate_new_filename(original_path)
                transfer_path = self.transfer_dir / new_filename
                
                # 確保檔案名稱唯一
                transfer_path = FileUtils.get_unique_filename(transfer_path)
                
                # 複製檔案
                shutil.copy2(original_path, transfer_path)
                copied_files.append((original_path, transfer_path))
                
                self.logger.debug(f"檔案複製完成: {original_path} -> {transfer_path}")
                
            except Exception as e:
                self.logger.error(f"複製檔案失敗: {original_path} - {str(e)}")
        
        self.logger.info(f"共複製 {len(copied_files)} 個檔案到transfer目錄")
        return copied_files
    
    def get_processing_summary(self) -> dict:
        """
        取得處理摘要
        
        Returns:
            dict: 處理摘要資訊
        """
        return self.progress_tracker.get_summary()
    
    def get_failed_files(self) -> List:
        """
        取得失敗的檔案清單
        
        Returns:
            List: 失敗的檔案進度清單
        """
        return self.progress_tracker.get_failed_files()
    
    def cleanup_transfer_directory(self) -> None:
        """清理transfer目錄"""
        try:
            if self.transfer_dir.exists():
                for file_path in self.transfer_dir.iterdir():
                    if file_path.is_file():
                        file_path.unlink()
                        
                self.logger.info("transfer目錄清理完成")
        except Exception as e:
            self.logger.error(f"清理transfer目錄失敗: {str(e)}")
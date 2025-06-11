"""
Cloudflare R2上傳器模組

使用boto3 S3 API連接Cloudflare R2，支援異步批量上傳。
"""

import asyncio
import mimetypes
from pathlib import Path
from typing import List, Optional, Tuple
import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, NoCredentialsError
import aiofiles

from .config import Config
from .utils.logger import get_logger
from .utils.hash_utils import HashUtils


class R2UploadError(Exception):
    """R2上傳錯誤"""
    pass


class R2Uploader:
    """Cloudflare R2上傳器"""
    
    def __init__(self, config: Config):
        """
        初始化R2上傳器
        
        Args:
            config: 配置物件
        """
        self.config = config
        self.logger = get_logger(__name__)
        self._client: Optional[boto3.client] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
    
    def _initialize_client(self) -> None:
        """初始化S3客戶端"""
        try:
            # 設定boto3配置
            boto_config = BotoConfig(
                region_name='auto',
                retries={
                    'max_attempts': self.config.max_retries,
                    'mode': 'adaptive'
                },
                max_pool_connections=self.config.max_concurrent_uploads * 2
            )
            
            # 建立S3客戶端
            self._client = boto3.client(
                's3',
                endpoint_url=self.config.r2_endpoint_url,
                aws_access_key_id=self.config.r2_access_key_id,
                aws_secret_access_key=self.config.r2_secret_access_key,
                config=boto_config
            )
            
            # 初始化信號量（控制並發數量）
            self._semaphore = asyncio.Semaphore(self.config.max_concurrent_uploads)
            
            self.logger.info("R2客戶端初始化成功")
            
        except NoCredentialsError:
            raise R2UploadError("R2憑證配置錯誤，請檢查存取金鑰設定")
        except Exception as e:
            raise R2UploadError(f"R2客戶端初始化失敗: {str(e)}")
    
    async def test_connection(self) -> bool:
        """
        測試R2連接
        
        Returns:
            bool: 連接是否成功
        """
        if self._client is None:
            self._initialize_client()
        
        try:
            # 嘗試列出儲存桶
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.head_bucket(Bucket=self.config.r2_bucket_name)
            )
            self.logger.info("R2連接測試成功")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                self.logger.error(f"儲存桶不存在: {self.config.r2_bucket_name}")
            elif error_code == '403':
                self.logger.error("存取被拒絕，請檢查憑證權限")
            else:
                self.logger.error(f"R2連接測試失敗: {e}")
            return False
        except Exception as e:
            self.logger.error(f"R2連接測試失敗: {str(e)}")
            return False
    
    def _get_content_type(self, file_path: Path) -> str:
        """
        取得檔案的Content-Type
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            str: Content-Type
        """
        content_type, _ = mimetypes.guess_type(str(file_path))
        return content_type or 'application/octet-stream'
    
    async def check_file_exists(self, object_key: str) -> bool:
        """
        檢查檔案是否已存在於R2中
        
        Args:
            object_key: R2中的物件金鑰
            
        Returns:
            bool: 檔案是否存在
        """
        if self._client is None:
            self._initialize_client()
        
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.head_object(Bucket=self.config.r2_bucket_name, Key=object_key)
            )
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                # 其他錯誤，假設檔案不存在
                self.logger.warning(f"檢查檔案存在時發生錯誤: {e}")
                return False
        except Exception as e:
            self.logger.warning(f"檢查檔案存在時發生錯誤: {e}")
            return False
    
    def generate_content_based_key(self, file_path: Path) -> Optional[str]:
        """
        基於檔案內容生成物件金鑰
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            Optional[str]: 物件金鑰，失敗時返回None
        """
        return HashUtils.generate_content_based_filename(file_path, self.config.hash_algorithm)
    
    async def upload_file(
        self,
        file_path: Path,
        object_key: Optional[str] = None,
        metadata: Optional[dict] = None,
        check_duplicate: bool = True
    ) -> Tuple[bool, str, bool]:
        """
        上傳單個檔案
        
        Args:
            file_path: 本地檔案路徑
            object_key: R2中的物件金鑰，如果為None則自動生成基於內容的金鑰
            metadata: 額外的中繼資料
            check_duplicate: 是否檢查重複檔案
            
        Returns:
            Tuple[bool, str, bool]: (是否成功, 錯誤訊息或URL, 是否為重複檔案)
        """
        if self._client is None:
            self._initialize_client()
        
        if self._semaphore is None:
            raise R2UploadError("上傳器未正確初始化")
        
        # 如果沒有提供object_key，則基於檔案內容生成
        if object_key is None:
            object_key = self.generate_content_based_key(file_path)
            if object_key is None:
                return False, "無法生成檔案金鑰", False
        
        # 檢查重複檔案
        if check_duplicate:
            exists = await self.check_file_exists(object_key)
            if exists:
                # 產生檔案URL
                file_url = f"{self.config.r2_endpoint_url.replace('https://', 'https://pub-')}/{self.config.r2_bucket_name}/{object_key}"
                self.logger.info(f"檔案已存在，跳過上傳: {file_path} -> {object_key}")
                return True, file_url, True  # 第三個參數表示是重複檔案
        
        async with self._semaphore:
            success, message = await self._upload_with_retry(file_path, object_key, metadata)
            return success, message, False  # 第三個參數表示不是重複檔案
    
    async def _upload_with_retry(
        self, 
        file_path: Path, 
        object_key: str,
        metadata: Optional[dict] = None
    ) -> Tuple[bool, str]:
        """
        帶重試機制的上傳
        
        Args:
            file_path: 本地檔案路徑
            object_key: R2中的物件金鑰
            metadata: 額外的中繼資料
            
        Returns:
            Tuple[bool, str]: (是否成功, 錯誤訊息或URL)
        """
        last_error = ""
        
        for attempt in range(self.config.max_retries + 1):
            try:
                return await self._do_upload(file_path, object_key, metadata)
                
            except Exception as e:
                last_error = str(e)
                self.logger.warning(
                    f"上傳嘗試 {attempt + 1}/{self.config.max_retries + 1} 失敗: "
                    f"{file_path} - {last_error}"
                )
                
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
        
        return False, f"上傳失敗（重試 {self.config.max_retries} 次後）: {last_error}"
    
    async def _do_upload(
        self, 
        file_path: Path, 
        object_key: str,
        metadata: Optional[dict] = None
    ) -> Tuple[bool, str]:
        """
        執行實際上傳
        
        Args:
            file_path: 本地檔案路徑
            object_key: R2中的物件金鑰
            metadata: 額外的中繼資料
            
        Returns:
            Tuple[bool, str]: (是否成功, 錯誤訊息或URL)
        """
        try:
            # 讀取檔案內容
            async with aiofiles.open(file_path, 'rb') as file:
                file_content = await file.read()
            
            # 準備上傳參數
            upload_args = {
                'Bucket': self.config.r2_bucket_name,
                'Key': object_key,
                'Body': file_content,
                'ContentType': self._get_content_type(file_path),
            }
            
            # 添加中繼資料
            if metadata:
                upload_args['Metadata'] = metadata
            
            # 執行上傳
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.put_object(**upload_args)
            )
            
            # 產生檔案URL
            file_url = f"{self.config.r2_endpoint_url.replace('https://', 'https://pub-')}/{self.config.r2_bucket_name}/{object_key}"
            
            self.logger.info(f"檔案上傳成功: {file_path} -> {object_key}")
            return True, file_url
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            return False, f"AWS錯誤 {error_code}: {error_message}"
            
        except FileNotFoundError:
            return False, f"檔案不存在: {file_path}"
            
        except Exception as e:
            return False, f"上傳錯誤: {str(e)}"
    
    async def upload_files(
        self, 
        file_mappings: List[Tuple[Path, str]], 
        progress_callback: Optional[callable] = None
    ) -> List[Tuple[Path, bool, str]]:
        """
        批量上傳檔案
        
        Args:
            file_mappings: (本地路徑, R2物件金鑰) 的列表
            progress_callback: 進度回呼函數
            
        Returns:
            List[Tuple[Path, bool, str]]: (檔案路徑, 是否成功, 結果訊息) 的列表
        """
        if self._client is None:
            self._initialize_client()
        
        results = []
        tasks = []
        
        # 建立上傳任務
        for file_path, object_key in file_mappings:
            task = self._upload_with_progress(file_path, object_key, progress_callback)
            tasks.append(task)
        
        # 並發執行上傳
        upload_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 處理結果
        for i, (file_path, object_key) in enumerate(file_mappings):
            result = upload_results[i]
            
            if isinstance(result, Exception):
                results.append((file_path, False, str(result)))
            else:
                success, message = result
                results.append((file_path, success, message))
        
        return results
    
    async def _upload_with_progress(
        self, 
        file_path: Path, 
        object_key: str, 
        progress_callback: Optional[callable] = None
    ) -> Tuple[bool, str]:
        """
        帶進度回呼的上傳
        
        Args:
            file_path: 本地檔案路徑
            object_key: R2中的物件金鑰
            progress_callback: 進度回呼函數
            
        Returns:
            Tuple[bool, str]: (是否成功, 錯誤訊息或URL)
        """
        try:
            success, message = await self.upload_file(file_path, object_key)
            
            if progress_callback:
                await asyncio.get_event_loop().run_in_executor(
                    None, progress_callback, file_path, success, message
                )
            
            return success, message
            
        except Exception as e:
            error_message = str(e)
            
            if progress_callback:
                await asyncio.get_event_loop().run_in_executor(
                    None, progress_callback, file_path, False, error_message
                )
            
            return False, error_message
    
    def close(self) -> None:
        """關閉上傳器，清理資源"""
        if self._client:
            # boto3客戶端會自動清理
            self._client = None
        
        if self._semaphore:
            self._semaphore = None
        
        self.logger.info("R2上傳器已關閉")
    
    async def __aenter__(self):
        """異步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器出口"""
        self.close()
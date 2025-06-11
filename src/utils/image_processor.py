"""
圖片處理模組

提供圖片壓縮、調整大小等功能。
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageOps
from ..config import Config
from .logger import get_logger


class ImageProcessor:
    """圖片處理器"""
    
    def __init__(self, config: Config):
        """
        初始化圖片處理器
        
        Args:
            config: 配置物件
        """
        self.config = config
        self.logger = get_logger(__name__)
    
    def process_image(self, input_path: Path, output_path: Path) -> bool:
        """
        處理圖片（壓縮、調整大小等）
        
        Args:
            input_path: 輸入檔案路徑
            output_path: 輸出檔案路徑
            
        Returns:
            bool: 是否處理成功
        """
        try:
            with Image.open(input_path) as img:
                # 移除EXIF資訊並自動旋轉
                img = ImageOps.exif_transpose(img)
                
                # 轉換為RGB模式（如果需要）
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 調整大小（如果需要）
                if self.config.max_image_size > 0:
                    img = self._resize_image(img, self.config.max_image_size)
                
                # 確保輸出目錄存在
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 儲存圖片
                save_kwargs = {}
                if self.config.enable_compression and output_path.suffix.lower() in ['.jpg', '.jpeg']:
                    save_kwargs['quality'] = self.config.compression_quality
                    save_kwargs['optimize'] = True
                
                img.save(output_path, **save_kwargs)
                
                self.logger.info(f"圖片處理完成: {input_path} -> {output_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"圖片處理失敗: {input_path} - {str(e)}")
            return False
    
    def _resize_image(self, img: Image.Image, max_size: int) -> Image.Image:
        """
        調整圖片大小
        
        Args:
            img: PIL圖片物件
            max_size: 最大尺寸
            
        Returns:
            Image.Image: 調整後的圖片
        """
        width, height = img.size
        
        # 如果圖片已經足夠小，直接返回
        if width <= max_size and height <= max_size:
            return img
        
        # 計算新的尺寸（保持長寬比）
        if width > height:
            new_width = max_size
            new_height = int(height * max_size / width)
        else:
            new_height = max_size
            new_width = int(width * max_size / height)
        
        # 使用高品質重採樣
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def generate_filename(self, original_path: Path) -> str:
        """
        根據配置產生檔案名稱
        
        Args:
            original_path: 原始檔案路徑
            
        Returns:
            str: 新的檔案名稱
        """
        extension = original_path.suffix.lower()
        
        if self.config.filename_format == "original":
            return original_path.name
        elif self.config.filename_format == "timestamp":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            return f"{timestamp}{extension}"
        elif self.config.filename_format == "uuid":
            return f"{uuid.uuid4().hex}{extension}"
        elif self.config.filename_format == "custom":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"{self.config.custom_prefix}{timestamp}{extension}"
        else:
            return original_path.name
    
    def get_image_info(self, image_path: Path) -> Optional[dict]:
        """
        取得圖片資訊
        
        Args:
            image_path: 圖片路徑
            
        Returns:
            Optional[dict]: 圖片資訊字典
        """
        try:
            with Image.open(image_path) as img:
                return {
                    "format": img.format,
                    "mode": img.mode,
                    "size": img.size,
                    "width": img.width,
                    "height": img.height,
                    "file_size": image_path.stat().st_size,
                }
        except Exception as e:
            self.logger.error(f"無法取得圖片資訊: {image_path} - {str(e)}")
            return None
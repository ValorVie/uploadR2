"""
UploadR2 - 批量上傳圖片到Cloudflare R2存儲的工具

這個套件提供了一個簡單而強大的工具，用於將本地圖片批量上傳到Cloudflare R2存儲。
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .config import Config, load_config
from .r2_uploader import R2Uploader
from .batch_processor import BatchProcessor
from .progress_tracker import ProgressTracker
from .utils import ImageProcessor, FileUtils, HashUtils

__all__ = [
    "Config",
    "load_config",
    "R2Uploader",
    "BatchProcessor",
    "ProgressTracker",
    "ImageProcessor",
    "FileUtils",
    "HashUtils",
]
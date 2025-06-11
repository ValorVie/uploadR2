"""
uploadR2 主程式

Cloudflare R2圖片批量上傳工具
"""

import asyncio
import sys
import argparse
from pathlib import Path
from typing import Optional

from src.config import load_config, Config
from src.batch_processor import BatchProcessor, BatchProcessorError
from src.utils.logger import setup_logger, get_logger


def setup_argument_parser() -> argparse.ArgumentParser:
    """設定命令行參數解析器"""
    parser = argparse.ArgumentParser(
        description="Cloudflare R2圖片批量上傳工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  python main.py                          # 使用預設設定處理images/original中的所有圖片
  python main.py --config custom.env     # 使用自訂配置檔案
  python main.py --dry-run               # 只掃描和驗證檔案，不實際上傳
  python main.py --cleanup               # 清理transfer目錄
  python main.py --test-connection       # 測試R2連接
        """
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default=".env",
        help="配置檔案路徑 (預設: .env)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只掃描和驗證檔案，不實際處理和上傳"
    )
    
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="清理transfer目錄後退出"
    )
    
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="測試R2連接後退出"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="日誌等級 (覆蓋配置檔案設定)"
    )
    
    parser.add_argument(
        "--max-concurrent",
        type=int,
        help="最大並發上傳數量 (覆蓋配置檔案設定)"
    )
    
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="不顯示進度條"
    )
    
    return parser


async def test_r2_connection(config: Config) -> bool:
    """
    測試R2連接
    
    Args:
        config: 配置物件
        
    Returns:
        bool: 連接是否成功
    """
    logger = get_logger()
    
    try:
        from src.r2_uploader import R2Uploader
        
        async with R2Uploader(config) as uploader:
            success = await uploader.test_connection()
            
            if success:
                logger.info("✅ R2連接測試成功")
                return True
            else:
                logger.error("❌ R2連接測試失敗")
                return False
                
    except Exception as e:
        logger.error(f"❌ R2連接測試失敗: {str(e)}")
        return False


async def main_async(args: argparse.Namespace) -> int:
    """
    主程式異步版本
    
    Args:
        args: 命令行參數
        
    Returns:
        int: 退出代碼
    """
    try:
        # 載入配置
        config = load_config(args.config)
        
        # 覆蓋命令行參數
        if args.log_level:
            config.log_level = args.log_level
        if args.max_concurrent:
            config.max_concurrent_uploads = args.max_concurrent
        if args.no_progress:
            config.show_progress = False
        
        # 設定日誌
        logger = setup_logger(
            log_file=config.log_file,
            log_level=config.log_level
        )
        
        logger.info("=== uploadR2 啟動 ===")
        logger.info(f"配置檔案: {args.config}")
        logger.info(f"R2儲存桶: {config.r2_bucket_name}")
        logger.info(f"最大並發數: {config.max_concurrent_uploads}")
        
        # 處理特殊命令
        if args.test_connection:
            success = await test_r2_connection(config)
            return 0 if success else 1
        
        # 初始化批量處理器
        processor = BatchProcessor(config)
        
        if args.cleanup:
            logger.info("清理transfer目錄...")
            processor.cleanup_transfer_directory()
            logger.info("清理完成")
            return 0
        
        # 掃描圖片檔案
        logger.info("掃描圖片檔案...")
        image_files = processor.scan_images()
        
        if not image_files:
            logger.warning("未找到任何圖片檔案")
            logger.info("請將圖片檔案放置在 images/original 目錄中")
            return 1
        
        logger.info(f"找到 {len(image_files)} 個圖片檔案")
        
        # 顯示檔案清單
        for i, file_path in enumerate(image_files[:10], 1):  # 最多顯示10個
            logger.info(f"  {i}. {file_path.name} ({file_path.stat().st_size / 1024:.1f} KB)")
        
        if len(image_files) > 10:
            logger.info(f"  ... 還有 {len(image_files) - 10} 個檔案")
        
        # Dry run模式
        if args.dry_run:
            logger.info("Dry run 模式 - 只驗證檔案，不實際處理")
            
            valid_files = 0
            invalid_files = 0
            
            for file_path in image_files:
                from src.utils.file_utils import FileUtils
                is_valid, error_msg = FileUtils.validate_file(file_path, config)
                
                if is_valid:
                    valid_files += 1
                    logger.debug(f"✅ {file_path.name}")
                else:
                    invalid_files += 1
                    logger.warning(f"❌ {file_path.name}: {error_msg}")
            
            logger.info(f"驗證完成: {valid_files} 個有效檔案, {invalid_files} 個無效檔案")
            return 0
        
        # 確認上傳
        if config.show_progress:
            try:
                response = input(f"\n準備上傳 {len(image_files)} 個檔案到 {config.r2_bucket_name}，是否繼續？ (y/N): ")
                if response.lower() not in ['y', 'yes']:
                    logger.info("用戶取消操作")
                    return 0
            except KeyboardInterrupt:
                logger.info("\n用戶中斷操作")
                return 0
        
        # 開始批量處理和上傳
        logger.info("開始批量處理和上傳...")
        await processor.process_and_upload_batch(image_files)
        
        # 顯示處理摘要
        summary = processor.get_processing_summary()
        logger.info("=== 處理摘要 ===")
        logger.info(f"總檔案數: {summary['total_files']}")
        logger.info(f"成功上傳: {summary['uploaded_files']}")
        logger.info(f"處理失敗: {summary['failed_files']}")
        logger.info(f"跳過檔案: {summary['skipped_files']}")
        logger.info(f"成功率: {summary['success_rate']:.2f}%")
        logger.info(f"總用時: {summary['elapsed_time']:.2f} 秒")
        
        # 顯示重複檔案清單
        duplicate_files = processor.get_duplicate_files()
        if duplicate_files:
            logger.info("=== 重複檔案（已存在，跳過上傳）===")
            for i, filename in enumerate(duplicate_files, 1):
                logger.info(f"{i:2d}. {filename}")
        
        # 顯示上傳成功的檔案URL清單（包含原始檔名對應）
        uploaded_files_with_urls = processor.get_uploaded_files_with_urls()
        if uploaded_files_with_urls:
            logger.info("=== 上傳成功的圖片URL ===")
            for i, (filename, url) in enumerate(uploaded_files_with_urls, 1):
                logger.info(f"{i:2d}. {filename} -> {url}")
        
        # 顯示失敗檔案
        failed_files = processor.get_failed_files()
        if failed_files:
            logger.warning("=== 失敗檔案 ===")
            for file_progress in failed_files:
                logger.warning(f"❌ {file_progress.file_path.name}: {file_progress.error_message}")
        
        # 根據結果設定退出代碼
        if summary['failed_files'] > 0:
            logger.warning("部分檔案處理失敗")
            return 1
        
        logger.info("✅ 所有檔案處理完成")
        return 0
        
    except BatchProcessorError as e:
        logger = get_logger()
        logger.error(f"批量處理錯誤: {str(e)}")
        return 1
        
    except KeyboardInterrupt:
        logger = get_logger()
        logger.info("用戶中斷操作")
        return 130  # 標準的鍵盤中斷退出代碼
        
    except Exception as e:
        logger = get_logger()
        logger.error(f"未預期的錯誤: {str(e)}", exc_info=True)
        return 1


def main() -> int:
    """
    主程式入口
    
    Returns:
        int: 退出代碼
    """
    # 解析命令行參數
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    try:
        # 檢查配置檔案
        if not Path(args.config).exists():
            print(f"錯誤: 配置檔案不存在: {args.config}")
            print("請複製 .env.example 到 .env 並填入您的 R2 配置資訊")
            return 1
        
        # 運行異步主程式
        return asyncio.run(main_async(args))
        
    except KeyboardInterrupt:
        print("\n用戶中斷操作")
        return 130
        
    except Exception as e:
        print(f"啟動錯誤: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

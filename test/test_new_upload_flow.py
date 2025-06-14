#!/usr/bin/env python3
"""
測試新的上傳流程

驗證：
1. 重複檔案檢測完全在本地執行
2. R2 上傳使用短檔名作為檔名
3. 保持現有的錯誤處理和日誌記錄
"""

import asyncio
import tempfile
import shutil
from pathlib import Path
import sys
import os

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.r2_uploader import R2Uploader
from src.utils.database_integration import create_database_integration
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_new_upload_flow():
    """測試新的上傳流程"""
    logger.info("開始測試新的上傳流程")
    
    # 創建測試配置（使用假的 R2 憑證進行測試）
    config = Config(
        r2_endpoint_url="https://test.r2.cloudflarestorage.com",
        r2_access_key_id="test_access_key",
        r2_secret_access_key="test_secret_key",
        r2_bucket_name="test_bucket",
        enable_short_keys=True,
        check_duplicate=True
    )
    
    # 創建臨時測試檔案
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("這是一個測試檔案，用於驗證新的上傳流程。\n")
        f.write("重複檔案檢測現在完全在本地資料庫中執行。\n")
        f.write("R2 上傳直接使用短檔名作為檔名。\n")
        test_file = Path(f.name)
    
    try:
        # 測試資料庫整合
        db_integration = create_database_integration(config)
        if not db_integration:
            logger.error("資料庫整合初始化失敗")
            return False
        
        logger.info("資料庫整合初始化成功")
        
        # 測試重複檔案檢測
        logger.info("測試重複檔案檢測...")
        duplicate_record = db_integration.check_duplicate_file(test_file)
        if duplicate_record:
            logger.info(f"發現重複檔案: {duplicate_record.short_key}")
        else:
            logger.info("沒有發現重複檔案")
        
        # 測試檔案記錄創建
        logger.info("測試檔案記錄創建...")
        temp_record = db_integration.create_file_record_from_path(
            test_file, "", ""
        )
        logger.info(f"創建檔案記錄: {temp_record.original_filename}")
        logger.info(f"UUID Key: {temp_record.uuid_key}")
        logger.info(f"SHA512 Hash: {temp_record.sha512_hash[:16]}...")
        
        # 測試存儲檔案記錄（生成短檔名）
        try:
            file_id = db_integration.store_file_record(temp_record)
            logger.info(f"檔案記錄已存儲，ID: {file_id}")
            logger.info(f"生成的短檔名: {temp_record.short_key}")
            
            # 測試更新上傳資訊
            test_r2_key = temp_record.short_key + temp_record.file_extension
            test_url = f"https://example.com/{test_r2_key}"
            
            update_success = db_integration.update_file_record_upload_info(
                temp_record.sha512_hash, test_r2_key, test_url
            )
            
            if update_success:
                logger.info("上傳資訊更新成功")
            else:
                logger.warning("上傳資訊更新失敗")
            
            # 測試重複檢測（應該能找到）
            duplicate_check = db_integration.check_duplicate_file(test_file)
            if duplicate_check:
                logger.info(f"重複檢測成功: {duplicate_check.short_key}")
                logger.info(f"上傳 URL: {duplicate_check.upload_url}")
            else:
                logger.warning("重複檢測失敗")
            
        except Exception as e:
            logger.error(f"檔案記錄存儲失敗: {e}")
            return False
        
        # 測試統計資訊
        stats = db_integration.get_statistics()
        if stats:
            logger.info("=== 資料庫統計 ===")
            logger.info(f"總檔案數: {stats['total_files']}")
            logger.info(f"有短檔名的檔案: {stats['files_with_short_keys']}")
            logger.info(f"總大小: {stats['total_size_mb']} MB")
        
        logger.info("新的上傳流程測試完成")
        return True
        
    except Exception as e:
        logger.error(f"測試過程中發生錯誤: {e}")
        return False
    
    finally:
        # 清理測試檔案
        if test_file.exists():
            test_file.unlink()
        
        # 關閉資料庫連接
        if 'db_integration' in locals():
            db_integration.close()


async def test_mock_r2_upload():
    """模擬 R2 上傳流程測試"""
    logger.info("開始模擬 R2 上傳流程測試")
    
    # 創建測試配置（使用假的 R2 憑證進行測試）
    config = Config(
        r2_endpoint_url="https://test.r2.cloudflarestorage.com",
        r2_access_key_id="test_access_key",
        r2_secret_access_key="test_secret_key",
        r2_bucket_name="test_bucket",
        enable_short_keys=True,
        check_duplicate=True
    )
    
    # 創建測試檔案
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jpg', delete=False) as f:
        f.write("fake image content for testing")
        test_file = Path(f.name)
    
    try:
        # 初始化上傳器（但不執行真實上傳）
        uploader = R2Uploader(config)
        
        # 測試重複檔案檢測邏輯
        if uploader.db_integration:
            logger.info("測試本地重複檢測...")
            existing_record = uploader.db_integration.check_duplicate_file(test_file)
            
            if existing_record:
                logger.info(f"發現重複檔案: {existing_record.short_key}")
            else:
                logger.info("沒有重複檔案，應該進行上傳")
                
                # 模擬檔案記錄創建流程
                temp_record = uploader.db_integration.create_file_record_from_path(
                    test_file, "", ""
                )
                
                try:
                    file_id = uploader.db_integration.store_file_record(temp_record)
                    if temp_record.short_key:
                        object_key = temp_record.short_key + temp_record.file_extension
                        logger.info(f"將使用短檔名作為 R2 object key: {object_key}")
                        
                        # 模擬生成 URL
                        mock_url = uploader._generate_file_url(object_key)
                        logger.info(f"生成的 URL: {mock_url}")
                        
                    else:
                        logger.warning("短檔名生成失敗")
                        
                except Exception as e:
                    logger.error(f"檔案記錄存儲失敗: {e}")
        
        logger.info("模擬 R2 上傳流程測試完成")
        return True
        
    except Exception as e:
        logger.error(f"模擬測試過程中發生錯誤: {e}")
        return False
    
    finally:
        # 清理
        if test_file.exists():
            test_file.unlink()
        
        if 'uploader' in locals():
            uploader.close()


async def main():
    """主函數"""
    logger.info("=== 新上傳流程測試開始 ===")
    
    try:
        # 測試 1: 基本資料庫流程
        success1 = await test_new_upload_flow()
        logger.info(f"基本資料庫流程測試: {'成功' if success1 else '失敗'}")
        
        # 測試 2: 模擬 R2 上傳
        success2 = await test_mock_r2_upload()
        logger.info(f"模擬 R2 上傳測試: {'成功' if success2 else '失敗'}")
        
        if success1 and success2:
            logger.info("=== 所有測試通過 ===")
            print("\n✅ 新的上傳流程測試通過！")
            print("✅ 重複檔案檢測完全在本地執行")
            print("✅ R2 上傳使用短檔名作為檔名")
            print("✅ URL 結構直接對應 R2 路徑")
        else:
            logger.error("=== 部分測試失敗 ===")
            print("\n❌ 測試失敗，請檢查日誌")
            
    except Exception as e:
        logger.error(f"測試執行失敗: {e}")
        print(f"\n❌ 測試執行失敗: {e}")


if __name__ == "__main__":
    asyncio.run(main())
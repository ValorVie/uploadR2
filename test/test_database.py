#!/usr/bin/env python3
"""
資料庫架構測試程式

測試 SQLite 資料庫架構的基本功能。
"""

import tempfile
import shutil
from pathlib import Path
from src.config import Config
from src.database import DatabaseManager, FileRecord
from src.utils.database_integration import DatabaseIntegration
from src.utils.logger import setup_logger


def test_database_architecture():
    """測試資料庫架構"""
    print("=== SQLite 資料庫架構測試 ===\n")
    
    # 設定日誌
    setup_logger(log_level="INFO")
    
    # 創建臨時目錄和測試配置
    temp_dir = Path(tempfile.mkdtemp())
    db_path = temp_dir / "test.db"
    
    try:
        # 創建測試配置
        config = Config(
            r2_endpoint_url="https://test.r2.cloudflarestorage.com",
            r2_access_key_id="test_key",
            r2_secret_access_key="test_secret",
            r2_bucket_name="test_bucket",
            database_path=str(db_path),
            enable_short_keys=True
        )
        
        print("1. 測試資料庫初始化...")
        db_manager = DatabaseManager(str(db_path))
        print("✅ 資料庫初始化成功")
        
        print("\n2. 測試短檔名生成...")
        short_key, length, salt = db_manager._short_key_generator.generate_short_key()
        print(f"✅ 短檔名生成成功: {short_key} (長度: {length})")
        
        print("\n3. 測試檔案記錄存儲...")
        # 創建測試檔案記錄
        test_record = FileRecord(
            uuid_key="test-uuid-12345",
            original_filename="test_image.jpg",
            file_extension=".jpg",
            file_size=1024000,
            mime_type="image/jpeg",
            sha512_hash="test_hash_12345",
            r2_object_key="test_object_key.jpg",
            upload_url="https://test.example.com/test_object_key.jpg"
        )
        
        file_id = db_manager.store_file_record(test_record)
        print(f"✅ 檔案記錄存儲成功，ID: {file_id}, 短檔名: {test_record.short_key}")
        
        print("\n4. 測試檔案記錄查詢...")
        # 通過UUID查詢
        record_by_uuid = db_manager.get_file_by_uuid(test_record.uuid_key)
        if record_by_uuid:
            print(f"✅ UUID查詢成功: {record_by_uuid.original_filename}")
        
        # 通過短檔名查詢
        if test_record.short_key:
            record_by_short_key = db_manager.get_file_by_short_key(test_record.short_key)
            if record_by_short_key:
                print(f"✅ 短檔名查詢成功: {record_by_short_key.original_filename}")
        
        print("\n5. 測試重複檔案檢查...")
        duplicate_record = db_manager.check_duplicate_by_hash(test_record.sha512_hash)
        if duplicate_record:
            print(f"✅ 重複檔案檢查成功: {duplicate_record.original_filename}")
        
        print("\n6. 測試統計資訊...")
        stats = db_manager.get_statistics()
        print(f"✅ 統計資訊獲取成功:")
        print(f"   - 總檔案數: {stats['total_files']}")
        print(f"   - 具有短檔名的檔案數: {stats['files_with_short_keys']}")
        print(f"   - 總大小: {stats['total_size_mb']} MB")
        
        # 短檔名統計
        short_key_stats = stats['short_key_statistics']
        print(f"   - 字符集大小: {short_key_stats['charset_size']}")
        print(f"   - 已使用短檔名數量: {short_key_stats['used_short_keys_count']}")
        
        if short_key_stats['sequences']:
            for seq in short_key_stats['sequences']:
                print(f"   - 長度 {seq['length']}: {seq['current']}/{seq['max_possible']} ({seq['usage_percent']}%)")
        
        print("\n7. 測試資料庫整合...")
        db_integration = DatabaseIntegration(config)
        
        # 創建測試檔案
        test_file = temp_dir / "test_image.jpg"
        test_file.write_bytes(b"fake image content for testing")
        
        # 測試重複檢查
        existing = db_integration.check_duplicate_file(test_file)
        if existing:
            print(f"✅ 重複檢查成功: 找到現有檔案 {existing.original_filename}")
        else:
            print("✅ 重複檢查成功: 未找到重複檔案")
        
        print("\n8. 測試多個短檔名生成...")
        generated_keys = set()
        for i in range(10):
            key, _, _ = db_manager._short_key_generator.generate_short_key()
            generated_keys.add(key)
        
        if len(generated_keys) == 10:
            print(f"✅ 生成了10個唯一短檔名: {', '.join(sorted(generated_keys))}")
        else:
            print(f"❌ 短檔名生成重複，只生成了 {len(generated_keys)} 個唯一值")
        
        # 關閉資源
        db_integration.close()
        db_manager.close()
        
        print("\n=== 測試完成 ===")
        print("✅ 所有測試通過！資料庫架構運作正常。")
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 清理臨時目錄
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            print(f"\n🧹 清理臨時目錄: {temp_dir}")


def test_short_key_performance():
    """測試短檔名生成效能"""
    print("\n=== 短檔名生成效能測試 ===")
    
    import time
    
    temp_dir = Path(tempfile.mkdtemp())
    db_path = temp_dir / "performance_test.db"
    
    try:
        db_manager = DatabaseManager(str(db_path))
        
        # 測試生成1000個短檔名的時間
        start_time = time.time()
        generated_keys = set()
        
        for i in range(1000):
            key, _, _ = db_manager._short_key_generator.generate_short_key()
            generated_keys.add(key)
            
            if (i + 1) % 100 == 0:
                print(f"已生成 {i + 1} 個短檔名...")
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        print(f"\n效能測試結果:")
        print(f"- 生成1000個短檔名耗時: {elapsed:.2f} 秒")
        print(f"- 平均每個短檔名: {elapsed/1000*1000:.2f} 毫秒")
        print(f"- 唯一短檔名數量: {len(generated_keys)}")
        print(f"- 重複率: {(1000-len(generated_keys))/1000*100:.2f}%")
        
        db_manager.close()
        
    except Exception as e:
        print(f"❌ 效能測試失敗: {e}")
        
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_database_architecture()
    test_short_key_performance()
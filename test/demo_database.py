#!/usr/bin/env python3
"""
SQLite 資料庫功能演示
"""

import os
from pathlib import Path
from src.config import Config, load_config
from src.database import DatabaseManager, FileRecord
from src.utils.database_integration import create_database_integration
from src.utils.logger import setup_logger

def main():
    """主要演示函數"""
    print("=== uploadR2 SQLite 資料庫功能演示 ===\n")
    
    # 設定日誌
    setup_logger(log_level="INFO")
    
    # 載入配置
    try:
        config = load_config()
        print(f"📁 資料庫檔案路徑: {config.database_path}")
        print(f"🔑 短檔名功能: {'✅ 啟用' if config.enable_short_keys else '❌ 停用'}")
        print(f"🔢 短檔名最小長度: {config.short_key_min_length}")
        print(f"📊 資料庫連接池大小: {config.database_pool_size}\n")
    except Exception as e:
        print(f"❌ 配置載入失敗: {e}")
        print("使用預設配置繼續演示...\n")
        
        # 使用預設配置
        config = Config(
            r2_endpoint_url="https://demo.r2.cloudflarestorage.com",
            r2_access_key_id="demo_key",
            r2_secret_access_key="demo_secret", 
            r2_bucket_name="demo_bucket",
            database_path="data/uploadr2.db",
            enable_short_keys=True
        )
    
    # 確保資料庫目錄存在
    db_path = Path(config.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        print("1. 📚 初始化資料庫管理器...")
        db_manager = DatabaseManager(config.database_path, config.database_pool_size)
        print(f"✅ 資料庫已建立: {db_path.absolute()}")
        print(f"📏 資料庫檔案大小: {db_path.stat().st_size if db_path.exists() else 0} bytes\n")
        
        print("2. 🔑 測試短檔名生成...")
        for i in range(5):
            short_key, length, salt = db_manager._short_key_generator.generate_short_key()
            print(f"   短檔名 {i+1}: {short_key} (長度: {length}, 鹽值: {salt[:8]}...)")
        print()
        
        print("3. 💾 測試檔案記錄存儲...")
        # 建立測試檔案記錄
        test_records = [
            FileRecord(
                uuid_key="demo-uuid-001",
                original_filename="demo_photo_1.jpg",
                file_extension=".jpg",
                file_size=2048000,
                mime_type="image/jpeg",
                sha512_hash="demo_hash_001_abcdef1234567890",
                r2_object_key="demo-uuid-001.jpg",
                upload_url="https://demo.example.com/demo-uuid-001.jpg"
            ),
            FileRecord(
                uuid_key="demo-uuid-002", 
                original_filename="demo_image_2.png",
                file_extension=".png",
                file_size=1536000,
                mime_type="image/png",
                sha512_hash="demo_hash_002_fedcba0987654321",
                r2_object_key="demo-uuid-002.png",
                upload_url="https://demo.example.com/demo-uuid-002.png"
            ),
            FileRecord(
                uuid_key="demo-uuid-003",
                original_filename="demo_screenshot.webp",
                file_extension=".webp", 
                file_size=892000,
                mime_type="image/webp",
                sha512_hash="demo_hash_003_123456789abcdef0",
                r2_object_key="demo-uuid-003.webp",
                upload_url="https://demo.example.com/demo-uuid-003.webp"
            )
        ]
        
        stored_records = []
        for i, record in enumerate(test_records):
            file_id = db_manager.store_file_record(record)
            stored_records.append(record)
            print(f"   檔案 {i+1}: {record.original_filename} -> {record.short_key} (ID: {file_id})")
        print()
        
        print("4. 🔍 測試檔案記錄查詢...")
        for record in stored_records[:2]:  # 只測試前兩個
            # UUID 查詢
            found_by_uuid = db_manager.get_file_by_uuid(record.uuid_key)
            if found_by_uuid:
                print(f"   UUID查詢: {record.uuid_key[:12]}... -> {found_by_uuid.original_filename}")
            
            # 短檔名查詢
            if record.short_key:
                found_by_short = db_manager.get_file_by_short_key(record.short_key)
                if found_by_short:
                    print(f"   短檔名查詢: {record.short_key} -> {found_by_short.original_filename}")
        print()
        
        print("5. 🔄 測試重複檔案檢查...")
        duplicate = db_manager.check_duplicate_by_hash("demo_hash_001_abcdef1234567890")
        if duplicate:
            print(f"   找到重複檔案: {duplicate.original_filename} (短檔名: {duplicate.short_key})")
        
        # 測試不存在的雜湊
        no_duplicate = db_manager.check_duplicate_by_hash("non_existent_hash_12345")
        if no_duplicate is None:
            print("   未找到不存在的雜湊檔案 ✅")
        print()
        
        print("6. 📊 資料庫統計資訊...")
        stats = db_manager.get_statistics()
        print(f"   總檔案數: {stats['total_files']}")
        print(f"   具有短檔名的檔案數: {stats['files_with_short_keys']}")
        print(f"   總大小: {stats['total_size_mb']} MB")
        print(f"   唯一副檔名數: {stats['unique_extensions']}")
        
        print("\n   檔案類型分布:")
        for ext_info in stats['extension_distribution']:
            print(f"     {ext_info['extension']}: {ext_info['count']} 個檔案")
        
        print("\n   短檔名統計:")
        short_stats = stats['short_key_statistics']
        print(f"     字符集大小: {short_stats['charset_size']}")
        print(f"     已使用短檔名: {short_stats['used_short_keys_count']}")
        print(f"     保留關鍵字: {short_stats['reserved_keys_count']}")
        
        for seq in short_stats['sequences']:
            print(f"     長度 {seq['length']}: {seq['current']}/{seq['max_possible']} ({seq['usage_percent']}%)")
        print()
        
        print("7. 🔗 測試資料庫整合...")
        db_integration = create_database_integration(config)
        if db_integration:
            # 獲取統計
            integration_stats = db_integration.get_statistics()
            if integration_stats:
                print(f"   整合模組統計: {integration_stats['total_files']} 個檔案")
            db_integration.close()
        print()
        
        # 關閉資料庫
        db_manager.close()
        
        # 顯示最終檔案資訊
        if db_path.exists():
            final_size = db_path.stat().st_size
            print(f"📁 最終資料庫檔案:")
            print(f"   路徑: {db_path.absolute()}")
            print(f"   大小: {final_size} bytes ({final_size/1024:.2f} KB)")
            print(f"   狀態: {'✅ 存在' if db_path.exists() else '❌ 不存在'}")
        
        print("\n=== 演示完成 ===")
        print("✅ 所有功能正常運作！")
        print(f"\n🗂️  您可以在以下位置找到資料庫檔案:")
        print(f"     {db_path.absolute()}")
        print("\n💡 提示:")
        print("   - 您可以使用 SQLite Browser 等工具查看資料庫內容")
        print("   - 資料庫包含檔案記錄、短檔名序列、保留關鍵字和操作日誌")
        print("   - 支援重複檔案檢測和高效能短檔名生成")
        
    except Exception as e:
        print(f"\n❌ 演示過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
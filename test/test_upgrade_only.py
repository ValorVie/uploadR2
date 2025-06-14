#!/usr/bin/env python3
"""
簡化的長度升級測試 - 專門測試升級機制
"""

import sys
from pathlib import Path
import secrets
import string

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.database import DatabaseManager
from src.database.short_key_generator import ShortKeyGenerator

def generate_dummy_file_record(short_key: str):
    """生成虛擬檔案記錄用於測試"""
    return {
        'uuid_key': f"test_uuid_{secrets.token_hex(16)}",
        'short_key': short_key,
        'original_filename': f"test_file_{short_key}.txt",
        'file_extension': '.txt',
        'file_size': 1024,
        'mime_type': 'text/plain',
        'sha512_hash': secrets.token_hex(64),
        'hash_algorithm': 'sha512',
        'r2_object_key': f"test/{short_key}.txt",
        'upload_url': f"https://test.com/{short_key}.txt",
        'upload_timestamp': '2024-01-01 00:00:00',
        'status': 'active'
    }

def main():
    print("🧪 測試長度升級機制")
    
    # 清理測試資料庫
    test_db_path = Path("data/test_upgrade.db")
    if test_db_path.exists():
        test_db_path.unlink()
        print("🗑️ 清理舊的測試資料庫")
    
    config = Config(
        r2_endpoint_url="https://test.r2.cloudflarestorage.com",
        r2_access_key_id="test_access_key",
        r2_secret_access_key="test_secret_key",
        r2_bucket_name="test_bucket",
        enable_short_keys=True,
        check_duplicate=True,
        database_path="data/test_upgrade.db"
    )
    
    db_manager = DatabaseManager(config.database_path, pool_size=5)
    
    try:
        generator = ShortKeyGenerator(db_manager)
        
        # 步驟1: 設置小的測試空間
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 重置序列表
            cursor.execute("DELETE FROM short_key_sequences")
            
            # 設置一個只有20個位置的測試空間
            test_max = 20
            cursor.execute("""
                INSERT INTO short_key_sequences (key_length, current_sequence, max_possible, exhausted)
                VALUES (4, 0, ?, FALSE)
            """, (test_max,))
            
            conn.commit()
            print(f"🔧 設置測試空間: 最大 {test_max} 個4位組合")
        
        # 步驟2: 填滿到85%以上
        charset = string.digits + string.ascii_lowercase + string.ascii_uppercase
        used_keys = set()
        
        # 填滿到17個（85%使用率）
        fill_count = 17
        print(f"📦 預先填充 {fill_count} 個4位短檔名...")
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            for i in range(fill_count):
                while True:
                    short_key = ''.join(secrets.choice(charset) for _ in range(4))
                    if short_key not in used_keys:
                        used_keys.add(short_key)
                        break
                
                dummy_record = generate_dummy_file_record(short_key)
                cursor.execute("""
                    INSERT INTO file_records (
                        uuid_key, short_key, original_filename, file_extension,
                        file_size, mime_type, sha512_hash, hash_algorithm,
                        r2_object_key, upload_url, upload_timestamp, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    dummy_record['uuid_key'], dummy_record['short_key'], 
                    dummy_record['original_filename'], dummy_record['file_extension'],
                    dummy_record['file_size'], dummy_record['mime_type'], 
                    dummy_record['sha512_hash'], dummy_record['hash_algorithm'],
                    dummy_record['r2_object_key'], dummy_record['upload_url'], 
                    dummy_record['upload_timestamp'], dummy_record['status']
                ))
                
                print(f"   填充第 {i+1} 個: {short_key}")
            
            # 更新序列計數
            cursor.execute("""
                UPDATE short_key_sequences 
                SET current_sequence = ?
                WHERE key_length = 4
            """, (fill_count,))
            
            conn.commit()
            usage_percent = (fill_count / test_max) * 100
            print(f"✅ 已填充 {fill_count} 個位置，使用率: {usage_percent:.1f}%")
        
        # 步驟3: 嘗試生成新短檔名，應該觸發升級
        print(f"\n🔄 開始生成新短檔名，預期會觸發長度升級...")
        
        generated_results = []
        for i in range(5):
            print(f"\n--- 生成第 {i+1} 個短檔名 ---")
            
            # 檢查生成前的序列狀態
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT key_length, current_sequence, max_possible, exhausted,
                           ROUND(CAST(current_sequence AS FLOAT) / max_possible * 100, 1) as usage_percent
                    FROM short_key_sequences 
                    ORDER BY key_length
                """)
                
                sequences = cursor.fetchall()
                print("📊 生成前序列狀態:")
                for seq in sequences:
                    status = "已用完" if seq[3] else "可用"
                    print(f"   長度 {seq[0]}: {seq[1]}/{seq[2]} ({seq[4]}%) - {status}")
            
            try:
                short_key, length, salt = generator.generate_short_key()
                generated_results.append({
                    'iteration': i + 1,
                    'short_key': short_key,
                    'length': length
                })
                
                print(f"✅ 生成成功: {short_key} (長度: {length})")
                
            except Exception as e:
                print(f"❌ 生成失敗: {e}")
                break
        
        # 步驟4: 分析結果
        if generated_results:
            lengths = [r['length'] for r in generated_results]
            unique_lengths = set(lengths)
            
            print(f"\n=== 測試結果 ===")
            print(f"成功生成 {len(generated_results)} 個短檔名")
            print(f"長度分布: {dict((l, lengths.count(l)) for l in unique_lengths)}")
            
            # 檢查是否有5位或更長的短檔名（證明發生了升級）
            if max(unique_lengths) > 4:
                print("✅ 成功觸發長度升級機制！")
                print(f"已升級到 {max(unique_lengths)} 位短檔名")
                
                # 檢查4位序列是否被標記為已耗盡
                with db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT exhausted FROM short_key_sequences WHERE key_length = 4
                    """)
                    row = cursor.fetchone()
                    if row and row[0]:
                        print("✅ 4位序列已正確標記為已耗盡")
                    else:
                        print("⚠️  4位序列未被標記為已耗盡")
                        
            else:
                print("❌ 未能觸發長度升級")
        else:
            print("❌ 沒有成功生成任何短檔名")
        
        # 檢查最終統計
        stats = generator.get_statistics()
        print("\n📈 最終統計:")
        for seq in stats["sequences"]:
            status = "已用完" if seq['exhausted'] else "可用"
            print(f"  長度 {seq['length']}: {seq['current']}/{seq['max_possible']} ({seq['usage_percent']:.1f}%) - {status}")
    
    finally:
        db_manager.close()
        
        # 清理測試資料庫
        if test_db_path.exists():
            test_db_path.unlink()
            print("🗑️ 清理測試資料庫")

if __name__ == "__main__":
    main()
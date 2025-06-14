#!/usr/bin/env python3
"""
測試短檔名碰撞和自動延展機制

驗證：
1. 短檔名生成器在碰撞時的重試機制
2. 長度自動升級機制
3. 保留關鍵字檢查
4. 並發情況下的短檔名生成
"""

import asyncio
import tempfile
import threading
import time
import secrets
import string
from pathlib import Path
import sys
import os

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.database import DatabaseManager
from src.database.short_key_generator import ShortKeyGenerator
from src.database.exceptions import ShortKeyCollisionError, ShortKeyExhaustedError
from src.utils.database_integration import create_database_integration
from src.utils.logger import get_logger

logger = get_logger(__name__)


def create_test_config():
    """創建測試配置"""
    return Config(
        r2_endpoint_url="https://test.r2.cloudflarestorage.com",
        r2_access_key_id="test_access_key",
        r2_secret_access_key="test_secret_key",
        r2_bucket_name="test_bucket",
        enable_short_keys=True,
        check_duplicate=True,
        database_path="data/test_collision.db"  # 使用專用測試資料庫
    )


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


async def test_basic_short_key_generation():
    """測試基本短檔名生成"""
    logger.info("=== 測試基本短檔名生成 ===")
    
    config = create_test_config()
    db_manager = DatabaseManager(config.database_path, pool_size=5)
    
    try:
        generator = ShortKeyGenerator(db_manager)
        
        # 生成一些短檔名
        generated_keys = []
        for i in range(10):
            short_key, length, salt = generator.generate_short_key()
            generated_keys.append(short_key)
            logger.info(f"生成短檔名 {i+1}: {short_key} (長度: {length})")
        
        # 驗證沒有重複
        unique_keys = set(generated_keys)
        if len(unique_keys) == len(generated_keys):
            logger.info("✅ 短檔名生成無重複")
        else:
            logger.error("❌ 發現重複的短檔名")
            return False
        
        # 檢查統計資訊
        stats = generator.get_statistics()
        logger.info(f"統計資訊: {stats}")
        
        return True
        
    except Exception as e:
        logger.error(f"基本短檔名生成測試失敗: {e}")
        return False
    
    finally:
        db_manager.close()


async def test_collision_handling():
    """測試碰撞處理機制 - 通過預先填充資料庫來創造碰撞情況"""
    logger.info("=== 測試碰撞處理機制 ===")
    
    config = create_test_config()
    db_manager = DatabaseManager(config.database_path, pool_size=5)
    
    try:
        generator = ShortKeyGenerator(db_manager)
        
        # 步驟1: 插入保留關鍵字
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 插入一些常見的保留關鍵字
            reserved_keys = ["test", "api", "www", "admin", "root", "user", "file", "data"]
            for key in reserved_keys:
                cursor.execute("""
                    INSERT OR IGNORE INTO reserved_short_keys (short_key, reason)
                    VALUES (?, ?)
                """, (key, "測試保留關鍵字"))
            
            conn.commit()
            logger.info(f"插入了 {len(reserved_keys)} 個保留關鍵字")
        
        # 步驟2: 預先填充一些4位短檔名到資料庫，創造碰撞環境
        charset = string.digits + string.ascii_lowercase + string.ascii_uppercase
        pre_filled_keys = set()
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 生成並插入50個隨機4位短檔名
            logger.info("預先填充50個4位短檔名來增加碰撞機率...")
            for i in range(50):
                while True:
                    short_key = ''.join(secrets.choice(charset) for _ in range(4))
                    # 確保不是保留關鍵字且未重複
                    if short_key not in reserved_keys and short_key not in pre_filled_keys:
                        pre_filled_keys.add(short_key)
                        break
                
                # 插入虛擬檔案記錄
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
                
                if i % 10 == 0:
                    logger.info(f"已預填充 {i+1} 個短檔名: {short_key}")
            
            conn.commit()
            logger.info(f"成功預填充 {len(pre_filled_keys)} 個4位短檔名")
        
        # 步驟3: 測試短檔名生成器的碰撞處理能力
        logger.info("開始測試短檔名生成器的碰撞處理...")
        
        generated_keys = set()
        generation_attempts = []
        reserved_collisions = 0
        existing_collisions = 0
        
        # 嘗試生成30個新的短檔名
        for i in range(30):
            try:
                short_key, length, salt = generator.generate_short_key()
                
                # 檢查是否與預填充的檔名衝突
                if short_key in pre_filled_keys:
                    existing_collisions += 1
                    logger.error(f"❌ 生成了已存在的短檔名: {short_key}")
                
                # 檢查是否與保留關鍵字衝突
                if short_key in reserved_keys:
                    reserved_collisions += 1
                    logger.error(f"❌ 生成了保留關鍵字: {short_key}")
                
                # 檢查內部重複
                if short_key in generated_keys:
                    logger.error(f"❌ 生成了重複短檔名: {short_key}")
                else:
                    generated_keys.add(short_key)
                
                generation_attempts.append({
                    'iteration': i + 1,
                    'short_key': short_key,
                    'length': length,
                    'is_new': short_key not in pre_filled_keys and short_key not in reserved_keys
                })
                
                if i % 5 == 0:
                    logger.info(f"第 {i+1} 個短檔名: {short_key} (長度: {length}) {'✅ 新' if generation_attempts[-1]['is_new'] else '❌ 衝突'}")
                    
            except ShortKeyCollisionError as e:
                logger.error(f"短檔名碰撞錯誤 (第 {i+1} 次嘗試): {e}")
                return False
            except Exception as e:
                logger.error(f"生成短檔名時發生未預期錯誤 (第 {i+1} 次嘗試): {e}")
                return False
        
        # 步驟4: 分析結果
        successful_generations = len(generated_keys)
        new_unique_keys = len([a for a in generation_attempts if a['is_new']])
        
        logger.info(f"\n=== 碰撞處理測試結果 ===")
        logger.info(f"總嘗試次數: 30")
        logger.info(f"成功生成唯一短檔名: {successful_generations}")
        logger.info(f"生成的新短檔名 (無衝突): {new_unique_keys}")
        logger.info(f"與已存在檔名衝突: {existing_collisions}")
        logger.info(f"與保留關鍵字衝突: {reserved_collisions}")
        
        # 檢查長度分布
        length_distribution = {}
        for attempt in generation_attempts:
            length = attempt['length']
            length_distribution[length] = length_distribution.get(length, 0) + 1
        
        logger.info(f"生成的短檔名長度分布: {length_distribution}")
        
        # 檢查最終統計
        stats = generator.get_statistics()
        logger.info("最終統計資訊:")
        for seq in stats["sequences"]:
            logger.info(f"  長度 {seq['length']}: {seq['current']}/{seq['max_possible']} ({seq['usage_percent']:.2f}%)")
        
        # 判斷測試是否成功
        # 成功條件：
        # 1. 沒有與已存在檔名的衝突
        # 2. 沒有與保留關鍵字的衝突
        # 3. 沒有內部重複
        # 4. 生成了預期數量的唯一短檔名
        
        test_passed = (
            existing_collisions == 0 and
            reserved_collisions == 0 and
            successful_generations == 30 and  # 應該生成30個唯一短檔名
            new_unique_keys >= 25  # 至少25個應該是真正新的
        )
        
        if test_passed:
            logger.info("✅ 碰撞處理機制測試通過")
        else:
            logger.error("❌ 碰撞處理機制測試失敗")
            logger.error(f"失敗原因: 已存在衝突={existing_collisions}, 保留字衝突={reserved_collisions}, 唯一生成={successful_generations}, 新檔名={new_unique_keys}")
        
        return test_passed
        
    except Exception as e:
        logger.error(f"碰撞處理測試失敗: {e}")
        import traceback
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return False
    
    finally:
        db_manager.close()


async def test_length_escalation():
    """測試長度升級機制 - 通過實際填滿短檔名空間來觸發升級"""
    logger.info("=== 測試長度升級機制 ===")
    
    config = create_test_config()
    db_manager = DatabaseManager(config.database_path, pool_size=5)
    
    try:
        generator = ShortKeyGenerator(db_manager)
        
        # 步驟1: 重置序列表，設置一個非常小的最大值來快速觸發升級
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 清空現有序列並重新設置
            cursor.execute("DELETE FROM short_key_sequences")
            
            # 設置長度4的最大值為很小的數字（比如10），這樣容易填滿
            small_max = 10
            cursor.execute("""
                INSERT INTO short_key_sequences (key_length, current_sequence, max_possible, exhausted)
                VALUES (4, 0, ?, FALSE)
            """, (small_max,))
            
            conn.commit()
            logger.info(f"設置長度 4 的最大值為 {small_max} 以快速觸發升級")
        
        # 步驟2: 先用虛擬記錄填滿長度4的空間
        charset = string.digits + string.ascii_lowercase + string.ascii_uppercase
        used_keys = set()
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 生成一些4位短檔名並插入到 file_records 表中
            logger.info("預先填充4位短檔名到資料庫...")
            for i in range(small_max - 2):  # 留2個位置，讓生成器可以再生成幾個
                # 生成4位隨機短檔名
                while True:
                    short_key = ''.join(secrets.choice(charset) for _ in range(4))
                    if short_key not in used_keys:
                        used_keys.add(short_key)
                        break
                
                # 創建虛擬檔案記錄
                dummy_record = generate_dummy_file_record(short_key)
                
                # 插入到 file_records 表
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
                
                if i % 5 == 0:
                    logger.info(f"已填充 {i+1} 個4位短檔名: {short_key}")
            
            # 更新序列計數
            cursor.execute("""
                UPDATE short_key_sequences
                SET current_sequence = ?
                WHERE key_length = 4
            """, (small_max - 2,))
            
            conn.commit()
            logger.info(f"已填充 {small_max - 2} 個4位短檔名到資料庫")
        
        # 步驟3: 現在嘗試生成新的短檔名，應該會觸發長度升級
        logger.info("開始生成新短檔名，預期會觸發長度升級...")
        print(f"\n📊 開始長度升級測試 - 目標: 從4位升級到5位")
        
        generated_keys = []
        length_changes = []
        
        for i in range(8):  # 生成8個短檔名
            try:
                print(f"\n🔄 嘗試生成第 {i+1} 個短檔名...")
                
                # 在生成前檢查當前序列狀態
                with db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT key_length, current_sequence, max_possible,
                               ROUND(CAST(current_sequence AS FLOAT) / max_possible * 100, 1) as usage_percent
                        FROM short_key_sequences
                        ORDER BY key_length
                    """)
                    
                    sequences_before = cursor.fetchall()
                    print(f"📈 生成前序列狀態:")
                    for seq in sequences_before:
                        print(f"   長度 {seq[0]}: {seq[1]}/{seq[2]} ({seq[3]}%)")
                
                short_key, length, salt = generator.generate_short_key()
                generated_keys.append(short_key)
                length_changes.append(length)
                
                print(f"✅ 第 {i+1} 個生成成功: {short_key} (長度: {length})")
                logger.info(f"第 {i+1} 個生成的短檔名: {short_key} (長度: {length})")
                
                # 如果生成成功，也把它加入到資料庫中（模擬真實使用情況）
                with db_manager.get_connection() as conn:
                    cursor = conn.cursor()
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
                    conn.commit()
                
            except Exception as e:
                logger.error(f"生成第 {i+1} 個短檔名時出錯: {e}")
                break
        
        # 步驟4: 分析結果
        unique_lengths = set(length_changes)
        logger.info(f"生成的短檔名長度分布: {dict((l, length_changes.count(l)) for l in unique_lengths)}")
        
        # 檢查統計資訊
        stats = generator.get_statistics()
        logger.info("最終統計資訊:")
        for seq in stats["sequences"]:
            logger.info(f"  長度 {seq['length']}: {seq['current']}/{seq['max_possible']} ({seq['usage_percent']:.2f}%) {'已用完' if seq['exhausted'] else '可用'}")
        
        # 驗證結果 - 修正判斷邏輯
        # 檢查是否有5位或更長的短檔名（證明發生了升級）
        max_length = max(unique_lengths) if unique_lengths else 4
        if max_length > 4:
            logger.info(f"✅ 成功檢測到長度升級: 升級到{max_length}位")
            print(f"🎉 長度升級成功！已升級到 {max_length} 位短檔名")
            
            # 檢查4位序列是否被標記為已耗盡
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT exhausted FROM short_key_sequences WHERE key_length = 4
                """)
                row = cursor.fetchone()
                if row and row[0]:
                    logger.info("✅ 4位序列已正確標記為已耗盡")
                    print("✅ 4位序列已正確標記為已耗盡")
                else:
                    logger.warning("⚠️  4位序列未被標記為已耗盡")
                    print("⚠️  4位序列未被標記為已耗盡")
            
            return True
        else:
            logger.warning(f"❌ 未檢測到長度升級，所有長度均為: {unique_lengths}")
            print(f"❌ 未檢測到長度升級，所有長度均為: {unique_lengths}")
            return False
            
    except Exception as e:
        logger.error(f"長度升級測試失敗: {e}")
        import traceback
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return False
    
    finally:
        db_manager.close()


async def test_concurrent_generation():
    """測試並發短檔名生成"""
    logger.info("=== 測試並發短檔名生成 ===")
    
    config = create_test_config()
    db_manager = DatabaseManager(config.database_path, pool_size=10)
    
    try:
        generator = ShortKeyGenerator(db_manager)
        
        # 並發生成短檔名
        results = []
        errors = []
        
        def generate_keys_worker(worker_id, count):
            """工作線程函數"""
            try:
                worker_keys = []
                for i in range(count):
                    short_key, length, salt = generator.generate_short_key()
                    worker_keys.append(short_key)
                    time.sleep(0.001)  # 小延遲模擬真實情況
                
                results.append((worker_id, worker_keys))
                logger.info(f"工作線程 {worker_id} 完成，生成了 {len(worker_keys)} 個短檔名")
                
            except Exception as e:
                errors.append((worker_id, str(e)))
                logger.error(f"工作線程 {worker_id} 失敗: {e}")
        
        # 啟動多個工作線程
        threads = []
        worker_count = 5
        keys_per_worker = 10
        
        logger.info(f"啟動 {worker_count} 個並發工作線程，每個生成 {keys_per_worker} 個短檔名")
        
        for worker_id in range(worker_count):
            thread = threading.Thread(
                target=generate_keys_worker,
                args=(worker_id, keys_per_worker)
            )
            threads.append(thread)
            thread.start()
        
        # 等待所有線程完成
        for thread in threads:
            thread.join()
        
        # 檢查結果
        if errors:
            logger.error(f"❌ 有 {len(errors)} 個工作線程失敗")
            for worker_id, error in errors:
                logger.error(f"  工作線程 {worker_id}: {error}")
            return False
        
        # 收集所有生成的短檔名
        all_keys = []
        for worker_id, keys in results:
            all_keys.extend(keys)
        
        # 檢查重複
        unique_keys = set(all_keys)
        if len(unique_keys) == len(all_keys):
            logger.info(f"✅ 並發生成 {len(all_keys)} 個短檔名，無重複")
            return True
        else:
            duplicates = len(all_keys) - len(unique_keys)
            logger.error(f"❌ 並發生成發現 {duplicates} 個重複短檔名")
            return False
            
    except Exception as e:
        logger.error(f"並發生成測試失敗: {e}")
        return False
    
    finally:
        db_manager.close()


async def test_forced_collision_scenario():
    """測試強制碰撞場景 - 模擬極端碰撞情況"""
    logger.info("=== 測試強制碰撞場景 ===")
    
    config = create_test_config()
    db_manager = DatabaseManager(config.database_path, pool_size=5)
    
    try:
        generator = ShortKeyGenerator(db_manager)
        
        # 步驟1: 創建一個測試空間（設置合理大小但能快速填滿）
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 清空並重新設置序列，創建一個有100個位置的測試空間
            cursor.execute("DELETE FROM short_key_sequences")
            test_max = 100  # 較大的空間，但仍然可控
            cursor.execute("""
                INSERT INTO short_key_sequences (key_length, current_sequence, max_possible, exhausted)
                VALUES (4, 0, ?, FALSE)
            """, (test_max,))
            
            # 清空保留關鍵字表，然後添加一些會佔用空間的保留字
            cursor.execute("DELETE FROM reserved_short_keys")
            
            # 添加一些特定的4位保留關鍵字
            reserved_4char = ["test", "api", "www", "admin"]
            for key in reserved_4char:
                cursor.execute("""
                    INSERT INTO reserved_short_keys (short_key, reason)
                    VALUES (?, ?)
                """, (key, "強制碰撞測試"))
            
            conn.commit()
            print(f"🔧 設置測試空間: 最大 {test_max} 個組合, 保留 {len(reserved_4char)} 個關鍵字")
            logger.info(f"設置測試空間: 最大 {test_max} 個組合, 保留 {len(reserved_4char)} 個關鍵字")
        
        # 步驟2: 預先填滿大部分可用空間（填到85%以上觸發升級）
        charset = string.digits + string.ascii_lowercase + string.ascii_uppercase
        used_keys = set(reserved_4char)  # 保留關鍵字已經佔用
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 填滿到85個（85%使用率），這樣應該會觸發升級
            fill_count = 85
            print(f"📦 預先填充 {fill_count} 個4位短檔名（達到85%使用率）...")
            logger.info(f"預先填滿 {fill_count} 個位置...")
            
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
                
                if i % 20 == 0 or i < 5:
                    print(f"   填充第 {i+1} 個: {short_key}")
                    logger.info(f"填充位置 {i+1}: {short_key}")
            
            # 更新序列計數
            cursor.execute("""
                UPDATE short_key_sequences
                SET current_sequence = ?
                WHERE key_length = 4
            """, (fill_count,))
            
            conn.commit()
            usage_percent = (fill_count / test_max) * 100
            print(f"✅ 已填充 {fill_count} 個位置，使用率: {usage_percent:.1f}%")
            logger.info(f"已佔用 {fill_count} 個位置，使用率: {usage_percent:.1f}%")
        
        # 步驟3: 現在嘗試生成更多短檔名，測試長度升級
        logger.info("開始測試長度升級機制...")
        
        generated_results = []
        
        # 嘗試生成5個短檔名（超過剩餘空間）
        for i in range(5):
            try:
                short_key, length, salt = generator.generate_short_key()
                generated_results.append({
                    'iteration': i + 1,
                    'short_key': short_key,
                    'length': length,
                    'salt': salt
                })
                
                logger.info(f"第 {i+1} 次生成: {short_key} (長度: {length})")
                
                # 將生成的短檔名也加入資料庫（模擬真實使用）
                if length == 4:  # 如果還是4位，檢查是否應該升級了
                    if short_key in used_keys:
                        logger.error(f"❌ 生成了已存在的短檔名: {short_key}")
                        break
                    used_keys.add(short_key)
                
                # 插入生成的記錄
                with db_manager.get_connection() as conn:
                    cursor = conn.cursor()
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
                    conn.commit()
                
            except Exception as e:
                logger.error(f"第 {i+1} 次生成失敗: {e}")
                import traceback
                logger.error(f"詳細錯誤: {traceback.format_exc()}")
                break
        
        # 步驟4: 分析結果
        if not generated_results:
            logger.error("❌ 無法生成任何短檔名")
            return False
        
        lengths_generated = [r['length'] for r in generated_results]
        unique_lengths = set(lengths_generated)
        
        logger.info(f"\n=== 強制碰撞測試結果 ===")
        logger.info(f"成功生成 {len(generated_results)} 個短檔名")
        logger.info(f"長度分布: {dict((l, lengths_generated.count(l)) for l in unique_lengths)}")
        
        # 檢查統計資訊
        stats = generator.get_statistics()
        logger.info("最終統計資訊:")
        for seq in stats["sequences"]:
            logger.info(f"  長度 {seq['length']}: {seq['current']}/{seq['max_possible']} ({seq['usage_percent']:.2f}%) {'已用完' if seq['exhausted'] else '可用'}")
        
        # 驗證是否發生了長度升級
        has_length_upgrade = len(unique_lengths) > 1 and max(unique_lengths) > 4
        
        if has_length_upgrade:
            logger.info("✅ 成功觸發長度升級機制")
            return True
        else:
            logger.warning("❌ 未能觸發長度升級機制")
            return False
        
    except Exception as e:
        logger.error(f"強制碰撞測試失敗: {e}")
        import traceback
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return False
    
    finally:
        db_manager.close()


async def test_integration_with_database():
    """測試與資料庫整合的短檔名處理"""
    logger.info("=== 測試與資料庫整合的短檔名處理 ===")
    
    config = create_test_config()
    db_integration = create_database_integration(config)
    
    if not db_integration:
        logger.error("無法創建資料庫整合")
        return False
    
    try:
        # 創建測試檔案
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("測試短檔名碰撞處理的檔案內容")
            test_file = Path(f.name)
        
        # 測試多次創建相同檔案記錄（應該觸發重複檢測）
        logger.info("測試重複檔案檢測...")
        
        first_record = db_integration.create_file_record_from_path(
            test_file, "", ""
        )
        
        # 第一次存儲
        file_id1 = db_integration.store_file_record(first_record)
        logger.info(f"第一次存儲成功，短檔名: {first_record.short_key}")
        
        # 第二次應該檢測到重複
        duplicate_check = db_integration.check_duplicate_file(test_file)
        if duplicate_check:
            logger.info(f"✅ 重複檢測成功: {duplicate_check.short_key}")
        else:
            logger.error("❌ 重複檢測失敗")
            return False
        
        # 嘗試再次存儲相同檔案（應該拋出 DuplicateFileError）
        try:
            second_record = db_integration.create_file_record_from_path(
                test_file, "", ""
            )
            file_id2 = db_integration.store_file_record(second_record)
            logger.error("❌ 應該檢測到重複檔案但沒有")
            return False
            
        except Exception as e:
            logger.info(f"✅ 正確檢測到重複檔案: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"資料庫整合測試失敗: {e}")
        return False
    
    finally:
        # 清理
        if 'test_file' in locals() and test_file.exists():
            test_file.unlink()
        
        if db_integration:
            db_integration.close()


async def main():
    """主函數"""
    logger.info("=== 短檔名碰撞和自動延展機制測試開始 ===")
    
    # 清理測試資料庫
    test_db_path = Path("data/test_collision.db")
    if test_db_path.exists():
        test_db_path.unlink()
        logger.info("清理舊的測試資料庫")
    
    try:
        # 運行所有測試
        tests = [
            ("基本短檔名生成", test_basic_short_key_generation()),
            ("碰撞處理機制", test_collision_handling()),
            ("強制碰撞場景", test_forced_collision_scenario()),
            ("長度升級機制", test_length_escalation()),
            ("並發生成測試", test_concurrent_generation()),
            ("資料庫整合測試", test_integration_with_database()),
        ]
        
        results = []
        for test_name, test_coro in tests:
            logger.info(f"\n--- 開始 {test_name} ---")
            try:
                result = await test_coro
                results.append((test_name, result))
                status = "✅ 通過" if result else "❌ 失敗"
                logger.info(f"{test_name}: {status}")
            except Exception as e:
                logger.error(f"{test_name} 執行失敗: {e}")
                results.append((test_name, False))
        
        # 總結
        logger.info("\n=== 測試總結 ===")
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅" if result else "❌"
            logger.info(f"{status} {test_name}")
        
        logger.info(f"\n總計: {passed}/{total} 個測試通過")
        
        if passed == total:
            print("\n🎉 所有短檔名碰撞和自動延展機制測試通過！")
            print("✅ 短檔名生成器碰撞處理正常")
            print("✅ 長度自動升級機制正常")
            print("✅ 保留關鍵字檢查正常")
            print("✅ 並發生成安全")
            print("✅ 資料庫整合重複檢測正常")
        else:
            print(f"\n⚠️  有 {total - passed} 個測試失敗，請檢查日誌")
            
    except Exception as e:
        logger.error(f"測試執行失敗: {e}")
        print(f"\n❌ 測試執行失敗: {e}")
    
    finally:
        # 清理測試資料庫
        if test_db_path.exists():
            test_db_path.unlink()
            logger.info("清理測試資料庫")


if __name__ == "__main__":
    asyncio.run(main())
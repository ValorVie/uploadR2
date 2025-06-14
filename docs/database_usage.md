# SQLite 資料庫使用指南

## 概述

uploadR2 專案整合了完整的 SQLite 資料庫系統，提供檔案記錄管理、重複檔案檢測、短檔名生成等功能。本文件詳述如何使用這些功能。

## 🚀 快速開始

### 1. 基本配置

在 `.env` 檔案中配置資料庫相關設定：

```bash
# 資料庫配置
DATABASE_PATH=data/uploadr2.db
DATABASE_POOL_SIZE=10

# 短檔名配置
ENABLE_SHORT_KEYS=true
SHORT_KEY_MIN_LENGTH=4
SHORT_KEY_CHARSET=alphanumeric_mixed
SHORT_KEY_SALT_LENGTH=16
MAX_SHORT_KEY_ATTEMPTS=100
```

### 2. 運行演示程式

```bash
# 運行完整的資料庫功能演示
uv run demo_database.py

# 運行基本測試
uv run test_simple.py

# 運行完整測試
uv run test_database.py
```

## 📚 核心功能

### 資料庫管理器 (DatabaseManager)

```python
from src.database import DatabaseManager, FileRecord

# 初始化資料庫管理器
db_manager = DatabaseManager("data/uploadr2.db", pool_size=10)

# 存儲檔案記錄
record = FileRecord(
    uuid_key="your-uuid-key",
    original_filename="example.jpg",
    file_extension=".jpg",
    file_size=1024000,
    mime_type="image/jpeg",
    sha512_hash="your-sha512-hash",
    r2_object_key="object-key.jpg",
    upload_url="https://your-domain.com/object-key.jpg"
)

file_id = db_manager.store_file_record(record)
print(f"檔案記錄已存儲，ID: {file_id}, 短檔名: {record.short_key}")
```

### 檔案記錄查詢

```python
# 通過 UUID 查詢
record = db_manager.get_file_by_uuid("your-uuid-key")

# 通過短檔名查詢  
record = db_manager.get_file_by_short_key("abc4")

# 檢查重複檔案
duplicate = db_manager.check_duplicate_by_hash("your-sha512-hash")
```

### 短檔名生成

```python
# 生成短檔名
short_key, length, salt = db_manager._short_key_generator.generate_short_key()
print(f"生成的短檔名: {short_key} (長度: {length})")

# 獲取短檔名統計
stats = db_manager._short_key_generator.get_statistics()
```

### 資料庫整合工具

```python
from src.utils.database_integration import create_database_integration
from src.config import load_config

# 創建資料庫整合實例
config = load_config()
db_integration = create_database_integration(config)

# 檢查重複檔案
duplicate_record = db_integration.check_duplicate_file(file_path)

# 創建檔案記錄
file_record = db_integration.create_file_record_from_path(
    file_path, r2_object_key, upload_url
)

# 存儲檔案記錄
file_id = db_integration.store_file_record(file_record)
```

## 🗄️ 資料表結構

### 主要資料表

#### 1. file_records（檔案記錄主表）
- `id`: 主鍵（自動遞增）
- `uuid_key`: UUID 金鑰（唯一，基於 SHA512）
- `short_key`: 短檔名（唯一，4-8 碼）
- `original_filename`: 原始檔名
- `file_extension`: 副檔名
- `file_size`: 檔案大小（位元組）
- `mime_type`: MIME 類型
- `sha512_hash`: SHA512 雜湊值
- `r2_object_key`: R2 對象金鑰
- `upload_url`: 完整訪問 URL
- `upload_timestamp`: 上傳時間
- `status`: 檔案狀態（active/deleted/archived）
- `access_count`: 訪問次數
- `metadata`: JSON 格式元數據
- `tags`: JSON 格式標籤

#### 2. short_key_sequences（短檔名序列表）
- `key_length`: 短檔名長度
- `current_sequence`: 當前序號
- `max_possible`: 最大可能數量
- `exhausted`: 是否已耗盡

#### 3. reserved_short_keys（保留短檔名表）
- `short_key`: 保留的短檔名
- `reason`: 保留原因

#### 4. file_operation_logs（操作日誌表）
- `file_record_id`: 檔案記錄 ID
- `operation_type`: 操作類型（upload/access/delete/update）
- `operation_details`: JSON 格式操作詳情
- `timestamp`: 操作時間

## 🔑 短檔名系統

### 特性
- **安全性**: 使用加密安全的隨機生成
- **防猜測**: 結合鹽值和多層隨機化
- **漸進式長度**: 從 4 位開始，需要時自動升級
- **高效能**: 每秒可生成數千個唯一短檔名
- **碰撞處理**: 自動重試和長度升級機制

### 字符集
- 數字: 0-9 (10 個)
- 小寫字母: a-z (26 個)  
- 大寫字母: A-Z (26 個)
- 總計: 62 個字符

### 容量計算
- 4 位: 62⁴ ≈ 1480萬個組合
- 5 位: 62⁵ ≈ 9.16億個組合
- 6 位: 62⁶ ≈ 568億個組合

## 📊 統計與監控

### 獲取統計資訊

```python
# 獲取完整統計
stats = db_manager.get_statistics()

print(f"總檔案數: {stats['total_files']}")
print(f"總大小: {stats['total_size_mb']} MB")
print(f"短檔名使用情況:")

for seq in stats['short_key_statistics']['sequences']:
    print(f"  長度 {seq['length']}: {seq['current']}/{seq['max_possible']} ({seq['usage_percent']}%)")
```

### 檔案類型分布

```python
for ext_info in stats['extension_distribution']:
    print(f"{ext_info['extension']}: {ext_info['count']} 個檔案")
```

## 🔧 進階使用

### 自定義短檔名生成

```python
from src.database.short_key_generator import ShortKeyGenerator

# 自定義生成器
generator = ShortKeyGenerator(db_manager)

# 批量生成
keys = []
for i in range(100):
    key, length, salt = generator.generate_short_key()
    keys.append(key)

print(f"生成了 {len(set(keys))} 個唯一短檔名")
```

### 資料庫遷移

```python
# 備份現有資料庫
import shutil
shutil.copy("data/uploadr2.db", "data/uploadr2.db.backup")

# 檢查資料庫架構版本
with db_manager.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1")
    version = cursor.fetchone()
    print(f"當前資料庫版本: {version[0] if version else '未知'}")
```

### 效能優化

```python
# 調整資料庫設定
with db_manager.get_connection() as conn:
    conn.execute("PRAGMA cache_size = 20000")  # 增加快取
    conn.execute("PRAGMA temp_store = MEMORY")  # 使用記憶體暫存
    conn.execute("PRAGMA mmap_size = 268435456")  # 256MB memory-mapped I/O
```

## 🛠️ 故障排除

### 常見問題

#### 1. 資料庫檔案未找到
```bash
# 確保 data 目錄存在
mkdir -p data

# 檢查檔案權限
ls -la data/uploadr2.db
```

#### 2. 短檔名生成失敗
```python
# 檢查序列狀態
stats = db_manager._short_key_generator.get_statistics()
for seq in stats['sequences']:
    if seq['exhausted']:
        print(f"長度 {seq['length']} 已耗盡")
```

#### 3. 資料庫鎖定
```python
# 檢查活動連接
import sqlite3
try:
    conn = sqlite3.connect("data/uploadr2.db", timeout=1.0)
    conn.close()
    print("資料庫可正常訪問")
except sqlite3.OperationalError as e:
    print(f"資料庫訪問錯誤: {e}")
```

### 日誌檢查

```python
from src.utils.logger import get_logger

# 啟用詳細日誌
logger = get_logger("database")
logger.setLevel("DEBUG")

# 檢查資料庫操作日誌
with db_manager.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT operation_type, COUNT(*) 
        FROM file_operation_logs 
        GROUP BY operation_type
    """)
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[1]} 次操作")
```

## 📝 最佳實踐

### 1. 資料庫維護
```python
# 定期執行 VACUUM 清理資料庫
with db_manager.get_connection() as conn:
    conn.execute("VACUUM")

# 更新統計資訊
with db_manager.get_connection() as conn:
    conn.execute("ANALYZE")
```

### 2. 備份策略
```python
import datetime
import shutil

# 自動備份
backup_name = f"uploadr2_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
shutil.copy("data/uploadr2.db", f"backups/{backup_name}")
```

### 3. 監控指標
- 資料庫檔案大小
- 短檔名使用率
- 查詢回應時間
- 錯誤率統計

## 🔗 相關文件

- [資料庫架構設計](database_architecture_design.md)
- [API 文件](../README.md)
- [配置指南](../src/config.py)

## 📞 技術支援

如果遇到問題，請檢查：
1. 資料庫檔案權限
2. 日誌檔案內容
3. 配置檔案設定
4. 系統資源使用情況

更多詳細資訊請參考完整的架構設計文件。
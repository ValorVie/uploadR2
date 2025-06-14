"""
資料庫架構定義

包含所有資料表、索引和觸發器的SQL定義。
"""

# 資料庫架構版本
SCHEMA_VERSION = 1

# 建立資料表的SQL語句
CREATE_TABLES_SQL = [
    """
    -- 檔案記錄主表
    CREATE TABLE IF NOT EXISTS file_records (
        -- 主鍵和基本標識
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid_key TEXT NOT NULL UNIQUE,              -- SHA512 雜湊轉換的UUID（主要標識）
        short_key TEXT UNIQUE,                      -- 短檔名（公開別名）
        
        -- 檔案基本資訊
        original_filename TEXT NOT NULL,            -- 原始檔名
        file_extension TEXT NOT NULL,               -- 副檔名（含.）
        file_size INTEGER NOT NULL,                 -- 檔案大小（bytes）
        mime_type TEXT NOT NULL,                    -- MIME類型
        
        -- 雜湊和校驗
        sha512_hash TEXT NOT NULL UNIQUE,           -- 完整SHA512雜湊值
        hash_algorithm TEXT NOT NULL DEFAULT 'sha512',  -- 雜湊算法
        
        -- 上傳資訊
        r2_object_key TEXT NOT NULL,               -- R2中的對象鍵
        upload_url TEXT NOT NULL,                  -- 完整的訪問URL
        upload_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        
        -- 短檔名生成資訊
        short_key_length INTEGER,                  -- 短檔名長度
        short_key_generation_salt TEXT,            -- 生成時使用的鹽值
        short_key_created_at DATETIME,             -- 短檔名創建時間
        
        -- 檔案狀態
        status TEXT NOT NULL DEFAULT 'active',     -- active, deleted, archived
        access_count INTEGER DEFAULT 0,            -- 訪問次數統計
        last_accessed_at DATETIME,                 -- 最後訪問時間
        
        -- 元數據
        metadata TEXT,                             -- JSON格式的額外元數據
        tags TEXT,                                 -- 標籤（JSON數組）
        
        -- 時間戳
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    """
    -- 短檔名序列管理表
    CREATE TABLE IF NOT EXISTS short_key_sequences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_length INTEGER NOT NULL UNIQUE,        -- 檔名長度（4, 5, 6...）
        current_sequence INTEGER NOT NULL DEFAULT 0,  -- 當前序號
        max_possible INTEGER NOT NULL,             -- 該長度的最大可能數量
        exhausted BOOLEAN NOT NULL DEFAULT FALSE,   -- 是否已用完
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    """
    -- 保留的短檔名表（避免生成系統保留字）
    CREATE TABLE IF NOT EXISTS reserved_short_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        short_key TEXT NOT NULL UNIQUE,
        reason TEXT NOT NULL,                      -- 保留原因
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    """
    -- 檔案操作日誌表
    CREATE TABLE IF NOT EXISTS file_operation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_record_id INTEGER NOT NULL,
        operation_type TEXT NOT NULL,              -- upload, access, delete, update
        operation_details TEXT,                    -- JSON格式的操作詳情
        client_ip TEXT,                           -- 客戶端IP
        user_agent TEXT,                          -- 用戶代理
        timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (file_record_id) REFERENCES file_records(id)
    )
    """,
    
    """
    -- 資料庫版本資訊表
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER NOT NULL,
        applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """
]

# 建立索引的SQL語句
CREATE_INDEXES_SQL = [
    # 主要查詢索引
    "CREATE INDEX IF NOT EXISTS idx_file_records_uuid_key ON file_records(uuid_key)",
    "CREATE INDEX IF NOT EXISTS idx_file_records_short_key ON file_records(short_key)",
    "CREATE INDEX IF NOT EXISTS idx_file_records_sha512_hash ON file_records(sha512_hash)",
    "CREATE INDEX IF NOT EXISTS idx_file_records_status ON file_records(status)",
    "CREATE INDEX IF NOT EXISTS idx_file_records_upload_timestamp ON file_records(upload_timestamp)",
    
    # 複合索引
    "CREATE INDEX IF NOT EXISTS idx_file_records_status_timestamp ON file_records(status, upload_timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_file_records_extension_status ON file_records(file_extension, status)",
    
    # 短檔名相關索引
    "CREATE INDEX IF NOT EXISTS idx_short_key_sequences_length ON short_key_sequences(key_length)",
    "CREATE INDEX IF NOT EXISTS idx_reserved_short_keys_key ON reserved_short_keys(short_key)",
    
    # 操作日誌索引
    "CREATE INDEX IF NOT EXISTS idx_file_operation_logs_file_id ON file_operation_logs(file_record_id)",
    "CREATE INDEX IF NOT EXISTS idx_file_operation_logs_timestamp ON file_operation_logs(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_file_operation_logs_operation_type ON file_operation_logs(operation_type)",
]

# 建立觸發器的SQL語句
CREATE_TRIGGERS_SQL = [
    """
    -- 更新 file_records updated_at 時間戳觸發器
    CREATE TRIGGER IF NOT EXISTS update_file_records_timestamp 
        AFTER UPDATE ON file_records
        FOR EACH ROW
    BEGIN
        UPDATE file_records SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END
    """,
    
    """
    -- 更新 short_key_sequences updated_at 時間戳觸發器
    CREATE TRIGGER IF NOT EXISTS update_short_key_sequences_timestamp 
        AFTER UPDATE ON short_key_sequences
        FOR EACH ROW
    BEGIN
        UPDATE short_key_sequences SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END
    """,
    
    """
    -- 訪問計數更新觸發器
    CREATE TRIGGER IF NOT EXISTS update_access_count
        AFTER INSERT ON file_operation_logs
        FOR EACH ROW
        WHEN NEW.operation_type = 'access'
    BEGIN
        UPDATE file_records 
        SET access_count = access_count + 1,
            last_accessed_at = CURRENT_TIMESTAMP
        WHERE id = NEW.file_record_id;
    END
    """,
    
    """
    -- 短檔名序列耗盡檢查觸發器
    CREATE TRIGGER IF NOT EXISTS check_sequence_exhaustion
        AFTER UPDATE ON short_key_sequences
        FOR EACH ROW
        WHEN NEW.current_sequence >= NEW.max_possible
    BEGIN
        UPDATE short_key_sequences 
        SET exhausted = TRUE 
        WHERE id = NEW.id;
    END
    """
]

# 初始化保留關鍵字
RESERVED_KEYS = [
    ("api", "API端點保留"),
    ("admin", "管理界面保留"),
    ("www", "網站根目錄保留"),
    ("help", "幫助頁面保留"),
    ("test", "測試用途保留"),
    ("null", "空值保留"),
    ("temp", "臨時檔案保留"),
    ("data", "數據目錄保留"),
    ("file", "檔案關鍵字保留"),
    ("user", "用戶關鍵字保留"),
    ("root", "根目錄保留"),
    ("sys", "系統關鍵字保留"),
    ("app", "應用關鍵字保留"),
    ("web", "網頁關鍵字保留"),
    ("img", "圖片關鍵字保留"),
    ("pic", "圖片關鍵字保留"),
    ("404", "錯誤頁面保留"),
    ("500", "錯誤頁面保留"),
    ("403", "錯誤頁面保留"),
    ("401", "錯誤頁面保留"),
]

def get_all_schema_sql():
    """獲取所有架構SQL語句"""
    return CREATE_TABLES_SQL + CREATE_INDEXES_SQL + CREATE_TRIGGERS_SQL
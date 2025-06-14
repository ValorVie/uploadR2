#!/usr/bin/env python3
"""
簡化的資料庫測試
"""

import tempfile
import shutil
from pathlib import Path

# 測試基本導入
try:
    from src.database import DatabaseManager
    print("✅ 資料庫模組導入成功")
except ImportError as e:
    print(f"❌ 導入失敗: {e}")
    exit(1)

# 測試資料庫初始化
temp_dir = Path(tempfile.mkdtemp())
db_path = temp_dir / "test.db"

try:
    print("測試資料庫初始化...")
    db_manager = DatabaseManager(str(db_path))
    print("✅ 資料庫初始化成功")
    
    print("測試短檔名生成...")
    short_key, length, salt = db_manager._short_key_generator.generate_short_key()
    print(f"✅ 短檔名生成成功: {short_key} (長度: {length})")
    
    db_manager.close()
    print("✅ 測試完成")
    
except Exception as e:
    print(f"❌ 測試失敗: {e}")
    import traceback
    traceback.print_exc()
    
finally:
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
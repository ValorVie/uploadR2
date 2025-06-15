# UploadR2

🚀 **具有完整 SQLite 資料庫支持的現代化檔案管理系統**

UploadR2 是一個高效、現代化的 Python 應用程式，專門設計用於將本地圖片批量上傳到 Cloudflare R2 存儲服務。整合了完整的 SQLite 資料庫系統，提供檔案記錄管理、短檔名生成、本地重複檔案檢測等企業級功能。支援並發上傳、智慧圖片處理、進度監控及完整的檔案操作追蹤。

## ✨ 功能特色

### 🚀 **高效能上傳**
- **並發上傳**：支援可配置的並發上傳數量 (1-20)
- **智慧重試**：自動重試失敗的上傳，支援自適應延遲
- **批量處理**：一次處理大量檔案，自動化整個工作流程

### 🖼️ **專業圖片處理**
- **自動壓縮**：智慧壓縮圖片，保持品質的同時減少檔案大小
- **尺寸調整**：自動調整圖片尺寸，支援最大尺寸限制
- **格式支援**：支援 JPEG、PNG、GIF、BMP、TIFF、WebP 等主流格式
- **EXIF 處理**：自動處理圖片方向和元數據

### 🛡️ **智慧防重複**
- **本地資料庫檢測**：使用 SQLite 資料庫存儲 SHA512 雜湊，實現高效本地重複檢測
- **跳過重複**：自動跳過已存在的檔案，避免重複上傳
- **檔案驗證**：上傳前驗證檔案完整性和格式

### 🗄️ **資料庫管理**
- **SQLite 整合**：完整的檔案記錄管理和操作日誌追蹤
- **檔案元數據**：存儲檔案大小、類型、上傳時間等完整資訊
- **訪問統計**：追蹤檔案訪問次數和最後訪問時間
- **標籤系統**：支援自定義標籤和元數據管理

### 🔑 **短檔名系統**
- **4-8位短檔名**：自動生成防猜測的短檔名別名
- **防碰撞機制**：智慧處理短檔名衝突和長度升級
- **加密安全生成**：使用加密安全的隨機演算法和鹽值
- **高容量設計**：4位可支援約1480萬個唯一檔名

### 📊 **完整監控**
- **即時進度**：使用 tqdm 顯示即時上傳進度
- **詳細統計**：提供成功率、用時、失敗原因等統計資訊
- **CSV 匯出**：自動匯出處理結果到 CSV 檔案
- **結構化日誌**：完整的操作日誌，便於問題追蹤

### 🔧 **靈活配置**
- **30+ 個可配置參數**：涵蓋上傳、處理、安全、資料庫等各個方面
- **多種檔名格式**：支援原始名稱、時間戳、UUID、自定義前綴
- **自定義域名**：支援自定義 CDN 域名生成完整 URL
- **資料庫配置**：完整的 SQLite 資料庫和短檔名系統配置

## 🔧 技術要求

- **Python 3.12+**
- **作業系統**：支援 Windows、macOS、Linux
- **記憶體**：建議至少 4GB（處理大量圖片時）
- **網路**：穩定的網際網路連接

## 📦 安裝指南

### 1. 取得專案

```bash
git clone https://github.com/your-username/uploadR2.git
cd uploadR2
```

### 2. 安裝依賴

#### 使用 uv（推薦）

```bash
# 安裝 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安裝依賴
uv sync
```

#### 使用 pip

```bash
# 建立虛擬環境
python -m venv venv

# 啟動虛擬環境
# Windows
venv\Scripts\activate
# macOS/Linux  
source venv/bin/activate

# 安裝依賴
pip install -e .
```

### 3. 配置環境

```bash
# 複製配置範例
cp .env.example .env

# 編輯配置檔案
nano .env  # 或使用您偏好的編輯器
```

## ⚙️ 配置設定

### Cloudflare R2 設定

從 [Cloudflare Dashboard](https://dash.cloudflare.com/) → R2 → Manage R2 API tokens 獲取以下資訊：

```env
# 必填：Cloudflare R2 連接配置
R2_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-access-key
R2_BUCKET_NAME=your-bucket-name
```

### 完整配置選項

| 配置項目 | 預設值 | 範圍 | 描述 |
|---------|--------|------|------|
| **連接設定** |
| `R2_ENDPOINT_URL` | - | 必填 | R2 端點 URL |
| `R2_ACCESS_KEY_ID` | - | 必填 | 存取金鑰 ID |
| `R2_SECRET_ACCESS_KEY` | - | 必填 | 秘密存取金鑰 |
| `R2_BUCKET_NAME` | - | 必填 | 儲存桶名稱 |
| **效能設定** |
| `MAX_CONCURRENT_UPLOADS` | 5 | 1-20 | 最大並發上傳數量 |
| `MAX_RETRIES` | 3 | 0-10 | 最大重試次數 |
| `RETRY_DELAY` | 1.0 | 0.1-60.0 | 重試延遲時間（秒） |
| **圖片處理** |
| `ENABLE_COMPRESSION` | true | - | 是否啟用圖片壓縮 |
| `COMPRESSION_QUALITY` | 85 | 1-100 | JPEG 壓縮品質 |
| `MAX_IMAGE_SIZE` | 2048 | 128-8192 | 最大圖片尺寸（像素） |
| `SUPPORTED_FORMATS` | jpg,jpeg,png,gif,bmp,tiff,webp | - | 支援的圖片格式 |
| **檔案管理** |
| `FILENAME_FORMAT` | original | original,timestamp,uuid,custom | 檔案命名格式 |
| `CUSTOM_PREFIX` | img_ | - | 自定義檔名前綴 |
| `MAX_FILE_SIZE_MB` | 50 | 1-500 | 最大檔案大小（MB） |
| **安全設定** |
| `CHECK_DUPLICATE` | true | - | 是否檢查重複檔案 |
| `HASH_ALGORITHM` | sha512 | sha256,sha512 | 雜湊演算法 |
| `VALIDATE_FILE_TYPE` | true | - | 是否驗證檔案類型 |
| **資料庫設定** |
| `DATABASE_PATH` | data/uploadr2.db | - | SQLite 資料庫檔案路徑 |
| `DATABASE_POOL_SIZE` | 10 | 1-50 | 資料庫連接池大小 |
| **短檔名設定** |
| `ENABLE_SHORT_KEYS` | true | - | 是否啟用短檔名功能 |
| `SHORT_KEY_MIN_LENGTH` | 4 | 3-10 | 短檔名最小長度 |
| `SHORT_KEY_CHARSET` | alphanumeric_mixed | - | 字符集類型 |
| `SHORT_KEY_SALT_LENGTH` | 16 | 8-32 | 生成短檔名使用的鹽值長度 |
| `MAX_SHORT_KEY_ATTEMPTS` | 100 | 10-1000 | 短檔名生成最大嘗試次數 |
| **介面設定** |
| `SHOW_PROGRESS` | true | - | 是否顯示進度條 |
| `LOG_LEVEL` | INFO | DEBUG,INFO,WARNING,ERROR,CRITICAL | 日誌等級 |
| `CUSTOM_DOMAIN` | - | 選填 | 自定義 CDN 域名 |

## 🚀 使用方法

### 基本使用

1. **準備圖片**：將圖片放入 `images/original/` 目錄
2. **執行上傳**：

```bash
python main.py
```

### 高級使用

#### 測試連接

```bash
python main.py --test-connection
```

#### 預覽模式（不實際上傳）

```bash
python main.py --dry-run
```

#### 使用自定義配置

```bash
python main.py --config production.env
```

#### 調整並發數量

```bash
python main.py --max-concurrent 10
```

#### 清理暫存檔案

```bash
python main.py --cleanup
```

#### 靜默模式

```bash
python main.py --no-progress --log-level WARNING
```

#### 資料庫功能演示

```bash
# 運行完整的資料庫功能演示
uv run test/demo_database.py

# 運行資料庫測試
uv run test/test_database.py

# 運行簡單測試
uv run test/test_simple.py
```

## 📁 檔案結構

```
uploadR2/
├── src/                     # 核心源碼
│   ├── __init__.py         # 套件初始化
│   ├── config.py           # 配置管理（Pydantic 驗證）
│   ├── batch_processor.py  # 批量處理協調器
│   ├── r2_uploader.py      # R2 上傳器（boto3 + asyncio）
│   ├── progress_tracker.py # 進度追蹤器（tqdm + 統計）
│   ├── database/           # 資料庫相關模組
│   │   ├── __init__.py     # 資料庫套件初始化
│   │   ├── database_manager.py # 資料庫管理器
│   │   ├── short_key_generator.py # 短檔名生成器
│   │   ├── models.py       # 資料模型定義
│   │   ├── schema.py       # 資料庫架構
│   │   └── exceptions.py   # 資料庫異常類
│   └── utils/              # 工具模組
│       ├── __init__.py
│       ├── file_utils.py   # 檔案操作工具
│       ├── image_processor.py # 圖片處理（Pillow）
│       ├── hash_utils.py   # 雜湊計算工具
│       ├── database_integration.py # 資料庫整合工具
│       └── logger.py       # 日誌管理工具
├── test/                   # 測試檔案
│   ├── demo_database.py    # 資料庫功能演示
│   ├── test_database.py    # 資料庫測試
│   ├── test_simple.py      # 簡單測試
│   └── test_*.py          # 其他測試檔案
├── docs/                   # 文件目錄
│   ├── database_architecture_design.md # 資料庫架構設計
│   ├── database_usage.md   # 資料庫使用指南
│   └── *.md               # 其他文件
├── data/                   # 資料目錄
│   └── uploadr2.db         # SQLite 資料庫檔案
├── images/                 # 圖片目錄
│   ├── original/          # 原始圖片（使用者放置）
│   └── transfer/          # 處理後圖片（自動生成）
├── logs/                  # 日誌目錄
├── results/               # 結果輸出目錄
├── main.py               # 主程式入口
├── pyproject.toml        # 專案配置和依賴
├── .env.example         # 環境變數範例
├── .gitignore           # Git 忽略檔案
└── README.md            # 本檔案
```

## 🖼️ 支援的圖片格式

| 格式 | 副檔名 | 支援壓縮 | 支援透明度 | 備註 |
|------|--------|----------|------------|------|
| JPEG | `.jpg`, `.jpeg` | ✅ | ❌ | 最佳壓縮比 |
| PNG | `.png` | ⚠️ | ✅ | 支援透明度 |
| WebP | `.webp` | ✅ | ✅ | 現代格式 |
| GIF | `.gif` | ❌ | ✅ | 支援動畫 |
| BMP | `.bmp` | ❌ | ❌ | Windows 點陣圖 |
| TIFF | `.tiff`, `.tif` | ❌ | ✅ | 高品質格式 |

## 🗄️ 資料庫系統

UploadR2 整合了完整的 SQLite 資料庫系統，提供檔案記錄管理、重複檢測、短檔名生成等功能。

### 🏗️ 資料表結構

#### 主要資料表
- **file_records**: 檔案記錄主表，存儲完整的檔案資訊
- **short_key_sequences**: 短檔名序列管理，追蹤各長度的使用狀況
- **reserved_short_keys**: 保留短檔名表，避免生成系統保留字
- **file_operation_logs**: 檔案操作日誌，記錄所有操作歷史

### 🔑 短檔名系統

#### 特性與優勢
- **防猜測設計**: 使用加密安全的隨機生成演算法
- **漸進式長度**: 從4位開始，需要時自動升級到更長位數
- **高容量支援**: 4位支援約1480萬個組合，5位支援約9.16億個組合
- **碰撞處理**: 智慧衝突檢測和自動重試機制

#### 容量說明
| 長度 | 理論組合數 | 實際可用數 | 適用場景 |
|------|------------|------------|----------|
| 4位 | 62⁴ ≈ 1,480萬 | 約1,470萬 | 小型到中型應用 |
| 5位 | 62⁵ ≈ 9.16億 | 約9.15億 | 大型應用 |
| 6位 | 62⁶ ≈ 568億 | 約567億 | 超大型應用 |

### 📊 資料庫使用示例

```python
from src.database import DatabaseManager, FileRecord
from src.utils.database_integration import create_database_integration

# 初始化資料庫管理器
db_manager = DatabaseManager("data/uploadr2.db")

# 創建檔案記錄
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

# 存儲記錄（自動生成短檔名）
file_id = db_manager.store_file_record(record)
print(f"檔案已存儲，短檔名: {record.short_key}")

# 查詢檔案
record = db_manager.get_file_by_short_key("abc4")
duplicate = db_manager.check_duplicate_by_hash("your-sha512-hash")

# 獲取統計資訊
stats = db_manager.get_statistics()
print(f"總檔案數: {stats['total_files']}")
```

### 🔧 資料庫維護

```bash
# 檢查資料庫狀態
uv run test/demo_database.py

# 運行完整測試
uv run test/test_database.py

# 檢查短檔名統計
python -c "
from src.database import DatabaseManager
db = DatabaseManager()
stats = db.get_statistics()
print('短檔名使用情況:', stats['short_key_statistics'])
"
```

## 🎛️ 命令列選項

```bash
python main.py [選項]

選項:
  --config PATH             配置檔案路徑（預設：.env）
  --dry-run                只掃描和驗證檔案，不實際上傳
  --cleanup                清理 transfer 目錄後退出
  --test-connection        測試 R2 連接後退出
  --log-level LEVEL        日誌等級（DEBUG|INFO|WARNING|ERROR|CRITICAL）
  --max-concurrent N       最大並發上傳數量（覆蓋配置檔案）
  --no-progress           不顯示進度條
  -h, --help              顯示說明訊息
```

### 使用範例

```bash
# 基本上傳
python main.py

# 高並發上傳（生產環境）
python main.py --max-concurrent 15 --log-level WARNING

# 開發除錯
python main.py --dry-run --log-level DEBUG

# 自動化腳本
python main.py --no-progress --config production.env
```

## 🔧 故障排除

### 常見問題

#### 1. 連接失敗

**錯誤**：`❌ R2連接測試失敗`

**解決方案**：
- 檢查 `.env` 檔案中的 R2 配置是否正確
- 確認網路連接正常
- 驗證 API 金鑰是否有效且未過期

```bash
# 測試連接
python main.py --test-connection
```

#### 2. 檔案處理失敗

**錯誤**：`圖片處理失敗`

**解決方案**：
- 檢查圖片檔案是否損壞
- 確認檔案格式是否受支援
- 檢查檔案大小是否超過限制

```bash
# 驗證檔案
python main.py --dry-run --log-level DEBUG
```

#### 3. 記憶體不足

**錯誤**：`MemoryError`

**解決方案**：
- 降低並發數量：`--max-concurrent 3`
- 減少最大圖片尺寸：`MAX_IMAGE_SIZE=1024`
- 分批處理大量檔案

#### 4. 權限錯誤

**錯誤**：`Permission denied`

**解決方案**：
- 檢查 R2 儲存桶的寫入權限
- 確認本地檔案的讀取權限
- 驗證目錄的建立權限

#### 5. 資料庫連接失敗

**錯誤**：`sqlite3.OperationalError: database is locked`

**解決方案**：
```bash
# 檢查資料庫檔案是否被其他程序使用
lsof data/uploadr2.db  # Linux/macOS
# 或重啟應用程式

# 確保資料庫目錄存在且有寫入權限
mkdir -p data
chmod 755 data
```

#### 6. 短檔名生成失敗

**錯誤**：`ShortKeyExhaustedError`

**解決方案**：
```python
# 檢查短檔名使用情況
from src.database import DatabaseManager
db = DatabaseManager()
stats = db._short_key_generator.get_statistics()

# 如果某個長度已耗盡，系統會自動升級到下一個長度
print("當前可用長度:", [s for s in stats['sequences'] if not s['exhausted']])
```

#### 7. 資料庫檔案損壞

**錯誤**：`sqlite3.DatabaseError: database disk image is malformed`

**解決方案**：
```bash
# 嘗試修復資料庫
sqlite3 data/uploadr2.db ".recover" | sqlite3 data/uploadr2_recovered.db

# 或從備份恢復
cp data/uploadr2.db.backup data/uploadr2.db
```

### 日誌分析

啟用詳細日誌以診斷問題：

```bash
python main.py --log-level DEBUG
```

日誌檔案位置：`logs/uploadr2.log`

## 🚀 開發資訊

### 開發環境設定

```bash
# 安裝開發依賴
uv sync

# 程式碼格式化
black src/
isort src/

# 型別檢查
mypy src/

# 執行測試
pytest
```

### 專案架構

UploadR2 採用模組化設計：

- **配置層**：使用 Pydantic 進行型別安全的配置管理
- **處理層**：批量處理器協調各個組件
- **上傳層**：基於 boto3 的異步 R2 上傳器
- **工具層**：檔案處理、圖片處理、雜湊計算等工具

### 技術堆疊

| 類別 | 技術 | 用途 |
|------|------|------|
| **核心語言** | Python 3.12+ | 主要開發語言 |
| **異步處理** | asyncio | 並發上傳和 I/O 操作 |
| **配置管理** | Pydantic | 型別安全的配置驗證 |
| **資料庫** | SQLite | 本地資料庫存儲和檔案記錄管理 |
| **資料庫管理** | 連接池 | 高效的資料庫連接管理 |
| **短檔名算法** | 加密安全隨機生成 | 防猜測短檔名生成系統 |
| **雲端存儲** | boto3 | Cloudflare R2 API 客戶端 |
| **圖片處理** | Pillow (PIL) | 圖片壓縮和格式轉換 |
| **進度顯示** | tqdm | 即時進度條和統計 |
| **檔案 I/O** | aiofiles | 異步檔案操作 |
| **環境管理** | python-dotenv | 環境變數載入 |

### 貢獻指南

1. Fork 本專案
2. 建立功能分支：`git checkout -b feature/amazing-feature`
3. 提交變更：`git commit -m 'Add: 新增驚人功能'`
4. 推送分支：`git push origin feature/amazing-feature`
5. 開啟 Pull Request

### 程式碼風格

- 使用 [Black](https://black.readthedocs.io/) 進行程式碼格式化
- 使用 [isort](https://pycqa.github.io/isort/) 進行 import 排序
- 使用 [MyPy](https://mypy.readthedocs.io/) 進行型別檢查
- 遵循 [PEP 8](https://pep8.org/) 程式碼風格指南

## 📄 授權資訊

本專案採用 **MIT 授權條款** - 詳見 [LICENSE](LICENSE) 檔案

```
MIT License

Copyright (c) 2025 UploadR2

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 🔗 相關連結

### 📚 專案文件
- [資料庫架構設計](docs/database_architecture_design.md)
- [資料庫使用指南](docs/database_usage.md)

### 🛠️ 技術文件
- [Cloudflare R2 文件](https://developers.cloudflare.com/r2/)
- [Python 官方網站](https://www.python.org/)
- [boto3 文件](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [Pillow 文件](https://pillow.readthedocs.io/)
- [SQLite 官方文件](https://sqlite.org/docs.html)
- [Pydantic 文件](https://pydantic-docs.helpmanual.io/)

## 🆘 支援與回饋

- **問題回報**：[建立 Issue](https://github.com/your-username/uploadR2/issues)
- **功能建議**：[功能請求](https://github.com/your-username/uploadR2/issues/new?template=feature_request.md)
- **安全問題**：請私下聯繫維護者

---

**UploadR2** - 讓圖片上傳變得簡單高效 🚀
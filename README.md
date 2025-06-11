# UploadR2

批量上傳圖片到Cloudflare R2存儲的工具

## 專案概述

UploadR2是一個高效的Python工具，專門用於將本地圖片批量上傳到Cloudflare R2存儲服務。支援圖片壓縮、格式轉換、並發上傳等功能。

## 功能特色

- 🚀 **並發上傳**: 支援多執行緒並發上傳，提高傳輸效率
- 🖼️ **圖片處理**: 自動壓縮、調整大小、格式轉換
- 🔧 **靈活配置**: 豐富的配置選項，滿足不同使用需求
- 📊 **進度顯示**: 即時顯示上傳進度和統計資訊
- 🛡️ **錯誤處理**: 完善的錯誤處理和重試機制
- 📝 **日誌記錄**: 詳細的操作日誌，便於問題追蹤

## 專案結構

```
uploadR2/
├── src/                    # 源碼目錄
│   ├── __init__.py
│   ├── config.py          # 配置管理
│   └── utils/             # 工具模組
│       ├── __init__.py
│       ├── file_utils.py  # 檔案工具
│       ├── image_processor.py # 圖片處理
│       └── logger.py      # 日誌工具
├── images/                # 圖片目錄
│   ├── original/          # 原始圖片
│   └── transfer/          # 處理後圖片
├── logs/                  # 日誌目錄
├── .env.example          # 環境變數範例
├── .gitignore
├── pyproject.toml        # 專案配置
└── README.md
```

## 快速開始

### 1. 環境需求

- Python 3.12+
- pip 或 uv

### 2. 安裝依賴

```bash
# 使用pip
pip install -e .

# 或使用uv（推薦）
uv sync
```

### 3. 配置環境

1. 複製環境變數範例檔案：
```bash
cp .env.example .env
```

2. 編輯`.env`檔案，填入您的Cloudflare R2配置：
```env
R2_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-access-key
R2_BUCKET_NAME=your-bucket-name
```

### 4. 準備圖片

將要上傳的圖片放入`images/original/`目錄中。

### 5. 執行上傳

```bash
python main.py
```

## 配置說明

### 環境變數

| 變數名稱 | 說明 | 預設值 |
|---------|------|--------|
| `R2_ENDPOINT_URL` | R2端點URL | 必填 |
| `R2_ACCESS_KEY_ID` | 存取金鑰ID | 必填 |
| `R2_SECRET_ACCESS_KEY` | 秘密存取金鑰 | 必填 |
| `R2_BUCKET_NAME` | 儲存桶名稱 | 必填 |
| `MAX_CONCURRENT_UPLOADS` | 最大並發數 | 5 |
| `MAX_RETRIES` | 最大重試次數 | 3 |
| `ENABLE_COMPRESSION` | 啟用圖片壓縮 | true |
| `COMPRESSION_QUALITY` | 壓縮品質(1-100) | 85 |
| `MAX_IMAGE_SIZE` | 最大圖片尺寸 | 2048 |

詳細配置選項請參考`.env.example`檔案。

## 支援的圖片格式

- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- BMP (.bmp)
- TIFF (.tiff)
- WebP (.webp)

## 開發環境

### 安裝開發依賴

```bash
# 使用pip
pip install -e ".[dev]"

# 使用uv
uv sync --group dev
```

### 程式碼格式化

```bash
black src/
isort src/
```

### 型別檢查

```bash
mypy src/
```

## 貢獻指南

1. Fork本專案
2. 建立功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交變更 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 開啟Pull Request

## 授權

本專案採用MIT授權條款 - 詳見 [LICENSE](LICENSE) 檔案

## 支援

如有問題或建議，請建立[Issue](https://github.com/your-username/uploadr2/issues)。
# 部署指南

## 部署架構

```
LINE App  →  LINE Platform  →  Webhook (HTTPS)
                                    ↓
                            Google Cloud Run
                            (本 Flask 後端)
                                    ↓
                            Google Sheets API
                                    ↓
                            Google Sheets 試算表
```

---

## 前置準備（一次性設定）

### 步驟 1：建立 LINE Official Account

1. 前往 [LINE Developers Console](https://developers.line.biz/)
2. 建立新的 Provider → 建立 Messaging API Channel
3. 記錄以下資訊：
   - **Channel Secret**（Basic settings 頁面）
   - **Channel Access Token**（Messaging API 頁面 → 長效 Token）
4. 關閉「自動回覆訊息」與「加入好友的歡迎訊息」

### 步驟 2：建立 Google Sheets

1. 開啟已準備好的 `family_line_oa_template.xlsx`
2. 上傳至 Google Drive → 轉換為 Google Sheets 格式
3. 記錄試算表網址中的 **Spreadsheet ID**
   ```
   https://docs.google.com/spreadsheets/d/【這段就是 ID】/edit
   ```

### 步驟 3：建立 Google Service Account

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 建立新專案（或使用現有）
3. 啟用 **Google Sheets API** 與 **Google Drive API**
4. 建立 Service Account：IAM 與管理員 → 服務帳戶 → 建立
5. 下載金鑰（JSON 格式），即 `credentials.json`
6. **將 Service Account 的 Email 加入 Google Sheets 編輯者**
   - 開啟試算表 → 共用 → 貼上 Service Account email → 設為「編輯者」

---

## 部署至 Google Cloud Run（推薦）

### 步驟 4：安裝 Google Cloud SDK

```bash
# macOS
brew install --cask google-cloud-sdk

# 登入
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 步驟 5：部署

```bash
cd line_oa_backend

# 建立 & 部署（第一次）
gcloud run deploy family-line-oa \
  --source . \
  --region asia-east1 \
  --allow-unauthenticated \
  --set-env-vars="LINE_CHANNEL_ACCESS_TOKEN=你的Token" \
  --set-env-vars="LINE_CHANNEL_SECRET=你的Secret" \
  --set-env-vars="GOOGLE_SPREADSHEET_ID=你的試算表ID" \
  --set-env-vars="GOOGLE_SPREADSHEET_URL=https://docs.google.com/spreadsheets/d/你的ID/edit" \
  --set-env-vars="ALLOWED_GROUP_ID=群組ID" \
  --set-env-vars="GOOGLE_CREDENTIALS_JSON=$(cat credentials.json | tr -d '\n')"
```

部署完成後，取得服務網址：
```
https://family-line-oa-xxxxxxxxxx-de.a.run.app
```

### 步驟 6：設定 LINE Webhook

1. 回到 LINE Developers Console
2. Messaging API → Webhook settings
3. Webhook URL 填入：`https://family-line-oa-xxxxxxxxxx-de.a.run.app/webhook`
4. 點擊「Verify」確認連線成功

### 步驟 7：設定 RichMenu

```bash
# 先準備 2500x843 px 的 PNG 圖片，命名為 richmenu_image.png
# 圖片建議分四格，標示：💰公積金 / 📋活動費用 / 👤我的紀錄 / 📊查看報表

export LINE_CHANNEL_ACCESS_TOKEN=你的Token
export GOOGLE_SPREADSHEET_URL=https://docs.google.com/spreadsheets/d/你的ID/edit
python setup_richmenu.py
```

### 步驟 8：取得群組 ID

1. 將 Bot 加入家族 LINE 群組
2. 任意在群組傳訊息
3. 查看 Cloud Run Log（gcloud run logs read）
4. 找到 `group_id` 欄位，格式為 `Cxxxxxxxxxx`
5. 更新環境變數：
   ```bash
   gcloud run services update family-line-oa \
     --region asia-east1 \
     --set-env-vars="ALLOWED_GROUP_ID=Cxxxxxxxxxx"
   ```

---

## 本地開發測試

```bash
# 安裝依賴
pip install -r requirements.txt

# 複製環境變數範本
cp .env.example .env
# 編輯 .env 填入實際值

# 啟動本地伺服器
flask run --port 8080

# 使用 ngrok 建立公開 HTTPS tunnel（測試用）
ngrok http 8080
# 將 ngrok 網址設為 LINE Webhook URL
```

---

## 更新部署

```bash
# 之後只需重新 deploy
gcloud run deploy family-line-oa --source . --region asia-east1
```

---

## 費用估算

| 服務 | 免費額度 | 家族使用量 |
|------|---------|---------|
| Cloud Run | 每月 200 萬次請求、180,000 vCPU 秒 | 遠低於免費額度 |
| Google Sheets API | 每天 300 次讀寫/秒 | 遠低於限制 |
| LINE Messaging API | 每月 200 則推播（免費方案） | 需注意推播次數 |

> 💡 家族規模（10-30人）幾乎不會產生任何費用。

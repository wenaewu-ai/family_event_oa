FROM python:3.11-slim

WORKDIR /app

# 安裝依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製程式碼
COPY . .

# 啟動 gunicorn（Cloud Run 預設使用 PORT 環境變數）
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 60 app:app

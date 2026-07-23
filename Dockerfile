# 使用 Playwright 官方預先裝好 Chromium 及所有系統依賴的鏡像
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# 設定工作目錄
WORKDIR /app

# 複製專案檔案
COPY . /app

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 暴露 Flask Port (5131)
EXPOSE 5131

# 啟動 Bot
CMD ["python3", "main.py"]

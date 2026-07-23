FROM mcr.microsoft.com/playwright/python:v1.61.0-jammy

# 強制 Python 即時輸出 Log，不要暫存
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 5131
CMD ["python3", "main.py"]

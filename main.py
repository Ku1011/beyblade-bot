import os
import time
import threading
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from flask import Flask

# -------------------------------------------------------------------
# 1. 基本設定
# -------------------------------------------------------------------
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1529665191586041876/adK2AjMfMcScpiskG32xmthHpU-CpAsnQ_ymncITfBmYip1DoqPL3qJLaHVO2maVjUXJ"

# ⚡ 巡檢目標間隔 (秒)
CHECK_INTERVAL = 10

# 🎯 監控的爆旋陀螺搜尋/分類頁面
CATEGORY_URL = "https://www.toysrus.com.hk/zh-hk/search/?q=Beyblade"

# 📦 用來儲存已紀錄商品的 Set (防重複通知)
seen_product_urls = set()
is_first_run = True  # 標記是否為第一次啟動

# -------------------------------------------------------------------
# 2. Flask Web Server (維持 Render Health Check)
# -------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return f"🤖 爆旋陀螺 全新商品上架監控 Bot 運作中！當前時間: {datetime.now().strftime('%H:%M:%S')}"

def run_flask():
    port = int(os.environ.get("PORT", 5131))
    app.run(host="0.0.0.0", port=port)

# -------------------------------------------------------------------
# 3. Discord 推播通知功能
# -------------------------------------------------------------------
def send_discord_notify(title, item_url):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = {
        "content": (
            f"🚨 **【爆旋陀螺 ✨ 全新商品上架通知】** 🚨\n"
            f"📦 **商品名稱：** {title}\n"
            f"⏰ **時間：** {now_str}\n"
            f"🔗 **搶購連結：** {item_url}"
        )
    }
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=message)
        if response.status_code in [200, 204]:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ [{title}] Discord 通知發送成功！", flush=True)
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Discord 通知發送失敗，Status Code: {response.status_code}", flush=True)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 發送 Discord 通知時發生錯誤: {e}", flush=True)

# -------------------------------------------------------------------
# 4. 全新商品掃描邏輯
# -------------------------------------------------------------------
def check_new_products(session):
    global is_first_run
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-HK,zh-TW;q=0.9,zh;q=0.8,en-US;q=0.7,en;q=0.6"
    }

    try:
        t_check = datetime.now().strftime("%H:%M:%S")
        print(f"[{t_check}] 🔍 正在掃描分類頁面，尋找新商品...", flush=True)

        response = session.get(CATEGORY_URL, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"[{t_check}] ⚠️ 網頁回應異常 HTTP {response.status_code}", flush=True)
            return

        soup = BeautifulSoup(response.text, "html.parser")
        
        # 尋找所有商品標題與連結 (Toys "R" Us 網頁商品連結包含 '.html')
        product_elements = soup.find_all("a", href=True)
        current_found_count = 0

        for a in product_elements:
            href = a["href"]
            title = a.get_text().strip()

            # 過濾出真正的商品頁面連結 (避開導覽列與分頁連結)
            if ".html" in href and "beyblade" in href.lower() and len(title) > 3:
                full_url = href if href.startswith("http") else f"https://www.toysrus.com.hk{href}"
                
                # 首次執行：建立基準清單，不發送通知
                if is_first_run:
                    seen_product_urls.add(full_url)
                    current_found_count += 1
                else:
                    # 後續巡檢：發現不在 seen 清單中的全新網址！
                    if full_url not in seen_product_urls:
                        print(f"[{t_check}] 🎉🎉🎉 發現全新商品上架：[{title}]", flush=True)
                        send_discord_notify(title, full_url)
                        seen_product_urls.add(full_url)  # 加入歷史清單

        if is_first_run:
            print(f"[{t_check}] ⚙️ 初始化完成！成功建立 baseline，共記錄 {current_found_count} 個現有商品。", flush=True)
            is_first_run = False

    except Exception as e:
        t_err = datetime.now().strftime("%H:%M:%S")
        print(f"[{t_err}] ⚠️ 檢查過程出錯: {e}", flush=True)

# -------------------------------------------------------------------
# 5. 主巡檢 Loop
# -------------------------------------------------------------------
def monitor_loop():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 全新商品動態監控系統啟動...", flush=True)
    session = requests.Session()

    while True:
        start_time = time.time()
        check_new_products(session)

        elapsed = time.time() - start_time
        sleep_time = max(0, CHECK_INTERVAL - elapsed)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏱️ 本輪掃描耗時 {elapsed:.2f} 秒。等待 {sleep_time:.2f} 秒...", flush=True)
        time.sleep(sleep_time)

# -------------------------------------------------------------------
# 6. 主程式入口
# -------------------------------------------------------------------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    monitor_loop()

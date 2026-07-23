import os
import time
import threading
from datetime import datetime
import requests
from flask import Flask
from playwright.sync_api import sync_playwright

# -------------------------------------------------------------------
# 1. 基本設定
# -------------------------------------------------------------------
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1529665191586041876/adK2AjMfMcScpiskG32xmthHpU-CpAsnQ_ymncITfBmYip1DoqPL3qJLaHVO2maVjUXJ"

# ⚡ 檢查循環間隔時間 (秒) - 設定為每 5 秒巡檢一次
CHECK_INTERVAL = 5

# 監控的爆旋陀螺商品清單
TARGET_ITEMS = [
    {
        "name": "BX-00 翔龍神劍3-60F V2",
        "url": "https://www.toysrus.com.hk/zh-hk/pre-order-beyblade-x-bx-00-dragonsword-3-60f-2.0-expected-august-2026-10159693.html"
    },
    {
        "name": "BX-57 三陀螺對戰盒 (黑色版)",
        "url": "https://www.toysrus.com.hk/zh-hk/pre-order-beyblade-x-bx-51-3-on-3-deck-case-black-version-expected-august-2026-10159697.html"
    },
    {
        "name": "UX-21 煉獄下界三陀螺套裝",
        "url": "https://www.toysrus.com.hk/zh-hk/pre-order-beyblade-x-ux-21-hellsnether-deck-set-expected-august-2026-10159699.html"
    }
]

# -------------------------------------------------------------------
# 2. Flask Web Server (維持 Render Health Check)
# -------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return f"🤖 爆旋陀螺 5 秒極速監控系統運作中！當前時間: {datetime.now().strftime('%H:%M:%S')}"

def run_flask():
    port = int(os.environ.get("PORT", 5131))
    app.run(host="0.0.0.0", port=port)

# -------------------------------------------------------------------
# 3. Discord 推播通知功能
# -------------------------------------------------------------------
def send_discord_notify(item_name, item_url):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = {
        "content": (
            f"🚨 **【爆旋陀螺返貨/預購通知】** 🚨\n"
            f"📦 **商品：** {item_name}\n"
            f"⏰ **時間：** {now_str}\n"
            f"🔗 **搶購連結：** {item_url}"
        )
    }
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=message)
        if response.status_code in [200, 204]:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ [{item_name}] Discord 通知發送成功！", flush=True)
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Discord 通知發送失敗，Status Code: {response.status_code}", flush=True)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 發送 Discord 通知時發生錯誤: {e}", flush=True)

# -------------------------------------------------------------------
# 4. Playwright 多商品極速監控主邏輯
# -------------------------------------------------------------------
def monitor_loop():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 爆旋陀螺 5 秒極速監控系統啟動...", flush=True)
    
    notified_items = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        while True:
            start_time = time.time()
            now_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{now_time}] 🔄 [巡檢開始] 正檢查 {len(TARGET_ITEMS)} 個商品庫存...", flush=True)

            for item in TARGET_ITEMS:
                name = item["name"]
                url = item["url"]
                t_check = datetime.now().strftime("%H:%M:%S")

                print(f"[{t_check}] 🔍 正在載入並檢查: [{name}]", flush=True)

                try:
                    # 使用 domcontentloaded 快速完成頁面載入
                    page.goto(url, timeout=15000, wait_until="domcontentloaded")
                    
                    is_available = (
                        page.locator("text=預購").is_visible() or 
                        page.locator("text=加入購物車").is_visible() or
                        page.locator("text=Pre-order").is_visible()
                    )

                    t_res = datetime.now().strftime("%H:%M:%S")
                    if is_available:
                        print(f"[{t_res}] 🎉🎉🎉 [{name}] 開放預購/有貨！", flush=True)
                        if not notified_items.get(url, False):
                            send_discord_notify(name, url)
                            notified_items[url] = True
                        else:
                            print(f"[{t_res}] ℹ️ [{name}] 已發送過通知，跳過。", flush=True)
                    else:
                        print(f"[{t_res}] ❌ [{name}] 目前無貨", flush=True)
                        notified_items[url] = False

                except Exception as e:
                    t_err = datetime.now().strftime("%H:%M:%S")
                    print(f"[{t_err}] ⚠️ 檢查 [{name}] 超時或出錯: {e}", flush=True)

            # 計算當前巡檢總耗時並精確計時 5 秒
            elapsed = time.time() - start_time
            sleep_time = max(0, CHECK_INTERVAL - elapsed)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏱️ 本輪耗時 {elapsed:.2f} 秒。等待 {sleep_time:.2f} 秒後進行下一輪...", flush=True)
            time.sleep(sleep_time)

# -------------------------------------------------------------------
# 5. 主程式入口
# -------------------------------------------------------------------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    monitor_loop()

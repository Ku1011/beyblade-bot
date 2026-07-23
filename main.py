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

# 檢查循環間隔時間 (秒) - 每 60 秒輪流檢查一次
CHECK_INTERVAL = 60

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
    return "🤖 爆旋陀螺 24/7 多商品監控 Bot 運作中！"

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
        if response.status_code == 204 or response.status_code == 200:
            print(f"✅ [{item_name}] Discord 通知發送成功！", flush=True)
        else:
            print(f"⚠️ Discord 通知發送失敗，Status Code: {response.status_code}", flush=True)
    except Exception as e:
        print(f"❌ 發送 Discord 通知時發生錯誤: {e}", flush=True)

# -------------------------------------------------------------------
# 4. Playwright 多商品庫存監控主邏輯
# -------------------------------------------------------------------
def monitor_loop():
    print("🤖 爆旋陀螺 3 商品自動監控系統啟動...", flush=True)
    
    # 記錄已通知過的商品，避免重複洗版
    notified_items = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        while True:
            print(f"\n--- 🔄 開始新一輪巡檢 ({datetime.now().strftime('%H:%M:%S')}) ---", flush=True)

            for item in TARGET_ITEMS:
                name = item["name"]
                url = item["url"]

                print(f"🔍 正在檢查: [{name}]...", flush=True)

                try:
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    time.sleep(2)  # 等待 JS 動態元件載入

                    # 判斷庫存/預購狀態
                    is_available = (
                        page.locator("text=預購").is_visible() or 
                        page.locator("text=加入購物車").is_visible() or
                        page.locator("text=Pre-order").is_visible()
                    )

                    if is_available:
                        print(f"🎉 🎉 🎉 [{name}] 有貨/開放預購啦！", flush=True)
                        
                        if not notified_items.get(url, False):
                            send_discord_notify(name, url)
                            notified_items[url] = True
                        else:
                            print(f"ℹ️ [{name}] 已經通知過，跳過重複發送。", flush=True)
                    else:
                        print(f"❌ [{name}] 暫時缺貨/未開放", flush=True)
                        notified_items[url] = False

                except Exception as e:
                    print(f"⚠️ 檢查 [{name}] 時發生例外狀況: {e}", flush=True)

                time.sleep(2)

            print(f"😴 一輪檢查完畢，等待 {CHECK_INTERVAL} 秒後進行下一輪...", flush=True)
            time.sleep(CHECK_INTERVAL)

# -------------------------------------------------------------------
# 5. 主程式入口
# -------------------------------------------------------------------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    monitor_loop()

import os
import time
import asyncio
import threading
from datetime import datetime
import requests
from flask import Flask
from playwright.async_api import async_playwright

# -------------------------------------------------------------------
# 1. 基本設定
# -------------------------------------------------------------------
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1529665191586041876/adK2AjMfMcScpiskG32xmthHpU-CpAsnQ_ymncITfBmYip1DoqPL3qJLaHVO2maVjUXJ"

# ⚡ 巡檢目標間隔 (秒)
CHECK_INTERVAL = 5

# 🔔 個別商品重複通知冷卻時間 (秒) - 120 秒
NOTIFICATION_COOLDOWN = 120

# 監控的爆旋陀螺商品清單
TARGET_ITEMS = [
    {
        "id": "item_1",
        "name": "BX-00 翔龍神劍3-60F V2",
        "url": "https://www.toysrus.com.hk/zh-hk/pre-order-beyblade-x-bx-00-dragonsword-3-60f-2.0-expected-august-2026-10159693.html"
    },
    {
        "id": "item_2",
        "name": "BX-57 三陀螺對戰盒 (黑色版)",
        "url": "https://www.toysrus.com.hk/zh-hk/pre-order-beyblade-x-bx-51-3-on-3-deck-case-black-version-expected-august-2026-10159697.html"
    },
    {
        "id": "item_3",
        "name": "UX-21 煉獄下界三陀螺套裝",
        "url": "https://www.toysrus.com.hk/zh-hk/pre-order-beyblade-x-ux-21-hellsnether-deck-set-expected-august-2026-10159699.html"
    }
]

# 全局紀錄每個商品的最後通知時間
item_last_notified = {}

# -------------------------------------------------------------------
# 2. Flask Web Server (維持 Render Health Check)
# -------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return f"🤖 爆旋陀螺 並行極速 Bot 運作中！當前時間: {datetime.now().strftime('%H:%M:%S')}"

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
# 4. 單一商品異步檢查任務
# -------------------------------------------------------------------
async def check_single_item(context, item):
    item_id = item["id"]
    name = item["name"]
    url = item["url"]
    t_check = datetime.now().strftime("%H:%M:%S")

    print(f"[{t_check}] 🔍 [同時檢查中] [{name}]...", flush=True)
    
    page = await context.new_page()
    
    # 封鎖圖片/媒體資源，加速並節省記憶體
    async def block_media(route):
        if route.request.resource_type in ["image", "media", "font"]:
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", block_media)

    try:
        # 使用 commit 模式：只要伺服器一回應內容就立刻開始解析，不等待圖片與次要元件
        await page.goto(url, timeout=20000, wait_until="commit")
        await asyncio.sleep(1.5) # 給予 1.5 秒讓基本 DOM 文字渲染完畢

        is_out_of_stock = await page.locator("text=暫時缺貨").first.is_visible()
        has_buy_button = (
            await page.locator("text=預訂").first.is_visible() or 
            await page.locator("text=加入購物車").first.is_visible()
        )

        is_available = has_buy_button and not is_out_of_stock

        t_res = datetime.now().strftime("%H:%M:%S")
        if is_available:
            print(f"[{t_res}] 🎉🎉🎉 [{name}] 開放預訂/有貨！", flush=True)
            
            current_timestamp = time.time()
            last_time = item_last_notified.get(item_id, 0)
            time_passed = current_timestamp - last_time

            if time_passed >= NOTIFICATION_COOLDOWN:
                send_discord_notify(name, url)
                item_last_notified[item_id] = current_timestamp
            else:
                wait_left = int(NOTIFICATION_COOLDOWN - time_passed)
                print(f"[{t_res}] ⏳ [{name}] 處於獨立冷卻期中（剩餘 {wait_left} 秒）。", flush=True)
        else:
            print(f"[{t_res}] ❌ [{name}] 目前暫時缺貨", flush=True)
            item_last_notified[item_id] = 0

    except Exception as e:
        t_err = datetime.now().strftime("%H:%M:%S")
        print(f"[{t_err}] ⚠️ 檢查 [{name}] 出錯: {e}", flush=True)
    finally:
        await page.close()

# -------------------------------------------------------------------
# 5. Playwright 並行主巡檢邏輯
# -------------------------------------------------------------------
async def monitor_loop():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 異步並行極速監控系統啟動...", flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu"
            ]
        )

        while True:
            start_time = time.time()
            now_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{now_time}] 🔄 [巡檢開始] 同時發起 {len(TARGET_ITEMS)} 個商品檢查...", flush=True)

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # ⚡ 利用 asyncio.gather 同時對 3 個網址發起請求
            tasks = [check_single_item(context, item) for item in TARGET_ITEMS]
            await asyncio.gather(*tasks)

            await context.close()

            elapsed = time.time() - start_time
            sleep_time = max(0, CHECK_INTERVAL - elapsed)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏱️ 本輪並行耗時 {elapsed:.2f} 秒。等待 {sleep_time:.2f} 秒...", flush=True)
            await asyncio.sleep(sleep_time)

def start_async_loop():
    asyncio.run(monitor_loop())

# -------------------------------------------------------------------
# 6. 主程式入口
# -------------------------------------------------------------------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    start_async_loop()

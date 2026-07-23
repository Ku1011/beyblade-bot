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

# 全局紀錄每個商品的最後通知時間 (Key: item_id, Value: timestamp)
item_last_notified = {}

# -------------------------------------------------------------------
# 2. Flask Web Server (維持 Render Health Check)
# -------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return f"🤖 爆旋陀螺 100% 精準並行 Bot 運作中！當前時間: {datetime.now().strftime('%H:%M:%S')}"

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
# 4. 單一商品超精準檢查任務
# -------------------------------------------------------------------
async def check_single_item(context, item):
    item_id = item["id"]
    name = item["name"]
    url = item["url"]
    t_check = datetime.now().strftime("%H:%M:%S")

    print(f"[{t_check}] 🔍 [精準檢查中] [{name}]...", flush=True)
    
    page = await context.new_page()
    
    # 封鎖圖片與媒體檔以加快速度，但保持 CSS/JS 正常加載
    async def block_media(route):
        if route.request.resource_type in ["image", "media", "font"]:
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", block_media)

    try:
        await page.goto(url, timeout=25000, wait_until="domcontentloaded")

        # 🎯 步驟 1: 等待頁面基礎區域載入完成
        await page.wait_for_selector("body", timeout=15000)
        await asyncio.sleep(1)  # 給予 1 秒讓動態 JavaScript 渲染按鈕狀態

        # 🎯 步驟 2: 多關鍵字檢查是否提示「缺貨」
        out_of_stock_keywords = ["暫時缺貨", "缺貨", "Out of stock", "售罄"]
        is_out_of_stock = False
        
        for kw in out_of_stock_keywords:
            if await page.locator(f"text={kw}").first.is_visible():
                is_out_of_stock = True
                break

        # 🎯 步驟 3: 精準尋找真正的 HTML 按鈕，並確認非 disabled (禁用) 狀態
        buy_button = page.locator("button:has-text('預訂'), button:has-text('加入購物車'), a:has-text('預訂'), a:has-text('加入購物車')").first
        
        has_buy_button = False
        if await buy_button.is_visible():
            # is_enabled() 能確認按鈕是否被停用 (例如變灰、無法點擊)
            has_buy_button = await buy_button.is_enabled()

        # 🎯 步驟 4: 綜合判定是否有貨
        is_available = has_buy_button and not is_out_of_stock

        t_res = datetime.now().strftime("%H:%M:%S")
        if is_available:
            print(f"[{t_res}] 🎉🎉🎉 [{name}] 開放預訂/有貨！", flush=True)
            
            current_timestamp = time.time()
            last_time = item_last_notified.get(item_id, 0)
            time_passed = current_timestamp - last_time

            # 檢查個別商品的獨立冷卻時間
            if time_passed >= NOTIFICATION_COOLDOWN:
                send_discord_notify(name, url)
                item_last_notified[item_id] = current_timestamp
            else:
                wait_left = int(NOTIFICATION_COOLDOWN - time_passed)
                print(f"[{t_res}] ⏳ [{name}] 處於獨立冷卻期中（剩餘 {wait_left} 秒）。", flush=True)
        else:
            print(f"[{t_res}] ❌ [{name}] 目前暫時缺貨", flush=True)
            # 一旦變回缺貨，清空該商品的冷卻紀錄，下次上架可立刻發送通知
            item_last_notified[item_id] = 0

    except Exception as e:
        t_err = datetime.now().strftime("%H:%M:%S")
        print(f"[{t_err}] ⚠️ 檢查 [{name}] 出錯: {e}", flush=True)
    finally:
        await page.close()

# -------------------------------------------------------------------
# 5. Playwright 並行主巡檢邏輯 (含自動記憶體回收與防 Crash)
# -------------------------------------------------------------------
async def monitor_loop():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 超精準異步並行監控系統啟動...", flush=True)

    while True:
        try:
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
                    print(f"\n[{now_time}] 🔄 [巡檢開始] 發起 {len(TARGET_ITEMS)} 個商品精準檢查...", flush=True)

                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )

                    # 同時並行檢查所有商品
                    tasks = [check_single_item(context, item) for item in TARGET_ITEMS]
                    await asyncio.gather(*tasks)

                    # 每輪結束手動關閉 Context，防止 Render 免費版記憶體溢出
                    await context.close()

                    elapsed = time.time() - start_time
                    sleep_time = max(0, CHECK_INTERVAL - elapsed)
                    
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏱️ 本輪耗時 {elapsed:.2f} 秒。等待 {sleep_time:.2f} 秒...", flush=True)
                    await asyncio.sleep(sleep_time)

        except Exception as main_e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 瀏覽器異常，5 秒後自動恢復: {main_e}", flush=True)
            await asyncio.sleep(5)

def start_async_loop():
    asyncio.run(monitor_loop())

# -------------------------------------------------------------------
# 6. 主程式入口
# -------------------------------------------------------------------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    start_async_loop()

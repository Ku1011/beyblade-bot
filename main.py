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

# ⚡ 巡檢目標間隔 (秒) - 輕量化後可以設定得非常快
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
    },
    {
        "id": "item_4",
        "name": "(網店預購) Bandai萬代 [解體匠機] RX-93 Nu高達 (2026年版) (預計2026年8月發貨)",
        "url": "https://www.toysrus.com.hk/zh-hk/pre-order-bandai-metal-structure-kaitai-shou-ki-rx-93-%CE%BDgundam-expected-august-2026-10159700.html"
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
    return f"🤖 爆旋陀螺 輕量極速 Bot 運作中！當前時間: {datetime.now().strftime('%H:%M:%S')}"

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
# 4. 輕量高效 HTML 解析檢查 logic
# -------------------------------------------------------------------
def check_item_http(item, session):
    item_id = item["id"]
    name = item["name"]
    url = item["url"]
    t_check = datetime.now().strftime("%H:%M:%S")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-HK,zh-TW;q=0.9,zh;q=0.8,en-US;q=0.7,en;q=0.6"
    }

    try:
        print(f"[{t_check}] 🔍 正在檢查: [{name}]...", flush=True)
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"[{t_check}] ⚠️ 網頁回應異常 HTTP {response.status_code}: [{name}]", flush=True)
            return

        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text()

        # 🎯 判定 1：檢查頁面是否有「暫時缺貨」等文字
        is_out_of_stock = any(kw in page_text for kw in ["暫時缺貨", "Out of stock", "售罄"])

        # 🎯 判定 2：檢查是否有可用的加入購物車/預訂按鈕
        # 尋找含有 add-to-cart 或相應 class / button 的元素
        has_buy_button = False
        add_to_cart_btn = soup.find("button", class_=lambda c: c and "add-to-cart" in c)
        
        if add_to_cart_btn:
            # 確保按鈕沒有 disabled 屬性
            is_disabled = add_to_cart_btn.has_attr("disabled") or "disabled" in add_to_cart_btn.get("class", [])
            has_buy_button = not is_disabled
        else:
            # 備用方案：頁面包含「預訂」或「加入購物車」字眼，且不包含「暫時缺貨」
            has_buy_button = ("預訂" in page_text or "加入購物車" in page_text) and not is_out_of_stock

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

# -------------------------------------------------------------------
# 5. 主巡檢 Loop
# -------------------------------------------------------------------
def monitor_loop():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 秒速 HTTP 輕量監控系統啟動...", flush=True)
    session = requests.Session()

    while True:
        start_time = time.time()
        now_time = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now_time}] 🔄 [巡檢開始] 正檢查 {len(TARGET_ITEMS)} 個商品庫存...", flush=True)

        for item in TARGET_ITEMS:
            check_item_http(item, session)
            time.sleep(0.5) # 商品之間間隔 0.5 秒，避免請求過快

        elapsed = time.time() - start_time
        sleep_time = max(0, CHECK_INTERVAL - elapsed)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏱️ 本輪耗時 {elapsed:.2f} 秒。等待 {sleep_time:.2f} 秒...", flush=True)
        time.sleep(sleep_time)

# -------------------------------------------------------------------
# 6. 主程式入口
# -------------------------------------------------------------------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    monitor_loop()

import os
import time
import requests
from threading import Thread
from flask import Flask
from playwright.sync_api import sync_playwright

# ==========================================
# ⚙️ 設定區 (請將下面換成你真正嘅網址)
# ==========================================
PRODUCT_URL = "https://www.toysrus.com.hk/zh-hk/pre-order-beyblade-x-bx-00-dragonsword-3-60f-2.0-expected-august-2026-10159693.html"  # 替換為真實嘅產品網址
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1529665191586041876/adK2AjMfMcScpiskG32xmthHpU-CpAsnQ_ymncITfBmYip1DoqPL3qJLaHVO2maVjUXJ"  # 替換為你的 Discord Webhook

# ==========================================
# 🌐 Flask 防休眠伺服器 (Keep Alive Server)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    # 當 UptimeRobot 嚟敲門嗰陣，就會見到呢句說話
    return "Bot is awake and running!"

def run_server():
    # 預設使用 8080 Port
    app.run(host='0.0.0.0', port=5131)

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True  # ✨ 設定為守護線程：主程式一死，伺服器自動陪葬，唔再霸佔 Port
    t.start()

# ==========================================
# 💬 Discord 通知功能
# ==========================================
def send_discord_alert(message):
    if DISCORD_WEBHOOK_URL == "https://discord.com/api/webhooks/1529665191586041876/adK2AjMfMcScpiskG32xmthHpU-CpAsnQ_ymncITfBmYip1DoqPL3qJLaHVO2maVjUXJ":
        print("⚠️ 尚未設定 Discord Webhook URL，略過發送通知。")
        return

    data = {"content": message}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
    except Exception as e:
        print(f"發送 Discord 通知失敗: {e}")

# ==========================================
# 🤖 核心查庫存邏輯 (Scraping Logic)
# ==========================================
def check_stock(page):
    """
    呢個函數用嚟判斷網頁上面有冇貨。
    需要根據 Toys "R" Us 網頁嘅實際 HTML 代碼嚟修改。
    假設網頁如果有「加入購物車」掣，個 class 叫 '.add-to-cart'
    """
    try:
        # 呢度係一個範例：如果搵到某個特定嘅按鈕，就當有貨 (回傳 True)
        # 你需要將 '.add-to-cart' 換成真實網頁嘅元素選擇器 (Selector)
        is_available = page.locator('.add-to-cart').is_visible()
        return is_available
    except Exception:
        return False

def main():
    print("🤖 爆旋陀螺監控系統啟動...")

    with sync_playwright() as p:
        # 啟動隱形瀏覽器 (headless=True 代表唔會彈出視窗)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"前往網頁: {'https://www.toysrus.com.hk/zh-hk/pre-order-beyblade-x-bx-00-dragonsword-3-60f-2.0-expected-august-2026-10159693.html'}")
        page.goto("https://www.toysrus.com.hk/zh-hk/pre-order-beyblade-x-bx-00-dragonsword-3-60f-2.0-expected-august-2026-10159693.html")

        while True:
            try:
                print("檢查緊庫存...")
                # 重新載入網頁獲取最新狀態
                page.reload()
                time.sleep(3) # 等待網頁載入

                if check_stock(page):
                    print("✅ 發現庫存！準備傳送通知...")
                    send_discord_alert(f"@everyone 🚨 爆旋陀螺返貨喇！快啲去搶： {PRODUCT_URL}")

                    # 發現有貨之後暫停 1 個鐘 (3600秒)，以免瘋狂轟炸 Discord
                    time.sleep(3600) 
                else:
                    print("未有貨...")
                    # 每次檢查嘅間隔時間 (目前設定為 5 秒，建議長遠改為 30-60 秒防封鎖)
                    time.sleep(5)     

            except Exception as e:
                print(f"發生錯誤： {e}")
                time.sleep(60) # 如果出錯就等 60 秒再試

# ==========================================
# 🚀 程式執行起點
# ==========================================
if __name__ == "__main__":
    # 1. 先啟動背景 Flask 伺服器等 UptimeRobot 敲門
    keep_alive()  

    # 2. 啟動查庫存腳本，並捕捉 Ctrl+C 暫停指令
    try:
        main()    
    except KeyboardInterrupt:
        # ✨ 終極清理大法：當你手動㩒 Ctrl + C 嗰陣，徹底殺死所有進程釋放 Port
        print("\n🛑 收到暫停指令，徹底關閉所有程式中...")
        os._exit(0)

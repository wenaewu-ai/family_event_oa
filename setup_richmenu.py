"""
RichMenu 初始化腳本
執行一次即可，之後不需重複執行

使用方式：
  python setup_richmenu.py
"""
import os
import sys
import requests

ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
SHEETS_URL   = os.environ.get("GOOGLE_SPREADSHEET_URL", "")

if not ACCESS_TOKEN:
    print("❌ 請先設定 LINE_CHANNEL_ACCESS_TOKEN 環境變數")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

# ─── 1. 建立 RichMenu ───────────────────────────────────────
richmenu_body = {
    "size": {"width": 2500, "height": 843},
    "selected": True,
    "name": "家族服務主選單",
    "chatBarText": "📋 家族服務選單",
    "areas": [
        {
            "bounds": {"x": 0, "y": 0, "width": 833, "height": 422},
            "action": {"type": "postback", "data": "action=view_fund",
                       "displayText": "💰 公積金"}
        },
        {
            "bounds": {"x": 833, "y": 0, "width": 834, "height": 422},
            "action": {"type": "postback", "data": "action=list_events",
                       "displayText": "📋 活動費用"}
        },
        {
            "bounds": {"x": 1667, "y": 0, "width": 833, "height": 422},
            "action": {"type": "postback", "data": "action=my_records",
                       "displayText": "👤 我的紀錄"}
        },
        {
            "bounds": {"x": 0, "y": 422, "width": 2500, "height": 421},
            "action": {"type": "uri",
                       "label": "📊 查看 Google Sheets",
                       "uri": SHEETS_URL or "https://docs.google.com/spreadsheets"}
        },
    ]
}

resp = requests.post(
    "https://api.line.me/v2/bot/richmenu",
    headers=HEADERS, json=richmenu_body
)
resp.raise_for_status()
rich_menu_id = resp.json()["richMenuId"]
print(f"✅ RichMenu 建立成功：{rich_menu_id}")

# ─── 2. 上傳 RichMenu 圖片 ──────────────────────────────────
# 請自行準備 2500x843 的 PNG 圖片放在同目錄
image_path = "richmenu_image.png"
if os.path.exists(image_path):
    with open(image_path, "rb") as f:
        img_resp = requests.post(
            f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
            headers={
                "Authorization": f"Bearer {ACCESS_TOKEN}",
                "Content-Type": "image/png",
            },
            data=f.read()
        )
        img_resp.raise_for_status()
        print("✅ RichMenu 圖片上傳成功")
else:
    print(f"⚠️  找不到 {image_path}，請上傳圖片後重新執行圖片上傳步驟")
    print("   圖片規格：2500 x 843 px，PNG 格式")

# ─── 3. 設為預設 RichMenu ───────────────────────────────────
default_resp = requests.post(
    f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}",
    headers=HEADERS
)
default_resp.raise_for_status()
print("✅ 已設為預設 RichMenu（所有用戶皆套用）")
print(f"\n完成！RichMenu ID：{rich_menu_id}")

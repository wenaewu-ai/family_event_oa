"""
新成員加入 / Bot 加入群組事件處理
"""
import os
import logging
from linebot.v3.messaging import (
    MessagingApi, ReplyMessageRequest, TextMessage
)
from utils.sheets import register_member

logger = logging.getLogger(__name__)

SHEETS_URL = os.environ.get("GOOGLE_SPREADSHEET_URL", "（請設定 GOOGLE_SPREADSHEET_URL）")


def handle_follow(event, line_bot_api: MessagingApi):
    """用戶加入 OA 好友"""
    user_id = event.source.user_id
    try:
        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name
    except Exception:
        display_name = "新成員"

    register_member(user_id, display_name)
    logger.info(f"New follower: {user_id} ({display_name})")

    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(text=(
            f"👋 歡迎 {display_name} 加入家族服務！\n\n"
            "請告知管理員將你加入成員清單，設定好家庭單位後即可使用所有功能。\n\n"
            "📋 成員清單由管理員在 Google Sheets 維護。"
        ))]
    ))


def handle_join(event, line_bot_api: MessagingApi):
    """Bot 被加入群組"""
    logger.info(f"Bot joined group: {getattr(event.source, 'group_id', 'unknown')}")
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(text=(
            "🏠 家族記帳 Bot 已就位！\n\n"
            "請點選下方選單開始使用：\n"
            "💰 公積金　📋 活動費用　👤 我的紀錄\n\n"
            "管理員請先至 Google Sheets 設定成員清單。"
        ))]
    ))

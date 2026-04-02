"""
文字訊息處理 — 用於多步驟對話中接收用戶輸入
（例如：輸入金額、說明、活動名稱等）
"""
import logging
import re
from datetime import datetime

from linebot.v3.messaging import (
    MessagingApi, ReplyMessageRequest, TextMessage,
    PushMessageRequest
)

from utils.sheets import (
    get_member, get_state, clear_state,
    add_fund_transaction, submit_expense,
    get_event, get_events
)
from utils.flex_builder import (
    fund_balance_card, fund_push_notification, my_expenses_card
)

logger = logging.getLogger(__name__)

import os
GROUP_ID = os.environ.get("ALLOWED_GROUP_ID", "")


def handle_message(event, line_bot_api: MessagingApi):
    user_id  = event.source.user_id
    text     = event.message.text.strip()
    member   = get_member(user_id)

    if not member or not member.get("family_unit"):
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="⚠️ 尚未設定家庭單位，請聯繫管理員。")]
        ))
        return

    state_data = get_state(user_id)
    if not state_data:
        return  # 非流程中的訊息，忽略

    state = state_data["state"]
    data  = state_data["data"]

    # ── Quick Reply 特殊前綴處理 ─────────────────────────────
    # 公積金收支類型選擇
    if text.startswith("__fund_type__"):
        tx_type = text.replace("__fund_type__", "")
        from utils.sheets import set_state as _set_state
        _set_state(user_id, "await_fund_input", {"type": tx_type})
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=(
                f"{'➕ 收入' if tx_type == '收入' else '➖ 支出'}\n\n"
                "請輸入金額與說明（格式：金額 說明）\n"
                "範例：5000 清明節採購費\n\n"
                "輸入「取消」可中止操作。"
            ))]
        ))
        return

    # 結清確認選擇
    if text.startswith("__settle__"):
        parts = text.split("__")
        # 格式：__settle__EVENT_ID__FAMILY_UNIT
        if len(parts) >= 4:
            event_id    = parts[2]
            family_unit = parts[3]
            settled_by  = member.get("display_name", "")
            count = mark_family_settled(event_id, family_unit, settled_by)
            ev = get_event(event_id)
            event_name = ev.get("event_name", "") if ev else event_id

            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"✅ 已將「{family_unit}」標記為結清（共更新 {count} 筆）")]
            ))

            # 推播通知群組
            if GROUP_ID:
                try:
                    from utils.flex_builder import settled_push_notification
                    line_bot_api.push_message(PushMessageRequest(
                        to=GROUP_ID,
                        messages=[settled_push_notification(event_name, family_unit, settled_by)]
                    ))
                except Exception as e:
                    logger.error(f"Settle push failed: {e}")
        return

    # ── 公積金：等待輸入金額與說明 ──────────────────────────
    if state == "await_fund_input":
        _handle_fund_input(event, line_bot_api, user_id, member, data, text)

    # ── 活動費用：等待輸入費用項目 ──────────────────────────
    elif state == "await_expense_input":
        _handle_expense_input(event, line_bot_api, user_id, member, data, text)

    # ── 建立活動：等待輸入活動名稱 ──────────────────────────
    elif state == "await_event_name":
        _handle_event_name(event, line_bot_api, user_id, member, data, text)

    # ── 建立活動：等待輸入活動日期 ──────────────────────────
    elif state == "await_event_date":
        _handle_event_date(event, line_bot_api, user_id, member, data, text)


# ─────────────────────────────────────────────────
# 公積金收支輸入
# ─────────────────────────────────────────────────

def _handle_fund_input(event, line_bot_api, user_id, member, data, text):
    """格式：金額 說明　例如：5000 清明節採購"""
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[0].isdigit():
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=(
                "⚠️ 格式錯誤，請重新輸入：\n"
                "金額（數字）空格 說明\n\n"
                "範例：5000 清明節採購費\n\n"
                "輸入「取消」可中止操作。"
            ))]
        ))
        return

    if text == "取消":
        clear_state(user_id)
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="已取消操作。")]
        ))
        return

    amount      = int(parts[0])
    description = parts[1]
    tx_type     = data.get("type", "支出")
    operator    = member.get("display_name", "")

    result = add_fund_transaction(tx_type, amount, description, operator)
    clear_state(user_id)

    # 回覆操作者
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[fund_balance_card(result["balance"], {
            "type": tx_type, "amount": amount,
            "description": description, "operator": operator,
            "timestamp": datetime.now().strftime("%Y/%m/%d %H:%M"),
        })]
    ))

    # 推播通知群組
    if GROUP_ID:
        try:
            line_bot_api.push_message(PushMessageRequest(
                to=GROUP_ID,
                messages=[fund_push_notification(
                    tx_type, amount, description, operator, result["balance"]
                )]
            ))
        except Exception as e:
            logger.error(f"Push notification failed: {e}")


# ─────────────────────────────────────────────────
# 活動費用提交輸入
# ─────────────────────────────────────────────────

def _handle_expense_input(event, line_bot_api, user_id, member, data, text):
    """格式：金額 項目說明　例如：1500 祭品（雞、魚）"""
    if text == "取消":
        clear_state(user_id)
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="已取消操作。")]
        ))
        return

    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[0].isdigit():
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=(
                "⚠️ 格式錯誤，請重新輸入：\n"
                "金額（數字）空格 費用說明\n\n"
                "範例：1500 祭品（雞、魚、豬肉）\n\n"
                "輸入「取消」可中止操作。"
            ))]
        ))
        return

    amount      = int(parts[0])
    item_name   = parts[1]
    event_id    = data.get("event_id", "")
    family_unit = member.get("family_unit", "")
    submitter   = member.get("display_name", "")

    submit_expense(event_id, family_unit, submitter, item_name, amount)
    clear_state(user_id)

    # 取得該家本次所有費用後顯示
    from utils.sheets import get_family_expenses
    expenses = get_family_expenses(event_id, family_unit)
    ev = get_event(event_id)
    event_name = ev.get("event_name", "") if ev else event_id

    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[my_expenses_card(event_name, event_id, family_unit, expenses)]
    ))


# ─────────────────────────────────────────────────
# 建立活動 — 活動名稱輸入
# ─────────────────────────────────────────────────

def _handle_event_name(event, line_bot_api, user_id, member, data, text):
    if text == "取消":
        clear_state(user_id)
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="已取消操作。")]
        ))
        return

    from utils.sheets import set_state
    set_state(user_id, "await_event_date", {"event_name": text})
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(text=(
            f"活動名稱：{text}\n\n"
            "請輸入活動日期（格式：YYYY/MM/DD）\n"
            "例如：2025/04/05\n\n"
            "輸入「取消」可中止操作。"
        ))]
    ))


# ─────────────────────────────────────────────────
# 建立活動 — 活動日期輸入
# ─────────────────────────────────────────────────

def _handle_event_date(event, line_bot_api, user_id, member, data, text):
    if text == "取消":
        clear_state(user_id)
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="已取消操作。")]
        ))
        return

    # 驗證日期格式
    try:
        datetime.strptime(text, "%Y/%m/%d")
    except ValueError:
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=(
                "⚠️ 日期格式錯誤，請輸入 YYYY/MM/DD\n"
                "例如：2025/04/05"
            ))]
        ))
        return

    event_name  = data.get("event_name", "")
    event_date  = text
    created_by  = member.get("display_name", "")
    event_id    = "EVT" + datetime.now().strftime("%Y%m%d%H%M")

    from utils.sheets import create_event
    create_event(event_id, event_name, event_date, created_by)
    clear_state(user_id)

    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(text=(
            f"✅ 活動已建立！\n\n"
            f"📌 {event_name}\n"
            f"📅 {event_date}\n"
            f"🆔 {event_id}\n\n"
            "成員現在可以開始提交費用了。"
        ))]
    ))

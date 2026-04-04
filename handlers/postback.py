"""
Postback 事件處理 — RichMenu 按鈕與卡片按鈕操作
"""
import os
import logging
from urllib.parse import parse_qs

from linebot.v3.messaging import (
    MessagingApi, ReplyMessageRequest, TextMessage,
    QuickReply, QuickReplyItem, MessageAction,
    PushMessageRequest
)

from utils.sheets import (
    get_member, is_admin, get_state, set_state, clear_state,
    get_fund_balance, get_events, get_event,
    get_event_expenses, get_family_expenses,
    calculate_split, mark_family_settled, get_event_fund_contribution
)
from utils.flex_builder import (
    fund_balance_card, event_list_carousel,
    event_detail_card, my_expenses_card, settled_push_notification
)

logger = logging.getLogger(__name__)

GROUP_ID = os.environ.get("ALLOWED_GROUP_ID", "")
SHEETS_URL = os.environ.get("GOOGLE_SPREADSHEET_URL", "")


def handle_postback(event, line_bot_api: MessagingApi):
    user_id = event.source.user_id
    data    = parse_qs(event.postback.data)
    action  = data.get("action", [""])[0]
    member  = get_member(user_id)

    if not member:
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="⚠️ 找不到你的成員資料，請聯繫管理員加入成員清單。")]
        ))
        return

    # ── 路由 ────────────────────────────────────────────────
    dispatch = {
        "view_fund":           _view_fund,
        "view_fund_detail":    _view_fund_detail,
        "add_fund":            _add_fund,
        "add_fund_type":       _add_fund_type,
        "list_events":         _list_events,
        "view_event":          _view_event,
        "submit_expense":      _submit_expense,
        "mark_settled":        _mark_settled,
        "mark_settled_confirm":_mark_settled_confirm,
        "my_records":          _my_records,
        "create_event":        _create_event,
        "fund_event_subsidy":  _fund_event_subsidy,
    }

    handler_fn = dispatch.get(action)
    if handler_fn:
        handler_fn(event, line_bot_api, user_id, member, data)
    else:
        logger.warning(f"Unknown action: {action}")


# ─────────────────────────────────────────────────
# 公積金
# ─────────────────────────────────────────────────

def _view_fund(event, line_bot_api, user_id, member, data):
    result = get_fund_balance()
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[fund_balance_card(result["balance"], result.get("last_op"))]
    ))


def _view_fund_detail(event, line_bot_api, user_id, member, data):
    url = SHEETS_URL or "尚未設定 Google Sheets 連結"
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(text=f"📊 完整公積金明細請至 Google Sheets 查看：\n{url}")]
    ))


def _add_fund(event, line_bot_api, user_id, member, data):
    """管理員才能新增收支"""
    if not is_admin(user_id):
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="⚠️ 只有管理員可以新增公積金收支。")]
        ))
        return

    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(
            text="請選擇收支類型：",
            quick_reply=QuickReply(items=[
                QuickReplyItem(action=MessageAction(
                    label="➕ 收入", text="__fund_type__收入")),
                QuickReplyItem(action=MessageAction(
                    label="➖ 支出", text="__fund_type__支出")),
                QuickReplyItem(action=MessageAction(
                    label="❌ 取消", text="取消")),
            ])
        )]
    ))


def _add_fund_type(event, line_bot_api, user_id, member, data):
    """接收 Quick Reply 選擇的收支類型，改用文字訊息中繼"""
    # 此路由由 message handler 中的 __fund_type__ 前綴訊息觸發
    pass  # 實際由 message.py 的 quick reply 回覆文字處理


# ─────────────────────────────────────────────────
# 活動列表
# ─────────────────────────────────────────────────

def _list_events(event, line_bot_api, user_id, member, data):
    events = get_events()
    if not events:
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="目前沒有任何活動紀錄。\n請管理員建立第一個活動！")]
        ))
        return

    # 補充 settled_count 資訊
    for ev in events:
        split = calculate_split(ev["event_id"])
        ev["settled_count"]  = split["settled_count"]
        ev["total_families"] = split["total_families"]

    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[event_list_carousel(events)]
    ))


# ─────────────────────────────────────────────────
# 活動詳情
# ─────────────────────────────────────────────────

def _view_event(event, line_bot_api, user_id, member, data):
    event_id = data.get("event_id", [""])[0]
    ev = get_event(event_id)
    if not ev:
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="找不到該活動，請重新選擇。")]
        ))
        return

    split = calculate_split(event_id)
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[event_detail_card(ev, split)]
    ))


# ─────────────────────────────────────────────────
# 提交費用
# ─────────────────────────────────────────────────

def _submit_expense(event, line_bot_api, user_id, member, data):
    event_id    = data.get("event_id", [""])[0]
    family_unit = member.get("family_unit", "")

    if not family_unit:
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="⚠️ 尚未設定家庭單位，請聯繫管理員。")]
        ))
        return

    # 顯示目前已提交的費用
    expenses  = get_family_expenses(event_id, family_unit)
    ev        = get_event(event_id)
    event_name = ev.get("event_name", "") if ev else event_id
    total     = sum(int(str(e.get("amount", 0)).replace(",", "")) for e in expenses)

    existing_text = ""
    if expenses:
        lines = "\n".join(
            f"  • {e.get('submitter','')}：{e.get('item_name','')} ${int(str(e.get('amount',0)).replace(',','')):,}"
            for e in expenses
        )
        existing_text = f"\n\n{family_unit} 目前已提交：\n{lines}\n小計：${total:,}"

    set_state(user_id, "await_expense_input", {"event_id": event_id})

    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(text=(
            f"📤 提交費用　─　{event_name}"
            f"{existing_text}\n\n"
            "請輸入本次費用（格式：金額 說明）\n"
            "範例：1500 祭品（雞、魚、豬肉）\n\n"
            "輸入「取消」可中止操作。"
        ))]
    ))


# ─────────────────────────────────────────────────
# 標記結清（管理員）
# ─────────────────────────────────────────────────

def _mark_settled(event, line_bot_api, user_id, member, data):
    if not is_admin(user_id):
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="⚠️ 只有管理員可以標記結清。")]
        ))
        return

    event_id = data.get("event_id", [""])[0]
    split    = calculate_split(event_id)
    unsettled = [f for f in split["families"] if not f["is_settled"]]

    if not unsettled:
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="✅ 所有家庭都已結清！")]
        ))
        return

    items = [
        QuickReplyItem(action=MessageAction(
            label=f"{f['family_unit']} (${f['paid']:,})",
            text=f"__settle__{event_id}__{f['family_unit']}"
        ))
        for f in unsettled[:12]  # LINE Quick Reply 最多 13 項
    ]
    items.append(QuickReplyItem(action=MessageAction(
        label="❌ 取消", text="取消"
    )))

    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(
            text="請選擇要標記結清的家庭：",
            quick_reply=QuickReply(items=items)
        )]
    ))


def _mark_settled_confirm(event, line_bot_api, user_id, member, data):
    """確認結清（由 message handler 的 __settle__ 前綴訊息觸發）"""
    pass  # 見 message.py 的 special prefix 處理


# ─────────────────────────────────────────────────
# 公積金補貼活動費用（管理員）
# ─────────────────────────────────────────────────

def _fund_event_subsidy(event, line_bot_api, user_id, member, data):
    if not is_admin(user_id):
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="⚠️ 只有管理員可以設定公積金補貼。")]
        ))
        return

    event_id = data.get("event_id", [""])[0]
    ev = get_event(event_id)
    if not ev:
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="找不到該活動，請重新選擇。")]
        ))
        return

    split = calculate_split(event_id)
    fund  = get_fund_balance()
    already = get_event_fund_contribution(event_id)

    set_state(user_id, "await_fund_subsidy", {"event_id": event_id})

    already_text = f"（本活動已補貼 ${already:,}）\n" if already > 0 else ""
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(text=(
            f"💰 公積金補貼　─　{ev.get('event_name', '')}\n\n"
            f"活動總費用：${split['total']:,}\n"
            f"公積金餘額：${fund['balance']:,}\n"
            f"{already_text}\n"
            "請輸入本次補貼金額（數字）：\n\n"
            "輸入「取消」可中止操作。"
        ))]
    ))


# ─────────────────────────────────────────────────
# 我的紀錄
# ─────────────────────────────────────────────────

def _my_records(event, line_bot_api, user_id, member, data):
    family_unit = member.get("family_unit", "")
    events = get_events(status_filter="進行中")

    if not events:
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="目前沒有進行中的活動。")]
        ))
        return

    # 預設顯示最新進行中活動的費用
    ev         = events[0]
    event_id   = ev.get("event_id", "")
    event_name = ev.get("event_name", "")
    expenses   = get_family_expenses(event_id, family_unit)

    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[my_expenses_card(event_name, event_id, family_unit, expenses)]
    ))


# ─────────────────────────────────────────────────
# 建立活動（管理員）
# ─────────────────────────────────────────────────

def _create_event(event, line_bot_api, user_id, member, data):
    if not is_admin(user_id):
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="⚠️ 只有管理員可以建立活動。")]
        ))
        return

    set_state(user_id, "await_event_name", {})
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(text=(
            "📌 建立新活動\n\n"
            "請輸入活動名稱：\n"
            "例如：2025 清明節\n\n"
            "輸入「取消」可中止操作。"
        ))]
    ))

"""
Flex Message 卡片組裝工具
將動態資料填入卡片樣板並回傳 LINE SDK 物件
"""
from linebot.v3.messaging import FlexMessage, FlexContainer


def _msg(alt_text: str, contents: dict) -> FlexMessage:
    return FlexMessage(
        alt_text=alt_text,
        contents=FlexContainer.from_dict(contents)
    )


# ─────────────────────────────────────────────────
# 公積金餘額卡片
# ─────────────────────────────────────────────────

def fund_balance_card(balance: int, last_op: dict | None) -> FlexMessage:
    last_op_boxes = []
    if last_op:
        color = "#CC4400" if last_op["type"] == "支出" else "#1E8449"
        sign  = "➖" if last_op["type"] == "支出" else "➕"
        last_op_boxes = [
            {"type": "separator"},
            {"type": "text", "text": "最近異動", "color": "#888888",
             "size": "xs", "weight": "bold"},
            {
                "type": "box", "layout": "horizontal",
                "contents": [
                    {"type": "text", "flex": 4, "size": "sm", "color": color,
                     "text": f"{sign} {last_op['description']}"},
                    {"type": "text", "flex": 2, "size": "sm", "color": color,
                     "weight": "bold", "align": "end",
                     "text": f"-${last_op['amount']:,}" if last_op["type"] == "支出"
                             else f"+${last_op['amount']:,}"},
                ]
            },
            {
                "type": "box", "layout": "horizontal",
                "contents": [
                    {"type": "text", "flex": 4, "size": "xs", "color": "#AAAAAA",
                     "text": f"  操作人：{last_op['operator']}"},
                    {"type": "text", "flex": 2, "size": "xs", "color": "#AAAAAA",
                     "align": "end", "text": str(last_op.get("timestamp", ""))[:10]},
                ]
            },
        ]

    contents = {
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#1E3A5F", "paddingAll": "16px",
            "contents": [
                {"type": "text", "text": "💰 家族公積金",
                 "color": "#FFFFFF", "size": "xl", "weight": "bold"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical",
            "spacing": "md", "paddingAll": "16px",
            "contents": [
                {
                    "type": "box", "layout": "vertical",
                    "backgroundColor": "#F0F7FF", "cornerRadius": "8px",
                    "paddingAll": "12px",
                    "contents": [
                        {"type": "text", "text": "目前餘額",
                         "color": "#666666", "size": "sm"},
                        {"type": "text", "text": f"${balance:,}",
                         "color": "#1E3A5F", "size": "3xl",
                         "weight": "bold", "margin": "xs"},
                    ]
                },
                *last_op_boxes,
            ]
        },
        "footer": {
            "type": "box", "layout": "horizontal",
            "spacing": "sm", "paddingAll": "12px",
            "contents": [
                {
                    "type": "button", "style": "secondary", "height": "sm", "flex": 1,
                    "action": {"type": "postback", "label": "📋 查看明細",
                               "data": "action=view_fund_detail"}
                },
                {
                    "type": "button", "style": "primary", "height": "sm",
                    "flex": 1, "color": "#1E3A5F",
                    "action": {"type": "postback", "label": "➕ 新增收支",
                               "data": "action=add_fund"}
                },
            ]
        }
    }
    return _msg("💰 家族公積金餘額", contents)


# ─────────────────────────────────────────────────
# 活動列表輪播
# ─────────────────────────────────────────────────

def event_list_carousel(events: list[dict]) -> FlexMessage:
    COLORS = ["#7B3F00", "#1A5276", "#196F3D", "#6C3483", "#1A374D"]
    bubbles = []

    for i, ev in enumerate(events[:9]):  # LINE 最多 12 個 bubble
        color = COLORS[i % len(COLORS)]
        settled = ev.get("settled_count", 0)
        total_f = ev.get("total_families", 0)
        settle_text = f"{settled}/{total_f} 戶 ✅" if total_f else "—"

        bubbles.append({
            "type": "bubble", "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": color, "paddingAll": "14px",
                "contents": [
                    {"type": "text", "text": ev.get("event_name", ""),
                     "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                    {"type": "text", "size": "xs", "margin": "xs",
                     "color": "#DDDDDD",
                     "text": f"{ev.get('event_date','')}　{ev.get('status','')}"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical",
                "spacing": "sm", "paddingAll": "12px",
                "contents": [
                    _row("總費用", f"${int(str(ev.get('total_amount',0)).replace(',','')):,}"),
                    _row("每戶分攤", f"${int(str(ev.get('amount_per_unit',0)).replace(',','')):,}"),
                    _row("結清進度", settle_text),
                ]
            },
            "footer": {
                "type": "box", "layout": "vertical", "paddingAll": "10px",
                "contents": [{
                    "type": "button", "style": "primary", "height": "sm",
                    "color": color,
                    "action": {"type": "postback", "label": "查看詳情 ▶",
                               "data": f"action=view_event&event_id={ev['event_id']}"}
                }]
            }
        })

    # 新增活動按鈕
    bubbles.append({
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical",
            "justifyContent": "center", "alignItems": "center",
            "paddingAll": "32px",
            "contents": [
                {"type": "text", "text": "＋", "size": "5xl",
                 "color": "#CCCCCC", "align": "center"},
                {"type": "text", "text": "新增活動", "size": "md",
                 "color": "#888888", "align": "center", "margin": "sm"},
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "paddingAll": "10px",
            "contents": [{
                "type": "button", "style": "secondary", "height": "sm",
                "action": {"type": "postback", "label": "＋ 建立新活動",
                           "data": "action=create_event"}
            }]
        }
    })

    return _msg("📋 活動費用清單",
                {"type": "carousel", "contents": bubbles})


def _row(label: str, value: str) -> dict:
    return {
        "type": "box", "layout": "horizontal",
        "contents": [
            {"type": "text", "text": label, "color": "#888888",
             "size": "sm", "flex": 2},
            {"type": "text", "text": value, "color": "#333333",
             "size": "sm", "weight": "bold", "flex": 3, "align": "end"},
        ]
    }


# ─────────────────────────────────────────────────
# 活動費用明細卡片
# ─────────────────────────────────────────────────

def event_detail_card(event: dict, split: dict) -> FlexMessage:
    family_rows = []
    for f in split["families"]:
        if f["is_settled"]:
            bg, icon, text_color = "#D5F5E3", "✅", "#1E8449"
            status_text = "已結清"
        else:
            bg, icon, text_color = "#FDEBD0", "⏳", "#CA6F1E"
            status_text = "未結清"

        family_rows.append({
            "type": "box", "layout": "horizontal",
            "backgroundColor": bg, "cornerRadius": "6px",
            "paddingAll": "8px",
            "contents": [
                {"type": "text", "flex": 3, "size": "sm",
                 "color": text_color, "weight": "bold",
                 "text": f"{icon} {f['family_unit']}"},
                {"type": "text", "flex": 2, "size": "sm",
                 "color": "#444444", "align": "end",
                 "text": f"${f['paid']:,}"},
                {"type": "text", "flex": 2, "size": "xs",
                 "color": text_color, "align": "end",
                 "text": status_text},
            ]
        })

    settled = split["settled_count"]
    total_f = split["total_families"]
    pct = int(settled / total_f * 100) if total_f else 0

    contents = {
        "type": "bubble", "size": "mega",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#7B3F00", "paddingAll": "16px",
            "contents": [
                {"type": "text", "text": f"🏮 {event.get('event_name','')}",
                 "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                {"type": "text", "size": "xs", "margin": "sm",
                 "color": "#F5CBA7",
                 "text": f"日期：{event.get('event_date','')}　狀態：{event.get('status','')}"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical",
            "spacing": "md", "paddingAll": "14px",
            "contents": [
                {
                    "type": "box", "layout": "horizontal", "spacing": "md",
                    "contents": [
                        _summary_box("總費用", f"${split['total']:,}", "#FFF3CD", "#7B3F00"),
                        _summary_box("每戶分攤", f"${split['per_unit']:,}", "#EAF4FB", "#1A5276"),
                    ]
                },
                {"type": "separator"},
                {"type": "text", "text": "各家結清狀況",
                 "weight": "bold", "size": "sm", "color": "#444444"},
                {"type": "box", "layout": "vertical",
                 "spacing": "sm", "contents": family_rows},
                {
                    "type": "box", "layout": "horizontal",
                    "backgroundColor": "#F4F6F7", "cornerRadius": "6px",
                    "paddingAll": "8px", "margin": "sm",
                    "contents": [
                        {"type": "text", "text": f"已結清 {settled} 戶 / 共 {total_f} 戶",
                         "size": "xs", "color": "#666666", "flex": 3},
                        {"type": "text", "text": f"進度 {pct}%",
                         "size": "xs", "color": "#1A5276",
                         "flex": 2, "align": "end", "weight": "bold"},
                    ]
                },
            ]
        },
        "footer": {
            "type": "box", "layout": "horizontal",
            "spacing": "sm", "paddingAll": "12px",
            "contents": [
                {
                    "type": "button", "style": "primary", "height": "sm",
                    "flex": 1, "color": "#7B3F00",
                    "action": {"type": "postback", "label": "📤 提交費用",
                               "data": f"action=submit_expense&event_id={event['event_id']}"}
                },
                {
                    "type": "button", "style": "secondary", "height": "sm", "flex": 1,
                    "action": {"type": "postback", "label": "✅ 標記結清",
                               "data": f"action=mark_settled&event_id={event['event_id']}"}
                },
            ]
        }
    }
    return _msg(f"🏮 {event.get('event_name','')} 費用明細", contents)


def _summary_box(label: str, value: str, bg: str, color: str) -> dict:
    return {
        "type": "box", "layout": "vertical",
        "backgroundColor": bg, "cornerRadius": "8px",
        "paddingAll": "10px", "flex": 1,
        "contents": [
            {"type": "text", "text": label, "color": "#888888", "size": "xs"},
            {"type": "text", "text": value, "color": color,
             "size": "xl", "weight": "bold"},
        ]
    }


# ─────────────────────────────────────────────────
# 我的費用紀錄卡片
# ─────────────────────────────────────────────────

def my_expenses_card(event_name: str, event_id: str,
                      family_unit: str, expenses: list[dict]) -> FlexMessage:
    total = sum(int(str(e.get("amount", 0)).replace(",", "")) for e in expenses)
    all_settled = all(e.get("is_settled") == "TRUE" for e in expenses) if expenses else False

    item_rows = []
    for e in expenses:
        item_rows.append({
            "type": "box", "layout": "horizontal",
            "backgroundColor": "#F8F9FA", "cornerRadius": "6px",
            "paddingAll": "8px",
            "contents": [
                {"type": "text", "text": e.get("submitter", ""),
                 "size": "xs", "color": "#888888", "flex": 2},
                {"type": "text", "text": e.get("item_name", ""),
                 "size": "sm", "color": "#333333", "flex": 3},
                {"type": "text",
                 "text": f"${int(str(e.get('amount',0)).replace(',','')):,}",
                 "size": "sm", "color": "#333333",
                 "flex": 2, "align": "end", "weight": "bold"},
            ]
        })

    settle_bg    = "#D5F5E3" if all_settled else "#FDEBD0"
    settle_color = "#1E8449" if all_settled else "#CA6F1E"
    settle_text  = "✅ 已結清" if all_settled else "⏳ 未結清"

    contents = {
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#2E4057", "paddingAll": "14px",
            "contents": [
                {"type": "text",
                 "text": f"👤 {family_unit}　費用紀錄",
                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                {"type": "text", "size": "xs", "margin": "xs",
                 "color": "#B0BEC5", "text": f"活動：{event_name}"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical",
            "spacing": "sm", "paddingAll": "14px",
            "contents": [
                {"type": "text", "text": f"{family_unit}　本次已提交",
                 "weight": "bold", "size": "sm", "color": "#444444"},
                {"type": "box", "layout": "vertical",
                 "spacing": "xs", "contents": item_rows} if item_rows
                else {"type": "text", "text": "尚未提交任何費用",
                      "color": "#AAAAAA", "size": "sm", "align": "center"},
                {"type": "separator"},
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "合計", "size": "sm",
                         "color": "#555555", "flex": 3, "weight": "bold"},
                        {"type": "text", "text": f"${total:,}",
                         "size": "md", "color": "#1E3A5F",
                         "flex": 2, "align": "end", "weight": "bold"},
                    ]
                },
                {
                    "type": "box", "layout": "horizontal",
                    "backgroundColor": settle_bg, "cornerRadius": "6px",
                    "paddingAll": "8px", "margin": "sm",
                    "contents": [
                        {"type": "text", "text": "結清狀態",
                         "size": "sm", "color": "#555555", "flex": 2},
                        {"type": "text", "text": settle_text,
                         "size": "sm", "color": settle_color,
                         "flex": 3, "align": "end", "weight": "bold"},
                    ]
                },
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "paddingAll": "10px",
            "contents": [{
                "type": "button", "style": "secondary", "height": "sm",
                "action": {"type": "postback", "label": "➕ 再新增一筆費用",
                           "data": f"action=submit_expense&event_id={event_id}"}
            }]
        }
    }
    return _msg(f"👤 {family_unit} 費用紀錄", contents)


# ─────────────────────────────────────────────────
# 群組推播通知
# ─────────────────────────────────────────────────

def fund_push_notification(tx_type: str, amount: int, description: str,
                            operator: str, new_balance: int) -> FlexMessage:
    header_color = "#CC4400" if tx_type == "支出" else "#1E8449"
    sign = "➖ 支出" if tx_type == "支出" else "➕ 收入"

    contents = {
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "horizontal",
            "backgroundColor": header_color, "paddingAll": "12px",
            "contents": [{"type": "text", "text": "📢 公積金異動通知",
                           "color": "#FFFFFF", "size": "md", "weight": "bold"}]
        },
        "body": {
            "type": "box", "layout": "vertical",
            "spacing": "sm", "paddingAll": "14px",
            "contents": [
                _row("類型", sign),
                _row("金額", f"${amount:,}"),
                _row("說明", description),
                _row("操作人", operator),
                {"type": "separator"},
                {
                    "type": "box", "layout": "horizontal",
                    "backgroundColor": "#EAF4FB", "cornerRadius": "6px",
                    "paddingAll": "10px",
                    "contents": [
                        {"type": "text", "text": "目前餘額",
                         "color": "#1A5276", "size": "sm", "flex": 2, "weight": "bold"},
                        {"type": "text", "text": f"${new_balance:,}",
                         "color": "#1A5276", "size": "lg",
                         "flex": 3, "align": "end", "weight": "bold"},
                    ]
                },
            ]
        }
    }
    return _msg("📢 家族公積金異動通知", contents)


def settled_push_notification(event_name: str, family_unit: str,
                               settled_by: str) -> FlexMessage:
    contents = {
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "horizontal",
            "backgroundColor": "#1E8449", "paddingAll": "12px",
            "contents": [{"type": "text", "text": "✅ 費用結清通知",
                           "color": "#FFFFFF", "size": "md", "weight": "bold"}]
        },
        "body": {
            "type": "box", "layout": "vertical",
            "spacing": "sm", "paddingAll": "14px",
            "contents": [
                _row("活動", event_name),
                _row("家庭", family_unit),
                _row("確認人", settled_by),
                {"type": "separator"},
                {
                    "type": "box", "layout": "horizontal",
                    "backgroundColor": "#D5F5E3", "cornerRadius": "6px",
                    "paddingAll": "10px",
                    "contents": [
                        {"type": "text",
                         "text": f"✅ {family_unit} 已完成結清",
                         "color": "#1E8449", "size": "sm",
                         "weight": "bold", "align": "center"},
                    ]
                },
            ]
        }
    }
    return _msg(f"✅ {family_unit} 費用結清通知", contents)

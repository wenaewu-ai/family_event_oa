"""
Google Sheets 讀寫工具
所有資料操作都透過此模組進行
"""
import os
import json
import time
import logging
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

SPREADSHEET_ID = os.environ["GOOGLE_SPREADSHEET_ID"]

# Sheet 名稱常數
SH_MEMBERS   = "成員清單"
SH_FUND      = "公積金總帳"
SH_EVENTS    = "活動清單"
SH_EXPENSES  = "活動費用明細"
SH_STATE     = "對話狀態"

# 成員清單快取（5 分鐘）
_member_cache: dict = {}
_member_cache_time: float = 0
CACHE_TTL = 300  # 秒


def _get_client() -> gspread.Client:
    """建立 gspread 客戶端"""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(
            os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json"),
            scopes=SCOPES,
        )
    return gspread.authorize(creds)


def _get_sheet(sheet_name: str):
    client = _get_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    return spreadsheet.worksheet(sheet_name)


def _normalize_records(rows: list[dict]) -> list[dict]:
    """將表頭的 \\n(...) 說明文字去掉，例如 'line_user_id\\n(LINE userId)' → 'line_user_id'"""
    return [{k.split("\n")[0]: v for k, v in r.items()} for r in rows]


def now_str() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M")


# ─────────────────────────────────────────────────
# 成員管理
# ─────────────────────────────────────────────────

def get_all_members() -> list[dict]:
    """取得所有成員（5 分鐘快取）"""
    global _member_cache, _member_cache_time
    if time.time() - _member_cache_time < CACHE_TTL and _member_cache:
        return list(_member_cache.values())
    ws = _get_sheet(SH_MEMBERS)
    rows = _normalize_records(ws.get_all_records(head=3))
    _member_cache = {r["line_user_id"]: r for r in rows if r.get("line_user_id")}
    _member_cache_time = time.time()
    return list(_member_cache.values())


def get_member(user_id: str) -> Optional[dict]:
    """依 line_user_id 取得成員資料"""
    get_all_members()  # 確保快取已載入
    return _member_cache.get(user_id)


def is_admin(user_id: str) -> bool:
    member = get_member(user_id)
    return bool(member and member.get("role") == "管理員")


def register_member(user_id: str, display_name: str):
    """新成員初次加入時自動建立待確認記錄"""
    if get_member(user_id):
        return  # 已存在
    ws = _get_sheet(SH_MEMBERS)
    ws.append_row([user_id, display_name, "", "成員", now_str(), "待分配家庭"])
    global _member_cache_time
    _member_cache_time = 0  # 清除快取


# ─────────────────────────────────────────────────
# 公積金總帳
# ─────────────────────────────────────────────────

def get_fund_balance() -> dict:
    """取得目前公積金餘額與最後異動資訊"""
    ws = _get_sheet(SH_FUND)
    rows = _normalize_records(ws.get_all_records(head=4))  # 第4列為表頭
    if not rows:
        # 讀取期初餘額（E3）
        init = ws.acell("E3").value or "0"
        return {"balance": int(str(init).replace(",", "")), "last_op": None}
    last = rows[-1]
    return {
        "balance": int(str(last.get("balance_after", 0)).replace(",", "")),
        "last_op": {
            "type": last.get("type"),
            "amount": last.get("amount"),
            "description": last.get("description"),
            "operator": last.get("operator"),
            "timestamp": last.get("timestamp"),
        },
    }


def add_fund_transaction(tx_type: str, amount: int, description: str,
                          operator: str, ref_event_id: str = "") -> dict:
    """新增公積金收支記錄"""
    ws = _get_sheet(SH_FUND)
    rows = _normalize_records(ws.get_all_records(head=4))

    if rows:
        prev_balance = int(str(rows[-1].get("balance_after", 0)).replace(",", ""))
    else:
        init = ws.acell("E3").value or "0"
        prev_balance = int(str(init).replace(",", ""))

    if tx_type == "收入":
        new_balance = prev_balance + amount
    else:
        new_balance = prev_balance - amount

    ws.append_row([
        now_str(), tx_type, amount, description,
        operator, new_balance, ref_event_id
    ])
    return {"balance": new_balance, "amount": amount, "type": tx_type}


# ─────────────────────────────────────────────────
# 活動管理
# ─────────────────────────────────────────────────

def get_events(status_filter: str = None) -> list[dict]:
    """取得活動列表"""
    ws = _get_sheet(SH_EVENTS)
    rows = _normalize_records(ws.get_all_records(head=3))
    if status_filter:
        rows = [r for r in rows if r.get("status") == status_filter]
    return rows


def get_event(event_id: str) -> Optional[dict]:
    events = get_events()
    for e in events:
        if e.get("event_id") == event_id:
            return e
    return None


def create_event(event_id: str, event_name: str, event_date: str,
                  created_by: str) -> dict:
    ws = _get_sheet(SH_EVENTS)
    ws.append_row([event_id, event_name, event_date, "進行中", 0, 0, 0, created_by])
    return {"event_id": event_id, "event_name": event_name}


# ─────────────────────────────────────────────────
# 活動費用明細
# ─────────────────────────────────────────────────

def get_event_expenses(event_id: str) -> list[dict]:
    ws = _get_sheet(SH_EXPENSES)
    rows = _normalize_records(ws.get_all_records(head=3))
    return [r for r in rows if r.get("event_id") == event_id]


def get_family_expenses(event_id: str, family_unit: str) -> list[dict]:
    return [r for r in get_event_expenses(event_id)
            if r.get("family_unit") == family_unit]


def submit_expense(event_id: str, family_unit: str, submitter: str,
                    item_name: str, amount: int,
                    receipt_url: str = "") -> dict:
    ws = _get_sheet(SH_EXPENSES)
    ws.append_row([
        event_id, family_unit, submitter, item_name,
        amount, receipt_url, now_str(),
        "FALSE", "", ""
    ])
    return {"event_id": event_id, "family_unit": family_unit,
            "item_name": item_name, "amount": amount}


def mark_family_settled(event_id: str, family_unit: str, settled_by: str):
    """將指定家庭的所有費用標記為已結清"""
    ws = _get_sheet(SH_EXPENSES)
    rows = ws.get_all_values()
    header_row = 3  # 表頭在第3列

    # 欄位索引（0-based）
    headers = rows[header_row - 1]
    idx = {h: i for i, h in enumerate(headers)}

    updated = 0
    for i, row in enumerate(rows[header_row:], start=header_row + 1):
        if (len(row) > idx.get("event_id", 0) and
                row[idx["event_id"]] == event_id and
                row[idx["family_unit"]] == family_unit and
                row[idx["is_settled"]] != "TRUE"):
            # 更新 is_settled, settled_at, settled_by
            ws.update_cell(i, idx["is_settled"] + 1, "TRUE")
            ws.update_cell(i, idx["settled_at"] + 1, now_str())
            ws.update_cell(i, idx["settled_by"] + 1, settled_by)
            updated += 1
            time.sleep(0.3)  # Sheets API 速率限制

    return updated


def calculate_split(event_id: str) -> dict:
    """計算費用分攤"""
    expenses = get_event_expenses(event_id)
    if not expenses:
        return {"total": 0, "families": [], "per_unit": 0, "settled_count": 0, "total_families": 0}

    families: dict[str, dict] = {}
    for exp in expenses:
        fu = exp.get("family_unit", "")
        if fu not in families:
            families[fu] = {"paid": 0, "items": [], "is_settled": True}
        families[fu]["paid"] += int(str(exp.get("amount", 0)).replace(",", ""))
        families[fu]["items"].append(exp)
        if exp.get("is_settled") != "TRUE":
            families[fu]["is_settled"] = False

    total = sum(f["paid"] for f in families.values())
    count = len(families)
    per_unit = round(total / count) if count else 0

    result = []
    for name, data in families.items():
        result.append({
            "family_unit": name,
            "paid": data["paid"],
            "per_unit": per_unit,
            "balance": data["paid"] - per_unit,
            "is_settled": data["is_settled"],
            "item_count": len(data["items"]),
        })

    settled_count = sum(1 for f in result if f["is_settled"])
    return {
        "total": total,
        "per_unit": per_unit,
        "families": result,
        "settled_count": settled_count,
        "total_families": count,
    }


# ─────────────────────────────────────────────────
# 對話狀態管理（多步驟流程）
# ─────────────────────────────────────────────────

def get_state(user_id: str) -> Optional[dict]:
    ws = _get_sheet(SH_STATE)
    rows = _normalize_records(ws.get_all_records(head=3))
    now = datetime.now()
    for r in rows:
        if r.get("line_user_id") == user_id:
            expires = r.get("expires_at", "")
            try:
                exp_dt = datetime.strptime(str(expires), "%Y/%m/%d %H:%M")
                if exp_dt > now:
                    return {"state": r.get("state"), "data": json.loads(r.get("temp_data", "{}"))}
            except (ValueError, json.JSONDecodeError):
                pass
    return None


def set_state(user_id: str, state: str, data: dict, ttl_seconds: int = 300):
    ws = _get_sheet(SH_STATE)
    expires = (datetime.now() + timedelta(seconds=ttl_seconds)).strftime("%Y/%m/%d %H:%M")
    updated_at = now_str()
    rows = ws.get_all_values()
    header_row = 3

    for i, row in enumerate(rows[header_row:], start=header_row + 1):
        if row and row[0] == user_id:
            ws.update(f"A{i}:E{i}", [[
                user_id, state, json.dumps(data, ensure_ascii=False),
                expires, updated_at
            ]])
            return

    ws.append_row([user_id, state, json.dumps(data, ensure_ascii=False), expires, updated_at])


def clear_state(user_id: str):
    ws = _get_sheet(SH_STATE)
    rows = ws.get_all_values()
    header_row = 3
    for i, row in enumerate(rows[header_row:], start=header_row + 1):
        if row and row[0] == user_id:
            ws.delete_rows(i)
            return

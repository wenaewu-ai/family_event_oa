"""
家族 LINE OA 記帳系統 - 主程式入口
"""
import os
import logging
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.webhooks import (
    MessageEvent, TextMessageContent,
    PostbackEvent, FollowEvent,
    JoinEvent
)

from handlers.postback import handle_postback
from handlers.message import handle_message
from handlers.follow import handle_follow, handle_join

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# LINE SDK 設定
configuration = Configuration(access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["LINE_CHANNEL_SECRET"])

# 允許的群組 ID（空字串表示不限制）
ALLOWED_GROUP_ID = os.environ.get("ALLOWED_GROUP_ID", "")


def is_allowed_source(event) -> bool:
    """檢查訊息來源是否在允許的群組內"""
    if not ALLOWED_GROUP_ID:
        return True
    source = event.source
    group_id = getattr(source, "group_id", None)
    return group_id == ALLOWED_GROUP_ID or group_id is None


@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    logger.info("Webhook received")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        abort(400)
    return "OK"


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "service": "family-line-oa"}


@handler.add(PostbackEvent)
def on_postback(event):
    if not is_allowed_source(event):
        return
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        handle_postback(event, line_bot_api)


@handler.add(MessageEvent, message=TextMessageContent)
def on_message(event):
    if not is_allowed_source(event):
        return
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        handle_message(event, line_bot_api)


@handler.add(FollowEvent)
def on_follow(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        handle_follow(event, line_bot_api)


@handler.add(JoinEvent)
def on_join(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        handle_join(event, line_bot_api)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)

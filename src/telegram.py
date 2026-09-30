import os

import requests


# ============================================================
# Telegram Config
# ============================================================

TELEGRAM_API_BASE = "https://api.telegram.org"


def _get_config():
    token = (
        os.getenv("TELEGRAM_BOT_TOKEN")
        or ""
    ).strip()

    chat_id = (
        os.getenv("TELEGRAM_CHAT_ID")
        or ""
    ).strip()

    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN 未設定"
        )

    if not chat_id:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID 未設定"
        )

    return token, chat_id


# ============================================================
# Send message
# ============================================================

def send_message(
    message: str,
) -> int | None:
    """
    發送 Telegram 訊息。

    成功：
        回傳 Telegram message_id

    失敗：
        印出 Telegram API 詳細錯誤
        並重新 raise，讓 main.py 可以正確處理。
    """

    token, chat_id = _get_config()

    url = (
        f"{TELEGRAM_API_BASE}"
        f"/bot{token}"
        f"/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }

    print(
        "========== TELEGRAM SEND =========="
    )

    print(
        f"chat_id = {chat_id}"
    )

    print(
        f"message_length = {len(message)}"
    )

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=20,
        )

    except requests.RequestException as error:

        print(
            "TELEGRAM NETWORK ERROR"
        )

        print(
            f"{error}"
        )

        raise

    print(
        f"TELEGRAM HTTP STATUS: "
        f"{response.status_code}"
    )

    print(
        f"TELEGRAM CONTENT TYPE: "
        f"{response.headers.get('Content-Type')}"
    )

    # --------------------------------------------------------
    # Telegram API 即使 HTTP 400，
    # body 通常會告訴我們真正原因。
    # --------------------------------------------------------

    try:

        data = response.json()

    except ValueError:

        data = None

    if not response.ok:

        print(
            "========== TELEGRAM ERROR =========="
        )

        print(
            f"response_text = "
            f"{response.text[:2000]}"
        )

        if isinstance(data, dict):

            print(
                f"ok = "
                f"{data.get('ok')}"
            )

            print(
                f"error_code = "
                f"{data.get('error_code')}"
            )

            print(
                f"description = "
                f"{data.get('description')}"
            )

        print(
            "===================================="
        )

        response.raise_for_status()

    # --------------------------------------------------------
    # 檢查 Telegram API 回傳
    # --------------------------------------------------------

    if not isinstance(data, dict):

        raise RuntimeError(
            "Telegram API 回傳不是 JSON"
        )

    if not data.get("ok"):

        raise RuntimeError(
            "Telegram API 回傳 ok=false: "
            f"{data}"
        )

    result = data.get(
        "result"
    )

    if not isinstance(
        result,
        dict
    ):

        raise RuntimeError(
            "Telegram API 缺少 result"
        )

    message_id = result.get(
        "message_id"
    )

    print(
        f"TELEGRAM MESSAGE ID: "
        f"{message_id}"
    )

    print(
        "===================================="
    )

    return message_id

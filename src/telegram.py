import os
import re

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
# Message Filter
#
# 訊息必須包含「桃園」或「新北」其中一個，
# 才允許發送 Telegram。
# ============================================================

REQUIRED_KEYWORDS = [
    "桃園",
    "新北",
]


def contains_required_keyword(
    message: str,
) -> bool:
    """
    檢查訊息是否包含必要關鍵字。

    只要包含：
        桃園
    或：
        新北

    就允許發送。

    如果兩個都沒有，則不發送。
    """

    return any(
        keyword in message
        for keyword in REQUIRED_KEYWORDS
    )


# ============================================================
# Secret redaction
#
# requests 的例外訊息會包含完整 URL（含 /bot<TOKEN>/），
# 直接 print 會把 Bot Token 寫進 GitHub Actions log，
# 或經由系統錯誤通知傳到 Telegram。
# ============================================================

def redact(text) -> str:
    text = str(text)

    token = (
        os.getenv("TELEGRAM_BOT_TOKEN")
        or ""
    ).strip()

    if token:
        text = text.replace(
            token,
            "***",
        )

    # 保險：即使 env 不同，也遮蔽 /bot<...>/ 樣式
    return re.sub(
        r"/bot[^/\s]+/",
        "/bot***/",
        text,
    )


# ============================================================
# Send message
# ============================================================

def send_message(
    message: str,
) -> int | None:
    """
    發送 Telegram 訊息。

    發送條件：
        訊息必須包含「桃園」或「新北」。

    成功：
        回傳 Telegram message_id

    未符合關鍵字：
        不發送，回傳 None

    失敗：
        印出 Telegram API 詳細錯誤
        並重新 raise，讓 main.py 可以正確處理。
    """

    # --------------------------------------------------------
    # 確保 message 是字串
    # --------------------------------------------------------

    if not isinstance(
        message,
        str,
    ):
        message = str(message)

    # --------------------------------------------------------
    # 發送前關鍵字過濾
    #
    # 必須包含「桃園」或「新北」
    # --------------------------------------------------------

    if not contains_required_keyword(
        message
    ):

        print(
            "========== TELEGRAM SKIPPED =========="
        )

        print(
            "訊息未包含必要關鍵字"
        )

        print(
            "必要關鍵字：桃園 / 新北"
        )

        print(
            f"message_length = {len(message)}"
        )

        print(
            "訊息不發送至 Telegram"
        )

        print(
            "======================================"
        )

        return None

    # --------------------------------------------------------
    # 取得 Telegram 設定
    # --------------------------------------------------------

    token, chat_id = _get_config()

    # --------------------------------------------------------
    # Telegram API URL
    # --------------------------------------------------------

    url = (
        f"{TELEGRAM_API_BASE}"
        f"/bot{token}"
        f"/sendMessage"
    )

    # --------------------------------------------------------
    # Telegram payload
    # --------------------------------------------------------

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
            redact(error)
        )

        raise RuntimeError(
            "Telegram 網路錯誤: "
            f"{redact(error)}"
        ) from None

    # --------------------------------------------------------
    # HTTP Status
    # --------------------------------------------------------

    print(
        f"TELEGRAM HTTP STATUS: "
        f"{response.status_code}"
    )

    print(
        f"TELEGRAM CONTENT TYPE: "
        f"{response.headers.get('Content-Type')}"
    )

    # --------------------------------------------------------
    # Telegram API Response
    # --------------------------------------------------------

    try:

        data = response.json()

    except ValueError:

        data = None

    # --------------------------------------------------------
    # HTTP Error
    # --------------------------------------------------------

    if not response.ok:

        print(
            "========== TELEGRAM ERROR =========="
        )

        print(
            f"response_text = "
            f"{redact(response.text[:2000])}"
        )

        if isinstance(
            data,
            dict,
        ):

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

        description = ""

        if isinstance(
            data,
            dict,
        ):

            description = data.get(
                "description",
                "",
            )

        raise RuntimeError(
            f"Telegram HTTP "
            f"{response.status_code}: "
            f"{redact(description)}"
        )

    # --------------------------------------------------------
    # 檢查 Telegram API 回傳
    # --------------------------------------------------------

    if not isinstance(
        data,
        dict,
    ):

        raise RuntimeError(
            "Telegram API 回傳不是 JSON"
        )

    if not data.get("ok"):

        raise RuntimeError(
            "Telegram API 回傳 ok=false: "
            f"{redact(data)}"
        )

    # --------------------------------------------------------
    # 取得 result
    # --------------------------------------------------------

    result = data.get(
        "result"
    )

    if not isinstance(
        result,
        dict,
    ):

        raise RuntimeError(
            "Telegram API 缺少 result"
        )

    # --------------------------------------------------------
    # 取得 message_id
    # --------------------------------------------------------

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

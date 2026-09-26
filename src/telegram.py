import os
import requests


TELEGRAM_BOT_TOKEN = os.environ[
    "TELEGRAM_BOT_TOKEN"
]

TELEGRAM_CHAT_ID = os.environ[
    "TELEGRAM_CHAT_ID"
]


def send_message(
    message: str
) -> int:

    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }

    response = requests.post(
        url,
        json=payload,
        timeout=30
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {result}"
        )

    return result["result"]["message_id"]

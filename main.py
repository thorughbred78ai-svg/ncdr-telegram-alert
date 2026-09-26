import os
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import requests


NCDR_API_KEY = os.environ["NCDR_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = Path("data/sent_alerts.json")


def load_state():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
    except Exception:
        return {}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def get_ncdr_alerts():
    """
    這裡放 NCDR 新版 API endpoint。

    NCDR 官方 API 架構包含：
    - group
    - dataListet
    - dataListtore
    - dump

    實際 endpoint 及 query parameter
    依你的 API Key / API 文件設定。
    """

    url = (
        "https://alerts.ncdr.nat.gov.tw/"
        "webapi/..."
    )

    headers = {
        "Accept": "application/json"
    }

    params = {
        "apikey": NCDR_API_KEY
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


def make_alert_id(alert):
    """
    優先使用 NCDR/CAP 自帶 ID。
    沒有的話才用內容產生 hash。
    """

    for key in [
        "capid",
        "capId",
        "id",
        "identifier"
    ]:
        if alert.get(key):
            return str(alert[key])

    raw = json.dumps(
        alert,
        ensure_ascii=False,
        sort_keys=True
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def format_message(alert):
    alert_type = (
        alert.get("alert_type")
        or alert.get("type")
        or "災害示警"
    )

    area = (
        alert.get("area")
        or alert.get("location")
        or "未提供"
    )

    description = (
        alert.get("description")
        or alert.get("headline")
        or "未提供"
    )

    published = (
        alert.get("published")
        or alert.get("effective")
        or "未提供"
    )

    return f"""🚨 NCDR 災害示警

⚠️ 類型：{alert_type}
📍 地區：{area}
🕐 時間：{published}

📋 說明：
{description}

🔔 本訊息由 NCDR 自動取得
"""


def send_telegram(message):
    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
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


def main():
    print("開始取得 NCDR 示警...")

    state = load_state()

    data = get_ncdr_alerts()

    # TODO:
    # 依 NCDR API 實際回傳格式調整
    alerts = data.get("alerts", [])

    print(f"取得 {len(alerts)} 筆示警")

    new_count = 0

    for alert in alerts:

        alert_id = make_alert_id(alert)

        if alert_id in state:
            print(
                f"SKIP 已推播: {alert_id}"
            )
            continue

        message = format_message(alert)

        print(
            f"NEW 新示警: {alert_id}"
        )

        send_telegram(message)

        state[alert_id] = {
            "sent_at": datetime.now(
                timezone.utc
            ).isoformat()
        }

        new_count += 1

    save_state(state)

    print(
        f"完成，本次新增推播 {new_count} 筆"
    )


if __name__ == "__main__":
    main()

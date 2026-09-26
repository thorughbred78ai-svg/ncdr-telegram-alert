import json
import os
from datetime import datetime, timezone

from ncdr import get_alerts
from telegram import send_message
from filter import is_wanted_alert
from state import (
    load_state,
    save_state,
    calculate_hash,
    cleanup_state
)


CONFIG_FILE = "config/config.json"


def load_config():
    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


def format_alert(alert: dict, updated: bool) -> str:

    title = (
        "🔄 NCDR 災害示警更新"
        if updated
        else "🚨 NCDR 災害示警"
    )

    event = (
        alert.get("event")
        or "災害示警"
    )

    headline = (
        alert.get("headline")
        or event
    )

    area = (
        alert.get("area")
        or "未提供"
    )

    effective = (
        alert.get("effective")
        or "未提供"
    )

    expires = (
        alert.get("expires")
        or "未提供"
    )

    description = (
        alert.get("description")
        or "未提供"
    )

    instruction = (
        alert.get("instruction")
        or ""
    )

    message = f"""{
title
}

━━━━━━━━━━━━━━
⚠️ {headline}
━━━━━━━━━━━━━━

📍 影響地區
{area}

🕐 生效時間
{effective}

⛔ 失效時間
{expires}

📋 示警內容
{description}
"""

    if instruction:
        message += f"""
    
🛡️ 建議措施
{instruction}
"""

    message += """
━━━━━━━━━━━━━━
資料來源：NCDR
"""

    return message.strip()


def send_error_notification(
    error: Exception,
    state: dict,
    cooldown_minutes: int
):
    """
    避免 NCDR API 掛掉時每 5 分鐘通知一次。
    """

    now = datetime.now(timezone.utc)

    last_error = state.get("__system_error__")

    if last_error:
        last_time = last_error.get("sent_at")

        if last_time:
            try:
                previous = datetime.fromisoformat(
                    last_time.replace(
                        "Z",
                        "+00:00"
                    )
                )

                seconds = (
                    now - previous
                ).total_seconds()

                if seconds < cooldown_minutes * 60:
                    return

            except ValueError:
                pass

    message = f"""⚠️ NCDR Bot 系統異常

目前無法取得 NCDR 資料。

時間：
{now.isoformat()}

錯誤：
{str(error)[:500]}

請檢查 GitHub Actions。
"""

    try:
        send_message(message)

        state["__system_error__"] = {
            "sent_at": now.isoformat()
        }

    except Exception:
        # Telegram 本身也故障時，
        # 不要讓錯誤處理再造成另一個例外。
        pass


def main():

    config = load_config()

    state = load_state()

    state = cleanup_state(
        state,
        config.get(
            "state_retention_days",
            30
        )
    )

    try:

        alerts = get_alerts()

        print(
            f"NCDR 取得 {len(alerts)} 筆資料"
        )

    except Exception as error:

        print(
            f"NCDR API ERROR: {error}"
        )

        send_error_notification(
            error,
            state,
            config.get(
                "error_notification_cooldown_minutes",
                60
            )
        )

        save_state(state)

        # 不讓 GitHub Actions 因 API 暫時錯誤
        # 直接變成無法辨識的狀態
        return

    new_count = 0
    update_count = 0

    for alert in alerts:

        if not is_wanted_alert(
            alert,
            config
        ):
            continue

        alert_id = alert["id"]

        content_hash = calculate_hash(
            alert
        )

        previous = state.get(
            alert_id
        )

        # 完全沒有看過
        if previous is None:

            message = format_alert(
                alert,
                updated=False
            )

            telegram_message_id = send_message(
                message
            )

            state[alert_id] = {
                "hash": content_hash,
                "sent_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "telegram_message_id":
                    telegram_message_id
            }

            new_count += 1

            print(
                f"NEW: {alert_id}"
            )

            continue

        # 已經推播過，而且內容沒有變
        if previous.get("hash") == content_hash:

            print(
                f"SKIP: {alert_id}"
            )

            continue

        # 同一 CAP ID，但內容已經變更
        message = format_alert(
            alert,
            updated=True
        )

        telegram_message_id = send_message(
            message
        )

        state[alert_id] = {
            "hash": content_hash,
            "sent_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "telegram_message_id":
                telegram_message_id
        }

        update_count += 1

        print(
            f"UPDATE: {alert_id}"
        )

    # 成功取得 API 後，
    # 清除舊的系統錯誤狀態
    state.pop(
        "__system_error__",
        None
    )

    save_state(state)

    print(
        f"完成：新增 {new_count}，"
        f"更新 {update_count}"
    )


if __name__ == "__main__":
    main()

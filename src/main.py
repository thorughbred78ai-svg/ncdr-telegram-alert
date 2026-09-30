import json
from datetime import datetime, timezone, timedelta

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

# ============================================================
# 12 小時內相同警報不重複推播
# ============================================================

DUPLICATE_SUPPRESSION_HOURS = 12


def load_config():

    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def format_alert(
    alert: dict,
    updated: bool
) -> str:

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
        or alert.get("matched_area")
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
    避免 NCDR API 掛掉時重複通知。
    """

    now = datetime.now(
        timezone.utc
    )

    last_error = state.get(
        "__system_error__"
    )

    if last_error:

        last_time = (
            last_error.get(
                "sent_at"
            )
        )

        if last_time:

            try:

                previous = (
                    datetime.fromisoformat(
                        last_time.replace(
                            "Z",
                            "+00:00"
                        )
                    )
                )

                seconds = (
                    now - previous
                ).total_seconds()

                if (
                    seconds
                    < cooldown_minutes * 60
                ):

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

        send_message(
            message
        )

        state["__system_error__"] = {
            "sent_at":
                now.isoformat()
        }

    except Exception:

        pass


def parse_sent_time(
    value: str
):
    """
    將 state 裡的 sent_at
    轉成 timezone-aware datetime。

    舊資料如果沒有時區，
    一律視為 UTC。
    """

    if not value:

        return None

    try:

        parsed = (
            datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00"
                )
            )
        )

        if parsed.tzinfo is None:

            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    except (
        ValueError,
        TypeError
    ):

        return None


def was_sent_within_12_hours(
    previous: dict,
    now: datetime
) -> bool:
    """
    判斷同一 alert ID
    是否在 12 小時內已經推播。

    注意：

    這裡只看 sent_at，
    不看 hash。

    因此即使 NCDR API 回傳相同
    或稍微不同的內容，
    只要同一 ID 在 12 小時內
    已經推播過，就不再推播。
    """

    sent_at = parse_sent_time(
        previous.get(
            "sent_at"
        )
    )

    if sent_at is None:

        return False

    elapsed = (
        now - sent_at
    )

    # 如果時間異常，例如 GitHub Actions
    # 時鐘與 state 不一致，
    # 不直接阻擋新的警報。
    if elapsed.total_seconds() < 0:

        return False

    return (
        elapsed
        < timedelta(
            hours=DUPLICATE_SUPPRESSION_HOURS
        )
    )


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
            f"NCDR 取得 "
            f"{len(alerts)} 筆資料"
        )

    except Exception as error:

        print(
            f"NCDR API ERROR: "
            f"{error}"
        )

        send_error_notification(
            error,
            state,
            config.get(
                "error_notification_cooldown_minutes",
                60
            )
        )

        save_state(
            state
        )

        return

    new_count = 0
    update_count = 0
    duplicate_count = 0

    now = datetime.now(
        timezone.utc
    )

    # ========================================================
    # Process alerts
    # ========================================================

    for alert in alerts:

        # ----------------------------------------------------
        # 先執行地區 + 災害類型過濾
        # ----------------------------------------------------

        if not is_wanted_alert(
            alert,
            config
        ):

            continue

        alert_id = alert.get(
            "id"
        )

        if not alert_id:

            print(
                "SKIP: alert 沒有 ID"
            )

            continue

        content_hash = (
            calculate_hash(
                alert
            )
        )

        previous = state.get(
            alert_id
        )

        # ====================================================
        # 第一次看到這個 alert
        # ====================================================

        if previous is None:

            message = format_alert(
                alert,
                updated=False
            )

            telegram_message_id = (
                send_message(
                    message
                )
            )

            state[alert_id] = {

                "hash":
                    content_hash,

                "sent_at":
                    now.isoformat(),

                "telegram_message_id":
                    telegram_message_id
            }

            new_count += 1

            print(
                f"NEW: {alert_id}"
            )

            continue

        # ====================================================
        # 12 小時內已經推播
        #
        # 不管 hash 有沒有改變，
        # 都不再次推播。
        # ====================================================

        if was_sent_within_12_hours(
            previous,
            now
        ):

            duplicate_count += 1

            print(
                f"SKIP 12H: "
                f"{alert_id} | "
                f"最近推播時間="
                f"{previous.get('sent_at')}"
            )

            # 更新 hash，但不更新 sent_at。
            #
            # 這樣可以記住目前最新內容，
            # 同時 12 小時限制仍然從原本推播時間計算。
            state[alert_id] = {

                "hash":
                    content_hash,

                "sent_at":
                    previous.get(
                        "sent_at"
                    ),

                "telegram_message_id":
                    previous.get(
                        "telegram_message_id"
                    )
            }

            continue

        # ====================================================
        # 超過 12 小時
        #
        # 如果內容沒有變：
        # 不需要再次推播。
        # ====================================================

        if (
            previous.get("hash")
            == content_hash
        ):

            print(
                f"SKIP SAME: "
                f"{alert_id}"
            )

            continue

        # ====================================================
        # 超過 12 小時，而且內容有更新
        #
        # 再次推播 UPDATE
        # ====================================================

        message = format_alert(
            alert,
            updated=True
        )

        telegram_message_id = (
            send_message(
                message
            )
        )

        state[alert_id] = {

            "hash":
                content_hash,

            "sent_at":
                now.isoformat(),

            "telegram_message_id":
                telegram_message_id
        }

        update_count += 1

        print(
            f"UPDATE: "
            f"{alert_id}"
        )

    # ========================================================
    # 成功取得 API
    # 清除系統錯誤狀態
    # ========================================================

    state.pop(
        "__system_error__",
        None
    )

    save_state(
        state
    )

    print(
        f"完成：新增 {new_count}，"
        f"更新 {update_count}，"
        f"12小時內跳過 {duplicate_count}"
    )


if __name__ == "__main__":

    main()

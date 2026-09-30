import json
from datetime import datetime, timezone, timedelta

from ncdr import get_alerts, should_send_alert
from telegram import send_message, redact
from state import (
    load_state,
    save_state,
    calculate_hash,
    cleanup_state,
)


# ============================================================
# Config
# ============================================================

CONFIG_FILE = "config/config.json"

# 同一個 NCDR alert ID 在這段時間內不重複推播
DUPLICATE_SUPPRESSION_HOURS = 12


# ============================================================
# Load config
# ============================================================

def load_config() -> dict:
    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


# ============================================================
# Time helpers
# ============================================================

def parse_sent_time(value: str):
    """
    將 state 裡的 sent_at 轉成 timezone-aware datetime。

    支援：
        2026-09-30T15:30:00+00:00
        2026-09-30T15:30:00Z

    如果舊資料沒有時區，
    一律視為 UTC。
    """

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    except (
        ValueError,
        TypeError,
    ):
        return None


def was_sent_within_12_hours(
    previous: dict,
    now: datetime,
) -> bool:
    """
    判斷同一個 alert ID
    是否在最近 12 小時內已經推播。

    注意：
    只看 sent_at，
    不看 hash。

    因此：

        同一 ID
        + 12 小時內
        + 即使內容有更新

    都不會再次推播。
    """

    sent_at = parse_sent_time(
        previous.get("sent_at")
    )

    if sent_at is None:
        return False

    elapsed = now - sent_at

    # 時間異常時不要阻擋推播
    if elapsed.total_seconds() < 0:
        return False

    return (
        elapsed
        < timedelta(
            hours=DUPLICATE_SUPPRESSION_HOURS
        )
    )


# ============================================================
# Format Telegram message
# ============================================================

# Telegram 單則訊息上限 4096 字元；超過會 HTTP 400 導致整則失敗。
# 各欄位設上限，確保總長度安全，且「影響地區」一定保留。
def _clip(text: str, limit: int) -> str:

    text = text or ""

    if len(text) <= limit:
        return text

    return text[:limit].rstrip() + "…（內容過長已截斷，請見 NCDR 原文）"


def format_alert(
    alert: dict,
    updated: bool,
) -> str:
    """
    將 NCDR alert 轉成 Telegram 訊息。
    """

    if updated:
        title = "🔄 NCDR 災害示警更新"
    else:
        title = "🚨 NCDR 災害示警"

    event = (
        alert.get("event")
        or alert.get("category")
        or "災害示警"
    )

    headline = (
        alert.get("headline")
        or event
    )

    # --------------------------------------------------------
    # 地區
    #
    # ncdr.py 已經完成地區判斷。
    #
    # 優先使用：
    #   area
    #
    # 如果 CAP 沒有 area，
    # 使用：
    #   matched_area
    # --------------------------------------------------------

    # 影響地區：以 geocode 實際命中的關注縣市為準（可信來源）。
    # 不再直接顯示 CAP 全部 areaDesc（地震只會是「最大震度N級地區」，
    # 不含縣市名稱，會導致推播前縣市檢查誤擋）。
    matched_areas = alert.get("matched_areas") or []

    if not matched_areas and alert.get("matched_area"):
        matched_areas = [alert["matched_area"]]

    area = "、".join(matched_areas) or "未提供"

    # CAP 原始區域描述（震度區、震央位置等）當作補充資訊
    raw_area = _clip(
        alert.get("area")
        or "",
        500,
    )

    effective = (
        alert.get("effective")
        or "未提供"
    )

    expires = (
        alert.get("expires")
        or "未提供"
    )

    description = _clip(
        alert.get("description")
        or "未提供",
        1500,
    )

    instruction = _clip(
        alert.get("instruction")
        or "",
        800,
    )

    message = f"""\
{title}

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

    if raw_area:
        message += f"""
🗺️ 區域說明
{raw_area}
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


# ============================================================
# System error notification
# ============================================================

def send_error_notification(
    error: Exception,
    state: dict,
    cooldown_minutes: int,
):
    """
    NCDR API 發生錯誤時通知 Telegram。

    為避免 GitHub Actions 每 5 分鐘失敗一次，
    系統錯誤通知有 cooldown。
    """

    now = datetime.now(
        timezone.utc
    )

    last_error = state.get(
        "__system_error__"
    )

    # --------------------------------------------------------
    # 檢查上一次錯誤通知時間
    # --------------------------------------------------------

    if last_error:
        last_time = last_error.get(
            "sent_at"
        )

        if last_time:
            previous = parse_sent_time(
                last_time
            )

            if previous is not None:
                elapsed = (
                    now - previous
                ).total_seconds()

                if elapsed < (
                    cooldown_minutes * 60
                ):
                    print(
                        "SKIP SYSTEM ERROR "
                        "NOTIFICATION: cooldown"
                    )

                    return

    # --------------------------------------------------------
    # 建立錯誤訊息
    # --------------------------------------------------------

    message = f"""\
⚠️ NCDR Bot 系統異常

目前無法取得 NCDR 資料。

時間：
{now.isoformat()}

錯誤：
{redact(error)[:500]}

請檢查 GitHub Actions。
"""

    try:
        send_message(
            message
        )

        state["__system_error__"] = {
            "sent_at":
                now.isoformat(),
        }

        print(
            "SYSTEM ERROR NOTIFICATION SENT"
        )

    except Exception as telegram_error:
        print(
            "SYSTEM ERROR NOTIFICATION FAILED: "
            f"{telegram_error}"
        )


# ============================================================
# Process one alert
# ============================================================

def process_alert(
    alert: dict,
    state: dict,
    now: datetime,
    wanted_areas: list,
) -> str:
    """
    處理單一 NCDR alert。

    回傳：
        "new"
        "update"
        "duplicate"
        "same"
        "skip"
        "blocked"   推播文字未涵蓋關注縣市，未推播
    """

    alert_id = alert.get(
        "id"
    )

    if not alert_id:
        print(
            "SKIP: alert 沒有 ID"
        )

        return "skip"

    alert_id = str(
        alert_id
    )

    # --------------------------------------------------------
    # 計算目前內容 hash
    # --------------------------------------------------------

    content_hash = calculate_hash(
        alert
    )

    previous = state.get(
        alert_id
    )

    # ========================================================
    # NEW
    #
    # 第一次看到這個 NCDR ID
    # ========================================================

    if previous is None:

        print(
            f"NEW ALERT: {alert_id}"
        )

        message = format_alert(
            alert,
            updated=False,
        )

        # 推播前最終檢查：訊息必須含關注縣市，否則不推播、
        # 也不寫入 state（之後條件成立仍可推播）
        if not should_send_alert(
            message,
            alert_id,
            wanted_areas,
        ):
            return "blocked"

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
                telegram_message_id,
        }

        return "new"

    # ========================================================
    # DUPLICATE WITHIN 12 HOURS
    #
    # 不管 hash 是否改變，
    # 12 小時內都不再次推播。
    # ========================================================

    if was_sent_within_12_hours(
        previous,
        now,
    ):

        print(
            f"SKIP 12H: {alert_id} | "
            f"最近推播時間="
            f"{previous.get('sent_at')}"
        )

        # ----------------------------------------------------
        # 更新 hash
        #
        # 但絕對不能更新 sent_at。
        #
        # 否則每次 GitHub Actions 執行，
        # 12 小時都會重新開始計算。
        # ----------------------------------------------------

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
                ),
        }

        return "duplicate"

    # ========================================================
    # 超過 12 小時
    #
    # 如果內容完全沒有變化，
    # 不重新推播。
    # ========================================================

    previous_hash = previous.get(
        "hash"
    )

    if previous_hash == content_hash:

        print(
            f"SKIP SAME: {alert_id}"
        )

        # 保留原 state。
        #
        # 不更新 sent_at，
        # 不產生 Telegram 訊息。

        return "same"

    # ========================================================
    # UPDATE
    #
    # 超過 12 小時
    # 而且內容 hash 已經改變
    # ========================================================

    print(
        f"UPDATE ALERT: {alert_id}"
    )

    message = format_alert(
        alert,
        updated=True,
    )

    if not should_send_alert(
        message,
        alert_id,
        wanted_areas,
    ):
        return "blocked"

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
            telegram_message_id,
    }

    return "update"


# ============================================================
# Main
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "NCDR Telegram Alert Bot"
    )

    print(
        "========================================"
    )

    # ========================================================
    # Config
    # ========================================================

    config = load_config()

    print(
        f"DUPLICATE SUPPRESSION = "
        f"{DUPLICATE_SUPPRESSION_HOURS} hours"
    )

    # ========================================================
    # Load state
    # ========================================================

    state = load_state()

    print(
        f"STATE ITEMS BEFORE CLEANUP = "
        f"{len(state)}"
    )

    state = cleanup_state(
        state,
        config.get(
            "state_retention_days",
            30,
        ),
    )

    print(
        f"STATE ITEMS AFTER CLEANUP = "
        f"{len(state)}"
    )

    # ========================================================
    # Get NCDR alerts
    # ========================================================

    try:

        alerts = get_alerts()

        print(
            f"NCDR 取得 "
            f"{len(alerts)} 筆資料"
        )

    except Exception as error:

        print(
            "NCDR API ERROR: "
            f"{error}"
        )

        send_error_notification(
            error,
            state,
            config.get(
                "error_notification_cooldown_minutes",
                60,
            ),
        )

        save_state(
            state
        )

        return

    # ========================================================
    # NCDR 成功
    #
    # 清除之前的系統錯誤狀態
    # ========================================================

    state.pop(
        "__system_error__",
        None,
    )

    # ========================================================
    # Counters
    # ========================================================

    new_count = 0
    update_count = 0
    duplicate_count = 0
    same_count = 0
    skip_count = 0
    blocked_count = 0
    error_count = 0

    wanted_areas = config.get(
        "areas",
        [],
    )

    # ========================================================
    # Current time
    # ========================================================

    now = datetime.now(
        timezone.utc
    )

    # ========================================================
    # Process alerts
    #
    # 注意：
    #
    # 這裡「不再呼叫 filter.py」。
    #
    # ncdr.py 已經完成：
    #
    #   災害類型過濾
    #   桃園市 / 新北市過濾
    #   地震震度區域判斷
    #
    # 因此 get_alerts() 回傳的資料，
    # 就直接進入 12 小時去重。
    # ========================================================

    for alert in alerts:

        # 單筆失敗（例如 Telegram 暫時錯誤）不可中斷整批，
        # 否則本次已成功推播的警報不會存入 state，下次會重複推播。
        # state 只在 send_message 成功後才寫入，失敗者下次會重試。
        try:

            result = process_alert(
                alert,
                state,
                now,
                wanted_areas,
            )

        except Exception as error:

            print(
                f"ALERT PROCESS ERROR: "
                f"{alert.get('id')} | "
                f"{redact(error)[:300]}"
            )

            error_count += 1

            continue

        if result == "new":
            new_count += 1

        elif result == "update":
            update_count += 1

        elif result == "duplicate":
            duplicate_count += 1

        elif result == "same":
            same_count += 1

        elif result == "blocked":
            blocked_count += 1

        else:
            skip_count += 1

    # ========================================================
    # Save state
    # ========================================================

    save_state(
        state
    )

    # ========================================================
    # Summary
    # ========================================================

    print(
        "========================================"
    )

    print(
        "NCDR PROCESS SUMMARY"
    )

    print(
        f"NCDR alerts      = {len(alerts)}"
    )

    print(
        f"NEW              = {new_count}"
    )

    print(
        f"UPDATE           = {update_count}"
    )

    print(
        f"SKIP 12 HOURS    = {duplicate_count}"
    )

    print(
        f"SKIP SAME        = {same_count}"
    )

    print(
        f"SKIP INVALID     = {skip_count}"
    )

    print(
        f"BLOCKED (NO AREA)= {blocked_count}"
    )

    print(
        f"SEND ERRORS      = {error_count}"
    )

    print(
        "========================================"
    )

    print(
        f"完成：新增 {new_count}，"
        f"更新 {update_count}，"
        f"12小時內跳過 {duplicate_count}，"
        f"相同內容跳過 {same_count}"
    )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()

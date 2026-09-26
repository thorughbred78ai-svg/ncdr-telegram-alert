import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


STATE_FILE = Path("data/sent_alerts.json")


def load_state() -> dict:
    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    STATE_FILE.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def calculate_hash(alert: dict) -> str:
    """
    計算警報內容 hash。
    同一 CAP identifier 但內容改變，
    就可以判斷為更新。
    """

    important_fields = {
        "headline": alert.get("headline", ""),
        "description": alert.get("description", ""),
        "instruction": alert.get("instruction", ""),
        "effective": alert.get("effective", ""),
        "expires": alert.get("expires", ""),
        "area": alert.get("area", "")
    }

    raw = json.dumps(
        important_fields,
        ensure_ascii=False,
        sort_keys=True
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def cleanup_state(
    state: dict,
    retention_days: int = 30
) -> dict:

    cutoff = datetime.now(
        timezone.utc
    ) - timedelta(
        days=retention_days
    )

    cleaned = {}

    for alert_id, record in state.items():

        sent_at = record.get("sent_at")

        if not sent_at:
            continue

        try:
            dt = datetime.fromisoformat(
                sent_at.replace("Z", "+00:00")
            )
        except ValueError:
            continue

        if dt >= cutoff:
            cleaned[alert_id] = record

    return cleaned

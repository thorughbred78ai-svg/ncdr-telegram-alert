from typing import Any
import json


def _text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        return " ".join(
            str(x) for x in value
        )

    if isinstance(value, dict):
        return json.dumps(
            value,
            ensure_ascii=False
        )

    return str(value)


def is_wanted_alert(
    alert: dict,
    config: dict
) -> bool:

    areas = config.get("areas", [])
    alert_types = config.get("alert_types", [])

    # ==========================================
    # 除錯：直接印出 NCDR 原始資料
    # ==========================================

    print("\n========== NCDR ALERT ==========")

    print(
        json.dumps(
            alert,
            ensure_ascii=False,
            indent=2
        )
    )

    print("=================================\n")

    # ==========================================
    # 地區
    # ==========================================

    alert_area = _text(
        alert.get("area")
        or alert.get("area_desc")
        or alert.get("areaDesc")
    )

    # ==========================================
    # 災害類型
    # ==========================================

    event = _text(
        alert.get("event")
    )

    alert_type = _text(
        alert.get("type")
    )

    alert_type_field = _text(
        alert.get("alert_type")
    )

    headline = _text(
        alert.get("headline")
    )

    description = _text(
        alert.get("description")
    )

    # ==========================================
    # 顯示實際比對內容
    # ==========================================

    print("FILTER DEBUG")
    print(f"area       = {alert_area!r}")
    print(f"event      = {event!r}")
    print(f"type       = {alert_type!r}")
    print(f"alert_type = {alert_type_field!r}")
    print(f"headline   = {headline!r}")

    print(
        f"areas      = {areas}"
    )

    print(
        f"alert_types = {alert_types}"
    )

    # ==========================================
    # 地區比對
    # ==========================================

    area_match = any(
        str(area).strip() in alert_area
        for area in areas
        if str(area).strip()
    )

    # ==========================================
    # 災害類型比對
    #
    # 暫時把所有可能包含災害名稱的欄位
    # 都拿來比對
    # ==========================================

    type_text = " ".join(
        [
            event,
            alert_type,
            alert_type_field,
            headline,
            description
        ]
    )

    type_match = any(
        str(keyword).strip() in type_text
        for keyword in alert_types
        if str(keyword).strip()
    )

    print(
        f"area_match = {area_match}"
    )

    print(
        f"type_match = {type_match}"
    )

    result = (
        area_match
        and type_match
    )

    print(
        f"RESULT = {result}"
    )

    return result

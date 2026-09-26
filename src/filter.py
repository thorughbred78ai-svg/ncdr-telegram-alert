from typing import Any


def _text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        return " ".join(str(x) for x in value)

    return str(value)


def is_wanted_alert(alert: dict, config: dict) -> bool:
    """
    判斷警報是否符合：
    1. 指定地區
    2. 指定災害類型
    """

    areas = config.get("areas", [])
    alert_types = config.get("alert_types", [])

    alert_area = _text(
        alert.get("area")
        or alert.get("area_desc")
        or alert.get("areaDesc")
    )

    alert_type = _text(
        alert.get("event")
        or alert.get("type")
        or alert.get("alert_type")
        or alert.get("headline")
    )

    area_match = any(
        area in alert_area
        for area in areas
    )

    type_match = any(
        alert_type_keyword in alert_type
        or alert_type_keyword in _text(
            alert.get("headline")
        )
        for alert_type_keyword in alert_types
    )

    return area_match and type_match

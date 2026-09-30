from typing import Any


def _text(value: Any) -> str:

    if value is None:
        return ""

    if isinstance(value, list):
        return " ".join(
            str(x)
            for x in value
        )

    return str(value)


def is_wanted_alert(
    alert: dict,
    config: dict
) -> bool:

    """
    判斷警報是否符合：

    1. 指定地區
    2. 指定災害類型
    """

    areas = config.get(
        "areas",
        []
    )

    alert_types = config.get(
        "alert_types",
        []
    )

    # ==========================================
    # 地區
    # ==========================================

    alert_area = _text(
        alert.get("area")
    )

    # ==========================================
    # 災害類型
    #
    # 優先使用 NCDR category
    # ==========================================

    alert_type = _text(
        alert.get("category")
        or alert.get("event")
    )

    area_match = any(
        area in alert_area
        for area in areas
    )

    type_match = any(
        alert_type_keyword in alert_type
        for alert_type_keyword in alert_types
    )

    print(
        "\nFILTER DEBUG"
    )

    print(
        f"area       = {alert_area!r}"
    )

    print(
        f"event      = {alert.get('event')!r}"
    )

    print(
        f"category   = {alert.get('category')!r}"
    )

    print(
        f"alert_type = {alert_type!r}"
    )

    print(
        f"headline   = {alert.get('headline')!r}"
    )

    print(
        f"areas      = {areas!r}"
    )

    print(
        f"alert_types = {alert_types!r}"
    )

    print(
        f"area_match = {area_match}"
    )

    print(
        f"type_match = {type_match}"
    )

    print(
        f"RESULT = {area_match and type_match}"
    )

    return (
        area_match
        and type_match
    )

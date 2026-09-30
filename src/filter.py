from typing import Any


def _text(value: Any) -> str:
    """
    將 NCDR 欄位統一轉成字串。
    """
    if value is None:
        return ""

    if isinstance(value, list):
        return " ".join(
            str(x) for x in value
        )

    return str(value)


def is_wanted_alert(
    alert: dict,
    config: dict
) -> bool:
    """
    判斷警報是否符合推播條件：

    1. 必須符合指定地區
    2. 必須符合指定災害類型

    兩個條件都符合才推播。
    """

    areas = config.get(
        "areas",
        []
    )

    alert_types = config.get(
        "alert_types",
        []
    )

    # --------------------------------------------------
    # 取得警報地區
    # --------------------------------------------------

    alert_area = _text(
        alert.get("area")
        or alert.get("area_desc")
        or alert.get("areaDesc")
    )

    # --------------------------------------------------
    # 取得災害類型
    # --------------------------------------------------

    alert_type = _text(
        alert.get("event")
        or alert.get("type")
        or alert.get("alert_type")
    )

    headline = _text(
        alert.get("headline")
    )

    # --------------------------------------------------
    # 地區比對
    # --------------------------------------------------

    area_match = any(
        str(area).strip() in alert_area
        for area in areas
        if str(area).strip()
    )

    # --------------------------------------------------
    # 災害類型比對
    #
    # event / type / alert_type / headline
    # 任一欄位包含關鍵字即可
    # --------------------------------------------------

    type_match = any(
        str(keyword).strip() in alert_type
        or str(keyword).strip() in headline
        for keyword in alert_types
        if str(keyword).strip()
    )

    # --------------------------------------------------
    # Debug
    # --------------------------------------------------

    print(
        f"FILTER: "
        f"area={alert_area!r}, "
        f"type={alert_type!r}, "
        f"headline={headline!r}, "
        f"area_match={area_match}, "
        f"type_match={type_match}"
    )

    return area_match and type_match

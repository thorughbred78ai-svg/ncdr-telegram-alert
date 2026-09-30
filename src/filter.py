def is_wanted_alert(
    alert: dict,
    config: dict
) -> bool:

    areas = config.get(
        "areas",
        []
    )

    alert_types = config.get(
        "alert_types",
        []
    )

    event = str(
        alert.get("category")
        or alert.get("event")
        or ""
    )

    area = str(
        alert.get("area")
        or ""
    )

    type_match = any(
        keyword in event
        for keyword in alert_types
    )

    area_match = any(
        wanted_area in area
        for wanted_area in areas
    )

    print(
        f"FILTER FINAL: "
        f"{alert.get('id')} | "
        f"type={event!r} | "
        f"area={area!r} | "
        f"type_match={type_match} | "
        f"area_match={area_match}"
    )

    return (
        type_match
        and area_match
    )

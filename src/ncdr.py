import json
import xml.etree.ElementTree as ET

import requests


NCDR_ALERT_LIST_URL = (
    "https://alerts.ncdr.nat.gov.tw/RssAtomFeed.ashx"
)

ATOM_NS = "http://www.w3.org/2005/Atom"
CAP_NS = "urn:oasis:names:tc:emergency:cap:1.1"


def load_config() -> dict:

    with open(
        "config/config.json",
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def get_alerts() -> list[dict]:

    response = requests.get(
        NCDR_ALERT_LIST_URL,
        headers={
            "Accept": (
                "application/atom+xml, "
                "application/xml, "
                "text/xml"
            )
        },
        timeout=30
    )

    response.raise_for_status()

    return normalize_alerts(
        response.text
    )


def _text(
    element,
    tag
) -> str:

    child = element.find(tag)

    if child is None:
        return ""

    return (
        child.text or ""
    ).strip()


def _cap_text(
    element,
    tag
) -> str:

    child = element.find(
        f"{{{CAP_NS}}}{tag}"
    )

    if child is None:
        return ""

    return (
        child.text or ""
    ).strip()


def normalize_alerts(
    data
) -> list[dict]:

    config = load_config()

    alert_types = config.get(
        "alert_types",
        []
    )

    areas = config.get(
        "areas",
        []
    )

    root = ET.fromstring(
        data
    )

    entries = root.findall(
        f"{{{ATOM_NS}}}entry"
    )

    print(
        f"NCDR Feed entries = {len(entries)}"
    )

    print(
        f"alert_types = {alert_types}"
    )

    print(
        f"areas = {areas}"
    )

    result = []

    for entry in entries:

        identifier = _text(
            entry,
            f"{{{ATOM_NS}}}id"
        )

        if not identifier:
            continue

        title = _text(
            entry,
            f"{{{ATOM_NS}}}title"
        )

        # ==========================================
        # category
        # ==========================================

        category_element = entry.find(
            f"{{{ATOM_NS}}}category"
        )

        category = ""

        if category_element is not None:

            category = (
                category_element.get("term")
                or ""
            ).strip()

        event = (
            category
            or title
        )

        # ==========================================
        # summary
        # ==========================================

        summary_element = entry.find(
            f"{{{ATOM_NS}}}summary"
        )

        description = ""

        if summary_element is not None:

            description = (
                summary_element.text
                or ""
            ).strip()

        # ==========================================
        # 第一層：災害類型
        # ==========================================

        type_match = any(
            keyword in event
            for keyword in alert_types
        )

        if not type_match:

            continue

        # ==========================================
        # 第二層：地區
        #
        # NCDR Atom summary 通常包含
        # 影響地區資訊。
        # ==========================================

        area_match = any(
            area in description
            for area in areas
        )

        if not area_match:

            continue

        # ==========================================
        # sender
        # ==========================================

        sender_element = entry.find(
            f"{{{ATOM_NS}}}author/"
            f"{{{ATOM_NS}}}name"
        )

        sender = ""

        if sender_element is not None:

            sender = (
                sender_element.text
                or ""
            ).strip()

        # ==========================================
        # CAP fields
        # ==========================================

        effective = _cap_text(
            entry,
            "effective"
        )

        expires = _cap_text(
            entry,
            "expires"
        )

        status = _cap_text(
            entry,
            "status"
        )

        msg_type = _cap_text(
            entry,
            "msgType"
        )

        # ==========================================
        # 建立結果
        # ==========================================

        result.append({

            "id": identifier,

            "event": event,

            "headline": title,

            "description": description,

            "instruction": "",

            "effective": effective,

            "expires": expires,

            "area": description,

            "category": category,

            "sender": sender,

            "status": status,

            "msgType": msg_type
        })

    print(
        f"NCDR 符合類型 + 地區 = "
        f"{len(result)} 筆"
    )

    return result

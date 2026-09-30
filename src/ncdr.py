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
    root,
    tag
) -> str:

    child = root.find(
        f".//{{{CAP_NS}}}{tag}"
    )

    if child is None:
        return ""

    return (
        child.text or ""
    ).strip()


def _get_category(
    entry
) -> str:

    category = entry.find(
        f"{{{ATOM_NS}}}category"
    )

    if category is None:
        return ""

    return (
        category.get("term")
        or ""
    ).strip()


def _get_cap_url(
    entry
) -> str:

    for link in entry.findall(
        f"{{{ATOM_NS}}}link"
    ):

        href = (
            link.get("href")
            or ""
        )

        if ".cap" in href.lower():

            return href

    return ""


def _get_cap_data(
    cap_url: str
) -> dict:

    if not cap_url:

        return {
            "area": "",
            "instruction": "",
            "effective": "",
            "expires": "",
            "status": "",
            "msgType": ""
        }

    try:

        response = requests.get(
            cap_url,
            timeout=8
        )

        response.raise_for_status()

        root = ET.fromstring(
            response.content
        )

        areas = []

        for area in root.findall(
            f".//{{{CAP_NS}}}area"
        ):

            area_desc = area.find(
                f"{{{CAP_NS}}}areaDesc"
            )

            if area_desc is None:
                continue

            value = (
                area_desc.text or ""
            ).strip()

            if value:
                areas.append(value)

        instruction = _cap_text(
            root,
            "instruction"
        )

        effective = _cap_text(
            root,
            "effective"
        )

        expires = _cap_text(
            root,
            "expires"
        )

        status = _cap_text(
            root,
            "status"
        )

        msg_type = _cap_text(
            root,
            "msgType"
        )

        return {
            "area": "、".join(
                dict.fromkeys(areas)
            ),
            "instruction": instruction,
            "effective": effective,
            "expires": expires,
            "status": status,
            "msgType": msg_type
        }

    except Exception as error:

        print(
            f"CAP ERROR: "
            f"{cap_url} | {error}"
        )

        return {
            "area": "",
            "instruction": "",
            "effective": "",
            "expires": "",
            "status": "",
            "msgType": ""
        }


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

    print(
        f"NCDR HTTP STATUS: "
        f"{response.status_code}"
    )

    print(
        f"NCDR CONTENT TYPE: "
        f"{response.headers.get('Content-Type')}"
    )

    response.raise_for_status()

    return normalize_alerts(
        response.content
    )


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
        f"NCDR Feed entries = "
        f"{len(entries)}"
    )

    print(
        f"alert_types = "
        f"{alert_types}"
    )

    print(
        f"areas = "
        f"{areas}"
    )

    type_matched = 0
    area_matched = 0

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

        category = _get_category(
            entry
        )

        event = (
            category
            or title
        )

        # ==========================================
        # 第一階段：alert_types
        # ==========================================

        type_match = any(
            keyword in event
            for keyword in alert_types
        )

        if not type_match:
            continue

        type_matched += 1

        print(
            f"TYPE MATCH: "
            f"{identifier} | {event}"
        )

        # ==========================================
        # summary
        # ==========================================

        summary = entry.find(
            f"{{{ATOM_NS}}}summary"
        )

        description = ""

        if summary is not None:

            description = (
                summary.text or ""
            ).strip()

        # ==========================================
        # 第二階段：取得 CAP
        # ==========================================

        cap_url = _get_cap_url(
            entry
        )

        cap = _get_cap_data(
            cap_url
        )

        area = cap["area"]

        # ==========================================
        # 第三階段：地區過濾
        # ==========================================

        area_match = any(
            wanted_area in area
            for wanted_area in areas
        )

        if not area_match:

            print(
                f"AREA SKIP: "
                f"{identifier} | "
                f"type={event} | "
                f"area={area!r}"
            )

            continue

        area_matched += 1

        print(
            f"AREA MATCH: "
            f"{identifier} | "
            f"type={event} | "
            f"area={area}"
        )

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
        # 建立統一格式
        # ==========================================

        result.append({

            "id": identifier,

            "event": event,

            "headline": title,

            "description": description,

            "instruction": cap[
                "instruction"
            ],

            "effective": (
                cap["effective"]
                or _cap_text(
                    entry,
                    "effective"
                )
            ),

            "expires": (
                cap["expires"]
                or _cap_text(
                    entry,
                    "expires"
                )
            ),

            "area": area,

            "category": category,

            "sender": sender,

            "status": cap[
                "status"
            ],

            "msgType": cap[
                "msgType"
            ],

            "cap_url": cap_url
        })

    print(
        "========== NCDR FILTER SUMMARY =========="
    )

    print(
        f"Feed entries   = {len(entries)}"
    )

    print(
        f"Type matched   = {type_matched}"
    )

    print(
        f"Area matched   = {area_matched}"
    )

    print(
        f"Final alerts   = {len(result)}"
    )

    print(
        "=========================================="
    )

    return result

import xml.etree.ElementTree as ET

import requests


NCDR_ALERT_LIST_URL = (
    "https://alerts.ncdr.nat.gov.tw/RssAtomFeed.ashx"
)


ATOM_NS = "http://www.w3.org/2005/Atom"
CAP_NS = "urn:oasis:names:tc:emergency:cap:1.1"


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


def _get_cap_url(
    entry
) -> str:

    for link in entry.findall(
        f"{{{ATOM_NS}}}link"
    ):

        href = link.get("href", "")

        if href.endswith(".cap"):
            return href

    return ""


def _get_cap_area(
    cap_url: str
) -> str:

    if not cap_url:
        return ""

    try:

        response = requests.get(
            cap_url,
            headers={
                "Accept": "application/xml, text/xml"
            },
            timeout=30
        )

        response.raise_for_status()

        root = ET.fromstring(
            response.text
        )

        areas = []

        for area in root.findall(
            f"{{{CAP_NS}}}info/"
            f"{{{CAP_NS}}}area"
        ):

            area_desc = area.find(
                f"{{{CAP_NS}}}areaDesc"
            )

            if area_desc is not None:

                value = (
                    area_desc.text or ""
                ).strip()

                if value:
                    areas.append(value)

        return "、".join(
            dict.fromkeys(areas)
        )

    except Exception as error:

        print(
            f"CAP AREA ERROR: {error}"
        )

        return ""


def normalize_alerts(
    data
) -> list[dict]:

    root = ET.fromstring(
        data
    )

    result = []

    for entry in root.findall(
        f"{{{ATOM_NS}}}entry"
    ):

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

        category = entry.find(
            f"{{{ATOM_NS}}}category"
        )

        category_term = ""

        if category is not None:

            category_term = (
                category.get("term")
                or ""
            ).strip()

        event = (
            category_term
            or title
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
        # sender
        # ==========================================

        sender_element = entry.find(
            f"{{{ATOM_NS}}}author/"
            f"{{{ATOM_NS}}}name"
        )

        sender = ""

        if sender_element is not None:

            sender = (
                sender_element.text or ""
            ).strip()

        # ==========================================
        # CAP URL
        # ==========================================

        cap_url = _get_cap_url(
            entry
        )

        # ==========================================
        # 從 CAP 取得影響地區
        # ==========================================

        area = _get_cap_area(
            cap_url
        )

        # ==========================================
        # 建立唯一 ID
        #
        # NCDR Feed 裡可能出現：
        #
        # TWC_water_202609301520
        #
        # 但 summary 不同。
        #
        # 因此把 cap_url 加進去避免互相覆蓋。
        # ==========================================

        unique_id = identifier

        if cap_url:
            unique_id = (
                f"{identifier}|{cap_url}"
            )

        result.append({

            "id": unique_id,

            "event": event,

            "headline": title,

            "description": description,

            "instruction": "",

            "effective": effective,

            "expires": expires,

            "area": area,

            "category": category_term,

            "sender": sender,

            "status": status,

            "msgType": msg_type,

            "cap_url": cap_url
        })

    return result

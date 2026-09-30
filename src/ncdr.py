import json
import xml.etree.ElementTree as ET

import requests


# ============================================================
# NCDR Atom Feed
# ============================================================

NCDR_ALERT_LIST_URL = (
    "https://alerts.ncdr.nat.gov.tw/RssAtomFeed.ashx"
)

ATOM_NS = "http://www.w3.org/2005/Atom"


# ============================================================
# Config
# ============================================================

def load_config() -> dict:

    with open(
        "config/config.json",
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# ============================================================
# XML helper
# ============================================================

def _element_text(element) -> str:

    if element is None:
        return ""

    return (
        "".join(
            element.itertext()
        )
        .strip()
    )


def _find_text(
    root,
    local_name: str
) -> str:
    """
    不管 XML namespace 是什麼，
    只按照 tag 最後的名稱搜尋。

    例如：

    <areaDesc>
    <cap:areaDesc>
    <ns0:areaDesc>

    都可以找到。
    """

    for element in root.iter():

        tag = element.tag

        if not isinstance(
            tag,
            str
        ):
            continue

        # {namespace}areaDesc
        if "}" in tag:

            name = tag.rsplit(
                "}",
                1
            )[1]

        else:

            name = tag

        if name == local_name:

            value = _element_text(
                element
            )

            if value:
                return value

    return ""


def _find_all_text(
    root,
    local_name: str
) -> list[str]:

    values = []

    for element in root.iter():

        tag = element.tag

        if not isinstance(
            tag,
            str
        ):
            continue

        if "}" in tag:

            name = tag.rsplit(
                "}",
                1
            )[1]

        else:

            name = tag

        if name != local_name:
            continue

        value = _element_text(
            element
        )

        if value:
            values.append(value)

    return values


# ============================================================
# Atom helpers
# ============================================================

def _atom_text(
    entry,
    tag: str
) -> str:

    element = entry.find(
        f"{{{ATOM_NS}}}{tag}"
    )

    return _element_text(
        element
    )


def _get_category(
    entry
) -> str:

    element = entry.find(
        f"{{{ATOM_NS}}}category"
    )

    if element is None:
        return ""

    return (
        element.get("term")
        or ""
    ).strip()


def _get_summary(
    entry
) -> str:

    element = entry.find(
        f"{{{ATOM_NS}}}summary"
    )

    return _element_text(
        element
    )


def _get_cap_url(
    entry
) -> str:

    for link in entry.findall(
        f"{{{ATOM_NS}}}link"
    ):

        href = (
            link.get("href")
            or ""
        ).strip()

        if not href:
            continue

        if ".cap" in href.lower():

            return href

    return ""


def _get_sender(
    entry
) -> str:

    author = entry.find(
        f"{{{ATOM_NS}}}author"
    )

    if author is None:
        return ""

    name = author.find(
        f"{{{ATOM_NS}}}name"
    )

    return _element_text(
        name
    )


# ============================================================
# CAP parser
# ============================================================

def _parse_cap(
    xml_data: bytes
) -> dict:
    """
    解析 NCDR CAP。

    不依賴固定 namespace，
    避免 NCDR CAP namespace 不一致造成
    areaDesc 找不到。
    """

    root = ET.fromstring(
        xml_data
    )

    # --------------------------------------------------------
    # Area
    # --------------------------------------------------------

    areas = _find_all_text(
        root,
        "areaDesc"
    )

    # 去除重複
    areas = list(
        dict.fromkeys(
            areas
        )
    )

    area = "、".join(
        areas
    )

    # --------------------------------------------------------
    # Other CAP fields
    # --------------------------------------------------------

    instruction = _find_text(
        root,
        "instruction"
    )

    effective = _find_text(
        root,
        "effective"
    )

    expires = _find_text(
        root,
        "expires"
    )

    status = _find_text(
        root,
        "status"
    )

    msg_type = _find_text(
        root,
        "msgType"
    )

    event = _find_text(
        root,
        "event"
    )

    headline = _find_text(
        root,
        "headline"
    )

    description = _find_text(
        root,
        "description"
    )

    return {

        "area": area,

        "instruction": instruction,

        "effective": effective,

        "expires": expires,

        "status": status,

        "msgType": msg_type,

        "event": event,

        "headline": headline,

        "description": description
    }


# ============================================================
# Download CAP
# ============================================================

def _get_cap_data(
    session: requests.Session,
    cap_url: str
) -> dict:

    empty = {
        "area": "",
        "instruction": "",
        "effective": "",
        "expires": "",
        "status": "",
        "msgType": "",
        "event": "",
        "headline": "",
        "description": ""
    }

    if not cap_url:

        print(
            "CAP URL EMPTY"
        )

        return empty

    try:

        response = session.get(
            cap_url,
            timeout=5
        )

        response.raise_for_status()

        return _parse_cap(
            response.content
        )

    except Exception as error:

        print(
            f"CAP ERROR: "
            f"{cap_url} | {error}"
        )

        return empty


# ============================================================
# Main API
# ============================================================

def get_alerts() -> list[dict]:

    config = load_config()

    print(
        "========== NCDR CONFIG =========="
    )

    print(
        f"areas = "
        f"{config.get('areas', [])}"
    )

    print(
        f"alert_types = "
        f"{config.get('alert_types', [])}"
    )

    print(
        "================================="
    )

    session = requests.Session()

    session.headers.update({
        "Accept": (
            "application/atom+xml, "
            "application/xml, "
            "text/xml"
        ),
        "User-Agent": (
            "NCDR-Telegram-Alert-Bot/1.0"
        )
    })

    try:

        response = session.get(
            NCDR_ALERT_LIST_URL,
            timeout=20
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

        alerts = normalize_alerts(
            response.content,
            config,
            session
        )

        return alerts

    finally:

        session.close()


# ============================================================
# Normalize
# ============================================================

def normalize_alerts(
    data: bytes,
    config: dict,
    session: requests.Session
) -> list[dict]:

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

    # ========================================================
    # Process entries
    # ========================================================

    for entry in entries:

        identifier = _atom_text(
            entry,
            "id"
        )

        if not identifier:
            continue

        title = _atom_text(
            entry,
            "title"
        )

        category = _get_category(
            entry
        )

        summary = _get_summary(
            entry
        )

        event = (
            category
            or title
        )

        # ====================================================
        # 1. alert_types
        # ====================================================

        type_match = any(
            keyword in event
            for keyword in alert_types
        )

        if not type_match:

            continue

        type_matched += 1

        print(
            f"TYPE MATCH: "
            f"{identifier} | "
            f"{event}"
        )

        # ====================================================
        # 2. CAP
        # ====================================================

        cap_url = _get_cap_url(
            entry
        )

        cap = _get_cap_data(
            session,
            cap_url
        )

        # ====================================================
        # 3. 地區
        #
        # 優先 CAP areaDesc
        # 如果 CAP 沒有，再用 Atom summary
        # ====================================================

        cap_area = (
            cap.get("area")
            or ""
        )

        area = cap_area

        area_match = any(
            wanted_area in cap_area
            for wanted_area in areas
        )

        # ----------------------------------------------------
        # CAP 沒找到 areaDesc
        # 嘗試 Atom summary
        # ----------------------------------------------------

        if not area_match:

            summary_area_match = any(
                wanted_area in summary
                for wanted_area in areas
            )

            if summary_area_match:

                area_match = True

                area = summary

                print(
                    f"AREA MATCH FROM SUMMARY: "
                    f"{identifier}"
                )

        # ====================================================
        # 4. 地區不符合
        # ====================================================

        if not area_match:

            print(
                f"AREA SKIP: "
                f"{identifier} | "
                f"type={event} | "
                f"cap_area={cap_area!r}"
            )

            continue

        area_matched += 1

        print(
            f"AREA MATCH: "
            f"{identifier} | "
            f"type={event} | "
            f"area={area}"
        )

        # ====================================================
        # 5. sender
        # ====================================================

        sender = _get_sender(
            entry
        )

        # ====================================================
        # 6. description
        #
        # CAP 有 description 就優先
        # 否則使用 Atom summary
        # ====================================================

        description = (
            cap.get("description")
            or summary
        )

        # ====================================================
        # 7. headline
        # ====================================================

        headline = (
            cap.get("headline")
            or title
            or event
        )

        # ====================================================
        # 8. effective / expires
        #
        # CAP 優先
        # Atom 如果沒有則補上
        # ====================================================

        effective = (
            cap.get("effective")
            or _atom_text(
                entry,
                "updated"
            )
        )

        expires = (
            cap.get("expires")
            or ""
        )

        # ====================================================
        # 9. 建立統一格式
        # ====================================================

        result.append({

            "id": identifier,

            "event": (
                cap.get("event")
                or event
            ),

            "headline": headline,

            "description": description,

            "instruction": (
                cap.get("instruction")
                or ""
            ),

            "effective": effective,

            "expires": expires,

            "area": area,

            "category": category,

            "sender": sender,

            "status": (
                cap.get("status")
                or ""
            ),

            "msgType": (
                cap.get("msgType")
                or ""
            ),

            "cap_url": cap_url
        })

    # ========================================================
    # Summary
    # ========================================================

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

import json
import xml.etree.ElementTree as ET

import requests


# ============================================================
# NCDR Atom Feed
# ============================================================

NCDR_ALERT_LIST_URL = (
    "https://alerts.ncdr.nat.gov.tw/RssAtomFeed.ashx"
)

ATOM_NS = (
    "http://www.w3.org/2005/Atom"
)


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
# XML helpers
# ============================================================

def _local_name(tag) -> str:

    if not isinstance(tag, str):
        return ""

    if "}" in tag:
        return tag.rsplit("}", 1)[1]

    if ":" in tag:
        return tag.rsplit(":", 1)[1]

    return tag


def _text(element) -> str:

    if element is None:
        return ""

    return "".join(
        element.itertext()
    ).strip()


def _find_text(
    root,
    name: str
) -> str:

    for element in root.iter():

        if _local_name(element.tag) != name:
            continue

        value = _text(element)

        if value:
            return value

    return ""


def _find_all(
    root,
    name: str
) -> list:

    result = []

    for element in root.iter():

        if _local_name(element.tag) == name:
            result.append(element)

    return result


# ============================================================
# Atom helpers
# ============================================================

def _atom_text(
    entry,
    name: str
) -> str:

    element = entry.find(
        f"{{{ATOM_NS}}}{name}"
    )

    return _text(element)


def _get_category(entry) -> str:

    element = entry.find(
        f"{{{ATOM_NS}}}category"
    )

    if element is None:
        return ""

    return (
        element.get("term")
        or ""
    ).strip()


def _get_summary(entry) -> str:

    element = entry.find(
        f"{{{ATOM_NS}}}summary"
    )

    return _text(element)


def _get_sender(entry) -> str:

    author = entry.find(
        f"{{{ATOM_NS}}}author"
    )

    if author is None:
        return ""

    name = author.find(
        f"{{{ATOM_NS}}}name"
    )

    return _text(name)


def _get_cap_url(entry) -> str:

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


# ============================================================
# Type matching
# ============================================================

def _type_matches(
    event: str,
    category: str,
    title: str,
    alert_types: list[str]
) -> bool:

    searchable = " ".join([
        event or "",
        category or "",
        title or ""
    ])

    return any(
        keyword in searchable
        for keyword in alert_types
    )


# ============================================================
# Area matching
# ============================================================

def _area_matches_text(
    text: str,
    areas: list[str]
) -> tuple[bool, str]:

    if not text:
        return False, ""

    for wanted_area in areas:

        if wanted_area in text:
            return True, wanted_area

    return False, ""


# ============================================================
# CAP area parser
# ============================================================

def _parse_cap_areas(root) -> list[dict]:
    """
    完整解析 CAP 裡面的 <area>。

    回傳：

    [
        {
            "areaDesc": "...",
            "geocodes": [
                {
                    "valueName": "...",
                    "value": "..."
                }
            ]
        }
    ]
    """

    result = []

    for area_element in _find_all(
        root,
        "area"
    ):

        area_desc = ""

        geocodes = []

        for child in list(
            area_element
        ):

            name = _local_name(
                child.tag
            )

            if name == "areaDesc":

                area_desc = _text(
                    child
                )

            elif name == "geocode":

                value_name = ""
                value = ""

                for geo_child in list(
                    child
                ):

                    geo_name = _local_name(
                        geo_child.tag
                    )

                    if geo_name == "valueName":

                        value_name = _text(
                            geo_child
                        )

                    elif geo_name == "value":

                        value = _text(
                            geo_child
                        )

                geocodes.append({
                    "valueName":
                        value_name,

                    "value":
                        value
                })

        result.append({

            "areaDesc":
                area_desc,

            "geocodes":
                geocodes
        })

    return result


# ============================================================
# 地震地區判斷
# ============================================================

def _match_earthquake_area(
    cap_areas: list[dict],
    wanted_areas: list[str]
) -> tuple[bool, str]:
    """
    判斷地震 CAP 是否包含指定縣市。

    第一優先：
        areaDesc

    第二優先：
        geocode value

    這裡故意不硬編 geocode 對應縣市，
    因為必須以實際 NCDR CAP 格式為準。
    """

    # --------------------------------------------------------
    # 第一層：areaDesc
    # --------------------------------------------------------

    for area in cap_areas:

        area_desc = (
            area.get("areaDesc")
            or ""
        )

        for wanted_area in wanted_areas:

            if wanted_area in area_desc:

                return True, wanted_area

    # --------------------------------------------------------
    # 第二層：geocode
    #
    # 目前先不猜代碼代表哪個縣市。
    # 把實際 geocode 留給 debug。
    # --------------------------------------------------------

    return False, ""


# ============================================================
# CAP parser
# ============================================================

def _parse_cap(
    xml_data: bytes
) -> dict:

    root = ET.fromstring(
        xml_data
    )

    cap_areas = _parse_cap_areas(
        root
    )

    area_descs = [
        item["areaDesc"]
        for item in cap_areas
        if item.get("areaDesc")
    ]

    area_descs = list(
        dict.fromkeys(
            area_descs
        )
    )

    return {

        "root":
            root,

        "cap_areas":
            cap_areas,

        "area_descs":
            area_descs,

        "area":
            "、".join(
                area_descs
            ),

        "instruction":
            _find_text(
                root,
                "instruction"
            ),

        "effective":
            _find_text(
                root,
                "effective"
            ),

        "expires":
            _find_text(
                root,
                "expires"
            ),

        "status":
            _find_text(
                root,
                "status"
            ),

        "msgType":
            _find_text(
                root,
                "msgType"
            ),

        "event":
            _find_text(
                root,
                "event"
            ),

        "headline":
            _find_text(
                root,
                "headline"
            ),

        "description":
            _find_text(
                root,
                "description"
            )
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

        "area_descs": [],

        "cap_areas": [],

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

        "Accept":
            "application/atom+xml, "
            "application/xml, "
            "text/xml",

        "User-Agent":
            "NCDR-Telegram-Alert-Bot/1.0"
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

        return normalize_alerts(
            response.content,
            config,
            session
        )

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
    # Feed entries
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

        sender = _get_sender(
            entry
        )

        cap_url = _get_cap_url(
            entry
        )

        event = (
            category
            or title
            or ""
        )

        # ====================================================
        # alert_types
        # ====================================================

        if not _type_matches(
            event,
            category,
            title,
            alert_types
        ):

            continue

        type_matched += 1

        print(
            f"TYPE MATCH: "
            f"{identifier} | "
            f"{event}"
        )

        # ====================================================
        # 是否地震
        # ====================================================

        is_earthquake = (
            "地震" in event
            or "地震" in category
            or "地震" in title
        )

        # ====================================================
        # CAP
        # ====================================================

        cap = _get_cap_data(
            session,
            cap_url
        )

        cap_area = (
            cap.get("area")
            or ""
        )

        cap_areas = (
            cap.get(
                "cap_areas",
                []
            )
        )

        # ====================================================
        # DEBUG：地震完整 CAP area
        # ====================================================

        if is_earthquake:

            print(
                "========== "
                "EARTHQUAKE CAP AREAS "
                "=========="
            )

            for index, area_data in enumerate(
                cap_areas,
                start=1
            ):

                print(
                    f"[{index}] "
                    f"areaDesc="
                    f"{area_data.get('areaDesc', '')!r}"
                )

                print(
                    f"    geocodes="
                    f"{area_data.get('geocodes', [])}"
                )

            print(
                "======================================"
            )

        # ====================================================
        # Area matching
        # ====================================================

        area_match = False
        matched_area = ""

        # ----------------------------------------------------
        # 地震
        # ----------------------------------------------------

        if is_earthquake:

            (
                area_match,
                matched_area
            ) = _match_earthquake_area(
                cap_areas,
                areas
            )

            # 再退回整個 CAP area
            if not area_match:

                (
                    area_match,
                    matched_area
                ) = _area_matches_text(
                    cap_area,
                    areas
                )

            if not area_match:

                print(
                    f"EARTHQUAKE AREA SKIP: "
                    f"{identifier} | "
                    f"area="
                    f"{cap_area!r}"
                )

        # ----------------------------------------------------
        # 非地震
        # ----------------------------------------------------

        else:

            (
                area_match,
                matched_area
            ) = _area_matches_text(
                cap_area,
                areas
            )

            if not area_match:

                (
                    area_match,
                    matched_area
                ) = _area_matches_text(
                    summary,
                    areas
                )

        # ====================================================
        # Area skip
        # ====================================================

        if not area_match:

            print(
                f"AREA SKIP: "
                f"{identifier} | "
                f"type={event} | "
                f"cap_area="
                f"{cap_area!r}"
            )

            continue

        area_matched += 1

        print(
            f"AREA MATCH: "
            f"{identifier} | "
            f"type={event} | "
            f"matched_area="
            f"{matched_area}"
        )

        # ====================================================
        # Fields
        # ====================================================

        description = (
            cap.get(
                "description"
            )
            or summary
        )

        headline = (
            cap.get(
                "headline"
            )
            or title
            or event
        )

        effective = (
            cap.get(
                "effective"
            )
            or _atom_text(
                entry,
                "updated"
            )
        )

        expires = (
            cap.get(
                "expires"
            )
            or ""
        )

        # ====================================================
        # Final object
        # ====================================================

        result.append({

            "id":
                identifier,

            "event":
                cap.get(
                    "event"
                )
                or event,

            "headline":
                headline,

            "description":
                description,

            "instruction":
                cap.get(
                    "instruction"
                )
                or "",

            "effective":
                effective,

            "expires":
                expires,

            "area":
                cap_area
                or matched_area,

            "category":
                category,

            "sender":
                sender,

            "status":
                cap.get(
                    "status"
                )
                or "",

            "msgType":
                cap.get(
                    "msgType"
                )
                or "",

            "cap_url":
                cap_url,

            "matched_area":
                matched_area,

            "cap_areas":
                cap_areas
        })

    # ========================================================
    # Summary
    # ========================================================

    print(
        "========== NCDR FILTER SUMMARY =========="
    )

    print(
        f"Feed entries   = "
        f"{len(entries)}"
    )

    print(
        f"Type matched   = "
        f"{type_matched}"
    )

    print(
        f"Area matched   = "
        f"{area_matched}"
    )

    print(
        f"Final alerts   = "
        f"{len(result)}"
    )

    print(
        "=========================================="
    )

    return result


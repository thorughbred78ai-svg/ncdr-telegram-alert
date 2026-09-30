import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Any

import requests


# ============================================================
# NCDR Atom Feed
# ============================================================

NCDR_ALERT_LIST_URL = (
    "https://alerts.ncdr.nat.gov.tw/RssAtomFeed.ashx"
)

ATOM_NS = "http://www.w3.org/2005/Atom"

# 臺灣時區 UTC+8
TAIWAN_TZ = timezone(
    timedelta(hours=8)
)


# ============================================================
# NCDR Taiwan_Geocode_113
#
# 來源：
#   city_113.kml
#
# 重要：
#   本程式完全使用 Taiwan_Geocode_113。
#
#   不使用：
#       Taiwan_Geocode_103
#
#   113 縣市代碼：
#
#       65000 -> 新北市
#       68000 -> 桃園市
#
#   鄉鎮市區等下層代碼：
#
#       650xxxx
#           -> 65000
#           -> 新北市
#
#       680xxxx
#           -> 68000
#           -> 桃園市
#
# ============================================================

NCDR_GEOCODE_113_CITY_MAP = {

    # --------------------------------------------------------
    # 直轄市
    # --------------------------------------------------------

    "63000": "臺北市",
    "64000": "高雄市",
    "65000": "新北市",
    "66000": "臺中市",
    "67000": "臺南市",
    "68000": "桃園市",

    # --------------------------------------------------------
    # 縣
    # --------------------------------------------------------

    "09007": "連江縣",
    "09020": "金門縣",

    "10002": "宜蘭縣",
    "10004": "新竹縣",
    "10005": "苗栗縣",
    "10007": "彰化縣",
    "10008": "南投縣",
    "10009": "雲林縣",
    "10010": "嘉義縣",
    "10013": "屏東縣",
    "10014": "臺東縣",
    "10015": "花蓮縣",
    "10016": "澎湖縣",

    # --------------------------------------------------------
    # 縣轄市
    # --------------------------------------------------------

    "10017": "基隆市",
    "10018": "新竹市",
    "10020": "嘉義市",
}


# ============================================================
# AREA aliases
#
# config.json 可以寫：
#
#   桃園市
#   桃園
#   新北市
#   新北
#
# 最終會統一成正式名稱。
# ============================================================

AREA_NAME_ALIASES = {

    "台北市": "臺北市",
    "台中市": "臺中市",
    "台南市": "臺南市",
    "台東縣": "臺東縣",

    "台北": "臺北市",
    "臺北": "臺北市",

    "台中": "臺中市",
    "臺中": "臺中市",

    "台南": "臺南市",
    "臺南": "臺南市",

    "台東": "臺東縣",
    "臺東": "臺東縣",

    "高雄": "高雄市",
    "基隆": "基隆市",

    "新竹": "新竹市",
    "苗栗": "苗栗縣",
    "彰化": "彰化縣",
    "南投": "南投縣",
    "雲林": "雲林縣",

    "嘉義": "嘉義市",
    "屏東": "屏東縣",
    "宜蘭": "宜蘭縣",
    "花蓮": "花蓮縣",
    "澎湖": "澎湖縣",
    "金門": "金門縣",
    "連江": "連江縣",

    "桃園": "桃園市",
    "新北": "新北市",
}


# ============================================================
# Config
# ============================================================

def load_config() -> dict:

    with open(
        "config/config.json",
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(f)


# ============================================================
# XML helpers
# ============================================================

def _local_name(
    tag: Any,
) -> str:

    if not isinstance(
        tag,
        str,
    ):
        return ""

    if "}" in tag:

        return tag.rsplit(
            "}",
            1,
        )[1]

    if ":" in tag:

        return tag.rsplit(
            ":",
            1,
        )[1]

    return tag


def _text(
    element: ET.Element | None,
) -> str:

    if element is None:
        return ""

    return "".join(
        element.itertext()
    ).strip()


def _find_text(
    root: ET.Element,
    name: str,
) -> str:

    for element in root.iter():

        if (
            _local_name(
                element.tag
            )
            != name
        ):
            continue

        value = _text(
            element
        )

        if value:
            return value

    return ""


def _find_all(
    root: ET.Element,
    name: str,
) -> list[ET.Element]:

    result = []

    for element in root.iter():

        if (
            _local_name(
                element.tag
            )
            == name
        ):

            result.append(
                element
            )

    return result


# ============================================================
# Atom helpers
# ============================================================

def _atom_text(
    entry: ET.Element,
    name: str,
) -> str:

    element = entry.find(
        f"{{{ATOM_NS}}}{name}"
    )

    return _text(
        element
    )


def _get_category(
    entry: ET.Element,
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
    entry: ET.Element,
) -> str:

    element = entry.find(
        f"{{{ATOM_NS}}}summary"
    )

    return _text(
        element
    )


def _get_sender(
    entry: ET.Element,
) -> str:

    author = entry.find(
        f"{{{ATOM_NS}}}author"
    )

    if author is None:
        return ""

    name = author.find(
        f"{{{ATOM_NS}}}name"
    )

    return _text(
        name
    )


def _get_cap_url(
    entry: ET.Element,
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


# ============================================================
# Type matching
# ============================================================

def _type_matches(
    event: str,
    category: str,
    title: str,
    alert_types: list[str],
) -> bool:

    searchable = " ".join([
        event or "",
        category or "",
        title or "",
    ])

    return any(
        keyword in searchable
        for keyword in alert_types
    )


# ============================================================
# Area normalization
# ============================================================

def _normalize_area_name(
    value: str,
) -> str:

    value = (
        value
        or ""
    ).strip()

    if not value:
        return ""

    return (
        AREA_NAME_ALIASES.get(
            value,
            value,
        )
    )


def _normalize_wanted_areas(
    areas: list[str],
) -> list[str]:

    result = []

    for area in areas:

        normalized = (
            _normalize_area_name(
                str(area)
            )
        )

        if not normalized:
            continue

        if normalized not in result:

            result.append(
                normalized
            )

    return result


# ============================================================
# Taiwan_Geocode_113
# ============================================================

def _normalize_geocode(
    value: str,
) -> str:
    """
    清理 NCDR Taiwan_Geocode_113。

    例如：

        " 65000 "
            -> "65000"

        "6502400"
            -> "6502400"
    """

    value = (
        value
        or ""
    ).strip()

    if not value:
        return ""

    value = re.sub(
        r"\s+",
        "",
        value,
    )

    return value


def _city_from_geocode_113(
    geocode: str,
) -> str:
    """
    使用 Taiwan_Geocode_113
    將行政區代碼轉成縣市。

    113 的縣市層級使用：

        65000 -> 新北市
        68000 -> 桃園市

    如果 CAP 提供的是下層行政區代碼：

        650xxxx
        680xxxx

    則取前五碼：

        650xx
        680xx

    再與 city_113.kml 的 COUNTYCODE 對應。

    注意：
        本函式完全不使用 103 的 65 / 68 邏輯。
    """

    code = _normalize_geocode(
        geocode
    )

    if not code:
        return ""

    # --------------------------------------------------------
    # 1. 完整縣市代碼
    # --------------------------------------------------------

    if code in NCDR_GEOCODE_113_CITY_MAP:

        return (
            NCDR_GEOCODE_113_CITY_MAP[
                code
            ]
        )

    # --------------------------------------------------------
    # 2. 下層行政區代碼
    #
    # 例如：
    #
    #   6500100
    #   6502400
    #   6800100
    #
    # 前五碼：
    #
    #   65000
    #   65000
    #   68000
    # --------------------------------------------------------

    if len(code) >= 5:

        city_code = code[:5]

        if (
            city_code
            in NCDR_GEOCODE_113_CITY_MAP
        ):

            return (
                NCDR_GEOCODE_113_CITY_MAP[
                    city_code
                ]
            )

    return ""


def _geocode_matches_areas(
    geocode: str,
    wanted_areas: list[str],
) -> str:

    city = _city_from_geocode_113(
        geocode
    )

    if not city:
        return ""

    normalized_wanted = (
        _normalize_wanted_areas(
            wanted_areas
        )
    )

    if city in normalized_wanted:

        return city

    return ""


# ============================================================
# Geocode parser
# ============================================================

def _get_geocodes(
    root: ET.Element,
) -> list[dict]:

    result = []

    for geocode in _find_all(
        root,
        "geocode",
    ):

        value_name = ""
        value = ""

        for child in list(
            geocode
        ):

            name = _local_name(
                child.tag
            )

            if name == "valueName":

                value_name = _text(
                    child
                )

            elif name == "value":

                value = _text(
                    child
                )

        if (
            value_name
            or value
        ):

            result.append({
                "valueName":
                    value_name,

                "value":
                    value,
            })

    return result


# ============================================================
# CAP area block parser
# ============================================================

def _get_area_blocks(
    root: ET.Element,
) -> list[dict]:
    """
    將 CAP 中每個 area 分開。

    只保留：
        areaDesc
        geocodes

    區域判斷只使用：

        Taiwan_Geocode_113
    """

    result = []

    for area_element in _find_all(
        root,
        "area",
    ):

        area_desc = ""

        geocodes = []

        for child in list(
            area_element
        ):

            child_name = (
                _local_name(
                    child.tag
                )
            )

            # ------------------------------------------------
            # areaDesc
            #
            # 僅供顯示。
            # 絕對不作區域匹配。
            # ------------------------------------------------

            if child_name == "areaDesc":

                value = _text(
                    child
                )

                if value:

                    area_desc = value

            # ------------------------------------------------
            # geocode
            # ------------------------------------------------

            elif child_name == "geocode":

                value_name = ""
                value = ""

                for geo_child in list(
                    child
                ):

                    geo_name = (
                        _local_name(
                            geo_child.tag
                        )
                    )

                    if geo_name == "valueName":

                        value_name = _text(
                            geo_child
                        )

                    elif geo_name == "value":

                        value = _text(
                            geo_child
                        )

                if (
                    value_name
                    or value
                ):

                    geocodes.append({
                        "valueName":
                            value_name,

                        "value":
                            value,
                    })

        result.append({
            "areaDesc":
                area_desc,

            "geocodes":
                geocodes,
        })

    return result


# ============================================================
# Taiwan_Geocode_113 matching
# ============================================================

def _match_area_blocks_by_geocode(
    area_blocks: list[dict],
    wanted_areas: list[str],
) -> tuple[str, list[dict]]:
    """
    核心區域過濾。

    唯一合法區域來源：

        Taiwan_Geocode_113

    不使用：

        areaDesc
        summary
        title
        description
        headline
        instruction
        CAP 全文
    """

    normalized_wanted = (
        _normalize_wanted_areas(
            wanted_areas
        )
    )

    if not normalized_wanted:

        return (
            "",
            [],
        )

    matched_area = ""

    matched_blocks = []

    for block in area_blocks:

        area_desc = (
            block.get(
                "areaDesc"
            )
            or ""
        )

        geocodes = (
            block.get(
                "geocodes"
            )
            or []
        )

        block_matched = ""

        for geo in geocodes:

            value_name = (
                geo.get(
                    "valueName"
                )
                or ""
            ).strip()

            value = (
                geo.get(
                    "value"
                )
                or ""
            ).strip()

            # ------------------------------------------------
            # 只接受 Taiwan_Geocode_113
            # ------------------------------------------------

            if (
                value_name
                != "Taiwan_Geocode_113"
            ):

                continue

            city = _city_from_geocode_113(
                value
            )

            if not city:
                continue

            if city in normalized_wanted:

                block_matched = city

                if not matched_area:

                    matched_area = city

                break

        if block_matched:

            matched_blocks.append({
                "areaDesc":
                    area_desc,

                "geocodes":
                    geocodes,

                "matched_area":
                    block_matched,
            })

    return (
        matched_area,
        matched_blocks,
    )


# ============================================================
# Earthquake parser
# ============================================================

def _parse_earthquake_areas(
    root: ET.Element,
    wanted_areas: list[str],
) -> dict:
    """
    地震 CAP 使用 Taiwan_Geocode_113。

    areaDesc：

        最大震度2級地區

    只作顯示 / 震度資訊。

    不用 areaDesc 判斷縣市。
    """

    area_blocks = _get_area_blocks(
        root
    )

    earthquake_areas = []

    earthquake_geocodes = []

    details = []

    # --------------------------------------------------------
    # Taiwan_Geocode_113 精準匹配
    # --------------------------------------------------------

    (
        matched_area,
        matched_blocks,
    ) = _match_area_blocks_by_geocode(
        area_blocks,
        wanted_areas,
    )

    # --------------------------------------------------------
    # 保存 area
    # --------------------------------------------------------

    for block in area_blocks:

        area_desc = (
            block.get(
                "areaDesc"
            )
            or ""
        )

        geocodes = (
            block.get(
                "geocodes"
            )
            or []
        )

        if area_desc:

            earthquake_areas.append(
                area_desc
            )

        for geo in geocodes:

            value_name = (
                geo.get(
                    "valueName"
                )
                or ""
            )

            value = (
                geo.get(
                    "value"
                )
                or ""
            )

            if (
                value_name
                or value
            ):

                earthquake_geocodes.append({
                    "valueName":
                        value_name,

                    "value":
                        value,
                })

        details.append({
            "areaDesc":
                area_desc,

            "geocodes":
                geocodes,
        })

    # --------------------------------------------------------
    # 震度
    # --------------------------------------------------------

    intensity_map = {}

    for block in area_blocks:

        area_desc = (
            block.get(
                "areaDesc"
            )
            or ""
        )

        match = re.search(
            r"最大震度\s*([0-9]+)級",
            area_desc,
        )

        if not match:
            continue

        intensity = int(
            match.group(1)
        )

        intensity_map.setdefault(
            intensity,
            [],
        )

        for geo in (
            block.get(
                "geocodes"
            )
            or []
        ):

            intensity_map[
                intensity
            ].append(
                geo
            )

    return {

        "matched_area":
            matched_area,

        "matched_blocks":
            matched_blocks,

        "earthquake_areas":
            list(
                dict.fromkeys(
                    earthquake_areas
                )
            ),

        "earthquake_geocodes":
            earthquake_geocodes,

        "earthquake_area_details":
            details,

        "earthquake_intensity":
            intensity_map,
    }


# ============================================================
# General CAP area parser
# ============================================================

def _parse_general_area(
    root: ET.Element,
    wanted_areas: list[str],
) -> tuple[
    str,
    list[str],
    list[dict],
]:
    """
    非地震 CAP 同樣只使用
    Taiwan_Geocode_113 判斷區域。

    areaDesc 僅供顯示。
    """

    area_blocks = _get_area_blocks(
        root
    )

    area_descs = []

    for block in area_blocks:

        value = (
            block.get(
                "areaDesc"
            )
            or ""
        )

        if value:

            area_descs.append(
                value
            )

    area_descs = list(
        dict.fromkeys(
            area_descs
        )
    )

    (
        matched_area,
        matched_blocks,
    ) = _match_area_blocks_by_geocode(
        area_blocks,
        wanted_areas,
    )

    return (
        matched_area,
        area_descs,
        matched_blocks,
    )


# ============================================================
# CAP parser
# ============================================================

def _parse_cap(
    xml_data: bytes,
    wanted_areas: list[str],
    is_earthquake: bool,
    summary: str,
) -> dict:

    root = ET.fromstring(
        xml_data
    )

    area_descs = []

    for element in _find_all(
        root,
        "areaDesc",
    ):

        value = _text(
            element
        )

        if value:

            area_descs.append(
                value
            )

    area_descs = list(
        dict.fromkeys(
            area_descs
        )
    )

    area = "、".join(
        area_descs
    )

    earthquake_data = {

        "matched_area":
            "",

        "matched_blocks":
            [],

        "earthquake_areas":
            [],

        "earthquake_geocodes":
            [],

        "earthquake_area_details":
            [],

        "earthquake_intensity":
            {},
    }

    matched_blocks = []

    # ========================================================
    # 地震
    # ========================================================

    if is_earthquake:

        earthquake_data = (
            _parse_earthquake_areas(
                root,
                wanted_areas,
            )
        )

        matched_area = (
            earthquake_data[
                "matched_area"
            ]
        )

        matched_blocks = (
            earthquake_data[
                "matched_blocks"
            ]
        )

    # ========================================================
    # 非地震
    # ========================================================

    else:

        (
            matched_area,
            _,
            matched_blocks,
        ) = _parse_general_area(
            root,
            wanted_areas,
        )

    # ========================================================
    # Return
    # ========================================================

    return {

        "root":
            root,

        "area":
            area,

        "area_descs":
            area_descs,

        "matched_area":
            matched_area,

        "matched_blocks":
            matched_blocks,

        "earthquake_areas":
            earthquake_data[
                "earthquake_areas"
            ],

        "earthquake_geocodes":
            earthquake_data[
                "earthquake_geocodes"
            ],

        "earthquake_area_details":
            earthquake_data[
                "earthquake_area_details"
            ],

        "earthquake_intensity":
            earthquake_data[
                "earthquake_intensity"
            ],

        "instruction":
            _find_text(
                root,
                "instruction",
            ),

        "effective":
            _find_text(
                root,
                "effective",
            ),

        "expires":
            _find_text(
                root,
                "expires",
            ),

        "status":
            _find_text(
                root,
                "status",
            ),

        "msgType":
            _find_text(
                root,
                "msgType",
            ),

        "event":
            _find_text(
                root,
                "event",
            ),

        "headline":
            _find_text(
                root,
                "headline",
            ),

        "description":
            _find_text(
                root,
                "description",
            ),

        "geocodes":
            _get_geocodes(
                root
            ),
    }


# ============================================================
# Empty CAP
# ============================================================

def _empty_cap() -> dict:

    return {

        "area":
            "",

        "area_descs":
            [],

        "matched_area":
            "",

        "matched_blocks":
            [],

        "earthquake_areas":
            [],

        "earthquake_geocodes":
            [],

        "earthquake_area_details":
            [],

        "earthquake_intensity":
            {},

        "geocodes":
            [],

        "instruction":
            "",

        "effective":
            "",

        "expires":
            "",

        "status":
            "",

        "msgType":
            "",

        "event":
            "",

        "headline":
            "",

        "description":
            "",
    }


# ============================================================
# CAP download
# ============================================================

def _get_cap_data(
    session: requests.Session,
    cap_url: str,
    wanted_areas: list[str],
    is_earthquake: bool,
    summary: str,
) -> dict:

    empty = _empty_cap()

    if not cap_url:

        print(
            "CAP URL EMPTY"
        )

        return empty

    try:

        response = session.get(
            cap_url,
            timeout=5,
        )

        response.raise_for_status()

        return _parse_cap(
            response.content,
            wanted_areas,
            is_earthquake,
            summary,
        )

    except requests.RequestException as error:

        print(
            f"CAP HTTP ERROR: "
            f"{cap_url} | {error}"
        )

        return empty

    except ET.ParseError as error:

        print(
            f"CAP XML ERROR: "
            f"{cap_url} | {error}"
        )

        return empty

    except Exception as error:

        print(
            f"CAP ERROR: "
            f"{cap_url} | {error}"
        )

        return empty


# ============================================================
# Date helpers
# ============================================================

def _normalize_datetime(
    value: str,
) -> str:
    """
    將 NCDR 時間轉成 ISO 8601。
    """

    value = (
        value
        or ""
    ).strip()

    if not value:
        return ""

    # --------------------------------------------------------
    # ISO 8601
    # --------------------------------------------------------

    try:

        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        return parsed.isoformat()

    except ValueError:
        pass

    # --------------------------------------------------------
    # NCDR 中文時間
    # --------------------------------------------------------

    patterns = [

        "%Y/%m/%d 下午 %I:%M:%S",

        "%Y/%m/%d 上午 %I:%M:%S",

        "%Y/%m/%d 下午 %I:%M",

        "%Y/%m/%d 上午 %I:%M",
    ]

    for pattern in patterns:

        try:

            parsed = datetime.strptime(
                value,
                pattern,
            )

            parsed = parsed.replace(
                tzinfo=TAIWAN_TZ
            )

            return parsed.isoformat()

        except ValueError:

            continue

    return value


# ============================================================
# Main
# ============================================================

def get_alerts() -> list[dict]:

    config = load_config()

    alert_types = config.get(
        "alert_types",
        [],
    )

    areas = config.get(
        "areas",
        [],
    )

    normalized_areas = (
        _normalize_wanted_areas(
            areas
        )
    )

    print(
        "========== NCDR CONFIG =========="
    )

    print(
        f"areas = {areas}"
    )

    print(
        f"normalized areas = "
        f"{normalized_areas}"
    )

    print(
        f"alert_types = "
        f"{alert_types}"
    )

    print(
        "AREA FILTER MODE = "
        "NCDR GEOCODE 113"
    )

    print(
        "AREA SOURCE = "
        "Taiwan_Geocode_113"
    )

    print(
        "TEXT AREA FALLBACK = DISABLED"
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
            "NCDR-Telegram-Alert-Bot/1.0",
    })

    try:

        response = session.get(
            NCDR_ALERT_LIST_URL,
            timeout=20,
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
            session,
        )

    finally:

        session.close()


# ============================================================
# Normalize alerts
# ============================================================

def normalize_alerts(
    data: bytes,
    config: dict,
    session: requests.Session,
) -> list[dict]:

    alert_types = config.get(
        "alert_types",
        [],
    )

    areas = config.get(
        "areas",
        [],
    )

    normalized_areas = (
        _normalize_wanted_areas(
            areas
        )
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
        f"{normalized_areas}"
    )

    type_matched = 0
    area_matched = 0
    cap_errors = 0

    result = []

    # ========================================================
    # Atom entries
    # ========================================================

    for entry in entries:

        identifier = _atom_text(
            entry,
            "id",
        )

        if not identifier:
            continue

        title = _atom_text(
            entry,
            "title",
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

        published_at = _atom_text(
            entry,
            "updated",
        )

        event = (
            category
            or title
            or ""
        )

        # ====================================================
        # 1. 類型
        # ====================================================

        if not _type_matches(
            event,
            category,
            title,
            alert_types,
        ):

            continue

        type_matched += 1

        print(
            f"TYPE MATCH: "
            f"{identifier} | "
            f"{event}"
        )

        # ====================================================
        # 2. 地震判斷
        # ====================================================

        is_earthquake = (
            "地震" in event
            or "地震" in category
            or "地震" in title
        )

        # ====================================================
        # 3. CAP
        # ====================================================

        cap = _get_cap_data(
            session,
            cap_url,
            normalized_areas,
            is_earthquake,
            summary,
        )

        if not cap.get(
            "area_descs"
        ):

            cap_errors += 1

        cap_area = (
            cap.get(
                "area"
            )
            or ""
        )

        matched_area = (
            cap.get(
                "matched_area"
            )
            or ""
        )

        area_descs = (
            cap.get(
                "area_descs"
            )
            or []
        )

        matched_blocks = (
            cap.get(
                "matched_blocks"
            )
            or []
        )

        # ====================================================
        # 4. Taiwan_Geocode_113 區域判斷
        #
        # 唯一合法來源：
        #
        #   Taiwan_Geocode_113
        #
        # 完全不使用：
        #
        #   areaDesc
        #   summary
        #   title
        #   description
        #   headline
        #   instruction
        #   CAP 全文
        # ====================================================

        if not matched_area:

            print(
                f"AREA SKIP: "
                f"{identifier} | "
                f"type={event} | "
                f"earthquake={is_earthquake} | "
                f"wanted={normalized_areas} | "
                f"area_descs={area_descs!r}"
            )

            continue

        area_matched += 1

        print(
            f"AREA MATCH: "
            f"{identifier} | "
            f"type={event} | "
            f"matched_area={matched_area}"
        )

        # ====================================================
        # 5. 印出實際命中的 113 geocode
        # ====================================================

        for block in matched_blocks:

            print(
                f"  GEOCODE 113 MATCH: "
                f"areaDesc="
                f"{block.get('areaDesc', '')!r}"
            )

            for geo in (
                block.get(
                    "geocodes"
                )
                or []
            ):

                if (
                    geo.get(
                        "valueName"
                    )
                    != "Taiwan_Geocode_113"
                ):

                    continue

                print(
                    f"    "
                    f"{geo.get('valueName', '')}"
                    f" = "
                    f"{geo.get('value', '')}"
                    f" -> "
                    f"{_city_from_geocode_113("
                    f"geo.get('value', '')"
                    f")}"
                )

        # ====================================================
        # 6. Description
        # ====================================================

        description = (
            cap.get(
                "description"
            )
            or summary
            or ""
        )

        # ====================================================
        # 7. Headline
        # ====================================================

        headline = (
            cap.get(
                "headline"
            )
            or title
            or event
        )

        # ====================================================
        # 8. Effective
        # ====================================================

        effective = (
            cap.get(
                "effective"
            )
            or published_at
            or ""
        )

        # ====================================================
        # 9. Expires
        # ====================================================

        expires = (
            cap.get(
                "expires"
            )
            or ""
        )

        # ====================================================
        # 10. 時間標準化
        # ====================================================

        effective_normalized = (
            _normalize_datetime(
                effective
            )
        )

        published_normalized = (
            _normalize_datetime(
                published_at
            )
        )

        expires_normalized = (
            _normalize_datetime(
                expires
            )
        )

        # ====================================================
        # 11. matched geocodes
        # ====================================================

        matched_geocodes = []

        for block in matched_blocks:

            for geo in (
                block.get(
                    "geocodes"
                )
                or []
            ):

                if (
                    geo.get(
                        "valueName"
                    )
                    == "Taiwan_Geocode_113"
                ):

                    matched_geocodes.append(
                        geo
                    )

        # 去除重複 geocode

        unique_matched_geocodes = []

        seen_geocodes = set()

        for geo in matched_geocodes:

            key = (
                geo.get(
                    "valueName"
                ),
                geo.get(
                    "value"
                ),
            )

            if key in seen_geocodes:
                continue

            seen_geocodes.add(
                key
            )

            unique_matched_geocodes.append(
                geo
            )

        # ====================================================
        # 12. 最終 alert
        # ====================================================

        alert = {

            # ------------------------------------------------
            # 核心欄位
            # ------------------------------------------------

            "id":
                str(identifier),

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

            # ------------------------------------------------
            # area
            #
            # 這裡以命中的縣市為主。
            #
            # 不再把整個 CAP 的 areaDesc
            # 當作 Telegram 區域範圍。
            # ------------------------------------------------

            "area":
                matched_area,

            # ------------------------------------------------
            # 分類
            # ------------------------------------------------

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

            # ------------------------------------------------
            # URL
            # ------------------------------------------------

            "cap_url":
                cap_url,

            # ------------------------------------------------
            # 區域
            # ------------------------------------------------

            "matched_area":
                matched_area,

            "areas":
                normalized_areas,

            "area_descs":
                cap.get(
                    "area_descs",
                    [],
                ),

            # ------------------------------------------------
            # Taiwan_Geocode_113
            # ------------------------------------------------

            "matched_geocodes":
                unique_matched_geocodes,

            # ------------------------------------------------
            # 地震
            # ------------------------------------------------

            "is_earthquake":
                is_earthquake,

            "earthquake_areas":
                cap.get(
                    "earthquake_areas",
                    [],
                ),

            "earthquake_geocodes":
                cap.get(
                    "earthquake_geocodes",
                    [],
                ),

            "earthquake_area_details":
                cap.get(
                    "earthquake_area_details",
                    [],
                ),

            "earthquake_intensity":
                cap.get(
                    "earthquake_intensity",
                    {},
                ),

            "geocodes":
                cap.get(
                    "geocodes",
                    [],
                ),

            # ------------------------------------------------
            # 時間 / 去重
            # ------------------------------------------------

            "published_at":
                published_at,

            "published_at_normalized":
                published_normalized,

            "effective_normalized":
                effective_normalized,

            "expires_normalized":
                expires_normalized,

            # ------------------------------------------------
            # Atom metadata
            # ------------------------------------------------

            "atom_title":
                title,

            "atom_summary":
                summary,

            "atom_updated":
                published_at,
        }

        result.append(
            alert
        )

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
        f"CAP errors     = "
        f"{cap_errors}"
    )

    print(
        f"Final alerts   = "
        f"{len(result)}"
    )

    print(
        "Area filter    = "
        "NCDR Taiwan_Geocode_113"
    )

    print(
        "Text fallback  = "
        "DISABLED"
    )

    print(
        "=========================================="
    )

    return result

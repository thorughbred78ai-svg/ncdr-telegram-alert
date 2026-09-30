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

def _local_name(tag: Any) -> str:
    """
    XML:

        {namespace}areaDesc
        cap:areaDesc

    都轉成：

        areaDesc
    """

    if not isinstance(tag, str):
        return ""

    if "}" in tag:
        return tag.rsplit("}", 1)[1]

    if ":" in tag:
        return tag.rsplit(":", 1)[1]

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

        if _local_name(element.tag) != name:
            continue

        value = _text(element)

        if value:
            return value

    return ""


def _find_all(
    root: ET.Element,
    name: str,
) -> list[ET.Element]:

    result = []

    for element in root.iter():

        if _local_name(element.tag) == name:
            result.append(element)

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

    return _text(element)


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

    return _text(element)


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

    return _text(name)


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
    """
    警報類型判斷。

    注意：
    這裡仍然可以用 title/category/event 做類型搜尋。

    但「區域」不會使用這種全文搜尋方式。
    """

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
# Text area matching
# ============================================================

def _area_matches_text(
    text: str,
    areas: list[str],
) -> str:
    """
    將文字與指定區域比對。

    注意：
    這個函式本身只負責文字比對。

    真正的區域過濾現在只會傳入
    CAP <areaDesc>，不會傳入整份 CAP。
    """

    if not text:
        return ""

    for wanted_area in areas:

        wanted_area = (
            wanted_area or ""
        ).strip()

        if not wanted_area:
            continue

        if wanted_area in text:
            return wanted_area

    return ""


def _match_area_descs_strict(
    area_descs: list[str],
    wanted_areas: list[str],
) -> str:
    """
    嚴格區域判斷。

    只允許真正的 CAP <areaDesc> 命中。

    不檢查：
        summary
        headline
        description
        instruction
        CAP 全文
        Atom title

    例如：

        config:
            areas = ["桃園市"]

        CAP:
            <areaDesc>新北市...</areaDesc>

        即使 description 寫：
            桃園市民眾也請注意...

        仍然不算桃園市警報。
    """

    if not area_descs:
        return ""

    if not wanted_areas:
        return ""

    for area_desc in area_descs:

        area_desc = (
            area_desc or ""
        ).strip()

        if not area_desc:
            continue

        matched = _area_matches_text(
            area_desc,
            wanted_areas,
        )

        if matched:
            return matched

    return ""


# ============================================================
# Geocode helpers
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

        for child in list(geocode):

            name = _local_name(
                child.tag
            )

            if name == "valueName":

                value_name = _text(child)

            elif name == "value":

                value = _text(child)

        if value_name or value:

            result.append({
                "valueName": value_name,
                "value": value,
            })

    return result


def _get_area_blocks(
    root: ET.Element,
) -> list[dict]:
    """
    把 CAP 裡每一個 <area> 分開解析。

    例如：

        <area>
            <areaDesc>最大震度2級地區</areaDesc>

            <geocode>
                <valueName>
                    Taiwan_Geocode_103
                </valueName>
                <value>10015</value>
            </geocode>
        </area>
    """

    result = []

    for area_element in _find_all(
        root,
        "area",
    ):

        area_desc = ""

        geocodes = []

        for child in list(area_element):

            child_name = _local_name(
                child.tag
            )

            if child_name == "areaDesc":

                value = _text(child)

                if value:
                    area_desc = value

            elif child_name == "geocode":

                value_name = ""
                value = ""

                for geo_child in list(child):

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

                if value_name or value:

                    geocodes.append({
                        "valueName": value_name,
                        "value": value,
                    })

        result.append({
            "areaDesc": area_desc,
            "geocodes": geocodes,
        })

    return result


# ============================================================
# 行政區名稱解析
# ============================================================

def _extract_city_names(
    text: str,
) -> list[str]:
    """
    從單一 areaDesc 擷取臺灣行政區名稱。

    注意：
    這個函式只應用於真正的 areaDesc，
    不會對 CAP 全文使用。
    """

    if not text:
        return []

    cities = [
        "臺北市",
        "新北市",
        "桃園市",
        "臺中市",
        "臺南市",
        "高雄市",
        "基隆市",
        "新竹市",
        "新竹縣",
        "苗栗縣",
        "彰化縣",
        "南投縣",
        "雲林縣",
        "嘉義市",
        "嘉義縣",
        "屏東縣",
        "宜蘭縣",
        "花蓮縣",
        "臺東縣",
        "澎湖縣",
        "金門縣",
        "連江縣",
    ]

    result = []

    for city in cities:

        if city in text:
            result.append(city)

    return result


# ============================================================
# 地震區域解析
# ============================================================

def _parse_earthquake_areas(
    root: ET.Element,
    wanted_areas: list[str],
) -> dict:
    """
    地震 CAP 特別處理。

    重要：

    舊版會從 CAP 全文尋找：

        桃園市
        新北市

    這會造成非指定區域誤推播。

    現在只允許：

        <area>
            <areaDesc>...</areaDesc>
        </area>

    裡面的 areaDesc 作為區域判斷依據。

    geocode 仍然完整保留，
    供 main.py 或後續程式使用。
    """

    area_blocks = _get_area_blocks(
        root
    )

    earthquake_areas = []
    earthquake_geocodes = []

    matched_areas = []

    details = []

    for block in area_blocks:

        area_desc = (
            block.get("areaDesc")
            or ""
        ).strip()

        geocodes = (
            block.get("geocodes")
            or []
        )

        # ----------------------------------------------------
        # 保存 areaDesc
        # ----------------------------------------------------

        if area_desc:

            earthquake_areas.append(
                area_desc
            )

        # ----------------------------------------------------
        # 保存 area + geocode
        # ----------------------------------------------------

        details.append({
            "areaDesc": area_desc,
            "geocodes": geocodes,
        })

        # ----------------------------------------------------
        # 保存 geocode
        # ----------------------------------------------------

        for geo in geocodes:

            value_name = (
                geo.get("valueName")
                or ""
            )

            value = (
                geo.get("value")
                or ""
            )

            if value_name or value:

                earthquake_geocodes.append({
                    "valueName": value_name,
                    "value": value,
                })

        # ----------------------------------------------------
        # 嚴格區域判斷
        #
        # 只看這個 <area> 的 areaDesc
        # ----------------------------------------------------

        for wanted_area in wanted_areas:

            wanted_area = (
                wanted_area or ""
            ).strip()

            if not wanted_area:
                continue

            if (
                wanted_area in area_desc
            ):

                if (
                    wanted_area
                    not in matched_areas
                ):

                    matched_areas.append(
                        wanted_area
                    )

    # --------------------------------------------------------
    # 震度
    # --------------------------------------------------------

    intensity_map = {}

    for block in area_blocks:

        area_desc = (
            block.get("areaDesc")
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
            []
        )

        for geo in (
            block.get("geocodes")
            or []
        ):

            intensity_map[
                intensity
            ].append(geo)

    return {
        "matched_areas":
            list(dict.fromkeys(
                matched_areas
            )),

        "earthquake_areas":
            list(dict.fromkeys(
                earthquake_areas
            )),

        "earthquake_geocodes":
            earthquake_geocodes,

        "earthquake_area_details":
            details,

        "earthquake_intensity":
            intensity_map,
    }


# ============================================================
# General CAP area matching
# ============================================================

def _parse_general_area(
    root: ET.Element,
    summary: str,
    wanted_areas: list[str],
) -> tuple[str, list[str]]:
    """
    一般警報區域判斷。

    嚴格規則：

        只看 CAP <areaDesc>

    不再使用：

        summary
        description
        headline
        instruction
        CAP 全文
    """

    area_descs = []

    for element in _find_all(
        root,
        "areaDesc",
    ):

        value = _text(element)

        if value:
            area_descs.append(value)

    area_descs = list(
        dict.fromkeys(
            area_descs
        )
    )

    # --------------------------------------------------------
    # 嚴格 areaDesc matching
    # --------------------------------------------------------

    matched_area = _match_area_descs_strict(
        area_descs,
        wanted_areas,
    )

    return (
        matched_area,
        area_descs,
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

        value = _text(element)

        if value:
            area_descs.append(value)

    area_descs = list(
        dict.fromkeys(
            area_descs
        )
    )

    area = "、".join(
        area_descs
    )

    # ========================================================
    # 地震
    # ========================================================

    earthquake_data = {
        "matched_areas": [],
        "earthquake_areas": [],
        "earthquake_geocodes": [],
        "earthquake_area_details": [],
        "earthquake_intensity": {},
    }

    if is_earthquake:

        earthquake_data = (
            _parse_earthquake_areas(
                root,
                wanted_areas,
            )
        )

        matched_area = ""

        for wanted_area in wanted_areas:

            if (
                wanted_area
                in earthquake_data[
                    "matched_areas"
                ]
            ):

                matched_area = wanted_area
                break

    # ========================================================
    # 非地震
    # ========================================================

    else:

        matched_area, _ = (
            _parse_general_area(
                root,
                summary,
                wanted_areas,
            )
        )

    return {

        "root":
            root,

        "area":
            area,

        "area_descs":
            area_descs,

        "matched_area":
            matched_area,

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
# CAP download
# ============================================================

def _empty_cap() -> dict:

    return {

        "area": "",

        "area_descs": [],

        "matched_area": "",

        "earthquake_areas": [],

        "earthquake_geocodes": [],

        "earthquake_area_details": [],

        "earthquake_intensity": {},

        "geocodes": [],

        "instruction": "",

        "effective": "",

        "expires": "",

        "status": "",

        "msgType": "",

        "event": "",

        "headline": "",

        "description": "",
    }


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
    將 NCDR 時間盡量轉成 ISO 8601。

    臺灣時間使用 UTC+8。

    例如：

        2026-09-30T15:30:00+08:00

    會保留為：

        2026-09-30T15:30:00+08:00
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

            # ------------------------------------------------
            # 重要：
            #
            # NCDR 為臺灣時間，不是 UTC。
            # ------------------------------------------------

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

    print(
        "========== NCDR CONFIG =========="
    )

    print(
        f"areas = {areas}"
    )

    print(
        f"alert_types = {alert_types}"
    )

    print(
        "AREA FILTER MODE = STRICT"
    )

    print(
        "Area source = CAP <areaDesc> ONLY"
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

            print(
                f"TYPE SKIP: "
                f"{identifier} | "
                f"title={title!r} | "
                f"category={category!r}"
            )

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
        # 3. 下載 CAP
        # ====================================================

        cap = _get_cap_data(
            session,
            cap_url,
            areas,
            is_earthquake,
            summary,
        )

        if not cap.get("area_descs"):

            cap_errors += 1

        cap_area = (
            cap.get("area")
            or ""
        )

        matched_area = (
            cap.get("matched_area")
            or ""
        )

        area_descs = (
            cap.get("area_descs")
            or []
        )

        # ====================================================
        # 4. 嚴格地區判斷
        # ====================================================
        #
        # 非常重要：
        #
        # 這裡不再 fallback 到：
        #
        #   summary
        #   headline
        #   description
        #   instruction
        #   CAP 全文
        #
        # cap["matched_area"] 已經只允許
        # 真正的 <areaDesc> 命中。
        # ====================================================

        if not matched_area:

            print(
                f"AREA SKIP: "
                f"{identifier} | "
                f"type={event} | "
                f"is_earthquake={is_earthquake} | "
                f"wanted={areas} | "
                f"area_descs={area_descs!r}"
            )

            continue

        area_matched += 1

        print(
            f"AREA MATCH: "
            f"{identifier} | "
            f"type={event} | "
            f"matched_area={matched_area} | "
            f"area_descs={area_descs!r}"
        )

        # ====================================================
        # 5. Description
        # ====================================================

        description = (
            cap.get("description")
            or summary
            or ""
        )

        # ====================================================
        # 6. Headline
        # ====================================================

        headline = (
            cap.get("headline")
            or title
            or event
        )

        # ====================================================
        # 7. Effective
        # ====================================================

        effective = (
            cap.get("effective")
            or published_at
            or ""
        )

        # ====================================================
        # 8. Expires
        # ====================================================

        expires = (
            cap.get("expires")
            or ""
        )

        # ====================================================
        # 9. 時間標準化
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
        # 10. 最終格式
        # ====================================================

        alert = {

            # ------------------------------------------------
            # 核心欄位
            # ------------------------------------------------

            "id":
                str(identifier),

            "event":
                cap.get("event")
                or event,

            "headline":
                headline,

            "description":
                description,

            "instruction":
                cap.get("instruction")
                or "",

            "effective":
                effective,

            "expires":
                expires,

            "area":
                cap_area
                or matched_area,

            # ------------------------------------------------
            # 分類
            # ------------------------------------------------

            "category":
                category,

            "sender":
                sender,

            "status":
                cap.get("status")
                or "",

            "msgType":
                cap.get("msgType")
                or "",

            # ------------------------------------------------
            # URL
            # ------------------------------------------------

            "cap_url":
                cap_url,

            # ------------------------------------------------
            # 地區
            # ------------------------------------------------

            "matched_area":
                matched_area,

            "areas":
                areas,

            "area_descs":
                cap.get(
                    "area_descs",
                    [],
                ),

            # ------------------------------------------------
            # 地震專用
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
            # 去重用
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
            # Feed metadata
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
        "STRICT / areaDesc ONLY"
    )

    print(
        "=========================================="
    )

    return result

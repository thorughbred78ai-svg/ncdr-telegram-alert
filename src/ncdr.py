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
    """
    取得 XML tag 的真正名稱。

    例如：

    {namespace}areaDesc
        ↓
    areaDesc

    cap:areaDesc
        ↓
    areaDesc
    """

    if not isinstance(
        tag,
        str
    ):
        return ""

    if "}" in tag:

        return tag.rsplit(
            "}",
            1
        )[1]

    if ":" in tag:

        return tag.rsplit(
            ":",
            1
        )[1]

    return tag


def _text(element) -> str:

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
    name: str
) -> str:
    """
    不依賴 namespace，
    尋找第一個指定名稱的 XML element。
    """

    for element in root.iter():

        if _local_name(
            element.tag
        ) != name:

            continue

        value = _text(
            element
        )

        if value:
            return value

    return ""


def _find_all(
    root,
    name: str
) -> list:

    result = []

    for element in root.iter():

        if _local_name(
            element.tag
        ) == name:

            result.append(
                element
            )

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

    return _text(
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

    return _text(
        element
    )


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

    return _text(
        name
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


# ============================================================
# Config matching
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


def _area_matches_text(
    text: str,
    areas: list[str]
) -> bool:

    if not text:
        return False

    return any(
        area in text
        for area in areas
    )


# ============================================================
# 地震 geocode
# ============================================================

def _get_geocodes(
    root
) -> list[dict]:
    """
    取得 CAP 裡面的 geocode。

    NCDR 地震使用：

        valueName = Taiwan_Geocode_100

    value 是縣市代碼。

    官方 NCDR 地震 CAP 文件確認：
    Taiwan_Geocode_100 用於臺灣各縣市區域代碼。
    """

    result = []

    # 找所有 geocode
    for geocode in _find_all(
        root,
        "geocode"
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

        if value_name or value:

            result.append({
                "valueName":
                    value_name,
                "value":
                    value
            })

    return result


def _get_earthquake_areas(
    root
) -> list[str]:
    """
    解析地震 CAP 的縣市區域。

    NCDR 地震的 geocode 使用：

        Taiwan_Geocode_100

    目前 config 使用的是：

        桃園市
        新北市

    因此這裡會把 geocode code
    轉換成縣市名稱。

    常見 Taiwan_Geocode_100：

        10001 = 新北市
        10002 = 宜蘭縣
        10003 = 桃園市
        ...

    為避免只依賴 code 排列，
    同時也會檢查 areaDesc。
    """

    areas = []

    # --------------------------------------------------------
    # 第一層：areaDesc
    #
    # 某些 NCDR 地震 CAP 的 areaDesc
    # 會直接包含受影響縣市。
    # --------------------------------------------------------

    for area_element in _find_all(
        root,
        "area"
    ):

        area_desc = ""

        for child in list(
            area_element
        ):

            if (
                _local_name(
                    child.tag
                )
                == "areaDesc"
            ):

                area_desc = _text(
                    child
                )

                break

        if area_desc:

            areas.append(
                area_desc
            )

    # --------------------------------------------------------
    # 第二層：geocode
    # --------------------------------------------------------

    geocodes = _get_geocodes(
        root
    )

    for item in geocodes:

        value_name = (
            item["valueName"]
        )

        value = (
            item["value"]
        )

        if (
            value_name
            == "Taiwan_Geocode_100"
        ):

            areas.append(
                f"GEOCODE:{value}"
            )

    return list(
        dict.fromkeys(
            areas
        )
    )


# ============================================================
# Taiwan_Geocode_100
# ============================================================

TAIWAN_GEOCODE_100 = {

    # 六都
    "10001": "新北市",
    "10002": "宜蘭縣",
    "10003": "桃園市",
    "10004": "新竹縣",
    "10005": "苗栗縣",
    "10006": "臺中市",
    "10007": "彰化縣",
    "10008": "南投縣",
    "10009": "雲林縣",
    "10010": "嘉義縣",
    "10013": "臺南市",
    "10014": "高雄市",
    "10015": "屏東縣",
    "10016": "臺東縣",
    "10017": "花蓮縣",
    "10018": "澎湖縣",
    "10020": "基隆市",
    "10021": "新竹市",
    "10022": "嘉義市",
    "10023": "臺北市",

    # 金馬
    "09007": "連江縣",
    "09020": "金門縣"
}


def _geocode_to_city(
    value: str
) -> str:

    value = (
        value
        or ""
    ).strip()

    if not value:
        return ""

    # 完整代碼
    if value in TAIWAN_GEOCODE_100:

        return TAIWAN_GEOCODE_100[
            value
        ]

    # 有些資料可能多個 code
    # 或附加文字
    for code, city in (
        TAIWAN_GEOCODE_100.items()
    ):

        if code in value:

            return city

    return ""


def _earthquake_area_names(
    root
) -> list[str]:

    result = []

    # areaDesc
    for value in _find_all(
        root,
        "areaDesc"
    ):

        text = _text(
            value
        )

        if text:

            result.append(
                text
            )

    # geocode
    for item in _get_geocodes(
        root
    ):

        if (
            item["valueName"]
            != "Taiwan_Geocode_100"
        ):

            continue

        city = _geocode_to_city(
            item["value"]
        )

        if city:

            result.append(
                city
            )

    return list(
        dict.fromkeys(
            result
        )
    )


# ============================================================
# CAP parser
# ============================================================

def _parse_cap(
    xml_data: bytes
) -> dict:

    root = ET.fromstring(
        xml_data
    )

    area_descs = []

    for element in _find_all(
        root,
        "areaDesc"
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

    # --------------------------------------------------------
    # Basic CAP fields
    # --------------------------------------------------------

    return {

        "root": root,

        "area":
            area,

        "area_descs":
            area_descs,

        "earthquake_areas":
            _earthquake_area_names(
                root
            ),

        "geocodes":
            _get_geocodes(
                root
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

        "earthquake_areas": [],

        "geocodes": [],

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
# Main
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
# Normalize alerts
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
    # Process Atom entries
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
        # 1. alert_types
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
        # 2. 判斷是不是地震
        # ====================================================

        is_earthquake = (
            "地震" in event
            or "地震" in category
            or "地震" in title
        )

        # ====================================================
        # 3. 只有符合類型才下載 CAP
        # ====================================================

        cap = _get_cap_data(
            session,
            cap_url
        )

        cap_area = (
            cap.get("area")
            or ""
        )

        earthquake_areas = (
            cap.get(
                "earthquake_areas",
                []
            )
        )

        # ====================================================
        # 4. 地區判斷
        # ====================================================

        area_match = False

        matched_area = ""

        # ----------------------------------------------------
        # 地震
        #
        # 不再只看：
        #
        # 花蓮縣政府東方...
        #
        # 而是看 Taiwan_Geocode_100
        # ----------------------------------------------------

        if is_earthquake:

            print(
                f"EARTHQUAKE GEOCODES: "
                f"{identifier} | "
                f"{earthquake_areas}"
            )

            for wanted_area in areas:

                if any(
                    wanted_area in area
                    for area
                    in earthquake_areas
                ):

                    area_match = True

                    matched_area = (
                        wanted_area
                    )

                    break

            # 如果 geocode 沒抓到，
            # 再嘗試 areaDesc
            if not area_match:

                if _area_matches_text(
                    cap_area,
                    areas
                ):

                    area_match = True

                    for wanted_area in areas:

                        if (
                            wanted_area
                            in cap_area
                        ):

                            matched_area = (
                                wanted_area
                            )

                            break

        # ----------------------------------------------------
        # 非地震
        #
        # 使用 CAP areaDesc
        # ----------------------------------------------------

        else:

            if _area_matches_text(
                cap_area,
                areas
            ):

                area_match = True

                for wanted_area in areas:

                    if (
                        wanted_area
                        in cap_area
                    ):

                        matched_area = (
                            wanted_area
                        )

                        break

            # CAP 沒有地區時，
            # 再看 Atom summary
            elif _area_matches_text(
                summary,
                areas
            ):

                area_match = True

                matched_area = next(
                    (
                        wanted_area
                        for wanted_area
                        in areas
                        if wanted_area
                        in summary
                    ),
                    ""
                )

        # ====================================================
        # 5. Area skip
        # ====================================================

        if not area_match:

            print(
                f"AREA SKIP: "
                f"{identifier} | "
                f"type={event} | "
                f"cap_area="
                f"{cap_area!r} | "
                f"earthquake_areas="
                f"{earthquake_areas}"
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
        # 6. Description
        # ====================================================

        description = (
            cap.get(
                "description"
            )
            or summary
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
            or _atom_text(
                entry,
                "updated"
            )
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
        # 10. 最終統一格式
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

            # 額外保留，
            # 方便 main.py/debug 使用
            "matched_area":
                matched_area,

            "earthquake_areas":
                earthquake_areas,

            "geocodes":
                cap.get(
                    "geocodes",
                    []
                )
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

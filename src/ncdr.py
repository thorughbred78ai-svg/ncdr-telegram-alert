import xml.etree.ElementTree as ET

import requests


# NCDR 民生示警公開資料平台
NCDR_ALERT_LIST_URL = (
    "https://alerts.ncdr.nat.gov.tw/RssAtomFeed.ashx"
)


# XML Namespace
ATOM_NS = "http://www.w3.org/2005/Atom"
CAP_NS = "urn:oasis:names:tc:emergency:cap:1.1"


def get_alerts() -> list[dict]:

    headers = {
        "Accept": "application/atom+xml, application/xml, text/xml"
    }

    response = requests.get(
        NCDR_ALERT_LIST_URL,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    return normalize_alerts(
        response.text
    )


def _get_text(
    element,
    tag: str
) -> str:

    if element is None:
        return ""

    child = element.find(
        tag
    )

    if child is None:
        return ""

    return (
        child.text or ""
    ).strip()


def _get_cap_text(
    element,
    tag: str
) -> str:

    if element is None:
        return ""

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

    """
    將 NCDR Atom Feed 轉成程式內統一格式。

    最終格式：

    {
        id,
        event,
        headline,
        description,
        instruction,
        effective,
        expires,
        area
    }
    """

    root = ET.fromstring(
        data
    )

    result = []

    for entry in root.findall(
        f"{{{ATOM_NS}}}entry"
    ):

        # ==========================================
        # ID
        # ==========================================

        identifier = _get_text(
            entry,
            f"{{{ATOM_NS}}}id"
        )

        if not identifier:
            continue

        # ==========================================
        # 災害類型
        #
        # <title>停水</title>
        # <category term="停水" />
        # ==========================================

        title = _get_text(
            entry,
            f"{{{ATOM_NS}}}title"
        )

        category = entry.find(
            f"{{{ATOM_NS}}}category"
        )

        category_term = ""

        if category is not None:
            category_term = (
                category.get("term")
                or ""
            ).strip()

        # 優先使用 category
        event = (
            category_term
            or title
        )

        # ==========================================
        # 摘要
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
        # CAP 狀態
        # ==========================================

        status = _get_cap_text(
            entry,
            "status"
        )

        msg_type = _get_cap_text(
            entry,
            "msgType"
        )

        effective = _get_cap_text(
            entry,
            "effective"
        )

        expires = _get_cap_text(
            entry,
            "expires"
        )

        # ==========================================
        # 發布單位
        # ==========================================

        author = entry.find(
            f"{{{ATOM_NS}}}author/"
            f"{{{ATOM_NS}}}name"
        )

        sender = ""

        if author is not None:
            sender = (
                author.text or ""
            ).strip()

        # ==========================================
        # 建立統一格式
        # ==========================================

        result.append({

            "id": identifier,

            # 真正災害類型
            "event": event,

            # Feed title
            "headline": title,

            # summary
            "description": description,

            "instruction": "",

            "effective": effective,

            "expires": expires,

            # Atom Feed 目前沒有直接提供
            # area 欄位
            "area": "",

            # 額外保留資訊
            "category": category_term,

            "sender": sender,

            "status": status,

            "msgType": msg_type
        })

    return result

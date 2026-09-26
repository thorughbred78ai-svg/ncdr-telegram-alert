import os
import requests


NCDR_API_KEY = os.environ["NCDR_API_KEY"]

# TODO:
# 從你的 NCDR API 文件取得實際 endpoint
NCDR_ALERT_LIST_URL = os.environ[
    "NCDR_ALERT_LIST_URL"
]


def get_alerts() -> list[dict]:

    headers = {
        "Accept": "application/json"
    }

    params = {
        "apikey": NCDR_API_KEY
    }

    response = requests.get(
        NCDR_ALERT_LIST_URL,
        headers=headers,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    return normalize_alerts(data)


def normalize_alerts(data) -> list[dict]:
    """
    將 NCDR API 回傳資料轉成程式內統一格式。

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

    if isinstance(data, list):
        raw_alerts = data

    elif isinstance(data, dict):
        raw_alerts = (
            data.get("alerts")
            or data.get("data")
            or data.get("items")
            or []
        )

    else:
        raw_alerts = []

    result = []

    for item in raw_alerts:

        identifier = (
            item.get("identifier")
            or item.get("id")
            or item.get("capid")
            or item.get("capId")
        )

        if not identifier:
            continue

        area = (
            item.get("areaDesc")
            or item.get("area")
            or item.get("location")
            or ""
        )

        result.append({
            "id": str(identifier),

            "event": (
                item.get("event")
                or item.get("type")
                or ""
            ),

            "headline": (
                item.get("headline")
                or ""
            ),

            "description": (
                item.get("description")
                or ""
            ),

            "instruction": (
                item.get("instruction")
                or ""
            ),

            "effective": (
                item.get("effective")
                or ""
            ),

            "expires": (
                item.get("expires")
                or ""
            ),

            "area": area
        })

    return result

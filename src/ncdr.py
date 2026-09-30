import requests


# NCDR 民生示警公開資料平台
NCDR_ALERT_LIST_URL = (
    "https://alerts.ncdr.nat.gov.tw/RssAtomFeed.ashx"
)


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

    data = response.text

    return normalize_alerts(data)


def normalize_alerts(data) -> list[dict]:
    """
    將 NCDR CAP/ATOM 資料轉成程式內統一格式。

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

    # 暫時保留。
    #
    # 下一步需要依照 NCDR 實際回傳的
    # Atom/CAP XML 結構解析。
    #
    # 先回傳空陣列，避免把錯誤資料送到 Telegram。

    return []

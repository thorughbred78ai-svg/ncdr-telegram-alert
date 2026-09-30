import requests


NCDR_ALERT_LIST_URL = (
    "https://alerts.ncdr.nat.gov.tw/RssAtomFeed.ashx"
)


def get_alerts() -> list[dict]:

    response = requests.get(
        NCDR_ALERT_LIST_URL,
        timeout=30
    )

    print(
        "NCDR HTTP STATUS:",
        response.status_code
    )

    print(
        "NCDR CONTENT TYPE:",
        response.headers.get("Content-Type")
    )

    print(
        "========== NCDR RAW =========="
    )

    print(
        response.text[:10000]
    )

    print(
        "=============================="
    )

    response.raise_for_status()

    return []


def normalize_alerts(data) -> list[dict]:
    return []

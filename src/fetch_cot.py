from __future__ import annotations

from datetime import date

import requests


def fetch_cot_line(today: date) -> str:
    """Read weekly non-commercial yen futures positions from CFTC."""
    fallback = "円先物 COT: 未確認（CFTC / 対象週未確認）"
    try:
        response = requests.get(
            "https://publicreporting.cftc.gov/resource/6dca-aqww.json",
            params={
                "cftc_contract_market_code": "097741",
                "$select": "report_date_as_yyyy_mm_dd,noncomm_positions_long_all,noncomm_positions_short_all",
                "$order": "report_date_as_yyyy_mm_dd DESC",
                "$limit": 1,
            },
            timeout=10,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return fallback
        row = rows[0]
        observed = date.fromisoformat(row["report_date_as_yyyy_mm_dd"][:10])
        age = (today - observed).days
        if not 0 <= age <= 14:
            return fallback
        net = int(row["noncomm_positions_long_all"]) - int(row["noncomm_positions_short_all"])
        year, week, _ = observed.isocalendar()
        return f"円先物 非商業部門ネット {net:+,}枚（CFTC / {year}年第{week}週・{observed}時点）"
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return fallback

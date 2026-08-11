from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests


JST = ZoneInfo("Asia/Tokyo")
DEFAULT_MAX_STALE_DAYS = 14


def _safe_float(value: str | None) -> float | None:
    if value in (None, ".", ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / previous) * 100


def fetch_macro_snapshot(task_config: dict[str, Any], sources: dict[str, Any]) -> list[dict[str, Any]]:
    fred_api_key = os.getenv("FRED_API_KEY", "").strip()
    if not fred_api_key:
        return []

    macro_sources = sources.get("macro", {}).get("fred_series", {})
    quality_config = sources.get("quality", {}) or {}
    max_stale_days = int(quality_config.get("macro_max_stale_days", DEFAULT_MAX_STALE_DAYS))
    items: list[dict[str, Any]] = []

    for series_key in task_config.get("macro_series", []):
        meta = macro_sources.get(series_key, {})
        series_id = meta.get("series_id")
        if not series_id:
            continue

        try:
            response = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": fred_api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 10,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            observations = payload.get("observations", [])
            usable = []
            for observation in observations:
                value = _safe_float(observation.get("value"))
                if value is None:
                    continue
                usable.append(
                    {
                        "date": observation.get("date", ""),
                        "value": value,
                    }
                )
            if len(usable) < 2:
                raise ValueError("有効な日次データが不足しています")

            current = usable[0]["value"]
            previous = usable[1]["value"]
            as_of = str(usable[0].get("date", ""))
            try:
                stale_days = (datetime.now(JST).date() - datetime.fromisoformat(as_of).date()).days
            except ValueError as exc:
                raise ValueError("基準日を確認できません") from exc
            if stale_days < 0:
                raise ValueError("未来日付のデータを検出しました")
            if stale_days > max_stale_days:
                raise ValueError(f"データが古いため未確認です（基準日 {as_of}）")

            series = list(reversed(usable[:6]))
            absolute_change = current - previous
            is_rate = series_key in {"US10Y", "SOFR", "YIELD_2S10S"}
            items.append(
                {
                    "key": series_key,
                    "label": meta.get("label", series_key),
                    "ticker": series_id,
                    "current": current,
                    "previous": previous,
                    "change_pct": _safe_pct_change(current, previous),
                    "change_abs": absolute_change,
                    "change_bps": absolute_change * 100 if is_rate else None,
                    "series": series,
                    "status": "ok",
                    "unit": meta.get("unit", ""),
                    "source": "FRED",
                    "as_of": as_of,
                    "stale_days": stale_days,
                    "quality_status": "verified",
                    "quality_notes": [f"基準日 {as_of}", "FRED公式系列"],
                    "comparison_group": "rate_level" if is_rate else "risk_indicator",
                }
            )
        except Exception as exc:
            items.append(
                {
                    "key": series_key,
                    "label": meta.get("label", series_key),
                    "ticker": series_id,
                    "current": None,
                    "previous": None,
                    "change_pct": None,
                    "series": [],
                    "status": "unavailable",
                    "unit": meta.get("unit", ""),
                    "source": "FRED",
                    "as_of": None,
                    "quality_status": "unavailable",
                    "comparison_group": "rate_level" if series_key in {"US10Y", "SOFR", "YIELD_2S10S"} else "risk_indicator",
                    "note": f"未確認: {exc}",
                }
            )

    return items

from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf

from fetch_macro import fetch_macro_snapshot


def _safe_pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / previous) * 100


def _series_from_history(history: pd.DataFrame) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    if history.empty:
        return series

    closes = history["Close"].dropna()
    for index, value in closes.tail(5).items():
        series.append({"date": str(index.date()), "value": float(value)})
    return series


def _fetch_symbol(symbol_key: str, ticker: str, label: str) -> dict[str, Any]:
    try:
        history = yf.download(
            ticker,
            period="7d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="column",
            multi_level_index=False,
        )
        closes = history["Close"].dropna()
        if len(closes) < 2:
            raise ValueError("終値データが不足しています")

        current = float(closes.iloc[-1])
        previous = float(closes.iloc[-2])
        pct_change = _safe_pct_change(current, previous)

        return {
            "key": symbol_key,
            "label": label,
            "ticker": ticker,
            "current": current,
            "previous": previous,
            "change_pct": pct_change,
            "series": _series_from_history(history),
            "status": "ok",
        }
    except Exception as exc:
        return {
            "key": symbol_key,
            "label": label,
            "ticker": ticker,
            "current": None,
            "previous": None,
            "change_pct": None,
            "series": [],
            "status": "unavailable",
            "note": f"未確認: {exc}",
        }


def fetch_fx_snapshot(
    task_id: str,
    task_config: dict[str, Any],
    sources: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    fx_sources = sources.get("fx", {})
    symbol_map = fx_sources.get("symbols", {})

    items: list[dict[str, Any]] = []
    for symbol_key in task_config.get("chart_symbols", []):
        meta = symbol_map.get(symbol_key, {})
        items.append(_fetch_symbol(symbol_key, meta.get("ticker", symbol_key), meta.get("label", symbol_key)))

    unavailable_items = fx_sources.get("unavailable_items", {})

    return {
        "task_id": task_id,
        "section": "fx",
        "items": items,
        "macro_items": fetch_macro_snapshot(task_config, sources),
        "highlights": {
            "speculative_positions": unavailable_items.get("speculative_positions", "未確認"),
        },
    }

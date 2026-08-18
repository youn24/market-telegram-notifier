from __future__ import annotations

import math
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from fetch_macro import fetch_macro_snapshot
from fetch_nikkei225jp import fetch_nikkei225jp_snapshot
from fetch_themes import fetch_theme_snapshot
from fetch_youtube import fetch_youtube_snapshot


JST = ZoneInfo("Asia/Tokyo")
DEFAULT_MAX_STALE_DAYS = 7


def _reasonable_move_limit(symbol_key: str) -> float:
    if symbol_key in {"USDJPY", "EURUSD", "EURJPY", "DXY"}:
        return 6.0
    if symbol_key in {"GOLD", "WTI"}:
        return 20.0
    return 18.0


def _safe_pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / previous) * 100


def _series_from_history(history: pd.DataFrame) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    if history.empty:
        return series

    closes = history["Close"].dropna().sort_index()
    for index, value in closes.tail(6).items():
        series.append({"date": str(index.date()), "value": float(value)})
    return series


def _download_history(ticker: str) -> pd.DataFrame:
    return yf.download(
        ticker,
        period="10d",
        interval="1d",
        # Adjusted prices prevent splits and distributions from appearing as market moves.
        auto_adjust=True,
        progress=False,
        group_by="column",
        multi_level_index=False,
    )


def _fetch_symbol(
    symbol_key: str,
    ticker: str,
    label: str,
    alternate_tickers: list[str] | None = None,
    max_stale_days: int = DEFAULT_MAX_STALE_DAYS,
) -> dict[str, Any]:
    tickers_to_try = [ticker, *(alternate_tickers or [])]
    errors: list[str] = []

    for candidate_ticker in tickers_to_try:
        if not candidate_ticker:
            continue
        try:
            history = _download_history(candidate_ticker)
            closes = history["Close"].dropna().sort_index()
            if len(closes) < 2:
                raise ValueError("終値データが不足しています")

            current = float(closes.iloc[-1])
            previous = float(closes.iloc[-2])
            if not all(math.isfinite(value) and value > 0 for value in (current, previous)):
                raise ValueError("価格が不正です")

            latest_index = closes.index[-1]
            latest_date = latest_index.date() if hasattr(latest_index, "date") else None
            if latest_date is None:
                raise ValueError("基準日を確認できません")
            stale_days = (datetime.now(JST).date() - latest_date).days
            if stale_days < 0:
                raise ValueError("未来日付のデータを検出しました")
            if stale_days > max_stale_days:
                raise ValueError(f"データが古いため未確認です（基準日 {latest_date}）")

            change_pct = _safe_pct_change(current, previous)
            limit = _reasonable_move_limit(symbol_key)
            if change_pct is None or abs(change_pct) > limit:
                raise ValueError(f"異常変動を検出しました（前日比 {change_pct:+.2f}% / 許容 {limit:.0f}%）")

            quality_notes = [f"基準日 {latest_date}", "調整後終値"]
            if candidate_ticker != ticker:
                quality_notes.append(f"代替ティッカー {candidate_ticker}")
            return {
                "key": symbol_key,
                "label": label,
                "ticker": candidate_ticker,
                "current": current,
                "previous": previous,
                "change_pct": change_pct,
                "series": _series_from_history(history),
                "status": "ok",
                "source": "Yahoo Finance via yfinance",
                "as_of": str(latest_date),
                "stale_days": stale_days,
                "quality_status": "verified",
                "quality_notes": quality_notes,
                "comparison_group": "market_return",
                "fallback_used": candidate_ticker != ticker,
                "primary_ticker": ticker,
            }
        except Exception as exc:
            errors.append(f"{candidate_ticker}: {exc}")

    try:
        note = " / ".join(errors[:3])
    except Exception:
        note = "取得エラー"
    return {
        "key": symbol_key,
        "label": label,
        "ticker": ticker,
        "current": None,
        "previous": None,
        "change_pct": None,
        "series": [],
        "status": "unavailable",
        "source": "Yahoo Finance via yfinance",
        "as_of": None,
        "quality_status": "unavailable",
        "comparison_group": "market_return",
        "note": f"未確認: {note}",
    }


def fetch_japan_market_snapshot(
    task_id: str,
    task_config: dict[str, Any],
    sources: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    market_sources = sources.get("japan_market", {})
    quality_config = sources.get("quality", {}) or {}
    max_stale_days = int(quality_config.get("market_max_stale_days", DEFAULT_MAX_STALE_DAYS))
    symbol_map = market_sources.get("symbols", {})
    items: list[dict[str, Any]] = []

    for symbol_key in task_config.get("chart_symbols", []):
        meta = symbol_map.get(symbol_key, {})
        alternates = [str(value) for value in meta.get("alternate_tickers", [])]
        items.append(
            _fetch_symbol(
                symbol_key,
                meta.get("ticker", symbol_key),
                meta.get("label", symbol_key),
                alternates,
                max_stale_days,
            )
        )

    unavailable_items = market_sources.get("unavailable_items", {})
    highlights = {}
    if task_config.get("focus") != "macro":
        highlights = {
            "earnings": unavailable_items.get("earnings", "未確認"),
            "ratings": unavailable_items.get("ratings", "未確認"),
            "supply_demand": unavailable_items.get("supply_demand", "未確認"),
        }
    themes = fetch_theme_snapshot(sources) if task_config.get("include_themes", False) else {"status": "disabled", "themes": []}
    price_patterns = themes.get("price_patterns", {"status": "disabled", "candidates": []}) if task_config.get("include_price_patterns", False) else {"status": "disabled", "candidates": []}
    youtube = fetch_youtube_snapshot(sources) if task_config.get("include_youtube", False) else {"status": "disabled", "items": []}

    return {
        "task_id": task_id,
        "section": "japan_market",
        "items": items,
        "macro_items": fetch_macro_snapshot(task_config, sources),
        "nikkei225jp": fetch_nikkei225jp_snapshot(sources),
        "themes": themes,
        "price_patterns": price_patterns,
        "youtube": youtube,
        "highlights": highlights,
    }

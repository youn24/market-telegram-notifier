from __future__ import annotations

import math
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf


JST = ZoneInfo("Asia/Tokyo")


def _safe_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1) * 100


def _close_series(history: pd.DataFrame, ticker: str) -> pd.Series:
    if history.empty:
        return pd.Series(dtype="float64")
    try:
        close_data = history["Close"]
    except (KeyError, TypeError):
        return pd.Series(dtype="float64")
    if isinstance(close_data, pd.DataFrame):
        if ticker in close_data.columns:
            close_data = close_data[ticker]
        elif len(close_data.columns) == 1:
            close_data = close_data.iloc[:, 0]
        else:
            return pd.Series(dtype="float64")
    values = pd.to_numeric(close_data, errors="coerce").dropna().sort_index()
    return values[values.map(lambda value: math.isfinite(float(value)) and float(value) > 0)]


def _to_jst(value: Any) -> datetime:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert(JST).to_pydatetime()


def _symbol_snapshot(
    ticker: str,
    label: str,
    intraday: pd.DataFrame,
    daily: pd.DataFrame,
    max_age_hours: float,
) -> dict[str, Any]:
    try:
        intraday_closes = _close_series(intraday, ticker)
        daily_closes = _close_series(daily, ticker)
        if intraday_closes.empty or daily_closes.empty:
            raise ValueError("価格データが不足しています")

        observed_at = _to_jst(intraday_closes.index[-1])
        age_hours = max(0.0, (datetime.now(JST) - observed_at).total_seconds() / 3600)
        if age_hours > max_age_hours:
            raise ValueError(f"データが古いため未確認です（{age_hours:.1f}時間前）")

        current = float(intraday_closes.iloc[-1])
        latest_daily_date = pd.Timestamp(daily_closes.index[-1]).date()
        if latest_daily_date >= observed_at.date() and len(daily_closes) >= 2:
            previous = float(daily_closes.iloc[-2])
        else:
            previous = float(daily_closes.iloc[-1])
        change_pct = _safe_change(current, previous)
        if change_pct is None or abs(change_pct) > 25:
            raise ValueError(f"異常変動を検出しました（{change_pct}）")

        return {
            "ticker": ticker,
            "label": label,
            "current": current,
            "previous": previous,
            "change_pct": change_pct,
            "status": "ok",
            "quality_status": "verified",
            "as_of": observed_at.strftime("%Y-%m-%d %H:%M JST"),
            "age_hours": round(age_hours, 2),
            "source": "Yahoo Finance via yfinance",
        }
    except Exception as exc:
        return {
            "ticker": ticker,
            "label": label,
            "current": None,
            "previous": None,
            "change_pct": None,
            "status": "unavailable",
            "quality_status": "unavailable",
            "as_of": None,
            "source": "Yahoo Finance via yfinance",
            "note": f"未確認: {exc}",
        }


def evaluate_theme_groups(
    symbols: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    themes_config = config.get("themes", {}) or {}
    minimum_valid = int(config.get("minimum_valid_symbols", 3))
    alert_average = float(config.get("alert_average_pct", 1.5))
    alert_breadth = float(config.get("alert_breadth_pct", 75.0))
    themes: list[dict[str, Any]] = []

    for theme_key, theme_meta in themes_config.items():
        members = []
        for member in theme_meta.get("symbols", []):
            ticker = str(member.get("ticker", ""))
            snapshot = dict(symbols.get(ticker, {}))
            snapshot.setdefault("ticker", ticker)
            snapshot.setdefault("label", member.get("label", ticker))
            members.append(snapshot)

        valid = [member for member in members if member.get("status") == "ok" and isinstance(member.get("change_pct"), (int, float))]
        coverage_pct = (len(valid) / len(members) * 100) if members else 0.0
        if len(valid) < minimum_valid:
            themes.append(
                {
                    "key": theme_key,
                    "label": theme_meta.get("label", theme_key),
                    "status": "unavailable",
                    "signal": "未確認",
                    "average_change_pct": None,
                    "breadth_up_pct": None,
                    "breadth_down_pct": None,
                    "coverage_pct": round(coverage_pct),
                    "valid_count": len(valid),
                    "total_count": len(members),
                    "members": members,
                    "leaders": [],
                    "note": f"未確認: 有効銘柄が{len(valid)}/{len(members)}で不足",
                }
            )
            continue

        changes = [float(member["change_pct"]) for member in valid]
        average = sum(changes) / len(changes)
        up_count = len([value for value in changes if value > 0])
        down_count = len([value for value in changes if value < 0])
        breadth_up = up_count / len(changes) * 100
        breadth_down = down_count / len(changes) * 100
        if average >= alert_average and breadth_up >= alert_breadth:
            signal = "一斉高"
            direction = "bull"
            breadth = breadth_up
        elif average <= -alert_average and breadth_down >= alert_breadth:
            signal = "一斉安"
            direction = "bear"
            breadth = breadth_down
        else:
            signal = "監視"
            direction = "neutral"
            breadth = max(breadth_up, breadth_down)

        if direction == "bull":
            leaders = sorted(valid, key=lambda member: float(member.get("change_pct", 0)), reverse=True)[:3]
        elif direction == "bear":
            leaders = sorted(valid, key=lambda member: float(member.get("change_pct", 0)))[:3]
        else:
            leaders = sorted(valid, key=lambda member: abs(float(member.get("change_pct", 0))), reverse=True)[:3]

        magnitude_score = min(30, abs(average) / max(alert_average, 0.01) * 20)
        breadth_score = min(30, breadth / 100 * 30)
        coverage_score = min(30, coverage_pct / 100 * 30)
        leader_score = 10 if len([value for value in changes if abs(value) >= alert_average]) >= 2 else 0
        confirmation_score = round(min(100, magnitude_score + breadth_score + coverage_score + leader_score))

        themes.append(
            {
                "key": theme_key,
                "label": theme_meta.get("label", theme_key),
                "status": "ok",
                "signal": signal,
                "direction": direction,
                "average_change_pct": average,
                "breadth_up_pct": breadth_up,
                "breadth_down_pct": breadth_down,
                "coverage_pct": round(coverage_pct),
                "valid_count": len(valid),
                "total_count": len(members),
                "confirmation_score": confirmation_score,
                "members": members,
                "leaders": leaders,
                "as_of": max((str(member.get("as_of")) for member in valid if member.get("as_of")), default=None),
            }
        )

    verified = [theme for theme in themes if theme.get("status") == "ok"]
    verified.sort(key=lambda theme: abs(float(theme.get("average_change_pct", 0))), reverse=True)
    alerts = [theme for theme in verified if theme.get("signal") in {"一斉高", "一斉安"} and int(theme.get("confirmation_score", 0)) >= 75]
    return {
        "status": "ok" if verified else "unavailable",
        "themes": themes,
        "primary": verified[0] if verified else None,
        "alerts": alerts,
        "verified_count": len(verified),
        "total_count": len(themes),
        "source": "Yahoo Finance via yfinance",
        "note": "テーマ判定は複数銘柄の等ウェイト平均と騰落の広がりで確認。単独銘柄の急変だけでは認定しません。",
    }


def fetch_theme_snapshot(sources: dict[str, Any]) -> dict[str, Any]:
    config = sources.get("theme_stocks", {}) or {}
    if not config.get("enabled", False):
        return {"status": "disabled", "themes": [], "primary": None, "alerts": [], "note": "テーマ株取得は無効です"}

    member_meta: dict[str, str] = {}
    for theme in (config.get("themes", {}) or {}).values():
        for member in theme.get("symbols", []):
            ticker = str(member.get("ticker", ""))
            if ticker:
                member_meta[ticker] = str(member.get("label", ticker))
    tickers = list(member_meta)
    if not tickers:
        return {"status": "unavailable", "themes": [], "primary": None, "alerts": [], "note": "テーマ構成銘柄は未確認"}

    try:
        intraday = yf.download(
            tickers,
            period="2d",
            interval="5m",
            auto_adjust=True,
            progress=False,
            group_by="column",
            threads=True,
        )
        daily = yf.download(
            tickers,
            period="10d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            group_by="column",
            threads=True,
        )
    except Exception as exc:
        return {"status": "unavailable", "themes": [], "primary": None, "alerts": [], "note": f"未確認: {exc}"}

    max_age_hours = float(config.get("max_age_hours", 30.0))
    snapshots = {
        ticker: _symbol_snapshot(ticker, label, intraday, daily, max_age_hours)
        for ticker, label in member_meta.items()
    }
    result = evaluate_theme_groups(snapshots, config)
    result["symbols"] = snapshots
    return result

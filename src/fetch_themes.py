from __future__ import annotations

import math
from datetime import datetime, time
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


def _field_series(history: pd.DataFrame, ticker: str, field: str) -> pd.Series:
    if history.empty:
        return pd.Series(dtype="float64")
    try:
        data = history[field]
    except (KeyError, TypeError):
        return pd.Series(dtype="float64")
    if isinstance(data, pd.DataFrame):
        if ticker in data.columns:
            data = data[ticker]
        elif len(data.columns) == 1:
            data = data.iloc[:, 0]
        else:
            return pd.Series(dtype="float64")
    return pd.to_numeric(data, errors="coerce").sort_index()


def _ohlcv_frame(history: pd.DataFrame, ticker: str, now: datetime | None = None) -> pd.DataFrame:
    now = now or datetime.now(JST)
    frame = pd.concat(
        {
            field.lower(): _field_series(history, ticker, field)
            for field in ["Open", "High", "Low", "Close", "Volume"]
        },
        axis=1,
    ).dropna()
    if frame.empty:
        return frame
    valid = (
        (frame[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (frame["high"] >= frame["low"])
        & (frame["volume"] >= 0)
    )
    frame = frame.loc[valid].sort_index()
    session_dates = pd.Index([pd.Timestamp(value).date() for value in frame.index])
    latest_allowed = now.time() >= time(15, 45)
    completed = session_dates <= now.date() if latest_allowed else session_dates < now.date()
    return frame.loc[completed].tail(70)


def _candle_shape(row: pd.Series) -> dict[str, float | bool]:
    candle_range = max(float(row["high"] - row["low"]), 0.000001)
    body = abs(float(row["close"] - row["open"]))
    upper_shadow = float(row["high"] - max(row["open"], row["close"]))
    lower_shadow = float(min(row["open"], row["close"]) - row["low"])
    close_location = float((row["close"] - row["low"]) / candle_range)
    reference_body = max(body, candle_range * 0.05)
    return {
        "body": body,
        "upper_shadow": upper_shadow,
        "lower_shadow": lower_shadow,
        "close_location": close_location,
        "hammer": lower_shadow >= reference_body * 2 and upper_shadow <= reference_body and close_location >= 0.55,
        "shooting_star": upper_shadow >= reference_body * 2 and lower_shadow <= reference_body and close_location <= 0.45,
    }


def evaluate_price_pattern(
    ticker: str,
    label: str,
    frame: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, Any]:
    minimum_history = int(config.get("minimum_history_days", 45))
    if len(frame) < minimum_history:
        return {"ticker": ticker, "label": label, "status": "unavailable", "signal": "未確認", "note": f"日足履歴が不足しています（{len(frame)}/{minimum_history}）"}

    latest = frame.iloc[-1]
    previous = frame.iloc[-2]
    before_previous = frame.iloc[-3]
    prior = frame.iloc[:-1]
    base_before_previous = frame.iloc[:-2]
    volume_average = float(prior["volume"].tail(20).mean())
    if not math.isfinite(volume_average) or volume_average <= 0:
        return {"ticker": ticker, "label": label, "status": "unavailable", "signal": "未確認", "note": "出来高基準を確認できません"}

    gap_threshold = float(config.get("gap_threshold_pct", 2.0))
    breakout_volume = float(config.get("breakout_volume_ratio", 1.5))
    confirmation_volume = float(config.get("confirmation_volume_ratio", 1.2))
    high_distance = float(config.get("high_zone_distance_pct", 5.0)) / 100
    low_distance = float(config.get("low_zone_distance_pct", 7.0)) / 100
    gap_pct = (float(latest["open"]) / float(previous["close"]) - 1) * 100
    volume_ratio = float(latest["volume"]) / volume_average
    latest_shape = _candle_shape(latest)
    previous_shape = _candle_shape(previous)
    prior_high20 = float(prior["high"].tail(20).max())
    prior_low20 = float(prior["low"].tail(20).min())
    prior_high60 = float(base_before_previous["high"].tail(60).max())
    prior_low60 = float(base_before_previous["low"].tail(60).min())
    previous_high_zone = float(previous["high"]) >= prior_high60 * (1 - high_distance)
    previous_low_zone = float(previous["low"]) <= prior_low60 * (1 + low_distance)
    previous_bullish_engulfing = (
        float(before_previous["close"]) < float(before_previous["open"])
        and float(previous["close"]) > float(previous["open"])
        and float(previous["open"]) <= float(before_previous["close"])
        and float(previous["close"]) >= float(before_previous["open"])
    )
    previous_bearish_engulfing = (
        float(before_previous["close"]) > float(before_previous["open"])
        and float(previous["close"]) < float(previous["open"])
        and float(previous["open"]) >= float(before_previous["close"])
        and float(previous["close"]) <= float(before_previous["open"])
    )

    signal = None
    direction = "neutral"
    score = 0
    evidence: list[str] = []
    if (
        gap_pct >= gap_threshold
        and float(latest["close"]) > float(latest["open"])
        and float(latest_shape["close_location"]) >= 0.7
        and volume_ratio >= breakout_volume
        and float(latest["close"]) > prior_high20
    ):
        signal = "上放れ継続確認"
        direction = "bull"
        score = 92
        evidence = [f"上窓{gap_pct:+.2f}%", f"20日高値更新", f"出来高{volume_ratio:.2f}倍", "終値が日中高値圏"]
    elif (
        gap_pct <= -gap_threshold
        and float(latest["close"]) < float(latest["open"])
        and float(latest_shape["close_location"]) <= 0.3
        and volume_ratio >= breakout_volume
        and float(latest["close"]) < prior_low20
    ):
        signal = "下放れ継続警戒"
        direction = "bear"
        score = 92
        evidence = [f"下窓{gap_pct:+.2f}%", "20日安値更新", f"出来高{volume_ratio:.2f}倍", "終値が日中安値圏"]
    elif (
        previous_low_zone
        and (bool(previous_shape["hammer"]) or previous_bullish_engulfing)
        and float(latest["close"]) > float(previous["high"])
        and float(latest["close"]) > float(latest["open"])
        and volume_ratio >= confirmation_volume
    ):
        signal = "底打ち反転確認"
        direction = "bull"
        score = 90
        pattern_name = "ハンマー" if previous_shape["hammer"] else "陽の包み足"
        evidence = ["60日安値圏", pattern_name, "翌日高値超え", f"出来高{volume_ratio:.2f}倍"]
    elif (
        previous_high_zone
        and (bool(previous_shape["shooting_star"]) or previous_bearish_engulfing)
        and float(latest["close"]) < float(previous["low"])
        and float(latest["close"]) < float(latest["open"])
        and volume_ratio >= confirmation_volume
    ):
        signal = "高値圏反落確認"
        direction = "bear"
        score = 90
        pattern_name = "流れ星" if previous_shape["shooting_star"] else "陰の包み足"
        evidence = ["60日高値圏", pattern_name, "翌日安値割れ", f"出来高{volume_ratio:.2f}倍"]

    as_of = pd.Timestamp(frame.index[-1]).strftime("%Y-%m-%d")
    if not signal:
        return {"ticker": ticker, "label": label, "status": "no_signal", "signal": "該当なし", "as_of": as_of}
    return {
        "ticker": ticker,
        "label": label,
        "status": "ok",
        "quality_status": "verified",
        "signal": signal,
        "direction": direction,
        "score": score,
        "gap_pct": gap_pct,
        "volume_ratio": volume_ratio,
        "evidence": evidence,
        "as_of": as_of,
        "source": "Yahoo Finance via yfinance（日足OHLCV）",
        "note": "確認度は複合条件の充足度であり、将来の勝率ではありません。",
    }


def evaluate_price_patterns(
    daily: pd.DataFrame,
    member_meta: dict[str, str],
    config: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    if not config.get("enabled", False):
        return {"status": "disabled", "candidates": [], "note": "ローソク足監視は無効です"}
    now = now or datetime.now(JST)
    results = []
    for ticker, label in member_meta.items():
        try:
            results.append(evaluate_price_pattern(ticker, label, _ohlcv_frame(daily, ticker, now), config))
        except Exception as exc:
            results.append(
                {
                    "ticker": ticker,
                    "label": label,
                    "status": "unavailable",
                    "signal": "未確認",
                    "note": f"OHLCVを検証できません: {exc}",
                }
            )
    max_age_days = int(config.get("max_age_days", 4))
    for item in results:
        if item.get("status") != "ok" or not item.get("as_of"):
            continue
        age_days = (now.date() - pd.Timestamp(item["as_of"]).date()).days
        if age_days < 0 or age_days > max_age_days:
            item.update({"status": "unavailable", "signal": "未確認", "note": f"基準日が古いため未確認です（{age_days}日前）"})
    minimum_score = int(config.get("minimum_score", 85))
    candidates = [item for item in results if item.get("status") == "ok" and int(item.get("score", 0)) >= minimum_score]
    candidates.sort(key=lambda item: (int(item.get("score", 0)), float(item.get("volume_ratio", 0))), reverse=True)
    unavailable_count = len([item for item in results if item.get("status") == "unavailable"])
    return {
        "status": "ok" if candidates else "no_signal",
        "candidates": candidates[: int(config.get("max_results", 5))],
        "scanned_count": len(results),
        "unavailable_count": unavailable_count,
        "minimum_score": minimum_score,
        "source": "Yahoo Finance via yfinance（日足OHLCV）",
        "note": "窓・高安値圏・出来高・終値位置・翌日確認を組み合わせ、単独の足型では通知しません。",
    }


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
            period="6mo",
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
    result["price_patterns"] = evaluate_price_patterns(daily, member_meta, sources.get("price_patterns", {}) or {})
    return result

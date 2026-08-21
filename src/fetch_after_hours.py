from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf


JST = ZoneInfo("Asia/Tokyo")
DEFAULT_MAX_AGE_MINUTES = 75


def _safe_change(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline in (None, 0):
        return None
    return (current / baseline - 1) * 100


def _numeric_closes(history: pd.DataFrame) -> pd.Series:
    if history.empty or "Close" not in history:
        return pd.Series(dtype="float64")
    close_data = history["Close"]
    if isinstance(close_data, pd.DataFrame):
        if close_data.empty:
            return pd.Series(dtype="float64")
        close_data = close_data.iloc[:, 0]
    values = pd.to_numeric(close_data, errors="coerce").dropna().sort_index()
    return values[values.map(lambda value: math.isfinite(float(value)) and float(value) > 0)]


def _as_jst(value: Any) -> datetime:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert(JST).to_pydatetime()


def _series_points(closes: pd.Series, limit: int = 12) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for timestamp, value in closes.tail(limit).items():
        observed = _as_jst(timestamp)
        points.append({"date": observed.isoformat(timespec="minutes"), "value": float(value)})
    return points


def _finite_positive(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) and numeric > 0 else None


def _comparison_baseline(
    ticker: str,
    kind: str,
    observed_at: datetime,
    daily_closes: pd.Series | None = None,
) -> tuple[float, str] | None:
    try:
        metadata = yf.Ticker(ticker).history_metadata or {}
        previous_close = _finite_positive(metadata.get("previousClose"))
        regular_price = _finite_positive(metadata.get("regularMarketPrice"))
        if kind == "adr" and regular_price is not None:
            timezone_name = str(metadata.get("exchangeTimezoneName") or "America/New_York")
            exchange_time = observed_at.astimezone(ZoneInfo(timezone_name)).time()
            in_regular_session = time(9, 30) <= exchange_time < time(16, 0)
            if not in_regular_session:
                return regular_price, "直近通常取引終値"
        if previous_close is not None:
            return previous_close, "前営業日終値"
    except Exception:
        pass
    if daily_closes is not None and not daily_closes.empty:
        fallback = float(daily_closes.iloc[-2] if len(daily_closes) >= 2 else daily_closes.iloc[-1])
        return fallback, "確定済み日足終値"
    return None


def _fetch_one(key: str, meta: dict[str, Any], max_age_minutes: int) -> dict[str, Any]:
    ticker = str(meta.get("ticker", key))
    label = str(meta.get("label", key))
    kind = str(meta.get("kind", "other"))
    threshold = float(meta.get("threshold_pct", 1.0))
    anomaly_limit = float(meta.get("anomaly_limit_pct", 30.0))

    try:
        intraday = yf.download(
            ticker,
            period="5d",
            interval="5m",
            prepost=True,
            auto_adjust=False,
            progress=False,
            group_by="column",
            multi_level_index=False,
            threads=False,
        )
        intraday_closes = _numeric_closes(intraday)
        if intraday_closes.empty:
            raise ValueError("時間外価格データが不足しています")

        current = float(intraday_closes.iloc[-1])
        observed_at = _as_jst(intraday_closes.index[-1])
        baseline_result = _comparison_baseline(ticker, kind, observed_at)
        if baseline_result is None:
            daily = yf.download(
                ticker,
                period="10d",
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="column",
                multi_level_index=False,
                threads=False,
            )
            baseline_result = _comparison_baseline(ticker, kind, observed_at, _numeric_closes(daily))
        if baseline_result is None:
            raise ValueError("比較基準となる前営業日終値を確認できません")
        baseline, baseline_label = baseline_result
        now = datetime.now(JST)
        age_minutes = max(0.0, (now - observed_at).total_seconds() / 60)
        if observed_at > now.replace(second=0, microsecond=0) and age_minutes == 0:
            raise ValueError("未来時刻のデータを検出しました")
        if age_minutes > max_age_minutes:
            raise ValueError(f"データが古いため未確認です（{age_minutes:.0f}分前）")

        change_pct = _safe_change(current, baseline)
        if change_pct is None or abs(change_pct) > anomaly_limit:
            raise ValueError(f"異常変動を検出しました（{change_pct}）")

        persistence_hits = 0
        recent_changes: list[float] = []
        for value in intraday_closes.tail(4):
            recent_change = _safe_change(float(value), baseline)
            if recent_change is None:
                continue
            recent_changes.append(recent_change)
            if change_pct and recent_change * change_pct > 0 and abs(recent_change) >= threshold * 0.5:
                persistence_hits += 1

        return {
            "key": key,
            "label": label,
            "ticker": ticker,
            "kind": kind,
            "current": current,
            "previous": baseline,
            "change_pct": change_pct,
            "threshold_pct": threshold,
            "series": _series_points(intraday_closes),
            "recent_changes": recent_changes,
            "persistence_hits": persistence_hits,
            "status": "ok",
            "source": "Yahoo Finance via yfinance",
            "as_of": observed_at.strftime("%Y-%m-%d %H:%M JST"),
            "age_minutes": round(age_minutes, 1),
            "quality_status": "verified",
            "quality_notes": ["5分足", f"{baseline_label}基準", f"観測遅延 {age_minutes:.0f}分"],
            "baseline_label": baseline_label,
            "comparison_group": "market_return",
            "group": meta.get("group"),
            "nikkei_link": meta.get("nikkei_link"),
        }
    except Exception as exc:
        return {
            "key": key,
            "label": label,
            "ticker": ticker,
            "kind": kind,
            "current": None,
            "previous": None,
            "change_pct": None,
            "threshold_pct": threshold,
            "series": [],
            "recent_changes": [],
            "persistence_hits": 0,
            "status": "unavailable",
            "source": "Yahoo Finance via yfinance",
            "as_of": None,
            "quality_status": "unavailable",
            "comparison_group": "market_return",
            "note": f"未確認: {exc}",
        }


def _direction(value: float | None) -> int:
    if value is None or value == 0:
        return 0
    return 1 if value > 0 else -1


def _valid(items: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    return next((item for item in items if item.get("key") == key and item.get("status") == "ok"), None)


def _same_direction_count(items: list[dict[str, Any]], keys: set[str], direction: int, minimum: float) -> int:
    return len(_same_direction_keys(items, keys, direction, minimum))


def _same_direction_keys(items: list[dict[str, Any]], keys: set[str], direction: int, minimum: float) -> set[str]:
    return {
        str(item.get("key"))
        for item in items
        if item.get("key") in keys
        and item.get("status") == "ok"
        and _direction(item.get("change_pct")) == direction
        and abs(float(item.get("change_pct", 0))) >= minimum
    }


def evaluate_after_hours_signals(
    items: list[dict[str, Any]],
    minimum_score: int = 80,
    minimum_corroborations: int = 2,
    minimum_persistence_hits: int = 2,
) -> dict[str, Any]:
    equity_keys = {"NIKKEI_FUT", "SP500_FUT", "NASDAQ100_FUT", "DOW_FUT", "RUSSELL_FUT", "SP500", "NASDAQ", "SOXX"}
    adr_keys = {"ADR_TM", "ADR_SONY", "ADR_MUFG", "ADR_SMFG", "ADR_MIZUHO", "ADR_HONDA"}
    candidates: list[dict[str, Any]] = []

    for item in items:
        change = item.get("change_pct")
        if item.get("status") != "ok" or not isinstance(change, (int, float)):
            continue
        threshold = float(item.get("threshold_pct", 1.0))
        if abs(change) < threshold:
            continue

        direction = _direction(change)
        score = 55  # 品質・鮮度を通過し、急変基準も超えた状態。
        reasons = [f"{item['label']}が基準{threshold:.1f}%を超え{change:+.2f}%"]
        contradictions: list[str] = []
        corroboration_keys: set[str] = set()
        persistence_hits = int(item.get("persistence_hits", 0))
        if persistence_hits >= 3:
            score += 20
            reasons.append("直近4観測のうち3回以上で同方向を維持")
        elif persistence_hits >= 2:
            score += 12
            reasons.append("直近観測で同方向が継続")
        else:
            contradictions.append("継続性は未確認")

        kind = str(item.get("kind", "other"))
        if item.get("key") in equity_keys:
            peer_keys = _same_direction_keys(items, equity_keys - {str(item.get("key"))}, direction, 0.35)
            peers = len(peer_keys)
            if peers >= 2:
                score += 20
                reasons.append(f"他の株価先物{peers}本も同方向")
                corroboration_keys.update(peer_keys)
            elif peers == 1:
                score += 10
                reasons.append("他の株価先物1本が同方向")
                corroboration_keys.update(peer_keys)
            else:
                contradictions.append("他の主要先物の追随は未確認")

            vix = _valid(items, "VIX")
            vix_change = vix.get("change_pct") if vix else None
            if isinstance(vix_change, (int, float)) and abs(vix_change) >= 3 and _direction(vix_change) == -direction:
                score += 10
                reasons.append("VIXも株価先物と整合")
                corroboration_keys.add("VIX")
            elif isinstance(vix_change, (int, float)) and abs(vix_change) >= 3 and _direction(vix_change) == direction:
                score -= 8
                contradictions.append("VIXの方向が株価先物と不一致")

            if item.get("key") == "NIKKEI_FUT":
                aligned_adr_keys = _same_direction_keys(items, adr_keys, direction, 1.0)
                adr_breadth = len(aligned_adr_keys)
                if adr_breadth >= 2:
                    score += 10
                    reasons.append(f"日本株ADR {adr_breadth}銘柄も同方向")
                    corroboration_keys.update(aligned_adr_keys)

        elif item.get("key") == "VIX":
            opposite_future_keys = _same_direction_keys(items, equity_keys, -direction, 0.35)
            opposite_futures = len(opposite_future_keys)
            if opposite_futures >= 2:
                score += 20
                reasons.append(f"株価先物{opposite_futures}本が逆方向で整合")
                corroboration_keys.update(opposite_future_keys)
            else:
                contradictions.append("株価先物との整合は弱い")
        elif kind == "adr":
            aligned_adr_keys = _same_direction_keys(items, adr_keys - {str(item.get("key"))}, direction, 1.0)
            adr_breadth = len(aligned_adr_keys)
            nikkei = _valid(items, "NIKKEI_FUT")
            if adr_breadth >= 2:
                score += 15
                reasons.append(f"他の日本株ADR {adr_breadth}銘柄も同方向")
                corroboration_keys.update(aligned_adr_keys)
            if nikkei and _direction(nikkei.get("change_pct")) == direction and abs(float(nikkei.get("change_pct", 0))) >= 0.5:
                score += 10
                reasons.append("日経先物も同方向")
                corroboration_keys.add("NIKKEI_FUT")
            if adr_breadth == 0:
                contradictions.append("他の日本株ADRの追随は未確認")
        elif kind == "us_stock":
            group = str(item.get("group") or "")
            peer_keys = {
                str(peer.get("key"))
                for peer in items
                if peer.get("kind") == "us_stock"
                and peer.get("key") != item.get("key")
                and str(peer.get("group") or "") == group
                and peer.get("status") == "ok"
                and _direction(peer.get("change_pct")) == direction
                and abs(float(peer.get("change_pct", 0))) >= 1.0
            }
            if peer_keys:
                score += min(15, 5 + len(peer_keys) * 5)
                reasons.append(f"同業・関連大型株{len(peer_keys)}銘柄も同方向")
                corroboration_keys.update(peer_keys)

            index_keys = {"NASDAQ", "SP500"}
            if group == "semiconductor":
                index_keys.add("SOXX")
            aligned_indexes = _same_direction_keys(items, index_keys, direction, 0.35)
            if aligned_indexes:
                score += 10
                reasons.append("米国指数・業種指数も同方向")
                corroboration_keys.update(aligned_indexes)

            nikkei = _valid(items, "NIKKEI_FUT")
            if nikkei and _direction(nikkei.get("change_pct")) == direction and abs(float(nikkei.get("change_pct", 0))) >= 0.35:
                score += 10
                reasons.append("日経先物も同方向")
                corroboration_keys.add("NIKKEI_FUT")
            nikkei_link = str(item.get("nikkei_link") or "")
            if nikkei_link:
                reasons.append(f"日経関連: {nikkei_link}")
            if not peer_keys and not aligned_indexes:
                contradictions.append("同業株・指数の追随は未確認")
        elif kind == "fx":
            nikkei = _valid(items, "NIKKEI_FUT")
            if nikkei and _direction(nikkei.get("change_pct")) == direction and abs(float(nikkei.get("change_pct", 0))) >= 0.5:
                score += 15
                reasons.append("日経先物も同方向")
                corroboration_keys.add("NIKKEI_FUT")
            else:
                contradictions.append("日本株先物との方向一致は未確認")
        elif kind == "commodity":
            if abs(change) >= threshold * 2:
                score += 15
                reasons.append("通常の通知基準の2倍を超える変動")
            opposite_equity_keys = _same_direction_keys(items, equity_keys, -direction, 0.35)
            equities_opposite = len(opposite_equity_keys)
            if item.get("key") == "GOLD" and equities_opposite >= 2:
                score += 10
                reasons.append("株価先物と逆方向でリスク回避の動きが整合")
                corroboration_keys.update(opposite_equity_keys)

        score = max(0, min(100, score))
        persistence_confirmed = persistence_hits >= minimum_persistence_hits
        corroboration_count = len(corroboration_keys)
        eligible = score >= minimum_score and persistence_confirmed and corroboration_count >= minimum_corroborations
        candidates.append(
            {
                "key": item.get("key"),
                "label": item.get("label"),
                "change_pct": float(change),
                "score": score,
                "eligible": eligible,
                "persistence_hits": persistence_hits,
                "corroboration_count": corroboration_count,
                "corroboration_keys": sorted(corroboration_keys),
                "reasons": reasons,
                "contradictions": contradictions,
                "as_of": item.get("as_of"),
                "source": item.get("source"),
            }
        )

    candidates.sort(key=lambda signal: (signal["score"], abs(signal["change_pct"])), reverse=True)
    eligible_candidates = [candidate for candidate in candidates if candidate["eligible"]]
    primary = eligible_candidates[0] if eligible_candidates else candidates[0] if candidates else None
    triggered = bool(eligible_candidates)
    if not primary:
        note = "通知基準を超える変動は確認されませんでした"
    elif not triggered:
        note = f"{primary['label']}は急変基準を超えましたが、継続性または独立した確認材料が不足しています"
    else:
        note = f"{primary['label']}の急変を複数条件で確認しました"

    return {
        "triggered": triggered,
        "primary": primary,
        "candidates": candidates[:5],
        "confirmation_label": "高" if triggered else "不足",
        "note": note,
        "minimum_score": minimum_score,
        "minimum_corroborations": minimum_corroborations,
        "minimum_persistence_hits": minimum_persistence_hits,
        "disclaimer": "通知は急変基準、継続性、独立した確認材料2件以上、総合点をすべて満たす場合だけ行います。確認度は勝率ではありません。",
    }


def fetch_after_hours_snapshot(
    task_id: str,
    task_config: dict[str, Any],
    sources: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    del rules
    source_key = str(task_config.get("source_key", "after_hours"))
    source_config = sources.get(source_key, {}) or {}
    symbols = source_config.get("symbols", {}) or {}
    max_age_minutes = int(source_config.get("max_age_minutes", DEFAULT_MAX_AGE_MINUTES))
    selected_keys = task_config.get("chart_symbols") or list(symbols)
    items_by_key: dict[str, dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=min(6, max(1, len(selected_keys)))) as executor:
        futures = {
            executor.submit(_fetch_one, key, symbols.get(key, {}), max_age_minutes): key
            for key in selected_keys
            if key in symbols
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                items_by_key[key] = future.result()
            except Exception as exc:
                meta = symbols.get(key, {})
                items_by_key[key] = {
                    "key": key,
                    "label": meta.get("label", key),
                    "status": "unavailable",
                    "quality_status": "unavailable",
                    "change_pct": None,
                    "series": [],
                    "note": f"未確認: {exc}",
                }

    items = [items_by_key[key] for key in selected_keys if key in items_by_key]
    alert = evaluate_after_hours_signals(
        items,
        minimum_score=int(source_config.get("minimum_score", 80)),
        minimum_corroborations=int(source_config.get("minimum_corroborations", 2)),
        minimum_persistence_hits=int(source_config.get("minimum_persistence_hits", 2)),
    )
    return {
        "task_id": task_id,
        "section": "after_hours",
        "series_mode": "intraday",
        "items": items,
        "macro_items": [],
        "highlights": {
            "analysis": alert["note"],
            "signal_reliability": alert["disclaimer"],
        },
        "alert": alert,
    }

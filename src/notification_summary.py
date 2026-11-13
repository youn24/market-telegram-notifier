from __future__ import annotations

from math import isfinite
from typing import Any


AI_LABEL_PRIORITY = ("根拠:", "注視:", "反証:", "回避:")
SKIP_LABELS = ("結論:", "未確認:")


def build_market_comparison(raw_data: dict[str, Any]) -> tuple[str, str] | None:
    """Compare related markets only when their observation labels match."""
    items = {
        item.get("key"): item
        for item in raw_data.get("items", [])
        if item.get("status") == "ok" and item.get("quality_status") not in {"stale", "unavailable"}
    }
    pairs = (
        ("NIKKEI225", "TOPIX"),
        ("NASDAQ", "SP500"),
        ("NASDAQ100_FUT", "SP500_FUT"),
    )
    for left_key, right_key in pairs:
        left, right = items.get(left_key), items.get(right_key)
        if not left or not right or not left.get("as_of") or left["as_of"] != right.get("as_of"):
            continue
        a, b = left.get("change_pct"), right.get("change_pct")
        if not all(isinstance(value, (int, float)) and isfinite(value) for value in (a, b)):
            continue
        left_label, right_label = left["label"], right["label"]
        gap = a - b
        evidence = f"{left_label} {a:+.2f}%／{right_label} {b:+.2f}%（差 {gap:+.2f}pt）"
        if a * b < 0:
            watch = f"{left_label}と{right_label}は逆方向。次の観測で同方向にそろうか確認。"
        elif abs(gap) >= 0.5:
            weaker = right_label if gap > 0 else left_label
            watch = f"{weaker}が追いつくか、強い側が失速して差が縮むかを確認。"
        elif a < 0 and b < 0:
            watch = "両方が前日基準を回復するか確認。片方だけの反発なら見方を保留。"
        elif a > 0 and b > 0:
            watch = "両方が上昇を維持するか確認。片方がマイナスに転じたら見直し。"
        else:
            watch = "次の観測で両方の方向がそろうか確認。"
        return evidence, watch
    return None


def _clean_line(value: Any, max_chars: int) -> str:
    text = " ".join(str(value).strip().strip("-・* ").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def build_notification_analysis_lines(
    summary: dict[str, Any],
    limit: int = 3,
    max_chars: int = 82,
) -> list[str]:
    """Return a compact, fact-based analysis block for Telegram."""
    if limit <= 0:
        return []

    ai_lines = summary.get("ai_summary") or []
    if ai_lines:
        raw_lines = [
            line
            for label in AI_LABEL_PRIORITY
            for line in ai_lines
            if str(line).strip().startswith(label)
        ]
        raw_lines.extend(
            line
            for line in ai_lines
            if not str(line).strip().startswith((*AI_LABEL_PRIORITY, *SKIP_LABELS))
        )
    else:
        commentary = list(summary.get("commentary") or summary.get("deep_summary_lines") or [])
        scenarios = list(summary.get("scenarios") or [])
        continuation = next((line for line in scenarios if str(line).startswith(("継続:", "注視:"))), "")
        invalidation = next((line for line in scenarios if str(line).startswith(("反証:", "回避:"))), "")
        raw_lines = []
        conclusion_source = " ".join(str(summary.get("conclusion_text", "")).split())
        evidence_index = next(
            (
                index
                for index, line in enumerate(commentary)
                if " ".join(str(line).strip().strip("-・* ").split()) != conclusion_source
            ),
            None,
        )
        evidence_source = commentary[evidence_index] if evidence_index is not None else ""
        evidence_normalized = " ".join(str(evidence_source).strip().strip("-・* ").split())
        if evidence_source:
            evidence = str(evidence_source).strip().strip("-・* ")
            raw_lines.append(evidence if evidence.startswith("根拠:") else f"根拠: {evidence}")
        if continuation:
            raw_lines.append(str(continuation).replace("継続:", "注視:", 1))
        elif evidence_index is not None:
            watch_source = next(
                (
                    line
                    for line in commentary[evidence_index + 1 :]
                    if " ".join(str(line).strip().strip("-・* ").split()) != evidence_normalized
                ),
                "",
            )
            watch = str(watch_source).strip().strip("-・* ")
            if watch:
                raw_lines.append(watch if watch.startswith("注視:") else f"注視: {watch}")
        if invalidation:
            raw_lines.append(str(invalidation).replace("回避:", "反証:", 1))

    conclusion = _clean_line(summary.get("conclusion_text", ""), max_chars)
    result: list[str] = []
    seen: set[str] = set()
    for value in raw_lines:
        line = _clean_line(value, max_chars)
        if not line or line == conclusion or line in seen:
            continue
        seen.add(line)
        result.append(line)
        if len(result) >= limit:
            break
    return result

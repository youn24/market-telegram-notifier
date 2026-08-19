from __future__ import annotations

from typing import Any


AI_LABEL_PRIORITY = ("根拠:", "注視:", "回避:")
SKIP_LABELS = ("結論:", "未確認:")


def _clean_line(value: Any, max_chars: int) -> str:
    text = " ".join(str(value).strip().strip("-・* ").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def build_notification_analysis_lines(
    summary: dict[str, Any],
    limit: int = 2,
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
        raw_lines = summary.get("commentary") or summary.get("deep_summary_lines") or []

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

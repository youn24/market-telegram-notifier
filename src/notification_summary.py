from __future__ import annotations

from typing import Any


AI_LABEL_PRIORITY = ("根拠:", "注視:", "反証:", "回避:")
SKIP_LABELS = ("結論:", "未確認:")


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

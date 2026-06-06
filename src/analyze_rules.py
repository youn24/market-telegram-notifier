from __future__ import annotations

from datetime import datetime
from typing import Any


def _format_number(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "未確認"
    return f"{value:,.{digits}f}"


def _format_pct(value: float | None) -> str:
    if value is None:
        return "未確認"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _classify_change(change_pct: float | None, thresholds: dict[str, Any]) -> str:
    if change_pct is None:
        return "未確認"

    if change_pct >= thresholds.get("strong_up_pct", 1.0):
        return "強めの上昇"
    if change_pct >= thresholds.get("moderate_up_pct", 0.3):
        return "小幅高"
    if change_pct <= thresholds.get("strong_down_pct", -1.0):
        return "強めの下落"
    if change_pct <= thresholds.get("moderate_down_pct", -0.3):
        return "小幅安"
    return "横ばい圏"


def build_summary(
    task_id: str,
    task_config: dict[str, Any],
    raw_data: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    thresholds = rules.get("thresholds", {})
    default_no_signal = rules.get("messages", {}).get("no_signal", "目立ったシグナルは未確認")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: list[str] = []
    signal_lines: list[str] = []

    for item in raw_data.get("items", []):
        line = (
            f"- {item['label']}: "
            f"{_format_number(item.get('current'))} "
            f"({ _format_pct(item.get('change_pct')) })"
        )
        lines.append(line)

        signal = _classify_change(item.get("change_pct"), thresholds)
        signal_lines.append(f"- {item['label']}: {signal}")

    for label, note in raw_data.get("highlights", {}).items():
        pretty = {
            "speculative_positions": "投機筋",
            "earnings": "決算",
            "ratings": "信用評価",
            "supply_demand": "需給",
            "analysis": "分析",
        }.get(label, label)
        lines.append(f"- {pretty}: {note}")

    if not raw_data.get("items"):
        signal_lines.append(f"- {default_no_signal}")

    body = "\n".join(
        [
            "主要項目",
            *lines,
            "",
            "簡易シグナル",
            *signal_lines,
        ]
    )

    return {
        "generated_at": generated_at,
        "body": body,
        "signals": signal_lines,
        "metrics": lines,
    }

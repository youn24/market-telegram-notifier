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


def _speaker_profile(task_id: str, task_config: dict[str, Any]) -> tuple[str, str]:
    category = task_config.get("category", "")
    if category == "fx":
        return "ゾウAI", "為替の流れを先に読む"
    if category == "japan_market":
        return "カワウソAI", "日本株の地合いをすばやく整理"
    return "マーケットAI", "市況をコンパクトに要約"


def _market_tone(raw_data: dict[str, Any], thresholds: dict[str, Any]) -> str:
    change_values = [item.get("change_pct") for item in raw_data.get("items", []) if item.get("change_pct") is not None]
    if not change_values:
        return "neutral"

    average_change = sum(change_values) / len(change_values)
    if average_change >= thresholds.get("moderate_up_pct", 0.3):
        return "bull"
    if average_change <= thresholds.get("moderate_down_pct", -0.3):
        return "bear"
    return "neutral"


def _build_commentary(
    task_id: str,
    task_config: dict[str, Any],
    raw_data: dict[str, Any],
    thresholds: dict[str, Any],
) -> list[str]:
    comments: list[str] = []
    positive_items = [item for item in raw_data.get("items", []) if (item.get("change_pct") or 0) >= thresholds.get("moderate_up_pct", 0.3)]
    negative_items = [item for item in raw_data.get("items", []) if (item.get("change_pct") or 0) <= thresholds.get("moderate_down_pct", -0.3)]
    tone = _market_tone(raw_data, thresholds)

    if tone == "bull" and positive_items:
        joined = "、".join(item["label"] for item in positive_items[:3])
        comments.append(f"{joined}がしっかりしていて、買いが入りやすい地合いです。")
    if tone == "bear" and negative_items:
        joined = "、".join(item["label"] for item in negative_items[:3])
        comments.append(f"{joined}は弱めなので、追いかけ買いは少し慎重に見たいです。")
    if tone == "neutral":
        comments.append("強弱がまだ混ざっていて、飛びつくより見極めを優先したい場面です。")

    unavailable_labels = []
    for label, note in raw_data.get("highlights", {}).items():
        if "未確認" in str(note):
            pretty = {
                "speculative_positions": "投機筋",
                "earnings": "決算",
                "ratings": "信用評価",
                "supply_demand": "需給",
                "analysis": "分析",
            }.get(label, label)
            unavailable_labels.append(pretty)
    if unavailable_labels:
        comments.append(f"{'、'.join(unavailable_labels)}は未確認なので、ここは断定せずに進めます。")

    if not comments:
        comments.append("大きな偏りはまだ薄く、初動の勢いと押し目の質を見たい場面です。")

    return comments[:3]


def build_summary(
    task_id: str,
    task_config: dict[str, Any],
    raw_data: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    thresholds = rules.get("thresholds", {})
    default_no_signal = rules.get("messages", {}).get("no_signal", "目立ったシグナルは未確認")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    speaker_name, speaker_role = _speaker_profile(task_id, task_config)
    tone = _market_tone(raw_data, thresholds)

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

    commentary = _build_commentary(task_id, task_config, raw_data, thresholds)

    return {
        "generated_at": generated_at,
        "body": body,
        "signals": signal_lines,
        "metrics": lines,
        "speaker_name": speaker_name,
        "speaker_role": speaker_role,
        "commentary": commentary,
        "market_tone": tone,
    }

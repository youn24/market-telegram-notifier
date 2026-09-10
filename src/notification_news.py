from __future__ import annotations

from typing import Any


def _clip(value: Any, max_chars: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def build_notification_news_lines(research: dict[str, Any]) -> list[str]:
    """Return one compact, attributed headline for the notification header."""
    items = research.get("items", []) if isinstance(research, dict) else []
    item = next(
        (
            candidate
            for candidate in items
            if candidate.get("status") == "ok"
            and str(candidate.get("title", "")).strip() not in {"", "未確認"}
        ),
        None,
    )
    if item is None:
        return ["話題: 市場材料は未確認", "材料ニュース: 取得できた公開見出しなし"]

    categories = [str(value).strip() for value in item.get("material_categories", []) if str(value).strip()]
    keywords = [str(value).strip() for value in item.get("matched_keywords", []) if str(value).strip()]
    topic = categories[0] if categories else keywords[0] if keywords else "市場材料"
    title = _clip(item.get("title"), 72)
    source = _clip(item.get("source") or "媒体未確認", 24)
    published = _clip(item.get("published") or "日時未確認", 20)
    return [f"話題: {_clip(topic, 24)}", f"材料ニュース: {title}（{source} / {published}）"]

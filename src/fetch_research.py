from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import requests


def _google_news_url(query: str, language: str, region: str) -> str:
    params = urlencode({"q": query, "hl": language, "gl": region, "ceid": f"{region}:{language.split('-')[0]}"})
    return f"https://news.google.com/rss/search?{params}"


def _format_published(value: str | None) -> str:
    if not value:
        return "日時未確認"
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return "日時未確認"


def _item_text(node: ET.Element, name: str) -> str:
    child = node.find(name)
    return (child.text or "").strip() if child is not None else ""


def _fetch_google_news(query: str, sources: dict[str, Any]) -> list[dict[str, Any]]:
    research_config = sources.get("research", {})
    language = str(research_config.get("language", "ja-JP"))
    region = str(research_config.get("region", "JP"))
    max_items = int(research_config.get("max_items_per_query", 3))

    response = requests.get(
        _google_news_url(query, language, region),
        headers={"User-Agent": "market-telegram-notifier/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)

    items: list[dict[str, Any]] = []
    for node in root.findall(".//item")[:max_items]:
        source_node = node.find("source")
        items.append(
            {
                "query": query,
                "title": _item_text(node, "title") or "未確認",
                "url": _item_text(node, "link"),
                "published": _format_published(_item_text(node, "pubDate")),
                "source": (source_node.text or "Google News").strip() if source_node is not None else "Google News",
                "status": "ok",
            }
        )
    return items


def _queries_for_task(task_config: dict[str, Any], sources: dict[str, Any]) -> list[str]:
    explicit = task_config.get("research_queries")
    if explicit:
        return [str(query) for query in explicit if str(query).strip()]

    research_config = sources.get("research", {})
    default_queries = research_config.get("default_queries", {})
    if task_config.get("focus") == "macro":
        return list(default_queries.get("macro", []))

    category = str(task_config.get("category", "default"))
    return list(default_queries.get(category, default_queries.get("default", [])))


def fetch_research_snapshot(
    task_id: str,
    task_config: dict[str, Any],
    sources: dict[str, Any],
) -> dict[str, Any]:
    queries = _queries_for_task(task_config, sources)
    if not queries:
        return {
            "status": "unavailable",
            "checked_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "items": [],
            "note": "検索クエリが未設定のため未確認",
        }

    items: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_titles: set[str] = set()

    for query in queries:
        try:
            for item in _fetch_google_news(query, sources):
                title = item.get("title", "")
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                items.append(item)
        except Exception as exc:
            errors.append(f"{query}: {exc}")

    max_total = int(sources.get("research", {}).get("max_total_items", 8))
    items = items[:max_total]

    if not items:
        return {
            "status": "unavailable",
            "checked_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "items": [],
            "note": "ニュース検索は未確認: " + (" / ".join(errors[:2]) if errors else "取得なし"),
        }

    return {
        "status": "ok",
        "checked_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "items": items,
        "note": "Google News RSSで検索。ヘッドラインは材料確認用で、数値は推測しません。",
    }

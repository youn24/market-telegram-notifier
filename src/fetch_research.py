from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import requests


def _task_research_key(task_config: dict[str, Any]) -> str:
    if task_config.get("focus") == "macro":
        return "macro"
    return str(task_config.get("category", "default"))


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


def _parse_published(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _item_text(node: ET.Element, name: str) -> str:
    child = node.find(name)
    return (child.text or "").strip() if child is not None else ""


def _fetch_google_news(query: str, sources: dict[str, Any]) -> list[dict[str, Any]]:
    research_config = sources.get("research", {})
    language = str(research_config.get("language", "ja-JP"))
    region = str(research_config.get("region", "JP"))
    max_items = int(research_config.get("max_items_per_query", 3))
    window_days = int(research_config.get("search_window_days", 3))
    search_query = f"{query} when:{max(1, window_days)}d"

    response = requests.get(
        _google_news_url(search_query, language, region),
        headers={"User-Agent": "market-telegram-notifier/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)

    items: list[dict[str, Any]] = []
    for node in root.findall(".//item")[:max_items]:
        source_node = node.find("source")
        pub_date = _item_text(node, "pubDate")
        parsed_published = _parse_published(pub_date)
        items.append(
            {
                "query": query,
                "search_query": search_query,
                "title": _item_text(node, "title") or "未確認",
                "url": _item_text(node, "link"),
                "published": _format_published(pub_date),
                "published_ts": parsed_published.isoformat() if parsed_published else "",
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


def _keyword_list(task_config: dict[str, Any], sources: dict[str, Any]) -> list[str]:
    research_config = sources.get("research", {})
    keyword_map = research_config.get("importance_keywords", {})
    category_key = _task_research_key(task_config)
    keywords = keyword_map.get(category_key, keyword_map.get("default", []))
    return [str(keyword) for keyword in keywords if str(keyword).strip()]


def _freshness_score(item: dict[str, Any], half_life_hours: float) -> float:
    published_ts = item.get("published_ts")
    if not published_ts:
        return 0.0
    try:
        published = datetime.fromisoformat(str(published_ts))
    except ValueError:
        return 0.0

    age_hours = max(0.0, (datetime.now(timezone.utc) - published).total_seconds() / 3600)
    item["age_hours"] = round(age_hours, 1)
    return max(0.0, 30.0 * (0.5 ** (age_hours / max(1.0, half_life_hours))))


def _score_item(item: dict[str, Any], keywords: list[str], half_life_hours: float) -> dict[str, Any]:
    title = str(item.get("title", ""))
    query_terms = [term for term in str(item.get("query", "")).replace("　", " ").split(" ") if term]
    matched_keywords = [keyword for keyword in keywords if keyword.lower() in title.lower()]
    matched_query_terms = [term for term in query_terms if term.lower() in title.lower()]
    source = str(item.get("source", ""))

    score = 0.0
    score += min(45.0, len(matched_keywords) * 12.0)
    score += min(15.0, len(matched_query_terms) * 3.0)
    score += _freshness_score(item, half_life_hours)
    age_hours = item.get("age_hours")
    if isinstance(age_hours, (int, float)):
        if age_hours > 168:
            score -= 55.0
        elif age_hours > 96:
            score -= 35.0
        elif age_hours > 48:
            score -= 15.0
    if source and source != "Google News":
        score += 5.0

    item["score"] = round(max(0.0, score), 1)
    item["matched_keywords"] = matched_keywords[:5]
    item["research_reason"] = " / ".join(
        [
            f"重要語:{'、'.join(matched_keywords[:3])}" if matched_keywords else "重要語:少なめ",
            f"鮮度:{item.get('age_hours', '未確認')}時間前" if item.get("age_hours") is not None else "鮮度:未確認",
        ]
    )
    return item


def _rank_items(items: list[dict[str, Any]], task_config: dict[str, Any], sources: dict[str, Any]) -> list[dict[str, Any]]:
    research_config = sources.get("research", {})
    keywords = _keyword_list(task_config, sources)
    half_life_hours = float(research_config.get("freshness_half_life_hours", 18))
    max_age_hours = float(research_config.get("max_age_hours", 96))
    scored = [_score_item(item, keywords, half_life_hours) for item in items]
    fresh_items = [item for item in scored if item.get("age_hours") is None or item.get("age_hours", 0) <= max_age_hours]
    ranked_source = fresh_items if len(fresh_items) >= min(3, len(scored)) else scored
    return sorted(ranked_source, key=lambda item: item.get("score", 0), reverse=True)


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
    items = _rank_items(items, task_config, sources)[:max_total]

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
        "top_keywords": _keyword_list(task_config, sources)[:8],
        "note": "Google News RSSで検索。ヘッドラインは材料確認用で、数値は推測しません。",
    }

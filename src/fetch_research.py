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


def _contains_any(text: str, patterns: list[str]) -> list[str]:
    lowered = text.lower()
    return [pattern for pattern in patterns if pattern.lower() in lowered]


def _material_categories(title: str, sources: dict[str, Any]) -> list[str]:
    category_map = sources.get("research", {}).get("material_categories", {})
    categories: list[str] = []
    for category, keywords in category_map.items():
        if _contains_any(title, [str(keyword) for keyword in keywords]):
            categories.append(str(category))
    return categories[:3]


def _source_quality(source: str, sources: dict[str, Any]) -> tuple[float, str]:
    preferred_sources = [str(value) for value in sources.get("research", {}).get("preferred_sources", [])]
    if any(preferred.lower() in source.lower() for preferred in preferred_sources):
        return 12.0, "優先媒体"
    if source and source != "Google News":
        return 5.0, "一般媒体"
    return 0.0, "媒体未確認"


def _noise_penalty(title: str, sources: dict[str, Any]) -> tuple[float, list[str]]:
    research_config = sources.get("research", {})
    patterns = [str(value) for value in research_config.get("penalized_title_patterns", [])]
    matched = _contains_any(title, patterns)
    return min(30.0, len(matched) * 10.0), matched[:3]


def _is_excluded_title(title: str, sources: dict[str, Any]) -> bool:
    patterns = [str(value) for value in sources.get("research", {}).get("excluded_title_patterns", [])]
    return bool(_contains_any(title, patterns))


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


def _score_item(item: dict[str, Any], keywords: list[str], half_life_hours: float, sources: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title", ""))
    query_terms = [term for term in str(item.get("query", "")).replace("　", " ").split(" ") if term]
    matched_keywords = [keyword for keyword in keywords if keyword.lower() in title.lower()]
    matched_query_terms = [term for term in query_terms if term.lower() in title.lower()]
    source = str(item.get("source", ""))
    source_bonus, source_reason = _source_quality(source, sources)
    noise_penalty, noise_patterns = _noise_penalty(title, sources)
    categories = _material_categories(title, sources)

    score = 0.0
    score += min(45.0, len(matched_keywords) * 12.0)
    score += min(15.0, len(matched_query_terms) * 3.0)
    score += _freshness_score(item, half_life_hours)
    score += source_bonus
    score -= noise_penalty
    age_hours = item.get("age_hours")
    if isinstance(age_hours, (int, float)):
        if age_hours > 168:
            score -= 55.0
        elif age_hours > 96:
            score -= 35.0
        elif age_hours > 48:
            score -= 15.0

    item["score"] = round(max(0.0, score), 1)
    item["matched_keywords"] = matched_keywords[:5]
    item["material_categories"] = categories
    item["source_quality"] = source_reason
    item["noise_patterns"] = noise_patterns
    item["research_reason"] = " / ".join(
        [
            f"重要語:{'、'.join(matched_keywords[:3])}" if matched_keywords else "重要語:少なめ",
            f"分類:{'、'.join(categories)}" if categories else "分類:未分類",
            f"鮮度:{item.get('age_hours', '未確認')}時間前" if item.get("age_hours") is not None else "鮮度:未確認",
            f"媒体:{source_reason}",
            f"減点:{'、'.join(noise_patterns)}" if noise_patterns else "減点なし",
        ]
    )
    return item


def _rank_items(items: list[dict[str, Any]], task_config: dict[str, Any], sources: dict[str, Any]) -> list[dict[str, Any]]:
    research_config = sources.get("research", {})
    keywords = _keyword_list(task_config, sources)
    half_life_hours = float(research_config.get("freshness_half_life_hours", 18))
    max_age_hours = float(research_config.get("max_age_hours", 96))
    scored = [
        _score_item(item, keywords, half_life_hours, sources)
        for item in items
        if not _is_excluded_title(str(item.get("title", "")), sources)
    ]
    fresh_items = [item for item in scored if item.get("age_hours") is None or item.get("age_hours", 0) <= max_age_hours]
    ranked_source = fresh_items if len(fresh_items) >= min(3, len(scored)) else scored
    return sorted(ranked_source, key=lambda item: item.get("score", 0), reverse=True)


def _select_diverse_items(ranked_items: list[dict[str, Any]], sources: dict[str, Any], max_total: int) -> list[dict[str, Any]]:
    research_config = sources.get("research", {})
    max_per_source = int(research_config.get("max_items_per_source", 2))
    prefer_category_diversity = bool(research_config.get("prefer_category_diversity", True))
    min_score = float(research_config.get("min_score", 20))
    high_quality_items = [item for item in ranked_items if float(item.get("score", 0)) >= min_score]
    candidate_items = high_quality_items if len(high_quality_items) >= min(3, max_total) else ranked_items

    selected: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    selected_categories: set[str] = set()

    def can_take(item: dict[str, Any]) -> bool:
        source = str(item.get("source", "媒体未確認"))
        return source_counts.get(source, 0) < max_per_source

    def take(item: dict[str, Any]) -> None:
        source = str(item.get("source", "媒体未確認"))
        source_counts[source] = source_counts.get(source, 0) + 1
        for category in item.get("material_categories", []):
            selected_categories.add(str(category))
        selected.append(item)

    if prefer_category_diversity:
        for item in candidate_items:
            categories = {str(category) for category in item.get("material_categories", [])}
            if categories and categories.isdisjoint(selected_categories) and can_take(item):
                take(item)
                if len(selected) >= max_total:
                    return selected

    for item in candidate_items:
        if item in selected:
            continue
        if can_take(item):
            take(item)
        if len(selected) >= max_total:
            break

    if len(selected) < min(max_total, len(candidate_items)):
        for item in candidate_items:
            if item not in selected:
                selected.append(item)
            if len(selected) >= max_total:
                break

    return selected[:max_total]


def _research_confidence(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {"label": "低", "score": 0, "reason": "検索材料が未確認"}

    sources = {item.get("source") for item in items if item.get("source")}
    categories = {category for item in items for category in item.get("material_categories", [])}
    fresh_count = len([item for item in items if isinstance(item.get("age_hours"), (int, float)) and item["age_hours"] <= 24])
    preferred_count = len([item for item in items if item.get("source_quality") == "優先媒体"])
    average_score = sum(float(item.get("score", 0)) for item in items) / max(1, len(items))

    confidence_score = 0
    confidence_score += min(35, len(items) * 4)
    confidence_score += min(25, len(sources) * 5)
    confidence_score += min(20, len(categories) * 5)
    confidence_score += min(10, fresh_count * 3)
    confidence_score += min(10, preferred_count * 2)
    if average_score >= 45:
        confidence_score += 10
    elif average_score < 25:
        confidence_score -= 10

    if confidence_score >= 70:
        label = "高"
    elif confidence_score >= 45:
        label = "中"
    else:
        label = "低"

    return {
        "label": label,
        "score": max(0, min(100, round(confidence_score))),
        "reason": f"材料{len(items)}件 / 媒体{len(sources)}種 / 分類{len(categories)}種 / 24時間内{fresh_count}件",
    }


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
    ranked_items = _rank_items(items, task_config, sources)
    items = _select_diverse_items(ranked_items, sources, max_total)

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
        "confidence": _research_confidence(items),
        "top_keywords": _keyword_list(task_config, sources)[:8],
        "note": "Google News RSSで検索。ヘッドラインは材料確認用で、数値は推測しません。",
    }

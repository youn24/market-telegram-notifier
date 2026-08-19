from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests


JST = ZoneInfo("Asia/Tokyo")
ATOM = "http://www.w3.org/2005/Atom"
YOUTUBE = "http://www.youtube.com/xml/schemas/2015"
CHANNEL_ID_PATTERN = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
RELATIVE_AGE_PATTERNS = (
    re.compile(r"(\d+)\s*(分|時間|日|週間|週|か月|ヶ月|月|年)前"),
    re.compile(r"(\d+)\s*(minute|hour|day|week|month|year)s?\s+ago", re.IGNORECASE),
)


def _published_at(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("公開日時のタイムゾーンを確認できません")
    return parsed.astimezone(JST)


def classify_youtube_topics(title: str, topic_keywords: dict[str, Any] | None = None) -> list[str]:
    matched: list[str] = []
    normalized_title = title.casefold()
    for label, keywords in (topic_keywords or {}).items():
        if any(str(keyword).casefold() in normalized_title for keyword in keywords or []):
            matched.append(str(label))
        if len(matched) >= 3:
            break
    return matched


def _extract_initial_data(html_text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for marker in ("var ytInitialData = ", "window[\"ytInitialData\"] = "):
        start = html_text.find(marker)
        if start < 0:
            continue
        try:
            data, _ = decoder.raw_decode(html_text[start + len(marker) :].lstrip())
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return {}


def _walk_lockups(value: Any):
    if isinstance(value, dict):
        lockup = value.get("lockupViewModel")
        if isinstance(lockup, dict):
            yield lockup
        for child in value.values():
            yield from _walk_lockups(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_lockups(child)


def _find_video_grid(value: Any) -> list[Any] | None:
    if isinstance(value, dict):
        grid = value.get("richGridRenderer")
        if isinstance(grid, dict) and isinstance(grid.get("contents"), list):
            return grid["contents"]
        for child in value.values():
            found = _find_video_grid(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_video_grid(child)
            if found is not None:
                return found
    return None


def _relative_age_upper_hours(text: str) -> float | None:
    unit_hours = {
        "分": 1 / 60,
        "時間": 1,
        "日": 24,
        "週間": 24 * 7,
        "週": 24 * 7,
        "か月": 24 * 31,
        "ヶ月": 24 * 31,
        "月": 24 * 31,
        "年": 24 * 366,
        "minute": 1 / 60,
        "hour": 1,
        "day": 24,
        "week": 24 * 7,
        "month": 24 * 31,
        "year": 24 * 366,
    }
    for pattern in RELATIVE_AGE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        amount = int(match.group(1))
        unit = match.group(2).lower()
        # Relative labels are rounded down. Use the upper edge so stale videos are not accepted.
        return (amount + 1) * unit_hours[unit]
    return None


def _relative_age_is_recent(text: str, max_age_hours: float) -> bool:
    upper_age_hours = _relative_age_upper_hours(text)
    return upper_age_hours is not None and upper_age_hours <= max_age_hours


def parse_youtube_channel_page(
    html_text: str,
    channel_label: str,
    max_age_hours: float = 72.0,
    topic_keywords: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    video_grid = _find_video_grid(_extract_initial_data(html_text))
    if video_grid is None:
        return []
    for lockup in _walk_lockups(video_grid):
        video_id = str(lockup.get("contentId", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) or video_id in seen:
            continue
        metadata = lockup.get("metadata", {}).get("lockupMetadataViewModel", {}) or {}
        title = str(metadata.get("title", {}).get("content", "")).strip()
        metadata_rows = metadata.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", []) or []
        metadata_texts = [
            str(part.get("text", {}).get("content", "")).strip()
            for row in metadata_rows
            for part in row.get("metadataParts", []) or []
        ]
        relative_published = next(
            (text for text in metadata_texts if any(pattern.search(text) for pattern in RELATIVE_AGE_PATTERNS)),
            "",
        )
        if not title or not relative_published or not _relative_age_is_recent(relative_published, max_age_hours):
            continue
        age_upper_hours = _relative_age_upper_hours(relative_published)
        seen.add(video_id)
        items.append(
            {
                "status": "ok",
                "quality_status": "verified",
                "channel": channel_label,
                "title": title,
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "published": f"{relative_published}（取得時点）",
                "published_exact": False,
                "age_hours_upper_bound": age_upper_hours,
                "source": "YouTube 公開チャンネルページ",
                "topics": classify_youtube_topics(title, topic_keywords),
            }
        )
    return items


def parse_youtube_feed(
    xml_text: str,
    channel_label: str,
    now: datetime | None = None,
    max_age_hours: float = 72.0,
    topic_keywords: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(JST)
    root = ET.fromstring(xml_text)
    items: list[dict[str, Any]] = []
    for entry in root.findall(f"{{{ATOM}}}entry"):
        title = (entry.findtext(f"{{{ATOM}}}title") or "").strip()
        video_id = (entry.findtext(f"{{{YOUTUBE}}}videoId") or "").strip()
        published_text = (entry.findtext(f"{{{ATOM}}}published") or "").strip()
        link_element = entry.find(f"{{{ATOM}}}link[@rel='alternate']")
        url = (link_element.get("href") if link_element is not None else "") or ""
        if not title or not video_id or not published_text or not url.startswith("https://www.youtube.com/"):
            continue
        published = _published_at(published_text)
        age_hours = (now - published).total_seconds() / 3600
        if age_hours < 0 or age_hours > max_age_hours:
            continue
        items.append(
            {
                "status": "ok",
                "quality_status": "verified",
                "channel": channel_label,
                "title": title,
                "video_id": video_id,
                "url": url,
                "published": published.strftime("%Y-%m-%d %H:%M JST"),
                "age_hours": round(age_hours, 1),
                "source": "YouTube 公開Atomフィード",
                "topics": classify_youtube_topics(title, topic_keywords),
            }
        )
    items.sort(
        key=lambda item: float(item.get("age_hours", item.get("age_hours_upper_bound", float("inf"))))
    )
    return items


def fetch_youtube_snapshot(sources: dict[str, Any]) -> dict[str, Any]:
    config = sources.get("youtube", {}) or {}
    if not config.get("enabled", False):
        return {"status": "disabled", "items": [], "note": "YouTube新着確認は無効です"}

    timeout = float(config.get("timeout_seconds", 15))
    max_age_hours = float(config.get("max_age_hours", 72))
    max_items = int(config.get("max_items", 3))
    max_items_per_channel = max(1, int(config.get("max_items_per_channel", max_items)))
    topic_keywords = config.get("topic_keywords", {}) or {}
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    fallback_channels: list[str] = []
    for channel in config.get("channels", []):
        channel_id = str(channel.get("channel_id", "")).strip()
        label = str(channel.get("label", channel_id)).strip()
        if not CHANNEL_ID_PATTERN.fullmatch(channel_id):
            errors.append(f"{label}: チャンネルID未確認")
            continue
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            response = requests.get(
                feed_url,
                timeout=timeout,
                headers={"User-Agent": "market-telegram-notifier/1.0"},
            )
            response.raise_for_status()
            channel_items = parse_youtube_feed(
                response.text,
                label,
                max_age_hours=max_age_hours,
                topic_keywords=topic_keywords,
            )
        except Exception as exc:
            try:
                response = requests.get(
                    f"https://www.youtube.com/channel/{channel_id}/videos",
                    timeout=timeout,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept-Language": "ja-JP,ja;q=0.9",
                    },
                )
                response.raise_for_status()
                channel_items = parse_youtube_channel_page(
                    response.text,
                    label,
                    max_age_hours=max_age_hours,
                    topic_keywords=topic_keywords,
                )
                fallback_channels.append(label)
            except Exception as fallback_exc:
                errors.append(f"{label}: Atom={exc} / 動画一覧={fallback_exc}")
                channel_items = []
        items.extend(channel_items[:max_items_per_channel])

    items.sort(
        key=lambda item: float(item.get("age_hours", item.get("age_hours_upper_bound", float("inf"))))
    )
    items = items[:max_items]
    if items:
        status = "ok"
        method_note = (
            f" Atom取得不可のため動画一覧を使用: {', '.join(fallback_channels)}。"
            if fallback_channels
            else ""
        )
        note = "公開ページのタイトル・公開表示・動画URLだけを取得しました。" + method_note + "参考観点はタイトルの語句分類であり、動画内の予想は事実認定しません。"
    elif errors:
        status = "unavailable"
        note = "未確認: " + " / ".join(errors[:3])
    else:
        status = "no_recent_items"
        note = f"直近{max_age_hours:.0f}時間の新着動画は確認されませんでした。"
    return {
        "status": status,
        "items": items,
        "fetched_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
        "source": "YouTube 公開ページ",
        "note": note,
    }

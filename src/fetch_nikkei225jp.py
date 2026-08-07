from __future__ import annotations

import logging
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests

LOGGER = logging.getLogger(__name__)
JST = ZoneInfo("Asia/Tokyo")
DEFAULT_URL = "https://nikkei225jp.com/"


class _Nikkei225TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._current_href: str | None = None
        self.texts: list[str] = []
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag == "a":
            attrs_map = {key: value for key, value in attrs}
            self._current_href = attrs_map.get("href")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "a":
            self._current_href = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        self.texts.append(text)
        if self._current_href:
            self.links.append({"label": text, "url": self._current_href})


def _source_config(sources: dict[str, Any]) -> dict[str, Any]:
    return sources.get("nikkei225jp", {}) or {}


def _enabled(sources: dict[str, Any]) -> bool:
    config = _source_config(sources)
    return bool(config.get("enabled", True))


def _keyword_links(links: list[dict[str, str]], base_url: str, keywords: list[str], limit: int) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for link in links:
        label = " ".join(str(link.get("label", "")).split())
        href = str(link.get("url", "")).strip()
        if not label or len(label) > 48:
            continue
        if not any(keyword.lower() in label.lower() for keyword in keywords):
            continue
        url = urljoin(base_url, href)
        key = (label, url)
        if key in seen:
            continue
        seen.add(key)
        selected.append({"label": label, "url": url})
        if len(selected) >= limit:
            break
    return selected


def _schedule_items(texts: list[str], limit: int) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    current_date = ""
    date_pattern = re.compile(r"^\d{1,2}/\d{1,2}(?:\([^)]*\))?$")
    skip_words = {"前へ", "次へ", "もっと見る", "トップ", "更新", "速報"}

    for text in texts:
        if date_pattern.match(text):
            current_date = text
            continue
        if not current_date or text in skip_words:
            continue
        if len(text) < 3 or len(text) > 80:
            continue
        if not re.search(r"(決算|発表|指標|会合|FOMC|CPI|PCE|雇用|金利|日銀|GDP|ISM|PMI|鉱工業|小売|貿易)", text):
            continue
        items.append({"date": current_date, "event": text})
        if len(items) >= limit:
            break
    return items


def fetch_nikkei225jp_snapshot(sources: dict[str, Any]) -> dict[str, Any]:
    if not _enabled(sources):
        return {"status": "disabled", "source": "nikkei225jp.com", "note": "nikkei225jp.com参照は無効です。"}

    config = _source_config(sources)
    url = str(config.get("url") or DEFAULT_URL)
    timeout = int(config.get("timeout_seconds", 20))
    max_links = int(config.get("max_links", 14))
    max_schedule = int(config.get("max_schedule_items", 10))
    keywords = config.get(
        "watch_keywords",
        [
            "世界株価",
            "日経平均",
            "先物",
            "CFD",
            "ADR",
            "米国",
            "為替",
            "商品",
            "金利",
            "恐怖指数",
            "空売り",
            "信用",
            "決算",
            "スケジュール",
        ],
    )

    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "market-telegram-notifier/1.0 (+https://github.com/youn24/market-telegram-notifier)",
                "Accept-Language": "ja,en;q=0.8",
            },
            timeout=timeout,
        )
        response.raise_for_status()
    except Exception as exc:
        LOGGER.warning("nikkei225jp.com参照をスキップしました: %s", exc)
        return {
            "status": "unavailable",
            "source": "nikkei225jp.com",
            "url": url,
            "fetched_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST"),
            "note": f"未確認: nikkei225jp.comを取得できませんでした ({exc})",
            "content_links": [],
            "schedule_items": [],
            "watch_notes": [],
        }

    parser = _Nikkei225TextParser()
    parser.feed(response.text)
    texts = parser.texts
    links = _keyword_links(parser.links, url, [str(keyword) for keyword in keywords], max_links)
    schedules = _schedule_items(texts, max_schedule)

    watch_notes = [
        "時間外は日経225先物/CFD、ADR、米国主要指数、SOX、VIX、為替、金利、商品を優先確認します。",
        "リアルタイム数値は取得できたデータのみ採用し、ページ上で確認できない値は未確認にします。",
    ]
    if not links:
        watch_notes.append("参照リンク一覧は未確認です。")
    if not schedules:
        watch_notes.append("経済スケジュールは未確認です。")

    return {
        "status": "ok",
        "source": "nikkei225jp.com",
        "url": url,
        "fetched_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST"),
        "content_links": links,
        "schedule_items": schedules,
        "watch_notes": watch_notes,
        "note": "nikkei225jp.comの公開ページを参照しました。数値は既存データ取得で確認できたものだけ使用します。",
    }

from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.modules.setdefault("requests", types.SimpleNamespace())

from fetch_research import _rank_items, _select_diverse_items  # noqa: E402


class ResearchQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = {"category": "japan_market"}
        self.sources = {
            "research": {
                "max_age_hours": 36,
                "freshness_half_life_hours": 18,
                "min_score": 20,
                "importance_keywords": {"japan_market": ["上方修正"]},
                "material_categories": {"業績修正": ["上方修正"]},
            }
        }

    def _item(self, title: str, published: datetime | None) -> dict[str, object]:
        return {
            "title": title,
            "query": "日本株 上方修正",
            "source": "日本経済新聞",
            "published_ts": published.isoformat() if published else "",
            "status": "ok",
        }

    def test_rank_excludes_stale_and_undated_headlines(self) -> None:
        now = datetime.now(timezone.utc)
        ranked = _rank_items(
            [
                self._item("企業が上方修正", now - timedelta(hours=2)),
                self._item("古い上方修正", now - timedelta(hours=60)),
                self._item("日時不明の上方修正", None),
            ],
            self.task,
            self.sources,
        )
        self.assertEqual([item["title"] for item in ranked], ["企業が上方修正"])

    def test_selection_does_not_pad_with_low_score_results(self) -> None:
        selected = _select_diverse_items(
            [
                {"title": "採用", "score": 45, "source": "A", "material_categories": []},
                {"title": "弱い候補", "score": 10, "source": "B", "material_categories": []},
            ],
            self.sources,
            8,
        )
        self.assertEqual([item["title"] for item in selected], ["採用"])


if __name__ == "__main__":
    unittest.main()

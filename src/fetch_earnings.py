from __future__ import annotations

from typing import Any


def fetch_earnings_snapshot(
    task_id: str,
    task_config: dict[str, Any],
    sources: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    note = sources.get("earnings", {}).get("unavailable_items", {}).get("analysis", "未確認")
    return {
        "task_id": task_id,
        "section": "earnings",
        "items": [],
        "highlights": {
            "analysis": note,
        },
    }

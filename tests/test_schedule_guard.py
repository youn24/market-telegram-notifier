from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from schedule_guard import evaluate_schedule

JST = ZoneInfo("Asia/Tokyo")


class ScheduleGuardTests(unittest.TestCase):
    def test_scheduled_run_is_allowed_only_inside_window(self) -> None:
        common = {
            "task_id": "japan_morning",
            "target": "09:30",
            "latest": "11:00",
            "weekdays": {1, 2, 3, 4, 5},
            "event_name": "schedule",
        }
        before = evaluate_schedule(now=datetime(2026, 8, 17, 9, 29, tzinfo=JST), **common)
        inside = evaluate_schedule(now=datetime(2026, 8, 17, 9, 30, tzinfo=JST), **common)
        late = evaluate_schedule(now=datetime(2026, 8, 17, 11, 1, tzinfo=JST), **common)

        self.assertFalse(before.ready)
        self.assertTrue(inside.ready)
        self.assertFalse(late.ready)

    def test_weekend_is_rejected_but_manual_run_is_allowed(self) -> None:
        common = {
            "task_id": "japan_close",
            "target": "17:00",
            "latest": "18:30",
            "weekdays": {1, 2, 3, 4, 5},
            "now": datetime(2026, 8, 16, 17, 10, tzinfo=JST),
        }
        scheduled = evaluate_schedule(event_name="schedule", **common)
        manual = evaluate_schedule(event_name="workflow_dispatch", **common)

        self.assertFalse(scheduled.ready)
        self.assertTrue(manual.ready)


if __name__ == "__main__":
    unittest.main()

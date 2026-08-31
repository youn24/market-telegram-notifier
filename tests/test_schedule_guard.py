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

from schedule_guard import evaluate_schedule, evaluate_task_eligibility

JST = ZoneInfo("Asia/Tokyo")


class ScheduleGuardTests(unittest.TestCase):
    def test_disabled_task_stays_disabled_when_manual(self):
        now = datetime(2026, 8, 29, 5, 41, tzinfo=JST)
        for enabled in (False, "false", None):
            self.assertFalse(evaluate_task_eligibility(
                {"enabled": enabled}, now, "workflow_dispatch"
            )[0])
        self.assertTrue(evaluate_task_eligibility(
            {"enabled": True, "weekdays": [1]}, now, "workflow_dispatch"
        )[0])

    def test_delayed_friday_date_reaches_task_gate(self):
        now = datetime(2026, 8, 29, 5, 41, tzinfo=JST)
        config = {"enabled": True, "weekdays": [1, 2, 3, 4, 5]}
        self.assertFalse(evaluate_task_eligibility(config, now, "schedule")[0])
        self.assertTrue(evaluate_task_eligibility(config, now, "schedule", "2026-08-28")[0])
        for date in ("2026-08-27", "2026-08-30", "invalid"):
            self.assertFalse(evaluate_task_eligibility(config, now, "schedule", date)[0])

    def test_workflows_do_not_override_delivery_receipt(self):
        for name in ("fx_morning", "japan_morning", "japan_close"):
            text = (ROOT / ".github" / "workflows" / f"{name}.yml").read_text(encoding="utf-8")
            self.assertNotIn('echo "sent=true"', text)
            self.assertIn("NOTIFICATION_DELIVERY_DATE: ${{ steps.window.outputs.date }}", text)

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

    def test_delayed_daily_run_is_recovered_once_for_same_date(self) -> None:
        decision = evaluate_schedule(
            task_id="japan_morning",
            target="09:30",
            latest="11:00",
            weekdays={1, 2, 3, 4, 5},
            now=datetime(2026, 8, 28, 21, 48, tzinfo=JST),
            event_name="schedule",
            allow_late=True,
        )

        self.assertTrue(decision.ready)
        self.assertEqual(decision.date_key, "2026-08-28")
        self.assertIn("救済送信", decision.reason)

    def test_friday_close_delayed_to_saturday_uses_friday_marker(self) -> None:
        decision = evaluate_schedule(
            task_id="japan_close",
            target="17:00",
            latest="18:30",
            weekdays={1, 2, 3, 4, 5},
            now=datetime(2026, 8, 29, 5, 41, tzinfo=JST),
            event_name="schedule",
            allow_late=True,
        )

        self.assertTrue(decision.ready)
        self.assertEqual(decision.date_key, "2026-08-28")
        self.assertIn("前対象日分", decision.reason)


if __name__ == "__main__":
    unittest.main()

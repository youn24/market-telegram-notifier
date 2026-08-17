from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class AfterHoursDecision:
    ready: bool
    session_key: str
    reason: str


def evaluate_after_hours_window(now: datetime, event_name: str) -> AfterHoursDecision:
    local_now = now.astimezone(JST)
    minutes = local_now.hour * 60 + local_now.minute
    session_date = local_now.date() if minutes >= 17 * 60 + 30 else (local_now - timedelta(days=1)).date()
    session_key = session_date.isoformat()

    if event_name == "workflow_dispatch":
        return AfterHoursDecision(True, session_key, "手動実行のため時間帯ガードを解除")

    in_window = minutes >= 17 * 60 + 30 or minutes <= 8 * 60 + 30
    if not in_window:
        return AfterHoursDecision(False, session_key, "時間外監視帯ではありません")
    if session_date.isoweekday() == 6:
        return AfterHoursDecision(False, session_key, "土曜開始のセッションは監視対象外です")
    return AfterHoursDecision(True, session_key, "時間外監視帯です")


def _write_output(values: dict[str, str]) -> None:
    output_path = os.getenv("GITHUB_OUTPUT", "").strip()
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    decision = evaluate_after_hours_window(
        datetime.now(JST),
        os.getenv("GITHUB_EVENT_NAME", "schedule").strip(),
    )
    _write_output(
        {
            "ready": str(decision.ready).lower(),
            "session_key": decision.session_key,
            "cache_key": f"notification-after-hours-{decision.session_key}",
            "reason": decision.reason,
        }
    )
    print(f"after_hours: {decision.reason} ready={str(decision.ready).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

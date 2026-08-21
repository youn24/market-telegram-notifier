from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo


NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class UsSessionDecision:
    ready: bool
    session_key: str
    reason: str


def evaluate_us_session_window(now: datetime, event_name: str) -> UsSessionDecision:
    market_now = now.astimezone(NEW_YORK)
    session_key = market_now.date().isoformat()
    if event_name == "workflow_dispatch":
        return UsSessionDecision(True, session_key, "手動実行のため時間帯ガードを解除")
    if market_now.isoweekday() > 5:
        return UsSessionDecision(False, session_key, "米国市場の週末です")
    if not time(9, 30) <= market_now.time() <= time(16, 0):
        return UsSessionDecision(False, session_key, "米国通常取引時間外です")
    return UsSessionDecision(True, session_key, "米国通常取引時間です")


def _write_output(values: dict[str, str]) -> None:
    output_path = os.getenv("GITHUB_OUTPUT", "").strip()
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    decision = evaluate_us_session_window(
        datetime.now(ZoneInfo("UTC")),
        os.getenv("GITHUB_EVENT_NAME", "schedule").strip(),
    )
    _write_output(
        {
            "ready": str(decision.ready).lower(),
            "session_key": decision.session_key,
            "cache_key": f"notification-us-session-{decision.session_key}",
            "reason": decision.reason,
        }
    )
    print(f"us_session: {decision.reason} ready={str(decision.ready).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

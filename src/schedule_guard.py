from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class ScheduleDecision:
    ready: bool
    date_key: str
    reason: str


def _minutes(value: str) -> int:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"時刻はHH:MM形式で指定してください: {value}") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"時刻の範囲が正しくありません: {value}")
    return hour * 60 + minute


def evaluate_schedule(
    *,
    task_id: str,
    target: str,
    latest: str,
    weekdays: set[int],
    now: datetime,
    event_name: str,
) -> ScheduleDecision:
    local_now = now.astimezone(JST)
    date_key = local_now.strftime("%Y-%m-%d")

    if event_name == "workflow_dispatch":
        return ScheduleDecision(True, date_key, "手動実行のため時刻ガードを解除")

    if weekdays and local_now.isoweekday() not in weekdays:
        return ScheduleDecision(False, date_key, "対象曜日ではありません")

    current_minutes = local_now.hour * 60 + local_now.minute
    target_minutes = _minutes(target)
    latest_minutes = _minutes(latest)
    if latest_minutes < target_minutes:
        raise ValueError("latestはtarget以降の時刻にしてください")

    if current_minutes < target_minutes:
        return ScheduleDecision(False, date_key, f"予定時刻{target}より前です")
    if current_minutes > latest_minutes:
        return ScheduleDecision(False, date_key, f"許容終了時刻{latest}を過ぎています")

    return ScheduleDecision(True, date_key, f"送信可能時間帯です: {target}-{latest}")


def _write_github_output(values: dict[str, str]) -> None:
    output_path = os.getenv("GITHUB_OUTPUT", "").strip()
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GitHub Actions通知の送信時間帯を判定します")
    parser.add_argument("--task", required=True)
    parser.add_argument("--target", required=True, help="送信開始時刻 HH:MM (JST)")
    parser.add_argument("--latest", required=True, help="送信許容終了時刻 HH:MM (JST)")
    parser.add_argument("--weekdays", required=True, help="ISO曜日番号をカンマ区切りで指定")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    weekdays = {int(value) for value in args.weekdays.split(",") if value.strip()}
    decision = evaluate_schedule(
        task_id=args.task,
        target=args.target,
        latest=args.latest,
        weekdays=weekdays,
        now=datetime.now(JST),
        event_name=os.getenv("GITHUB_EVENT_NAME", "schedule").strip(),
    )
    cache_key = f"notification-{args.task}-{decision.date_key}"
    _write_github_output(
        {
            "ready": str(decision.ready).lower(),
            "date": decision.date_key,
            "cache_key": cache_key,
            "reason": decision.reason,
        }
    )
    print(f"{args.task}: {decision.reason} ready={str(decision.ready).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from fetch_after_hours import fetch_after_hours_snapshot


BASE_DIR = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = BASE_DIR / "output" / "after_hours_alert" / "snapshot.json"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _write_output(values: dict[str, str]) -> None:
    output_path = os.getenv("GITHUB_OUTPUT", "").strip()
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    tasks = _load_yaml(BASE_DIR / "config" / "tasks.yaml")
    sources = _load_yaml(BASE_DIR / "config" / "sources.yaml")
    rules = _load_yaml(BASE_DIR / "config" / "rules.yaml")
    task = tasks.get("after_hours_alert", {})
    if not task.get("enabled", False):
        _write_output({"triggered": "false", "reason": "enabled:false"})
        print("after_hours_alert: enabled:false")
        return 0

    snapshot = fetch_after_hours_snapshot("after_hours_alert", task, sources, rules)
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    alert = snapshot.get("alert", {})
    triggered = bool(alert.get("triggered"))
    _write_output(
        {
            "triggered": str(triggered).lower(),
            "snapshot": str(SNAPSHOT_PATH),
            "reason": str(alert.get("note", "未確認")).replace("\n", " "),
        }
    )
    print(f"after_hours_alert: {alert.get('note', '未確認')} triggered={str(triggered).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

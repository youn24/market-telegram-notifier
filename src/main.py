from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from analyze_rules import build_summary
from create_cards import create_summary_card
from create_charts import create_market_chart
from fetch_earnings import fetch_earnings_snapshot
from fetch_fx import fetch_fx_snapshot
from fetch_japan_market import fetch_japan_market_snapshot
from notify_telegram import send_telegram_notification
from openai_summary import maybe_generate_openai_summary

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "output"


@dataclass
class TaskContext:
    task_id: str
    task_config: dict[str, Any]
    sources: dict[str, Any]
    rules: dict[str, Any]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_configs(task_id: str) -> TaskContext:
    tasks = load_yaml(CONFIG_DIR / "tasks.yaml")
    sources = load_yaml(CONFIG_DIR / "sources.yaml")
    rules = load_yaml(CONFIG_DIR / "rules.yaml")

    if task_id not in tasks:
        raise ValueError(f"未定義の task_id です: {task_id}")

    return TaskContext(
        task_id=task_id,
        task_config=tasks[task_id],
        sources=sources,
        rules=rules,
    )


def is_task_runnable(task_config: dict[str, Any], now: datetime) -> tuple[bool, str]:
    if not task_config.get("enabled", False):
        return False, "enabled:false のため送信をスキップしました"

    weekdays = task_config.get("weekdays", [])
    if weekdays and now.isoweekday() not in weekdays:
        return False, f"本日は対象曜日外です: isoweekday={now.isoweekday()}"

    return True, ""


def should_ignore_weekday_check() -> bool:
    return os.getenv("GITHUB_EVENT_NAME", "").strip() == "workflow_dispatch"


def fetch_task_data(context: TaskContext) -> dict[str, Any]:
    category = context.task_config.get("category")

    if category == "fx":
        return fetch_fx_snapshot(context.task_id, context.task_config, context.sources, context.rules)
    if category == "japan_market":
        return fetch_japan_market_snapshot(context.task_id, context.task_config, context.sources, context.rules)
    if category == "earnings":
        return fetch_earnings_snapshot(context.task_id, context.task_config, context.sources, context.rules)

    raise ValueError(f"未対応の category です: {category}")


def ensure_output_dir(task_id: str) -> Path:
    task_output = OUTPUT_DIR / task_id
    task_output.mkdir(parents=True, exist_ok=True)
    return task_output


def build_notification(context: TaskContext) -> tuple[str, list[Path], dict[str, Any]]:
    raw_data = fetch_task_data(context)
    summary = build_summary(context.task_id, context.task_config, raw_data, context.rules)

    openai_text = maybe_generate_openai_summary(summary)
    if openai_text:
        summary["body"] = openai_text

    output_dir = ensure_output_dir(context.task_id)
    chart_path = create_market_chart(context.task_id, context.task_config, raw_data, context.rules, output_dir)
    card_path = create_summary_card(context.task_id, context.task_config, summary, context.rules, output_dir)

    text = "\n".join(
        [
            f"【{context.task_config.get('title', context.task_id)}】",
            f"日時: {summary['generated_at']}",
            "",
            summary["body"],
        ]
    )

    images = [path for path in [chart_path, card_path] if path is not None and path.exists()]
    return text, images, raw_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="金融市場 Telegram 通知")
    parser.add_argument("--task", required=True, help="config/tasks.yaml の task_id")
    parser.add_argument("--dry-run", action="store_true", help="Telegram 送信を行わず内容のみ表示")
    return parser.parse_args()


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main() -> int:
    load_dotenv()
    setup_logging()
    args = parse_args()

    context = load_configs(args.task)
    now = datetime.now()
    if should_ignore_weekday_check():
        runnable, reason = True, "workflow_dispatch のため曜日チェックをスキップしました"
        logging.info(reason)
    else:
        runnable, reason = is_task_runnable(context.task_config, now)
    if not runnable:
        logging.info(reason)
        return 0

    message, images, _ = build_notification(context)
    logging.info("通知本文:\n%s", message)

    if args.dry_run:
        logging.info("dry-run のため Telegram 送信をスキップしました")
        return 0

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        logging.warning("Telegram 環境変数が未設定のため送信をスキップしました")
        return 0

    send_telegram_notification(bot_token=bot_token, chat_id=chat_id, text=message, image_paths=images)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

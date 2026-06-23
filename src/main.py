from __future__ import annotations

import argparse
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

from analyze_rules import build_summary
from create_cards import create_summary_card
from create_charts import create_market_chart
from create_report import create_market_report
from design_director import build_design_direction, write_design_handoff
from fetch_earnings import fetch_earnings_snapshot
from fetch_fx import fetch_fx_snapshot
from fetch_japan_market import fetch_japan_market_snapshot
from fetch_research import fetch_research_snapshot
from notify_telegram import send_telegram_notification
from openai_summary import maybe_generate_openai_summary

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "output"
SITE_DIR = BASE_DIR / "site"
JST = ZoneInfo("Asia/Tokyo")


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


def report_url() -> str | None:
    explicit = os.getenv("REPORT_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/") + "/"

    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not repository or "/" not in repository:
        return None

    owner, repo = repository.split("/", 1)
    return f"https://{owner}.github.io/{repo}/"


def display_title(task_config: dict[str, Any], task_id: str) -> str:
    title = str(task_config.get("title", task_id)).strip()
    run_at = str(task_config.get("run_at", "")).strip()
    if run_at:
        normalized_run_at = run_at.lstrip("0")
        title_without_time = re.sub(r"^\s*\d{1,2}:\d{2}\s*", "", title).strip()
        if title.startswith(run_at) or title.startswith(normalized_run_at):
            return title
        return f"{run_at} {title_without_time or title}"
    return title


def clip_message_text(text: str, max_chars: int = 80) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def clean_analysis_lines(lines: list[str], limit: int = 5, max_chars: int = 80) -> list[str]:
    cleaned: list[str] = []
    for line in lines:
        text = str(line).strip().strip("-・* ")
        if not text:
            continue
        cleaned.append(clip_message_text(text, max_chars))
        if len(cleaned) >= limit:
            break
    return cleaned


def build_notification(context: TaskContext) -> tuple[str, list[Path], dict[str, Any]]:
    raw_data = fetch_task_data(context)
    raw_data["research"] = fetch_research_snapshot(context.task_id, context.task_config, context.sources)
    summary = build_summary(context.task_id, context.task_config, raw_data, context.rules)

    openai_text = maybe_generate_openai_summary(summary)
    if openai_text:
        summary["body"] = openai_text
        summary["ai_summary"] = clean_analysis_lines(openai_text.splitlines())
        summary["commentary"] = summary["ai_summary"][:3]

    output_dir = ensure_output_dir(context.task_id)
    chart_path = create_market_chart(context.task_id, context.task_config, raw_data, context.rules, output_dir)
    card_path = create_summary_card(context.task_id, context.task_config, summary, context.rules, output_dir)
    create_market_report(context.task_id, context.task_config, summary, raw_data, SITE_DIR, card_path, chart_path)
    design_direction = build_design_direction(context.task_id, context.task_config, summary, raw_data)
    write_design_handoff(SITE_DIR, design_direction)

    link = report_url()
    title = display_title(context.task_config, context.task_id)
    headline = {
        "bull": "結論: 強気寄り",
        "bear": "結論: 警戒",
        "neutral": "結論: 様子見",
    }.get(summary.get("market_tone", "neutral"), "結論: 様子見")
    teacher_line = clip_message_text(
        summary.get("conclusion_text", "未確認データを残しながら、取れる数字だけで判断します。"),
        90,
    )
    student_line = clip_message_text(summary.get("dialogue", [{}])[0].get("text", ""), 70)
    analysis_lines = clean_analysis_lines(summary.get("ai_summary") or summary.get("deep_summary_lines", []))
    analysis_block = "\n".join(f"- {line}" for line in analysis_lines)

    message_parts = [
        f"【{title}】",
        f"配信日時: {summary['generated_at']}",
        headline,
        "",
        "AI分析",
        analysis_block or f"- {teacher_line}",
        "",
        f"ガネーシャ先生: {teacher_line}",
    ]
    if student_line:
        message_parts.extend(["", f"カワウソくん: {student_line}"])
    if link:
        message_parts.extend(["", f"レポート: {link}"])

    text = "\n".join(message_parts)

    images = [path for path in [card_path, chart_path] if path is not None and path.exists()]
    return text, images, raw_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="金融市場 Telegram 通知")
    parser.add_argument("--task", required=True, help="config/tasks.yaml の task_id")
    parser.add_argument("--dry-run", action="store_true", help="Telegram 送信を行わず内容のみ表示")
    return parser.parse_args()


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("matplotlib").setLevel(logging.ERROR)
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)


def main() -> int:
    load_dotenv()
    setup_logging()
    args = parse_args()

    context = load_configs(args.task)
    now = datetime.now(JST)
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

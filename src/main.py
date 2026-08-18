from __future__ import annotations

import argparse
import html
import json
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
from fetch_after_hours import fetch_after_hours_snapshot
from fetch_fx import fetch_fx_snapshot
from fetch_japan_market import fetch_japan_market_snapshot
from fetch_nikkei225jp import fetch_nikkei225jp_snapshot
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

    if category == "after_hours":
        snapshot_path = os.getenv("AFTER_HOURS_SNAPSHOT_FILE", "").strip()
        if snapshot_path:
            path = Path(snapshot_path)
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        return fetch_after_hours_snapshot(context.task_id, context.task_config, context.sources, context.rules)

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


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def should_use_ai_summary(dry_run: bool) -> bool:
    if not env_flag("AI_SUMMARY_ENABLED", True):
        return False
    if dry_run and not env_flag("AI_SUMMARY_ON_DRY_RUN", False):
        return False
    return True


def should_attach_telegram_image() -> bool:
    return env_flag("TELEGRAM_ATTACH_IMAGE", True)


def _write_github_output(values: dict[str, str]) -> None:
    output_path = os.getenv("GITHUB_OUTPUT", "").strip()
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def _apply_after_hours_summary(summary: dict[str, Any], raw_data: dict[str, Any]) -> None:
    alert = raw_data.get("alert", {}) or {}
    primary = alert.get("primary") or {}
    change = primary.get("change_pct")
    key = str(primary.get("key", ""))
    direction = 1 if isinstance(change, (int, float)) and change > 0 else -1
    if key == "VIX":
        tone = "bear" if direction > 0 else "bull"
    elif key.endswith("_FUT") or key.startswith("ADR_"):
        tone = "bull" if direction > 0 else "bear"
    else:
        tone = "neutral"

    score = int(primary.get("score", 0))
    reasons = [str(value) for value in primary.get("reasons", [])]
    contradictions = [str(value) for value in primary.get("contradictions", [])]
    label = str(primary.get("label", "時間外市場"))
    change_text = f"{change:+.2f}%" if isinstance(change, (int, float)) else "未確認"
    confirmation = str(alert.get("confirmation_label", "未確認"))
    conclusion = f"{label}が{change_text}。鮮度・継続性・関連市場を確認し、確認度{confirmation}です。"
    action = "初動へ飛びつかず、次の観測でも方向が維持されるかと反証条件を確認します。"

    summary.update(
        {
            "market_tone": tone,
            "series_mode": "intraday",
            "conclusion_label": f"急変確認 / 確認度{confirmation}",
            "conclusion_text": conclusion,
            "commentary": [*reasons[:2], action],
            "signals": [f"- 確認度: {score}/100（勝率ではありません）", *[f"- 根拠: {line}" for line in reasons[:3]]],
            "dialogue": [
                {"speaker": "カワウソくん", "role": "student", "text": f"先生、{label}の{change_text}は追いかけてよい動きですか？"},
                {"speaker": "ガネーシャ先生", "role": "teacher", "text": f"急変は確認しました。ただし勝率ではありません。{action}"},
            ],
            "analysis_dashboard": {
                "score": score,
                "band": f"確認度{confirmation}",
                "breadth": 0,
                "up_count": len([item for item in raw_data.get("items", []) if isinstance(item.get("change_pct"), (int, float)) and item["change_pct"] > 0]),
                "down_count": len([item for item in raw_data.get("items", []) if isinstance(item.get("change_pct"), (int, float)) and item["change_pct"] < 0]),
                "average_change": 0.0,
                "leader_text": label,
                "laggard_text": contradictions[0] if contradictions else "明確な反証は未確認",
                "risk_reasons": reasons[:3],
                "action": action,
                "checklist": [f"確認度: {score}/100", *reasons[:3], f"反証: {contradictions[0] if contradictions else '明確な反証は未確認'}", f"実戦方針: {action}"],
            },
            "trade_checklist": [f"確認度: {score}/100", *reasons[:3], *[f"反証: {line}" for line in contradictions[:2]], action],
            "deep_summary_lines": [conclusion, *reasons[:2], action],
            "scenarios": [
                f"継続: 次回観測でも{label}と関連市場が同方向なら急変継続を確認",
                "中立: 変動幅が基準内へ戻れば一時的な振れとして再評価",
                f"反証: {contradictions[0] if contradictions else '関連市場が逆方向へ転じた場合はシグナルを弱める'}",
            ],
        }
    )


def build_notification(context: TaskContext, use_ai: bool = True) -> tuple[str, list[Path], dict[str, Any]] | None:
    raw_data = fetch_task_data(context)
    if context.task_config.get("category") == "after_hours" and not raw_data.get("alert", {}).get("triggered"):
        logging.info("時間外通知を見送りました: %s", raw_data.get("alert", {}).get("note", "基準未達"))
        return None
    if context.task_config.get("category") == "after_hours" and "nikkei225jp" not in raw_data:
        raw_data["nikkei225jp"] = fetch_nikkei225jp_snapshot(context.sources)
    raw_data["research"] = fetch_research_snapshot(context.task_id, context.task_config, context.sources)
    summary = build_summary(context.task_id, context.task_config, raw_data, context.rules)
    if context.task_config.get("category") == "after_hours":
        _apply_after_hours_summary(summary, raw_data)

    openai_text = maybe_generate_openai_summary(summary) if use_ai else None
    if openai_text:
        summary["body"] = openai_text
        summary["ai_summary"] = clean_analysis_lines(openai_text.splitlines())
        if context.task_config.get("category") != "after_hours":
            summary["commentary"] = summary["ai_summary"][:3]

    output_dir = ensure_output_dir(context.task_id)
    chart_path = create_market_chart(context.task_id, context.task_config, raw_data, context.rules, output_dir)
    card_path = create_summary_card(context.task_id, context.task_config, summary, context.rules, output_dir)
    design_direction = build_design_direction(context.task_id, context.task_config, summary, raw_data)
    create_market_report(context.task_id, context.task_config, summary, raw_data, SITE_DIR, card_path, chart_path, design_direction)
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
    title_text = html.escape(title)
    headline_text = html.escape(headline)
    generated_at_text = html.escape(str(summary["generated_at"]))
    teacher_text = html.escape(teacher_line)
    message_parts = [
        f"<b>{title_text}</b>",
        f"配信日時: <code>{generated_at_text}</code>",
        f"<b>{headline_text}</b>",
        "",
        f"要点: {teacher_text}",
    ]
    if summary.get("money_flow", {}).get("status") == "ok":
        flow_text = html.escape(clip_message_text(str(summary.get("money_flow_headline", "未確認")), 80))
        message_parts.append(f"資金方向: {flow_text}")
    if summary.get("theme_primary"):
        theme_text = html.escape(clip_message_text(str(summary.get("theme_headline", "テーマ株: 未確認")), 80))
        message_parts.append(f"注目テーマ: {theme_text}")
    if summary.get("price_pattern_candidates"):
        pattern_text = html.escape(clip_message_text(str(summary.get("price_pattern_headline", "未確認")), 80))
        message_parts.append(f"複合足型: {pattern_text}")
    if link:
        safe_link = html.escape(link, quote=True)
        message_parts.extend(["", f'<a href="{safe_link}">詳細はこちら</a>'])
    else:
        message_parts.extend(["", "詳細レポートURL: 未確認"])

    text = "\n".join(message_parts)

    images = [card_path] if should_attach_telegram_image() and card_path is not None and card_path.exists() else []
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
        _write_github_output({"sent": "false", "reason": reason})
        return 0

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not args.dry_run and (not bot_token or not chat_id):
        logging.warning("Telegram 環境変数が未設定のため送信とAI要約をスキップしました")
        _write_github_output({"sent": "false", "reason": "telegram secrets missing"})
        return 2

    use_ai = should_use_ai_summary(args.dry_run)
    if not use_ai:
        logging.info("AI要約は節約設定によりスキップしました")

    notification = build_notification(context, use_ai=use_ai)
    if notification is None:
        _write_github_output({"sent": "false", "reason": "signal threshold not met"})
        return 0
    message, images, _ = notification
    logging.info("通知本文:\n%s", message)

    if args.dry_run:
        logging.info("dry-run のため Telegram 送信をスキップしました")
        _write_github_output({"sent": "false", "reason": "dry-run"})
        return 0

    send_telegram_notification(bot_token=bot_token, chat_id=chat_id, text=message, image_paths=images)
    _write_github_output({"sent": "true", "reason": "telegram delivered"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

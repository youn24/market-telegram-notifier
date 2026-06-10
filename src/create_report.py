from __future__ import annotations

import html
import shutil
from pathlib import Path
from typing import Any


def _safe(text: str) -> str:
    return html.escape(text, quote=True)


def _market_label(tone: str) -> tuple[str, str]:
    mapping = {
        "bull": ("強気寄り", "#16a34a"),
        "bear": ("警戒", "#dc2626"),
        "neutral": ("様子見", "#d97706"),
    }
    return mapping.get(tone, mapping["neutral"])


def _render_list(items: list[str], css_class: str) -> str:
    blocks: list[str] = []
    for item in items:
        blocks.append(f'<li class="{css_class}">{_safe(item.replace("- ", "", 1))}</li>')
    return "\n".join(blocks)


def _render_metrics(metrics: list[str]) -> str:
    cards: list[str] = []
    for metric in metrics:
        cards.append(f'<div class="metric-card">{_safe(metric.replace("- ", "", 1))}</div>')
    return "\n".join(cards)


def _render_dialogue(dialogue: list[dict[str, str]]) -> str:
    blocks: list[str] = []
    for item in dialogue:
        role = item.get("role", "teacher")
        role_class = "student" if role == "student" else "teacher"
        blocks.append(
            "\n".join(
                [
                    f'<section class="talk {role_class}">',
                    f'  <div class="talk-role">{_safe(item.get("speaker", ""))}</div>',
                    f'  <div class="talk-text">{_safe(item.get("text", ""))}</div>',
                    "</section>",
                ]
            )
        )
    return "\n".join(blocks)


def _render_bullets(items: list[str], css_class: str) -> str:
    rows = []
    for item in items:
        rows.append(f'<li class="{css_class}">{_safe(item)}</li>')
    return "\n".join(rows)


def _copy_if_exists(source: Path | None, destination: Path) -> str | None:
    if source is None or not source.exists():
        return None
    shutil.copy2(source, destination)
    return destination.name


def create_market_report(
    task_id: str,
    task_config: dict[str, Any],
    summary: dict[str, Any],
    raw_data: dict[str, Any],
    site_dir: Path,
    card_path: Path | None,
    chart_path: Path | None,
) -> Path:
    site_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = site_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    copied_card = _copy_if_exists(card_path, assets_dir / "summary-card.png")
    copied_chart = _copy_if_exists(chart_path, assets_dir / "market-chart.png")

    market_label, market_color = _market_label(summary.get("market_tone", "neutral"))
    metrics_html = _render_metrics(summary.get("metrics", [])[:5])
    signals_html = _render_list(summary.get("signals", [])[:4], "signal-item")
    commentary_html = _render_list(summary.get("commentary", [])[:3], "memo-item")
    opportunity_html = _render_bullets(summary.get("opportunities", [])[:3], "opportunity-item")
    caution_html = _render_bullets(summary.get("cautions", [])[:3], "caution-item")

    chart_img = f'<img src="assets/{copied_chart}" alt="market chart" class="section-image">' if copied_chart else ""
    card_img = f'<img src="assets/{copied_card}" alt="summary card" class="section-image">' if copied_card else ""

    item_rows = []
    for item in raw_data.get("items", []):
        current_text = "未確認" if item.get("current") is None else f"{item.get('current'):,.2f}"
        change_value = item.get("change_pct")
        change_text = "未確認" if change_value is None else f"{change_value:+.2f}%"
        item_rows.append(
            "\n".join(
                [
                    '<div class="table-row">',
                    f'  <div>{_safe(item.get("label", ""))}</div>',
                    f'  <div>{_safe(current_text)}</div>',
                    f'  <div>{_safe(change_text)}</div>',
                    "</div>",
                ]
            )
        )

    html_text = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{_safe(task_config.get("title", task_id))}</title>
  <style>
    :root {{
      --bg: #fff8f1;
      --panel: #fffdfa;
      --line: #eed7c4;
      --text: #2c241f;
      --sub: #7a6558;
      --accent: {market_color};
      --good: #166534;
      --bad: #991b1b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Hiragino Sans", "Yu Gothic", "Meiryo", sans-serif;
      background: linear-gradient(180deg, #fff9f4 0%, #fff1e4 100%);
      color: var(--text);
    }}
    .page {{
      max-width: 540px;
      margin: 0 auto;
      padding: 18px 14px 48px;
    }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 18px;
      box-shadow: 0 8px 24px rgba(132, 92, 63, 0.08);
      margin-bottom: 14px;
    }}
    .eyebrow {{
      font-size: 12px;
      color: var(--sub);
      margin-bottom: 8px;
    }}
    h1 {{
      font-size: 28px;
      line-height: 1.25;
      margin: 0 0 10px;
    }}
    .theme {{
      font-size: 15px;
      line-height: 1.7;
      color: var(--sub);
      margin-bottom: 14px;
    }}
    .badge {{
      display: inline-block;
      background: var(--accent);
      color: white;
      border-radius: 999px;
      padding: 8px 14px;
      font-weight: 700;
      font-size: 14px;
      margin-bottom: 12px;
    }}
    .meta {{
      font-size: 12px;
      color: var(--sub);
    }}
    h2 {{
      font-size: 21px;
      margin: 0 0 12px;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }}
    .metric-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 12px 14px;
      background: #fff9f4;
      font-size: 16px;
      line-height: 1.6;
      font-weight: 700;
    }}
    .section-image {{
      width: 100%;
      display: block;
      border-radius: 18px;
      border: 1px solid var(--line);
      margin-top: 12px;
    }}
    .signal-list, .memo-list {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 10px;
    }}
    .signal-item, .memo-item {{
      background: #fff9f4;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px 14px;
      line-height: 1.7;
      font-size: 15px;
    }}
    .opportunity-item, .caution-item {{
      border-radius: 16px;
      padding: 12px 14px;
      line-height: 1.8;
      font-size: 15px;
      border: 1px solid var(--line);
      margin-bottom: 10px;
      list-style: none;
    }}
    .opportunity-item {{ background: #f0fdf4; color: var(--good); }}
    .caution-item {{ background: #fef2f2; color: var(--bad); }}
    .conclusion {{
      font-size: 19px;
      line-height: 1.8;
      font-weight: 700;
      background: #fff9f4;
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 16px;
    }}
    .table {{
      display: grid;
      gap: 8px;
    }}
    .table-head, .table-row {{
      display: grid;
      grid-template-columns: 1.3fr 1fr 1fr;
      gap: 8px;
      align-items: center;
    }}
    .table-head {{
      font-size: 12px;
      color: var(--sub);
      font-weight: 700;
      padding: 0 6px;
    }}
    .table-row {{
      background: #fff9f4;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      font-size: 15px;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">{_safe(summary.get("theme_title", "本日のテーマ"))}</div>
      <h1>{_safe(task_config.get("title", task_id))}</h1>
      <div class="badge">{_safe(market_label)}</div>
      <div class="theme">{_safe(summary.get("theme_subtitle", ""))}</div>
      <div class="meta">更新: {_safe(summary.get("generated_at", ""))}</div>
    </section>

    <section class="panel">
      <h2>結論</h2>
      <div class="conclusion">{_safe(summary.get("conclusion_text", ""))}</div>
    </section>

    <section class="panel">
      <h2>重要数字</h2>
      <div class="metric-grid">
        {metrics_html}
      </div>
    </section>

    <section class="panel">
      <h2>チャート</h2>
      {chart_img}
      {card_img}
    </section>

    <section class="panel">
      <h2>主要項目一覧</h2>
      <div class="table">
        <div class="table-head">
          <div>項目</div>
          <div>現在値</div>
          <div>前日比</div>
        </div>
        {"".join(item_rows)}
      </div>
    </section>

    <section class="panel">
      <h2>注目ポイント</h2>
      <ul class="signal-list">
        {opportunity_html}
      </ul>
      <ul class="signal-list">
        {caution_html}
      </ul>
    </section>

    <section class="panel">
      <h2>シグナル一覧</h2>
      <ul class="signal-list">
        {signals_html}
      </ul>
    </section>

    <section class="panel">
      <h2>先生の補足メモ</h2>
      <ul class="memo-list">
        {commentary_html}
      </ul>
    </section>
  </main>
</body>
</html>
"""

    report_path = site_dir / "index.html"
    report_path.write_text(html_text, encoding="utf-8")
    return report_path

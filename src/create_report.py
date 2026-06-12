from __future__ import annotations

import html
import shutil
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
HERO_ASSET = BASE_DIR / "assets" / "design" / "market-digest-hero.png"


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


def _render_digest_tiles(summary: dict[str, Any], raw_data: dict[str, Any]) -> str:
    macro_count = len([item for item in raw_data.get("macro_items", []) if item.get("status") == "ok"])
    market_count = len([item for item in raw_data.get("items", []) if item.get("status") == "ok"])
    tiles = [
        ("結論", summary.get("conclusion_label", "様子見"), "tile-accent"),
        ("取得済み", f"市場 {market_count} / マクロ {macro_count}", "tile-blue"),
        ("注目", "金利・VIX・為替", "tile-green"),
        ("作戦", "3シナリオで確認", "tile-gold"),
    ]
    return "\n".join(
        f'<div class="digest-tile {klass}"><span>{_safe(label)}</span><strong>{_safe(value)}</strong></div>'
        for label, value, klass in tiles
    )


def _render_sparkline(series: list[dict[str, Any]], color: str) -> str:
    values = [point.get("value") for point in series if point.get("value") is not None]
    if len(values) < 2:
        return '<div class="sparkline-empty">未確認</div>'

    min_value = min(values)
    max_value = max(values)
    span = max(max_value - min_value, 0.000001)
    points = []
    for index, value in enumerate(values):
        x = 8 + index * (104 / max(1, len(values) - 1))
        y = 44 - ((value - min_value) / span) * 32
        points.append(f"{x:.1f},{y:.1f}")
    return f'<svg class="sparkline" viewBox="0 0 120 52" aria-hidden="true"><polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>'


def _render_macro_cards(items: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for item in items:
        change = item.get("change_pct")
        change_text = "未確認" if change is None else f"{change:+.2f}%"
        current = item.get("current")
        unit = item.get("unit", "")
        value_text = "未確認" if current is None else f"{current:,.2f}{unit}"
        color = "#16a34a" if (change or 0) >= 0 else "#dc2626"
        cards.append(
            "\n".join(
                [
                    '<article class="macro-card">',
                    f'  <div class="macro-name">{_safe(item.get("label", ""))}</div>',
                    f'  <div class="macro-value">{_safe(value_text)}</div>',
                    f'  <div class="macro-change" style="color:{color}">{_safe(change_text)}</div>',
                    f'  {_render_sparkline(item.get("series", []), color)}',
                    "</article>",
                ]
            )
        )
    return "\n".join(cards) or '<div class="metric-card">マクロ指標は未確認</div>'


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
    copied_hero = _copy_if_exists(HERO_ASSET, assets_dir / "market-digest-hero.png")

    market_label, market_color = _market_label(summary.get("market_tone", "neutral"))
    digest_tiles_html = _render_digest_tiles(summary, raw_data)
    metrics_html = _render_metrics(summary.get("metrics", [])[:5])
    market_metrics_html = _render_metrics(summary.get("market_metrics", [])[:5])
    macro_cards_html = _render_macro_cards(raw_data.get("macro_items", []))
    signals_html = _render_list(summary.get("signals", [])[:4], "signal-item")
    commentary_html = _render_list(summary.get("commentary", [])[:3], "memo-item")
    opportunity_html = _render_bullets(summary.get("opportunities", [])[:3], "opportunity-item")
    caution_html = _render_bullets(summary.get("cautions", [])[:3], "caution-item")
    dialogue_html = _render_dialogue(summary.get("dialogue", []))
    scenario_html = _render_bullets(summary.get("scenarios", [])[:3], "scenario-item")

    chart_img = f'<img src="assets/{copied_chart}" alt="market chart" class="section-image">' if copied_chart else ""
    card_img = f'<img src="assets/{copied_card}" alt="summary card" class="section-image">' if copied_card else ""
    hero_background = (
        f"linear-gradient(135deg, rgba(23, 32, 51, .92), rgba(15, 118, 110, .72)), url('assets/{copied_hero}')"
        if copied_hero
        else "linear-gradient(135deg, #172033 0%, #243b67 48%, #0f766e 100%)"
    )

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
      --bg: #f5f7fb;
      --panel: #ffffff;
      --line: #dbe4ef;
      --text: #172033;
      --sub: #64748b;
      --accent: {market_color};
      --navy: #172033;
      --blue: #2563eb;
      --gold: #f59e0b;
      --good: #166534;
      --bad: #991b1b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Hiragino Sans", "Yu Gothic", "Meiryo", sans-serif;
      background:
        linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, transparent 28%),
        linear-gradient(225deg, rgba(245, 158, 11, 0.12) 0%, transparent 24%),
        var(--bg);
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
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 14px 34px rgba(23, 32, 51, 0.10);
      margin-bottom: 14px;
    }}
    .hero {{
      position: relative;
      overflow: hidden;
      color: white;
      background: {hero_background};
      background-size: cover;
      background-position: center;
      border: 0;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      right: -42px;
      top: -42px;
      width: 168px;
      height: 168px;
      border-radius: 50%;
      background: rgba(245, 158, 11, 0.28);
    }}
    .hero > * {{
      position: relative;
      z-index: 1;
    }}
    .eyebrow {{
      font-size: 12px;
      color: #facc15;
      margin-bottom: 8px;
      font-weight: 800;
    }}
    h1 {{
      font-size: 28px;
      line-height: 1.25;
      margin: 0 0 10px;
    }}
    .theme {{
      font-size: 15px;
      line-height: 1.7;
      color: #dbeafe;
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
      color: #cbd5e1;
    }}
    .digest-strip {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin: 14px 0 0;
    }}
    .digest-tile {{
      border-radius: 16px;
      padding: 12px;
      color: white;
      min-height: 74px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.16);
    }}
    .digest-tile span {{
      font-size: 11px;
      opacity: .86;
      font-weight: 800;
    }}
    .digest-tile strong {{
      font-size: 16px;
      line-height: 1.35;
    }}
    .tile-accent {{ background: linear-gradient(135deg, var(--accent), #111827); }}
    .tile-blue {{ background: linear-gradient(135deg, #2563eb, #06b6d4); }}
    .tile-green {{ background: linear-gradient(135deg, #059669, #84cc16); }}
    .tile-gold {{ background: linear-gradient(135deg, #f59e0b, #ef4444); }}
    h2 {{
      font-size: 21px;
      margin: 0 0 12px;
      border-left: 6px solid var(--accent);
      padding-left: 10px;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }}
    .macro-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}
    .macro-card {{
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px;
      background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
      min-height: 152px;
      box-shadow: 0 8px 18px rgba(23, 32, 51, 0.06);
    }}
    .macro-name {{
      color: var(--sub);
      font-size: 12px;
      font-weight: 700;
      line-height: 1.4;
    }}
    .macro-value {{
      font-size: 24px;
      font-weight: 800;
      margin-top: 6px;
    }}
    .macro-change {{
      font-size: 14px;
      font-weight: 800;
      margin-top: 2px;
    }}
    .sparkline {{
      width: 100%;
      height: 48px;
      margin-top: 8px;
      background: #eef2ff;
      border-radius: 12px;
    }}
    .sparkline-empty {{
      margin-top: 12px;
      color: var(--sub);
      font-size: 13px;
    }}
    .metric-card {{
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px 14px;
      background: linear-gradient(90deg, #ffffff 0%, #f8fafc 100%);
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
      background: #f8fafc;
      border: 1px solid var(--line);
      border-radius: 14px;
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
    .scenario-item {{
      border-radius: 16px;
      padding: 12px 14px;
      line-height: 1.8;
      font-size: 15px;
      border: 1px solid var(--line);
      margin-bottom: 10px;
      list-style: none;
      background: #eff6ff;
      color: #1e3a8a;
    }}
    .talk {{
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px 14px;
      margin-bottom: 10px;
      line-height: 1.8;
    }}
    .talk.teacher {{ background: linear-gradient(90deg, #fff7ed, #ffffff); border-left: 6px solid #f59e0b; }}
    .talk.student {{ background: linear-gradient(90deg, #eff6ff, #ffffff); border-left: 6px solid #2563eb; }}
    .talk-role {{
      color: var(--sub);
      font-size: 12px;
      font-weight: 800;
      margin-bottom: 4px;
    }}
    .talk-text {{
      font-size: 15px;
      font-weight: 700;
    }}
    .conclusion {{
      font-size: 19px;
      line-height: 1.8;
      font-weight: 700;
      background: linear-gradient(135deg, rgba(245, 158, 11, .14), rgba(37, 99, 235, .09));
      border: 1px solid rgba(245, 158, 11, .35);
      border-radius: 16px;
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
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 12px;
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
      <div class="digest-strip">
        {digest_tiles_html}
      </div>
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
      <h2>金利・VIX・マクロ比較</h2>
      <div class="macro-grid">
        {macro_cards_html}
      </div>
    </section>

    <section class="panel">
      <h2>ガネーシャ先生とカワウソくん</h2>
      {dialogue_html}
    </section>

    <section class="panel">
      <h2>チャート</h2>
      {chart_img}
      {card_img}
    </section>

    <section class="panel">
      <h2>指数・為替一覧</h2>
      <div class="metric-grid">
        {market_metrics_html}
      </div>
    </section>

    <section class="panel">
      <h2>取得データ一覧</h2>
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
      <h2>今日の3シナリオ</h2>
      <ul class="signal-list">
        {scenario_html}
      </ul>
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

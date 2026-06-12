from __future__ import annotations

import html
import shutil
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
HERO_ASSET = BASE_DIR / "assets" / "design" / "market-digest-hero.png"

WORLD_BOARD_GROUPS = [
    ("日本", ["NIKKEI225", "TOPIX"]),
    ("米国", ["DOW", "SP500", "NASDAQ", "RUSSELL2000"]),
    ("欧州", ["FTSE100", "DAX", "CAC40"]),
    ("アジア", ["HANGSENG", "SHANGHAI", "KOSPI"]),
    ("為替・商品", ["USDJPY", "EURUSD", "GOLD", "WTI"]),
    ("金利・リスク", ["US10Y", "SOFR", "VIX", "YIELD_2S10S", "DOLLAR_BROAD"]),
]

CHART_BOARD_KEYS = ["NIKKEI225", "TOPIX", "DOW", "SP500", "NASDAQ", "USDJPY", "US10Y", "VIX", "GOLD", "WTI"]


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


def _render_price_sparkline(series: list[dict[str, Any]], color: str) -> str:
    values = [point.get("value") for point in series if point.get("value") is not None]
    if len(values) < 2:
        return '<div class="price-chart-empty">未確認</div>'

    min_value = min(values)
    max_value = max(values)
    span = max(max_value - min_value, 0.000001)
    points = []
    area_points = ["8,86"]
    for index, value in enumerate(values):
        x = 8 + index * (176 / max(1, len(values) - 1))
        y = 78 - ((value - min_value) / span) * 58
        points.append(f"{x:.1f},{y:.1f}")
        area_points.append(f"{x:.1f},{y:.1f}")
    area_points.append("184,86")
    return "\n".join(
        [
            '<svg class="price-chart" viewBox="0 0 192 92" aria-hidden="true">',
            f'  <polygon points="{" ".join(area_points)}" fill="{color}" opacity="0.14"/>',
            f'  <polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>',
            '  <line x1="8" y1="86" x2="184" y2="86" stroke="rgba(100,116,139,.24)" stroke-width="2"/>',
            "</svg>",
        ]
    )


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


def _format_tile_value(item: dict[str, Any]) -> str:
    current = item.get("current")
    unit = item.get("unit", "")
    if current is None:
        return "未確認"
    return f"{current:,.2f}{unit}"


def _format_tile_change(item: dict[str, Any]) -> str:
    change = item.get("change_pct")
    if change is None:
        return "未確認"
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.2f}%"


def _render_market_tile(item: dict[str, Any] | None, key: str) -> str:
    if item is None:
        return (
            '<div class="market-tile unavailable">'
            f'<span>{_safe(key)}</span><strong>未確認</strong><em>データなし</em></div>'
        )

    change = item.get("change_pct")
    direction = "up" if (change or 0) >= 0 else "down"
    return "\n".join(
        [
            f'<div class="market-tile {direction}">',
            f'  <span>{_safe(item.get("label", key))}</span>',
            f'  <strong>{_safe(_format_tile_value(item))}</strong>',
            f'  <em>{_safe(_format_tile_change(item))}</em>',
            "</div>",
        ]
    )


def _render_world_board(raw_data: dict[str, Any]) -> str:
    lookup = {item.get("key"): item for item in raw_data.get("items", []) + raw_data.get("macro_items", [])}
    sections: list[str] = []
    for group_name, keys in WORLD_BOARD_GROUPS:
        tiles = "\n".join(_render_market_tile(lookup.get(key), key) for key in keys)
        sections.append(
            "\n".join(
                [
                    '<section class="board-group">',
                    f'  <h3>{_safe(group_name)}</h3>',
                    f'  <div class="market-grid">{tiles}</div>',
                    "</section>",
                ]
            )
        )
    return "\n".join(sections)


def _render_chart_board(raw_data: dict[str, Any]) -> str:
    lookup = {item.get("key"): item for item in raw_data.get("items", []) + raw_data.get("macro_items", [])}
    cards: list[str] = []
    for key in CHART_BOARD_KEYS:
        item = lookup.get(key)
        if not item:
            continue
        change = item.get("change_pct")
        direction = "up" if (change or 0) >= 0 else "down"
        color = "#16a34a" if direction == "up" else "#dc2626"
        cards.append(
            "\n".join(
                [
                    f'<article class="chart-card {direction}">',
                    '  <div class="chart-card-head">',
                    f'    <span>{_safe(item.get("label", key))}</span>',
                    f'    <em>{_safe(_format_tile_change(item))}</em>',
                    "  </div>",
                    f'  <strong>{_safe(_format_tile_value(item))}</strong>',
                    f'  {_render_price_sparkline(item.get("series", []), color)}',
                    "</article>",
                ]
            )
        )
    return "\n".join(cards) or '<div class="metric-card">チャートは未確認</div>'


def _render_ticker_strip(raw_data: dict[str, Any]) -> str:
    lookup = {item.get("key"): item for item in raw_data.get("items", []) + raw_data.get("macro_items", [])}
    keys = ["NIKKEI225", "TOPIX", "DOW", "SP500", "NASDAQ", "USDJPY", "US10Y", "VIX"]
    chips: list[str] = []
    for key in keys:
        item = lookup.get(key)
        if not item:
            continue
        change = item.get("change_pct")
        direction = "up" if (change or 0) >= 0 else "down"
        chips.append(
            "\n".join(
                [
                    f'<div class="ticker-chip {direction}">',
                    f'  <span>{_safe(item.get("label", key))}</span>',
                    f'  <strong>{_safe(_format_tile_change(item))}</strong>',
                    "</div>",
                ]
            )
        )
    return "\n".join(chips)


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
    world_board_html = _render_world_board(raw_data)
    chart_board_html = _render_chart_board(raw_data)
    ticker_strip_html = _render_ticker_strip(raw_data)
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
    hero_background = "#ffffff"

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
      --bg: #f3f4f6;
      --panel: #ffffff;
      --line: #e5e7eb;
      --text: #111827;
      --sub: #6b7280;
      --accent: {market_color};
      --good: #166534;
      --bad: #991b1b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Hiragino Sans", "Yu Gothic", "Meiryo", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    .page {{
      max-width: 760px;
      margin: 0 auto;
      padding: 12px 10px 40px;
    }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 12px;
      box-shadow: none;
      margin-bottom: 8px;
    }}
    .hero {{
      position: relative;
      overflow: hidden;
      color: var(--text);
      background: {hero_background};
      border-left: 6px solid var(--accent);
    }}
    .hero > * {{
      position: relative;
      z-index: 1;
    }}
    .eyebrow {{
      font-size: 12px;
      color: var(--sub);
      margin-bottom: 6px;
      font-weight: 800;
    }}
    h1 {{
      font-size: 22px;
      line-height: 1.25;
      margin: 0 0 8px;
    }}
    .theme {{
      font-size: 14px;
      line-height: 1.6;
      color: var(--sub);
      margin-bottom: 10px;
    }}
    .badge {{
      display: inline-block;
      background: #ffffff;
      color: var(--accent);
      border: 1px solid var(--accent);
      border-radius: 999px;
      padding: 5px 10px;
      font-weight: 700;
      font-size: 13px;
      margin-bottom: 10px;
    }}
    .meta {{
      font-size: 12px;
      color: var(--sub);
    }}
    .digest-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 6px;
      margin: 8px 0 0;
    }}
    .digest-tile {{
      border-radius: 4px;
      padding: 8px;
      color: var(--text);
      background: #f9fafb;
      border: 1px solid var(--line);
      min-height: 56px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
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
    .tile-accent, .tile-blue, .tile-green, .tile-gold {{ border-left: 4px solid var(--accent); }}
    .ticker-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(86px, 1fr));
      gap: 6px;
      margin-bottom: 10px;
    }}
    .ticker-chip {{
      min-height: 48px;
      border-radius: 4px;
      padding: 7px;
      color: var(--text);
      background: #ffffff;
      border: 1px solid var(--line);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .ticker-chip span {{
      font-size: 10px;
      font-weight: 800;
      opacity: .9;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .ticker-chip strong {{
      font-size: 14px;
      line-height: 1;
    }}
    .ticker-chip.up {{ border-left: 4px solid #16a34a; }}
    .ticker-chip.down {{ border-left: 4px solid #dc2626; }}
    .ticker-chip.up strong {{ color: #166534; }}
    .ticker-chip.down strong {{ color: #991b1b; }}
    h2 {{
      font-size: 18px;
      margin: 0 0 10px;
      border-bottom: 1px solid var(--line);
      padding: 0 0 8px;
    }}
    h3 {{
      font-size: 15px;
      margin: 0 0 8px;
      color: var(--sub);
    }}
    .world-board {{
      display: grid;
      gap: 8px;
    }}
    .chart-board {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 8px;
    }}
    .chart-card {{
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 8px;
      background: #ffffff;
      box-shadow: none;
      min-height: 148px;
      overflow: hidden;
    }}
    .chart-card-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 6px;
    }}
    .chart-card-head span {{
      color: var(--sub);
      font-size: 12px;
      font-weight: 900;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .chart-card-head em {{
      font-style: normal;
      font-size: 12px;
      font-weight: 900;
    }}
    .chart-card.up .chart-card-head em {{ color: #16a34a; }}
    .chart-card.down .chart-card-head em {{ color: #dc2626; }}
    .chart-card strong {{
      display: block;
      font-size: 20px;
      line-height: 1.2;
      margin-bottom: 8px;
    }}
    .price-chart {{
      width: 100%;
      height: 82px;
      border-radius: 4px;
      background:
        repeating-linear-gradient(0deg, rgba(148,163,184,.18) 0, rgba(148,163,184,.18) 1px, transparent 1px, transparent 22px);
    }}
    .price-chart-empty {{
      display: grid;
      place-items: center;
      height: 92px;
      color: var(--sub);
      border-radius: 12px;
      background: #f8fafc;
      font-size: 13px;
      font-weight: 800;
    }}
    .board-group {{
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 8px;
      background: #ffffff;
    }}
    .market-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(105px, 1fr));
      gap: 6px;
    }}
    .market-tile {{
      min-height: 62px;
      border-radius: 4px;
      padding: 7px;
      color: var(--text);
      background: #ffffff;
      border: 1px solid var(--line);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .market-tile span {{
      font-size: 10px;
      font-weight: 800;
      opacity: .92;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .market-tile strong {{
      font-size: 15px;
      line-height: 1.2;
    }}
    .market-tile em {{
      font-style: normal;
      font-size: 13px;
      font-weight: 900;
    }}
    .market-tile.up {{ border-left: 4px solid #16a34a; }}
    .market-tile.down {{ border-left: 4px solid #dc2626; }}
    .market-tile.unavailable {{ border-left: 4px solid #64748b; }}
    .market-tile.up em {{ color: #166534; }}
    .market-tile.down em {{ color: #991b1b; }}
    .metric-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }}
    .macro-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
    }}
    .macro-card {{
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 8px;
      background: #ffffff;
      min-height: 152px;
      box-shadow: none;
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
      border-radius: 4px;
      padding: 12px 14px;
      background: #ffffff;
      font-size: 16px;
      line-height: 1.6;
      font-weight: 700;
    }}
    .section-image {{
      width: 100%;
      display: block;
      border-radius: 4px;
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
      border-radius: 4px;
      padding: 12px 14px;
      line-height: 1.7;
      font-size: 15px;
    }}
    .opportunity-item, .caution-item {{
      border-radius: 4px;
      padding: 12px 14px;
      line-height: 1.8;
      font-size: 15px;
      border: 1px solid var(--line);
      margin-bottom: 10px;
      list-style: none;
    }}
    .opportunity-item {{ background: #ffffff; color: var(--good); border-left: 4px solid #16a34a; }}
    .caution-item {{ background: #ffffff; color: var(--bad); border-left: 4px solid #dc2626; }}
    .scenario-item {{
      border-radius: 4px;
      padding: 12px 14px;
      line-height: 1.8;
      font-size: 15px;
      border: 1px solid var(--line);
      margin-bottom: 10px;
      list-style: none;
      background: #ffffff;
      border-left: 4px solid #2563eb;
      color: #1e3a8a;
    }}
    .talk {{
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 12px 14px;
      margin-bottom: 10px;
      line-height: 1.8;
    }}
    .talk.teacher {{ background: #ffffff; border-left: 4px solid #f59e0b; }}
    .talk.student {{ background: #ffffff; border-left: 4px solid #2563eb; }}
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
      background: #ffffff;
      border: 1px solid var(--line);
      border-left: 5px solid var(--accent);
      border-radius: 8px;
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
      border-radius: 6px;
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
      <h2>世界マーケットボード</h2>
      <div class="ticker-strip">
        {ticker_strip_html}
      </div>
      <div class="world-board">
        {world_board_html}
      </div>
    </section>

    <section class="panel">
      <h2>主要チャートボード</h2>
      <div class="chart-board">
        {chart_board_html}
      </div>
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

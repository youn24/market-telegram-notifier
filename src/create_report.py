from __future__ import annotations

import html
import shutil
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
HERO_ASSET = BASE_DIR / "assets" / "design" / "market-digest-hero.png"
CHARACTER_DIR = BASE_DIR / "assets" / "characters"

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


def _category_style(task_config: dict[str, Any]) -> dict[str, str]:
    category = str(task_config.get("category", "japan_market"))
    if task_config.get("focus") == "macro":
        category = "macro"
    styles = {
        "macro": {
            "class": "macro",
            "kicker": "MACRO NOTE",
            "label": "マクロ総覧",
            "subtitle": "金利・為替・株・商品を一枚で俯瞰",
            "accent": "#0284c7",
            "accent2": "#ca8a04",
            "soft": "#e0f2fe",
        },
        "japan_market": {
            "class": "japan",
            "kicker": "TOKYO BOARD",
            "label": "日本株",
            "subtitle": "寄り付き・大引け・需給の温度差を見る",
            "accent": "#ea580c",
            "accent2": "#16a34a",
            "soft": "#fff7ed",
        },
        "fx": {
            "class": "fx",
            "kicker": "FX LENS",
            "label": "為替",
            "subtitle": "通貨の強弱と金利差を短く確認",
            "accent": "#7c3aed",
            "accent2": "#0d9488",
            "soft": "#f5f3ff",
        },
        "earnings": {
            "class": "earnings",
            "kicker": "EARNINGS",
            "label": "決算",
            "subtitle": "業績・ガイダンス・市場反応を整理",
            "accent": "#e11d48",
            "accent2": "#d97706",
            "soft": "#fff1f2",
        },
        "after_hours": {
            "class": "after-hours",
            "kicker": "AFTER HOURS",
            "label": "時間外急変",
            "subtitle": "先物・VIX・為替・商品・日本株ADRを複数条件で確認",
            "accent": "#d97706",
            "accent2": "#0284c7",
            "soft": "#fffbeb",
        },
    }
    return styles.get(category, styles["japan_market"])


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


def _render_analysis_dashboard(summary: dict[str, Any]) -> str:
    dashboard = summary.get("analysis_dashboard", {})
    if not dashboard:
        return '<div class="metric-card">分析ダッシュボードは未確認です。</div>'
    score = int(dashboard.get("score", 50))
    band = _safe(str(dashboard.get("band", "中立")))
    breadth = int(dashboard.get("breadth", 50))
    checklist = "".join(
        f'<li>{_safe(line)}</li>'
        for line in summary.get("trade_checklist", [])[:5]
    )
    risk_lines = "".join(
        f'<span>{_safe(line)}</span>'
        for line in dashboard.get("risk_reasons", [])[:3]
    )
    return "\n".join(
        [
            '<div class="pro-analysis">',
            '  <div class="score-orb">',
            f'    <div class="score-number">{score}</div>',
            '    <div class="score-unit">/100</div>',
            f'    <div class="score-band">{band}</div>',
            '  </div>',
            '  <div class="analysis-cards">',
            f'    <article><span>市場の幅</span><strong>{breadth}%</strong><em>上昇銘柄の比率感</em></article>',
            f'    <article><span>追い風</span><strong>{_safe(str(dashboard.get("leader_text", "未確認")))}</strong><em>強い側</em></article>',
            f'    <article><span>逆風</span><strong>{_safe(str(dashboard.get("laggard_text", "未確認")))}</strong><em>弱い側</em></article>',
            f'    <article class="wide"><span>実戦方針</span><strong>{_safe(str(dashboard.get("action", "未確認")))}</strong><em>今日の判断軸</em></article>',
            '  </div>',
            f'  <div class="risk-tape">{risk_lines}</div>',
            f'  <ul class="trade-checklist">{checklist}</ul>',
            '</div>',
        ]
    )


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _movement_class(value: float | None) -> str:
    if value is None:
        return "flat"
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "flat"


def _format_value(item: dict[str, Any]) -> str:
    value = _to_float(item.get("current"))
    unit = str(item.get("unit", ""))
    if value is None:
        return "未確認"
    if abs(value) >= 100:
        return f"{value:,.2f}{unit}"
    return f"{value:.2f}{unit}"


def _format_change(value: float | None) -> str:
    if value is None:
        return "未確認"
    return f"{value:+.2f}%"


def _render_visual_signal_panel(summary: dict[str, Any]) -> str:
    dashboard = summary.get("analysis_dashboard", {})
    score = max(0, min(100, int(_to_float(dashboard.get("score")) or 50)))
    breadth = max(0, min(100, int(_to_float(dashboard.get("breadth")) or 50)))
    band = str(dashboard.get("band", summary.get("conclusion_label", "中立")))
    risk_reasons = dashboard.get("risk_reasons", []) or ["目立つリスク材料は未確認です。"]
    action = str(dashboard.get("action", "追加確認が必要です。"))
    leader = str(dashboard.get("leader_text", "未確認"))
    laggard = str(dashboard.get("laggard_text", "未確認"))
    checklist = summary.get("trade_checklist", [])[:4]
    checklist_html = "".join(f"<li>{_safe(str(line))}</li>" for line in checklist)
    risk_html = "".join(f"<span>{_safe(str(line))}</span>" for line in risk_reasons[:3])
    return "\n".join(
        [
            '<div class="visual-signal">',
            '  <div class="signal-meter-card">',
            '    <span class="signal-kicker">Market Score</span>',
            f'    <strong>{score}</strong>',
            f'    <em>{_safe(band)}</em>',
            f'    <div class="meter-track"><i style="width:{score}%"></i></div>',
            f'    <p>市場の広がり {breadth}% / 強い側: {_safe(leader)} / 弱い側: {_safe(laggard)}</p>',
            '  </div>',
            '  <div class="signal-cards">',
            f'    <article><b class="signal-icon trend"></b><span>流れ</span><strong>{_safe(leader)}</strong></article>',
            f'    <article><b class="signal-icon risk"></b><span>警戒</span><strong>{_safe(str(risk_reasons[0]))}</strong></article>',
            f'    <article><b class="signal-icon action"></b><span>作戦</span><strong>{_safe(action)}</strong></article>',
            '  </div>',
            f'  <div class="risk-radar">{risk_html}</div>',
            f'  <ul class="visual-checklist">{checklist_html}</ul>',
            '</div>',
        ]
    )


def _render_market_heatmap(raw_data: dict[str, Any]) -> str:
    items = [
        item
        for item in [*raw_data.get("items", []), *raw_data.get("macro_items", [])]
        if item.get("label")
    ]
    ranked = sorted(
        items,
        key=lambda item: abs(_to_float(item.get("change_pct")) or 0),
        reverse=True,
    )[:16]
    if not ranked:
        return '<div class="heatmap-empty">ヒートマップは未確認です。</div>'

    cells: list[str] = []
    for item in ranked:
        change = _to_float(item.get("change_pct"))
        klass = _movement_class(change)
        cells.append(
            "\n".join(
                [
                    f'<article class="heatmap-cell {klass}">',
                    f'  <span>{_safe(str(item.get("label", "")))}</span>',
                    f'  <strong>{_safe(_format_value(item))}</strong>',
                    f'  <em>{_safe(_format_change(change))}</em>',
                    '</article>',
                ]
            )
        )
    return '<div class="heatmap-grid">' + "\n".join(cells) + "</div>"


def _render_digest_tiles(summary: dict[str, Any], raw_data: dict[str, Any]) -> str:
    macro_count = len([item for item in raw_data.get("macro_items", []) if item.get("status") == "ok"])
    market_count = len([item for item in raw_data.get("items", []) if item.get("status") == "ok"])
    research_count = len(raw_data.get("research", {}).get("items", []))
    nikkei_status = raw_data.get("nikkei225jp", {}).get("status")
    tiles = [
        ("結論", summary.get("conclusion_label", "様子見"), "tile-accent"),
        ("取得済み", f"市場 {market_count} / マクロ {macro_count}", "tile-blue"),
        ("材料検索", f"{research_count}件" if research_count else "未確認", "tile-green"),
        ("225参照", "確認済み" if nikkei_status == "ok" else "未確認", "tile-blue"),
        ("作戦", "3シナリオで確認", "tile-gold"),
    ]
    return "\n".join(
        f'<div class="digest-tile {klass}"><span>{_safe(label)}</span><strong>{_safe(value)}</strong></div>'
        for label, value, klass in tiles
    )


def _render_nikkei225jp_reference(raw_data: dict[str, Any]) -> str:
    data = raw_data.get("nikkei225jp", {}) or {}
    status = data.get("status")
    source_url = _safe(str(data.get("url", "https://nikkei225jp.com/")))
    fetched_at = _safe(str(data.get("fetched_at", "未確認")))
    note = _safe(str(data.get("note", "nikkei225jp.com参照は未確認です。")))

    if status != "ok":
        return "\n".join(
            [
                '<div class="nikkei-reference unavailable">',
                "  <h3>nikkei225jp.com参照</h3>",
                f"  <p>{note}</p>",
                f'  <a href="{source_url}" target="_blank" rel="noopener">nikkei225jp.comを開く</a>',
                "</div>",
            ]
        )

    links = data.get("content_links", [])[:14]
    schedules = data.get("schedule_items", [])[:10]
    notes = data.get("watch_notes", [])[:4]

    link_html = "\n".join(
        f'<a href="{_safe(str(item.get("url", "")))}" target="_blank" rel="noopener">{_safe(str(item.get("label", "未確認")))}</a>'
        for item in links
    ) or '<span class="nikkei-empty">参照リンクは未確認</span>'
    schedule_html = "\n".join(
        f'<li><strong>{_safe(str(item.get("date", "未確認")))}</strong><span>{_safe(str(item.get("event", "未確認")))}</span></li>'
        for item in schedules
    ) or '<li><strong>未確認</strong><span>経済スケジュールは取得できませんでした。</span></li>'
    note_html = "\n".join(f"<li>{_safe(str(note_item))}</li>" for note_item in notes)

    return "\n".join(
        [
            '<div class="nikkei-reference">',
            "  <div>",
            "    <h3>nikkei225jp.com参照</h3>",
            f"    <p>{note}</p>",
            f"    <small>参照時刻: {fetched_at}</small>",
            "  </div>",
            '  <div class="nikkei-link-grid">',
            link_html,
            "  </div>",
            '  <div class="nikkei-watch-grid">',
            "    <article>",
            "      <h4>時間外チェック</h4>",
            f"      <ul>{note_html}</ul>",
            "    </article>",
            "    <article>",
            "      <h4>スケジュール候補</h4>",
            f"      <ul>{schedule_html}</ul>",
            "    </article>",
            "  </div>",
            "</div>",
        ]
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
    return f'<svg class="sparkline" viewBox="0 0 120 52" aria-hidden="true"><polyline class="chart-line" points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>'


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
            f'  <polyline class="chart-line" points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>',
            '  <line x1="8" y1="86" x2="184" y2="86" stroke="rgba(100,116,139,.24)" stroke-width="2"/>',
            "</svg>",
        ]
    )


def _render_macro_cards(items: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for item in items:
        change = item.get("change_pct")
        change_bps = item.get("change_bps")
        if isinstance(change_bps, (int, float)):
            change_text = f"{change_bps:+.1f}bp"
        else:
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


def _render_theme_board(raw_data: dict[str, Any]) -> str:
    snapshot = raw_data.get("themes", {}) or {}
    rows = snapshot.get("themes", []) or []
    if not rows:
        return '<div class="theme-empty">テーマ株は対象外、または未確認です。</div>'

    cards: list[str] = []
    for theme in rows:
        status = theme.get("status")
        direction = theme.get("direction", "neutral") if status == "ok" else "unavailable"
        average = theme.get("average_change_pct")
        average_text = f"{average:+.2f}%" if isinstance(average, (int, float)) else "未確認"
        breadth_key = "breadth_down_pct" if direction == "bear" else "breadth_up_pct"
        breadth = theme.get(breadth_key)
        breadth_text = f"{breadth:.0f}%" if isinstance(breadth, (int, float)) else "未確認"
        score = theme.get("confirmation_score")
        score_text = str(score) if isinstance(score, int) else "未確認"
        valid_count = theme.get("valid_count", 0)
        total_count = theme.get("total_count", 0)

        leaders = []
        for member in theme.get("leaders", [])[:3]:
            change = member.get("change_pct")
            change_text = f"{change:+.2f}%" if isinstance(change, (int, float)) else "未確認"
            leaders.append(
                f'<li><span>{_safe(member.get("label", member.get("ticker", "未確認")))}</span>'
                f'<strong>{_safe(change_text)}</strong></li>'
            )
        leaders_html = "".join(leaders) or "<li><span>主導銘柄</span><strong>未確認</strong></li>"
        note = theme.get("note") or "複数銘柄の等ウェイト平均と騰落の広がりで判定"
        cards.append(
            "\n".join(
                [
                    f'<article class="theme-card {direction}">',
                    '  <div class="theme-card-head">',
                    f'    <h3>{_safe(theme.get("label", "テーマ株"))}</h3>',
                    f'    <span>{_safe(theme.get("signal", "未確認"))}</span>',
                    "  </div>",
                    '  <div class="theme-stats">',
                    f'    <div><small>平均騰落</small><strong>{_safe(average_text)}</strong></div>',
                    f'    <div><small>同方向</small><strong>{_safe(breadth_text)}</strong></div>',
                    f'    <div><small>取得</small><strong>{_safe(f"{valid_count}/{total_count}")}</strong></div>',
                    f'    <div><small>確認度</small><strong>{_safe(score_text)}</strong></div>',
                    "  </div>",
                    f'  <ul class="theme-leaders">{leaders_html}</ul>',
                    f'  <p>{_safe(note)}</p>',
                    "</article>",
                ]
            )
        )
    return '<div class="theme-board">' + "\n".join(cards) + "</div>"


def _render_money_flow_board(summary: dict[str, Any]) -> str:
    flow = summary.get("money_flow", {}) or {}
    rows = flow.get("rows", []) or []
    if not rows:
        return '<div class="flow-empty">資金方向は未確認です。</div>'

    cards = []
    for row in rows:
        direction = row.get("direction", "neutral") if row.get("status") == "verified" else "unavailable"
        cards.append(
            "\n".join(
                [
                    f'<article class="flow-card {direction}">',
                    f'  <span>{_safe(row.get("label", "未確認"))}</span>',
                    f'  <strong>{_safe(row.get("signal", "未確認"))}</strong>',
                    f'  <em>{_safe(row.get("evidence", "未確認"))}</em>',
                    "</article>",
                ]
            )
        )
    return "\n".join(
        [
            '<div class="flow-headline">',
            f'  <small>{_safe(flow.get("label", "価格から見た資金方向"))}</small>',
            f'  <strong>{_safe(flow.get("headline", "未確認"))}</strong>',
            "</div>",
            f'<div class="flow-board">{"".join(cards)}</div>',
            f'<p class="flow-note">{_safe(flow.get("actual_flow_note", "実際の資金流入額は未確認です。"))}</p>',
        ]
    )


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


def _character_sources(tone: str) -> tuple[Path, Path]:
    suffix = {"bull": "bull", "bear": "bear", "neutral": "ai"}.get(tone, "ai")
    return (
        CHARACTER_DIR / f"elephant-{suffix}.png",
        CHARACTER_DIR / f"otter-{suffix}.png",
    )


def _render_dialogue(dialogue: list[dict[str, str]], elephant_asset: str | None, otter_asset: str | None) -> str:
    blocks: list[str] = []
    for item in dialogue:
        role = item.get("role", "teacher")
        role_class = "student" if role == "student" else "teacher"
        asset = otter_asset if role_class == "student" else elephant_asset
        avatar = f'<img src="assets/{_safe(asset)}" alt="{_safe(item.get("speaker", ""))}" class="talk-avatar">' if asset else ""
        blocks.append(
            "\n".join(
                [
                    f'<section class="talk {role_class}">',
                    f"  {avatar}",
                    '  <div class="talk-bubble">',
                    f'    <div class="talk-role">{_safe(item.get("speaker", ""))}</div>',
                    f'    <div class="talk-text">{_safe(item.get("text", ""))}</div>',
                    "  </div>",
                    "</section>",
                ]
            )
        )
    return "\n".join(blocks)


def _render_analysis_summary(summary: dict[str, Any], elephant_asset: str | None, otter_asset: str | None) -> str:
    elephant = f'<img src="assets/{_safe(elephant_asset)}" alt="ガネーシャ先生" class="summary-character">' if elephant_asset else ""
    otter = f'<img src="assets/{_safe(otter_asset)}" alt="カワウソくん" class="summary-character">' if otter_asset else ""
    comments = _render_list(summary.get("commentary", [])[:3], "memo-item")
    return "\n".join(
        [
            '<div class="analysis-summary">',
            f'  <div class="summary-characters">{elephant}{otter}</div>',
            '  <ul class="memo-list summary-memos">',
            f"    {comments}",
            "  </ul>",
            "</div>",
        ]
    )


def _render_hero_illustration(summary: dict[str, Any], elephant_asset: str | None, otter_asset: str | None) -> str:
    elephant = f'<img src="assets/{_safe(elephant_asset)}" alt="ガネーシャ先生" class="hero-character ganesha">' if elephant_asset else ""
    otter = f'<img src="assets/{_safe(otter_asset)}" alt="カワウソくん" class="hero-character otter">' if otter_asset else ""
    label = _safe(summary.get("conclusion_label", "様子見"))
    return "\n".join(
        [
            '<div class="hero-visual" aria-label="相場ナビゲーター">',
            '  <div class="pulse-ring"></div>',
            '  <div class="orbit-dot dot-a"></div>',
            '  <div class="orbit-dot dot-b"></div>',
            f"  {elephant}",
            f"  {otter}",
            f'  <div class="hero-visual-label">{label}</div>',
            "</div>",
        ]
    )


def _render_bullets(items: list[str], css_class: str) -> str:
    rows = []
    for item in items:
        rows.append(f'<li class="{css_class}">{_safe(item)}</li>')
    return "\n".join(rows)


def _render_research_cards(summary: dict[str, Any]) -> str:
    items = summary.get("research_items", [])
    if not items:
        return f'<div class="research-card unavailable">{_safe(summary.get("research_note", "材料検索は未確認"))}</div>'

    cards: list[str] = []
    confidence = _safe(summary.get("research_confidence_line", "リサーチ信頼度: 未確認"))
    cards.append(f'<div class="research-confidence">{confidence}</div>')
    coverage_lines = summary.get("research_coverage_lines", [])
    if coverage_lines:
        coverage_items = "".join(f"<li>{_safe(line)}</li>" for line in coverage_lines[:6])
        cards.append(f'<ul class="research-coverage">{coverage_items}</ul>')
    evidence_lines = summary.get("research_evidence_briefs") or summary.get("research_evidence_lines", [])
    if evidence_lines:
        evidence_items = "".join(f"<li>{_safe(line)}</li>" for line in evidence_lines[:6])
        cards.append(f'<ul class="research-evidence">{evidence_items}</ul>')
    theme_html = "".join(f'<div class="research-theme-chip">{_safe(line.replace("重要テーマ: ", ""))}</div>' for line in summary.get("research_theme_lines", [])[:4])
    if theme_html:
        cards.append(f'<div class="research-themes">{theme_html}</div>')
    for item in items[:6]:
        url = item.get("url", "")
        title = _safe(item.get("title", "未確認"))
        source = _safe(item.get("source", "媒体未確認"))
        published = _safe(item.get("published", "日時未確認"))
        score = _safe(str(item.get("score", "未採点")))
        reason = _safe(item.get("research_reason", ""))
        title_html = f'<a href="{_safe(url)}" target="_blank" rel="noopener noreferrer">{title}</a>' if url else title
        cards.append(
            "\n".join(
                [
                    '<article class="research-card">',
                    f'  <div class="research-meta">{source} / {published} / score {score}</div>',
                    f'  <div class="research-title">{title_html}</div>',
                    f'  <div class="research-reason">{reason}</div>',
                    "</article>",
                ]
            )
        )
    return "\n".join(cards)


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
    design_direction: dict[str, Any] | None = None,
) -> Path:
    site_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = site_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    copied_card = _copy_if_exists(card_path, assets_dir / "summary-card.png")
    copied_chart = _copy_if_exists(chart_path, assets_dir / "market-chart.png")
    copied_hero = _copy_if_exists(HERO_ASSET, assets_dir / "market-digest-hero.png")
    elephant_source, otter_source = _character_sources(summary.get("market_tone", "neutral"))
    copied_elephant = _copy_if_exists(elephant_source, assets_dir / "ganesha-sensei.png")
    copied_otter = _copy_if_exists(otter_source, assets_dir / "kawauso-kun.png")

    market_label, market_color = _market_label(summary.get("market_tone", "neutral"))
    category_style = _category_style(task_config)
    digest_tiles_html = _render_digest_tiles(summary, raw_data)
    world_board_html = _render_world_board(raw_data)
    theme_board_html = _render_theme_board(raw_data)
    money_flow_html = _render_money_flow_board(summary)
    chart_board_html = _render_chart_board(raw_data)
    ticker_strip_html = _render_ticker_strip(raw_data)
    metrics_html = _render_metrics(summary.get("metrics", [])[:5])
    market_metrics_html = _render_metrics(summary.get("market_metrics", [])[:5])
    macro_cards_html = _render_macro_cards(raw_data.get("macro_items", []))
    analysis_dashboard_html = _render_analysis_dashboard(summary)
    visual_signal_html = _render_visual_signal_panel(summary)
    market_heatmap_html = _render_market_heatmap(raw_data)
    signals_html = _render_list(summary.get("signals", [])[:4], "signal-item")
    commentary_html = _render_list(summary.get("commentary", [])[:3], "memo-item")
    opportunity_html = _render_bullets(summary.get("opportunities", [])[:3], "opportunity-item")
    caution_html = _render_bullets(summary.get("cautions", [])[:3], "caution-item")
    dialogue_html = _render_dialogue(summary.get("dialogue", []), copied_elephant, copied_otter)
    analysis_summary_html = _render_analysis_summary(summary, copied_elephant, copied_otter)
    hero_illustration_html = _render_hero_illustration(summary, copied_elephant, copied_otter)
    scenario_html = _render_bullets(summary.get("scenarios", [])[:3], "scenario-item")
    research_html = _render_research_cards(summary)
    nikkei225jp_html = _render_nikkei225jp_reference(raw_data)
    data_quality = summary.get("data_quality", {}) or {}
    quality_unavailable = "、".join(data_quality.get("unavailable_labels", [])) or "なし"
    data_quality_html = f"""
      <div class="quality-strip">
        <strong>{_safe(data_quality.get("badge", "確認済 0/0"))}</strong>
        <span>{_safe(data_quality.get("as_of_label", "基準日 未確認"))}</span>
        <em>未確認: {_safe(quality_unavailable)}</em>
      </div>
    """
    design_direction = design_direction or {}
    selected_canva_name = _safe(str(design_direction.get("canva_candidate_name", "Canva候補はdesign-brief.mdで確認")))
    selected_canva_url = _safe(str(design_direction.get("canva_candidate_url", "design-brief.md")))
    selected_canva_reason = _safe(str(design_direction.get("canva_candidate_reason", "今回の相場に合わせた候補を表示します。")))
    selected_adobe_name = _safe(str(design_direction.get("adobe_concept_name", "Adobe制作候補")))
    selected_adobe_reason = _safe(str(design_direction.get("adobe_concept_reason", "Adobe Express / Illustrator向けの制作方針です。")))
    design_tools_html = f"""
      <div class="design-actions">
        <a class="design-pill primary" href="design-brief.md">Canva / Adobe 用デザイン指示書</a>
        <a class="design-pill primary" href="{selected_canva_url}">{selected_canva_name}</a>
        <span class="design-pill">チャート最優先</span>
        <span class="design-pill">文字背景あり</span>
        <span class="design-pill">未確認は明示</span>
      </div>
      <div class="selected-designs">
        <article>
          <span>今回のCanva候補</span>
          <strong>{selected_canva_name}</strong>
          <em>{selected_canva_reason}</em>
        </article>
        <article>
          <span>Adobe候補</span>
          <strong>{selected_adobe_name}</strong>
          <em>{selected_adobe_reason}</em>
        </article>
      </div>
      <div class="visual-principles">
        <div><strong>1. 先に結論</strong><span>強気・警戒・様子見を最上部で判断できます。</span></div>
        <div><strong>2. 次に数字</strong><span>重要指標と前日比ランキングを大きく表示します。</span></div>
        <div><strong>3. 最後に作戦</strong><span>先生とカワウソ君の会話で行動に落とします。</span></div>
      </div>
    """

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
      --bg: #eef3f8;
      --panel: #ffffff;
      --line: #dbe3ee;
      --text: #111827;
      --sub: #475569;
      --accent: {market_color};
      --category: {category_style["accent"]};
      --category-2: {category_style["accent2"]};
      --category-soft: {category_style["soft"]};
      --good: #166534;
      --bad: #991b1b;
      --soft-blue: #eef7ff;
      --soft-gold: #fff7df;
      --soft-green: #effaf3;
      --soft-red: #fff1f2;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Hiragino Sans", "Yu Gothic", "Meiryo", sans-serif;
      background:
        radial-gradient(circle at top left, color-mix(in srgb, var(--accent) 18%, transparent), transparent 34%),
        linear-gradient(180deg, #f8fbff 0%, var(--bg) 340px);
      color: var(--text);
      font-size: 17px;
    }}
    .page {{
      max-width: 1040px;
      margin: 0 auto;
      padding: 18px 14px 48px;
    }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 14px 34px rgba(15, 23, 42, .08);
      margin-bottom: 16px;
      animation: fadeUp .48s ease both;
    }}
    .hero {{
      position: relative;
      overflow: hidden;
      color: var(--text);
      background:
        linear-gradient(135deg, color-mix(in srgb, var(--category) 13%, white), #ffffff 54%),
        {hero_background};
      border-left: 10px solid var(--category);
    }}
    .hero::after {{
      content: "{_safe(category_style["kicker"])}";
      position: absolute;
      right: 18px;
      top: 14px;
      color: color-mix(in srgb, var(--category) 20%, transparent);
      font-size: clamp(34px, 8vw, 84px);
      font-weight: 1000;
      line-height: 1;
      pointer-events: none;
    }}
    .hero > * {{
      position: relative;
      z-index: 1;
    }}
    .hero-layout {{
      display: grid;
      grid-template-columns: 1fr 210px;
      gap: 18px;
      align-items: center;
    }}
    .hero-visual {{
      position: relative;
      min-height: 190px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background:
        radial-gradient(circle at 52% 44%, color-mix(in srgb, var(--accent) 16%, white), transparent 42%),
        #f8fafc;
      overflow: hidden;
    }}
    .hero-character {{
      position: absolute;
      width: 88px;
      height: 88px;
      object-fit: contain;
      filter: drop-shadow(0 10px 14px rgba(15, 23, 42, .14));
      animation: floatSoft 4.2s ease-in-out infinite;
    }}
    .hero-character.ganesha {{
      left: 18px;
      bottom: 36px;
    }}
    .hero-character.otter {{
      right: 16px;
      bottom: 20px;
      width: 76px;
      height: 76px;
      animation-delay: .7s;
    }}
    .hero-visual-label {{
      position: absolute;
      left: 50%;
      bottom: 10px;
      transform: translateX(-50%);
      background: #ffffff;
      border: 1px solid var(--accent);
      color: var(--accent);
      border-radius: 999px;
      padding: 5px 10px;
      font-size: 12px;
      font-weight: 900;
      white-space: nowrap;
    }}
    .pulse-ring {{
      position: absolute;
      left: 50%;
      top: 50%;
      width: 78px;
      height: 78px;
      border: 2px solid color-mix(in srgb, var(--accent) 50%, transparent);
      border-radius: 999px;
      transform: translate(-50%, -50%);
      animation: pulseRing 2.8s ease-out infinite;
    }}
    .orbit-dot {{
      position: absolute;
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: var(--accent);
      opacity: .75;
      animation: orbitDot 5s linear infinite;
    }}
    .dot-a {{
      left: 28px;
      top: 26px;
    }}
    .dot-b {{
      right: 34px;
      top: 44px;
      animation-delay: 1.6s;
    }}
    .eyebrow {{
      font-size: 14px;
      color: var(--category);
      margin-bottom: 6px;
      font-weight: 900;
      letter-spacing: .04em;
    }}
    .category-ribbon {{
      display: inline-grid;
      grid-template-columns: auto auto;
      gap: 8px 10px;
      align-items: center;
      margin-bottom: 12px;
      padding: 8px 11px;
      border: 1px solid color-mix(in srgb, var(--category) 46%, var(--line));
      border-left: 7px solid var(--category);
      border-radius: 6px;
      background: color-mix(in srgb, var(--category-soft) 74%, white);
      box-shadow: inset 0 -3px 0 color-mix(in srgb, var(--category) 18%, transparent);
    }}
    .category-ribbon span {{
      color: var(--category);
      font-size: 12px;
      font-weight: 1000;
      letter-spacing: .08em;
    }}
    .category-ribbon strong {{
      color: #0f172a;
      font-size: 18px;
      font-weight: 1000;
      line-height: 1.1;
    }}
    .category-ribbon em {{
      grid-column: 1 / -1;
      color: #334155;
      font-style: normal;
      font-size: 13px;
      font-weight: 850;
    }}
    h1 {{
      font-size: clamp(28px, 4vw, 42px);
      line-height: 1.25;
      margin: 0 0 12px;
      text-decoration: underline;
      text-decoration-color: color-mix(in srgb, var(--category) 38%, transparent);
      text-decoration-thickness: 6px;
      text-underline-offset: 7px;
    }}
    .theme {{
      font-size: 17px;
      line-height: 1.75;
      color: #334155;
      margin-bottom: 14px;
      background: #ffffffcc;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 10px 12px;
    }}
    .badge {{
      display: inline-block;
      background: color-mix(in srgb, var(--accent) 12%, white);
      color: var(--accent);
      border: 1px solid var(--accent);
      border-radius: 999px;
      padding: 7px 13px;
      font-weight: 900;
      font-size: 15px;
      margin-bottom: 12px;
    }}
    .meta {{
      display: inline-block;
      font-size: 14px;
      font-weight: 800;
      color: var(--sub);
      background: #f8fafc;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 8px 10px;
    }}
    .quality-strip {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 12px;
      padding: 12px 14px;
      border: 1px solid #bfd3e8;
      border-radius: 14px;
      background: #f5f9fd;
      color: #334155;
    }}
    .quality-strip strong {{ color: #0369a1; }}
    .quality-strip span {{ font-weight: 800; }}
    .quality-strip em {{ color: #64748b; font-style: normal; }}
    .digest-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
      margin: 14px 0 0;
    }}
    .digest-tile {{
      border-radius: 14px;
      padding: 12px;
      color: var(--text);
      background: #f9fafb;
      border: 1px solid var(--line);
      min-height: 74px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform .18s ease, border-color .18s ease, background .18s ease;
    }}
    .digest-tile:hover {{
      transform: translateY(-2px);
      border-color: color-mix(in srgb, var(--accent) 45%, var(--line));
      background: #ffffff;
    }}
    .digest-tile span {{
      font-size: 12px;
      opacity: .86;
      font-weight: 800;
    }}
    .digest-tile strong {{
      font-size: 20px;
      line-height: 1.35;
    }}
    .design-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }}
    .design-pill {{
      display: inline-flex;
      align-items: center;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 8px 13px;
      background: #f8fafc;
      color: #334155;
      font-size: 14px;
      font-weight: 900;
      text-decoration: none;
    }}
    .design-pill.primary {{
      color: #ffffff;
      background: linear-gradient(135deg, #0f172a, color-mix(in srgb, var(--accent) 72%, #0f172a));
      border-color: color-mix(in srgb, var(--accent) 55%, #0f172a);
      box-shadow: 0 12px 26px color-mix(in srgb, var(--accent) 18%, transparent);
    }}
    .selected-designs {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
      margin-top: 14px;
    }}
    .selected-designs article {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 16px;
      background:
        linear-gradient(135deg, #ffffff 0%, color-mix(in srgb, var(--accent) 8%, white) 100%);
      box-shadow: 0 10px 22px rgba(15, 23, 42, .06);
    }}
    .selected-designs span {{
      display: block;
      color: var(--sub);
      font-size: 13px;
      font-weight: 900;
      margin-bottom: 8px;
    }}
    .selected-designs strong {{
      display: block;
      color: #0f172a;
      font-size: 18px;
      line-height: 1.5;
    }}
    .selected-designs em {{
      display: block;
      margin-top: 8px;
      color: var(--accent);
      font-style: normal;
      font-size: 13px;
      font-weight: 850;
      line-height: 1.55;
    }}
    .visual-principles {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-top: 14px;
    }}
    .visual-principles div {{
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px 15px;
      background:
        linear-gradient(135deg, #ffffff 0%, color-mix(in srgb, var(--accent) 7%, white) 100%);
      min-height: 104px;
    }}
    .visual-principles strong {{
      display: block;
      color: var(--accent);
      font-size: 17px;
      margin-bottom: 8px;
    }}
    .visual-principles span {{
      display: block;
      color: #334155;
      font-size: 15px;
      font-weight: 800;
      line-height: 1.65;
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
      animation: fadeUp .5s ease both;
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
      font-size: 24px;
      margin: -2px -2px 16px;
      border-bottom: 0;
      padding: 10px 14px;
      color: #0f172a;
      background: linear-gradient(90deg, var(--soft-blue), #ffffff);
      border-left: 7px solid var(--accent);
      border-radius: 14px;
    }}
    h3 {{
      font-size: 17px;
      margin: 0 0 8px;
      color: var(--sub);
    }}
    .world-board {{
      display: grid;
      gap: 8px;
    }}
    .theme-board {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 14px;
    }}
    .theme-card {{
      padding: 18px;
      border: 1px solid #cbd5e1;
      border-top: 5px solid #64748b;
      border-radius: 18px;
      background: #ffffff;
      box-shadow: 0 12px 26px rgba(15, 23, 42, .08);
    }}
    .theme-card.bull {{ border-top-color: #16a34a; background: linear-gradient(180deg, #f0fdf4, #ffffff 42%); }}
    .theme-card.bear {{ border-top-color: #dc2626; background: linear-gradient(180deg, #fef2f2, #ffffff 42%); }}
    .theme-card.unavailable {{ color: #64748b; background: #f8fafc; }}
    .theme-card-head {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
    .theme-card-head h3 {{ margin: 0; color: #0f172a; font-size: 22px; }}
    .theme-card-head span {{ padding: 6px 12px; border-radius: 999px; background: #e2e8f0; font-weight: 900; }}
    .theme-card.bull .theme-card-head span {{ color: #166534; background: #dcfce7; }}
    .theme-card.bear .theme-card-head span {{ color: #991b1b; background: #fee2e2; }}
    .theme-stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 16px 0; }}
    .theme-stats div {{ padding: 10px 6px; border-radius: 12px; text-align: center; background: rgba(226, 232, 240, .66); }}
    .theme-stats small {{ display: block; color: #64748b; font-size: 12px; font-weight: 800; }}
    .theme-stats strong {{ display: block; margin-top: 4px; color: #0f172a; font-size: 18px; }}
    .theme-leaders {{ margin: 0; padding: 0; list-style: none; }}
    .theme-leaders li {{ display: flex; justify-content: space-between; gap: 12px; padding: 8px 4px; border-bottom: 1px solid #e2e8f0; }}
    .theme-leaders strong {{ color: #0f172a; }}
    .theme-card p {{ margin: 12px 0 0; color: #64748b; font-size: 13px; line-height: 1.5; }}
    .theme-empty {{ padding: 20px; border-radius: 14px; color: #64748b; background: #f8fafc; }}
    .flow-headline {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 14px;
      padding: 16px 18px;
      border-radius: 16px;
      color: #e0f2fe;
      background: linear-gradient(135deg, #082f49, #0f172a);
    }}
    .flow-headline small {{ color: #7dd3fc; font-size: 13px; font-weight: 900; }}
    .flow-headline strong {{ font-size: 20px; text-align: right; }}
    .flow-board {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .flow-card {{ display: grid; gap: 7px; min-height: 118px; padding: 16px; border: 1px solid #cbd5e1; border-left: 6px solid #64748b; border-radius: 15px; background: #fff; }}
    .flow-card.bull {{ border-left-color: #16a34a; background: #f0fdf4; }}
    .flow-card.bear {{ border-left-color: #dc2626; background: #fef2f2; }}
    .flow-card.unavailable {{ color: #64748b; background: #f8fafc; }}
    .flow-card span {{ color: #64748b; font-size: 13px; font-weight: 900; }}
    .flow-card strong {{ color: #0f172a; font-size: 19px; }}
    .flow-card em {{ color: #475569; font-size: 13px; font-style: normal; line-height: 1.45; }}
    .flow-note {{ margin: 14px 2px 0; color: #64748b; font-size: 13px; line-height: 1.6; }}
    .flow-empty {{ padding: 20px; border-radius: 14px; color: #64748b; background: #f8fafc; }}
    .chart-board {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
    }}
    .chart-card {{
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 13px;
      background: #ffffff;
      box-shadow: 0 8px 18px rgba(15, 23, 42, .06);
      min-height: 174px;
      overflow: hidden;
      transition: transform .18s ease, border-color .18s ease;
    }}
    .chart-card:hover {{
      transform: translateY(-2px);
      border-color: color-mix(in srgb, var(--accent) 42%, var(--line));
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
      font-size: 14px;
      font-weight: 900;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .chart-card-head em {{
      font-style: normal;
      font-size: 14px;
      font-weight: 900;
      border-radius: 999px;
      padding: 4px 8px;
      background: #f8fafc;
    }}
    .chart-card.up .chart-card-head em {{ color: #16a34a; }}
    .chart-card.down .chart-card-head em {{ color: #dc2626; }}
    .chart-card strong {{
      display: block;
      font-size: 26px;
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
    .chart-line {{
      stroke-dasharray: 420;
      stroke-dashoffset: 420;
      animation: drawLine 1.25s ease forwards;
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
      border-radius: 16px;
      padding: 12px;
      background: #ffffff;
    }}
    .market-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(105px, 1fr));
      gap: 10px;
    }}
    .market-tile {{
      min-height: 78px;
      border-radius: 14px;
      padding: 10px;
      color: var(--text);
      background: #ffffff;
      border: 1px solid var(--line);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform .16s ease, background .16s ease;
    }}
    .market-tile:hover {{
      transform: translateY(-1px);
      background: #f8fafc;
    }}
    .market-tile span {{
      font-size: 12px;
      font-weight: 800;
      opacity: .92;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .market-tile strong {{
      font-size: 19px;
      line-height: 1.2;
    }}
    .market-tile em {{
      font-style: normal;
      font-size: 15px;
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
      border-radius: 15px;
      padding: 14px 16px;
      background: #ffffff;
      font-size: 18px;
      line-height: 1.75;
      font-weight: 800;
      box-shadow: 0 8px 18px rgba(15, 23, 42, .05);
    }}
    .pro-analysis {{
      display: grid;
      grid-template-columns: 210px 1fr;
      gap: 16px;
      align-items: stretch;
    }}
    .score-orb {{
      min-height: 210px;
      border-radius: 28px;
      background:
        radial-gradient(circle at 50% 30%, color-mix(in srgb, var(--accent) 32%, white), transparent 54%),
        linear-gradient(160deg, #0f172a, #10243a);
      color: #ffffff;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      border: 1px solid color-mix(in srgb, var(--accent) 50%, #334155);
      box-shadow: 0 18px 34px rgba(15, 23, 42, .22);
    }}
    .score-number {{
      font-size: 64px;
      line-height: .95;
      font-weight: 1000;
      letter-spacing: -.04em;
    }}
    .score-unit {{
      color: #bfdbfe;
      font-weight: 900;
      margin-top: 4px;
    }}
    .score-band {{
      margin-top: 14px;
      border: 1px solid color-mix(in srgb, var(--accent) 65%, white);
      border-radius: 999px;
      padding: 7px 14px;
      color: #ffffff;
      font-weight: 1000;
      background: color-mix(in srgb, var(--accent) 28%, transparent);
    }}
    .analysis-cards {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }}
    .analysis-cards article {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 16px;
      background:
        linear-gradient(135deg, #ffffff, color-mix(in srgb, var(--accent) 6%, white));
      min-height: 112px;
    }}
    .analysis-cards article.wide {{
      grid-column: 1 / -1;
      border-left: 8px solid var(--accent);
    }}
    .analysis-cards span {{
      display: block;
      color: var(--sub);
      font-size: 13px;
      font-weight: 900;
      margin-bottom: 7px;
    }}
    .analysis-cards strong {{
      display: block;
      font-size: 18px;
      line-height: 1.55;
      color: #0f172a;
    }}
    .analysis-cards em {{
      display: block;
      margin-top: 8px;
      color: var(--accent);
      font-style: normal;
      font-size: 12px;
      font-weight: 900;
    }}
    .risk-tape {{
      grid-column: 1 / -1;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}
    .risk-tape span {{
      border-radius: 999px;
      padding: 8px 11px;
      background: #fff7ed;
      border: 1px solid #fed7aa;
      color: #9a3412;
      font-size: 13px;
      font-weight: 900;
    }}
    .trade-checklist {{
      grid-column: 1 / -1;
      list-style: none;
      display: grid;
      gap: 8px;
      padding: 0;
      margin: 12px 0 0;
    }}
    .trade-checklist li {{
      border-radius: 14px;
      padding: 12px 14px;
      background: #f8fafc;
      border: 1px solid var(--line);
      font-weight: 850;
      line-height: 1.65;
    }}
    .terminal-panel {{
      color: #e5f4ff;
      background:
        radial-gradient(circle at 0% 0%, rgba(56, 189, 248, .24), transparent 32%),
        radial-gradient(circle at 100% 8%, rgba(245, 158, 11, .16), transparent 28%),
        linear-gradient(145deg, #07111d 0%, #0b1726 58%, #07111d 100%);
      border-color: rgba(96, 165, 250, .42);
      box-shadow: 0 24px 58px rgba(2, 6, 23, .32);
    }}
    .terminal-panel h2,
    .terminal-panel h3 {{
      color: #f8fafc;
      background: rgba(15, 23, 42, .72);
      border-color: #38bdf8;
    }}
    .terminal-panel h3 {{
      margin: 18px 0 12px;
      padding: 9px 12px;
      border-left: 6px solid #38bdf8;
      border-radius: 14px;
    }}
    .visual-signal {{
      display: grid;
      grid-template-columns: minmax(210px, .8fr) 1.4fr;
      gap: 14px;
      margin-bottom: 16px;
    }}
    .signal-meter-card {{
      border: 1px solid rgba(96, 165, 250, .36);
      border-radius: 22px;
      padding: 18px;
      background: linear-gradient(160deg, rgba(15, 23, 42, .92), rgba(8, 47, 73, .74));
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .04);
    }}
    .signal-kicker {{
      display: block;
      color: #7dd3fc;
      font-size: 12px;
      font-weight: 1000;
      letter-spacing: .08em;
      text-transform: uppercase;
    }}
    .signal-meter-card strong {{
      display: inline-block;
      font-size: 70px;
      line-height: 1;
      margin-top: 8px;
      letter-spacing: -.06em;
    }}
    .signal-meter-card em {{
      display: inline-block;
      margin-left: 10px;
      color: #fde68a;
      font-style: normal;
      font-weight: 1000;
      vertical-align: super;
    }}
    .signal-meter-card p {{
      margin: 12px 0 0;
      color: #cbd5e1;
      font-size: 14px;
      line-height: 1.7;
      font-weight: 800;
    }}
    .meter-track {{
      height: 12px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(148, 163, 184, .22);
      margin-top: 12px;
    }}
    .meter-track i {{
      display: block;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, #ef4444, #f59e0b 48%, #22c55e);
      box-shadow: 0 0 18px rgba(34, 197, 94, .38);
    }}
    .signal-cards {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }}
    .signal-cards article {{
      border: 1px solid rgba(96, 165, 250, .32);
      border-radius: 18px;
      padding: 14px;
      background: rgba(15, 23, 42, .68);
      min-height: 136px;
    }}
    .signal-cards span {{
      display: block;
      color: #93c5fd;
      font-size: 13px;
      font-weight: 1000;
      margin: 10px 0 6px;
    }}
    .signal-cards strong {{
      display: block;
      color: #f8fafc;
      font-size: 15px;
      line-height: 1.65;
    }}
    .signal-icon {{
      display: inline-grid;
      place-items: center;
      width: 36px;
      height: 36px;
      border-radius: 12px;
      background: rgba(56, 189, 248, .16);
      border: 1px solid rgba(125, 211, 252, .34);
      position: relative;
    }}
    .signal-icon::before {{
      content: "";
      width: 18px;
      height: 18px;
      border: 3px solid #7dd3fc;
      border-left: 0;
      border-bottom: 0;
      transform: rotate(-45deg);
      border-radius: 2px;
    }}
    .signal-icon.risk::before {{
      width: 0;
      height: 0;
      border-left: 10px solid transparent;
      border-right: 10px solid transparent;
      border-bottom: 18px solid #f97316;
      border-top: 0;
      transform: none;
    }}
    .signal-icon.action::before {{
      width: 18px;
      height: 18px;
      border: 3px solid #22c55e;
      border-top: 0;
      border-left: 0;
      transform: rotate(45deg);
    }}
    .risk-radar {{
      grid-column: 1 / -1;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .risk-radar span {{
      border-radius: 999px;
      padding: 8px 11px;
      color: #fed7aa;
      background: rgba(154, 52, 18, .22);
      border: 1px solid rgba(251, 146, 60, .42);
      font-size: 13px;
      font-weight: 900;
    }}
    .visual-checklist {{
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      list-style: none;
      padding: 0;
      margin: 0;
    }}
    .visual-checklist li {{
      border-radius: 14px;
      padding: 11px 13px;
      color: #dbeafe;
      background: rgba(30, 41, 59, .78);
      border: 1px solid rgba(148, 163, 184, .22);
      font-size: 14px;
      font-weight: 850;
      line-height: 1.6;
    }}
    .heatmap-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
    }}
    .heatmap-cell {{
      min-height: 94px;
      border-radius: 16px;
      padding: 12px;
      color: #f8fafc;
      background: rgba(15, 23, 42, .72);
      border: 1px solid rgba(148, 163, 184, .24);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.03);
    }}
    .heatmap-cell.up {{
      background: linear-gradient(145deg, rgba(22, 101, 52, .96), rgba(20, 83, 45, .62));
      border-color: rgba(74, 222, 128, .4);
    }}
    .heatmap-cell.down {{
      background: linear-gradient(145deg, rgba(153, 27, 27, .96), rgba(127, 29, 29, .62));
      border-color: rgba(248, 113, 113, .4);
    }}
    .heatmap-cell span {{
      color: rgba(248, 250, 252, .86);
      font-size: 12px;
      font-weight: 1000;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .heatmap-cell strong {{
      font-size: 20px;
      line-height: 1.2;
      margin-top: 8px;
    }}
    .heatmap-cell em {{
      color: #ffffff;
      font-style: normal;
      font-size: 16px;
      font-weight: 1000;
    }}
    .heatmap-empty {{
      border-radius: 16px;
      padding: 18px;
      background: rgba(15, 23, 42, .72);
      border: 1px solid rgba(148, 163, 184, .24);
      font-weight: 900;
    }}
    .section-image {{
      width: 100%;
      display: block;
      border-radius: 18px;
      border: 8px solid #0b1624;
      background: #0b1624;
      margin-top: 16px;
      box-shadow: 0 16px 34px rgba(15, 23, 42, .18);
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
      padding: 14px 16px;
      line-height: 1.85;
      font-size: 17px;
    }}
    .opportunity-item, .caution-item {{
      border-radius: 14px;
      padding: 14px 16px;
      line-height: 1.9;
      font-size: 17px;
      border: 1px solid var(--line);
      margin-bottom: 10px;
      list-style: none;
    }}
    .opportunity-item {{ background: var(--soft-green); color: var(--good); border-left: 6px solid #16a34a; }}
    .caution-item {{ background: var(--soft-red); color: var(--bad); border-left: 6px solid #dc2626; }}
    .scenario-item {{
      border-radius: 14px;
      padding: 14px 16px;
      line-height: 1.9;
      font-size: 17px;
      border: 1px solid var(--line);
      margin-bottom: 10px;
      list-style: none;
      background: var(--soft-blue);
      border-left: 6px solid #2563eb;
      color: #1e3a8a;
    }}
    .research-grid {{
      display: grid;
      gap: 8px;
    }}
    .research-themes {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 4px;
    }}
    .research-confidence {{
      border: 1px solid #fed7aa;
      border-left: 6px solid #f97316;
      border-radius: 14px;
      padding: 13px 15px;
      background: #fff7ed;
      color: #9a3412;
      font-size: 15px;
      font-weight: 900;
      line-height: 1.6;
    }}
    .research-coverage {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 6px;
    }}
    .research-coverage li {{
      border: 1px solid #bfdbfe;
      border-left: 6px solid #2563eb;
      border-radius: 14px;
      background: #eff6ff;
      color: #1e3a8a;
      padding: 11px 13px;
      font-size: 14px;
      font-weight: 900;
      line-height: 1.55;
    }}
    .research-evidence {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 8px;
    }}
    .research-evidence li {{
      border: 1px solid #bbf7d0;
      border-left: 6px solid #16a34a;
      border-radius: 14px;
      background: #f0fdf4;
      color: #14532d;
      padding: 12px 14px;
      font-size: 14px;
      font-weight: 850;
      line-height: 1.6;
    }}
    .research-theme-chip {{
      border: 1px solid #bae6fd;
      border-radius: 999px;
      padding: 6px 10px;
      background: #f0f9ff;
      color: #075985;
      font-size: 12px;
      font-weight: 900;
    }}
    .research-card {{
      border: 1px solid var(--line);
      border-left: 6px solid #0ea5e9;
      border-radius: 14px;
      padding: 14px 16px;
      background: #ffffff;
      line-height: 1.75;
    }}
    .research-card.unavailable {{
      border-left-color: #64748b;
      color: var(--sub);
      font-weight: 800;
    }}
    .research-meta {{
      color: var(--sub);
      font-size: 13px;
      font-weight: 800;
      margin-bottom: 4px;
    }}
    .research-title {{
      font-size: 17px;
      font-weight: 800;
    }}
    .research-title a {{
      color: #075985;
      text-decoration: none;
    }}
    .research-reason {{
      color: var(--sub);
      font-size: 13px;
      font-weight: 700;
      margin-top: 4px;
    }}
    .nikkei-reference {{
      border: 1px solid #bfdbfe;
      border-left: 8px solid #0284c7;
      border-radius: 22px;
      background: linear-gradient(135deg, #f8fbff, #eef7ff);
      padding: 20px;
      display: grid;
      gap: 18px;
    }}
    .nikkei-reference.unavailable {{
      border-left-color: #94a3b8;
      background: #f8fafc;
    }}
    .nikkei-reference h3,
    .nikkei-reference h4 {{
      margin: 0 0 8px;
      color: #0f172a;
      font-weight: 1000;
    }}
    .nikkei-reference p {{
      margin: 0 0 8px;
      color: #334155;
      font-weight: 800;
      line-height: 1.6;
    }}
    .nikkei-reference small {{
      color: #64748b;
      font-weight: 800;
    }}
    .nikkei-link-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 8px;
    }}
    .nikkei-link-grid a,
    .nikkei-reference > a {{
      color: #075985;
      background: #ffffff;
      border: 1px solid #bae6fd;
      border-radius: 999px;
      padding: 9px 11px;
      text-decoration: none;
      font-weight: 900;
      font-size: 13px;
    }}
    .nikkei-watch-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 12px;
    }}
    .nikkei-watch-grid article {{
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 18px;
      padding: 14px;
    }}
    .nikkei-watch-grid ul {{
      margin: 0;
      padding-left: 18px;
      color: #334155;
      font-weight: 750;
      line-height: 1.55;
    }}
    .nikkei-watch-grid li + li {{
      margin-top: 7px;
    }}
    .nikkei-watch-grid li strong {{
      display: inline-block;
      min-width: 58px;
      color: #0f766e;
      margin-right: 6px;
    }}
    .nikkei-empty {{
      color: #64748b;
      font-weight: 900;
    }}
    .analysis-summary {{
      display: grid;
      grid-template-columns: 150px 1fr;
      gap: 12px;
      align-items: center;
    }}
    .summary-characters {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      align-items: end;
      background: #f8fafc;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
    }}
    .summary-character {{
      width: 100%;
      height: auto;
      display: block;
      object-fit: contain;
      animation: floatSoft 4.5s ease-in-out infinite;
    }}
    .summary-character:nth-child(2) {{
      animation-delay: .8s;
    }}
    .summary-memos {{
      gap: 8px;
    }}
    .talk {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px 18px;
      margin-bottom: 12px;
      line-height: 1.9;
      display: flex;
      gap: 12px;
      align-items: center;
    }}
    .talk.student {{
      flex-direction: row-reverse;
    }}
    .talk.teacher {{ background: var(--soft-gold); border-left: 7px solid #f59e0b; }}
    .talk.student {{ background: var(--soft-blue); border-left: 7px solid #2563eb; }}
    .talk-avatar {{
      width: 86px;
      height: 86px;
      object-fit: contain;
      flex: 0 0 86px;
      animation: floatSoft 4.4s ease-in-out infinite;
    }}
    .talk.student .talk-avatar {{
      animation-delay: .6s;
    }}
    .talk-bubble {{
      flex: 1;
      min-width: 0;
    }}
    .talk-role {{
      color: var(--sub);
      font-size: 14px;
      font-weight: 800;
      margin-bottom: 4px;
    }}
    .talk-text {{
      font-size: 18px;
      font-weight: 800;
    }}
    .conclusion {{
      font-size: 23px;
      line-height: 1.85;
      font-weight: 900;
      background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 12%, white), #ffffff);
      border: 1px solid var(--line);
      border-left: 9px solid var(--accent);
      border-radius: 18px;
      padding: 18px 20px;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.7);
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
      font-size: 14px;
      color: var(--sub);
      font-weight: 700;
      padding: 0 6px;
    }}
    .table-row {{
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      font-size: 17px;
      font-weight: 800;
    }}
    @media (max-width: 520px) {{
      body {{
        font-size: 16px;
      }}
      .page {{
        padding: 10px 8px 34px;
      }}
      .hero, .panel {{
        border-radius: 16px;
        padding: 14px;
        margin-bottom: 12px;
      }}
      .flow-headline {{
        display: grid;
        gap: 8px;
        padding: 14px;
      }}
      .flow-headline strong {{
        font-size: 18px;
        line-height: 1.45;
        text-align: left;
      }}
      .flow-board {{
        grid-template-columns: 1fr;
      }}
      .flow-card {{
        min-height: 0;
        padding: 14px;
      }}
      .hero-layout {{
        grid-template-columns: 1fr;
      }}
      .hero-visual {{
        min-height: 128px;
      }}
      .hero-character {{
        width: 72px;
        height: 72px;
      }}
      .hero-character.otter {{
        width: 64px;
        height: 64px;
      }}
      .visual-principles {{
        grid-template-columns: 1fr;
      }}
      .design-pill {{
        width: 100%;
        justify-content: center;
      }}
      .selected-designs {{
        grid-template-columns: 1fr;
      }}
      .analysis-summary {{
        grid-template-columns: 1fr;
      }}
      .pro-analysis {{
        grid-template-columns: 1fr;
      }}
      .analysis-cards {{
        grid-template-columns: 1fr;
      }}
      .visual-signal {{
        grid-template-columns: 1fr;
      }}
      .signal-cards {{
        grid-template-columns: 1fr;
      }}
      .visual-checklist {{
        grid-template-columns: 1fr;
      }}
      .heatmap-grid {{
        grid-template-columns: repeat(2, 1fr);
      }}
      .summary-characters {{
        max-width: 220px;
        margin: 0 auto;
      }}
      .talk, .talk.student {{
        flex-direction: column;
        align-items: flex-start;
      }}
      .talk-avatar {{
        width: 72px;
        height: 72px;
      }}
      h1 {{
        font-size: 25px;
      }}
      h2 {{
        font-size: 20px;
        padding: 9px 12px;
      }}
      .conclusion {{
        font-size: 19px;
        padding: 15px 16px;
      }}
      .talk-text, .metric-card, .scenario-item, .opportunity-item, .caution-item, .signal-item, .memo-item {{
        font-size: 16px;
      }}
      .section-image {{
        border-width: 5px;
        border-radius: 14px;
      }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{
        animation-duration: .001ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: .001ms !important;
      }}
    }}
    @keyframes fadeUp {{
      from {{
        opacity: 0;
        transform: translateY(10px);
      }}
      to {{
        opacity: 1;
        transform: translateY(0);
      }}
    }}
    @keyframes drawLine {{
      to {{
        stroke-dashoffset: 0;
      }}
    }}
    @keyframes floatSoft {{
      0%, 100% {{
        transform: translateY(0);
      }}
      50% {{
        transform: translateY(-6px);
      }}
    }}
    @keyframes pulseRing {{
      0% {{
        opacity: .72;
        transform: translate(-50%, -50%) scale(.72);
      }}
      100% {{
        opacity: 0;
        transform: translate(-50%, -50%) scale(1.85);
      }}
    }}
    @keyframes orbitDot {{
      0% {{
        transform: translate(0, 0) scale(1);
      }}
      50% {{
        transform: translate(22px, 14px) scale(.8);
      }}
      100% {{
        transform: translate(0, 0) scale(1);
      }}
    }}
  </style>
</head>
<body class="category-{_safe(category_style["class"])}">
  <main class="page">
    <section class="hero">
      <div class="hero-layout">
        <div>
          <div class="category-ribbon">
            <span>{_safe(category_style["kicker"])}</span>
            <strong>{_safe(category_style["label"])}</strong>
            <em>{_safe(category_style["subtitle"])}</em>
          </div>
          <div class="eyebrow">{_safe(summary.get("theme_title", "本日のテーマ"))}</div>
          <h1>{_safe(task_config.get("title", task_id))}</h1>
          <div class="badge">{_safe(market_label)}</div>
          <div class="theme">{_safe(summary.get("theme_subtitle", ""))}</div>
          <div class="meta">配信日時: {_safe(summary.get("generated_at", ""))}</div>
          {data_quality_html}
          <div class="digest-strip">
            {digest_tiles_html}
          </div>
        </div>
        {hero_illustration_html}
      </div>
    </section>

    <section class="panel design-panel">
      <h2>デザイン方針</h2>
      {design_tools_html}
    </section>

    <section class="panel">
      <h2>結論</h2>
      <div class="conclusion">{_safe(summary.get("conclusion_text", ""))}</div>
    </section>

    <section class="panel">
      <h2>プロ判断ボード</h2>
      {analysis_dashboard_html}
    </section>

    <section class="panel terminal-panel">
      <h2>視覚ダッシュボード</h2>
      {visual_signal_html}
      <h3>騰落ヒートマップ</h3>
      {market_heatmap_html}
    </section>

    <section class="panel">
      <h2>足元のお金の流れ</h2>
      {money_flow_html}
    </section>

    <section class="panel">
      <h2>テーマ株・主導銘柄</h2>
      <p class="section-note">単独銘柄ではなく、複数銘柄の平均騰落と同方向比率で確認します。</p>
      {theme_board_html}
    </section>

    <section class="panel">
      <h2>先生の分析要約</h2>
      {analysis_summary_html}
    </section>

    <section class="panel">
      <h2>材料検索・ニュース根拠</h2>
      <div class="research-grid">
        {research_html}
      </div>
    </section>

    <section class="panel">
      <h2>nikkei225jp.com参照</h2>
      {nikkei225jp_html}
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

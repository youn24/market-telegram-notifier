from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
CHARACTER_DIR = BASE_DIR / "assets" / "characters"


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = [
        "C:/Windows/Fonts/meiryob.ttc" if bold else "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/YuGothB.ttc" if bold else "C:/Windows/Fonts/YuGothM.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in font_candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in str(text).replace("\n", " "):
        candidate = current + char
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = char
    if current:
        lines.append(current)
    return lines or [""]


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: str,
    max_width: int,
    max_lines: int,
    line_gap: int = 8,
) -> int:
    x, y = xy
    lines = _wrap_text(draw, text, font, max_width)[:max_lines]
    line_height = draw.textbbox((0, 0), "あ", font=font)[3] + line_gap
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _tone_palette(tone: str) -> dict[str, str]:
    palettes = {
        "bull": {
            "accent": "#16a34a",
            "accent_dark": "#166534",
            "soft": "#dcfce7",
            "pale": "#f0fdf4",
            "label": "強気寄り",
        },
        "bear": {
            "accent": "#dc2626",
            "accent_dark": "#991b1b",
            "soft": "#fee2e2",
            "pale": "#fff1f2",
            "label": "警戒",
        },
        "neutral": {
            "accent": "#d97706",
            "accent_dark": "#92400e",
            "soft": "#fef3c7",
            "pale": "#fffbeb",
            "label": "様子見",
        },
    }
    return palettes.get(tone, palettes["neutral"])


def _draw_background(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    draw.rectangle((0, 0, width, height), fill="#fff8ec")
    for y in range(0, height, 72):
        draw.line((0, y, width, y), fill="#fde7bf", width=1)
    for x in range(0, width, 72):
        draw.line((x, 0, x, height), fill="#fff1d4", width=1)
    for x, y, r, color in [
        (930, 170, 170, "#fde68a"),
        (90, 520, 130, "#dbeafe"),
        (970, 1290, 180, "#dcfce7"),
        (120, 1720, 145, "#fee2e2"),
    ]:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)


def _character_paths(tone: str) -> tuple[Path, Path]:
    suffix = {"bull": "bull", "bear": "bear", "neutral": "ai"}.get(tone, "ai")
    return CHARACTER_DIR / f"elephant-{suffix}.png", CHARACTER_DIR / f"otter-{suffix}.png"


def _paste_character(canvas: Image.Image, path: Path, box: tuple[int, int, int, int]) -> None:
    if not path.exists():
        return
    character = Image.open(path).convert("RGBA")
    target_width = max(1, box[2] - box[0])
    target_height = max(1, box[3] - box[1])
    character.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
    x = box[0] + (target_width - character.width) // 2
    y = box[1] + (target_height - character.height) // 2
    canvas.alpha_composite(character, (x, y))


def _metric_parts(metric: str) -> tuple[str, str]:
    text = metric.replace("- ", "", 1).strip()
    if ":" in text:
        name, value = text.split(":", 1)
        return name.strip(), value.strip()
    return text[:12], text[12:].strip()


def _draw_metric_tiles(
    draw: ImageDraw.ImageDraw,
    metrics: list[str],
    palette: dict[str, str],
    x: int,
    y: int,
    width: int,
) -> None:
    title_font = _load_font(22, bold=True)
    value_font = _load_font(26, bold=True)
    small_font = _load_font(18)
    tile_w = (width - 24) // 2
    tile_h = 120
    for index, metric in enumerate(metrics[:4]):
        col = index % 2
        row = index // 2
        tx = x + col * (tile_w + 24)
        ty = y + row * (tile_h + 22)
        name, value = _metric_parts(metric)
        value_color = "#16a34a" if "+" in value else "#dc2626" if "-" in value else "#334155"
        draw.rounded_rectangle((tx, ty, tx + tile_w, ty + tile_h), radius=18, fill="#ffffff", outline="#ead7ba", width=2)
        draw.rounded_rectangle((tx + 16, ty + 16, tx + 58, ty + 58), radius=12, fill=palette["soft"])
        draw.text((tx + 30, ty + 21), str(index + 1), fill=palette["accent_dark"], font=small_font)
        draw.text((tx + 74, ty + 18), name[:14], fill="#7c4a22", font=title_font)
        _draw_wrapped(draw, (tx + 22, ty + 66), value, value_font, value_color, tile_w - 44, 1)


def _draw_change_bars(
    draw: ImageDraw.ImageDraw,
    visual_items: list[dict[str, Any]],
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    label_font = _load_font(18, bold=True)
    value_font = _load_font(17)
    draw.rounded_rectangle((x, y, x + width, y + height), radius=22, fill="#ffffff", outline="#ead7ba", width=2)
    draw.text((x + 24, y + 22), "騰落バー（前日比）", fill="#7c4a22", font=_load_font(24, bold=True))
    chart_x = x + 150
    chart_y = y + 78
    chart_w = width - 210
    center = chart_x + chart_w // 2
    visible_items = visual_items[:5]
    max_abs = max([abs(float(item.get("change_pct") or 0)) for item in visible_items] + [1.0])
    max_abs = min(max_abs, 5.0)
    draw.line((center, chart_y - 10, center, y + height - 24), fill="#cbd5e1", width=2)
    for index, item in enumerate(visible_items):
        row_y = chart_y + index * 32
        label = str(item.get("label", "未確認"))[:10]
        change_pct = item.get("change_pct")
        change_text = str(item.get("change_text", "未確認"))
        color = "#94a3b8"
        if change_pct is not None:
            color = "#16a34a" if change_pct >= 0 else "#dc2626"
        length = 0 if change_pct is None else int(min(abs(float(change_pct)), max_abs) / max_abs * (chart_w // 2 - 8))
        draw.text((x + 24, row_y - 8), label, fill="#334155", font=label_font)
        if change_pct is None:
            draw.rounded_rectangle((center - 14, row_y, center + 14, row_y + 18), radius=9, fill="#cbd5e1")
        elif change_pct >= 0:
            draw.rounded_rectangle((center, row_y, center + length, row_y + 18), radius=9, fill=color)
        else:
            draw.rounded_rectangle((center - length, row_y, center, row_y + 18), radius=9, fill=color)
        draw.rounded_rectangle((x + width - 150, row_y - 13, x + width - 20, row_y + 25), radius=12, fill="#ffffff")
        draw.text((x + width - 136, row_y - 9), change_text, fill=color, font=value_font)


def _shorten_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> list[str]:
    lines = _wrap_text(draw, str(text), font, max_width)
    if len(lines) <= max_lines:
        return lines
    clipped = lines[:max_lines]
    while clipped[-1] and _text_width(draw, clipped[-1] + "…", font) > max_width:
        clipped[-1] = clipped[-1][:-1]
    clipped[-1] += "…"
    return clipped


def _draw_quick_summary(
    draw: ImageDraw.ImageDraw,
    summary: dict[str, Any],
    palette: dict[str, str],
    x: int,
    y: int,
    width: int,
) -> None:
    draw.rounded_rectangle((x, y, x + width, y + 230), radius=26, fill="#ffffff", outline="#ead7ba", width=2)
    draw.text((x + 26, y + 22), "まず見る3点", fill="#7c4a22", font=_load_font(28, bold=True))
    comments = summary.get("ai_summary") or summary.get("deep_summary_lines") or summary.get("commentary", []) or []
    fallback = [
        summary.get("conclusion_text", "結論は未確認データを残しながら判断します。"),
        "数字は取得できたデータだけを使い、推測では作りません。",
        "詳しい根拠はブラウザ版レポートで確認できます。",
    ]
    rows = (comments + fallback)[:3]
    icons = ["1", "2", "3"]
    colors = [palette["soft"], "#eff6ff", "#f8fafc"]
    for index, row in enumerate(rows):
        ry = y + 68 + index * 50
        draw.rounded_rectangle((x + 26, ry, x + width - 26, ry + 40), radius=16, fill=colors[index], outline="#e5e7eb")
        draw.ellipse((x + 42, ry + 7, x + 68, ry + 33), fill="#ffffff", outline=palette["accent"])
        draw.text((x + 51, ry + 7), icons[index], fill=palette["accent_dark"], font=_load_font(16, bold=True))
        line_font = _load_font(18, bold=index == 0)
        line = _shorten_text(draw, row, line_font, width - 132, 1)[0]
        draw.text((x + 82, ry + 8), line, fill="#243041", font=line_font)


def _draw_signal_board(
    draw: ImageDraw.ImageDraw,
    summary: dict[str, Any],
    palette: dict[str, str],
    x: int,
    y: int,
    width: int,
) -> None:
    draw.rounded_rectangle((x, y, x + width, y + 158), radius=26, fill="#ffffff", outline="#ead7ba", width=2)
    draw.text((x + 26, y + 20), "今日の作戦メーター", fill="#7c4a22", font=_load_font(26, bold=True))
    labels = [("守る", "#dc2626"), ("待つ", "#d97706"), ("攻める", "#16a34a")]
    tone = summary.get("market_tone", "neutral")
    active_index = {"bear": 0, "neutral": 1, "bull": 2}.get(tone, 1)
    seg_w = (width - 76) // 3
    for index, (label, color) in enumerate(labels):
        sx = x + 26 + index * (seg_w + 12)
        fill = color if index == active_index else "#f8fafc"
        text_color = "#ffffff" if index == active_index else color
        draw.rounded_rectangle((sx, y + 70, sx + seg_w, y + 118), radius=18, fill=fill, outline=color, width=2)
        draw.text((sx + seg_w // 2 - _text_width(draw, label, _load_font(22, bold=True)) // 2, y + 80), label, fill=text_color, font=_load_font(22, bold=True))
    conclusion = _shorten_text(draw, summary.get("conclusion_text", ""), _load_font(18), width - 52, 1)[0]
    draw.text((x + 26, y + 128), conclusion, fill=palette["accent_dark"], font=_load_font(18))


def _draw_sparkline_panel(
    draw: ImageDraw.ImageDraw,
    summary: dict[str, Any],
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    items = summary.get("sparkline_items", []) or []
    draw.rounded_rectangle((x, y, x + width, y + height), radius=22, fill="#ffffff", outline="#ead7ba", width=2)
    draw.text((x + 24, y + 20), "日足ミニチャート（初日=100）", fill="#7c4a22", font=_load_font(26, bold=True))
    plot_x = x + 42
    plot_y = y + 74
    plot_w = width - 84
    plot_h = height - 122
    for i in range(4):
        gy = plot_y + int(plot_h * i / 3)
        draw.line((plot_x, gy, plot_x + plot_w, gy), fill="#e2e8f0", width=1)
    colors = ["#2563eb", "#16a34a", "#d97706", "#db2777"]
    legend_x = x + 34
    legend_y = y + height - 38
    for index, item in enumerate(items[:4]):
        series = item.get("series", [])
        values = [point.get("value") for point in series if point.get("value") is not None]
        if len(values) < 2 or not values[0]:
            continue
        normalized = [(value / values[0]) * 100 for value in values]
        min_v = min(normalized)
        max_v = max(normalized)
        span = max(max_v - min_v, 1)
        points = []
        for pos, value in enumerate(normalized):
            px = plot_x + int(plot_w * pos / max(1, len(normalized) - 1))
            py = plot_y + plot_h - int((value - min_v) / span * plot_h)
            points.append((px, py))
        if len(points) >= 2:
            draw.line(points, fill=colors[index % len(colors)], width=5, joint="curve")
            for point in points[-2:]:
                draw.ellipse((point[0] - 5, point[1] - 5, point[0] + 5, point[1] + 5), fill=colors[index % len(colors)])
        label = str(item.get("label", ""))[:12]
        lx = legend_x + (index % 2) * 230
        ly = legend_y + (index // 2) * 24
        draw.rounded_rectangle((lx, ly + 7, lx + 28, ly + 15), radius=4, fill=colors[index % len(colors)])
        draw.text((lx + 36, ly), label, fill="#334155", font=_load_font(17))


def _draw_speech(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    speaker: str,
    text: str,
    palette: dict[str, str],
    role: str,
    max_lines: int = 4,
) -> int:
    label_font = _load_font(22, bold=True)
    body_font = _load_font(24, bold=True if role == "teacher" else False)
    border = palette["accent"] if role == "teacher" else "#38bdf8"
    fill = "#fffef9" if role == "teacher" else "#f0f9ff"
    all_lines = _wrap_text(draw, text, body_font, width - 52)
    lines = all_lines[:max_lines]
    if len(all_lines) > max_lines and lines:
        while lines[-1] and _text_width(draw, lines[-1] + "…", body_font) > width - 52:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1] + "…"
    height = 66 + len(lines) * 34
    draw.rounded_rectangle((x, y, x + width, y + height), radius=22, fill=fill, outline=border, width=3)
    draw.text((x + 26, y + 18), speaker, fill=border, font=label_font)
    text_y = y + 58
    for line in lines:
        draw.text((x + 26, text_y), line, fill="#243041", font=body_font)
        text_y += 34
    return y + height


def _draw_research_and_scenarios(
    draw: ImageDraw.ImageDraw,
    summary: dict[str, Any],
    palette: dict[str, str],
    x: int,
    y: int,
    width: int,
) -> None:
    title_font = _load_font(24, bold=True)
    body_font = _load_font(16)
    small_font = _load_font(14)
    draw.rounded_rectangle((x, y, x + width, y + 132), radius=24, fill="#ffffff", outline="#ead7ba", width=2)
    draw.text((x + 26, y + 20), "材料リサーチと今日の見方", fill="#7c4a22", font=title_font)
    confidence = summary.get("research_confidence_line", "")
    if confidence:
        draw.rounded_rectangle((x + 324, y + 18, x + width - 26, y + 50), radius=14, fill=palette["soft"])
        _draw_wrapped(draw, (x + 342, y + 25), confidence, small_font, palette["accent_dark"], width - 392, 1)
    item_y = y + 58
    items = summary.get("research_items", [])
    if not items:
        note = summary.get("research_note", "材料検索は未確認です。")
        _draw_wrapped(draw, (x + 30, item_y), note, body_font, "#64748b", width - 60, 1)
    for index, item in enumerate(items[:1], start=1):
        source = str(item.get("source", "媒体未確認"))[:12]
        title = str(item.get("title", "未確認"))
        draw.rounded_rectangle((x + 26, item_y, x + width - 26, item_y + 34), radius=14, fill="#f8fafc", outline="#e5e7eb")
        line = _shorten_text(draw, f"{source}: {title}", body_font, width - 84, 1)[0]
        draw.text((x + 42, item_y + 7), line, fill="#1f2937", font=body_font)
    scenario_y = y + 96
    labels = ["強気", "中立", "警戒"]
    colors = ["#dcfce7", "#fef3c7", "#fee2e2"]
    for index, scenario in enumerate(summary.get("scenarios", [])[:3]):
        sx = x + 26 + index * ((width - 68) // 3 + 8)
        sw = (width - 84) // 3
        draw.rounded_rectangle((sx, scenario_y, sx + sw, y + 122), radius=13, fill=colors[index], outline="#ead7ba")
        draw.text((sx + 14, scenario_y + 8), labels[index], fill="#7c4a22", font=small_font)
        cleaned = str(scenario).split(":", 1)[-1].strip()
        _draw_wrapped(draw, (sx + 60, scenario_y + 8), cleaned, _load_font(11), "#334155", sw - 72, 1)


def _dark_palette(tone: str) -> dict[str, str]:
    palettes = {
        "bull": {"accent": "#22c55e", "accent2": "#60a5fa", "chip": "上昇優位 / 押し目監視"},
        "bear": {"accent": "#ef4444", "accent2": "#f59e0b", "chip": "警戒優先 / 戻り売り注意"},
        "neutral": {"accent": "#38bdf8", "accent2": "#facc15", "chip": "強弱まちまち / 見極め"},
    }
    return palettes.get(tone, palettes["neutral"])


def _category_style(task_config: dict[str, Any]) -> dict[str, str]:
    category = str(task_config.get("category", "japan_market"))
    if task_config.get("focus") == "macro":
        category = "macro"
    styles = {
        "macro": {
            "kicker": "MACRO NOTE",
            "label": "マクロ総覧",
            "subtitle": "金利・為替・株・商品を一枚で俯瞰",
            "accent": "#38bdf8",
            "accent2": "#facc15",
            "fill": "#082f49",
            "rail": "GLOBAL / RATES / FX",
            "signal_label": "俯瞰軸",
        },
        "japan_market": {
            "kicker": "TOKYO BOARD",
            "label": "日本株",
            "subtitle": "寄り付き・大引け・需給の温度差を見る",
            "accent": "#f97316",
            "accent2": "#22c55e",
            "fill": "#431407",
            "rail": "NIKKEI / TOPIX / FLOW",
            "signal_label": "注目軸",
        },
        "fx": {
            "kicker": "FX LENS",
            "label": "為替",
            "subtitle": "通貨の強弱と金利差を短く確認",
            "accent": "#a78bfa",
            "accent2": "#2dd4bf",
            "fill": "#2e1065",
            "rail": "USD / JPY / RATES",
            "signal_label": "為替軸",
        },
        "earnings": {
            "kicker": "EARNINGS",
            "label": "決算",
            "subtitle": "業績・ガイダンス・市場反応を整理",
            "accent": "#f43f5e",
            "accent2": "#fbbf24",
            "fill": "#4c0519",
            "rail": "RESULTS / GUIDANCE",
            "signal_label": "決算軸",
        },
    }
    return styles.get(category, styles["japan_market"])


def _draw_dark_background(draw: ImageDraw.ImageDraw, width: int, height: int, category_style: dict[str, str]) -> None:
    draw.rectangle((0, 0, width, height), fill="#030712")
    for y in range(height):
        if y % 3 != 0:
            continue
        shade = int(10 + 22 * (y / max(1, height)))
        draw.line((0, y, width, y), fill=(5, 18 + shade // 3, 32 + shade, 255), width=3)
    for x, y, r, color in [
        (130, 120, 190, "#0f2a44"),
        (950, 520, 260, "#082f49"),
        (100, 1520, 260, "#111827"),
        (970, 1760, 190, "#1e1b4b"),
    ]:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
    draw.rectangle((0, 0, 18, height), fill=category_style["accent"])
    for y in range(88, height, 210):
        draw.line((28, y, 28, y + 96), fill=category_style["accent2"], width=4)


def _draw_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str | None = None,
    accent: str = "#38bdf8",
) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=24, fill="#0b1624", outline="#334155", width=2)
    draw.rounded_rectangle((x1 + 2, y1 + 2, x2 - 2, y2 - 2), radius=22, outline="#10243a", width=2)
    if title:
        draw.text((x1 + 26, y1 + 18), title, fill="#e5e7eb", font=_load_font(28, bold=True))
        draw.line((x1 + 26, y1 + 60, x2 - 26, y1 + 60), fill="#1f3b57", width=1)


def _draw_chip(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    color: str,
    fill: str,
) -> None:
    draw.rounded_rectangle(box, radius=16, fill=fill, outline=color, width=2)
    font = _load_font(24, bold=True)
    x1, y1, x2, y2 = box
    draw.text((x1 + (x2 - x1 - _text_width(draw, text, font)) // 2, y1 + 12), text, fill=color, font=font)


def _trend_counts(visual_items: list[dict[str, Any]]) -> tuple[int, int]:
    up = len([item for item in visual_items if isinstance(item.get("change_pct"), (int, float)) and item["change_pct"] > 0])
    down = len([item for item in visual_items if isinstance(item.get("change_pct"), (int, float)) and item["change_pct"] < 0])
    return up, down


def _headline_chip(summary: dict[str, Any], visual_items: list[dict[str, Any]]) -> str:
    vix = next((item for item in visual_items if "VIX" in str(item.get("label", "")).upper()), None)
    vix_change = vix.get("change_pct") if vix else None
    tone = summary.get("market_tone", "neutral")
    dashboard = summary.get("analysis_dashboard", {})
    score = dashboard.get("score")
    band = dashboard.get("band")
    if isinstance(score, int) and band:
        return f"地合い {score}/100・{band}"
    if isinstance(vix_change, (int, float)) and vix_change >= 1.0:
        return "VIX上昇 / 警戒感あり"
    if tone == "bull":
        return "指数強め / 買い優勢"
    if tone == "bear":
        return "下落優勢 / 守り重視"
    return "強弱混在 / 見極め"


def _normalized_points(series: list[dict[str, Any]], max_points: int = 6) -> list[float]:
    values = [point.get("value") for point in series if point.get("value") is not None][-max_points:]
    if len(values) < 2 or not values[0]:
        return []
    return [(float(value) / float(values[0])) * 100 for value in values]


def _draw_header_icon(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    palette: dict[str, str],
    is_morning: bool,
) -> None:
    if is_morning:
        cx, cy, radius = x + 22, y + 22, 13
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=palette["accent2"])
        for dx, dy in [(-28, 0), (28, 0), (0, -28), (0, 28), (-20, -20), (20, -20), (-20, 20), (20, 20)]:
            draw.line((cx + dx * 0.62, cy + dy * 0.62, cx + dx, cy + dy), fill=palette["accent2"], width=4)
        return

    draw.ellipse((x + 2, y + 2, x + 46, y + 46), outline=palette["accent2"], width=5)
    draw.line((x + 24, y + 24, x + 24, y + 10), fill=palette["accent2"], width=5)
    draw.line((x + 24, y + 24, x + 36, y + 28), fill=palette["accent2"], width=5)


def _draw_dark_header(
    draw: ImageDraw.ImageDraw,
    summary: dict[str, Any],
    task_config: dict[str, Any],
    visual_items: list[dict[str, Any]],
    palette: dict[str, str],
    category_style: dict[str, str],
    x: int,
    y: int,
    width: int,
) -> None:
    title = str(task_config.get("title", "相場チェック"))
    _draw_header_icon(draw, x + 24, y + 24, palette, "7:00" in title or "朝" in title)
    draw.rounded_rectangle((x + 82, y + 16, x + 312, y + 52), radius=14, fill=category_style["fill"], outline=category_style["accent"], width=2)
    draw.text((x + 102, y + 23), category_style["kicker"], fill=category_style["accent2"], font=_load_font(19, bold=True))
    draw.text((x + width - 258, y + 22), category_style["rail"], fill=category_style["accent"], font=_load_font(18, bold=True))
    _draw_wrapped(draw, (x + 82, y + 62), title, _load_font(34, bold=True), "#f8fafc", width - 360, 2)
    draw.text((x + 82, y + 154), category_style["subtitle"], fill="#dbeafe", font=_load_font(22, bold=True))
    draw.rounded_rectangle((x + width - 280, y + 112, x + width - 28, y + 154), radius=18, fill="#10243a", outline=category_style["accent"])
    draw.text((x + width - 250, y + 120), category_style["label"], fill=category_style["accent2"], font=_load_font(20, bold=True))
    up, down = _trend_counts(visual_items)
    chip_y = y + 190
    _draw_chip(draw, (x + 24, chip_y, x + 235, chip_y + 64), f"↗ 上昇 {up}", "#4ade80", "#0f2f22")
    _draw_chip(draw, (x + 255, chip_y, x + 466, chip_y + 64), f"↘ 下落 {down}", "#fb7185", "#33151f")
    _draw_chip(draw, (x + 486, chip_y, x + width - 28, chip_y + 64), f"★ {_headline_chip(summary, visual_items)}", "#60a5fa", "#0b2442")


def _draw_priority_banner(
    draw: ImageDraw.ImageDraw,
    summary: dict[str, Any],
    palette: dict[str, str],
    category_style: dict[str, str],
    x: int,
    y: int,
    width: int,
) -> None:
    label = str(summary.get("conclusion_label", "様子見"))
    conclusion = str(summary.get("conclusion_text", "取得できたデータのみで確認します。"))
    dashboard = summary.get("analysis_dashboard", {})
    score = dashboard.get("score")
    score_text = f"{score}/100" if isinstance(score, int) else "未確認"
    draw.rounded_rectangle(
        (x, y, x + width, y + 96),
        radius=24,
        fill="#f8fafc",
        outline=palette["accent"],
        width=4,
    )
    draw.rounded_rectangle((x + 18, y + 18, x + 190, y + 78), radius=18, fill=category_style["fill"], outline=category_style["accent"], width=2)
    draw.text((x + 42, y + 30), category_style["signal_label"], fill=category_style["accent2"], font=_load_font(27, bold=True))
    draw.text((x + 214, y + 18), label, fill=palette["accent"], font=_load_font(34, bold=True))
    line_font = _load_font(24, bold=True)
    line = _shorten_text(draw, conclusion, line_font, width - 468, 1)[0]
    draw.text((x + 214, y + 56), line, fill="#0f172a", font=line_font)
    draw.rounded_rectangle((x + width - 216, y + 18, x + width - 24, y + 78), radius=18, fill="#0b1624", outline="#334155", width=2)
    draw.text((x + width - 190, y + 29), f"地合い {score_text}", fill="#f8fafc", font=_load_font(23, bold=True))


def _paste_dark_characters(canvas: Image.Image, tone: str) -> None:
    elephant_path, otter_path = _character_paths(tone)
    _paste_character(canvas, elephant_path, (770, 80, 970, 278))
    _paste_character(canvas, otter_path, (920, 132, 1060, 278))


def _draw_dark_line_chart(
    draw: ImageDraw.ImageDraw,
    summary: dict[str, Any],
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    _draw_panel(draw, (x, y, x + width, y + height), "直近6取得日の価格推移（初日=100）")
    risk_keys = {"US10Y", "SOFR", "VIX", "YIELD_2S10S"}
    all_items = summary.get("sparkline_items", []) or []
    price_items = [item for item in all_items if str(item.get("key", "")) not in risk_keys]
    items = (price_items or all_items)[:5]
    plot_x = x + 70
    plot_y = y + 94
    plot_w = width - 140
    plot_h = height - 260
    legend_y_base = y + height - 112
    colors = ["#38bdf8", "#f97316", "#22c55e", "#ec4899", "#8b5cf6", "#06b6d4", "#facc15", "#cbd5e1"]
    all_values: list[float] = []
    normalized_map: list[tuple[dict[str, Any], list[float]]] = []
    for item in items:
        values = _normalized_points(item.get("series", []), 6)
        if values:
            normalized_map.append((item, values))
            all_values.extend(values)
    min_v = min(all_values + [96])
    max_v = max(all_values + [104])
    span = max(4.0, max_v - min_v)
    min_v -= span * 0.12
    max_v += span * 0.12
    span = max_v - min_v

    for index in range(5):
        gy = plot_y + int(plot_h * index / 4)
        label_value = max_v - span * index / 4
        draw.line((plot_x, gy, plot_x + plot_w, gy), fill="#203044", width=1)
        draw.text((plot_x - 54, gy - 13), f"{label_value:.0f}", fill="#dbeafe", font=_load_font(18, bold=True))
    for index in range(6):
        gx = plot_x + int(plot_w * index / 5)
        draw.line((gx, plot_y, gx, plot_y + plot_h), fill="#162437", width=1)
        label = "当日" if index == 5 else f"{5 - index}営業日前"
        draw.text((gx - 44, plot_y + plot_h + 18), label, fill="#dbeafe", font=_load_font(16, bold=True))

    for index, (item, values) in enumerate(normalized_map):
        color = colors[index % len(colors)]
        points = []
        for pos, value in enumerate(values):
            px = plot_x + int(plot_w * pos / max(1, len(values) - 1))
            py = plot_y + plot_h - int((value - min_v) / span * plot_h)
            points.append((px, py))
        if len(points) >= 2:
            draw.line(points, fill=color, width=6, joint="curve")
            for point in points:
                draw.ellipse((point[0] - 7, point[1] - 7, point[0] + 7, point[1] + 7), fill=color)
        legend_col = index % 2
        legend_row = index // 2
        legend_x = x + 42 + legend_col * ((width - 84) // 2)
        legend_y = legend_y_base + legend_row * 34
        draw.rounded_rectangle((legend_x, legend_y + 7, legend_x + 34, legend_y + 17), radius=5, fill=color)
        draw.text((legend_x + 46, legend_y - 2), str(item.get("label", "未確認"))[:11], fill="#f8fafc", font=_load_font(20, bold=True))
        change = item.get("change_pct")
        change_text = "未確認" if change is None else f"{change:+.2f}%"
        change_color = "#4ade80" if isinstance(change, (int, float)) and change >= 0 else "#fb7185"
        draw.text((legend_x + 178, legend_y - 2), change_text, fill=change_color, font=_load_font(19, bold=True))


def _draw_dark_bar_ranking(
    draw: ImageDraw.ImageDraw,
    visual_items: list[dict[str, Any]],
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    _draw_panel(draw, (x, y, x + width, y + height), "前日比ランキング")
    ranked = [
        item
        for item in visual_items
        if isinstance(item.get("change_pct"), (int, float))
    ]
    ranked.sort(key=lambda item: float(item.get("change_pct", 0)), reverse=True)
    if not ranked:
        draw.text((x + 34, y + 92), "前日比データは未確認です。", fill="#cbd5e1", font=_load_font(22, bold=True))
        return

    plot_x = x + 314
    plot_y = y + 86
    plot_w = width - 410
    center = plot_x + plot_w // 2
    row_gap = 43
    max_abs = max([abs(float(item.get("change_pct", 0))) for item in ranked[:8]] + [1.0])
    draw.line((center, plot_y - 10, center, y + height - 44), fill="#64748b", width=2)
    for tick in [-1.0, -0.5, 0, 0.5, 1.0]:
        tx = center + int(tick * (plot_w // 2))
        draw.line((tx, plot_y - 8, tx, y + height - 54), fill="#1f334a", width=1)
    for index, item in enumerate(ranked[:8]):
        row_y = plot_y + index * row_gap
        label = str(item.get("label", "未確認"))[:14]
        change = float(item.get("change_pct", 0))
        color = "#4ade80" if change >= 0 else "#fb7185"
        length = int(min(abs(change), max_abs) / max_abs * (plot_w // 2 - 8))
        draw.text((x + 34, row_y - 10), label, fill="#f8fafc", font=_load_font(21, bold=True))
        if change >= 0:
            draw.rounded_rectangle((center, row_y - 3, center + length, row_y + 20), radius=10, fill=color)
        else:
            draw.rounded_rectangle((center - length, row_y - 3, center, row_y + 20), radius=10, fill=color)
        value = f"{change:+.2f}%"
        value_x = center + length + 10 if change >= 0 else center - length - _text_width(draw, value, _load_font(17, bold=True)) - 10
        draw.text((value_x, row_y - 10), value, fill="#f8fafc", font=_load_font(20, bold=True))
    draw.text((center - 12, y + height - 42), "0%", fill="#cbd5e1", font=_load_font(16, bold=True))


def _draw_dark_memo(
    draw: ImageDraw.ImageDraw,
    summary: dict[str, Any],
    x: int,
    y: int,
    width: int,
    height: int,
    palette: dict[str, str],
) -> None:
    _draw_panel(draw, (x, y, x + width, y + height), None, palette["accent"])
    draw.text((x + 28, y + 22), "AI 実戦メモ", fill=palette["accent2"], font=_load_font(34, bold=True))
    comments = (
        summary.get("trade_checklist")
        or summary.get("ai_summary")
        or summary.get("deep_summary_lines")
        or summary.get("commentary", [])
    )[:3]
    if not comments:
        comments = [summary.get("conclusion_text", "大きな偏りは未確認です。")]
    text_y = y + 82
    for comment in comments[:3]:
        draw.rounded_rectangle((x + 30, text_y - 8, x + width - 30, text_y + 34), radius=16, fill="#10243a", outline="#1e3a5f")
        draw.text((x + 48, text_y - 1), "•", fill="#f8fafc", font=_load_font(27, bold=True))
        memo_font = _load_font(25, bold=True)
        memo_line = _shorten_text(draw, comment, memo_font, width - 110, 1)[0]
        draw.text((x + 82, text_y - 3), memo_line, fill="#f8fafc", font=memo_font)
        text_y += 49
    evidence = summary.get("research_evidence_briefs") or summary.get("research_evidence_lines", [])
    if evidence:
        line = _shorten_text(draw, "根拠: " + evidence[0], _load_font(18), width - 70, 1)[0]
        draw.rounded_rectangle((x + 28, y + height - 54, x + width - 28, y + height - 18), radius=12, fill="#10243a", outline="#1e3a5f")
        draw.text((x + 44, y + height - 48), line, fill="#bfdbfe", font=_load_font(18, bold=True))


def create_summary_card(
    task_id: str,
    task_config: dict[str, Any],
    summary: dict[str, Any],
    rules: dict[str, Any],
    output_dir: Path,
) -> Path:
    width = int(rules.get("common", {}).get("card_width", 1080))
    height = int(rules.get("common", {}).get("card_height", 1920))
    image = Image.new("RGBA", (width, height), "#030712")
    draw = ImageDraw.Draw(image)

    palette = _dark_palette(summary.get("market_tone", "neutral"))
    category_style = _category_style(task_config)
    _draw_dark_background(draw, width, height, category_style)
    visual_items = summary.get("visual_items", [])

    margin = 34
    draw.rounded_rectangle((margin, margin, width - margin, height - margin), radius=32, fill="#07111e", outline="#28415e", width=3)
    _paste_dark_characters(image, summary.get("market_tone", "neutral"))
    _draw_dark_header(draw, summary, task_config, visual_items, palette, category_style, 52, 54, width - 104)
    _draw_priority_banner(draw, summary, palette, category_style, 52, 314, width - 104)
    _draw_dark_line_chart(draw, summary, 52, 434, width - 104, 500)
    _draw_dark_bar_ranking(draw, visual_items, 52, 958, width - 104, 430)
    _draw_dark_memo(draw, summary, 52, 1430, width - 104, 330, palette)

    footer_font = _load_font(16)
    footer = f"{category_style['label']} | 数値は取得できたデータのみ使用。取得不能な情報は未確認。詳細はブラウザ版レポートへ。"
    draw.text((72, height - 70), footer, fill="#94a3b8", font=footer_font)
    draw.text((72, height - 44), f"生成時刻: {summary['generated_at']}", fill="#64748b", font=_load_font(14))

    path = output_dir / f"{task_id}_card.png"
    image.convert("RGB").save(path, quality=95)
    return path

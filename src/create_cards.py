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
    max_abs = max([abs(float(item.get("change_pct") or 0)) for item in visual_items[:7]] + [1.0])
    max_abs = min(max_abs, 5.0)
    draw.line((center, chart_y - 10, center, y + height - 24), fill="#cbd5e1", width=2)
    for index, item in enumerate(visual_items[:7]):
        row_y = chart_y + index * 38
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
        draw.text((x + width - 96, row_y - 9), change_text, fill=color, font=value_font)


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
    draw.text((x + 24, y + 20), "日足ミニチャート（初日=100）", fill="#7c4a22", font=_load_font(24, bold=True))
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
    title_font = _load_font(28, bold=True)
    body_font = _load_font(18)
    small_font = _load_font(16)
    draw.rounded_rectangle((x, y, x + width, y + 350), radius=24, fill="#ffffff", outline="#ead7ba", width=2)
    draw.text((x + 26, y + 20), "材料リサーチと今日の見方", fill="#7c4a22", font=title_font)
    confidence = summary.get("research_confidence_line", "")
    if confidence:
        draw.rounded_rectangle((x + 26, y + 62, x + width - 26, y + 100), radius=14, fill=palette["soft"])
        _draw_wrapped(draw, (x + 42, y + 71), confidence, small_font, palette["accent_dark"], width - 84, 1)
    item_y = y + 114
    items = summary.get("research_items", [])
    if not items:
        note = summary.get("research_note", "材料検索は未確認です。")
        _draw_wrapped(draw, (x + 30, item_y), note, body_font, "#64748b", width - 60, 2)
    for index, item in enumerate(items[:2], start=1):
        source = str(item.get("source", "媒体未確認"))[:14]
        score = item.get("score", "未採点")
        title = str(item.get("title", "未確認"))
        draw.rounded_rectangle((x + 26, item_y, x + width - 26, item_y + 62), radius=16, fill="#f8fafc", outline="#e5e7eb")
        draw.text((x + 42, item_y + 9), f"{index}. {source} / score {score}", fill="#0369a1", font=small_font)
        _draw_wrapped(draw, (x + 42, item_y + 32), title, body_font, "#1f2937", width - 84, 1)
        item_y += 72
    scenario_y = y + 260
    labels = ["強気", "中立", "警戒"]
    colors = ["#dcfce7", "#fef3c7", "#fee2e2"]
    for index, scenario in enumerate(summary.get("scenarios", [])[:3]):
        sx = x + 26 + index * ((width - 68) // 3 + 8)
        sw = (width - 84) // 3
        draw.rounded_rectangle((sx, scenario_y, sx + sw, y + 326), radius=15, fill=colors[index], outline="#ead7ba")
        draw.text((sx + 14, scenario_y + 10), labels[index], fill="#7c4a22", font=small_font)
        cleaned = str(scenario).split(":", 1)[-1].strip()
        _draw_wrapped(draw, (sx + 14, scenario_y + 32), cleaned, _load_font(14), "#334155", sw - 28, 2)


def create_summary_card(
    task_id: str,
    task_config: dict[str, Any],
    summary: dict[str, Any],
    rules: dict[str, Any],
    output_dir: Path,
) -> Path:
    width = int(rules.get("common", {}).get("card_width", 1080))
    height = int(rules.get("common", {}).get("card_height", 1920))
    image = Image.new("RGBA", (width, height), "#fff8ec")
    draw = ImageDraw.Draw(image)
    _draw_background(draw, width, height)

    title_font = _load_font(42, bold=True)
    subtitle_font = _load_font(24)
    small_font = _load_font(20)
    palette = _tone_palette(summary.get("market_tone", "neutral"))
    elephant_path, otter_path = _character_paths(summary.get("market_tone", "neutral"))

    margin = 34
    draw.rounded_rectangle((margin, margin, width - margin, height - margin), radius=34, fill="#ffffff", outline="#e7cfa9", width=4)
    draw.rounded_rectangle((margin + 14, margin + 14, width - margin - 14, 250), radius=28, fill=palette["pale"], outline="#ead7ba", width=2)
    draw.text((66, 64), summary.get("theme_title", "今日の相場メモ"), fill=palette["accent_dark"], font=subtitle_font)
    title = task_config.get("title", task_id)
    _draw_wrapped(draw, (66, 105), title, title_font, "#3b2415", 650, 2)
    draw.text((68, 216), f"配信日時: {summary['generated_at']}", fill="#64748b", font=small_font)
    draw.rounded_rectangle((760, 72, 1018, 188), radius=24, fill="#ffffff", outline=palette["accent"], width=4)
    draw.text((812, 98), palette["label"], fill=palette["accent"], font=_load_font(38, bold=True))

    _paste_character(image, elephant_path, (56, 238, 230, 418))
    _paste_character(image, otter_path, (856, 238, 1026, 418))

    teacher_text = summary.get("conclusion_text", "未確認データを残しながら、取れる数字だけで判断します。")
    student_text = ""
    if summary.get("dialogue"):
        student_text = summary["dialogue"][0].get("text", "")
    speech_y = 270
    _draw_speech(draw, 238, speech_y, 594, "ガネーシャ先生の結論", teacher_text, palette, "teacher", max_lines=3)
    if student_text:
        draw.rounded_rectangle((640, 438, 1018, 492), radius=20, fill="#f0f9ff", outline="#38bdf8", width=3)
        draw.text((660, 452), "カワウソくん: ", fill="#0284c7", font=_load_font(18, bold=True))
        student_font = _load_font(18)
        short_lines = _wrap_text(draw, student_text, student_font, 190)
        short_question = short_lines[0]
        if len(short_lines) > 1:
            while short_question and _text_width(draw, short_question + "…", student_font) > 190:
                short_question = short_question[:-1]
            short_question += "…"
        draw.text((786, 452), short_question, fill="#243041", font=student_font)

    _draw_metric_tiles(draw, summary.get("metrics", []), palette, 56, 500, width - 112)
    _draw_sparkline_panel(draw, summary, 56, 780, width - 112, 330)
    _draw_change_bars(draw, summary.get("visual_items", []), 56, 1140, width - 112, 360)
    _draw_research_and_scenarios(draw, summary, palette, 56, 1520, width - 112)

    footer_font = _load_font(14)
    footer = "数値は取得できたデータのみ使用。取得不能な情報は未確認として扱います。"
    draw.text((72, height - 42), footer, fill="#64748b", font=footer_font)

    path = output_dir / f"{task_id}_card.png"
    image.convert("RGB").save(path, quality=95)
    return path

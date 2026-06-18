from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
CHARACTER_DIR = BASE_DIR / "assets" / "characters"


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = [
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in font_candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_japanese_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        test = current + char
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines or [text]


def _draw_gradient_background(image: Image.Image) -> None:
    width, height = image.size
    top_color = (248, 250, 252, 255)
    bottom_color = (248, 250, 252, 255)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(int(top_color[i] * (1 - ratio) + bottom_color[i] * ratio) for i in range(4))
        ImageDraw.Draw(image).line((0, y, width, y), fill=color)


def _tone_palette(tone: str) -> tuple[str, str, str]:
    mapping = {
        "bull": ("#16a34a", "#dcfce7", "#f0fdf4"),
        "bear": ("#dc2626", "#fee2e2", "#fef2f2"),
        "neutral": ("#d97706", "#fef3c7", "#fffbeb"),
    }
    return mapping.get(tone, mapping["neutral"])


def _draw_header_pattern(draw: ImageDraw.ImageDraw, width: int) -> None:
    for index, x in enumerate(range(34, width - 34, 86)):
        color = "#fbbf24" if index % 2 == 0 else "#38bdf8"
        draw.rounded_rectangle((x, 34, x + 44, 44), radius=8, fill=color)
    for index, x in enumerate(range(60, width - 80, 130)):
        color = "#22c55e" if index % 2 == 0 else "#ef4444"
        draw.ellipse((x, 258, x + 18, 276), fill=color)


def _character_paths(tone: str) -> tuple[Path, Path]:
    suffix = {"bull": "bull", "bear": "bear", "neutral": "ai"}.get(tone, "ai")
    return (
        CHARACTER_DIR / f"elephant-{suffix}.png",
        CHARACTER_DIR / f"otter-{suffix}.png",
    )


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


def _draw_market_flow(draw: ImageDraw.ImageDraw, accent: str, x: int, y: int) -> None:
    draw.rounded_rectangle((x, y, x + 230, y + 54), radius=16, fill="#ffffff", outline=accent, width=2)
    draw.line((x + 22, y + 34, x + 72, y + 18, x + 122, y + 29, x + 178, y + 14), fill=accent, width=5)
    draw.polygon([(x + 178, y + 14), (x + 164, y + 12), (x + 172, y + 26)], fill=accent)
    for offset in [24, 74, 124]:
        draw.ellipse((x + offset - 4, y + 30 - 4, x + offset + 4, y + 30 + 4), fill=accent)


def _draw_market_temperature(
    draw: ImageDraw.ImageDraw,
    visual_items: list[dict[str, Any]],
    x: int,
    y: int,
    width: int,
    small_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    mini_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    draw.text((x, y), "市場温度バー", fill="#172033", font=mini_font)
    row_y = y + 38
    center_x = x + width // 2
    max_abs = max([abs(item.get("change_pct") or 0) for item in visual_items[:5]] + [1])
    max_abs = min(max_abs, 3.5)

    draw.line((center_x, row_y - 8, center_x, row_y + 250), fill="#cbd5e1", width=2)
    for item in visual_items[:5]:
        change_pct = item.get("change_pct")
        label = str(item.get("label", "未確認"))[:12]
        change_text = str(item.get("change_text", "未確認"))
        color = "#64748b" if change_pct is None else "#16a34a" if change_pct >= 0 else "#dc2626"
        length = 0 if change_pct is None else int(min(abs(change_pct), max_abs) / max_abs * 155)
        bar_top = row_y + 30
        if change_pct is None:
            draw.rounded_rectangle((center_x - 18, bar_top, center_x + 18, bar_top + 18), radius=8, fill="#cbd5e1")
        elif change_pct >= 0:
            draw.rounded_rectangle((center_x, bar_top, center_x + length, bar_top + 18), radius=8, fill=color)
        else:
            draw.rounded_rectangle((center_x - length, bar_top, center_x, bar_top + 18), radius=8, fill=color)
        draw.text((x, row_y), label, fill="#334155", font=mini_font)
        draw.text((x + width - 105, row_y), change_text, fill=color, font=mini_font)
        row_y += 50


def create_summary_card(
    task_id: str,
    task_config: dict[str, Any],
    summary: dict[str, Any],
    rules: dict[str, Any],
    output_dir: Path,
) -> Path:
    width = int(rules.get("common", {}).get("card_width", 1280))
    height = int(rules.get("common", {}).get("card_height", 720))
    image = Image.new("RGBA", (width, height), "#ffffff")
    _draw_gradient_background(image)
    draw = ImageDraw.Draw(image)

    title_font = _load_font(42)
    body_font = _load_font(28)
    strong_font = _load_font(40)
    small_font = _load_font(24)
    chip_font = _load_font(26)
    mini_font = _load_font(20)

    tone = summary.get("market_tone", "neutral")
    accent, badge_fill, section_fill = _tone_palette(tone)
    elephant_path, otter_path = _character_paths(tone)

    draw.rounded_rectangle((22, 22, width - 22, height - 22), radius=18, fill="#ffffff", outline="#dbe4ef", width=2)
    draw.rounded_rectangle((34, 34, width - 34, 302), radius=14, fill="#ffffff", outline="#dbe4ef", width=2)
    draw.rectangle((34, 34, 44, 302), fill=accent)
    draw.text((64, 64), summary.get("theme_title", "本日のテーマ"), fill=accent, font=mini_font)
    draw.text((64, 102), summary.get("theme_subtitle", ""), fill="#475569", font=small_font)
    title_lines = _wrap_japanese_text(draw, task_config.get("title", task_id), title_font, 560)
    title_y = 150
    for title_line in title_lines[:2]:
        draw.text((64, title_y), title_line, fill="#111827", font=title_font)
        title_y += 48
    draw.text((66, 254), f"配信日時: {summary['generated_at']}", fill="#64748b", font=small_font)
    draw.rounded_rectangle((768, 74, 1020, 222), radius=18, fill="#ffffff", outline=accent, width=3)
    draw.text((810, 103), summary.get("conclusion_label", "様子見"), fill=accent, font=_load_font(40))
    _draw_market_flow(draw, accent, 772, 232)

    draw.rounded_rectangle((38, 326, width - 38, 560), radius=16, fill="#ffffff", outline="#dbe4ef", width=2)
    draw.text((64, 362), "結論", fill=accent, font=mini_font)
    conclusion_lines = _wrap_japanese_text(draw, summary.get("conclusion_text", ""), chip_font, width - 120)
    conclusion_y = 404
    for line in conclusion_lines[:4]:
        draw.text((64, conclusion_y), line, fill="#1f2937", font=chip_font)
        conclusion_y += 34

    draw.rounded_rectangle((38, 590, width - 38, 980), radius=16, fill="#ffffff", outline="#dbe4ef", width=2)
    draw.text((64, 624), "重要数字と市場温度", fill="#172033", font=strong_font)
    panel_y = 684
    for index, metric in enumerate(summary.get("metrics", [])[:3], start=1):
        draw.rounded_rectangle((64, panel_y - 4, 548, panel_y + 62), radius=10, fill="#f8fafc", outline="#e5e7eb", width=1)
        draw.rounded_rectangle((82, panel_y + 10, 126, panel_y + 52), radius=10, fill="#ffffff", outline=accent, width=2)
        draw.text((96, panel_y + 14), str(index), fill=accent, font=small_font)
        wrapped_metric = _wrap_japanese_text(draw, metric.replace("- ", "", 1), small_font, 370)
        text_y = panel_y + 13
        for metric_line in wrapped_metric[:1]:
            draw.text((152, text_y), metric_line, fill="#243041", font=small_font)
            text_y += 30
        panel_y += 76
    _draw_market_temperature(draw, summary.get("visual_items", []), 590, 684, 400, small_font, mini_font)

    draw.rounded_rectangle((38, 1010, width - 38, 1438), radius=16, fill="#ffffff", outline="#dbe4ef", width=2)
    draw.text((64, 1044), "先生の分析要約", fill="#172033", font=strong_font)
    draw.rounded_rectangle((820, 1070, width - 64, 1400), radius=18, fill="#f8fafc", outline="#e5e7eb", width=2)
    _paste_character(image, elephant_path, (838, 1088, 950, 1228))
    _paste_character(image, otter_path, (918, 1240, width - 82, 1388))
    point_y = 1108
    text_width = width - 390
    for line in summary.get("commentary", [])[:2]:
        wrapped = _wrap_japanese_text(draw, f"・{line}", small_font, text_width)
        for wrapped_line in wrapped[:2]:
            draw.text((78, point_y), wrapped_line, fill="#243041", font=small_font)
            point_y += 28
        point_y += 10
    for line in summary.get("opportunities", [])[:1]:
        wrapped = _wrap_japanese_text(draw, f"・{line}", small_font, text_width)
        for wrapped_line in wrapped[:2]:
            draw.text((78, point_y), wrapped_line, fill="#166534", font=small_font)
            point_y += 28
        point_y += 10
    point_y += 8
    for line in summary.get("cautions", [])[:1]:
        wrapped = _wrap_japanese_text(draw, f"・{line}", small_font, text_width)
        for wrapped_line in wrapped[:2]:
            draw.text((78, point_y), wrapped_line, fill="#991b1b", font=small_font)
            point_y += 28
        point_y += 10

    draw.rounded_rectangle((38, 1468, width - 38, 1868), radius=16, fill="#ffffff", outline="#dbe4ef", width=2)
    draw.rounded_rectangle((64, 1550, width - 64, 1560), radius=4, fill=accent)
    draw.text((64, 1502), "今日の3シナリオ", fill="#172033", font=strong_font)
    memo_y = 1568
    for line in summary.get("scenarios", [])[:3]:
        wrapped = _wrap_japanese_text(draw, f"・{line}", small_font, width - 120)
        for wrapped_line in wrapped[:2]:
            draw.text((82, memo_y), wrapped_line, fill="#475569", font=small_font)
            memo_y += 28
        memo_y += 12

    path = output_dir / f"{task_id}_card.png"
    image.convert("RGB").save(path)
    return path

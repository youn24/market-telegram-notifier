from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


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
    top_color = (255, 248, 244, 255)
    bottom_color = (255, 238, 222, 255)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(int(top_color[i] * (1 - ratio) + bottom_color[i] * ratio) for i in range(4))
        ImageDraw.Draw(image).line((0, y, width, y), fill=color)


def _tone_palette(tone: str) -> tuple[str, str, str]:
    mapping = {
        "bull": ("#16a34a", "#ecfdf5", "#dcfce7"),
        "bear": ("#dc2626", "#fef2f2", "#fee2e2"),
        "neutral": ("#d97706", "#fffbeb", "#fef3c7"),
    }
    return mapping.get(tone, mapping["neutral"])


def create_summary_card(
    task_id: str,
    task_config: dict[str, Any],
    summary: dict[str, Any],
    rules: dict[str, Any],
    output_dir: Path,
) -> Path:
    width = int(rules.get("common", {}).get("card_width", 1280))
    height = int(rules.get("common", {}).get("card_height", 720))
    image = Image.new("RGBA", (width, height), "#fff8f3")
    _draw_gradient_background(image)
    draw = ImageDraw.Draw(image)

    title_font = _load_font(48)
    body_font = _load_font(28)
    strong_font = _load_font(40)
    small_font = _load_font(24)
    chip_font = _load_font(26)
    mini_font = _load_font(20)

    accent, badge_fill, section_fill = _tone_palette(summary.get("market_tone", "neutral"))

    draw.rounded_rectangle((22, 22, width - 22, height - 22), radius=42, fill="#fffaf7", outline="#efcfbf", width=3)
    draw.rounded_rectangle((34, 34, width - 34, 292), radius=36, fill="#fff2ea", outline="#efcfbf", width=2)
    draw.text((60, 64), summary.get("theme_title", "本日のテーマ"), fill="#7a3c20", font=mini_font)
    draw.text((60, 100), summary.get("theme_subtitle", ""), fill="#9a5d40", font=small_font)
    draw.text((60, 160), task_config.get("title", task_id), fill="#7a3c20", font=title_font)
    draw.text((62, 224), f"生成時刻: {summary['generated_at']}", fill="#9a5d40", font=small_font)
    draw.rounded_rectangle((774, 74, 1018, 220), radius=28, fill=badge_fill, outline=accent, width=2)
    draw.text((820, 102), summary.get("conclusion_label", "様子見"), fill=accent, font=_load_font(42))

    draw.rounded_rectangle((38, 326, width - 38, 560), radius=34, fill=badge_fill, outline=accent, width=2)
    draw.text((64, 362), "結論", fill=accent, font=mini_font)
    conclusion_lines = _wrap_japanese_text(draw, summary.get("conclusion_text", ""), chip_font, width - 120)
    conclusion_y = 404
    for line in conclusion_lines[:4]:
        draw.text((64, conclusion_y), line, fill="#1f2937", font=chip_font)
        conclusion_y += 34

    draw.rounded_rectangle((38, 590, width - 38, 980), radius=34, fill="#fffdfb", outline="#f0ddd0", width=2)
    draw.text((64, 624), "重要数字", fill="#7a3c20", font=strong_font)
    panel_y = 690
    for index, metric in enumerate(summary.get("metrics", [])[:4], start=1):
        draw.rounded_rectangle((64, panel_y - 8, width - 64, panel_y + 72), radius=24, fill=section_fill, outline="#f4e2d8", width=1)
        draw.rounded_rectangle((82, panel_y + 14, 126, panel_y + 56), radius=18, fill="#ffffff", outline="#f0c8a0", width=1)
        draw.text((96, panel_y + 18), str(index), fill=accent, font=small_font)
        wrapped_metric = _wrap_japanese_text(draw, metric.replace("- ", "", 1), body_font, width - 220)
        text_y = panel_y + 16
        for metric_line in wrapped_metric[:2]:
            draw.text((152, text_y), metric_line, fill="#243041", font=body_font)
            text_y += 30
        panel_y += 92

    draw.rounded_rectangle((38, 1010, width - 38, 1438), radius=34, fill="#fffdfb", outline="#f0ddd0", width=2)
    draw.text((64, 1044), "注目ポイント", fill="#7a3c20", font=strong_font)
    point_y = 1108
    for line in summary.get("opportunities", [])[:2]:
        wrapped = _wrap_japanese_text(draw, f"・{line}", small_font, width - 120)
        for wrapped_line in wrapped[:2]:
            draw.text((78, point_y), wrapped_line, fill="#166534", font=small_font)
            point_y += 28
        point_y += 10
    point_y += 8
    for line in summary.get("cautions", [])[:2]:
        wrapped = _wrap_japanese_text(draw, f"・{line}", small_font, width - 120)
        for wrapped_line in wrapped[:2]:
            draw.text((78, point_y), wrapped_line, fill="#991b1b", font=small_font)
            point_y += 28
        point_y += 10

    draw.rounded_rectangle((38, 1468, width - 38, 1868), radius=34, fill="#ffffff", outline="#f0ddd0", width=2)
    draw.text((64, 1502), "先生の要約", fill="#7a3c20", font=strong_font)
    memo_y = 1568
    for line in summary.get("commentary", [])[:3]:
        wrapped = _wrap_japanese_text(draw, f"・{line}", small_font, width - 120)
        for wrapped_line in wrapped[:2]:
            draw.text((82, memo_y), wrapped_line, fill="#475569", font=small_font)
            memo_y += 28
        memo_y += 12

    path = output_dir / f"{task_id}_card.png"
    image.convert("RGB").save(path)
    return path

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


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [text]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        test = f"{current} {word}"
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


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


def _draw_elephant(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    cx = (left + right) // 2
    cy = (top + bottom) // 2 + 10
    gold = "#f4b93f"
    deep = "#c9861f"
    soft = "#ffe7a6"

    draw.ellipse((cx - 78, cy - 70, cx + 78, cy + 60), fill=gold, outline=deep, width=5)
    draw.ellipse((cx - 120, cy - 55, cx - 35, cy + 35), fill=gold, outline=deep, width=5)
    draw.ellipse((cx + 35, cy - 55, cx + 120, cy + 35), fill=gold, outline=deep, width=5)
    draw.rounded_rectangle((cx - 24, cy - 5, cx + 24, cy + 110), radius=22, fill=gold, outline=deep, width=5)
    draw.ellipse((cx - 42, cy + 78, cx - 8, cy + 125), fill=soft, outline=deep, width=4)
    draw.ellipse((cx + 8, cy + 78, cx + 42, cy + 125), fill=soft, outline=deep, width=4)
    draw.ellipse((cx - 32, cy - 18, cx - 8, cy + 8), fill="white")
    draw.ellipse((cx + 8, cy - 18, cx + 32, cy + 8), fill="white")
    draw.ellipse((cx - 23, cy - 11, cx - 13, cy - 1), fill="#111827")
    draw.ellipse((cx + 13, cy - 11, cx + 23, cy - 1), fill="#111827")
    draw.arc((cx - 26, cy + 20, cx + 26, cy + 50), start=10, end=170, fill="#7c2d12", width=4)
    draw.arc((cx - 8, cy + 22, cx + 44, cy + 98), start=90, end=320, fill=deep, width=8)


def _draw_otter(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    cx = (left + right) // 2
    cy = (top + bottom) // 2 + 10
    brown = "#a1623a"
    deep = "#6b3f22"
    cream = "#fff1dd"

    draw.ellipse((cx - 82, cy - 60, cx + 82, cy + 90), fill=brown, outline=deep, width=5)
    draw.ellipse((cx - 65, cy - 118, cx + 65, cy - 8), fill=brown, outline=deep, width=5)
    draw.ellipse((cx - 52, cy - 18, cx + 52, cy + 84), fill=cream, outline=deep, width=4)
    draw.ellipse((cx - 52, cy - 84, cx - 26, cy - 55), fill=brown, outline=deep, width=4)
    draw.ellipse((cx + 26, cy - 84, cx + 52, cy - 55), fill=brown, outline=deep, width=4)
    draw.ellipse((cx - 35, cy - 70, cx - 8, cy - 43), fill="white")
    draw.ellipse((cx + 8, cy - 70, cx + 35, cy - 43), fill="white")
    draw.ellipse((cx - 25, cy - 61, cx - 15, cy - 51), fill="#111827")
    draw.ellipse((cx + 15, cy - 61, cx + 25, cy - 51), fill="#111827")
    draw.ellipse((cx - 12, cy - 40, cx + 12, cy - 20), fill="#7c2d12")
    draw.arc((cx - 28, cy - 32, cx + 28, cy + 2), start=20, end=160, fill="#7c2d12", width=4)
    draw.arc((cx + 60, cy + 6, cx + 170, cy + 80), start=180, end=300, fill=deep, width=18)


def _speaker_style(task_id: str) -> tuple[str, str, str]:
    if task_id.startswith("fx"):
        return "ゾウAI", "#fff3d6", "#f4b93f"
    if task_id.startswith("japan"):
        return "カワウソAI", "#fff0ea", "#b17347"
    return "マーケットAI", "#eef2ff", "#64748b"


def _draw_speech_bubble(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str,
    outline: str,
) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=30, fill=fill, outline=outline, width=4)
    tail = [(left + 40, bottom - 16), (left + 92, bottom - 16), (left + 60, bottom + 26)]
    draw.polygon(tail, fill=fill, outline=outline)


def create_summary_card(
    task_id: str,
    task_config: dict[str, Any],
    summary: dict[str, Any],
    rules: dict[str, Any],
    output_dir: Path,
) -> Path:
    width = int(rules.get("common", {}).get("card_width", 1280))
    height = int(rules.get("common", {}).get("card_height", 720))
    image = Image.new("RGB", (width, height), "#fff7ed")
    draw = ImageDraw.Draw(image)

    title_font = _load_font(42)
    body_font = _load_font(27)
    strong_font = _load_font(32)
    small_font = _load_font(22)
    chip_font = _load_font(20)

    speaker_name, bubble_fill, accent = _speaker_style(task_id)

    draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=34, fill="#fffaf4", outline="#f1d6ad", width=3)
    draw.rounded_rectangle((40, 40, width - 40, 126), radius=26, fill="#fff1df", outline="#efc58b", width=2)
    draw.text((70, 58), task_config.get("title", task_id), fill="#7c2d12", font=title_font)
    draw.text((72, 104), f"生成時刻: {summary['generated_at']}", fill="#9a3412", font=small_font)

    draw.rounded_rectangle((56, 150, 780, 675), radius=28, fill="#ffffff", outline="#efd7b4", width=2)
    draw.rounded_rectangle((820, 150, 1220, 675), radius=28, fill="#fff8ef", outline="#efd7b4", width=2)

    bubble_box = (86, 184, 742, 334)
    _draw_speech_bubble(draw, bubble_box, bubble_fill, accent)
    draw.text((108, 196), speaker_name, fill="#7c2d12", font=strong_font)

    comment_y = 244
    for line in summary.get("commentary", []):
        wrapped = _wrap_japanese_text(draw, line, body_font, 596)
        for wrapped_line in wrapped:
            draw.text((108, comment_y), wrapped_line, fill="#111827", font=body_font)
            comment_y += 34
        comment_y += 6

    panel_y = 370
    draw.text((86, panel_y), "主要項目", fill="#7c2d12", font=strong_font)
    panel_y += 48
    for metric in summary.get("metrics", [])[:5]:
        draw.rounded_rectangle((86, panel_y - 6, 742, panel_y + 28), radius=16, fill="#fff8ef", outline="#f3e2c7", width=1)
        wrapped_metric = _wrap_japanese_text(draw, metric, body_font, 620)
        text_y = panel_y
        for metric_line in wrapped_metric[:2]:
            draw.text((102, text_y), metric_line, fill="#1f2937", font=body_font)
            text_y += 28
        panel_y += 54

    chip_y = 196
    draw.text((850, chip_y), "AIの見立て", fill="#7c2d12", font=strong_font)
    chip_y += 54
    for signal in summary.get("signals", [])[:5]:
        draw.rounded_rectangle((850, chip_y, 1188, chip_y + 56), radius=18, fill="#ffffff", outline="#efd7b4", width=2)
        signal_text = signal.replace("- ", "", 1)
        wrapped_signal = _wrap_japanese_text(draw, signal_text, chip_font, 300)
        line_y = chip_y + 10
        for signal_line in wrapped_signal[:2]:
            draw.text((868, line_y), signal_line, fill="#334155", font=chip_font)
            line_y += 21
        chip_y += 68

    draw.text((850, 564), summary.get("speaker_role", "市況を整理"), fill="#9a3412", font=small_font)
    if task_id.startswith("fx"):
        _draw_elephant(draw, (846, 280, 1184, 660))
    else:
        _draw_otter(draw, (846, 280, 1184, 660))

    path = output_dir / f"{task_id}_card.png"
    image.save(path)
    return path

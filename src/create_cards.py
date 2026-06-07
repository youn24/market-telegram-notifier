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


def _speaker_style(task_id: str) -> tuple[str, str, str]:
    if task_id.startswith("fx"):
        return "ゾウAI", "#fff6de", "#f5bf4f"
    if task_id.startswith("japan"):
        return "カワウソAI", "#fff1eb", "#bf8156"
    return "マーケットAI", "#eef2ff", "#64748b"


def _character_asset(task_id: str, output_dir: Path) -> Path | None:
    root = output_dir.parent.parent
    if task_id.startswith("fx"):
        candidate = root / "assets" / "characters" / "elephant-ai.png"
    else:
        candidate = root / "assets" / "characters" / "otter-ai.png"
    return candidate if candidate.exists() else None


def _paste_character(image: Image.Image, asset_path: Path, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    character = Image.open(asset_path).convert("RGBA")
    target_width = right - left
    target_height = bottom - top
    character.thumbnail((target_width, target_height), Image.LANCZOS)
    x = left + (target_width - character.width) // 2
    y = top + (target_height - character.height) // 2
    image.alpha_composite(character, (x, y))


def _draw_speech_bubble(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str,
    outline: str,
    tail_side: str = "left",
) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=30, fill=fill, outline=outline, width=4)
    if tail_side == "right":
        tail = [(right - 92, bottom - 16), (right - 40, bottom - 16), (right - 58, bottom + 28)]
    else:
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
    image = Image.new("RGBA", (width, height), "#fff8f3")
    draw = ImageDraw.Draw(image)

    title_font = _load_font(42)
    body_font = _load_font(28)
    strong_font = _load_font(34)
    small_font = _load_font(22)
    chip_font = _load_font(21)

    speaker_name, bubble_fill, accent = _speaker_style(task_id)
    character_asset = _character_asset(task_id, output_dir)

    draw.rounded_rectangle((20, 20, width - 20, height - 20), radius=38, fill="#fffaf7", outline="#efcfbf", width=3)
    draw.rounded_rectangle((36, 36, width - 36, 132), radius=28, fill="#fff2ea", outline="#efcfbf", width=2)
    draw.text((64, 56), task_config.get("title", task_id), fill="#7a3c20", font=title_font)
    draw.text((66, 103), f"生成時刻: {summary['generated_at']}", fill="#9a5d40", font=small_font)

    draw.rounded_rectangle((52, 154, 764, 676), radius=30, fill="#ffffff", outline="#f0ddd0", width=2)
    draw.rounded_rectangle((792, 154, 1230, 676), radius=30, fill="#fff6f2", outline="#f0ddd0", width=2)

    panel_y = 190
    draw.text((84, panel_y), "きょうの数字", fill="#7a3c20", font=strong_font)
    panel_y += 50
    for metric in summary.get("metrics", [])[:5]:
        draw.rounded_rectangle((84, panel_y - 8, 730, panel_y + 36), radius=18, fill="#fff8f3", outline="#f4e2d8", width=1)
        wrapped_metric = _wrap_japanese_text(draw, metric.replace("- ", "", 1), body_font, 600)
        text_y = panel_y + 2
        for metric_line in wrapped_metric[:2]:
            draw.text((102, text_y), metric_line, fill="#243041", font=body_font)
            text_y += 28
        panel_y += 60

    draw.text((824, 190), "AIのひとこと", fill="#7a3c20", font=strong_font)
    bubble_box = (824, 238, 1198, 448)
    _draw_speech_bubble(draw, bubble_box, bubble_fill, accent, tail_side="right")
    draw.text((848, 254), speaker_name, fill="#7a3c20", font=strong_font)

    comment_y = 308
    for line in summary.get("commentary", [])[:2]:
        wrapped = _wrap_japanese_text(draw, line, body_font, 314)
        for wrapped_line in wrapped[:3]:
            draw.text((848, comment_y), wrapped_line, fill="#111827", font=body_font)
            comment_y += 34
        comment_y += 4

    signal_y = 474
    draw.text((824, signal_y), summary.get("speaker_role", "市況を整理"), fill="#9a5d40", font=small_font)
    signal_y += 34
    for signal in summary.get("signals", [])[:2]:
        draw.rounded_rectangle((824, signal_y, 1198, signal_y + 54), radius=18, fill="#ffffff", outline="#f0ddd0", width=2)
        signal_text = signal.replace("- ", "", 1)
        wrapped_signal = _wrap_japanese_text(draw, signal_text, chip_font, 326)
        line_y = signal_y + 12
        for signal_line in wrapped_signal[:2]:
            draw.text((844, line_y), signal_line, fill="#334155", font=chip_font)
            line_y += 20
        signal_y += 64

    if character_asset is not None:
        _paste_character(image, character_asset, (850, 470, 1190, 664))

    path = output_dir / f"{task_id}_card.png"
    image.convert("RGB").save(path)
    return path

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
        return "ガネーシャ先生", "#fff6de", "#f5bf4f"
    if task_id.startswith("japan"):
        return "ガネーシャ先生", "#fff1eb", "#bf8156"
    return "ガネーシャ先生", "#eef2ff", "#64748b"


def _character_asset(task_id: str, output_dir: Path, summary: dict[str, Any], role: str) -> Path | None:
    root = output_dir.parent.parent
    tone = summary.get("market_tone", "neutral")
    if role == "teacher":
        mapping = {
            "bull": root / "assets" / "characters" / "elephant-bull.png",
            "bear": root / "assets" / "characters" / "elephant-bear.png",
            "neutral": root / "assets" / "characters" / "elephant-ai.png",
        }
    else:
        mapping = {
            "bull": root / "assets" / "characters" / "otter-bull.png",
            "bear": root / "assets" / "characters" / "otter-bear.png",
            "neutral": root / "assets" / "characters" / "otter-ai.png",
        }
    candidate = mapping.get(tone, next(iter(mapping.values())))
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


def _draw_gradient_background(image: Image.Image) -> None:
    width, height = image.size
    top_color = (255, 248, 244, 255)
    bottom_color = (255, 238, 222, 255)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(int(top_color[i] * (1 - ratio) + bottom_color[i] * ratio) for i in range(4))
        ImageDraw.Draw(image).line((0, y, width, y), fill=color)


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
    _draw_gradient_background(image)
    draw = ImageDraw.Draw(image)

    title_font = _load_font(44)
    body_font = _load_font(30)
    strong_font = _load_font(38)
    small_font = _load_font(24)
    chip_font = _load_font(26)
    mini_font = _load_font(20)

    speaker_name, bubble_fill, accent = _speaker_style(task_id)
    teacher_asset = _character_asset(task_id, output_dir, summary, "teacher")
    student_asset = _character_asset(task_id, output_dir, summary, "student")

    draw.rounded_rectangle((22, 22, width - 22, height - 22), radius=42, fill="#fffaf7", outline="#efcfbf", width=3)
    draw.rounded_rectangle((34, 34, width - 34, 330), radius=36, fill="#fff2ea", outline="#efcfbf", width=2)
    draw.text((60, 64), summary.get("theme_title", "本日のテーマ"), fill="#7a3c20", font=mini_font)
    draw.text((60, 100), summary.get("theme_subtitle", ""), fill="#9a5d40", font=small_font)
    draw.text((60, 160), task_config.get("title", task_id), fill="#7a3c20", font=title_font)
    draw.text((62, 224), f"生成時刻: {summary['generated_at']}", fill="#9a5d40", font=small_font)
    draw.rounded_rectangle((780, 72, 1008, 260), radius=28, fill="#fffaf4", outline="#efd2a8", width=2)
    draw.text((814, 110), "AI", fill="#d97706", font=_load_font(54))
    draw.text((808, 178), "Design Pro", fill="#9a5d40", font=small_font)

    draw.rounded_rectangle((38, 360, width - 38, 1060), radius=34, fill="#fffdfb", outline="#f0ddd0", width=2)
    draw.text((64, 392), "ガネーシャ先生とカワウソくんの会話", fill="#7a3c20", font=strong_font)

    if student_asset is not None:
        _paste_character(image, student_asset, (56, 448, 340, 760))
    student_bubble = (300, 472, 992, 652)
    _draw_speech_bubble(draw, student_bubble, "#fff7f3", "#e6b8a5", tail_side="left")
    student_lines = _wrap_japanese_text(draw, summary.get("dialogue", [{}])[0].get("text", ""), chip_font, 620)
    draw.text((338, 494), summary.get("student_name", "カワウソくん"), fill="#9a5d40", font=small_font)
    student_y = 540
    for line in student_lines[:4]:
        draw.text((338, student_y), line, fill="#243041", font=chip_font)
        student_y += 30

    if teacher_asset is not None:
        _paste_character(image, teacher_asset, (736, 682, 1006, 1042))
    teacher_bubble = (86, 724, 734, 960)
    _draw_speech_bubble(draw, teacher_bubble, bubble_fill, accent, tail_side="right")
    teacher_lines = _wrap_japanese_text(draw, summary.get("dialogue", [{}, {}])[1].get("text", ""), chip_font, 574)
    draw.text((118, 748), speaker_name, fill="#7a3c20", font=strong_font)
    teacher_y = 806
    for line in teacher_lines[:5]:
        draw.text((118, teacher_y), line, fill="#111827", font=chip_font)
        teacher_y += 32

    draw.rounded_rectangle((38, 1090, width - 38, 1868), radius=34, fill="#ffffff", outline="#f0ddd0", width=2)
    draw.text((64, 1124), "きょうの数字", fill="#7a3c20", font=strong_font)

    panel_y = 1182
    for index, metric in enumerate(summary.get("metrics", [])[:5], start=1):
        draw.rounded_rectangle((64, panel_y - 8, width - 64, panel_y + 74), radius=24, fill="#fff8f3", outline="#f4e2d8", width=1)
        draw.rounded_rectangle((82, panel_y + 12, 126, panel_y + 54), radius=18, fill="#ffedd5", outline="#f0c8a0", width=1)
        draw.text((96, panel_y + 16), str(index), fill="#b45309", font=small_font)
        wrapped_metric = _wrap_japanese_text(draw, metric.replace("- ", "", 1), body_font, width - 220)
        text_y = panel_y + 14
        for metric_line in wrapped_metric[:2]:
            draw.text((152, text_y), metric_line, fill="#243041", font=body_font)
            text_y += 30
        panel_y += 100

    draw.text((64, 1716), "先生のメモ", fill="#7a3c20", font=strong_font)
    memo_y = 1772
    for line in summary.get("commentary", [])[:2]:
        wrapped = _wrap_japanese_text(draw, f"・{line}", small_font, width - 130)
        for wrapped_line in wrapped[:2]:
            draw.text((82, memo_y), wrapped_line, fill="#475569", font=small_font)
            memo_y += 26
        memo_y += 10

    path = output_dir / f"{task_id}_card.png"
    image.convert("RGB").save(path)
    return path

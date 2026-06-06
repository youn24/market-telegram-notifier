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


def create_summary_card(
    task_id: str,
    task_config: dict[str, Any],
    summary: dict[str, Any],
    rules: dict[str, Any],
    output_dir: Path,
) -> Path:
    width = int(rules.get("common", {}).get("card_width", 1280))
    height = int(rules.get("common", {}).get("card_height", 720))
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image)

    title_font = _load_font(42)
    body_font = _load_font(28)
    small_font = _load_font(22)

    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=28, fill="#e2e8f0", outline="#cbd5e1", width=2)
    draw.text((80, 80), task_config.get("title", task_id), fill="#0f172a", font=title_font)
    draw.text((80, 145), f"生成時刻: {summary['generated_at']}", fill="#334155", font=small_font)

    text_block = summary["body"]
    y = 210
    for line in text_block.splitlines():
        draw.text((80, y), line, fill="#111827", font=body_font)
        y += 38
        if y > height - 80:
            break

    path = output_dir / f"{task_id}_card.png"
    image.save(path)
    return path

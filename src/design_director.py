from __future__ import annotations

from pathlib import Path
from typing import Any


def _tone_direction(tone: str) -> dict[str, str]:
    directions = {
        "bull": {
            "mood": "明るく前向き。上昇の勢いは出すが、読みやすさを最優先にする。",
            "palette": "deep navy, white, emerald green, gold highlights, small red accents",
            "visual": "上昇チャート、整理されたダッシュボード、強いセクターを示す小さなパネル",
        },
        "bear": {
            "mood": "警戒感を出しつつ、暗くしすぎず冷静な判断ができる雰囲気にする。",
            "palette": "deep navy, white, alert red, muted gold, cool gray",
            "visual": "下落チャート、リスク警告、VIXや金利を確認する分析パネル",
        },
        "neutral": {
            "mood": "様子見と見極め。過度に強気にも弱気にも寄せず、比較しやすい構成にする。",
            "palette": "deep navy, white, amber, cyan, balanced green and red",
            "visual": "横ばいチャート、比較表、金利・為替・指数を並べた俯瞰パネル",
        },
    }
    return directions.get(tone, directions["neutral"])


def build_design_direction(task_id: str, task_config: dict[str, Any], summary: dict[str, Any], raw_data: dict[str, Any]) -> dict[str, str]:
    tone = summary.get("market_tone", "neutral")
    direction = _tone_direction(tone)
    title = task_config.get("title", task_id)

    macro_labels = ", ".join(item.get("label", "") for item in raw_data.get("macro_items", [])[:4]) or "macro indicators"
    market_labels = ", ".join(item.get("label", "") for item in raw_data.get("items", [])[:4]) or "market indicators"

    image_prompt = "\n".join(
        [
            "Use case: productivity-visual",
            "Asset type: mobile financial market digest hero background, no text",
            f"Primary request: Create a premium visual header for '{title}'.",
            f"Market mood: {direction['mood']}",
            f"Visual motifs: {direction['visual']}.",
            f"Data themes to suggest visually: {market_labels}; {macro_labels}.",
            "Style/medium: polished fintech editorial infographic background.",
            "Composition: portrait mobile layout, usable dark area at upper-left for overlaid Japanese title.",
            f"Color palette: {direction['palette']}.",
            "Constraints: no readable text, no numbers, no logos, no watermark, no characters.",
        ]
    )

    canva_prompt = "\n".join(
        [
            "スマホ縦長の金融市場ダイジェストを作成してください。",
            f"タイトル: {title}",
            f"結論: {summary.get('conclusion_label', '様子見')}",
            f"全体トーン: {direction['mood']}",
            "最優先: 読みやすさ、次に情報量、最後に装飾。",
            "構成: 1. 結論 2. 金利・VIX・為替 3. 指数 4. 今日の3シナリオ 5. 要約メモ。",
            f"配色: {direction['palette']}",
            "文字は大きく、スマホでスクロールして読みやすく。過度な装飾や背景の文字被りは禁止。",
        ]
    )

    return {
        "image_prompt": image_prompt,
        "canva_prompt": canva_prompt,
        "palette": direction["palette"],
        "mood": direction["mood"],
    }


def write_design_handoff(site_dir: Path, direction: dict[str, str]) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)
    brief_path = site_dir / "design-brief.md"
    brief_path.write_text(
        "\n".join(
            [
                "# Design Brief",
                "",
                "## Canva Prompt",
                "",
                direction["canva_prompt"],
                "",
                "## Image Generation Prompt",
                "",
                direction["image_prompt"],
                "",
                "## Palette",
                "",
                direction["palette"],
            ]
        ),
        encoding="utf-8",
    )

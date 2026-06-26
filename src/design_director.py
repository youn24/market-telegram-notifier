from __future__ import annotations

from pathlib import Path
from typing import Any


def _tone_direction(tone: str) -> dict[str, str]:
    directions = {
        "bull": {
            "mood": "強気寄り。上昇の継続性を見ながら、過熱感と押し目の質を同時に確認する。",
            "palette": "deep navy, white, emerald green, cyan blue, restrained gold accents",
            "visual": "上昇チャート、整理されたマーケットボード、勢いのあるセクターを示すグリーンのカード",
            "character": "ガネーシャ先生は落ち着いて根拠を説明し、カワウソ君は前のめりに質問する。",
        },
        "bear": {
            "mood": "警戒寄り。下落・VIX上昇・金利変化を優先し、無理な追いかけ買いを避ける。",
            "palette": "deep navy, white, alert red, amber, cool gray",
            "visual": "リスク警戒パネル、下落チャート、守りを意識した赤と琥珀色の強調",
            "character": "ガネーシャ先生は冷静にリスクを整理し、カワウソ君は守り方を相談する。",
        },
        "neutral": {
            "mood": "様子見。方向感を決めつけず、強弱の分岐点と確認すべき数字を整理する。",
            "palette": "deep navy, white, amber, cyan, balanced green and red",
            "visual": "横ばいチャート、比較表、金利・為替・指数を並べた俯瞰パネル",
            "character": "ガネーシャ先生は判断を急がず、カワウソ君は次に見るべき条件を聞く。",
        },
    }
    return directions.get(tone, directions["neutral"])


def build_design_direction(
    task_id: str,
    task_config: dict[str, Any],
    summary: dict[str, Any],
    raw_data: dict[str, Any],
) -> dict[str, str]:
    tone = summary.get("market_tone", "neutral")
    direction = _tone_direction(tone)
    title = task_config.get("title", task_id)

    macro_labels = ", ".join(item.get("label", "") for item in raw_data.get("macro_items", [])[:4]) or "macro indicators"
    market_labels = ", ".join(item.get("label", "") for item in raw_data.get("items", [])[:6]) or "market indicators"

    image_prompt = "\n".join(
        [
            "Use case: mobile financial market digest hero background, no text.",
            f"Title context: {title}",
            f"Market mood: {direction['mood']}",
            f"Visual motifs: {direction['visual']}",
            f"Data themes to imply visually: {market_labels}; {macro_labels}",
            "Style: premium fintech editorial dashboard, high contrast, clean grid, polished illustration.",
            "Composition: portrait mobile layout with safe empty space for Japanese title and charts.",
            f"Color palette: {direction['palette']}",
            "Constraints: no readable text, no fabricated numbers, no logos, no watermark.",
        ]
    )

    canva_prompt = "\n".join(
        [
            "スマホで読みやすい日本語の金融市場ダイジェストを作成してください。",
            f"タイトル: {title}",
            f"結論バッジ: {summary.get('conclusion_label', '様子見')}",
            f"全体トーン: {direction['mood']}",
            f"キャラクター演出: {direction['character']}",
            "最優先: チャート、前日比ランキング、重要数字、AI要約を大きく見せる。",
            "構成: 1. タイトル 2. 結論 3. 直近6営業日のチャート 4. 前日比ランキング 5. 重要数字 6. ガネーシャ先生とカワウソ君の会話 7. 今日の作戦。",
            "デザイン: ダークネイビーの金融端末風。カードごとに余白を広く取り、文字背景を敷いて読みやすくする。",
            f"配色: {direction['palette']}",
            "禁止: 文字を小さくしすぎない。キャラクターを本文やグラフに重ねない。数字を推測で作らない。",
        ]
    )

    adobe_prompt = "\n".join(
        [
            "Adobe Express / Illustrator 向けデザイン指示:",
            "1080x1920pxの縦長キャンバス。背景は深いネイビー、カードは半透明の濃紺、境界線は青みの細線。",
            "タイトルは上部に大きく、結論バッジは右上。チャート領域を中央に大きく確保。",
            "ガネーシャ先生とカワウソ君は下部または横の吹き出しだけに配置し、本文には重ねない。",
            "上昇は緑、下落は赤、注意は琥珀色、未確認はグレーで統一。",
        ]
    )

    return {
        "image_prompt": image_prompt,
        "canva_prompt": canva_prompt,
        "adobe_prompt": adobe_prompt,
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
                "このファイルは、Canva / Adobe / 画像生成AIへ渡すためのデザイン指示書です。",
                "通知本文の数字は実データのみを使い、未取得データは未確認として扱います。",
                "",
                "## Canva Prompt",
                "",
                direction["canva_prompt"],
                "",
                "## Adobe Prompt",
                "",
                direction["adobe_prompt"],
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

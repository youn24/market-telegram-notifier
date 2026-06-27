from __future__ import annotations

from pathlib import Path
from typing import Any


CANVA_CANDIDATES = [
    {
        "tier": "standard",
        "name": "通常候補1: バランス型ダイジェスト",
        "url": "https://www.canva.com/d/DPv9rzR6p93bfmm",
        "best_for": "様子見や通常相場。読みやすさ優先。",
    },
    {
        "tier": "standard",
        "name": "通常候補2: 会話重視",
        "url": "https://www.canva.com/d/_LTDdGyt_jlnU4l",
        "best_for": "ガネーシャ先生とカワウソ君の説明を見せたい日。",
    },
    {
        "tier": "standard",
        "name": "通常候補3: 数字整理型",
        "url": "https://www.canva.com/d/ssL7DU1R--8RFr7",
        "best_for": "重要数字と要約を整理したい日。",
    },
    {
        "tier": "standard",
        "name": "通常候補4: シンプル通知型",
        "url": "https://www.canva.com/d/WM559WOBLIjI0pL",
        "best_for": "情報量を抑え、通知の見やすさを優先する日。",
    },
    {
        "tier": "premium",
        "name": "高品質候補1: 金融端末ダッシュボード",
        "url": "https://www.canva.com/d/WfdrW_9rcAlytLo",
        "best_for": "9:30や17:00など、チャートと判断ボードを強く見せたい日。",
    },
    {
        "tier": "premium",
        "name": "高品質候補2: 世界市場俯瞰",
        "url": "https://www.canva.com/d/d0pP4f28Y06Wvh1",
        "best_for": "7:00の全体マクロ、海外市場、金利、為替の俯瞰。",
    },
    {
        "tier": "premium",
        "name": "高品質候補3: リスク温度計",
        "url": "https://www.canva.com/d/rPz8xzMjxn0xpIp",
        "best_for": "VIX上昇、金利急変、警戒相場。",
    },
    {
        "tier": "premium",
        "name": "高品質候補4: 実戦シナリオ型",
        "url": "https://www.canva.com/d/I-J0mE4bOJBYa4f",
        "best_for": "強気/中立/警戒の3シナリオを見せたい日。",
    },
]


ADOBE_CONCEPTS = [
    {
        "name": "Adobe候補A: Express用スマホ速報カード",
        "best_for": "Telegramに貼る縦長カード。短い文と大きな数字を優先。",
        "prompt": "Adobe Expressで1080x1920px。深いネイビー背景、半透明カード、円形の地合いスコア、横棒ランキング、重要数字カードを大きく配置。",
    },
    {
        "name": "Adobe候補B: Illustrator用金融端末ボード",
        "best_for": "ブラウザ版や高品質レポートの見本。グリッドとチャートが主役。",
        "prompt": "Illustratorで金融端末風の情報ボード。12カラムグリッド、青い罫線、緑/赤の騰落表現、カードごとに十分な余白。",
    },
    {
        "name": "Adobe候補C: Firefly用ヒーロー背景",
        "best_for": "タイトル背景やヘッダー画像。文字なしの雰囲気づくり。",
        "prompt": "Adobe Fireflyで文字なしの金融市場ヒーロー背景。深いネイビー、光るチャート線、世界市場を示す抽象グリッド、数字やロゴは入れない。",
    },
]


def _candidate_index(task_id: str, tone: str, count: int) -> int:
    seed = sum(ord(char) for char in f"{task_id}:{tone}")
    return seed % max(1, count)


def _select_canva_candidate(task_id: str, task_config: dict[str, Any], tone: str) -> dict[str, str]:
    use_premium = (
        task_config.get("focus") == "macro"
        or task_id in {"japan_morning", "japan_close"}
        or tone in {"bull", "bear"}
    )
    tier = "premium" if use_premium else "standard"
    candidates = [candidate for candidate in CANVA_CANDIDATES if candidate["tier"] == tier]
    return candidates[_candidate_index(task_id, tone, len(candidates))]


def _select_adobe_concept(task_id: str, tone: str) -> dict[str, str]:
    if "morning" in task_id or task_id == "fx_morning":
        return ADOBE_CONCEPTS[2]
    if tone == "bear":
        return ADOBE_CONCEPTS[0]
    return ADOBE_CONCEPTS[1]


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
    canva_candidate = _select_canva_candidate(task_id, task_config, tone)
    adobe_concept = _select_adobe_concept(task_id, tone)

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
        "canva_candidate_name": canva_candidate["name"],
        "canva_candidate_url": canva_candidate["url"],
        "canva_candidate_tier": canva_candidate["tier"],
        "canva_candidate_reason": canva_candidate["best_for"],
        "adobe_concept_name": adobe_concept["name"],
        "adobe_concept_reason": adobe_concept["best_for"],
        "adobe_concept_prompt": adobe_concept["prompt"],
        "palette": direction["palette"],
        "mood": direction["mood"],
    }


def write_design_handoff(site_dir: Path, direction: dict[str, str]) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)
    brief_path = site_dir / "design-brief.md"
    canva_list = [
        f"- [{candidate['name']}]({candidate['url']}) / {candidate['tier']} / {candidate['best_for']}"
        for candidate in CANVA_CANDIDATES
    ]
    adobe_list = [
        f"- {concept['name']}: {concept['best_for']} / {concept['prompt']}"
        for concept in ADOBE_CONCEPTS
    ]
    brief_path.write_text(
        "\n".join(
            [
                "# Design Brief",
                "",
                "このファイルは、Canva / Adobe / 画像生成AIへ渡すためのデザイン指示書です。",
                "通知本文の数字は実データのみを使い、未取得データは未確認として扱います。",
                "",
                "## Selected Canva Candidate",
                "",
                f"- Name: {direction['canva_candidate_name']}",
                f"- Tier: {direction['canva_candidate_tier']}",
                f"- URL: {direction['canva_candidate_url']}",
                f"- Use when: {direction['canva_candidate_reason']}",
                "",
                "## Selected Adobe Concept",
                "",
                f"- Name: {direction['adobe_concept_name']}",
                f"- Use when: {direction['adobe_concept_reason']}",
                f"- Prompt: {direction['adobe_concept_prompt']}",
                "",
                "## All Canva Candidates",
                "",
                *canva_list,
                "",
                "## All Adobe Concepts",
                "",
                *adobe_list,
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

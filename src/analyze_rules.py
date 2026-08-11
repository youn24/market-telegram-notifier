from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def _format_number(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "未確認"
    return f"{value:,.{digits}f}"


def _format_pct(value: float | None) -> str:
    if value is None:
        return "未確認"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _classify_change(change_pct: float | None, thresholds: dict[str, Any]) -> str:
    if change_pct is None:
        return "未確認"

    if change_pct >= thresholds.get("strong_up_pct", 1.0):
        return "強めの上昇"
    if change_pct >= thresholds.get("moderate_up_pct", 0.3):
        return "小幅高"
    if change_pct <= thresholds.get("strong_down_pct", -1.0):
        return "強めの下落"
    if change_pct <= thresholds.get("moderate_down_pct", -0.3):
        return "小幅安"
    return "横ばい圏"


def _speaker_profile(task_id: str, task_config: dict[str, Any]) -> tuple[str, str]:
    category = task_config.get("category", "")
    if task_config.get("focus") == "macro":
        return "ガネーシャ先生", "世界の株・金利・為替・商品をまとめて読む"
    if category == "fx":
        return "ガネーシャ先生", "為替の流れを先に読む"
    if category == "japan_market":
        return "ガネーシャ先生", "日本株の地合いをすばやく整理"
    return "ガネーシャ先生", "市況をコンパクトに要約"


def _market_tone(raw_data: dict[str, Any], thresholds: dict[str, Any]) -> str:
    change_values = [item.get("change_pct") for item in raw_data.get("items", []) if item.get("change_pct") is not None]
    if not change_values:
        return "neutral"

    average_change = sum(change_values) / len(change_values)
    if average_change >= thresholds.get("moderate_up_pct", 0.3):
        return "bull"
    if average_change <= thresholds.get("moderate_down_pct", -0.3):
        return "bear"
    return "neutral"


def _variant_index(generated_at: str, *parts: str, modulo: int = 3) -> int:
    seed = sum(ord(char) for char in "|".join([generated_at, *parts]))
    return seed % max(1, modulo)


def _change_groups(raw_data: dict[str, Any], thresholds: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    positive_items = [
        item
        for item in raw_data.get("items", [])
        if (item.get("change_pct") or 0) >= thresholds.get("moderate_up_pct", 0.3)
    ]
    negative_items = [
        item
        for item in raw_data.get("items", [])
        if (item.get("change_pct") or 0) <= thresholds.get("moderate_down_pct", -0.3)
    ]
    return positive_items, negative_items


def _labels(items: list[dict[str, Any]], fallback: str) -> str:
    return "、".join(item.get("label", "") for item in items[:2] if item.get("label")) or fallback


def _macro_temperature(raw_data: dict[str, Any]) -> str:
    macro_items = raw_data.get("macro_items", [])
    us10y = _find_item(macro_items, "US10Y")
    vix = _find_item(macro_items, "VIX")
    dollar = _find_item(macro_items, "DOLLAR_BROAD")
    reads: list[str] = []

    if vix and vix.get("change_pct") is not None:
        if vix["change_pct"] >= 3:
            reads.append("VIX上昇で警戒温度は高め")
        elif vix["change_pct"] <= -3:
            reads.append("VIX低下でリスク許容は改善")
    if us10y and us10y.get("change_pct") is not None:
        reads.append("米金利上昇" if us10y["change_pct"] > 0 else "米金利低下")
    if dollar and dollar.get("change_pct") is not None:
        reads.append("ドル強め" if dollar["change_pct"] > 0 else "ドル弱め")

    return "、".join(reads[:2]) if reads else "マクロは未確認を残して確認"


def _research_lines(raw_data: dict[str, Any]) -> list[str]:
    research = raw_data.get("research", {})
    items = research.get("items", [])
    if not items:
        note = research.get("note", "ニュース検索は未確認")
        return [f"材料検索: {note}"]

    lines: list[str] = []
    for item in items[:4]:
        title = item.get("title", "未確認")
        source = item.get("source", "媒体未確認")
        published = item.get("published", "日時未確認")
        score = item.get("score", "未採点")
        reason = item.get("research_reason", "")
        lines.append(f"{title}（{source} / {published} / score={score} / {reason}）")
    return lines


def _research_confidence_line(raw_data: dict[str, Any]) -> str:
    confidence = raw_data.get("research", {}).get("confidence", {})
    label = confidence.get("label", "低")
    score = confidence.get("score", 0)
    reason = confidence.get("reason", "検索材料は未確認")
    return f"リサーチ信頼度: {label}（{score}/100）- {reason}"


def _research_theme_lines(raw_data: dict[str, Any]) -> list[str]:
    items = raw_data.get("research", {}).get("items", [])
    keyword_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for item in items:
        for keyword in item.get("matched_keywords", []):
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        for category in item.get("material_categories", []):
            category_counts[category] = category_counts.get(category, 0) + 1

    lines: list[str] = []
    for category, count in sorted(category_counts.items(), key=lambda pair: pair[1], reverse=True)[:3]:
        lines.append(f"材料カテゴリ: {category}（関連見出し {count}件）")

    if not keyword_counts and not lines:
        return ["重要テーマ: ニュース材料は未確認または重要語一致が少なめです。"]

    ranked = sorted(keyword_counts.items(), key=lambda pair: pair[1], reverse=True)[:4]
    lines.extend(f"重要テーマ: {keyword}（関連見出し {count}件）" for keyword, count in ranked)
    return lines[:5]


def _research_coverage_lines(raw_data: dict[str, Any]) -> list[str]:
    coverage = raw_data.get("research", {}).get("coverage", {})
    if not coverage:
        return ["検索カバレッジ: 未確認"]

    lines = [
        f"検索カバレッジ: {coverage.get('label', '未確認')}（{coverage.get('score', 0)}/100）",
    ]
    for check in coverage.get("checks", [])[:5]:
        status = str(check.get("status", "partial"))
        marker = "OK" if status == "ok" else "不足" if status == "missing" else "一部"
        lines.append(f"{marker}: {check.get('label', '確認項目')} - {check.get('detail', '未確認')}")

    if coverage.get("followup_triggered"):
        lines.append(f"追加検索: {len(coverage.get('followup_queries', []))}本")

    missing_categories = coverage.get("missing_categories", [])
    if missing_categories:
        lines.append("不足観点: " + " / ".join(str(category) for category in missing_categories[:3]))
    return lines[:7]


def _research_evidence_lines(raw_data: dict[str, Any]) -> list[str]:
    packs = raw_data.get("research", {}).get("evidence_packs", [])
    if not packs:
        return ["カテゴリ別根拠: 未確認"]

    lines: list[str] = []
    for pack in packs[:6]:
        category = pack.get("category", "未分類")
        status = str(pack.get("status", "missing"))
        if status == "ok":
            marker = "根拠あり"
        elif status == "candidate":
            marker = "候補のみ"
        else:
            marker = "不足"
        source = pack.get("top_source", "媒体未確認")
        score = pack.get("top_score", "未採点")
        title = str(pack.get("top_title", "未確認"))
        detail = pack.get("detail", "未確認")
        lines.append(f"{category}: {marker} - {detail} / {source} / score={score} / {title}")
    return lines


def _research_evidence_briefs(raw_data: dict[str, Any]) -> list[str]:
    packs = raw_data.get("research", {}).get("evidence_packs", [])
    if not packs:
        return ["根拠: 未確認"]

    briefs: list[str] = []
    for pack in packs[:5]:
        category = str(pack.get("category", "未分類"))
        status = str(pack.get("status", "missing"))
        if status == "ok":
            marker = "根拠あり"
        elif status == "candidate":
            marker = "候補のみ"
        else:
            marker = "不足"
        adopted_count = pack.get("adopted_count", 0)
        source_count = pack.get("source_count", 0)
        fresh_count = pack.get("fresh_count", 0)
        source = pack.get("top_source", "媒体未確認")
        briefs.append(f"{category}: {marker} / 採用{adopted_count}件 / 媒体{source_count}種 / 24h内{fresh_count}件 / {source}")
    return briefs


def _research_digest(raw_data: dict[str, Any]) -> str:
    research = raw_data.get("research", {})
    items = research.get("items", [])
    if not items:
        return research.get("note", "材料検索は未確認です。")

    source_names = []
    for item in items[:3]:
        source = item.get("source")
        if source and source not in source_names:
            source_names.append(source)
    top_item = items[0]
    score = top_item.get("score", "未採点")
    confidence = raw_data.get("research", {}).get("confidence", {})
    confidence_label = confidence.get("label", "低")
    return f"材料検索では{len(items)}件を確認。信頼度は{confidence_label}、最上位材料はscore {score}、主な出所は{'、'.join(source_names) or '未確認'}です。"


def _nikkei225jp_lines(raw_data: dict[str, Any]) -> list[str]:
    data = raw_data.get("nikkei225jp", {}) or {}
    status = data.get("status")
    if status != "ok":
        return [str(data.get("note", "nikkei225jp.com参照は未確認です。"))]

    lines = [str(data.get("note", "nikkei225jp.comを参照しました。"))]
    links = data.get("content_links", [])[:5]
    schedules = data.get("schedule_items", [])[:3]
    if links:
        labels = "、".join(str(item.get("label", "未確認")) for item in links)
        lines.append(f"参照候補: {labels}")
    if schedules:
        schedule_text = "、".join(f"{item.get('date', '未確認')} {item.get('event', '未確認')}" for item in schedules)
        lines.append(f"予定候補: {schedule_text}")
    for note in data.get("watch_notes", [])[:2]:
        lines.append(str(note))
    return lines[:5]


def _clip_analysis_text(text: str, max_chars: int = 60) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def _deep_summary_lines(
    raw_data: dict[str, Any],
    tone: str,
    conclusion_text: str,
    opportunities: list[str],
    cautions: list[str],
    research_confidence_line: str,
    research_evidence_lines: list[str],
) -> list[str]:
    tone_label = {"bull": "強気寄り", "bear": "警戒", "neutral": "様子見"}.get(tone, "様子見")
    evidence_line = research_evidence_lines[0] if research_evidence_lines else research_confidence_line
    unknowns = []
    for label, note in raw_data.get("highlights", {}).items():
        if "未確認" in str(note):
            unknowns.append(
                {
                    "speculative_positions": "投機筋",
                    "earnings": "決算",
                    "ratings": "信用評価",
                    "supply_demand": "需給",
                    "analysis": "分析",
                }.get(label, label)
            )
    unknown_text = "、".join(unknowns[:3]) if unknowns else "不足カテゴリと未取得データ"
    return [
        f"結論: {_clip_analysis_text(f'{tone_label}。{conclusion_text}')}",
        f"根拠: {_clip_analysis_text(evidence_line)}",
        f"注視: {_clip_analysis_text(opportunities[0] if opportunities else '強い銘柄の継続性と出来高を確認します。')}",
        f"回避: {_clip_analysis_text(cautions[0] if cautions else '根拠の薄い飛びつきと過度な枚数を避けます。')}",
        f"未確認: {_clip_analysis_text(f'{unknown_text}は断定せず、取得済み数値を優先します。')}",
    ]


def _theme_block(task_id: str, task_config: dict[str, Any], tone: str, generated_at: str) -> tuple[str, str]:
    day_seed = int(generated_at[8:10])
    theme_map = {
        "fx": [
            ("本日のテーマ", "通貨の温度差を先に読む"),
            ("今日の視点", "ドル主導かクロス円主導かを切り分ける"),
            ("朝の作戦", "飛びつきより流れの継続性を確認する"),
        ],
        "japan_market": [
            ("本日のテーマ", "寄り後の強弱を3分で整理する"),
            ("今日の視点", "指数より先に主役セクターを探す"),
            ("朝の作戦", "初動の質と押し目の強さを比べる"),
        ],
        "macro": [
            ("本日のマクロ地図", "米国株・金利・為替・商品からリスク選好を読む"),
            ("朝の世界地合い", "株・債券・ドル・原油・金の方向を一枚で確認する"),
            ("寄り前の大局観", "日本株を見る前に世界の資金の流れを整理する"),
        ],
        "default": [
            ("本日のテーマ", "数字から先に地合いを読む"),
            ("今日の視点", "未確認を残したまま断定しない"),
            ("朝の作戦", "勢いと継続性を分けて考える"),
        ],
    }
    if task_config.get("focus") == "macro":
        category_key = "macro"
    else:
        category_key = "fx" if task_id.startswith("fx") else "japan_market" if task_id.startswith("japan") else "default"
    choices = theme_map[category_key]
    title, subtitle = choices[day_seed % len(choices)]
    tone_suffix = {
        "bull": "強気寄りの地合いを丁寧に追います",
        "bear": "下振れリスクを先に意識します",
        "neutral": "様子見と見極めを優先します",
    }[tone]
    return title, f"{subtitle} / {tone_suffix}"


def _student_question(
    task_id: str,
    task_config: dict[str, Any],
    tone: str,
    raw_data: dict[str, Any],
    thresholds: dict[str, Any],
    generated_at: str,
) -> str:
    positive_items, negative_items = _change_groups(raw_data, thresholds)
    strong_side = _labels(positive_items, "強い指数")
    weak_side = _labels(negative_items, "弱い指数")
    macro_temp = _macro_temperature(raw_data)
    variant = _variant_index(generated_at, task_id, tone, modulo=4)

    if task_config.get("focus") == "macro":
        patterns = {
            "bull": [
                f"先生、{strong_side}が支えていますが、今日はリスクオンとして見ていいですか？",
                f"先生、{macro_temp}なら、日本株の寄り前は攻め目線を少し持てますか？",
                f"先生、世界の資金は株へ向かっている雰囲気ですか？それともまだ選別ですか？",
                f"先生、今朝は追うより押し目待ちですか？強い地合いの見方を教えてください。",
            ],
            "bear": [
                f"先生、{weak_side}が重いです。今日は寄り前から守りを厚くした方がいいですか？",
                f"先生、{macro_temp}なら、リスク回避が日本株にも波及しそうですか？",
                f"先生、下げの初動なのか一時的な調整なのか、どこを見ればいいですか？",
                f"先生、今日は買い場探しより、まず地合いの悪化確認が先ですか？",
            ],
            "neutral": [
                f"先生、{macro_temp}で強弱が割れています。今日は方向感待ちですか？",
                "先生、世界地合いがはっきりしません。寄り付き後は何を一番に見ればいいですか？",
                "先生、株・金利・為替が同じ方向を向いていない時は、どう判断すればいいですか？",
                "先生、今朝は無理に結論を出さず、どの条件が揃ったら動くべきですか？",
            ],
        }
        return patterns[tone][variant]
    if task_id.startswith("fx"):
        patterns = {
            "bull": [
                "先生、いまは円安の流れに素直についていっていいですか？",
                "先生、ドル買いが続くなら、押し目を待つ方が良さそうですか？",
                "先生、為替のモメンタムはまだ残っていますか？",
                "先生、上に走った後の高値掴みを避けるには何を見ればいいですか？",
            ],
            "bear": [
                "先生、いまは逆張りよりリスク回避を優先した方がいいですか？",
                "先生、円高方向に振れるなら、戻りの重さを見た方がいいですか？",
                "先生、ドルの失速が本物かどうか、どこで確認しますか？",
                "先生、急な巻き戻しが来た時は、追わずに待つべきですか？",
            ],
            "neutral": [
                "先生、いまの為替は方向感待ちですか？",
                "先生、レンジっぽい時はどちら側のブレイクを待てばいいですか？",
                "先生、為替が煮詰まっている時、先に見るべき材料は金利ですか？",
                "先生、今は値幅よりもタイミングを絞る局面ですか？",
            ],
        }
        return patterns[tone][variant]

    patterns = {
        "bull": [
            f"先生、寄り後は{strong_side}の流れに素直についていっていい場面ですか？",
            "先生、今日は強い銘柄の押し目を待つ作戦でいいですか？",
            "先生、指数が強い時でも、飛びつきを避けるポイントはどこですか？",
            "先生、買いが広がっているのか、一部だけ強いのかをどう見ますか？",
        ],
        "bear": [
            f"先生、{weak_side}が重いです。今日は無理に入らず守り寄りで見た方がいいですか？",
            "先生、寄り後に戻しても、戻り売りを警戒した方がいいですか？",
            "先生、今日は反発狙いより、地合いの悪化確認が先ですか？",
            "先生、弱い日に触ってはいけない銘柄の見分け方を教えてください。",
        ],
        "neutral": [
            "先生、今日は飛びつくより見極め優先ですか？",
            "先生、強弱が混ざる日は、最初の何分を観察すればいいですか？",
            "先生、方向感が薄い時は、出来高と板のどちらを重視しますか？",
            "先生、今は銘柄選別の精度を上げる日ですか？",
        ],
    }
    return patterns[tone][variant]


def _teacher_answer(
    raw_data: dict[str, Any],
    thresholds: dict[str, Any],
    tone: str,
    task_config: dict[str, Any],
    generated_at: str,
) -> str:
    positive_items, negative_items = _change_groups(raw_data, thresholds)
    strong_side = _labels(positive_items, "強い指数")
    weak_side = _labels(negative_items, "弱い指数")
    macro_temp = _macro_temperature(raw_data)
    variant = _variant_index(generated_at, task_config.get("category", ""), tone, modulo=4)

    if tone == "bull" and positive_items:
        patterns = [
            f"{strong_side}が支えています。追いかけるより、押し目の浅さと出来高の残り方を見たいです。",
            f"地合いは前向きです。ただし強い日ほど高値掴みが出やすいので、初動後の二段目を確認しましょう。",
            f"{macro_temp}です。買い目線は残しますが、指数だけでなく主役銘柄の広がりを見ます。",
            f"リスク選好はあります。とはいえ『強いから買う』ではなく、『崩れないから拾う』感覚が大事です。",
        ]
        return patterns[variant]
    if tone == "bear" and negative_items:
        patterns = [
            f"{weak_side}が重いです。今日は買い急がず、戻りの鈍さと下げ止まりの質を確認します。",
            f"守りを厚くします。反発しても出来高が伴わないなら、無理に追わない方が安全です。",
            f"{macro_temp}です。下げたから安いではなく、売り圧力が抜けたかを先に見ます。",
            f"今日は『取る日』より『残す日』の意識です。焦らず、悪い流れが止まるまで待ちましょう。",
        ]
        return patterns[variant]

    patterns = [
        "まだ強弱が混ざっています。最初の値動きだけで決めず、続く側に寄せていきましょう。",
        f"{macro_temp}です。方向感が薄い時は、勝負より観察の精度を上げる局面です。",
        "結論を急がなくて大丈夫です。出来高、値持ち、主役銘柄の有無を順番に確認しましょう。",
        "今日は地合いの輪郭がまだぼんやりしています。シナリオを持ちつつ、条件が揃うまで待ちます。",
    ]
    return patterns[variant]


def _conclusion_block(raw_data: dict[str, Any], thresholds: dict[str, Any], tone: str) -> tuple[str, str]:
    positive_items = [item for item in raw_data.get("items", []) if (item.get("change_pct") or 0) >= thresholds.get("moderate_up_pct", 0.3)]
    negative_items = [item for item in raw_data.get("items", []) if (item.get("change_pct") or 0) <= thresholds.get("moderate_down_pct", -0.3)]
    macro_reads = _macro_read(raw_data)
    action = _action_label(tone, raw_data)

    if tone == "bull":
        anchor = "、".join(item["label"] for item in positive_items[:2]) or "主要指数"
        return action, f"{anchor}が支えています。{macro_reads[0]} 強い側は見ますが、飛びつきより押し目と継続性を優先します。"
    if tone == "bear":
        anchor = "、".join(item["label"] for item in negative_items[:2]) or "主要指数"
        return action, f"{anchor}が重いです。{macro_reads[0]} 今日は無理に追わず、戻りの重さと見送りの精度を優先します。"
    return action, f"強弱がまだ割れています。{macro_reads[0]} 初動だけで決めず、継続する側が見えるまで待ちたい局面です。"


def _build_watchpoints(raw_data: dict[str, Any], thresholds: dict[str, Any]) -> tuple[list[str], list[str]]:
    opportunities: list[str] = []
    cautions: list[str] = []

    for item in raw_data.get("items", []):
        label = item.get("label", "")
        change_pct = item.get("change_pct")
        if change_pct is None:
            continue
        if change_pct >= thresholds.get("moderate_up_pct", 0.3):
            opportunities.append(f"{label}は{change_pct:+.2f}%で底堅く、強い側の継続を確認したいです。")
        elif change_pct <= thresholds.get("moderate_down_pct", -0.3):
            cautions.append(f"{label}は{change_pct:+.2f}%で弱く、逆張りより戻りの重さを見たいです。")

    if not opportunities:
        opportunities.append("飛びつくほどの強い追い風はまだ限定的で、押し目の質を見て判断したいです。")
    if not cautions:
        cautions.append("大崩れのシグナルは強くなく、過度に弱気へ寄せすぎないことも大事です。")

    return opportunities[:3], cautions[:3]


def _numeric_change(item: dict[str, Any] | None) -> float | None:
    if not item:
        return None
    value = item.get("change_pct")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _numeric_bps(item: dict[str, Any] | None) -> float | None:
    if not item:
        return None
    value = item.get("change_bps")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _score_band(score: int) -> str:
    if score >= 70:
        return "攻め優位"
    if score >= 55:
        return "やや強い"
    if score >= 45:
        return "中立"
    if score >= 30:
        return "守り優位"
    return "強い警戒"


def _build_analysis_dashboard(raw_data: dict[str, Any], tone: str, thresholds: dict[str, Any]) -> dict[str, Any]:
    items = raw_data.get("items", [])
    macro_items = raw_data.get("macro_items", [])
    changes = [float(item["change_pct"]) for item in items if isinstance(item.get("change_pct"), (int, float))]
    up_count = len([value for value in changes if value > 0])
    down_count = len([value for value in changes if value < 0])
    breadth = round((up_count / len(changes)) * 100) if changes else 50
    average_change = sum(changes) / len(changes) if changes else 0.0

    us10y = _find_item(macro_items, "US10Y")
    vix = _find_item(macro_items, "VIX")
    dollar = _find_item(macro_items, "DOLLAR_BROAD")
    spread = _find_item(macro_items, "YIELD_2S10S")
    vix_change = _numeric_change(vix)
    us10y_bps = _numeric_bps(us10y)
    dollar_change = _numeric_change(dollar)

    risk_points = 0
    risk_reasons: list[str] = []
    if vix_change is not None:
        if vix_change >= 3:
            risk_points += 22
            risk_reasons.append(f"VIXが{vix_change:+.2f}%で警戒温度上昇")
        elif vix_change <= -3:
            risk_points -= 10
            risk_reasons.append(f"VIXが{vix_change:+.2f}%で過度な警戒は後退")
    if us10y_bps is not None and us10y_bps >= 5:
        risk_points += 10
        risk_reasons.append(f"米10年金利が{us10y_bps:+.1f}bpで株の重石に注意")
    if dollar_change is not None and dollar_change >= 0.5:
        risk_points += 6
        risk_reasons.append(f"ドル指数が{dollar_change:+.2f}%で外需・為替感応を確認")
    if spread and spread.get("current") is not None:
        risk_reasons.append(f"2年10年スプレッドは{spread['current']:.2f}%")

    market_score = 50 + average_change * 12 + (breadth - 50) * 0.35 - risk_points * 0.45
    if tone == "bull":
        market_score += 6
    elif tone == "bear":
        market_score -= 6
    score = max(0, min(100, round(market_score)))

    leaders = sorted(
        [item for item in items if isinstance(item.get("change_pct"), (int, float))],
        key=lambda item: float(item.get("change_pct", 0)),
        reverse=True,
    )
    laggards = list(reversed(leaders))
    leader_text = "、".join(f"{item.get('label')} {_format_pct(item.get('change_pct'))}" for item in leaders[:2]) or "未確認"
    laggard_text = "、".join(f"{item.get('label')} {_format_pct(item.get('change_pct'))}" for item in laggards[:2]) or "未確認"

    if score >= 65:
        action = "強い銘柄の浅い押し目だけを候補にし、飛び乗りは避ける"
    elif score <= 40:
        action = "守りを優先し、戻り売り・下げ止まり確認までは無理に入らない"
    else:
        action = "方向が出るまで観察し、出来高と値持ちが揃った銘柄だけを見る"

    checklist = [
        f"地合いスコア: {score}/100（{_score_band(score)}）",
        f"上昇/下落数: {up_count} / {down_count}、平均変化率は{average_change:+.2f}%",
        f"追い風: {leader_text}",
        f"逆風: {laggard_text}",
        f"実戦方針: {action}",
    ]
    if risk_reasons:
        checklist.append(f"リスク温度: {' / '.join(risk_reasons[:2])}")

    return {
        "score": score,
        "band": _score_band(score),
        "breadth": breadth,
        "up_count": up_count,
        "down_count": down_count,
        "average_change": average_change,
        "leader_text": leader_text,
        "laggard_text": laggard_text,
        "risk_reasons": risk_reasons[:3] or ["マクロリスクは未確認を残して判断"],
        "action": action,
        "checklist": checklist,
    }


def _format_macro_value(item: dict[str, Any]) -> str:
    current = item.get("current")
    unit = item.get("unit", "")
    if current is None:
        return "未確認"
    return f"{current:,.2f}{unit}"


def _format_item_line(item: dict[str, Any]) -> str:
    return (
        f"- {item['label']}: "
        f"{_format_number(item.get('current'))} "
        f"({_format_pct(item.get('change_pct'))})"
    )


def _format_macro_line(item: dict[str, Any]) -> str:
    change_bps = item.get("change_bps")
    change_text = f"{change_bps:+.1f}bp" if isinstance(change_bps, (int, float)) else _format_pct(item.get("change_pct"))
    return f"- {item['label']}: {_format_macro_value(item)} ({change_text})"


def _build_visual_items(raw_data: dict[str, Any]) -> list[dict[str, Any]]:
    preferred_keys = ["NIKKEI225", "TOPIX", "SP500", "NASDAQ", "USDJPY", "US10Y", "VIX", "YIELD_2S10S"]
    source_items = raw_data.get("items", []) + raw_data.get("macro_items", [])
    by_key = {item.get("key"): item for item in source_items}
    ordered_items = [by_key[key] for key in preferred_keys if key in by_key]
    ordered_items.extend(item for item in source_items if item not in ordered_items)

    visual_items: list[dict[str, Any]] = []
    for item in ordered_items[:8]:
        current = item.get("current")
        unit = item.get("unit", "")
        visual_items.append(
            {
                "key": item.get("key", ""),
                "label": item.get("label", "未確認"),
                "value": "未確認" if current is None else f"{current:,.2f}{unit}",
                "change_pct": item.get("change_pct"),
                "change_text": (
                    f"{item.get('change_bps'):+.1f}bp"
                    if isinstance(item.get("change_bps"), (int, float))
                    else _format_pct(item.get("change_pct"))
                ),
                "comparison_group": item.get("comparison_group", "market_return"),
                "as_of": item.get("as_of"),
                "source": item.get("source", "未確認"),
                "quality_status": item.get("quality_status", "unavailable"),
            }
        )
    return visual_items


def _build_sparkline_items(raw_data: dict[str, Any]) -> list[dict[str, Any]]:
    preferred_keys = ["NIKKEI225", "TOPIX", "SP500", "NASDAQ", "USDJPY", "US10Y", "VIX", "DOLLAR_BROAD"]
    source_items = raw_data.get("items", []) + raw_data.get("macro_items", [])
    by_key = {item.get("key"): item for item in source_items}
    ordered_items = [by_key[key] for key in preferred_keys if key in by_key]
    ordered_items.extend(item for item in source_items if item not in ordered_items)

    sparkline_items: list[dict[str, Any]] = []
    for item in ordered_items:
        series = _sorted_series(item.get("series", []), limit=6)
        if len(series) < 2:
            continue
        sparkline_items.append(
            {
                "key": item.get("key", ""),
                "label": item.get("label", "未確認"),
                "series": series,
                "change_pct": item.get("change_pct"),
                "comparison_group": item.get("comparison_group", "market_return"),
                "as_of": item.get("as_of"),
            }
        )
        if len(sparkline_items) >= 8:
            break
    return sparkline_items


def _build_data_quality(raw_data: dict[str, Any]) -> dict[str, Any]:
    source_items = raw_data.get("items", []) + raw_data.get("macro_items", [])
    total = len(source_items)
    verified_items = [
        item
        for item in source_items
        if item.get("status") == "ok" and item.get("quality_status") == "verified"
    ]
    unavailable_items = [item for item in source_items if item not in verified_items]
    dates = sorted(
        str(item.get("as_of"))
        for item in verified_items
        if item.get("as_of")
    )
    coverage = round(len(verified_items) / total * 100) if total else 0
    latest_as_of = dates[-1] if dates else None
    oldest_as_of = dates[0] if dates else None
    unavailable_labels = [str(item.get("label", "未確認")) for item in unavailable_items[:4]]

    if coverage >= 90:
        label = "高"
    elif coverage >= 70:
        label = "中"
    else:
        label = "要確認"

    return {
        "verified": len(verified_items),
        "total": total,
        "unavailable": len(unavailable_items),
        "coverage": coverage,
        "label": label,
        "latest_as_of": latest_as_of,
        "oldest_as_of": oldest_as_of,
        "unavailable_labels": unavailable_labels,
        "badge": f"確認済 {len(verified_items)}/{total}" if total else "確認済 0/0",
        "as_of_label": f"最新基準日 {latest_as_of}" if latest_as_of else "基準日 未確認",
    }


def _find_item(items: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    for item in items:
        if item.get("key") == key:
            return item
    return None


def _parse_series_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _sorted_series(series: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    points_by_date: dict[date, float] = {}
    for point in series:
        point_date = _parse_series_date(point.get("date"))
        value = point.get("value")
        if point_date is None or value is None:
            continue
        try:
            points_by_date[point_date] = float(value)
        except (TypeError, ValueError):
            continue
    return [
        {"date": point_date.isoformat(), "value": value}
        for point_date, value in sorted(points_by_date.items(), key=lambda pair: pair[0])[-limit:]
    ]


def _macro_read(raw_data: dict[str, Any]) -> list[str]:
    macro_items = raw_data.get("macro_items", [])
    reads: list[str] = []

    us10y = _find_item(macro_items, "US10Y")
    vix = _find_item(macro_items, "VIX")
    spread = _find_item(macro_items, "YIELD_2S10S")
    dollar = _find_item(macro_items, "DOLLAR_BROAD")

    if us10y and us10y.get("change_pct") is not None:
        direction = "上昇" if us10y["change_pct"] > 0 else "低下"
        reads.append(f"米10年金利は{direction}方向で、株のバリュエーションには影響を見たいです。")
    if vix and vix.get("change_pct") is not None:
        if vix["change_pct"] >= 3:
            reads.append("VIXが上がっており、リスク回避の気配を少し強めに見ます。")
        elif vix["change_pct"] <= -3:
            reads.append("VIXが低下しており、過度な警戒は少し和らいでいます。")
    if spread and spread.get("current") is not None:
        reads.append(f"2年10年スプレッドは{spread['current']:.2f}%で、金利差の方向を確認します。")
    if dollar and dollar.get("change_pct") is not None:
        direction = "強含み" if dollar["change_pct"] > 0 else "弱含み"
        reads.append(f"ドル指数は{direction}で、為替と外需株への影響を見ます。")

    if not reads:
        reads.append("マクロ指標は未確認が残るため、指数と為替の実測値を優先します。")
    return reads[:3]


def _action_label(tone: str, raw_data: dict[str, Any]) -> str:
    macro_items = raw_data.get("macro_items", [])
    vix = _find_item(macro_items, "VIX")
    us10y = _find_item(macro_items, "US10Y")

    if tone == "bull":
        if vix and (vix.get("change_pct") or 0) > 3:
            return "強気寄りだが追いかけ注意"
        return "押し目待ち"
    if tone == "bear":
        return "守り寄り"
    if us10y and abs(us10y.get("change_pct") or 0) > 2:
        return "金利確認"
    return "様子見"


def _build_scenarios(raw_data: dict[str, Any], tone: str) -> list[str]:
    macro_reads = _macro_read(raw_data)
    if tone == "bull":
        return [
            "強気シナリオ: 指数が崩れず、強い銘柄の押し目が浅いなら順張り候補を探します。",
            "中立シナリオ: 初動だけ強く、その後の出来高が細るなら見送りを優先します。",
            f"警戒シナリオ: {macro_reads[0]}",
        ]
    if tone == "bear":
        return [
            "強気シナリオ: 下げてもすぐ戻し、主力株に買い直しが入るなら短期反発を確認します。",
            "中立シナリオ: 指数が方向感なく上下するなら、無理に枚数を増やしません。",
            "警戒シナリオ: 弱い指数が戻りで止まるなら、追いかけ買いは避けます。",
        ]
    return [
        "強気シナリオ: 直近高値を抜く銘柄が増えるなら、強い側に少し寄せます。",
        "中立シナリオ: 強弱が割れるなら、出来高と継続性が出るまで待ちます。",
        "警戒シナリオ: 指数より先に個別が崩れるなら、守りを優先します。",
    ]


def _build_commentary(
    task_id: str,
    task_config: dict[str, Any],
    raw_data: dict[str, Any],
    thresholds: dict[str, Any],
) -> list[str]:
    comments: list[str] = []
    positive_items = [item for item in raw_data.get("items", []) if (item.get("change_pct") or 0) >= thresholds.get("moderate_up_pct", 0.3)]
    negative_items = [item for item in raw_data.get("items", []) if (item.get("change_pct") or 0) <= thresholds.get("moderate_down_pct", -0.3)]
    tone = _market_tone(raw_data, thresholds)

    if tone == "bull" and positive_items:
        joined = "、".join(item["label"] for item in positive_items[:3])
        comments.append(f"{joined}がしっかりしていて、買いが入りやすい地合いです。")
    if tone == "bear" and negative_items:
        joined = "、".join(item["label"] for item in negative_items[:3])
        comments.append(f"{joined}は弱めなので、追いかけ買いは少し慎重に見たいです。")
    if tone == "neutral":
        comments.append("強弱がまだ混ざっていて、飛びつくより見極めを優先したい場面です。")

    comments.extend(_macro_read(raw_data))

    unavailable_labels = []
    for label, note in raw_data.get("highlights", {}).items():
        if "未確認" in str(note):
            pretty = {
                "speculative_positions": "投機筋",
                "earnings": "決算",
                "ratings": "信用評価",
                "supply_demand": "需給",
                "analysis": "分析",
            }.get(label, label)
            unavailable_labels.append(pretty)
    if unavailable_labels:
        comments.append(f"{'、'.join(unavailable_labels)}は未確認なので、ここは断定せずに進めます。")

    comments.append(_research_digest(raw_data))

    if not comments:
        comments.append("大きな偏りはまだ薄く、初動の勢いと押し目の質を見たい場面です。")

    return comments[:3]


def build_summary(
    task_id: str,
    task_config: dict[str, Any],
    raw_data: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    thresholds = rules.get("thresholds", {})
    default_no_signal = rules.get("messages", {}).get("no_signal", "目立ったシグナルは未確認")
    generated_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    speaker_name, speaker_role = _speaker_profile(task_id, task_config)
    tone = _market_tone(raw_data, thresholds)
    theme_title, theme_subtitle = _theme_block(task_id, task_config, tone, generated_at)

    lines: list[str] = []
    market_lines: list[str] = []
    macro_lines: list[str] = []
    signal_lines: list[str] = []

    for item in raw_data.get("items", []):
        line = _format_item_line(item)
        market_lines.append(line)
        lines.append(line)

        signal = _classify_change(item.get("change_pct"), thresholds)
        signal_lines.append(f"- {item['label']}: {signal}")

    for item in raw_data.get("macro_items", []):
        line = _format_macro_line(item)
        macro_lines.append(line)
        lines.append(line)
        signal = _classify_change(item.get("change_pct"), thresholds)
        signal_lines.append(f"- {item['label']}: {signal}")

    for label, note in raw_data.get("highlights", {}).items():
        pretty = {
            "speculative_positions": "投機筋",
            "earnings": "決算",
            "ratings": "信用評価",
            "supply_demand": "需給",
            "analysis": "分析",
        }.get(label, label)
        lines.append(f"- {pretty}: {note}")

    if not raw_data.get("items"):
        signal_lines.append(f"- {default_no_signal}")

    body = "\n".join(
        [
            "主要項目",
            *lines,
            "",
            "簡易シグナル",
            *signal_lines,
        ]
    )

    commentary = _build_commentary(task_id, task_config, raw_data, thresholds)
    research_lines = _research_lines(raw_data)
    research_theme_lines = _research_theme_lines(raw_data)
    research_confidence_line = _research_confidence_line(raw_data)
    research_coverage_lines = _research_coverage_lines(raw_data)
    research_evidence_lines = _research_evidence_lines(raw_data)
    research_evidence_briefs = _research_evidence_briefs(raw_data)
    nikkei225jp_lines = _nikkei225jp_lines(raw_data)
    student_name = "カワウソくん"
    dialogue = [
        {
            "speaker": student_name,
            "role": "student",
            "text": _student_question(task_id, task_config, tone, raw_data, thresholds, generated_at),
        },
        {
            "speaker": speaker_name,
            "role": "teacher",
            "text": _teacher_answer(raw_data, thresholds, tone, task_config, generated_at),
        },
    ]
    conclusion_label, conclusion_text = _conclusion_block(raw_data, thresholds, tone)
    opportunities, cautions = _build_watchpoints(raw_data, thresholds)
    scenarios = _build_scenarios(raw_data, tone)
    analysis_dashboard = _build_analysis_dashboard(raw_data, tone, thresholds)
    data_quality = _build_data_quality(raw_data)
    deep_summary_lines = _deep_summary_lines(
        raw_data,
        tone,
        conclusion_text,
        opportunities,
        cautions,
        research_confidence_line,
        research_evidence_briefs,
    )
    deep_summary_lines = [analysis_dashboard["checklist"][0], *deep_summary_lines[:3]]
    key_metrics = macro_lines[:4] + market_lines[:4]

    return {
        "generated_at": generated_at,
        "body": body,
        "signals": signal_lines,
        "metrics": key_metrics + [line for line in lines if line not in key_metrics],
        "market_metrics": market_lines,
        "macro_metrics": macro_lines,
        "speaker_name": speaker_name,
        "speaker_role": speaker_role,
        "commentary": commentary,
        "market_tone": tone,
        "student_name": student_name,
        "theme_title": theme_title,
        "theme_subtitle": theme_subtitle,
        "dialogue": dialogue,
        "conclusion_label": conclusion_label,
        "conclusion_text": conclusion_text,
        "opportunities": opportunities,
        "cautions": cautions,
        "scenarios": scenarios,
        "analysis_dashboard": analysis_dashboard,
        "data_quality": data_quality,
        "trade_checklist": analysis_dashboard["checklist"],
        "visual_items": _build_visual_items(raw_data),
        "sparkline_items": _build_sparkline_items(raw_data),
        "research_items": raw_data.get("research", {}).get("items", []),
        "research_lines": research_lines,
        "research_theme_lines": research_theme_lines,
        "research_confidence_line": research_confidence_line,
        "research_coverage_lines": research_coverage_lines,
        "research_evidence_lines": research_evidence_lines,
        "research_evidence_briefs": research_evidence_briefs,
        "research_evidence_packs": raw_data.get("research", {}).get("evidence_packs", []),
        "nikkei225jp_lines": nikkei225jp_lines,
        "deep_summary_lines": deep_summary_lines,
        "research_note": raw_data.get("research", {}).get("note", "材料検索は未確認"),
    }

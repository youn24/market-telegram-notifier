from __future__ import annotations

from datetime import datetime
from typing import Any


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


def _theme_block(task_id: str, tone: str, generated_at: str) -> tuple[str, str]:
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


def _student_question(task_id: str, task_config: dict[str, Any], tone: str) -> str:
    if task_config.get("focus") == "macro":
        if tone == "bull":
            return "先生、今日は世界全体ではリスクを取りに行く地合いですか？"
        if tone == "bear":
            return "先生、今日は日本株の前に世界のリスク回避を警戒した方がいいですか？"
        return "先生、今朝の世界地合いは方向感待ちですか？"
    if task_id.startswith("fx"):
        if tone == "bull":
            return "先生、いまは円安の流れに素直についていっていいですか？"
        if tone == "bear":
            return "先生、いまは逆張りよりリスク回避を優先した方がいいですか？"
        return "先生、いまの為替は方向感待ちですか？"
    if tone == "bull":
        return "先生、寄り後は強い銘柄を素直に追っていい場面ですか？"
    if tone == "bear":
        return "先生、今日は無理に入らず守り寄りで見た方がいいですか？"
    return "先生、今日は飛びつくより見極め優先ですか？"


def _teacher_answer(
    raw_data: dict[str, Any],
    thresholds: dict[str, Any],
    tone: str,
) -> str:
    positive_items = [item for item in raw_data.get("items", []) if (item.get("change_pct") or 0) >= thresholds.get("moderate_up_pct", 0.3)]
    negative_items = [item for item in raw_data.get("items", []) if (item.get("change_pct") or 0) <= thresholds.get("moderate_down_pct", -0.3)]

    if tone == "bull" and positive_items:
        joined = "、".join(item["label"] for item in positive_items[:2])
        return f"{joined}が支えているので、強い銘柄を押し目で拾えるかを見たいです。"
    if tone == "bear" and negative_items:
        joined = "、".join(item["label"] for item in negative_items[:2])
        return f"{joined}が重いので、今日は無理に追わず戻り売りと見送りを優先します。"
    return "まだ強弱が混ざっています。最初の値動きだけで決めず、続く側に寄せていきましょう。"


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
    return f"- {item['label']}: {_format_macro_value(item)} ({_format_pct(item.get('change_pct'))})"


def _find_item(items: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    for item in items:
        if item.get("key") == key:
            return item
    return None


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
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    speaker_name, speaker_role = _speaker_profile(task_id, task_config)
    tone = _market_tone(raw_data, thresholds)
    theme_title, theme_subtitle = _theme_block(task_id, tone, generated_at)

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
    student_name = "カワウソくん"
    dialogue = [
        {"speaker": student_name, "role": "student", "text": _student_question(task_id, task_config, tone)},
        {"speaker": speaker_name, "role": "teacher", "text": _teacher_answer(raw_data, thresholds, tone)},
    ]
    conclusion_label, conclusion_text = _conclusion_block(raw_data, thresholds, tone)
    opportunities, cautions = _build_watchpoints(raw_data, thresholds)
    scenarios = _build_scenarios(raw_data, tone)
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
    }

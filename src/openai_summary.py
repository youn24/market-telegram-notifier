from __future__ import annotations

import os
from typing import Any

import requests


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _as_lines(values: Any, limit: int, max_chars: int = 120) -> list[str]:
    if not values:
        return []
    if not isinstance(values, list):
        values = [values]

    lines: list[str] = []
    for value in values:
        text = " ".join(str(value).split())
        if not text:
            continue
        if len(text) > max_chars:
            text = text[: max_chars - 1].rstrip() + "…"
        lines.append(text)
        if len(lines) >= limit:
            break
    return lines


def _trim_prompt(prompt: str) -> str:
    max_chars = _env_int("AI_SUMMARY_MAX_INPUT_CHARS", 5200)
    if len(prompt) <= max_chars:
        return prompt
    return prompt[: max_chars - 80].rstrip() + "\n[入力節約のためここで省略]"


def _build_prompt(summary: dict[str, Any]) -> str:
    include_detail = os.getenv("AI_SUMMARY_DETAIL", "").strip().lower() in {"1", "true", "yes"}
    prompt = "\n".join(
        [
            "You are a Japanese financial market assistant for a day trader.",
            "Return the answer in natural Japanese only.",
            "Use only the compact evidence below. Do not invent numbers.",
            "Do not reveal chain-of-thought. Output only the final concise analysis.",
            "Write exactly five short labeled lines.",
            "Line 1 must start with 結論:",
            "Line 2 must start with 根拠:",
            "Line 3 must start with 注視:",
            "Line 4 must start with 回避:",
            "Line 5 must start with 未確認:",
            "Each line must be 70 Japanese characters or fewer.",
            "Do not invent numbers. If data is unavailable, say 未確認.",
            "Use practical trading language for day trading, but avoid overconfident claims.",
            "Prioritize evidence marked 根拠あり. Treat 候補のみ and 不足 cautiously.",
            "",
            f"Conclusion label: {summary.get('conclusion_label', '')}",
            f"Conclusion text: {' '.join(str(summary.get('conclusion_text', '')).split())[:160]}",
            "Rule summary:",
            *_as_lines(summary.get("commentary", []), 2, 100),
            "Macro metrics:",
            *_as_lines(summary.get("macro_metrics", []), 4, 90),
            "Market metrics:",
            *_as_lines(summary.get("market_metrics", summary.get("metrics", [])), 5, 90),
            "Signals:",
            *_as_lines(summary.get("signals", []), 3, 90),
            "Scenarios:",
            *_as_lines(summary.get("scenarios", []), 3, 100),
            "Research confidence:",
            *_as_lines(summary.get("research_confidence_line", ""), 1, 120),
            "Research coverage:",
            *_as_lines(summary.get("research_coverage_lines", []), 4, 90),
            "Compact research evidence:",
            *_as_lines(summary.get("research_evidence_briefs", []), 5, 110),
            "Research themes:",
            *_as_lines(summary.get("research_theme_lines", []), 3, 90),
            "Top headlines, context only:",
            *_as_lines(summary.get("research_lines", []), 2 if not include_detail else 5, 120),
            *(
                ["Detailed evidence:", *_as_lines(summary.get("research_evidence_lines", []), 4, 140)]
                if include_detail
                else []
            ),
        ]
    )
    return _trim_prompt(prompt)


def _maybe_generate_gemini_summary(summary: dict[str, Any]) -> str | None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    prompt = _build_prompt(summary)

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": _env_float("AI_SUMMARY_TEMPERATURE", 0.2),
                    "maxOutputTokens": _env_int("AI_SUMMARY_MAX_OUTPUT_TOKENS", 360),
                },
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get("candidates", [])
        if not candidates:
            return None

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "\n".join(part.get("text", "").strip() for part in parts if part.get("text", "").strip()).strip()
        return text or None
    except Exception:
        return None


def _maybe_generate_openai_summary(summary: dict[str, Any]) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    prompt = _build_prompt(summary)

    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": prompt,
                "temperature": _env_float("AI_SUMMARY_TEMPERATURE", 0.2),
                "max_output_tokens": _env_int("AI_SUMMARY_MAX_OUTPUT_TOKENS", 360),
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        text = payload.get("output_text", "").strip()
        return text or None
    except Exception:
        return None


def maybe_generate_openai_summary(summary: dict[str, Any]) -> str | None:
    return _maybe_generate_gemini_summary(summary) or _maybe_generate_openai_summary(summary)

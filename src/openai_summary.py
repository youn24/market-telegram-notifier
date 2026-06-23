from __future__ import annotations

import os
from typing import Any

import requests


def _build_prompt(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "You are a Japanese financial market assistant for a day trader.",
            "Return the answer in natural Japanese only.",
            "Think carefully using all provided market, macro, scenario, and research evidence.",
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
            f"Conclusion text: {summary.get('conclusion_text', '')}",
            "Rule-based commentary:",
            *summary.get("commentary", []),
            "Macro metrics:",
            *summary.get("macro_metrics", []),
            "Market metrics:",
            *summary.get("market_metrics", summary.get("metrics", [])),
            "Signals:",
            *summary.get("signals", []),
            "Scenarios:",
            *summary.get("scenarios", []),
            "Research headlines from free search/RSS. Treat these as context, not verified numeric data:",
            summary.get("research_confidence_line", ""),
            "Research coverage and missing viewpoints:",
            *summary.get("research_coverage_lines", []),
            "Compact research evidence by category. Use these first for judgment:",
            *summary.get("research_evidence_briefs", []),
            "Detailed research evidence by category. Use ok evidence strongly, mention candidate/missing viewpoints cautiously:",
            *summary.get("research_evidence_lines", []),
            "Research themes:",
            *summary.get("research_theme_lines", []),
            "Ranked research headlines:",
            *summary.get("research_lines", []),
        ]
    )


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
            json={"contents": [{"parts": [{"text": prompt}]}]},
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
            json={"model": model, "input": prompt},
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

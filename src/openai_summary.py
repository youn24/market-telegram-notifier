from __future__ import annotations

import os
from typing import Any

import requests


def _build_prompt(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "You are a Japanese financial market assistant for a day trader.",
            "Return the answer in natural Japanese only.",
            "Write exactly three short bullet points.",
            "Bullet 1: overall market tone.",
            "Bullet 2: what to watch.",
            "Bullet 3: what to avoid or be careful about.",
            "Do not invent numbers. If data is unavailable, say 未確認.",
            "Use practical trading language, but avoid overconfident claims.",
            "",
            f"Conclusion label: {summary.get('conclusion_label', '')}",
            f"Conclusion text: {summary.get('conclusion_text', '')}",
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

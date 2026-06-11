from __future__ import annotations

import os
from typing import Any

import requests


def _build_prompt(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "あなたは日本語の金融市場アシスタントです。",
            "以下の要点を見て、デイトレ目線で分かりやすい要約を3つの短い箇条書きで返してください。",
            "1行目は全体の地合い、2行目は注目点、3行目は注意点にしてください。",
            "数値の推測は禁止です。未確認の情報は未確認と書いてください。",
            "強い断定は避けつつ、実戦で読みやすい日本語にしてください。",
            "",
            f"結論ラベル: {summary.get('conclusion_label', '')}",
            f"結論文: {summary.get('conclusion_text', '')}",
            "主要数値:",
            *summary.get("metrics", []),
            "シグナル:",
            *summary.get("signals", []),
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
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt,
                            }
                        ]
                    }
                ]
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

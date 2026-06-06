from __future__ import annotations

import os
from typing import Any


def maybe_generate_openai_summary(summary: dict[str, Any]) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    # OpenAI API を後から追加しやすいように入口だけ分離しています。
    # 初期状態ではルールベース要約をそのまま使います。
    return None

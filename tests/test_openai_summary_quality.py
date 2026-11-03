from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.modules.setdefault("requests", types.SimpleNamespace())

from openai_summary import _is_fact_safe_ai_text  # noqa: E402


class OpenAISummaryQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.summary = {
            "conclusion_text": "日経平均は+1.20%で強い側です。",
            "market_metrics": ["日経平均: +1.20%"],
        }

    def test_accepts_strict_five_line_summary_with_supplied_numbers(self) -> None:
        text = "\n".join(
            [
                "結論: 強い側ですが追いかけません。",
                "根拠: 日経平均は+1.20%です。",
                "注視: 次の観測でも上昇が続くか確認します。",
                "反証: 上昇が失速すれば判断を弱めます。",
                "未確認: 売買主体は未確認です。",
            ]
        )
        self.assertTrue(_is_fact_safe_ai_text(text, self.summary))

    def test_rejects_missing_labels_and_unsupported_causality(self) -> None:
        missing = "結論: 様子見です。\n根拠: 日経平均は+1.20%です。"
        causal = "\n".join(
            [
                "結論: 強い側です。",
                "根拠: 決算が原因です。",
                "注視: 継続を確認します。",
                "反証: 失速なら判断を弱めます。",
                "未確認: 需給は未確認です。",
            ]
        )
        self.assertFalse(_is_fact_safe_ai_text(missing, self.summary))
        self.assertFalse(_is_fact_safe_ai_text(causal, self.summary))


if __name__ == "__main__":
    unittest.main()

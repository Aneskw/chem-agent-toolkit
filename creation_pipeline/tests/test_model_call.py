import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_call import call


class ModelCallEncodingTests(unittest.TestCase):
    @patch("model_call.subprocess.run")
    def test_unicode_prompt_uses_utf8_pipes(self, run_mock):
        answer = {"text": "保留 PDF 连字 ﬁ"}
        events = [
            {"type": "item.completed", "item": {
                "type": "agent_message", "text": json.dumps(answer, ensure_ascii=False),
            }},
            {"type": "turn.completed", "usage": {"input_tokens": 3, "output_tokens": 2}},
        ]
        run_mock.return_value = subprocess.CompletedProcess(
            args=["codex"], returncode=0,
            stdout="\n".join(json.dumps(event, ensure_ascii=False) for event in events),
            stderr="",
        )

        value, _ = call(
            "读取中文与 ﬁ ligature。",
            {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            "test-model",
        )

        self.assertEqual(value, answer)
        kwargs = run_mock.call_args.kwargs
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertIn("ﬁ", kwargs["input"])
        self.assertIn("中文", kwargs["input"])


if __name__ == "__main__":
    unittest.main()

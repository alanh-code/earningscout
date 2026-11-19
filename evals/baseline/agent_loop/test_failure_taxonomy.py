"""Taxonomy labels parse to known categories, and the trace digest lists every tool call."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "agent_loop_taxonomy", HERE / "failure_taxonomy.py"
)
tax = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tax)


class Labels(unittest.TestCase):
    def test_parse_keeps_known_categories_only(self):
        lab = tax.parse_label(
            'x {"primary": "omitted_item", "secondary": "nope", "why": "w"} y'
        )
        self.assertEqual((lab["primary"], lab["secondary"]), ("omitted_item", None))
        self.assertTrue(
            tax.parse_label('{"primary": "other"}')["primary"].startswith("invalid:")
        )
        self.assertEqual(tax.parse_label("no json")["primary"], "parse_error")

    def test_digest_lists_searches_fetches_and_code(self):
        trace = {
            "turns": [
                {
                    "tool_calls": [
                        {
                            "name": "web_search",
                            "ok": True,
                            "args": {"query": "q1"},
                            "result": '[{"url": "https://www.sec.gov/a"}]',
                        },
                        {
                            "name": "web_fetch",
                            "ok": False,
                            "refused": True,
                            "args": {"url": "https://github.com/x"},
                        },
                        {
                            "name": "code_execution",
                            "ok": True,
                            "args": {"code": "print(1)"},
                            "result": "1",
                        },
                    ]
                }
            ]
        }
        text = "\n".join(tax.digest(trace))
        self.assertIn("search [ok] q1", text)
        self.assertIn("result https://www.sec.gov/a", text)
        self.assertIn("fetch [refused] https://github.com/x", text)
        self.assertIn("print(1)", text)


if __name__ == "__main__":
    unittest.main()

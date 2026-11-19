"""Leak scan flags URLs the agent protocol blocks, not only whole blocked hosts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evals.baseline import scan_leaks


class ScanLeaks(unittest.TestCase):
    def test_blocked_by_uses_protocol_rules(self):
        domains = {"github.com", "cdn.jsdelivr.net/gh", "doi.org/10.5281"}
        cases = {
            "https://github.com/x/y": "github.com",
            "https://cdn.jsdelivr.net/gh/x/y/a.csv": "protocol rule",
            "https://doi.org/10.5281/zenodo.1": "protocol rule",
            "https://web.archive.org/web/2/https://github.com/x/y": "protocol rule",
            "https://example.com/vals-ai/finance-agent/a.csv": "protocol rule",
            "https://www.sec.gov/a.htm": None,
            "https://cdn.jsdelivr.net/npm/pkg/README.md": None,
        }
        for url, want in cases.items():
            self.assertEqual(scan_leaks.blocked_by(url, domains), want, url)

    def test_scan_run_reports_a_wrapped_gold_url_in_a_tool_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "traces").mkdir()
            trace = {
                "id": "vals-01",
                "turns": [
                    {
                        "tool_calls": [
                            {
                                "result": "see https://ghproxy.example/https://raw.githubusercontent.com/x/y/a.csv"
                            }
                        ]
                    }
                ],
            }
            (run / "traces" / "vals-01.json").write_text(json.dumps(trace))
            hits = scan_leaks.scan_run(run, {"raw.githubusercontent.com"})
        self.assertEqual(
            [h["blocked_domain"] for h in hits if h["kind"] == "url"], ["protocol rule"]
        )


if __name__ == "__main__":
    unittest.main()

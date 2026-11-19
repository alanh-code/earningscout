"""apply_policy keeps the judge's pre-policy grades under a model-neutral name."""

from __future__ import annotations

import unittest
from pathlib import Path

import apply_policy as ap


class Backup(unittest.TestCase):
    def test_pre_policy_copies_use_the_judge_suffix(self):
        d = Path("run")
        self.assertEqual(ap.backup_path(d, "results"), d / "results_judge.csv")

    def test_verifier_wins_only_on_decided_numeric_correctness(self):
        checks = [
            {"operator": "correctness", "result": "met"},
            {"operator": "contradiction", "result": "not triggered"},
        ]
        self.assertEqual(ap.overall_from_checks(checks, "right"), "right")
        checks[0]["result"] = "not met"
        self.assertEqual(ap.overall_from_checks(checks, "right"), "wrong")
        self.assertEqual(ap.overall_from_checks(checks, "abstain"), "abstain")


if __name__ == "__main__":
    unittest.main()

"""Checks for the judge's consistency flags (no API calls)."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "run_judge_flags_under_test",
    ROOT / "evals/contamination/closed_book/judge/run_judge.py",
)
jr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jr)


def grade(met: int, total: int, fraction) -> dict:
    checks = [
        {"operator": "correctness", "result": "met" if i < met else "not met"}
        for i in range(total)
    ]
    checks.append({"operator": "contradiction", "result": "triggered"})
    return {
        "checks": checks,
        "correctness_met": met,
        "correctness_total": total,
        "rubric_fraction": fraction,
        "contradiction_triggered": True,
        "overall": "wrong",
    }


class RubricFraction(unittest.TestCase):
    def test_rounded_fraction_is_not_flagged(self):
        self.assertEqual(jr.consistency_flags({}, grade(3, 11, 0.2727)), [])

    def test_wrong_fraction_is_flagged(self):
        flags = jr.consistency_flags({}, grade(3, 11, 0.5))
        self.assertTrue(any("rubric_fraction" in f for f in flags))


if __name__ == "__main__":
    unittest.main()

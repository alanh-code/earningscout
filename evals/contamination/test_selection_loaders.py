"""Checks for contamination question loading (no API calls)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class SelectionLoaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.judge = load(
            "run_judge_under_test",
            ROOT / "evals/contamination/closed_book/judge/run_judge.py",
        )
        sys.path.insert(0, str(ROOT / "evals/verifier"))
        cls.verifier = load(
            "run_verifier_under_test",
            ROOT / "evals/verifier/run_verifier.py",
        )

    def test_answers_dir_loads_the_current_10(self):
        run = ROOT / "evals/contamination/closed_book/runs/selected"
        items = self.judge.load_items_from_answer_dir(run)
        self.assertEqual(
            [i["id"] for i in items],
            [
                "vals-01",
                "vals-03",
                "vals-11",
                "vals-16",
                "vals-17",
                "vals-18",
                "vals-19",
                "vals-31",
                "vals-33",
                "vals-44",
            ],
        )
        self.assertTrue(all(i["model_answer"] for i in items))

    def test_default_closed_book_verifier_stays_on_the_frozen_15(self):
        items, reference = self.verifier.closed_book_items()
        self.assertEqual(len(items), 15)
        self.assertTrue({"vals-04", "vals-08", "vals-18"} <= set(items))
        self.assertNotIn("vals-11", items)  # new selection only, not in the 15
        self.assertTrue(reference)
        self.assertTrue(all(r["question_id"] in items for r in reference))

    def test_selected_verifier_reads_judge_majority(self):
        run = ROOT / "evals/contamination/closed_book/runs/selected"
        items, reference = self.verifier.closed_book_items(run)
        self.assertEqual(
            set(items),
            {
                "vals-01",
                "vals-03",
                "vals-11",
                "vals-16",
                "vals-17",
                "vals-18",
                "vals-19",
                "vals-31",
                "vals-33",
                "vals-44",
            },
        )
        self.assertTrue(reference)
        self.assertTrue(all(r["question_id"] in items for r in reference))
        self.assertTrue(
            any(r["question_id"] == "vals-18" and r["result"] for r in reference)
        )


if __name__ == "__main__":
    unittest.main()

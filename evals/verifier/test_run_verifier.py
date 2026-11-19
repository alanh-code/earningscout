"""Verifier output folders and cache reuse: no cross-run reuse of extractions."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import run_verifier as rv


class OutputFolder(unittest.TestCase):
    def test_agent_loop_run_gets_its_own_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "official"
            run.mkdir()
            self.assertEqual(rv.baseline_out(run), rv.OUT / "official")
            (run / "run_meta.json").write_text(json.dumps({"harness": "agent_loop"}))
            self.assertEqual(rv.baseline_out(run), rv.OUT / "agent-loop-official")


class Reference(unittest.TestCase):
    def test_reference_is_the_judge_majority_from_before_the_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "official"
            (run / "judge").mkdir(parents=True)
            head = "question_id,check_id,operator,criteria,result,overall,reason\n"
            (run / "judge" / "judge_grades_majority.csv").write_text(
                head + "vals-01,1,correctness,c,not met,wrong,merged\n"
            )
            (run / "judge" / "judge_grades_majority_judge.csv").write_text(
                head + "vals-01,1,correctness,c,met,right,judge\n"
            )
            (run / "answers").mkdir()
            (run / "answers" / "vals-01.json").write_text(
                json.dumps(
                    {
                        "id": "vals-01",
                        "question": "q",
                        "answer": "g",
                        "model_answer": "a",
                    }
                )
            )
            items, reference = rv.baseline_items(run)
        self.assertEqual([r["result"] for r in reference], ["met"])


class Cache(unittest.TestCase):
    def test_cached_extraction_is_reused_only_for_the_same_answer(self):
        entry = {"_cost": 0.1, "_answer_sha": rv.answer_sha("A")}
        self.assertFalse(rv.is_stale(entry, "A"))
        self.assertTrue(rv.is_stale(entry, "B"))
        self.assertTrue(rv.is_stale(None, "A"))
        self.assertFalse(rv.is_stale({"_cost": 0.1}, "B"))


if __name__ == "__main__":
    unittest.main()

"""Agent-loop runner: saved judge passes are reused, and peak hours pause grading."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("agent_loop_run", HERE / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)

GRADE = {"overall": "right"}


class Grade(unittest.TestCase):
    def records(self):
        return [{"id": "vals-01"}, {"id": "vals-02"}]

    def test_saved_passes_are_skipped_and_new_ones_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            saved = run.pass_path(run_dir, 0, "vals-01")
            saved.parent.mkdir(parents=True)
            saved.write_text(
                json.dumps({"grade": GRADE, "cost_usd": 0.5, "reported_models": ["m"]})
            )
            calls = []

            def fake(item, template, guide, pass_i):
                calls.append((item["id"], pass_i))
                return dict(GRADE), 0.1, ["m"]

            with mock.patch.object(run, "judge_one", side_effect=fake):
                cost, passes, models = run.grade(self.records(), 2, 0.0, 100.0, run_dir)
            self.assertNotIn(("vals-01", 0), calls)
            self.assertEqual(len(calls), run.JUDGE_PASSES * 2 - 1)
            self.assertAlmostEqual(cost, 0.5 + 0.1 * len(calls))
            self.assertTrue(all(len(p) == 2 for p in passes))
            self.assertTrue(run.pass_path(run_dir, 2, "vals-02").exists())

    def test_peak_hours_stop_grading_and_keep_finished_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)

            def fake(item, template, guide, pass_i):
                if item["id"] == "vals-02":
                    raise run.llm.PeakHours("peak")
                return dict(GRADE), 0.1, ["m"]

            with (
                mock.patch.object(run, "judge_one", side_effect=fake),
                self.assertRaises(SystemExit),
            ):
                run.grade(self.records(), 1, 0.0, 100.0, run_dir)
            self.assertTrue(run.pass_path(run_dir, 0, "vals-01").exists())
            self.assertFalse(run.pass_path(run_dir, 0, "vals-02").exists())


if __name__ == "__main__":
    unittest.main()

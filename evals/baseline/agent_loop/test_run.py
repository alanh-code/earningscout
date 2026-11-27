"""Agent-loop runner: saved judge passes are reused, and peak hours pause grading."""

from __future__ import annotations

import importlib.util
import json
import os
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
                cost, passes, _models = run.grade(self.records(), 2, 0.0, 100.0, run_dir)
            self.assertNotIn(("vals-01", 0), calls)
            self.assertEqual(len(calls), run.JUDGE_PASSES * 2 - 1)
            self.assertAlmostEqual(cost, 0.5 + 0.1 * len(calls))
            self.assertTrue(all(len(p) == 2 for p in passes))
            self.assertTrue(run.pass_path(run_dir, 2, "vals-02").exists())

    def test_single_pass_screening_judges_once(self):
        try:
            run.set_judge_passes(1)
            self.assertEqual((run.JUDGE_PASSES, run.common.JUDGE_PASSES), (1, 1))
            self.assertEqual(run.protocol_meta()["judge_passes"], 1)
            with tempfile.TemporaryDirectory() as tmp:
                calls = []

                def fake(item, template, guide, pass_i):
                    calls.append((item["id"], pass_i))
                    return dict(GRADE), 0.1, ["m"]

                with mock.patch.object(run, "judge_one", side_effect=fake):
                    _, passes, _ = run.grade(self.records(), 2, 0.0, 100.0, Path(tmp))
            self.assertEqual(sorted(calls), [("vals-01", 0), ("vals-02", 0)])
            self.assertEqual(len(passes), 1)
            with self.assertRaises(SystemExit):
                run.set_judge_passes(0)
        finally:
            run.set_judge_passes(3)

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


class DefaultQuestionSet(unittest.TestCase):
    def test_scored_items_drop_exclusions(self):
        items = [{"id": "vals-01"}, {"id": "vals-02"}, {"id": "vals-03"}]
        got = run.scored_items(items, {"vals-02": "reason"})
        self.assertEqual([q["id"] for q in got], ["vals-01", "vals-03"])

    def test_new_run_defaults_to_the_scored_set(self):
        all_ids = [q["id"] for q in run.common.load_questions()]
        excluded = run.common.load_exclusions()
        expected = [q for q in all_ids if q not in excluded]
        self.assertTrue(excluded)

        def fake_agent(item):
            return {
                "id": item["id"],
                "cost_usd": 0.0,
                "latency_s": 0.0,
                "n_turns": 1,
                "tool_calls": {},
                "n_refused": 0,
            }

        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(run, "RUNS", Path(tmp)),
                mock.patch.object(run.llm, "resolve_model"),
                mock.patch.object(run.llm, "require_off_peak"),
                mock.patch.object(run, "agent_record", side_effect=fake_agent),
                mock.patch.object(run, "finish") as finish,
                mock.patch("sys.argv", ["run.py", "--name", "default_set"]),
            ):
                run.main()
            meta = json.loads((Path(tmp) / "default_set" / "run_meta.json").read_text())
        self.assertEqual(meta["ids"], expected)
        records = finish.call_args.args[1]
        self.assertEqual([r["id"] for r in records], expected)


class DisplayRunDir(unittest.TestCase):
    def test_absolute_path_under_root(self):
        path = run.ROOT / "evals" / "baseline" / "agent_loop" / "runs" / "example"
        self.assertEqual(
            run.display_run_dir(path),
            "evals/baseline/agent_loop/runs/example",
        )

    def test_relative_path_from_repo_root(self):
        rel = Path("evals/baseline/agent_loop/runs/example")
        prev = Path.cwd()
        os.chdir(run.ROOT)
        try:
            self.assertEqual(
                run.display_run_dir(rel),
                "evals/baseline/agent_loop/runs/example",
            )
        finally:
            os.chdir(prev)

    def test_path_outside_root_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "outside"
            self.assertEqual(run.display_run_dir(path), str(path.resolve()))


if __name__ == "__main__":
    unittest.main()

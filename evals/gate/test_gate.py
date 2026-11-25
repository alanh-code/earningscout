import csv
import json
import tempfile
import unittest
from pathlib import Path

from evals.gate import gate

IDS = [f"vals-{i:02d}" for i in range(1, 11)]
NO_EXCLUSIONS: dict[str, str] = {}
TYPES = {q: ("Trends" if i % 2 else "Adjustments") for i, q in enumerate(IDS)}


def write_run(
    root: Path, name: str, right: set[str], *, ids=IDS, leak_hits=0, skip=()
) -> Path:
    run = root / "runs" / name
    (run / "judge").mkdir(parents=True)
    (run / "answers").mkdir()
    with (run / "results.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "type", "overall", "n_tool_calls"])
        w.writeheader()
        for q in ids:
            w.writerow(
                {
                    "id": q,
                    "type": TYPES.get(q, "Trends"),
                    "overall": "right" if q in right else "wrong",
                    "n_tool_calls": 4,
                }
            )
            (run / "answers" / f"{q}.json").write_text(json.dumps({"n_turns": 3}))
    (run / "run_meta.json").write_text(json.dumps({"total_cost_usd": 2.0}))
    (run / "leak_scan.json").write_text(json.dumps({"n_hits": leak_hits, "hits": []}))
    (run / "verifier_policy.json").write_text(
        json.dumps({"n_check_changes": 1, "n_overall_changes": 0})
    )
    for name_ in gate.JUDGE_FILES:
        (run / "judge" / name_).write_text("question_id\n")
    vdir = root / "verifier" / f"agent-loop-{name}"
    vdir.mkdir(parents=True)
    with (vdir / "verdicts.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["question_id", "verifier", "reference"])
        w.writeheader()
        for q in ids:
            w.writerow({"question_id": q, "verifier": "met", "reference": "met"})
            w.writerow(
                {"question_id": q, "verifier": "not numeric", "reference": "met"}
            )
    for rel in skip:
        (run / rel).unlink()
    return run


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vroot = self.root / "verifier"
        # vals-01..06 always right, vals-07 right twice, vals-08 once, vals-09..10 never.
        base = [set(IDS[:7]), set(IDS[:7]) | {"vals-08"}, set(IDS[:6])]
        runs = [write_run(self.root, f"b{i}", r) for i, r in enumerate(base)]
        self.freeze = gate.build_freeze(
            [gate.load_run(r, self.vroot, NO_EXCLUSIONS) for r in runs]
        )

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, *runs):
        return gate.check(list(runs), self.freeze, self.vroot, NO_EXCLUSIONS)

    def test_freeze_sets_and_stats(self):
        f = self.freeze
        self.assertEqual(f["always_right"], IDS[:6])
        self.assertEqual(f["flaky"], ["vals-07", "vals-08"])
        self.assertEqual(f["always_wrong"], ["vals-09", "vals-10"])
        self.assertEqual(f["pass_counts"]["vals-07"], 2)
        self.assertEqual(
            [f["per_run"][n]["right"] for n in ("b0", "b1", "b2")], [7, 8, 6]
        )
        self.assertEqual(f["summary"]["min_right"], 6)
        self.assertEqual(f["summary"]["verifier_agreement"], 1.0)
        self.assertEqual(f["summary"]["per_type"]["Trends"]["total"], 15)

    def test_null_model_floor(self):
        m = gate.null_model(self.freeze, 1)
        self.assertAlmostEqual(m["expected_right"], 7.0)
        self.assertAlmostEqual(m["sd_right"], (2 * 2 / 9) ** 0.5, places=3)
        self.assertLess(gate.null_model(self.freeze, 3)["sd_right"], m["sd_right"])

    def test_unchanged_run_passes(self):
        report = self.check(write_run(self.root, "cand", set(IDS[:7])))
        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(report["warnings"], [])
        self.assertEqual(report["paired"]["always_right_regressions"], [])

    def test_accuracy_regression_fails(self):
        report = self.check(write_run(self.root, "cand", set(IDS[:4])))
        self.assertFalse(report["passed"])
        self.assertTrue(any(f.startswith("accuracy") for f in report["failures"]))

    def test_always_right_regression_warns_with_ids(self):
        right = (set(IDS[:6]) - {"vals-02"}) | {"vals-07", "vals-08"}
        report = self.check(write_run(self.root, "cand", right))
        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(report["paired"]["always_right_regressions"], ["vals-02"])
        self.assertTrue(any("vals-02" in w for w in report["warnings"]))

    def test_always_wrong_fix_and_type_delta(self):
        report = self.check(write_run(self.root, "cand", set(IDS[:7]) | {"vals-09"}))
        self.assertEqual(report["paired"]["always_wrong_fixes"], ["vals-09"])
        self.assertIn("vals-09", report["paired"]["gained"])
        self.assertIn("delta_pp", report["per_type"]["Trends"])

    def test_leak_hit_fails(self):
        report = self.check(write_run(self.root, "cand", set(IDS[:7]), leak_hits=1))
        self.assertFalse(report["passed"])
        self.assertTrue(any("leak" in f for f in report["failures"]))

    def test_missing_question_fails(self):
        report = self.check(write_run(self.root, "cand", set(IDS[:7]), ids=IDS[:-1]))
        self.assertFalse(report["passed"])
        self.assertTrue(any("vals-10" in f for f in report["failures"]))

    def test_extra_question_fails(self):
        report = self.check(
            write_run(self.root, "cand", set(IDS[:7]), ids=[*IDS, "vals-11"])
        )
        self.assertFalse(report["passed"])
        self.assertTrue(any("vals-11" in f for f in report["failures"]))

    def test_repeated_question_rows_fail(self):
        report = self.check(
            write_run(self.root, "cand", set(IDS[:7]), ids=[*IDS, "vals-01"])
        )
        self.assertFalse(report["passed"])
        self.assertTrue(any("repeated" in f for f in report["failures"]))

    def test_missing_artifacts_fail(self):
        for rel in (
            "leak_scan.json",
            "judge/judge_grades_run2.csv",
            "verifier_policy.json",
        ):
            with self.subTest(rel=rel):
                run = write_run(
                    self.root, f"cand-{rel.replace('/', '-')}", set(IDS[:7]), skip=[rel]
                )
                report = self.check(run)
                self.assertFalse(report["passed"])
                self.assertIn(Path(rel).name, report["failures"][0])

    def test_missing_verifier_verdicts_fail(self):
        run = write_run(self.root, "cand", set(IDS[:7]))
        (self.vroot / "agent-loop-cand" / "verdicts.csv").unlink()
        self.assertFalse(self.check(run)["passed"])

    def test_multi_run_mean(self):
        a = write_run(self.root, "c1", set(IDS[:7]))
        b = write_run(self.root, "c2", set(IDS[:6]))
        report = self.check(a, b)
        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(report["accuracy"]["mean_right"], 6.5)
        self.assertIn("Regression gate: PASS", gate.render(report))


class ExclusionTest(unittest.TestCase):
    def test_load_run_drops_excluded_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = write_run(root, "c1", set(IDS[:3]))
            got = gate.load_run(
                run, root / "verifier", {"vals-02": "r", "vals-09": "r"}
            )
        self.assertEqual(
            sorted(got["outcomes"]), [q for q in IDS if q not in ("vals-02", "vals-09")]
        )
        self.assertEqual(got["n"], 8)
        self.assertEqual(got["right"], 2)
        self.assertEqual(got["verifier"]["decided"], 8)


class CommittedBaselineTest(unittest.TestCase):
    def test_freeze_matches_committed_runs(self):
        runs = [gate.load_run(gate.RUNS / n) for n in gate.BASELINE_RUNS]
        frozen = json.loads(gate.FREEZE_PATH.read_text())
        self.assertEqual(gate.build_freeze(runs), frozen)

    def test_baseline_runs_pass_the_gate(self):
        frozen = json.loads(gate.FREEZE_PATH.read_text())
        dirs = [gate.RUNS / n for n in gate.BASELINE_RUNS]
        report = gate.check(dirs, frozen)
        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(
            report["accuracy"]["per_run"],
            {
                run: f"{right}/{len(frozen['question_ids'])}"
                for run, right in zip(gate.BASELINE_RUNS, (32, 31, 30), strict=True)
            },
        )

    def test_freeze_scores_all_questions_minus_exclusions(self):
        frozen = json.loads(gate.FREEZE_PATH.read_text())
        excluded = gate.common.load_exclusions()
        scored = [
            q["id"] for q in gate.common.load_questions() if q["id"] not in excluded
        ]
        self.assertEqual(frozen["question_ids"], scored)


if __name__ == "__main__":
    unittest.main()

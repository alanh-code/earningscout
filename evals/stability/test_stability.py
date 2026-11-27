import csv
import json
import tempfile
import unittest
from pathlib import Path

from evals.stability import stability as st


def write_run(root: Path, name: str, answers: dict[str, tuple[bool, str]]) -> Path:
    run = root / name
    (run / "answers").mkdir(parents=True)
    with (run / "results.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "overall"])
        w.writeheader()
        for q, (right, text) in answers.items():
            w.writerow({"id": q, "overall": "right" if right else "wrong"})
            (run / "answers" / f"{q}.json").write_text(json.dumps({"model_answer": text}))
    return run


class AnswerKeyTest(unittest.TestCase):
    def test_scale_words_and_units_normalize(self):
        self.assertEqual(st.answer_key("Revenue was **$1.75 billion**."), st.answer_key("Revenue: $1,750 million"))
        self.assertEqual(st.numbers("up 70 bps and 6.546x"), [(70.0, "bps"), (6.55, "x")])

    def test_rounding_difference_is_kept(self):
        self.assertNotEqual(st.answer_key("about 6.5"), st.answer_key("about 6.55"))

    def test_years_dates_and_tokens_are_skipped(self):
        self.assertEqual(st.numbers("FY2024 10-K, Q4, filed March 10, 2025: 12.5"), [(12.5, "")])

    def test_negative_forms(self):
        self.assertEqual(st.numbers("change of −7.45% or (3.2)"), [(-7.45, "%"), (-3.2, "")])

    def test_answer_paragraph_wins_and_labels_count(self):
        text = "Guidance was 10.8% to 10.9%.\n\n**Answer: beat by 70 bps**"
        self.assertEqual(st.answer_key(text), (((70.0, "bps"),), ("beat",)))

    def test_no_number_or_label_has_no_key(self):
        self.assertIsNone(st.answer_key("The CEO highlighted global expertise."))


class StabilityTest(unittest.TestCase):
    def test_summary(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            runs = [
                write_run(root, "a", {"q1": (True, "**6.55**"), "q2": (True, "beat"), "q3": (False, "text")}),
                write_run(root, "b", {"q1": (True, "6.55x"), "q2": (False, "beat"), "q3": (False, "text")}),
                write_run(root, "c", {"q1": (True, "6.55"), "q2": (True, "miss"), "q3": (False, "words")}),
            ]
            s = st.stability([st.load_run(r, {}) for r in runs])
        self.assertEqual(s["scores"], [2, 1, 2])
        self.assertEqual(s["same_outcome"], 2)
        self.assertEqual(s["flips"], ["q2"])
        self.assertEqual(s["comparable"], 2)
        self.assertEqual(s["same_answer"], 0)  # 6.55 vs 6.55x differ in unit
        self.assertEqual(s["grading_flips"], [])

    def test_exclusions_and_grading_flip(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            runs = [
                write_run(root, "a", {"q1": (True, "beat by 70 bps"), "x": (True, "1")}),
                write_run(root, "b", {"q1": (False, "Beat by 70 bps"), "x": (False, "2")}),
            ]
            s = st.stability([st.load_run(r, {"x": "excluded"}) for r in runs])
        self.assertEqual(s["n_questions"], 1)
        self.assertEqual(s["grading_flips"], ["q1"])
        self.assertAlmostEqual(s["per_question"]["q1"]["pass_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()

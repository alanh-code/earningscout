import unittest

from evals.stability import ablate as ab


def run(spec: dict[str, tuple[bool, object]]) -> dict[str, dict]:
    return {q: {"right": r, "key": k} for q, (r, k) in spec.items()}


IDS = ["q1", "q2", "q3", "q4"]


class CompareTest(unittest.TestCase):
    def test_clear_gain_is_helps_and_lists_wins(self):
        base = [run({"q1": (True, 1), "q2": (False, 2), "q3": (False, 3), "q4": (False, 4)})] * 3
        cand = [run({"q1": (True, 1), "q2": (True, 2), "q3": (True, 3), "q4": (False, 4)}),
                run({"q1": (True, 1), "q2": (True, 2), "q3": (True, 3), "q4": (True, 4)}),
                run({"q1": (True, 1), "q2": (True, 2), "q3": (True, 3), "q4": (False, 4)})]
        c = ab.compare(ab.config_stats(base, IDS), ab.config_stats(cand, IDS))
        self.assertEqual(c["verdict"], "helps")
        self.assertEqual(c["wins"], ["q2", "q3", "q4"])
        self.assertEqual(c["losses"], [])

    def test_reverse_is_hurts_and_noise_is_no_effect(self):
        good = [run({q: (True, 1) for q in IDS})] * 3
        bad = [run({"q1": (True, 1), "q2": (False, 1), "q3": (False, 1), "q4": (True, 1)}),
               run({"q1": (True, 1), "q2": (False, 1), "q3": (False, 1), "q4": (False, 1)}),
               run({"q1": (True, 1), "q2": (False, 1), "q3": (False, 1), "q4": (True, 1)})]
        self.assertEqual(ab.compare(ab.config_stats(good, IDS), ab.config_stats(bad, IDS))["verdict"], "hurts")
        noisy_a = [run({"q1": (True, 1), "q2": (i == 0, 1), "q3": (True, 1), "q4": (False, 1)}) for i in range(3)]
        noisy_b = [run({"q1": (True, 1), "q2": (i == 1, 1), "q3": (True, 1), "q4": (False, 1)}) for i in range(3)]
        self.assertEqual(ab.compare(ab.config_stats(noisy_a, IDS), ab.config_stats(noisy_b, IDS))["verdict"], "no effect")

    def test_single_run_side_gives_no_verdict(self):
        base = [run({q: (False, 1) for q in IDS})] * 3
        cand = [run({q: (True, 1) for q in IDS})]
        c = ab.compare(ab.config_stats(base, IDS), ab.config_stats(cand, IDS))
        self.assertTrue(c["verdict"].startswith("insufficient"))
        self.assertTrue(c["stability"].startswith("n/a"))

    def test_stability_counts(self):
        runs = [run({"q1": (True, 1), "q2": (True, 2), "q3": (False, None), "q4": (True, 4)}),
                run({"q1": (True, 1), "q2": (False, 9), "q3": (False, None), "q4": (True, 4)})]
        s = ab.config_stats(runs, IDS)
        self.assertEqual(s["same_outcome"], 3)
        self.assertEqual((s["same_answer"], s["comparable"]), (2, 3))


class VoteTest(unittest.TestCase):
    def test_plurality_key_and_abstain(self):
        runs = [run({"q1": (True, "a"), "q2": (False, "x"), "q3": (True, "p")}),
                run({"q1": (False, "b"), "q2": (True, "y"), "q3": (False, "q")}),
                run({"q1": (True, "a"), "q2": (False, "x"), "q3": (False, "r")})]
        v = ab.vote(runs, ["q1", "q2", "q3"], threshold=2)
        self.assertEqual(v["per_question"], {"q1": "right", "q2": "wrong", "q3": "abstain"})
        self.assertEqual((v["vote_right"], v["abstain"], v["pass_at_n"], v["outcome_majority"]), (1, 1, 3, 1))
        v1 = ab.vote(runs, ["q1", "q2", "q3"], threshold=1)
        self.assertEqual(v1["per_question"]["q3"], "right")  # no agreement: falls back to the first run

    def test_subset_filter(self):
        runs = [[{"vals-03": {}, "vals-04": {}, "vals-08": {}}]]
        self.assertEqual(ab._ids(runs, "informative"), ["vals-03", "vals-08"])
        self.assertEqual(ab._ids(runs, "vals-04"), ["vals-04"])


if __name__ == "__main__":
    unittest.main()

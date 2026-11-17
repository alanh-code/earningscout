"""Unit tests for the deterministic part of the number verifier."""

import unittest

from number_verifier import compare, grade_check, parse


def ok(gold, answer, gold_scale=None, answer_scale=None):
    return compare(parse(gold, gold_scale), parse(answer, answer_scale))[0]


class Precision(unittest.TestCase):
    def test_exact_at_gold_precision(self):
        self.assertTrue(ok("$163.51", "$163.51"))
        self.assertFalse(ok("$163.51", "$164.70"))

    def test_more_precise_answer_rounds_to_gold(self):
        self.assertTrue(ok("2.8%", "2.84%"))
        self.assertFalse(ok("2.8%", "2.86%"))
        self.assertTrue(ok("6.55", "6.548"))

    def test_coarser_answer_is_normal_rounding_only(self):
        self.assertTrue(ok("$105.2 billion", "$105B"))
        self.assertTrue(ok("$2,263,113", "$2.26 million"))
        self.assertFalse(ok("6.55", "6.6"))
        self.assertTrue(ok("$163.51", "$164"))  # gold rounded to the answer's precision
        self.assertFalse(ok("$163.51", "$165"))
        self.assertFalse(
            ok("$3.25 Billion", "about $3.3 billion")
        )  # tie: could be $3.30B


class Units(unittest.TestCase):
    def test_scale_words_and_suffixes(self):
        self.assertTrue(ok("$3.25 Billion", "$3,250 million"))
        self.assertTrue(ok("$14,060M", "$14.06 billion"))
        self.assertFalse(ok("$3.25 Billion", "$3.25 million"))

    def test_implied_scale(self):
        self.assertTrue(ok("260,009", "NT$260.01 billion", gold_scale="million"))
        self.assertTrue(ok("260,009", "NT$260.01 billion"))  # scale inferred
        self.assertTrue(ok("2,865,507", "$2,865.5 million", gold_scale="thousand"))

    def test_fraction_and_percent(self):
        self.assertTrue(ok("0.824", "82.4%"))
        self.assertTrue(ok("0.83", "~83%"))
        self.assertFalse(ok("0.75", "~77%"))

    def test_cents(self):
        self.assertTrue(ok("$0.1125", "11.25", answer_scale="cents"))
        self.assertTrue(ok("$0.1125", "11.25¢"))
        self.assertTrue(ok("0.824", "82.4", answer_scale="percent"))

    def test_currency_mismatch(self):
        self.assertFalse(ok("NT$835,152 million", "$835,152 million"))

    def test_bps_and_points(self):
        self.assertTrue(ok("80bps", "0.8 percentage points"))
        self.assertTrue(ok("140 basis points", "1.4pp"))
        self.assertTrue(ok("80bps", "0.8%"))  # shorthand for points; same magnitude
        self.assertFalse(ok("80bps", "80%"))

    def test_percent_vs_plain_number(self):
        self.assertFalse(ok("12.7%", "$12.7 million"))


class Signs(unittest.TestCase):
    def test_parentheses_and_minus(self):
        self.assertTrue(ok("$(149.7) Million", "-$149.7 million"))
        self.assertTrue(ok("$(149.7) Million", "loss of $149.7 million"))
        self.assertTrue(ok("-10.9%", "declined 10.9%"))
        self.assertTrue(ok("-1.2% Miss", "missed by 1.2%"))

    def test_loss_growth_stays_positive(self):
        self.assertTrue(ok("10.7%", "Loss widens ~11%"))

    def test_sign_flip_is_wrong(self):
        self.assertFalse(ok("-10.9%", "10.9%"))
        self.assertFalse(ok("1.9% BEAT", "-1.9%"))


class RangesAndHedges(unittest.TestCase):
    def test_hedged_estimate_containing_gold(self):
        self.assertTrue(ok("$105.2 billion", "about $100B or more"))
        self.assertTrue(ok("$105.2 billion", "about $100 billion"))
        self.assertFalse(ok("$105.2 billion", "$100 billion"))
        self.assertFalse(ok("$105.2 billion", "about $90 billion"))

    def test_bounds(self):
        self.assertFalse(
            ok("$105.2 billion", "more than $1 billion")
        )  # true but misleading
        self.assertFalse(ok("$105.2 billion", "at least $110 billion"))
        self.assertTrue(ok("over 100,000 jobs", "105,000 jobs"))
        self.assertFalse(ok("over 100,000 jobs", "90,000 jobs"))

    def test_answer_range_vs_gold_point(self):
        self.assertTrue(ok("$105.2 billion", "$100-110 billion"))
        self.assertFalse(ok("$105.2 billion", "$50 to $150 billion"))
        self.assertFalse(ok("$105.2 billion", "$106-110 billion"))

    def test_gold_range_needs_matching_endpoints(self):
        self.assertTrue(ok("$7.2 billion to $7.8 billion", "$7.2–7.8B"))
        self.assertTrue(
            ok("$7.2 billion to $7.8 billion", "$7.2 billion - $7.8 billion")
        )
        self.assertFalse(ok("$7.2 billion to $7.8 billion", "$7.3–7.9B"))
        self.assertFalse(ok("$7.2 billion to $7.8 billion", "$7.5 billion"))
        self.assertTrue(ok("$3.94 - $4.06", "$3.94 to $4.06"))

    def test_labels_are_not_numbers(self):
        self.assertTrue(ok("2024: 11.70", "FY2024 ARM of $11.70"))
        self.assertEqual(parse("Q1 2025: -1.2%").low, -1.2)


class Checks(unittest.TestCase):
    def test_correctness_needs_every_quantity(self):
        qs = [
            {"gold": "$6.8 billion to $7.4 billion", "answers": ["$6.8–7.4 billion"]},
            {"gold": "8.5%", "answers": ["8.5%"]},
        ]
        self.assertEqual(grade_check("correctness", qs)[0], "met")
        qs[1]["answers"] = []
        self.assertEqual(grade_check("correctness", qs)[0], "not found")
        qs[0]["answers"] = ["$6.9–7.5 billion"]
        self.assertEqual(grade_check("correctness", qs)[0], "not met")

    def test_any_stated_version_can_match(self):
        qs = [{"gold": "$75.0 billion", "answers": ["$91–93B", "$75B"]}]
        self.assertEqual(grade_check("correctness", qs)[0], "met")

    def test_contradiction_ignores_missing_values(self):
        qs = [
            {"gold": "$3.25 Billion", "answers": []},
            {"gold": "2.8%", "answers": ["2.8%"]},
        ]
        self.assertEqual(grade_check("contradiction", qs)[0], "not triggered")
        qs[0]["answers"] = ["$3.9 billion"]
        self.assertEqual(grade_check("contradiction", qs)[0], "triggered")

    def test_no_numbers(self):
        self.assertEqual(grade_check("correctness", [])[0], "not numeric")


if __name__ == "__main__":
    unittest.main()

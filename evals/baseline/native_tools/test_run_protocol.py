"""Checks for the native-tools runner protocol (no API calls)."""

from __future__ import annotations

import unittest

import run as nt


class Protocol(unittest.TestCase):
    def test_as_of_is_the_documented_protocol_date(self):
        self.assertEqual(nt.PROTOCOL_AS_OF, "Thursday, May 1, 2025")

    def test_current_questions_get_the_protocol_date(self):
        prompt = nt.system_for(
            "What would be the impact if debt were refinanced at rates higher than current?"
        )
        self.assertIn("Thursday, May 1, 2025", prompt)
        self.assertNotEqual(prompt, nt.SYSTEM_MINIMAL)

    def test_other_questions_get_no_as_of_date(self):
        self.assertEqual(
            nt.system_for(
                "Did TJX beat or miss its Q4 FY 2025 pre-tax margin guidance?"
            ),
            nt.SYSTEM_MINIMAL,
        )

    def test_domain_block_is_optional(self):
        blocked = nt.build_tools(block=True)
        open_tools = nt.build_tools(block=False)
        self.assertEqual(blocked[0]["blocked_domains"], list(nt.BLOCKED_DOMAINS))
        self.assertNotIn("blocked_domains", open_tools[0])
        self.assertNotIn("blocked_domains", open_tools[1])


if __name__ == "__main__":
    unittest.main()

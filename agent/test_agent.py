"""Offline checks for the agent protocol, provider config, tools and loop (no API calls).

Set EARNINGSCOUT_LIVE=1 to also run the live checks, which call Exa and E2B
with the keys in .env (a fraction of a cent).
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import UTC, date, datetime, timedelta
from unittest import mock

from agent import llm, loop, protocol, tools

LIVE = os.environ.get("EARNINGSCOUT_LIVE") == "1"
BLOCKED_URLS = [
    "https://github.com/vals-ai/finance-agent",
    "https://raw.githubusercontent.com/vals-ai/x/main/public.csv",
    "https://gist.github.com/x",
    "https://www.vals.ai/benchmarks",
    "https://huggingface.co/datasets/x",
    "http://HF.CO/x",
    "https://zenodo.org/records/1",
    "https://hf-mirror.com/x",
    "https://github.com./x",
    "https://vals-ai.com/benchmarks/finance_agent_v1",
    "https://github.laiyagushi.com/vals-ai/finance-agent",
    "https://deepwiki.com/vals-ai/finance-agent",
    "https://meridianlabs-ai.github.io/inspect_harbor/registry/vals_financeagent.html",
    "https://hub.harborframework.com/datasets/vals/financeagent",
    "https://openreward.ai/GeneralReasoning/financeagent-terminal",
    "https://context7.com/vals-ai/finance-agent/llms.txt",
    "https://shadowgraph.io/vals-ai/finance-agent",
    "https://doi.org/10.5281/zenodo.15428638",
    "https://doi.org/10.57967/hf/5514",
]


class Protocol(unittest.TestCase):
    def test_as_of_is_the_documented_protocol_date(self):
        self.assertEqual(protocol.PROTOCOL_AS_OF, "Thursday, May 1, 2025")
        self.assertTrue(protocol.as_of_iso().startswith("2025-05-01T23:59:59"))

    def test_current_questions_get_the_protocol_date(self):
        prompt = protocol.system_for("What is the current dividend yield?")
        self.assertIn(protocol.PROTOCOL_AS_OF, prompt)
        self.assertEqual(
            protocol.system_for("What was Q4 revenue?"), protocol.SYSTEM_MINIMAL
        )

    def test_blocked_hosts(self):
        for url in BLOCKED_URLS:
            self.assertTrue(protocol.is_blocked_url(url), url)
        for url in [
            "https://www.sec.gov/a.htm",
            "https://notgithub.com/x",
            "https://investor.tjx.com",
            "https://doi.org/10.1016/j.example",
            "https://other.github.io/x",
            "https://cdn.jsdelivr.net/npm/some-package/README.md",
            "https://web.archive.org/web/2/https://www.sec.gov/a.htm",
            "https://www.example.com/blog/how-we-use-github-actions",
            "https://ml4trading.io/agent-lab/evaluation/finance-agent-benchmark/",
        ]:
            self.assertFalse(protocol.is_blocked_url(url), url)

    def test_gold_mirrors_proxies_and_markers_are_blocked(self):
        for url in [
            "https://cdn.jsdelivr.net/gh/vals-ai/finance-agent@main/data/public.csv",
            "https://fastly.jsdelivr.net/gh/someone/fork/data.csv",
            "https://rawcdn.githack.com/vals-ai/finance-agent/main/data/public.csv",
            "https://raw.githack.com/x/y/main/a.csv",
            "https://cdn.statically.io/gh/vals-ai/finance-agent/main/data/public.csv",
            "https://ghproxy.net/https://raw.githubusercontent.com/x/y/main/a.csv",
            "https://some-proxy.example/https://raw.githubusercontent.com/x/y/main/a.csv",
            "https://web.archive.org/web/2/https://github.com/x/y",
            "https://archive.ph/https%3A%2F%2Fhuggingface.co%2Fdatasets%2Fx",
            "https://reader.example/?url=https://github.com/x/y",
            "https://example.com/mirror/vals-ai/finance-agent/data/public.csv",
            "https://example.com/datasets/finance_agent_benchmark.csv",
            "https://kkgithub.com/x/y",
            "https://verified-skill.com/skills/coral-bricks-ai/coral-ai/compute-debt-refi-impact",
            "https://www.coralbricks.ai/blog/write-a-winning-agent-harness",
        ]:
            self.assertTrue(protocol.is_blocked_url(url), url)

    def test_non_http_urls_are_refused(self):
        for url in ["file:///etc/passwd", "ftp://sec.gov/x", "not a url", ""]:
            self.assertTrue(protocol.is_blocked_url(url), url)


class Provider(unittest.TestCase):
    def test_models_are_configured(self):
        self.assertEqual(llm.AGENT_MODEL, "deepseek-flash")
        self.assertEqual(llm.JUDGE_MODEL, "deepseek-v4-pro")
        for name in (llm.AGENT_MODEL, llm.JUDGE_MODEL, llm.VERIFIER_MODEL):
            self.assertIn(name, llm.MODELS)

    def test_peak_hours(self):
        p = llm.PROVIDERS["deepseek"]
        monday = datetime.min.replace(tzinfo=UTC)  # day one of the calendar is a Monday
        self.assertEqual(monday.weekday(), 0)
        self.assertTrue(llm.is_peak(p, monday.replace(hour=2)))
        self.assertTrue(llm.is_peak(p, monday.replace(hour=9, minute=59)))
        self.assertFalse(llm.is_peak(p, monday.replace(hour=4)))
        self.assertFalse(llm.is_peak(p, monday.replace(hour=10)))
        self.assertFalse(
            llm.is_peak(p, monday.replace(hour=2) + timedelta(days=5))
        )  # Saturday

    def test_cost_uses_cache_split_and_peak_rate(self):
        usage = {
            "cache_hit_tokens": 1_000_000,
            "cache_miss_tokens": 1_000_000,
            "output_tokens": 1_000_000,
        }
        off = llm.cost_usd("deepseek-flash", usage)
        self.assertAlmostEqual(off, 0.003 + 0.15 + 0.60)
        self.assertAlmostEqual(
            llm.cost_usd("deepseek-flash", usage, peak=True), 2 * off
        )

    def test_usage_normalization(self):
        u = llm.normalize_usage(
            {
                "prompt_tokens": 100,
                "completion_tokens": 7,
                "prompt_cache_hit_tokens": 60,
                "prompt_cache_miss_tokens": 40,
            }
        )
        self.assertEqual(
            (
                u["input_tokens"],
                u["cache_hit_tokens"],
                u["cache_miss_tokens"],
                u["output_tokens"],
            ),
            (100, 60, 40, 7),
        )

    def test_send_makes_no_call_in_peak_hours(self):
        client = mock.Mock()
        req = llm.build_request(
            llm.AGENT_MODEL,
            [{"role": "user", "content": "hi"}],
            max_tokens=8,
            thinking=False,
        )
        with (
            mock.patch.object(llm, "client_for", return_value=client),
            mock.patch.object(llm, "is_peak", return_value=True),
            mock.patch.object(llm, "ALLOW_PEAK", False),
            self.assertRaises(llm.PeakHours),
        ):
            llm.send(req)
        client.chat.completions.create.assert_not_called()

    def test_require_off_peak_sets_the_send_guard(self):
        with mock.patch.object(llm, "ALLOW_PEAK", False):
            llm.require_off_peak([llm.AGENT_MODEL], allow_peak=True)
            self.assertTrue(llm.ALLOW_PEAK)
            with mock.patch.object(llm, "is_peak", return_value=False):
                llm.require_off_peak([llm.AGENT_MODEL], allow_peak=False)
            self.assertFalse(llm.ALLOW_PEAK)

    def test_request_sends_temperature_only_without_thinking(self):
        msgs = [{"role": "user", "content": "q"}]
        on = llm.build_request(
            "deepseek-flash", msgs, max_tokens=10, thinking=True, temperature=0
        )
        off = llm.build_request(
            "deepseek-flash", msgs, max_tokens=10, thinking=False, temperature=0
        )
        self.assertNotIn("temperature", on)
        self.assertEqual(off["temperature"], 0)
        self.assertEqual(on["seed"], protocol.SEED)
        self.assertEqual(off["thinking"], {"type": "disabled"})

    def test_saved_responses_drop_wall_clock_fields(self):
        clean = llm.sanitize({"id": "x", "created": 1, "model": "m", "choices": []})
        self.assertEqual(set(clean), {"model", "choices"})

    def test_response_text_reads_both_formats(self):
        chat = {"choices": [{"message": {"content": "A"}, "finish_reason": "stop"}]}
        legacy = {"content": [{"type": "text", "text": "B"}]}
        self.assertEqual(llm.response_text(chat), "A")
        self.assertEqual(llm.response_text(legacy), "B")


class AllowPeakEnv(unittest.TestCase):
    def test_env_var_sets_the_default_for_subprocesses(self):
        import importlib

        try:
            with mock.patch.dict(os.environ, {"ALLOW_PEAK": "1"}):
                self.assertTrue(importlib.reload(llm).ALLOW_PEAK)
            with mock.patch.dict(os.environ, {"ALLOW_PEAK": "0"}):
                self.assertFalse(importlib.reload(llm).ALLOW_PEAK)
            with mock.patch.dict(os.environ):
                os.environ.pop("ALLOW_PEAK", None)
                self.assertFalse(importlib.reload(llm).ALLOW_PEAK)
        finally:
            importlib.reload(llm)


class ClosedEnvironment(unittest.TestCase):
    def request(self, **kw):
        return llm.build_request(
            "deepseek-flash",
            [{"role": "user", "content": "q"}],
            max_tokens=10,
            thinking=False,
            temperature=0,
            **kw,
        )

    def reply(self, **message):
        return {
            "model": "deepseek-flash",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "a", **message},
                    "finish_reason": "stop",
                }
            ],
        }

    def test_clean_request_passes(self):
        self.assertEqual(llm.closed_violations(self.request(), self.reply()), [])

    def test_tools_system_prompt_and_thinking_fail(self):
        self.assertTrue(
            llm.closed_violations(
                self.request(tools=[{"type": "function"}]), self.reply()
            )
        )
        req = self.request()
        req["messages"] = [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "q"},
        ]
        self.assertTrue(llm.closed_violations(req, self.reply()))
        self.assertTrue(
            llm.closed_violations(self.request(), self.reply(tool_calls=[{"id": "x"}]))
        )
        self.assertTrue(
            llm.closed_violations(self.request(), self.reply(reasoning_content="r"))
        )
        other = self.reply()
        other["model"] = "other"
        self.assertTrue(llm.closed_violations(self.request(), other))


class FakeResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append((url, json))
        return FakeResponse(self.data)


class FakeGetSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, headers=None, timeout=None):
        self.calls.append((url, headers))
        return FakeResponse(self.routes[url])


SEC_ROUTES = {
    tools.SEC_TICKERS_URL: {
        "0": {"cik_str": 1321655, "ticker": "PLTR", "title": "Palantir Technologies Inc."},
        "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    },
    tools.SEC_SUBMISSIONS_URL.format(cik=1321655): {
        "filings": {
            "recent": {
                "form": ["8-K", "10-K", "10-Q", "4", "10-K/A"],
                "filingDate": ["2025-05-05", "2025-02-18", "2024-11-05", "2024-11-01", "2024-03-01"],
                "reportDate": ["2025-05-05", "2024-12-31", "2024-09-30", "", "2023-12-31"],
                "accessionNumber": ["0001321655-25-000001", "0001321655-25-000002", "0001321655-24-000003", "x-4", "0001321655-24-000005"],
                "primaryDocument": ["a.htm", "b.htm", "c.htm", "d.xml", "e.htm"],
                "items": ["2.02,9.01", "", "", "", ""],
            }
        }
    },
}


SEC_ROUTES[tools.SEC_ENTITY_SEARCH_URL.format(query="Redfin%20Corporation")] = {
    "hits": {"hits": [{"_id": "1382821", "_source": {"entity": "Redfin Corp"}}]}
}
SEC_ROUTES[tools.SEC_ENTITY_SEARCH_URL.format(query="Nonexistent%20Widgets")] = {"hits": {"hits": []}}


class SecFilings(unittest.TestCase):
    def sec(self):
        tools.Sec._cache.clear()
        return tools.Sec(session=FakeGetSession(SEC_ROUTES), user_agent="test agent")

    def test_resolves_ticker_and_name(self):
        sec = self.sec()
        self.assertEqual(sec.resolve("pltr")[0], 1321655)
        self.assertEqual(sec.resolve("Palantir Technologies")[0], 1321655)
        self.assertEqual(sec.resolve("Apple")[0], 320193)
        self.assertEqual(sec.resolve("Redfin Corporation"), (1382821, "Redfin Corp"))  # former registrant
        with self.assertRaises(tools.ToolError):
            sec.resolve("Nonexistent Widgets")

    def test_lists_forms_filed_by_the_as_of_date_newest_first(self):
        sec = self.sec()
        text, info = sec.filings("PLTR", date(2025, 3, 1))
        rows = json.loads(text.split("\n", 1)[1])
        self.assertEqual([r["form"] for r in rows], ["10-K", "10-Q", "10-K/A"])
        self.assertEqual(
            rows[0]["document"],
            "https://www.sec.gov/Archives/edgar/data/1321655/000132165525000002/b.htm",
        )
        self.assertEqual(info["results"], 3)
        only_8k, _ = sec.filings("PLTR", date(2025, 6, 1), ["8-K"])
        self.assertIn("2.02", only_8k)
        self.assertEqual(sec.session.calls[0][1]["User-Agent"], "test agent")

    def test_needs_set_as_of_and_uses_its_date(self):
        runner = tools.ToolRunner(
            exa=tools.Exa(api_key="test", session=FakeSession({})),
            sandbox=tools.CodeSandbox(factory=mock.Mock()),
            sec=self.sec(),
        )
        self.assertIn("set_as_of first", runner.call("sec_filings", '{"company": "PLTR"}'))
        runner.call("set_as_of", '{"date": "2024-12-01", "reason": "r"}')
        out = runner.call("sec_filings", '{"company": "PLTR", "forms": "10-Q"}')
        self.assertIn("2024-11-05", out)
        self.assertNotIn("2025-02-18", out)
        self.assertEqual(runner.used["sec_filings"], 1)

    def test_prompt_puts_filings_first(self):
        for prompt in (protocol.SYSTEM_MINIMAL, protocol.SYSTEM_WITH_DATE):
            self.assertIn(protocol.SOURCE_RULES, prompt)


class ToolCache(unittest.TestCase):
    def test_repeat_request_is_served_from_disk_at_no_cost(self):
        import tempfile

        data = {"results": [{"url": "https://www.sec.gov/a.htm", "title": "10-K"}], "costDollars": {"total": 0.01}}
        with tempfile.TemporaryDirectory() as d:
            session = FakeSession(data)
            exa = tools.Exa(api_key="test", session=session, cache_dir=d)
            first = exa.search("Q4  Revenue", date(2025, 1, 31))
            again = tools.Exa(api_key="test", session=session, cache_dir=d).search(
                "q4 revenue", date(2025, 1, 31)
            )
            other_day = exa.search("q4 revenue", date(2024, 1, 31))
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(first[0], again[0])
        self.assertEqual((first[1], again[1]), (0.01, 0.0))
        self.assertEqual((first[2]["exa_cache_hit"], again[2]["exa_cache_hit"]), (False, True))
        self.assertFalse(other_day[2]["exa_cache_hit"])

    def test_key_ignores_url_fragment_and_query_case(self):
        a = tools.cache_key("/contents", {"urls": ["https://x.com/a#p2"]})
        self.assertEqual(a, tools.cache_key("/contents", {"urls": ["https://x.com/a"]}))
        self.assertNotEqual(a, tools.cache_key("/contents", {"urls": ["https://x.com/b"]}))

    def test_no_cache_by_default(self):
        self.assertIsNone(tools.Exa(api_key="test", session=FakeSession({})).cache_dir)


class BlockedHostsAreRefused(unittest.TestCase):
    """Search, fetch and the sandbox all refuse the gold hosts."""

    def test_search_excludes_and_filters_blocked_hosts(self):
        session = FakeSession(
            {
                "results": [
                    {
                        "url": "https://github.com/vals-ai/finance-agent",
                        "title": "gold",
                    },
                    {"url": "https://huggingface.co/datasets/vals", "title": "gold"},
                    {
                        "url": "https://www.sec.gov/a.htm",
                        "title": "10-K",
                        "highlights": ["revenue"],
                    },
                ],
                "costDollars": {"total": 0.004},
            }
        )
        exa = tools.Exa(api_key="test", session=session)
        text, cost, info = exa.search("vals finance agent answers")
        body = session.calls[0][1]
        for d in protocol.BLOCKED_DOMAINS:
            self.assertIn(d, body["excludeDomains"])
            if "/" not in d:
                self.assertIn("*." + d, body["excludeDomains"])
        self.assertEqual(body["type"], "lite")
        self.assertEqual(body["endPublishedDate"], protocol.as_of_iso())
        self.assertNotIn("github.com", text)
        self.assertNotIn("huggingface", text)
        self.assertIn("sec.gov", text)
        self.assertEqual(info["dropped_blocked"], 2)
        self.assertAlmostEqual(cost, 0.004)

    def test_fetch_refuses_blocked_hosts_before_any_request(self):
        session = FakeSession({})
        exa = tools.Exa(api_key="test", session=session)
        for url in BLOCKED_URLS:
            with self.assertRaises(tools.ToolError):
                exa.fetch(url)
        self.assertEqual(session.calls, [])

    def test_fetch_refuses_a_redirect_to_a_blocked_host(self):
        session = FakeSession(
            {"results": [{"url": "https://github.com/x", "text": "gold"}]}
        )
        exa = tools.Exa(api_key="test", session=session)
        with self.assertRaises(tools.ToolError):
            exa.fetch("https://example.com/short-link")

    def test_runner_fetches_an_allowed_page(self):
        session = FakeSession(
            {
                "results": [
                    {
                        "url": "https://www.sec.gov/a.htm",
                        "title": "10-K",
                        "text": "Revenue 10",
                    }
                ],
                "costDollars": {"total": 0.001},
            }
        )
        runner = tools.ToolRunner(
            exa=tools.Exa(api_key="test", session=session),
            sandbox=tools.CodeSandbox(factory=mock.Mock()),
        )
        out = runner.call("web_fetch", json.dumps({"url": "https://www.sec.gov/a.htm"}))
        self.assertIn("Revenue 10", out)
        self.assertTrue(runner.log[-1]["ok"])
        self.assertAlmostEqual(runner.cost["exa"], 0.001)

    def test_runner_reports_refusals_to_the_model(self):
        runner = tools.ToolRunner(
            exa=tools.Exa(api_key="test", session=FakeSession({})),
            sandbox=tools.CodeSandbox(factory=mock.Mock()),
        )
        out = runner.call(
            "web_fetch", json.dumps({"url": "https://github.com/vals-ai"})
        )
        self.assertTrue(out.startswith("Error: refused"))
        self.assertTrue(runner.log[-1]["refused"])

    def test_sandbox_is_created_without_internet_and_killed(self):
        created = {}

        class FakeSandbox:
            @staticmethod
            def create(**kw):
                created.update(kw)
                return mock.Mock(
                    run_code=mock.Mock(
                        return_value=mock.Mock(
                            logs=mock.Mock(stdout=["4\n"], stderr=[]),
                            results=[],
                            error=None,
                        )
                    )
                )

        with mock.patch.dict(
            "sys.modules", {"e2b_code_interpreter": mock.Mock(Sandbox=FakeSandbox)}
        ):
            box = tools.CodeSandbox(api_key="test")
            text, _, _ = box.run("print(2+2)")
            sbx = box.sandbox
            box.close()
        self.assertIs(created["allow_internet_access"], False)
        self.assertEqual(created["timeout"], tools.SANDBOX_LIFETIME_S)
        self.assertIn("4", text)
        sbx.kill.assert_called_once()
        self.assertIsNone(box.sandbox)

    def test_budget_is_enforced(self):
        runner = tools.ToolRunner(
            exa=mock.Mock(),
            sandbox=tools.CodeSandbox(factory=mock.Mock()),
            budgets={"web_search": 0, "web_fetch": 0, "code_execution": 0},
        )
        runner.as_of = protocol.protocol_as_of_date()
        self.assertIn("budget", runner.call("web_search", '{"query": "x"}'))


def fake_chat(script):
    """A chat() stand-in that replays assistant messages and records requests."""
    sent = []

    def chat(model, messages, **kw):
        sent.append({"messages": [dict(m) for m in messages], **kw})
        message = script[len(sent) - 1]
        finish = "tool_calls" if message.get("tool_calls") else "stop"
        return {
            "response": {
                "model": model,
                "choices": [{"message": message, "finish_reason": finish}],
            },
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_hit_tokens": 0,
                "cache_miss_tokens": 10,
                "reasoning_tokens": 0,
            },
            "cost_usd": 0.001,
            "peak": False,
            "reported_model": model,
            "attempts": 1,
        }

    return chat, sent


class Loop(unittest.TestCase):
    def runner(self):
        box = tools.CodeSandbox(factory=mock.Mock())
        box.run = mock.Mock(return_value=("stdout:\n42", 0.0, {"code_error": False}))
        return tools.ToolRunner(
            exa=tools.Exa(api_key="test", session=FakeSession({})), sandbox=box
        )

    def test_tool_round_trip_passes_reasoning_back(self):
        call = {
            "id": "c1",
            "type": "function",
            "function": {
                "name": "code_execution",
                "arguments": '{"code": "print(6*7)"}',
            },
        }
        chat, sent = fake_chat(
            [
                {
                    "role": "assistant",
                    "content": "",
                    "reasoning_content": "compute",
                    "tool_calls": [call],
                },
                {"role": "assistant", "content": "42", "reasoning_content": "done"},
            ]
        )
        rec = loop.run_agent("What is 6*7?", chat=chat, tools=self.runner())
        self.assertEqual(rec["model_answer"], "42")
        self.assertEqual(rec["n_tool_calls"], 1)
        logged = rec["turns"][0]["tool_calls"][0]
        self.assertTrue(logged["ok"])
        self.assertNotIn("error", logged)
        self.assertEqual(logged["result"], "stdout:\n42")
        second = sent[1]["messages"]
        self.assertEqual(second[0]["role"], "system")
        self.assertEqual(second[2]["reasoning_content"], "compute")
        self.assertEqual(second[3]["role"], "tool")
        self.assertTrue(sent[0]["thinking"])

    def test_last_turn_disables_tools(self):
        call = {
            "id": "c1",
            "type": "function",
            "function": {
                "name": "web_fetch",
                "arguments": '{"url": "https://github.com/x"}',
            },
        }
        chat, sent = fake_chat(
            [
                {"role": "assistant", "content": "", "tool_calls": [call]},
                {"role": "assistant", "content": "final"},
            ]
        )
        rec = loop.run_agent("q", chat=chat, tools=self.runner(), max_turns=2)
        self.assertEqual(sent[0]["tool_choice"], "auto")
        self.assertEqual(sent[1]["tool_choice"], "none")
        self.assertEqual(rec["n_refused"], 1)

    def test_sandbox_closed_on_error(self):
        def boom(*a, **k):
            raise RuntimeError("api down")

        runner = self.runner()
        runner.close = mock.Mock()
        with self.assertRaises(RuntimeError):
            loop.run_agent("q", chat=boom, tools=runner)
        runner.close.assert_called_once()


class LongPagePrompt(unittest.TestCase):
    def test_prompts_mention_reading_on(self):
        for prompt in (protocol.SYSTEM_MINIMAL, protocol.SYSTEM_WITH_DATE):
            self.assertIn("offset", prompt)
            self.assertIn("find", prompt)
        self.assertIn(protocol.PROTOCOL_AS_OF, protocol.SYSTEM_WITH_DATE)


class AnswerPrompt(unittest.TestCase):
    def test_prompts_ask_for_two_decimal_ratios_and_the_largest_add_back(self):
        for prompt in (protocol.SYSTEM_MINIMAL, protocol.SYSTEM_WITH_DATE):
            self.assertIn(protocol.ANSWER_RULES, prompt)

    def test_prompts_require_code_arithmetic_and_a_final_answer_block(self):
        for prompt in (protocol.SYSTEM_MINIMAL, protocol.SYSTEM_WITH_DATE):
            self.assertIn(protocol.OUTPUT_RULES, prompt)
        self.assertIn("code_execution", protocol.OUTPUT_RULES)
        self.assertIn("one line for each figure or verdict", protocol.OUTPUT_RULES)
        self.assertTrue(protocol.OUTPUT_RULES.endswith("label <beat, miss, in line, yes, no, or n/a>"))

    def test_rounding_rules_split_ratios_and_beat_or_miss(self):
        self.assertIn("ratios and multiples to two decimal places", protocol.ANSWER_RULES)
        self.assertIn("a beat or miss", protocol.ANSWER_RULES)
        self.assertIn("give it to one decimal place", protocol.ANSWER_RULES)
        self.assertIn("never show the same quantity at two different roundings", protocol.ANSWER_RULES)
        self.assertIn("every year or period in the span", protocol.COVERAGE_RULES)
        self.assertIn("instead of 'n/a'", protocol.COVERAGE_RULES)
        self.assertIn("Lead with the figure the question asks for", protocol.ANSWER_RULES)
        self.assertIn("number of decimals", protocol.ANSWER_RULES)

    def test_coverage_and_definition_rules_are_in_every_prompt(self):
        for prompt in (protocol.SYSTEM_MINIMAL, protocol.SYSTEM_WITH_DATE):
            self.assertIn(protocol.COVERAGE_RULES, prompt)
            self.assertIn(protocol.DEFINITION_RULES, prompt)
        self.assertIn("both the low end and the high end", protocol.COVERAGE_RULES)
        self.assertIn("Include only what the question asks for", protocol.COVERAGE_RULES)
        self.assertIn("company's own guidance", protocol.DEFINITION_RULES)
        self.assertIn("round only the final result", protocol.DEFINITION_RULES)
        self.assertIn("headline figures as published", protocol.DEFINITION_RULES)
        self.assertIn("issued after the as-of date", protocol.AS_OF_RULES)

    def test_prompt_examples_do_not_quote_benchmark_answers(self):
        """No number written in the system prompt may appear in a public gold answer."""
        import csv
        import re
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "data" / "vals" / "public.csv"
        with path.open(newline="", encoding="utf-8") as f:
            gold = " ".join(r["Answer"] for r in csv.DictReader(f))
        for prompt in (protocol.SYSTEM_MINIMAL, protocol.SYSTEM_WITH_DATE):
            for num in re.findall(r"\d+\.\d+", prompt):
                self.assertNotRegex(gold, rf"(?<![\d.]){re.escape(num)}(?!\d)", num)


class FakeExa:
    """Stand-in for Exa: counts paid fetches and serves fixed pages."""

    def __init__(self, pages, blocked=("github.com",), final_urls=None, published=None):
        self.pages = pages
        self.published = published or {}
        self.blocked = list(blocked)
        self.final_urls = final_urls or {}
        self.fetches = []

    def fetch(self, url):
        if tools.is_blocked_url(url, self.blocked):
            raise tools.ToolError("refused: that host is blocked for this evaluation")
        self.fetches.append(url)
        final = self.final_urls.get(url, url)
        return {
            "head": f"Title: t\nURL: {final}\n",
            "text": self.pages[url],
            "url": final,
            "published": self.published.get(url),
        }, 0.001


class LongPageFetchTest(unittest.TestCase):
    URL = "https://www.sec.gov/filing.htm"

    def runner(self, text, **kw):
        exa = FakeExa({self.URL: text}, **kw)
        return tools.ToolRunner(exa=exa, sandbox=mock.Mock()), exa

    def fetch(self, runner, **args):
        return runner.call("web_fetch", json.dumps({"url": self.URL, **args}))

    def test_short_page_has_no_range_note(self):
        runner, _ = self.runner("short text")
        out = self.fetch(runner)
        self.assertIn("short text", out)
        self.assertNotIn("Characters", out)
        self.assertEqual(runner.log[-1]["page_chars"], 10)

    def test_long_page_reports_range_and_paginates_from_cache(self):
        text = "a" * tools.FETCH_CHUNK_CHARS + "b" * 1000
        runner, exa = self.runner(text)
        first = self.fetch(runner)
        self.assertIn(f"Characters 0-{tools.FETCH_CHUNK_CHARS} of {len(text)}", first)
        self.assertIn(f"offset={tools.FETCH_CHUNK_CHARS}", first)
        self.assertNotIn("b", first.split("\n\n", 1)[1])
        second = self.fetch(runner, offset=tools.FETCH_CHUNK_CHARS)
        self.assertTrue(second.endswith("b" * 1000))
        self.assertNotIn("remain", second)
        self.assertEqual(len(exa.fetches), 1)
        self.assertEqual(runner.used["web_fetch"], 1)
        self.assertEqual(runner.page_reads, 1)
        self.assertEqual([e["cached"] for e in runner.log], [False, True])
        self.assertEqual(runner.log[-1]["cost_usd"], 0.0)

    def test_offset_past_end_and_negative_are_clamped(self):
        runner, _ = self.runner("x" * 100)
        self.fetch(runner)
        self.assertEqual(
            self.fetch(runner, offset=10_000).rstrip().split("\n")[-1],
            "Characters 100-100 of 100.",
        )
        self.assertEqual(runner.log[-1]["start"], 100)
        self.fetch(runner, offset=-5)
        self.assertEqual(runner.log[-1]["start"], 0)

    def test_bad_offset_is_an_error(self):
        runner, exa = self.runner("x")
        self.assertIn("offset must be an integer", self.fetch(runner, offset="abc"))
        self.assertEqual(exa.fetches, [])

    def test_find_returns_passages_with_offsets(self):
        text = "filler " * 8000 + "Net revenue retention was 115%." + " filler" * 100
        runner, exa = self.runner(text)
        out = self.fetch(runner, find="net revenue retention")
        self.assertIn("1 passages match", out)
        self.assertIn("115%", out)
        pos = text.index("Net revenue")
        self.assertIn(f"[characters {pos - tools.FIND_CONTEXT_CHARS}-", out)
        self.assertEqual(runner.log[-1]["matches"], 1)
        self.assertEqual(len(exa.fetches), 1)
        self.fetch(runner, find="retention")
        self.assertEqual(len(exa.fetches), 1)

    def test_find_falls_back_to_words_and_reports_no_match(self):
        runner, _ = self.runner("The gross margin was 40%. Later, margin fell.")
        out = self.fetch(runner, find="margin compression")
        self.assertIn("passages match", out)
        self.assertIn("No match", self.fetch(runner, find="zzz qq"))

    def test_find_caps_passages(self):
        runner, _ = self.runner(("hit " + "." * 2000) * 20)
        out = self.fetch(runner, find="hit")
        self.assertIn(f"showing the first {tools.FIND_MAX_MATCHES}", out)
        self.assertEqual(out.count("[characters"), tools.FIND_MAX_MATCHES)

    def test_page_read_cap_stops_loops(self):
        runner, exa = self.runner("x" * 10)
        self.fetch(runner)
        for _ in range(tools.PAGE_READS):
            self.fetch(runner, offset=1)
        self.assertIn("re-read limit", self.fetch(runner, offset=1))
        self.assertEqual(len(exa.fetches), 1)

    def test_new_url_still_uses_fetch_budget(self):
        exa = FakeExa({f"https://a.com/{i}": "x" for i in range(3)})
        runner = tools.ToolRunner(
            exa=exa,
            sandbox=mock.Mock(),
            budgets={"web_fetch": 2, "web_search": 1, "code_execution": 1},
        )
        for i in range(3):
            out = runner.call("web_fetch", json.dumps({"url": f"https://a.com/{i}"}))
        self.assertIn("budget of 2 calls is used up", out)
        self.assertEqual(len(exa.fetches), 2)

    def test_fragment_and_final_url_share_the_cache(self):
        exa = FakeExa(
            {self.URL: "x"}, final_urls={self.URL: "https://www.sec.gov/final.htm"}
        )
        runner = tools.ToolRunner(exa=exa, sandbox=mock.Mock())
        runner.call("web_fetch", json.dumps({"url": self.URL}))
        runner.call("web_fetch", json.dumps({"url": self.URL + "#part2"}))
        runner.call("web_fetch", json.dumps({"url": "https://www.sec.gov/final.htm"}))
        self.assertEqual(len(exa.fetches), 1)

    def test_blocked_url_refused_before_cache_or_request(self):
        runner, exa = self.runner("x")
        runner.pages[tools.page_key("https://github.com/x")] = {
            "head": "",
            "text": "gold",
            "url": "https://github.com/x",
        }
        out = runner.call(
            "web_fetch", json.dumps({"url": "https://github.com/x", "find": "gold"})
        )
        self.assertIn("refused", out)
        self.assertNotIn("gold", out.replace("https://github.com/x", ""))
        self.assertTrue(runner.log[-1]["refused"])
        self.assertEqual(exa.fetches, [])
        self.assertEqual(runner.used["web_fetch"], 0)

    def test_exa_fetch_requests_full_page_and_checks_final_url(self):
        session = mock.Mock()
        session.post.return_value = mock.Mock(
            status_code=200,
            json=lambda: {
                "results": [{"url": "https://github.com/vals", "text": "gold"}],
                "costDollars": {"total": 0.001},
            },
        )
        exa = tools.Exa(api_key="k", session=session, blocked=["github.com"])
        with self.assertRaisesRegex(tools.ToolError, "resolved to a blocked host"):
            exa.fetch("https://example.com/redirect")
        body = session.post.call_args.kwargs["json"]
        self.assertEqual(body["text"]["maxCharacters"], tools.FETCH_MAX_CHARS)


class AsOfDiscipline(unittest.TestCase):
    """The as-of date is set first, caps searches, and flags later pages."""

    CAP = protocol.protocol_as_of_date()

    def search_session(self, results):
        return FakeSession({"results": results, "costDollars": {"total": 0.004}})

    def runner(self, session=None, exa=None):
        return tools.ToolRunner(
            exa=exa or tools.Exa(api_key="test", session=session or FakeSession({})),
            sandbox=mock.Mock(),
        )

    def set_as_of(self, runner, day=None):
        args = {"reason": "test"} | ({"date": day} if day else {})
        return runner.call("set_as_of", json.dumps(args))

    def test_prompt_asks_for_the_as_of_date_first(self):
        for prompt in (protocol.SYSTEM_MINIMAL, protocol.SYSTEM_WITH_DATE):
            self.assertIn("set_as_of", prompt)
            self.assertIn("originally reported", prompt)
        names = [t["function"]["name"] for t in tools.TOOL_SPECS]
        self.assertEqual(names[0], "set_as_of")

    def test_search_before_set_as_of_is_refused_without_a_request(self):
        session = self.search_session([])
        runner = self.runner(session)
        out = runner.call("web_search", '{"query": "x"}')
        self.assertIn("set_as_of first", out)
        self.assertEqual(session.calls, [])
        self.assertEqual(runner.used["web_search"], 0)

    def test_set_as_of_caps_searches_and_drops_later_results(self):
        session = self.search_session(
            [
                {"url": "https://a.com/old", "publishedDate": "2024-11-30T00:00:00Z"},
                {"url": "https://a.com/new", "publishedDate": "2025-02-10T00:00:00Z"},
                {"url": "https://a.com/undated"},
            ]
        )
        runner = self.runner(session)
        self.assertIn("2024-12-31", self.set_as_of(runner, "2024-12-31"))
        text = runner.call("web_search", '{"query": "x"}')
        body = session.calls[0][1]
        self.assertEqual(body["endPublishedDate"], "2024-12-31T23:59:59.999Z")
        self.assertIn("a.com/old", text)
        self.assertIn("a.com/undated", text)
        self.assertNotIn("a.com/new", text)
        self.assertEqual(runner.log[-1]["dropped_after_as_of"], 1)

    def test_set_as_of_defaults_to_and_never_passes_the_protocol_date(self):
        runner = self.runner()
        self.set_as_of(runner)
        self.assertEqual(runner.as_of, self.CAP)
        self.set_as_of(runner, "2030-01-01")
        self.assertEqual(runner.as_of, self.CAP)

    def test_bad_date_is_an_error_and_keeps_the_budget(self):
        runner = self.runner()
        self.assertIn("YYYY-MM-DD", self.set_as_of(runner, "December 2024"))
        self.assertIsNone(runner.as_of)
        self.assertEqual(runner.used["set_as_of"], 0)

    def test_set_as_of_can_be_revised_within_its_budget(self):
        runner = self.runner()
        for day in ("2025-03-01", "2021-06-30", "2021-07-15"):
            self.set_as_of(runner, day)
        self.assertEqual(runner.as_of.isoformat(), "2021-07-15")
        self.assertIn("budget", self.set_as_of(runner, "2021-08-01"))

    def test_edgar_filing_year_from_the_accession_number(self):
        url = "https://www.sec.gov/Archives/edgar/data/1617640/000161764025000016/z-20241231.htm"
        self.assertEqual(tools.edgar_filing_year(url), 2025)
        self.assertIsNone(tools.edgar_filing_year("https://www.sec.gov/cgi-bin/browse"))

    def test_fetched_page_after_the_as_of_date_is_flagged(self):
        later = "https://www.sec.gov/Archives/edgar/data/1617640/000161764025000016/z-20241231.htm"
        earlier = "https://www.sec.gov/Archives/edgar/data/1617640/000161764024000012/z-20231231.htm"
        dated = "https://news.example.com/raise"
        exa = FakeExa(
            {later: "FY2024", earlier: "FY2023", dated: "raised"},
            published={dated: "2025-10-30T00:00:00Z"},
        )
        runner = self.runner(exa=exa)
        self.set_as_of(runner, "2024-12-31")
        out = runner.call("web_fetch", json.dumps({"url": later}))
        self.assertTrue(out.startswith("Note: this page was filed in 2025"))
        self.assertTrue(runner.log[-1]["after_as_of"])
        self.assertNotIn(
            "Note:", runner.call("web_fetch", json.dumps({"url": earlier}))
        )
        out = runner.call("web_fetch", json.dumps({"url": dated}))
        self.assertIn("is dated 2025-10-30", out)
        cached = runner.call("web_fetch", json.dumps({"url": later, "offset": 2}))
        self.assertIn("Note:", cached)

    def test_exa_fetch_keeps_the_published_date(self):
        session = FakeSession(
            {
                "results": [
                    {
                        "url": "https://a.com/x",
                        "text": "t",
                        "publishedDate": "2025-01-02T00:00:00Z",
                    }
                ]
            }
        )
        page, _ = tools.Exa(api_key="k", session=session).fetch("https://a.com/x")
        self.assertEqual(tools.parse_day(page["published"]).isoformat(), "2025-01-02")


@unittest.skipUnless(LIVE, "set EARNINGSCOUT_LIVE=1 for live Exa and E2B checks")
class Live(unittest.TestCase):
    def test_live_search_returns_no_blocked_hosts(self):
        text, _, info = tools.Exa().search(
            "vals ai finance agent benchmark public questions github"
        )
        urls = [r["url"] for r in json.loads(text)] if text.startswith("[") else []
        self.assertEqual(len(urls), info["results"])
        for url in urls:
            self.assertFalse(protocol.is_blocked_url(url), url)

    def test_live_sandbox_has_no_network(self):
        box = tools.CodeSandbox()
        try:
            code = (
                "import urllib.request\n"
                "for u in ['https://github.com', 'https://huggingface.co', 'https://www.sec.gov']:\n"
                "    try:\n"
                "        urllib.request.urlopen(u, timeout=8)\n"
                "        print('REACHED', u)\n"
                "    except Exception as e:\n"
                "        print('BLOCKED', u, type(e).__name__)\n"
            )
            text, _, _ = box.run(code)
        finally:
            box.close()
        self.assertNotIn("REACHED", text)
        self.assertEqual(text.count("BLOCKED"), 3)


if __name__ == "__main__":
    unittest.main()

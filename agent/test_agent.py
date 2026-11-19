"""Offline checks for the agent protocol, provider config, tools and loop (no API calls).

Set EARNINGSCOUT_LIVE=1 to also run the live checks, which call Exa and E2B
with the keys in .env (a fraction of a cent).
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import UTC, datetime, timedelta
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

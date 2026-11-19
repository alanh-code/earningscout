"""Agent tools: web search and page fetch on Exa, Python on an E2B sandbox.

Every tool enforces the gold-host blocklist itself:
  web_search      Exa `excludeDomains` plus a host check on every result, and an
                  end-published-date at the protocol as-of date
  web_fetch       host check before the request and on the returned URL
  code_execution  E2B sandbox with internet access off, a per-call timeout and a
                  sandbox lifetime cap; the sandbox is killed when the question ends
"""

from __future__ import annotations

import json
import time

from agent.llm import env_key
from agent.protocol import BLOCKED_DOMAINS, as_of_iso, is_blocked_url

EXA_URL = "https://api.exa.ai"
SEARCH_TYPE = "lite"
SEARCH_RESULTS = 8
SEARCH_HIGHLIGHT_CHARS = 1200
FETCH_MAX_CHARS = 40000
CODE_OUTPUT_CHARS = 20000
EXEC_TIMEOUT_S = 120
SANDBOX_LIFETIME_S = 900
# E2B default sandbox (2 vCPU, 512 MiB) at list price, USD per second.
E2B_USD_PER_S = 2 * 0.000014 + 0.5 * 0.0000045

# Per-question tool budgets.
BUDGETS = {"web_search": 15, "web_fetch": 15, "code_execution": 30}

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web. Returns titles, URLs, publication dates and short excerpts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch the text of a web page or PDF by URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full http(s) URL"}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_execution",
            "description": (
                "Run Python in a sandbox with no internet access. State persists across calls "
                "within this question. Use print() to see values."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code"}
                },
                "required": ["code"],
            },
        },
    },
]


class ToolError(RuntimeError):
    pass


def exa_domains(blocked: list[str]) -> list[str]:
    """Each blocked domain plus its wildcard subdomain form (path entries as is), for Exa excludeDomains."""
    out: list[str] = []
    for d in blocked:
        forms = (d,) if "/" in d else (d, f"*.{d}")
        for form in forms:
            if form not in out:
                out.append(form)
    return out


class Exa:
    def __init__(
        self, api_key: str | None = None, session=None, blocked: list[str] | None = None
    ):
        import requests

        self.key = api_key
        self.session = session or requests.Session()
        self.blocked = list(BLOCKED_DOMAINS if blocked is None else blocked)

    def _post(self, path: str, body: dict) -> dict:
        key = self.key or env_key("EXA_API_KEY")
        delay = 2.0
        for attempt in range(1, 5):
            r = self.session.post(
                EXA_URL + path, headers={"x-api-key": key}, json=body, timeout=90
            )
            if r.status_code in {429, 500, 502, 503, 504} and attempt < 4:
                time.sleep(delay)
                delay *= 2
                continue
            if r.status_code != 200:
                raise ToolError(f"Exa {path} returned HTTP {r.status_code}")
            return r.json()
        raise ToolError(f"Exa {path} failed after retries")

    def search_request(self, query: str) -> dict:
        return {
            "query": query,
            "type": SEARCH_TYPE,
            "numResults": SEARCH_RESULTS,
            "excludeDomains": exa_domains(self.blocked),
            "endPublishedDate": as_of_iso(),
            "contents": {"highlights": {"maxCharacters": SEARCH_HIGHLIGHT_CHARS}},
        }

    def search(self, query: str) -> tuple[str, float, dict]:
        data = self._post("/search", self.search_request(query))
        kept, dropped = [], 0
        for res in data.get("results") or []:
            if is_blocked_url(res.get("url") or "", self.blocked):
                dropped += 1
                continue
            highlights = res.get("highlights") or []
            kept.append(
                {
                    "title": res.get("title"),
                    "url": res.get("url"),
                    "published": res.get("publishedDate"),
                    "excerpt": " ... ".join(highlights)
                    if highlights
                    else (res.get("text") or "")[:SEARCH_HIGHLIGHT_CHARS],
                }
            )
        cost = float((data.get("costDollars") or {}).get("total") or 0)
        text = json.dumps(kept, ensure_ascii=False) if kept else "No results."
        return text, cost, {"results": len(kept), "dropped_blocked": dropped}

    def fetch(self, url: str) -> tuple[str, float, dict]:
        if is_blocked_url(url, self.blocked):
            raise ToolError("refused: that host is blocked for this evaluation")
        data = self._post(
            "/contents", {"urls": [url], "text": {"maxCharacters": FETCH_MAX_CHARS}}
        )
        cost = float((data.get("costDollars") or {}).get("total") or 0)
        results = data.get("results") or []
        if not results:
            statuses = data.get("statuses") or []
            why = (statuses[0].get("error") or {}).get("tag") if statuses else None
            raise ToolError(f"could not fetch the page ({why or 'no content'})")
        res = results[0]
        final_url = res.get("url") or url
        if is_blocked_url(final_url, self.blocked):
            raise ToolError("refused: the page resolved to a blocked host")
        text = res.get("text") or ""
        head = f"Title: {res.get('title') or ''}\nURL: {final_url}\n"
        if res.get("publishedDate"):
            head += f"Published: {res['publishedDate']}\n"
        return head + "\n" + text, cost, {"page_chars": len(text)}


class CodeSandbox:
    """One E2B sandbox per question, created on first use, killed by close()."""

    def __init__(self, api_key: str | None = None, factory=None):
        self.key = api_key
        self.factory = factory
        self.sandbox = None
        self.started = None
        self.alive_s = 0.0

    def _create(self):
        if self.factory is not None:
            return self.factory()
        from e2b_code_interpreter import Sandbox

        return Sandbox.create(
            timeout=SANDBOX_LIFETIME_S,
            allow_internet_access=False,
            api_key=self.key or env_key("E2B_API_KEY"),
        )

    def run(self, code: str) -> tuple[str, float, dict]:
        if self.sandbox is None:
            self.sandbox = self._create()
            self.started = time.monotonic()
        ex = self.sandbox.run_code(code, timeout=EXEC_TIMEOUT_S)
        parts = []
        stdout = "".join(getattr(ex.logs, "stdout", []) or [])
        stderr = "".join(getattr(ex.logs, "stderr", []) or [])
        if stdout:
            parts.append("stdout:\n" + stdout)
        if stderr:
            parts.append("stderr:\n" + stderr)
        for res in ex.results or []:
            if getattr(res, "text", None):
                parts.append("result:\n" + res.text)
        if ex.error:
            parts.append(f"error: {ex.error.name}: {ex.error.value}")
        text = "\n".join(parts) or "(no output)"
        if len(text) > CODE_OUTPUT_CHARS:
            text = text[:CODE_OUTPUT_CHARS] + "\n[output truncated]"
        return text, 0.0, {"code_error": bool(ex.error)}

    def close(self) -> float:
        """Kill the sandbox. Returns its compute cost in USD."""
        if self.sandbox is None:
            return 0.0
        try:
            self.sandbox.kill()
        finally:
            self.alive_s = time.monotonic() - (self.started or time.monotonic())
            self.sandbox = None
        return self.alive_s * E2B_USD_PER_S


class ToolRunner:
    """Dispatch tool calls, enforce budgets, and log every call."""

    def __init__(
        self,
        exa: Exa | None = None,
        sandbox: CodeSandbox | None = None,
        budgets: dict | None = None,
    ):
        self.exa = exa or Exa()
        self.sandbox = sandbox or CodeSandbox()
        self.budgets = dict(BUDGETS if budgets is None else budgets)
        self.used = {k: 0 for k in self.budgets}
        self.log: list[dict] = []
        self.cost = {"exa": 0.0, "e2b": 0.0}

    def call(self, name: str, raw_args: str) -> str:
        entry: dict = {"name": name, "ok": False}
        try:
            args = json.loads(raw_args or "{}")
            if not isinstance(args, dict):
                raise ToolError("arguments must be a JSON object")
            entry["args"] = args
            if name not in self.budgets:
                raise ToolError(f"unknown tool {name!r}")
            if self.used[name] >= self.budgets[name]:
                raise ToolError(
                    f"{name} budget of {self.budgets[name]} calls is used up; answer with what you have"
                )
            self.used[name] += 1
            if name == "web_search":
                text, cost, info = self.exa.search(str(args.get("query") or ""))
                self.cost["exa"] += cost
            elif name == "web_fetch":
                text, cost, info = self.exa.fetch(str(args.get("url") or ""))
                self.cost["exa"] += cost
            else:
                text, cost, info = self.sandbox.run(str(args.get("code") or ""))
            entry.update(ok=True, cost_usd=cost, chars=len(text), **info)
            return text
        except json.JSONDecodeError:
            entry["error"] = "arguments were not valid JSON"
            return "Error: arguments were not valid JSON."
        except ToolError as exc:
            entry["error"] = str(exc)
            entry["refused"] = str(exc).startswith("refused")
            return f"Error: {exc}"
        except Exception as exc:  # noqa: BLE001 - a tool failure is reported back to the model
            entry["error"] = f"{type(exc).__name__}: {exc}"
            return f"Error: {type(exc).__name__}: {exc}"
        finally:
            self.log.append(entry)

    def close(self) -> None:
        self.cost["e2b"] += self.sandbox.close()

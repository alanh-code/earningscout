"""Agent tools: web search and page fetch on Exa, Python on an E2B sandbox.

Every tool enforces the gold-host blocklist itself:
  set_as_of       the question's as-of date, which the model works out first; it
                  caps later searches (never past the protocol as-of date)
  web_search      Exa `excludeDomains` plus a host check on every result, and an
                  end-published-date at the as-of date; results dated later are dropped
  web_fetch       host check before the request and on the returned URL; the full
                  page is cached per question so later chunks and in-page searches
                  make no new request; a page dated after the as-of date carries a
                  note saying so
  code_execution  E2B sandbox with internet access off, a per-call timeout and a
                  sandbox lifetime cap; the sandbox is killed when the question ends
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from datetime import date
from pathlib import Path
from typing import ClassVar

from agent.llm import env_key
from agent.protocol import (
    BLOCKED_DOMAINS,
    as_of_iso,
    is_blocked_url,
    protocol_as_of_date,
)

EXA_URL = "https://api.exa.ai"
SEARCH_TYPE = "lite"
SEARCH_RESULTS = 8
SEARCH_HIGHLIGHT_CHARS = 1200
FETCH_MAX_CHARS = 400000
FETCH_CHUNK_CHARS = 40000
FIND_MAX_MATCHES = 8
FIND_CONTEXT_CHARS = 600
FIND_MIN_WORD = 4
CODE_OUTPUT_CHARS = 20000
EXEC_TIMEOUT_S = 120
SANDBOX_LIFETIME_S = 900
# E2B default sandbox (2 vCPU, 512 MiB) at list price, USD per second.
E2B_USD_PER_S = 2 * 0.000014 + 0.5 * 0.0000045

# Per-question tool budgets. Reading a further chunk of, or searching in, an already
# fetched page is free but has its own cap.
BUDGETS = {
    "web_search": 15,
    "web_fetch": 15,
    "code_execution": 30,
    "set_as_of": 3,
    "sec_filings": 6,
}
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# EDGAR's entity search also knows former registrants (acquired or delisted) missing from the ticker file.
SEC_ENTITY_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index?keysTyped={query}"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEC_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"
# SEC asks automated clients to name themselves; override with SEC_USER_AGENT in .env.
SEC_USER_AGENT = "earningscout research contact@example.com"
SEC_FORMS = ("10-K", "10-Q", "8-K")
SEC_LIST_LIMIT = 12
PAGE_READS = 40
# Set by runners (--tool-cache). When set, Exa responses are kept on disk keyed by the normalized
# request, so a repeated search or fetch sees exactly the results it saw the first time.
CACHE_DIR: Path | None = None

# EDGAR archive paths carry the accession number, whose digits 11-12 are the filing year.
EDGAR_ACCESSION = re.compile(
    r"/Archives/edgar/data/\d+/(\d{10})(\d{2})(\d{6})(?:/|$)", re.IGNORECASE
)

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "set_as_of",
            "description": (
                "Set the question's as-of date before searching. web_search then returns only pages "
                "published on or before it, and fetched pages dated later are flagged. Omit date when "
                "the question allows the latest information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "As-of date, YYYY-MM-DD"},
                    "reason": {
                        "type": "string",
                        "description": "One line: why this is the as-of date",
                    },
                },
                "required": ["reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sec_filings",
            "description": (
                "List a US-listed company's SEC EDGAR filings filed on or before the as-of date, newest "
                "first, with each main document and its filing index. The index is a folder listing: "
                "join its URL with a file name to read an exhibit, such as an 8-K's ex99 press release. "
                "Read filings with web_fetch."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Ticker or company name"},
                    "forms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Form types, default 10-K, 10-Q and 8-K",
                    },
                },
                "required": ["company"],
            },
        },
    },
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
            "description": (
                "Fetch the text of a web page or PDF by URL, 40,000 characters at a time. "
                "Long pages report their total length; pass offset to read further, or find "
                "to get the passages that mention a phrase. Re-reading a fetched page is free."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full http(s) URL"},
                    "offset": {
                        "type": "integer",
                        "description": "Character offset to start reading from (default 0)",
                    },
                    "find": {
                        "type": "string",
                        "description": "Phrase to search for in the page; returns matching passages with their offsets",
                    },
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


def cache_key(path: str, body: dict) -> str:
    """Hash of an Exa request with the query case and spacing and the URL fragment normalized."""
    body = dict(body)
    if "query" in body:
        body["query"] = " ".join(str(body["query"]).lower().split())
    if "urls" in body:
        body["urls"] = [page_key(u) for u in body["urls"]]
    return hashlib.sha256(json.dumps([path, body], sort_keys=True).encode()).hexdigest()


class Exa:
    def __init__(
        self,
        api_key: str | None = None,
        session=None,
        blocked: list[str] | None = None,
        cache_dir: Path | None = None,
    ):
        import requests

        self.key = api_key
        self.session = session or requests.Session()
        self.blocked = list(BLOCKED_DOMAINS if blocked is None else blocked)
        self.cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
        self.last_hit = False

    def _post(self, path: str, body: dict) -> dict:
        """POST to Exa, through the disk cache when one is set. A cache hit costs nothing."""
        self.last_hit = False
        if self.cache_dir is None:
            return self._post_live(path, body)
        file = self.cache_dir / f"{cache_key(path, body)}.json"
        if file.exists():
            self.last_hit = True
            data = json.loads(file.read_text(encoding="utf-8"))
            data.pop("costDollars", None)
            return data
        data = self._post_live(path, body)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = file.with_suffix(f".{os.getpid()}.{id(self)}.tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, file)
        return data

    def _post_live(self, path: str, body: dict) -> dict:
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

    def search_request(self, query: str, end: date | None = None) -> dict:
        return {
            "query": query,
            "type": SEARCH_TYPE,
            "numResults": SEARCH_RESULTS,
            "excludeDomains": exa_domains(self.blocked),
            "endPublishedDate": as_of_iso(end),
            "contents": {"highlights": {"maxCharacters": SEARCH_HIGHLIGHT_CHARS}},
        }

    def search(self, query: str, end: date | None = None) -> tuple[str, float, dict]:
        """Search pages published on or before end (default: the protocol as-of date)."""
        end = end or protocol_as_of_date()
        data = self._post("/search", self.search_request(query, end))
        kept, dropped, late = [], 0, 0
        for res in data.get("results") or []:
            if is_blocked_url(res.get("url") or "", self.blocked):
                dropped += 1
                continue
            published = parse_day(res.get("publishedDate"))
            if published and published > end:
                late += 1
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
        return (
            text,
            cost,
            {
                "results": len(kept),
                "dropped_blocked": dropped,
                "dropped_after_as_of": late,
                "exa_cache_hit": self.last_hit,
            },
        )

    def fetch(self, url: str) -> tuple[dict, float]:
        """Fetch a whole page. Returns {"head", "text", "url"} and the Exa cost."""
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
        head = f"Title: {res.get('title') or ''}\nURL: {final_url}\n"
        if res.get("publishedDate"):
            head += f"Published: {res['publishedDate']}\n"
        return {
            "head": head,
            "text": res.get("text") or "",
            "url": final_url,
            "published": res.get("publishedDate"),
            "exa_cache_hit": self.last_hit,
        }, cost


def parse_day(value) -> date | None:
    """The date part of an ISO 8601 date or timestamp, or None."""
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def edgar_filing_year(url: str) -> int | None:
    """Filing year from an EDGAR archive URL's accession number, or None."""
    m = EDGAR_ACCESSION.search(url or "")
    return 2000 + int(m.group(2)) if m else None


def after_as_of_note(page: dict, as_of: date) -> str:
    """A note for a page dated after the as-of date, or an empty string."""
    published = parse_day(page.get("published"))
    if published and published > as_of:
        when = f"is dated {published.isoformat()}"
    else:
        year = edgar_filing_year(page.get("url") or "")
        if not year or year <= as_of.year:
            return ""
        when = f"was filed in {year}"
    return (
        f"Note: this page {when}, after the as-of date {as_of.isoformat()}. Prefer sources issued "
        "on or before it, and do not report this page's later figures as the answer.\n"
    )


def page_key(url: str) -> str:
    """Cache key: the URL without its fragment or surrounding whitespace."""
    return url.strip().split("#", 1)[0]


def page_chunk(page: dict, offset: int) -> tuple[str, dict]:
    text = page["text"]
    total = len(text)
    start = min(max(offset, 0), total)
    end = min(start + FETCH_CHUNK_CHARS, total)
    out = page["head"]
    if total > FETCH_CHUNK_CHARS or start:
        out += f"Characters {start}-{end} of {total}."
        if end < total:
            out += f" {total - end} remain: call web_fetch with offset={end} to read on, or find to search this page."
        out += "\n"
    return out + "\n" + text[start:end], {
        "page_chars": total,
        "start": start,
        "end": end,
    }


def find_positions(text: str, query: str) -> list[int]:
    """Start offsets of the phrase (case-insensitive); if it never occurs, of its longer words."""
    low = text.lower()
    terms = [query.lower().strip()]
    if terms[0] not in low:
        terms = [w for w in terms[0].split() if len(w) >= FIND_MIN_WORD]
    hits: list[int] = []
    for term in terms:
        i = low.find(term) if term else -1
        while i != -1:
            hits.append(i)
            i = low.find(term, i + 1)
    return sorted(set(hits))


def page_find(page: dict, query: str) -> tuple[str, dict]:
    text = page["text"]
    passages: list[tuple[int, int]] = []
    for pos in find_positions(text, query):
        start = max(pos - FIND_CONTEXT_CHARS, 0)
        end = min(pos + FIND_CONTEXT_CHARS, len(text))
        if passages and start <= passages[-1][1]:
            passages[-1] = (passages[-1][0], end)
        else:
            passages.append((start, end))
    shown = passages[:FIND_MAX_MATCHES]
    out = page["head"] + f"Page length {len(text)} characters. "
    if not shown:
        out += f"No match for {query!r}."
    else:
        out += f"{len(passages)} passages match {query!r}"
        out += (
            f"; showing the first {len(shown)}." if len(passages) > len(shown) else "."
        )
        for start, end in shown:
            out += f"\n\n[characters {start}-{end}]\n{text[start:end]}"
    return out, {"page_chars": len(text), "find": query, "matches": len(passages)}


def _norm_name(name: str) -> str:
    name = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    words = [w for w in name.split() if w not in {"inc", "corp", "corporation", "co", "company", "ltd", "plc", "the", "holdings", "group"}]
    return " ".join(words)


class Sec:
    """SEC EDGAR company lookup and filing lists. Responses are shared across questions in a process."""

    _cache: ClassVar[dict[str, dict]] = {}
    _lock = threading.Lock()

    def __init__(self, session=None, user_agent: str | None = None):
        import requests

        self.session = session or requests.Session()
        self.user_agent = user_agent or os.environ.get("SEC_USER_AGENT") or SEC_USER_AGENT

    def _get(self, url: str) -> dict:
        with self._lock:
            if url in self._cache:
                return self._cache[url]
        delay = 1.0
        for attempt in range(1, 5):
            r = self.session.get(url, headers={"User-Agent": self.user_agent}, timeout=60)
            if r.status_code in {429, 500, 502, 503, 504} and attempt < 4:
                time.sleep(delay)
                delay *= 2
                continue
            if r.status_code != 200:
                raise ToolError(f"SEC EDGAR returned HTTP {r.status_code}")
            data = r.json()
            with self._lock:
                self._cache[url] = data
            return data
        raise ToolError("SEC EDGAR failed after retries")

    def resolve(self, company: str) -> tuple[int, str]:
        """CIK and name for a ticker or company name: exact ticker, exact name or name prefix in the
        current ticker file, then EDGAR's entity search (former registrants too)."""
        rows = list(self._get(SEC_TICKERS_URL).values())
        q = company.strip()
        for test in (
            lambda r: r["ticker"].upper() == q.upper().lstrip("$"),
            lambda r: _norm_name(r["title"]) == _norm_name(q),
            lambda r: _norm_name(r["title"]).startswith(_norm_name(q)),
        ):
            hits = [r for r in rows if test(r)]
            if hits and _norm_name(q):
                return int(hits[0]["cik_str"]), hits[0]["title"]
        if _norm_name(q):
            from urllib.parse import quote

            found = self._get(SEC_ENTITY_SEARCH_URL.format(query=quote(q)))
            hits = (found.get("hits") or {}).get("hits") or []
            if hits:
                return int(hits[0]["_id"]), hits[0]["_source"]["entity"]
        raise ToolError(f"no SEC registrant matches {company!r}; try its ticker or full legal name")

    def filings(self, company: str, as_of: date, forms=SEC_FORMS) -> tuple[str, dict]:
        cik, name = self.resolve(company)
        recent = self._get(SEC_SUBMISSIONS_URL.format(cik=cik))["filings"]["recent"]
        wanted = {f.upper() for f in forms} or set(SEC_FORMS)
        rows = []
        for i, form in enumerate(recent["form"]):
            filed = parse_day(recent["filingDate"][i])
            base = form.upper().removesuffix("/A")
            if base not in wanted or filed is None or filed > as_of:
                continue
            acc = recent["accessionNumber"][i].replace("-", "")
            index = SEC_ARCHIVE_URL.format(cik=cik, acc=acc)
            rows.append(
                {
                    "form": form,
                    "filed": filed.isoformat(),
                    "period": recent["reportDate"][i] or None,
                    "items": recent.get("items", [""] * (i + 1))[i] or None,
                    "document": index + recent["primaryDocument"][i],
                    "index": index,
                }
            )
        rows.sort(key=lambda r: r["filed"], reverse=True)
        rows = rows[:SEC_LIST_LIMIT]
        head = f"{name} (CIK {cik}), filings on or before {as_of.isoformat()}:\n"
        text = head + (json.dumps(rows, ensure_ascii=False) if rows else "No filings of those forms.")
        return text, {"cik": cik, "results": len(rows)}


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
        sec: Sec | None = None,
    ):
        self.exa = exa or Exa()
        self.sec = sec or Sec()
        self.sandbox = sandbox or CodeSandbox()
        self.budgets = dict(BUDGETS if budgets is None else budgets)
        self.used = {k: 0 for k in self.budgets}
        self.page_reads = 0
        self.as_of: date | None = None
        self.pages: dict[str, dict] = {}
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
            if name == "web_fetch":
                text, cost, info = self.web_fetch(args)
                entry.update(ok=True, cost_usd=cost, chars=len(text), **info)
                return text
            if name in ("web_search", "sec_filings") and self.as_of is None:
                raise ToolError(
                    "call set_as_of first: work out the question's as-of date"
                )
            self.spend(name)
            if name == "set_as_of":
                text, cost, info = self.set_as_of(args)
            elif name == "sec_filings":
                forms = args.get("forms") or SEC_FORMS
                if isinstance(forms, str):
                    forms = [forms]
                text, info = self.sec.filings(str(args.get("company") or ""), self.as_of, forms)
                cost = 0.0
            elif name == "web_search":
                text, cost, info = self.exa.search(
                    str(args.get("query") or ""), self.as_of
                )
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

    def spend(self, name: str) -> None:
        if self.used[name] >= self.budgets[name]:
            raise ToolError(
                f"{name} budget of {self.budgets[name]} calls is used up; answer with what you have"
            )
        self.used[name] += 1

    def set_as_of(self, args: dict) -> tuple[str, float, dict]:
        """Record the as-of date; none, or one past the protocol date, means the protocol date."""
        cap = protocol_as_of_date()
        raw = str(args.get("date") or "").strip()
        day = parse_day(raw) if raw else cap
        if day is None:
            self.used["set_as_of"] -= 1
            raise ToolError(
                "date must be YYYY-MM-DD, or omit it for the latest information"
            )
        self.as_of = min(day, cap)
        text = (
            f"As-of date set to {self.as_of.isoformat()}. web_search returns pages published on or "
            "before it; fetched pages dated later are flagged."
        )
        return text, 0.0, {"as_of": self.as_of.isoformat(), "requested": raw or None}

    def web_fetch(self, args: dict) -> tuple[str, float, dict]:
        """Serve from the page cache when possible; only a first fetch calls Exa and uses the fetch budget."""
        url = str(args.get("url") or "")
        if is_blocked_url(url, self.exa.blocked):
            raise ToolError("refused: that host is blocked for this evaluation")
        try:
            offset = int(args.get("offset") or 0)
        except (TypeError, ValueError):
            raise ToolError("offset must be an integer") from None
        find = str(args.get("find") or "").strip()
        page = self.pages.get(page_key(url))
        cost = 0.0
        cached = page is not None
        if not cached:
            self.spend("web_fetch")
            page, cost = self.exa.fetch(url)
            self.cost["exa"] += cost
            self.pages[page_key(url)] = page
            self.pages.setdefault(page_key(page["url"]), page)
        else:
            if self.page_reads >= PAGE_READS:
                raise ToolError(
                    f"page re-read limit of {PAGE_READS} is used up; answer with what you have"
                )
            self.page_reads += 1
        text, info = page_find(page, find) if find else page_chunk(page, offset)
        note = after_as_of_note(page, self.as_of or protocol_as_of_date())
        return note + text, cost, {
            "cached": cached,
            "exa_cache_hit": page.get("exa_cache_hit", False),
            "after_as_of": bool(note),
            **info,
        }

    def close(self) -> None:
        self.cost["e2b"] += self.sandbox.close()

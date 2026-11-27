"""Scoring protocol shared by the agent and the evals: as-of date, gold-host blocklist, prompts.

These values define the benchmark protocol, so every runner reads them from here.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import unquote, urlsplit

SEED = 42

# Scoring-protocol as-of date. After the newest gold as-of (April 7, 2025 in
# vals-07 and vals-19); in the month the public set appeared on GitHub; not a
# build or run day.
PROTOCOL_AS_OF = "Thursday, May 1, 2025"

# Hosts that carry the Vals finance-agent public gold, mirrors of its repo or
# dataset, or redistributions of the tasks. A listed domain also covers its
# subdomains. An entry with a path ("doi.org/10.5281") blocks only URLs on that
# host whose path starts with that prefix.
BLOCKED_DOMAINS = [
    # the benchmark repo, its raw files, the Vals site and the dataset hosts
    "github.com",
    "githubusercontent.com",
    "raw.githubusercontent.com",
    "vals.ai",
    "huggingface.co",
    "hf.co",
    "zenodo.org",
    "hf-mirror.com",
    # mirrors and redistributions of the repo, dataset or tasks
    "vals-ai.com",
    "github.laiyagushi.com",
    "deepwiki.com",
    "meridianlabs-ai.github.io",
    "harborframework.com",
    "openreward.ai",
    "context7.com",
    "shadowgraph.io",
    # DOI prefixes that resolve to the Zenodo and Hugging Face copies
    "doi.org/10.5281",
    "doi.org/10.57967",
    # GitHub CDN and proxy mirrors; jsDelivr, githack and ghproxy serve the gold CSV through fetch
    "cdn.jsdelivr.net/gh",
    "fastly.jsdelivr.net/gh",
    "gcore.jsdelivr.net/gh",
    "testingcf.jsdelivr.net/gh",
    "cdn.statically.io/gh",
    "githack.com",
    "ghproxy.net",
    "ghproxy.com",
    "gh-proxy.com",
    "ghfast.top",
    "kkgithub.com",
    "bgithub.xyz",
    "gitmirror.com",
    # agent skills tuned to the benchmark that encode its answer template and rubric conventions
    "verified-skill.com",
    "coralbricks.ai",
]

# Strings that mark the gold repo or dataset anywhere in a URL (forks, archives, proxies).
GOLD_URL_MARKERS = ("vals-ai/finance-agent", "finance_agent_benchmark")

AS_OF_RULES = (
    "Before searching, work out the question's as-of date and call set_as_of with it. "
    "It is the latest date whose information the question allows: a date the question says it is now, "
    "or that limits what is known (for example 'it is currently March 11, 2025' or "
    "'as of December 2024, what has been ...'); otherwise, for guidance, plans, announcements or "
    "expected dates, the date they were first issued. A period-end date that names what to report "
    "('as of Dec 31, 2024', 'FY 2024') is not an as-of date, because the report for that period comes "
    "out later. If the question allows the latest information, call set_as_of without a date. "
    "You may call set_as_of again once you learn when something was first issued. "
    "Prefer filings and articles issued on or before the as-of date, use figures as originally reported "
    "then rather than later revisions, restatements or updated guidance, and leave later developments "
    "out of the final answer. Check the publication date of each source: do not use one issued after "
    "the as-of date, and when sources disagree use the latest one issued on or before it."
)
ANSWER_RULES = (
    "Unless the question or the source uses another precision, report ratios and multiples to two decimal "
    "places (for example 4.27, not 4.3). A percentage difference from guidance or consensus (a beat or miss), "
    "a growth rate or a margin is a percentage, not a ratio: give it to one decimal place (for example 2.9% or "
    "18.4 bps), the same way in the explanation and in the final block. When the question or the source states "
    "its figures with a given number of decimals, answer with the same. "
    "Commit to one final figure for each item at one precision; never show the same quantity at two different "
    "roundings (for example 3.46 and 3.5). "
    "Lead with the figure the question asks for as the source states it (the headline figure in the "
    "filing or press release); put purchase price or other adjustments in a short note "
    "after it, not into the figure."
)
COVERAGE_RULES = (
    "Before answering, list every item the question asks for (each company, period, metric, comparison "
    "and explanation) and make sure the final answer covers each one. When a result is compared with a "
    "guided or expected range, state the difference from both the low end and the high end. "
    "For a change or trend over a span of years or periods, give the value for every year or period in the "
    "span, the overall change and the average annual rate, give the rate separately for each sub-period when the pace "
    "or direction changes, and say what drove it. For a request to summarize "
    "or list (risks, factors, items), cover every distinct category the source names, one line each, in the "
    "source's own terms, and put that summary in the final block instead of 'n/a'. "
    "Include only what the question asks for: leave out extra figures, dates, alternative readings or "
    "side claims that could conflict with the answer."
)
DEFINITION_RULES = (
    "Judge beat, miss or in line against the benchmark the question names; when it names none, use the "
    "company's own guidance, and call a result within the guided range in line (met), using the "
    "source's own wording where it gives one. When the source itself quantifies an impact, change or "
    "growth rate, quote that figure instead of recomputing it with a different method. "
    "Compute only from inputs exactly as the source reports them (same line items, period and units). "
    "For a comparison with guidance or an estimate, use the headline figures as published in the guidance "
    "release and in the results release (the figures its text states), not a more precise value rebuilt from "
    "supplemental tables; round only the final result."
)
OUTPUT_RULES = (
    "Do every calculation (sums, differences, averages, ratios, growth rates, margins) with "
    "code_execution and copy the result from its output; do not compute in your head. "
    "Write the explanation first, then end the reply with this block and nothing after it, "
    "one line for each figure or verdict the question asks for, so no part is left out:\n"
    "Final answer:\n"
    "- <what it is>: value <number or n/a>; unit <for example USD millions, %, bps, x, shares, or n/a>; "
    "label <beat, miss, in line, yes, no, or n/a>"
)
SOURCE_RULES = (
    "For figures a US-listed company reports (financial statements, guidance, deal terms), call "
    "sec_filings first and read the relevant 10-K, 10-Q or 8-K with web_fetch (an 8-K's press release "
    "is an exhibit listed in its filing index); use web_search for what the filings do not cover."
)
SYSTEM_MINIMAL = (
    "Answer the question. Use the available tools when they help. "
    "If a fetched page is longer than one chunk, read on with web_fetch offset or search it with find "
    "instead of guessing what the rest says. "
    f"{AS_OF_RULES} {SOURCE_RULES} {ANSWER_RULES} {COVERAGE_RULES} {DEFINITION_RULES} {OUTPUT_RULES}"
)
SYSTEM_WITH_DATE = (
    f"{SYSTEM_MINIMAL} "
    f"Today's date is {PROTOCOL_AS_OF}. If the question gives a different as-of date, use the date in the question."
)


def system_for(question: str) -> str:
    """The as-of date is injected only when the question asks about the current state."""
    if "current" in question.lower():
        return SYSTEM_WITH_DATE
    return SYSTEM_MINIMAL


def protocol_as_of_date() -> date:
    """The protocol as-of date: no tool returns pages published after it."""
    return datetime.strptime(PROTOCOL_AS_OF, "%A, %B %d, %Y").date()


def as_of_iso(day: date | None = None) -> str:
    """An as-of date (default: the protocol date) as an ISO 8601 instant at the end of that day, UTC."""
    return (day or protocol_as_of_date()).strftime("%Y-%m-%dT23:59:59.999Z")


def host_of(url: str) -> str:
    try:
        host = urlsplit(url.strip()).hostname or ""
    except ValueError:
        return ""
    return host.lower().rstrip(".")


def _host_matches(host: str, domain: str) -> bool:
    domain = domain.lower().removeprefix("*.").rstrip(".")
    return host == domain or host.endswith("." + domain)


def is_blocked_host(host: str, blocked: list[str] | None = None) -> bool:
    """True when the whole host is blocked (path-scoped entries are ignored here)."""
    host = (host or "").lower().rstrip(".")
    if not host:
        return False
    for entry in BLOCKED_DOMAINS if blocked is None else blocked:
        if "/" not in entry and _host_matches(host, entry):
            return True
    return False


def is_blocked_path(host: str, path: str, blocked: list[str] | None = None) -> bool:
    host = (host or "").lower().rstrip(".")
    for entry in BLOCKED_DOMAINS if blocked is None else blocked:
        if "/" in entry:
            domain, prefix = entry.split("/", 1)
            if _host_matches(host, domain) and path.lstrip("/").lower().startswith(
                prefix.lower()
            ):
                return True
    return False


def is_blocked_url(url: str, blocked: list[str] | None = None) -> bool:
    """True for a blocked host, and for anything that is not a plain http(s) URL with a host."""
    try:
        parts = urlsplit((url or "").strip())
    except ValueError:
        return True
    if parts.scheme.lower() not in {"http", "https"}:
        return True
    host = host_of(url)
    if not host:
        return True
    if is_blocked_host(host, blocked) or is_blocked_path(host, parts.path, blocked):
        return True
    rest = unquote(f"{parts.path}?{parts.query}#{parts.fragment}").lower()
    if any(marker in rest for marker in GOLD_URL_MARKERS):
        return True
    return _embeds_blocked_url(rest, blocked)


def _embeds_blocked_url(rest: str, blocked: list[str] | None = None) -> bool:
    """True when the path or query wraps a blocked URL (web archives, proxies such as host/https://github.com/...)."""
    for entry in BLOCKED_DOMAINS if blocked is None else blocked:
        pattern = re.escape(entry.lower().removeprefix("*."))
        if re.search(rf"(?:^|[/.@=:])(?:{pattern})(?:[/:?#&]|$)", rest):
            return True
    return False

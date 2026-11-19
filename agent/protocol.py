"""Scoring protocol shared by the agent and the evals: as-of date, gold-host blocklist, prompts.

These values define the benchmark protocol, so every runner reads them from here.
"""

from __future__ import annotations

import re
from datetime import datetime
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

SYSTEM_MINIMAL = "Answer the question. Use the available tools when they help."
SYSTEM_WITH_DATE = (
    "Answer the question. Use the available tools when they help. "
    f"Today's date is {PROTOCOL_AS_OF}. If the question gives a different as-of date, use the date in the question."
)


def system_for(question: str) -> str:
    """The as-of date is injected only when the question asks about the current state."""
    if "current" in question.lower():
        return SYSTEM_WITH_DATE
    return SYSTEM_MINIMAL


def as_of_iso() -> str:
    """The protocol as-of date as an ISO 8601 instant (end of that day, UTC)."""
    day = datetime.strptime(PROTOCOL_AS_OF, "%A, %B %d, %Y")
    return day.strftime("%Y-%m-%dT23:59:59.999Z")


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

#!/usr/bin/env python3
"""Scan a baseline run's traces for gold-source URLs or text."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from agent.protocol import BLOCKED_DOMAINS, is_blocked_url  # noqa: E402

GOLD_TEXT = re.compile(
    r"finance[-_]agent|finance_agent_benchmark|vals-ai/finance|github\.com/vals-ai|"
    r"huggingface\.co/datasets/vals-ai|public\.csv|vals\.ai",
    re.IGNORECASE,
)
URL = re.compile(r"https?://[^\s\]\"'<>)]+", re.IGNORECASE)
# Default: the protocol blocklist; a run's run_meta.json may add more.
DEFAULT_DOMAINS = set(BLOCKED_DOMAINS)


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().lstrip(".")
    except ValueError:
        return ""


def covered(host: str, domains: set[str]) -> str | None:
    for d in domains:
        if host == d or host.endswith("." + d):
            return d
    return None


def blocked_by(url: str, domains: set[str]) -> str | None:
    """The blocked domain covering the URL's host, else "protocol rule" when the
    protocol check blocks it (path entries, wrapped URLs, gold markers), else None."""
    host = host_of(url)
    hit = covered(host, domains) if host else None
    if hit:
        return hit
    if host and is_blocked_url(url, sorted(domains)):
        return "protocol rule"
    return None


def walk(obj, bag: list[str]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            walk(v, bag)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, bag)
    elif isinstance(obj, str):
        bag.append(obj)


def scan_run(run_dir: Path, domains: set[str]) -> list[dict]:
    hits = []
    for folder in ("traces", "raw"):
        for path in sorted((run_dir / folder).glob("vals-*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            strings: list[str] = []
            walk(data.get("turns") or data, strings)
            blob = "\n".join(strings)
            qid = data.get("id") or path.stem
            urls = URL.findall(blob)
            seen = set()
            for url in urls:
                url = url.rstrip(".,;)]}")
                key = ("url", url)
                if key in seen:
                    continue
                blocked = blocked_by(url, domains)
                goldish = bool(GOLD_TEXT.search(url))
                if blocked or goldish:
                    seen.add(key)
                    hits.append(
                        {
                            "id": qid,
                            "file": str(path.relative_to(run_dir)),
                            "kind": "url",
                            "blocked_domain": blocked,
                            "gold_pattern": goldish,
                            "value": url,
                        }
                    )
            # Text hits that are not just the same URLs already reported.
            for m in GOLD_TEXT.finditer(blob):
                start = max(0, m.start() - 80)
                end = min(len(blob), m.end() + 80)
                snippet = re.sub(r"\s+", " ", blob[start:end]).strip()
                key = ("text", snippet)
                if key in seen:
                    continue
                # skip if snippet is only a URL already listed
                if any(h["id"] == qid and h["value"] in snippet for h in hits):
                    continue
                seen.add(key)
                hits.append(
                    {
                        "id": qid,
                        "file": str(path.relative_to(run_dir)),
                        "kind": "text",
                        "blocked_domain": None,
                        "gold_pattern": True,
                        "value": snippet,
                    }
                )
    return hits


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path)
    args = ap.parse_args()
    run_dir = args.run_dir
    domains = set(DEFAULT_DOMAINS)
    meta = run_dir / "run_meta.json"
    if meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        extra = (
            m.get("blocked_domains")
            or (m.get("tools_enabled") or {}).get("blocked_domains")
            or []
        )
        domains.update(extra)
    hits = scan_run(run_dir, domains)
    out = run_dir / "leak_scan.json"
    out.write_text(
        json.dumps({"n_hits": len(hits), "hits": hits}, indent=2, ensure_ascii=False)
        + "\n"
    )
    print(f"{len(hits)} gold-source hits in {run_dir}")
    for h in hits:
        print(f"  {h['id']} {h['kind']} {h['value'][:200]}")


if __name__ == "__main__":
    main()

"""Deterministic grading of numeric rubric checks.

An LLM only locates text: for each rubric check it copies the gold number span and
the matching span from the model answer. Python then parses both spans (units,
scale, sign, ranges, bounds, hedges) and compares them with fixed rules:

- A precise answer must equal the gold at the gold's stated precision.
- A coarser answer is accepted only as normal rounding (within ROUNDING_REL).
- A hedged answer, range or bound is accepted when it honestly contains the gold
  and is tight enough not to mislead (HEDGE_REL, RANGE_REL, BOUND_REL).
- A gold range must be matched endpoint by endpoint, so shifted ranges fail.

Verdicts: correctness checks are "met" / "not met" / "not found" (no committed
figure located, left to the judge); contradiction checks are "triggered" /
"not triggered"; checks without numbers are "not numeric".
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, replace

ROUNDING_REL = 0.005  # coarser exact answer, e.g. $105B for $105.2B
HEDGE_REL = 0.05  # "about $100B" for $105.2B
RANGE_REL = 0.20  # answer range width relative to the gold
BOUND_REL = 0.10  # "$100B or more" for $105.2B

SCALES = {
    "k": 1e3,
    "thousand": 1e3,
    "thousands": 1e3,
    "m": 1e6,
    "mm": 1e6,
    "mn": 1e6,
    "mil": 1e6,
    "million": 1e6,
    "millions": 1e6,
    "b": 1e9,
    "bn": 1e9,
    "billion": 1e9,
    "billions": 1e9,
    "t": 1e12,
    "tn": 1e12,
    "trillion": 1e12,
    "trillions": 1e12,
    "cent": 0.01,
    "cents": 0.01,
    "¢": 0.01,
}
CURRENCY = r"(?:NT\$|US\$|HK\$|C\$|A\$|\$|€|£|¥|RMB|USD|NTD|EUR)"
NUMBER = re.compile(
    rf"(?P<sign>[-−]|\()?\s?(?P<cur>{CURRENCY})?\s?(?P<sign2>[-−]|\()?"
    r"(?P<num>\d[\d,]*(?:\.\d+)?|\.\d+)\)?\s*"
    r"(?P<scale>thousands?|millions?|billions?|trillions?|cents?|¢|mil|mn|mm|bn|tn|[kmbt](?![a-z]))?\s*"
    r"(?P<unit>%|percent(?:age points?)?|pct|pp|ppts?|bps|basis points?|x(?![a-z]))?",
    re.IGNORECASE,
)
RANGE_JOIN = re.compile(r"^\s*(?:to|through|and|[-–—~])?\s*$", re.IGNORECASE)
HEDGE = re.compile(
    r"\b(about|approx\w*|roughly|around|nearly|almost|close to|some|est\w*)\b|~|≈",
    re.IGNORECASE,
)
LOWER = re.compile(
    r"\b(or more|or higher|at least|more than|over|above|exceed\w*|upwards of)\b|\+\s*$|>",
    re.IGNORECASE,
)
UPPER = re.compile(
    r"\b(or less|or lower|at most|less than|under|below|up to|no more than)\b|<",
    re.IGNORECASE,
)
NEG_WORD = re.compile(
    r"\b(loss|losses|decline[ds]?|decrease[ds]?|down|miss(?:ed)?|negative|fell|drop(?:ped)?|shortfall)\b",
    re.IGNORECASE,
)
# "down" is omitted here: it is too common in ordinary prose ("down to", "broken down").
CONTEXT_LOSS = re.compile(
    r"\b(loss|losses|decline[ds]?|decrease[ds]?|miss(?:ed)?|negative|fell|drop(?:ped)?|shortfall)\b",
    re.IGNORECASE,
)
LOSS_PHRASE = re.compile(
    r"(?:loss(?:es)?|decline|decrease|shortfall|drop)\s+of\s+(?:\*\*)?$",
    re.IGNORECASE,
)


@dataclass
class Quantity:
    low: float  # equal to high for a point
    high: float
    kind: str  # point | range | lower | upper
    step: float  # absolute precision of the stated figure
    hedged: bool
    unit: str  # "", "%", "x"
    scaled: bool  # scale written or implied (B, million, ...)
    currency: str
    neg_word: bool = False  # unsigned figure described as a loss, decline, miss...
    round_step: float = 0.0  # coarser precision a whole number with trailing zeros may carry
    bps: bool = False  # written in basis points (stored as percentage points)
    year_range: bool = False  # only calendar years ("2022 to 2024"): a period, not a quantity


@dataclass
class _Num:
    value: float  # unsigned, in base units
    step: float
    unit: str
    scale: float
    scale_written: bool
    currency: str
    signed: bool  # minus sign or parentheses


def _read(m: re.Match, hint: float | None) -> _Num:
    text = m["num"].replace(",", "")
    decimals = len(text.split(".")[1]) if "." in text else 0
    word = (m["scale"] or "").lower()
    scale = SCALES.get(word) or hint or 1.0
    value, step, unit = float(text), 10.0**-decimals, ""
    u = (m["unit"] or "").lower()
    if u.startswith("b"):  # bps / basis points -> percentage points
        value, step, unit = value / 100, step / 100, "%"
    elif u:
        unit = "x" if u == "x" else "%"
    cur = (m["cur"] or "").upper()
    cur = {"US$": "$", "USD": "$", "NTD": "NT$"}.get(cur, cur)
    return _Num(
        value * scale,
        step * scale,
        unit,
        scale,
        bool(word) or bool(hint),
        cur,
        bool(m["sign"]) or bool(m["sign2"]),
    )


def parse(span: str | None, scale_hint: str | None = None) -> Quantity | None:
    """Parse a short span holding one figure, a range, or a bound."""
    if not span:
        return None
    # Typographic minus signs: hyphen variants always, an en dash only when it
    # leads a number (not between two numbers, where it joins a range).
    span = span.replace("\u2010", "-").replace("\u2011", "-")
    # LaTeX escapes from math-formatted answers: "22.62\%", "\$1.2B", "14{,}060".
    span = re.sub(r"\\([%$])", r"\1", span).replace("{,}", ",")
    span = re.sub(r"(?<![\d.])\u2013(?=\s?[$€£¥]?\d)", "-", span)
    # A worked expression ("(2,168 + 2,128) / 2 = 2,148") states its figure after the last "=".
    if "=" in span:
        result = span.rsplit("=", 1)[1]
        if re.search(r"\d", result):
            span = result
    hint_word = (
        scale_hint.strip().lower().split()[-1]
        if scale_hint and scale_hint.strip()
        else ""
    )
    hint = SCALES.get(hint_word)
    if (
        hint_word in ("percent", "%")
        and "%" not in span
        and "percent" not in span.lower()
    ):
        span += "%"
    found = [m for m in NUMBER.finditer(span) if m["num"]]
    found = [m for m in found if not _is_label(span, m)] or found
    if not found:
        return None
    first = _read(found[0], hint)
    nums, kind = [first], "point"
    if len(found) > 1:
        second, m1 = _read(found[1], hint), found[1]
        gap = span[found[0].end() : m1.start()]
        dash = m1["sign"] in ("-", "−") and gap.strip() == ""
        if RANGE_JOIN.match(gap) and (gap.strip() or dash):
            if dash:
                second.signed = False
            if not found[0]["scale"] and found[1]["scale"]:  # "$6.8 to $7.4 billion"
                first.value *= second.scale / first.scale
                first.step *= second.scale / first.scale
                first.scale_written = True
            nums, kind = [first, second], "range"
    values = [-n.value if n.signed else n.value for n in nums]
    hedged = bool(HEDGE.search(span))
    if kind == "point" and LOWER.search(span):
        kind = "lower"
    elif kind == "point" and UPPER.search(span):
        kind = "upper"
    step = max(n.step for n in nums)
    if hedged and kind != "range" and "." not in found[0]["num"]:
        step = max(step, _last_digit(found[0]["num"]) * first.scale)
    # A whole number ending in three or more zeros ("85,945,000") may be rounded to that place.
    last = _last_digit(found[0]["num"]) if "." not in found[0]["num"] else 1.0
    round_step = last * first.scale if kind == "point" and last >= 1000 else 0.0
    return Quantity(
        min(values),
        max(values),
        kind,
        step,
        hedged,
        first.unit or nums[-1].unit,
        any(n.scale_written for n in nums),
        first.currency or nums[-1].currency,
        kind == "point" and not first.signed and bool(NEG_WORD.search(span)),
        round_step,
        any((m["unit"] or "").lower().startswith("b") for m in found[: len(nums)]),
        kind == "range"
        and all(
            "." not in m["num"] and "," not in m["num"] and 1900 <= float(m["num"]) <= 2100
            and not (m["unit"] or m["scale"] or m["cur"])
            for m in found[:2]
        ),
    )


def _is_label(span: str, m: re.Match) -> bool:
    text = m["num"]
    start = m.start("num")
    if start > 0 and span[start - 1].isalpha() and not m["cur"]:
        return True  # Q1, H2, FY24 (a letter right before the digits, not "to 5")
    if m["cur"] or m["unit"] or m["scale"] or "." in text or "," in text:
        return False
    if not (len(text) == 4 and 1900 <= int(text) <= 2100):
        return False
    before = span[max(0, m.start() - 4) : m.start()]
    return bool(re.search(r"(FY|Q\d|CY|H\d)\s*$", before, re.IGNORECASE)) or len(
        span.strip()
    ) != len(text)


def _last_digit(num: str) -> float:
    digits = num.replace(",", "").split(".")[0]
    zeros = len(digits) - len(digits.rstrip("0"))
    return 10.0**zeros if zeros < len(digits) else 1.0


def _align(gold: Quantity, ans: Quantity) -> float:
    """Factor to multiply the answer by when one side has no stated scale."""
    if gold.scaled == ans.scaled or gold.unit == "%" or ans.unit == "%":
        return 1.0
    g, a = abs(gold.high) or 1.0, abs(ans.high) or 1.0
    candidates = [10.0**k for k in range(-12, 13, 3)]
    return min(candidates, key=lambda f: abs(math.log10(a * f / g)))


def _as_percent(q: Quantity) -> Quantity:
    if q.unit == "%":
        return q
    return Quantity(
        q.low * 100,
        q.high * 100,
        q.kind,
        q.step * 100,
        q.hedged,
        "%",
        q.scaled,
        q.currency,
        q.neg_word,
        q.round_step * 100,
    )


def _close(a: float, g: float, a_step: float, g_step: float, hedged: bool) -> bool:
    eps = 1e-9 * max(abs(g), 1.0)
    if a_step <= g_step * (1 + 1e-9):  # answer at least as precise as the gold
        return abs(a - g) <= g_step / 2 + eps
    rel = abs(a - g) / abs(g) if g else abs(a - g)
    limit = HEDGE_REL if hedged else ROUNDING_REL
    # A coarser figure must round the gold unambiguously: $3.3B is not accepted
    # for $3.25B, since it could equally be a different value such as $3.30B.
    return abs(a - g) < a_step / 2 - eps and rel <= limit + 1e-12


def compare(gold: Quantity, ans: Quantity) -> tuple[bool, str]:
    """True if the answer figure states the gold figure without misleading."""
    if gold.unit and ans.unit and gold.unit != ans.unit:
        return False, f"unit {ans.unit} vs gold {gold.unit}"
    if gold.currency and ans.currency and gold.currency != ans.currency:
        return False, f"currency {ans.currency} vs gold {gold.currency}"
    if {gold.unit, ans.unit} == {"", "%"} and not (gold.currency or ans.currency):
        # 0.824 and 82.4% are the same ratio; a bare 8.5 next to a separate "unit %" means 8.5%.
        if not ans.unit and gold.bps:  # a bare 140 next to a separate "unit bps" means 140 bps
            ok, why = compare(gold, replace(ans, low=ans.low / 100, high=ans.high / 100, step=ans.step / 100, unit="%"))
            if ok:
                return ok, why
        if not ans.unit:
            as_points = replace(ans, unit="%")
            ok, why = compare(gold, as_points)
            if ok:
                return ok, why
        gold = _as_percent(gold)
        ans = _as_percent(ans)
    f = _align(gold, ans)
    lo, hi, step = ans.low * f, ans.high * f, ans.step * f
    if gold.kind == "range":
        if ans.kind != "range":
            return False, "gold is a range; answer is not"
        ok = _close(lo, gold.low, step, gold.step, ans.hedged) and _close(
            hi, gold.high, step, gold.step, ans.hedged
        )
        return ok, "range endpoints match" if ok else "range endpoints differ"
    if gold.kind in ("lower", "upper"):
        inside = (
            lo >= gold.low - gold.step / 2
            if gold.kind == "lower"
            else hi <= gold.high + gold.step / 2
        )
        same = ans.kind == gold.kind and _close(
            lo, gold.low, step, gold.step, ans.hedged
        )
        ok = (ans.kind == "point" and inside) or same
        return ok, "satisfies gold bound" if ok else "does not satisfy gold bound"
    g = gold.low
    if (g < 0 and ans.neg_word) or (
        lo < 0 and gold.neg_word
    ):  # "-1.2%" vs "missed by 1.2%"
        g, lo, hi = abs(g), abs(lo), abs(hi)
    if ans.kind == "point":
        if (
            lo != 0
            and g != 0
            and (lo < 0) != (g < 0)
            and _close(abs(lo), abs(g), step, gold.step, ans.hedged)
        ):
            return False, "sign differs"
        ok = _close(lo, g, step, gold.step, ans.hedged) or (
            ans.round_step > step
            and _close(lo, g, ans.round_step * f, gold.step, ans.hedged)
        )
        return (
            ok,
            "matches at gold precision" if ok else f"{_fmt(lo)} vs gold {_fmt(g)}",
        )
    if ans.kind == "range":
        inside = lo - gold.step / 2 <= g <= hi + gold.step / 2
        tight = (hi - lo) <= RANGE_REL * abs(g)
        return inside and tight, "range contains gold" if inside and tight else (
            "range too wide" if inside else "range misses gold"
        )
    bound = lo
    inside = g >= bound - step / 2 if ans.kind == "lower" else g <= bound + step / 2
    tight = abs(g - bound) <= BOUND_REL * abs(g) + step / 2
    return inside and tight, "bound contains gold" if inside and tight else (
        "bound too loose" if inside else "bound excludes gold"
    )


def _fmt(x: float) -> str:
    return f"{x:,.6g}"


def _gold_is_loss(gold: Quantity, label: str = "") -> bool:
    """True when the gold figure is a signed loss, or the check label describes one."""
    if gold.low < 0 or gold.neg_word:
        return True
    return bool(label) and bool(CONTEXT_LOSS.search(label)) and gold.kind == "point"


def _loss_span_in_text(span: str, text: str) -> str | None:
    """A parenthetical or 'loss of ...' wording in text that wraps this span."""
    idx = 0
    while True:
        i = text.find(span, idx)
        if i < 0:
            return None
        j = i
        while j > 0 and text[j - 1] in " \t":
            j -= 1
        if j > 0 and text[j - 1] == "(":
            k = i + len(span)
            while k < len(text) and text[k] in " \t":
                k += 1
            if k < len(text) and text[k] == ")":
                cand = text[j - 1 : k + 1]
                parsed = parse(cand)
                if parsed is not None and (parsed.low < 0 or parsed.neg_word):
                    return cand
        prefix = text[max(0, i - 48) : i]
        m = LOSS_PHRASE.search(prefix)
        if m:
            cand = text[i - (len(prefix) - m.start()) : i + len(span)]
            parsed = parse(cand)
            if parsed is not None and (parsed.low < 0 or parsed.neg_word):
                return cand
        idx = i + 1


def with_loss_context(span: str, text: str, gold: Quantity, label: str = "") -> str:
    """Prefer a parenthetical or 'loss of' span when the gold (or check) is a loss."""
    if not span or not _gold_is_loss(gold, label):
        return span
    ans = parse(span)
    if ans is None or ans.low < 0 or ans.neg_word:
        return span
    return _loss_span_in_text(span, text) or span


def surrounding_loss(span: str, text: str, gold: Quantity, label: str = "") -> bool:
    """True when text around this span describes it as a loss, decline or shortfall."""
    if not span or not text or not _gold_is_loss(gold, label):
        return False
    start = 0
    while True:
        i = text.find(span, start)
        if i < 0:
            return False
        window = text[max(0, i - 80) : i + len(span) + 20]
        if CONTEXT_LOSS.search(window):
            return True
        start = i + 1


def grade_check(
    operator: str,
    quantities: list[dict],
    text: str = "",
    label: str = "",
) -> tuple[str, list[dict]]:
    """Grade one rubric check from extracted spans. Returns (verdict, details).

    Each quantity carries the span(s) where the answer commits to its value;
    it matches if one of them states the gold figure. Correctness:
    "met" if all match, "not met" if any stated figure misses, "not found" if
    nothing misses but some figure is absent (left to the judge, which can see
    equivalent forms such as a growth rate from a stated base). Contradiction:
    "triggered" if a stated figure misses, else "not triggered".
    """
    details, verdicts = [], []
    for q in quantities:
        gold = parse(q.get("gold"), q.get("gold_scale"))
        if gold is None or gold.year_range:  # a period such as "2022 to 2024" is left to the judge
            continue
        hint = label or q.get("label") or ""
        spans = q.get("answers") or []
        parsed: list[tuple[str, Quantity | None]] = []
        for span in spans:
            used = with_loss_context(span, text, gold, hint)
            ans = parse(used, q.get("answer_scale"))
            if (
                ans is not None
                and ans.low >= 0
                and not ans.neg_word
                and surrounding_loss(used, text, gold, hint)
            ):
                ans.neg_word = True
            parsed.append((used, ans))
        results = [
            (span, *compare(gold, ans)) for span, ans in parsed if ans is not None
        ]
        if not results:
            ok, why, span = None, "not stated in answer", None
        else:
            span, ok, why = next((r for r in results if r[1]), results[-1])
        verdicts.append(ok)
        details.append({"gold": q.get("gold"), "answer": span, "ok": ok, "why": why})
    if not verdicts:
        return "not numeric", details
    if operator == "contradiction":
        return ("triggered" if False in verdicts else "not triggered"), details
    if False in verdicts:
        return "not met", details
    return ("met" if all(verdicts) else "not found"), details


EXTRACT_PROMPT = """You locate numbers in text. You do not judge correctness.

For each rubric check below, list the numeric quantities it asserts (money, counts,
percentages, basis points, ratios, multiples, per-share values, share counts).
Ignore dates, years, quarter names and fiscal-period labels; those are not quantities.
For each quantity return:
- "label": short name of what the number measures (include the period).
- "gold": the shortest verbatim span from the check text (for contradiction checks,
  from the official answer) holding the figure, including its currency, scale, unit,
  sign or parentheses, range ("X to Y") and bound words ("over", "up to").
- "gold_scale": the scale or unit word ("thousand", "million", "billion", "cents",
  "percent") only if it is implied by context (a table header, the question) rather
  than written next to the gold figure; else null.
- "answers": the shortest verbatim span(s) from the MODEL ANSWER where it commits to
  its own value for this same quantity (same entity, period and measure), including
  hedge words ("about", "~"), bound words ("or more", "at least"), range wording,
  currency, scale, unit, and the sign: parentheses, a minus, or a sign word that
  makes the number negative ("loss of", "decline of", "shortfall of", "missed by").
  If the gold figure is a signed loss, or the check is about a loss, copy a signed
  span (for example "($149.7)" or "loss of $149.7M"), not a bare positive amount
  taken out of that wording. Use the value the answer presents as its answer (its
  headline or final figure), even if it was computed with different inputs (another
  exchange rate, another base). Do not use figures it gives only as alternatives
  under another method, as earlier or superseded versions, or as parts of a
  different total. Usually one span; list more only if it repeats the committed
  figure. [] if it states no value for this quantity.
  Read the official answer to see exactly what the gold figure measures (e.g. a
  shortfall versus the guidance midpoint, not the low end; a midpoint, not the
  range) and pick the answer's figure for that same measure, even when the
  answer's figure differs from the gold. If the gold is a single figure and the
  answer gives both a range and its own single figure (e.g. a midpoint), use the
  single figure.
- "answer_scale": like gold_scale, for the answer spans.
Also return "non_numeric_claim": true if the check also asserts something that is not
a number (a direction like "beat", a reason, a ranking), else false.

Copy spans exactly; do not compute, convert or round anything.
Call the record tool once, with one entry per rubric check.

QUESTION:
{question}

OFFICIAL ANSWER:
{gold_answer}

RUBRIC CHECKS:
{checks}

MODEL ANSWER:
{model_answer}
"""

_SPAN = {"type": ["string", "null"]}
RECORD_TOOL = {
    "name": "record",
    "description": "Record the located spans for every rubric check.",
    "input_schema": {
        "type": "object",
        "required": ["checks"],
        "properties": {
            "checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["check_id", "quantities", "non_numeric_claim"],
                    "properties": {
                        "check_id": {"type": "integer"},
                        "non_numeric_claim": {"type": "boolean"},
                        "quantities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["label", "gold", "answers"],
                                "properties": {
                                    "label": {"type": "string"},
                                    "gold": {"type": "string"},
                                    "gold_scale": _SPAN,
                                    "answers": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "answer_scale": _SPAN,
                                },
                            },
                        },
                    },
                },
            }
        },
    },
}
RECORD_FUNCTION = {
    "type": "function",
    "function": {
        "name": RECORD_TOOL["name"],
        "description": RECORD_TOOL["description"],
        "parameters": RECORD_TOOL["input_schema"],
    },
}


def extract(
    question: str,
    gold_answer: str,
    checks: list[dict],
    model_answer: str,
    model: str | None = None,
) -> tuple[dict, float]:
    """One LLM call per question; returns ({check_id: extraction}, cost_usd)."""
    from agent import llm

    listing = "\n".join(
        f"{c['check_id']}. [{c['operator']}] {c['criteria']}" for c in checks
    )
    prompt = (
        EXTRACT_PROMPT.replace("{question}", question)
        .replace("{gold_answer}", gold_answer)
        .replace("{checks}", listing)
        .replace("{model_answer}", model_answer)
    )
    cost = 0.0
    for attempt in range(3):  # malformed tool-call JSON is rare and not repeatable; ask again
        out = llm.chat(
            model or llm.VERIFIER_MODEL,
            [{"role": "user", "content": prompt}],
            max_tokens=16000,
            thinking=False,
            temperature=0,
            tools=[RECORD_FUNCTION],
            tool_choice={"type": "function", "function": {"name": RECORD_TOOL["name"]}},
        )
        cost += out["cost_usd"]
        calls = llm.message_of(out["response"]).get("tool_calls") or []
        call = next(c for c in calls if c["function"]["name"] == RECORD_TOOL["name"])
        try:
            data = json.loads(call["function"]["arguments"])
        except json.JSONDecodeError:
            if attempt == 2:
                raise
            continue
        return {int(c["check_id"]): c for c in data["checks"]}, cost
    raise RuntimeError("unreachable")

"""Tool-calling agent loop on an OpenAI-compatible chat completions API.

The model gets the question, the protocol system prompt and three tools. Each
turn it either calls tools (run here, results fed back) or answers. Thinking
is on, and its reasoning is passed back on every turn as the API requires
when tools are present. The last allowed turn disables tools so the model has
to answer.
"""

from __future__ import annotations

import time
from collections import Counter

from agent import llm
from agent.protocol import system_for
from agent.tools import TOOL_SPECS, ToolRunner

MAX_TURNS = 40
MAX_TOKENS = 32000
REASONING_EFFORT = "high"


def assistant_message(message: dict) -> dict:
    """The assistant turn to send back, including reasoning_content and tool_calls."""
    out = {"role": "assistant", "content": message.get("content") or ""}
    if message.get("reasoning_content"):
        out["reasoning_content"] = message["reasoning_content"]
    if message.get("tool_calls"):
        out["tool_calls"] = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["function"]["name"],
                    "arguments": tc["function"].get("arguments") or "{}",
                },
            }
            for tc in message["tool_calls"]
        ]
    return out


def run_agent(
    question: str,
    *,
    model: str = llm.AGENT_MODEL,
    tools: ToolRunner | None = None,
    max_turns: int = MAX_TURNS,
    max_tokens: int = MAX_TOKENS,
    chat=llm.chat,
) -> dict:
    started = time.perf_counter()
    runner = tools or ToolRunner()
    messages: list[dict] = [
        {"role": "system", "content": system_for(question)},
        {"role": "user", "content": question},
    ]
    turns: list[dict] = []
    usage_tot: Counter = Counter()
    model_cost = 0.0
    text = ""
    stop = None
    try:
        for turn in range(1, max_turns + 1):
            last = turn == max_turns
            out = chat(
                model,
                messages,
                tools=TOOL_SPECS,
                tool_choice="none" if last else "auto",
                thinking=True,
                reasoning_effort=REASONING_EFFORT,
                max_tokens=max_tokens,
            )
            response = out["response"]
            message = llm.message_of(response)
            stop = llm.finish_reason(response)
            model_cost += out["cost_usd"]
            usage_tot.update(out["usage"])
            calls = message.get("tool_calls") or []
            log = {
                "turn": turn,
                "reported_model": out["reported_model"],
                "system_fingerprint": out.get("system_fingerprint"),
                "finish_reason": stop,
                "usage": out["usage"],
                "cost_usd": out["cost_usd"],
                "peak": out["peak"],
                "attempts": out["attempts"],
                "content": message.get("content") or "",
                "reasoning_chars": len(message.get("reasoning_content") or ""),
                "tool_calls": [],
            }
            turns.append(log)
            messages.append(assistant_message(message))
            if stop == "length":
                raise RuntimeError("agent response truncated at max_tokens")
            if not calls:
                text = (message.get("content") or "").strip()
                break
            for tc in calls:
                name = tc["function"]["name"]
                result = runner.call(name, tc["function"].get("arguments") or "{}")
                # The full tool output goes into the trace so leak scans can read it.
                log["tool_calls"].append(
                    {**runner.log[-1], "result_chars": len(result), "result": result}
                )
                messages.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": result}
                )
        else:
            raise RuntimeError("agent exceeded the turn limit")
    finally:
        runner.close()
    if not text:
        raise RuntimeError("agent returned no text answer")
    tool_counts = Counter(e["name"] for e in runner.log)
    tool_cost = runner.cost["exa"] + runner.cost["e2b"]
    return {
        "model_answer": text,
        "stop_reason": stop,
        "reported_models": sorted({t["reported_model"] or "" for t in turns}),
        "tokens": dict(usage_tot),
        "model_cost_usd": model_cost,
        "tool_cost_usd": {k: round(v, 6) for k, v in runner.cost.items()},
        "cost_usd": model_cost + tool_cost,
        "latency_s": time.perf_counter() - started,
        "tool_calls": {"total": len(runner.log), **dict(tool_counts)},
        "n_tool_calls": len(runner.log),
        "n_refused": sum(1 for e in runner.log if e.get("refused")),
        "n_turns": len(turns),
        "turns": turns,
    }

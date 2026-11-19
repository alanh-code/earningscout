"""Provider config and a single chat-completions call used by the agent, the judge and the verifier.

Every model is reached through an OpenAI-compatible chat completions endpoint.
Model names, prices and peak hours live here, so swapping a model is a config
change, not a code change. Keys are read from the repo's `.env` (or the
environment) and are never printed or logged.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from agent.protocol import SEED

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    key_env: str
    # Weekday UTC hour ranges [start, end) billed at the peak rate.
    peak_hours_utc: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class Model:
    name: str
    provider: str
    version: str
    # USD per million tokens at the off-peak rate.
    cache_hit: float
    cache_miss: float
    output: float
    peak_multiplier: float = 1.0
    thinking_param: bool = True
    notes: dict = field(default_factory=dict)


PROVIDERS = {
    "deepseek": Provider(
        name="deepseek",
        base_url="https://api.deepseek.com",
        key_env="DEEPSEEK_API_KEY",
        peak_hours_utc=((1, 4), (6, 10)),
    ),
}

# List prices from the DeepSeek pricing page; peak is twice off-peak.
MODELS = {
    "deepseek-flash": Model(
        name="deepseek-flash",
        provider="deepseek",
        version="DeepSeek-V4.1-Flash",
        cache_hit=0.003,
        cache_miss=0.15,
        output=0.60,
        peak_multiplier=2.0,
    ),
    "deepseek-v4-pro": Model(
        name="deepseek-v4-pro",
        provider="deepseek",
        version="DeepSeek-V4-Pro",
        cache_hit=0.022,
        cache_miss=0.66,
        output=1.98,
        peak_multiplier=2.0,
    ),
}

AGENT_MODEL = "deepseek-flash"
JUDGE_MODEL = "deepseek-v4-pro"
VERIFIER_MODEL = "deepseek-flash"

RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}
# Response fields that carry a wall-clock time or a per-request id; dropped before saving.
VOLATILE_FIELDS = ("created", "id")


class PeakHours(RuntimeError):
    """Raised before a paid call when the provider is in peak hours and peak use is not allowed."""


# Set by runners from --allow-peak. When False, send() makes no call during peak hours.
ALLOW_PEAK = False


class OutOfCredit(RuntimeError):
    """The provider refused the call for billing reasons. Never retried."""


def env_key(name: str) -> str:
    """Read a key from `.env`, then the environment. The value is never printed."""
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith(name + "="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    value = os.environ.get(name, "")
    if not value:
        sys.exit(f"{name} is not set in .env")
    return value


def model_config(name: str) -> Model:
    if name not in MODELS:
        sys.exit(f"no provider config for model {name!r}; add it to agent/llm.py")
    return MODELS[name]


def provider_for(name: str) -> Provider:
    return PROVIDERS[model_config(name).provider]


def is_peak(provider: Provider, now: datetime | None = None) -> bool:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    if now.weekday() >= 5:
        return False
    return any(start <= now.hour < end for start, end in provider.peak_hours_utc)


def require_off_peak(model_names: list[str], allow_peak: bool = False) -> None:
    """Refuse to start a run during a provider's peak hours unless allowed.

    Also sets ALLOW_PEAK, so send() keeps refusing paid calls if a run reaches peak hours."""
    global ALLOW_PEAK
    ALLOW_PEAK = allow_peak
    if allow_peak:
        return
    for name in model_names:
        provider = provider_for(name)
        if is_peak(provider):
            sys.exit(
                f"{provider.name} is in peak hours (weekdays "
                + ", ".join(
                    f"{a:02d}:00-{b:02d}:00" for a, b in provider.peak_hours_utc
                )
                + " UTC). Rerun off-peak or pass --allow-peak."
            )


def prices(name: str, peak: bool = False) -> dict:
    m = model_config(name)
    k = m.peak_multiplier if peak else 1.0
    return {
        "cache_hit": m.cache_hit * k,
        "cache_miss": m.cache_miss * k,
        "output": m.output * k,
    }


def normalize_usage(usage: dict | None) -> dict:
    usage = usage or {}
    prompt = int(usage.get("prompt_tokens") or 0)
    hit = int(usage.get("prompt_cache_hit_tokens") or 0)
    if not hit:
        hit = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    miss = usage.get("prompt_cache_miss_tokens")
    miss = int(miss) if miss is not None else max(prompt - hit, 0)
    details = usage.get("completion_tokens_details") or {}
    return {
        "input_tokens": prompt,
        "output_tokens": int(usage.get("completion_tokens") or 0),
        "cache_hit_tokens": hit,
        "cache_miss_tokens": miss,
        "reasoning_tokens": int(details.get("reasoning_tokens") or 0),
    }


def cost_usd(name: str, usage: dict, peak: bool = False) -> float:
    """Cost of one response from its normalized usage."""
    p = prices(name, peak)
    return (
        usage.get("cache_hit_tokens", 0) / 1e6 * p["cache_hit"]
        + usage.get("cache_miss_tokens", 0) / 1e6 * p["cache_miss"]
        + usage.get("output_tokens", 0) / 1e6 * p["output"]
    )


def price_caption(name: str) -> str:
    p = prices(name)
    return (
        f"${p['cache_miss']:.3f}/${p['output']:.2f} per million input/output tokens, "
        f"cached input ${p['cache_hit']:.3f}/M ({name} off-peak list price; peak is "
        f"{model_config(name).peak_multiplier:g}x)"
    )


_CLIENTS: dict[str, object] = {}


def client_for(name: str):
    provider = provider_for(name)
    if provider.name not in _CLIENTS:
        from openai import OpenAI

        # Explicit key and URL, so nothing from the surrounding shell changes where calls go.
        _CLIENTS[provider.name] = OpenAI(
            api_key=env_key(provider.key_env),
            base_url=provider.base_url,
            max_retries=0,
            timeout=600,
        )
    return _CLIENTS[provider.name]


def list_models(name: str) -> list[str]:
    return [m.id for m in client_for(name).models.list()]


def resolve_model(name: str) -> str:
    """Confirm the model id is served by the provider's /models endpoint."""
    model_config(name)
    served = list_models(name)
    if name not in served:
        sys.exit(f"model {name!r} is not in the provider model list {served}")
    return name


def sanitize(response: dict) -> dict:
    return {k: v for k, v in response.items() if k not in VOLATILE_FIELDS}


def build_request(
    name: str,
    messages: list[dict],
    *,
    max_tokens: int,
    thinking: bool,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    temperature: float | None = None,
    seed: int | None = SEED,
    reasoning_effort: str | None = None,
) -> dict:
    request: dict = {"model": name, "messages": messages, "max_tokens": max_tokens}
    if model_config(name).thinking_param:
        request["thinking"] = {"type": "enabled" if thinking else "disabled"}
    if thinking and reasoning_effort:
        request["reasoning_effort"] = reasoning_effort
    # Thinking mode ignores temperature, so only send it when it takes effect.
    if temperature is not None and not thinking:
        request["temperature"] = temperature
    if seed is not None:
        request["seed"] = seed
    if tools:
        request["tools"] = tools
    if tool_choice is not None:
        request["tool_choice"] = tool_choice
    return request


def send(request: dict, retries: int = 6, base_delay: float = 2.0) -> dict:
    """POST one chat completion with retries on rate limits, server errors and timeouts.

    Returns {"response", "usage", "cost_usd", "peak", "reported_model", "attempts"}.
    """
    import openai

    name = request["model"]
    provider = provider_for(name)
    client = client_for(name)
    body = dict(request)
    extra = {}
    for key in ("thinking",):
        if key in body:
            extra[key] = body.pop(key)
    delay = base_delay
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        if not ALLOW_PEAK and is_peak(provider):
            raise PeakHours(
                f"{provider.name} is in peak hours; paused before a paid call (resume off-peak)"
            )
        try:
            raw = client.chat.completions.create(**body, extra_body=extra or None)
            response = raw.model_dump(mode="json", exclude_none=True)
            usage = normalize_usage(response.get("usage"))
            peak = is_peak(provider)
            return {
                "response": sanitize(response),
                "usage": usage,
                "cost_usd": cost_usd(name, usage, peak),
                "peak": peak,
                "reported_model": response.get("model"),
                "system_fingerprint": response.get("system_fingerprint"),
                "attempts": attempt,
            }
        except openai.APIStatusError as exc:
            status = getattr(exc, "status_code", None)
            if status == 402:
                raise OutOfCredit(
                    f"{provider.name} refused the call (402): add credit"
                ) from exc
            if status not in RETRY_STATUS:
                raise
            last_exc = exc
        except (openai.APIConnectionError, openai.APITimeoutError) as exc:
            last_exc = exc
        if attempt == retries:
            break
        print(
            f"{name}: transient error, retry {attempt}/{retries - 1} in {delay:.0f}s",
            flush=True,
        )
        time.sleep(delay)
        delay = min(delay * 2, 60)
    raise last_exc or RuntimeError("send exited without a response")


def chat(name: str, messages: list[dict], **kwargs) -> dict:
    retries = kwargs.pop("retries", 6)
    request = build_request(name, messages, **kwargs)
    out = send(request, retries=retries)
    out["request"] = request
    return out


def message_of(response: dict) -> dict:
    choices = response.get("choices") or [{}]
    return choices[0].get("message") or {}


def finish_reason(response: dict) -> str | None:
    choices = response.get("choices") or [{}]
    return choices[0].get("finish_reason")


def response_text(response: dict) -> str:
    """Final answer text from a chat-completions response or a legacy Messages response."""
    if "choices" in response:
        return (message_of(response).get("content") or "").strip()
    return "".join(
        b.get("text") or ""
        for b in response.get("content", [])
        if isinstance(b, dict) and b.get("type") == "text"
    )


CLOSED_FIELDS = {"model", "max_tokens", "thinking", "temperature", "seed", "messages"}


def closed_violations(
    request: dict, response: dict, model: str | None = None
) -> list[str]:
    """Closed-environment checks for a no-tools recall request and its response.

    The request must be one plain user message with no tools, no system prompt
    and thinking off; the response must be one plain text answer that ended
    normally and was served by the requested model.
    """
    problems = []
    extra = set(request) - CLOSED_FIELDS
    if extra:
        problems.append(f"unexpected request fields {sorted(extra)}")
    if (request.get("thinking") or {}).get("type") != "disabled":
        problems.append("thinking is not disabled")
    messages = request.get("messages") or []
    if len(messages) != 1:
        problems.append("request is not a single fresh message")
    first = (messages or [{}])[0]
    if first.get("role") != "user" or not isinstance(first.get("content"), str):
        problems.append("message is not plain user text (or a system prompt was sent)")
    if len(response.get("choices") or []) != 1:
        problems.append("expected exactly one choice")
    reply = message_of(response)
    if reply.get("tool_calls"):
        problems.append("response contains tool calls")
    if reply.get("reasoning_content"):
        problems.append("response contains thinking output")
    if not (reply.get("content") or "").strip():
        problems.append("response has no text")
    if finish_reason(response) != "stop":
        problems.append(f"finish_reason {finish_reason(response)}")
    want = model or request.get("model")
    if response.get("model") != want:
        problems.append(f"answered by {response.get('model')}")
    return problems

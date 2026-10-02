"""
The one place FitFindr talks to the model.

Two of your three tools call out to a service. Everything that does goes
through `generate()` below.

That matters more in unit 3 than it did in unit 1, because an agent run is
several requests rather than one. A student iterating on a loop will cross the
per-minute limit within a few minutes. Rather than three hundred people each
writing their own pacing code, the pacing lives here, once.

What this does for you:

  • Paces requests so you stay under the per-minute limit, and says when it's
    waiting. A pause is the limiter doing its job, not a hang.
  • Reuses answers to prompts already sent, while you're building. Turned off
    for evaluation runs.
  • Stops if a session makes an unreasonable number of calls, rather than
    silently draining your day's allowance. A runaway agent loop is the
    classic way to do that.
  • Retries when the service says you're going too fast.
  • Returns a readable message when the model can't be reached, instead of a
    stack trace. Unit 4 Milestone 2 has you trigger exactly that on purpose.
  • Counts your calls and the tokens they used, so quota — and cost — are
    numbers you can see rather than numbers you multiply off a pricing page.

The model name and the temperature live in config.py, not here.
"""

import hashlib
import json
import os
import re
import sys
import time

import config

_call_times: list[float] = []
_session_calls = 0
_cache_hits = 0
_prompt_tokens = 0
_output_tokens = 0
_client = None
_budget_warned = False


class QuotaGuard(Exception):
    """Raised when a session blows through its request budget."""


class ModelUnavailable(Exception):
    """
    Raised when the model can't be reached at all — a bad key, no network, a
    model name that doesn't resolve.

    This exists so your agent can catch one specific thing and say something
    useful, instead of showing a user a stack trace. Unit 4 Milestone 2 has you
    trigger it deliberately by changing one character of your key.
    """


# ─── Cache ───────────────────────────────────────────────────────────────────


def _cache_key(prompt: str, system: str | None, temperature: float) -> str:
    blob = json.dumps(
        [config.MODEL, system or "", prompt, temperature], sort_keys=True
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _cache_read(key: str) -> str | None:
    path = config.CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))["response"]
    except Exception:
        return None


def _cache_write(key: str, response: str) -> None:
    config.CACHE_DIR.mkdir(exist_ok=True)
    path = config.CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps({"response": response}), encoding="utf-8")


def clear_cache() -> int:
    """Delete every cached response. Returns how many were removed."""
    if not config.CACHE_DIR.exists():
        return 0
    files = list(config.CACHE_DIR.glob("*.json"))
    for f in files:
        f.unlink()
    return len(files)


# ─── Pacing and guards ───────────────────────────────────────────────────────


def _wait_for_slot() -> None:
    """Sleep, if we've used up this minute's allowance."""
    now = time.monotonic()
    _call_times[:] = [t for t in _call_times if now - t < 60.0]

    if len(_call_times) < config.REQUESTS_PER_MINUTE:
        return

    sleep_for = 60.0 - (now - _call_times[0]) + 0.1
    if sleep_for > 0:
        # Only worth announcing if it's long enough to notice. Otherwise the
        # message reads "Waiting 0s", which looks like something went wrong.
        if sleep_for >= 1.0:
            print(
                f"  [rate limit] {config.REQUESTS_PER_MINUTE} requests used this "
                f"minute. Waiting {sleep_for:.0f}s. This is normal.",
                file=sys.stderr,
                flush=True,
            )
        time.sleep(sleep_for)
        _call_times[:] = [t for t in _call_times if time.monotonic() - t < 60.0]


def _check_budget() -> None:
    global _budget_warned
    if _session_calls < config.SESSION_REQUEST_BUDGET:
        return
    if not _budget_warned:
        _budget_warned = True
    raise QuotaGuard(
        f"This session has made {_session_calls} requests, which is the "
        f"budget set in config.py (SESSION_REQUEST_BUDGET).\n"
        f"That usually means a loop is running away rather than that you've "
        f"done {_session_calls} requests' worth of real work.\n"
        f"Stop the program and look for the loop. If you really do need more, "
        f"raise the number in config.py — but look first."
    )


def usage() -> str:
    """One line on what this session has spent. Printed by app.py on exit."""
    tokens = ""
    if _prompt_tokens or _output_tokens:
        tokens = (
            f", {_prompt_tokens} prompt + {_output_tokens} output tokens"
        )
    return (
        f"{_session_calls} model calls this session"
        f"{f', {_cache_hits} served from cache' if _cache_hits else ''}"
        f"{tokens}"
    )


def call_count() -> int:
    return _session_calls


def token_counts() -> dict:
    """
    What this session actually spent, in tokens, as reported by the service.

    Here's why this exists: a number off the pricing page is an estimate of
    what a run like yours might cost. This is what your run did cost. When you
    write down the cost of one agent run, take it from here.

    Cached answers cost nothing and so add nothing — if you want the real
    per-run numbers, run with the cache off.
    """
    return {
        "prompt": _prompt_tokens,
        "output": _output_tokens,
        "total": _prompt_tokens + _output_tokens,
    }


def _record_tokens(response) -> None:
    """
    Add one response's token counts to the session total.

    The service reports them on `response.usage_metadata`. It is allowed to
    report nothing, or half of it — and a missing count is never a good enough
    reason to kill a run that already succeeded, so anything unexpected here is
    dropped rather than raised.
    """
    global _prompt_tokens, _output_tokens
    try:
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return
        prompt = getattr(meta, "prompt_token_count", None)
        output = getattr(meta, "candidates_token_count", None)
        if isinstance(prompt, int):
            _prompt_tokens += prompt
        if isinstance(output, int):
            _output_tokens += output
    except Exception:  # noqa: BLE001 — counting must never break a working call
        pass


# ─── The call ────────────────────────────────────────────────────────────────


def _explain(exc: Exception) -> str:
    """Turn a provider exception into something a person can act on."""
    message = str(exc).lower()
    if "api key" in message or "api_key" in message or "unauthenticated" in message:
        return (
            "The model rejected your API key. Check GEMINI_API_KEY in your .env "
            "file, or create a fresh key at aistudio.google.com."
        )
    if "not found" in message or "404" in message:
        return (
            f"The model name '{config.MODEL}' did not resolve. If you changed "
            f"AI201_MODEL in your .env, put it back. Otherwise post in the help "
            f"channel — this is not something you caused."
        )
    if "connection" in message or "timeout" in message or "network" in message:
        return "Couldn't reach the model. Check your internet connection and try again."
    return f"Couldn't reach the model: {exc}"


def _retry_delay(exc: Exception, attempt: int) -> float:
    """
    How long to wait before retrying a call the service pushed back on.

    When you cross the per-minute limit, the service usually says how long it
    wants you to wait — "Please retry in 29.7s", or a retryDelay field. Honour
    that, because the limit is per *minute* and a 1-2-4-8 backoff gives up
    about fifteen seconds in, well before the minute is over. That's the
    difference between a run that pauses and a run that dies.

    Falls back to exponential backoff when the service doesn't say.
    """
    text = str(exc)
    match = (
        re.search(r"retry in (\d+(?:\.\d+)?)\s*s", text, re.I)
        or re.search(r"retryDelay['\"]?\s*:\s*['\"](\d+(?:\.\d+)?)s", text)
    )
    hinted = float(match.group(1)) + 1.0 if match else 0.0
    return min(65.0, max(2.0 ** attempt, hinted))


def _get_client():
    global _client
    if _client is None:
        from google import genai

        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError(
                "No GEMINI_API_KEY found.\n"
                "Copy .env.example to .env and paste your key in, then try "
                "again. `python test.py` will confirm it's working."
            )
        _client = genai.Client(api_key=key)
    return _client


def generate(
    prompt: str,
    system: str | None = None,
    cache: bool = True,
    temperature: float | None = None,
) -> str:
    """
    Send a prompt and get text back.

    Args:
        prompt: what you're asking.
        system: an optional instruction about how to behave. This is the
                agent's control surface — when to do what, and what to do with
                nothing. Not a personality setting.
        cache:  reuse an identical earlier answer if there is one. Leave this
                True while building. Pass False when you're evaluating — five
                tries of the same input have to be five real answers.
        temperature: how much the model varies between runs. Defaults to
                config.TEMPERATURE. Pass 0.0 when you want the same answer
                every time.

    Every call in this course goes through here. If you need to change how the
    model is called, change it in this one place.
    """
    global _session_calls, _cache_hits

    use_cache = cache and config.CACHE_ENABLED
    temperature = config.TEMPERATURE if temperature is None else temperature
    key = _cache_key(prompt, system, temperature)

    if use_cache:
        hit = _cache_read(key)
        if hit is not None:
            _cache_hits += 1
            return hit

    _check_budget()

    last_error: Exception | None = None
    for attempt in range(config.MAX_RETRIES):
        _wait_for_slot()
        try:
            client = _get_client()
            _call_times.append(time.monotonic())
            _session_calls += 1

            call_config = {"temperature": temperature}
            if system:
                call_config["system_instruction"] = system
            kwargs = {
                "model": config.MODEL,
                "contents": prompt,
                "config": call_config,
            }

            response = client.models.generate_content(**kwargs)
            _record_tokens(response)
            text = (response.text or "").strip()

            if use_cache:
                _cache_write(key, text)
            return text

        except Exception as exc:  # noqa: BLE001 — surfaced below
            last_error = exc
            message = str(exc).lower()
            rate_limited = (
                "429" in message
                or "resource" in message and "exhaust" in message
                or "rate" in message and "limit" in message
            )
            if not rate_limited:
                raise ModelUnavailable(_explain(exc)) from exc
            backoff = _retry_delay(exc, attempt)
            print(
                f"  [rate limit] service pushed back. Waiting {backoff:.0f}s "
                f"(attempt {attempt + 1} of {config.MAX_RETRIES}). This is "
                f"the limiter doing its job, not a bug.",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(backoff)

    raise RuntimeError(
        f"Still rate limited after {config.MAX_RETRIES} attempts. Wait a "
        f"minute and try again — your key is fine.\nLast error: {last_error}"
    )

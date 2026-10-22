"""The ONE module every AI call goes through (§5 Phase 3 task 1).

Why one module. An AI call is the only thing this project does that is neither free nor
reproducible: it costs money, and two identical inputs can return different answers. So the
rule is the same one `statements_io.py` applies to reading statements — "what is an AI call,
what did it cost, and what did it return" is decided in exactly one place, and every caller
gets the same hashing, caching, logging, spend cap and validation whether it wants them or
not. A module that calls Anthropic directly is a bug.

Four things happen on every call:

  * **Input hash.** sha256 over canonical JSON of everything that could change the answer:
    model, prompt version, effort, max_tokens, output schema, system prompt, user text. Two
    runs that hash the same asked the same question.
  * **Cache.** The raw response lands at `data/raw/anthropic/<task>/<hash>.json` — the same
    convention every collector uses, and `data/raw/` is gitignored, so model output never
    enters the repository. A re-run over unchanged input makes zero calls and spends zero
    dollars. A refusal or an unparseable answer is NOT cached: caching it would make the
    failure permanent.
  * **Audit log.** One JSON line per call in `data/quality/ai-calls/<YYYY-MM>.jsonl`, which
    IS tracked in git, because "everything is checkable" (MISSION §7) has to cover the
    parts of the pipeline a reader cannot reproduce. The line carries hashes, token counts,
    cost and the Anthropic request id — never the API key, never prompt or response text.
    The text is in the cache file the hash names.
  * **Spend cap.** Owner decision 5, 2026-10-09: a hard per-run dollar ceiling from
    `ai.yaml`. When a run reaches it the next call raises `AiCapReached` and the run STOPS;
    it does not finish the batch.

## Concurrency (added 2026-10-22, owner: make the triage run as fast as it can be)

A `Run` may be shared by worker threads. One lock covers everything a call changes: the cap
check and its reservation (one atomic step), the spend true-up, the counters, and the
audit-log append — so the log holds one complete line per call, never two interleaved.
Cache files are written atomically, because two workers can ask the same text at once.

**The cap stays exact with calls in flight.** `call(..., reserve=True)` first reserves an
UPPER BOUND on what the call can cost — input: the UTF-8 byte length of system prompt, user
text and schema plus a fixed framing allowance (a token is never shorter than one byte);
output: the task's `max_tokens`, which also bounds thinking — and refuses the call if
spend plus every in-flight reservation plus this one would pass the cap. The reservation
is released and the measured cost booked when the answer arrives. So N calls in flight
can never carry total spend past the cap; the price is that a run can stop up to N
reservations SHORT of it. Without `reserve`, a call behaves as it always has: refused only
once spend has already reached the cap.

**`max_retries=0` on the SDK client.** The SDK otherwise retries a 429 by itself, silently,
and the caller's pacing never learns it is being limited. The batch caller retries on its
own terms instead (`ingest/triage_run.py`), and reads the rate-limit headers, which
`_live_completer` returns with each answer and the audit line now records.

What is NOT here: any judgment. This module does not decide what a good statement is, what
"priority" means, or what precision is good enough — Q-E and Q-F, ratified by the owner at
task 4. It moves bytes and counts dollars.

Testing seam. `Run` takes a `completer`: a callable that receives the request kwargs and
returns the API's JSON response as a dict. Tests pass a fake, so the whole suite runs with
no key, no network and no spend. `tests/test_ai.py` also drives the real SDK through an
`httpx2.MockTransport` once, to prove the request we build is the request we meant.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ingest import env
from ingest.cache import atomic_write_text, repo_root

# The response headers that say how close the organization is to its rate limits
# (platform.claude.com/docs/en/api/rate-limits, "Response headers").
RATE_LIMIT_HEADERS = (
    "retry-after",
    "anthropic-ratelimit-requests-limit",
    "anthropic-ratelimit-requests-remaining",
    "anthropic-ratelimit-requests-reset",
    "anthropic-ratelimit-tokens-limit",
    "anthropic-ratelimit-tokens-remaining",
    "anthropic-ratelimit-tokens-reset",
    "anthropic-ratelimit-input-tokens-limit",
    "anthropic-ratelimit-input-tokens-remaining",
    "anthropic-ratelimit-input-tokens-reset",
    "anthropic-ratelimit-output-tokens-limit",
    "anthropic-ratelimit-output-tokens-remaining",
    "anthropic-ratelimit-output-tokens-reset",
)

# Where `_live_completer` puts those headers in the payload. Taken out again before the
# payload is cached: the cache is the model's answer, not the state of a rate limiter.
RATE_LIMITS_KEY = "rate_limits"

# Tokens the API adds around a request (roles, message framing) beyond the bytes we send.
# Generous on purpose: it only makes the cap reservation an over-estimate.
FRAMING_TOKENS = 256


def rate_limit_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """The rate-limit headers present on one response, by name."""
    return {name: headers[name] for name in RATE_LIMIT_HEADERS if name in headers}


class AiError(RuntimeError):
    """Base for every failure this module raises."""


class AiConfigError(AiError):
    """`ai.yaml` is missing, malformed, or disagrees with a prompt file on disk."""


class AiCapReached(AiError):
    """The run hit its per-run dollar cap. Nothing further is called."""


class AiResponseError(AiError):
    """The model refused, was truncated, or did not return the JSON the schema requires."""


# A completer receives the request kwargs and returns the API response as a plain dict
# (`anthropic.types.Message.to_dict()`), optionally carrying a `request_id` key.
Completer = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class Price:
    """USD per 1,000,000 tokens for one model."""

    input: float
    output: float


@dataclass(frozen=True)
class TaskConfig:
    """One `tasks:` entry of `ai.yaml`."""

    name: str
    model: str
    prompt_version: str
    prompt_file: str
    prompt_sha256: str
    effort: str
    max_tokens: int
    output_schema: dict[str, Any]


@dataclass(frozen=True)
class AiConfig:
    """All of `ai.yaml`, parsed."""

    config_version: int
    per_run_cost_cap_usd: float
    max_statements_per_member_per_run: int
    prices: dict[str, Price]
    tasks: dict[str, TaskConfig]

    def task(self, name: str) -> TaskConfig:
        try:
            return self.tasks[name]
        except KeyError:
            known = ", ".join(sorted(self.tasks)) or "none"
            raise AiConfigError(f"unknown AI task {name!r} (ai.yaml defines: {known})") from None

    def price(self, model: str) -> Price:
        try:
            return self.prices[model]
        except KeyError:
            raise AiConfigError(
                f"no price recorded for model {model!r}; add it to ai.yaml `prices:` "
                f"so the run can be costed and capped"
            ) from None


@dataclass(frozen=True)
class AiResult:
    """One completed call. `data` is the validated JSON object the model returned."""

    task: str
    data: dict[str, Any]
    input_hash: str
    cached: bool
    cost_usd: float
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    request_id: str | None
    stop_reason: str | None
    # The rate-limit headers the answer came back with; empty for a cache hit.
    rate_limits: dict[str, str] = field(default_factory=dict)


def config_path(data_dir: Path | None = None) -> Path:
    base = data_dir if data_dir is not None else repo_root() / "data"
    return base / "config" / "ai.yaml"


def load_config(data_dir: Path | None = None) -> AiConfig:
    """Parse `ai.yaml`. Raises `AiConfigError` on anything missing or mistyped."""
    path = config_path(data_dir)
    if not path.exists():
        raise AiConfigError(f"ai.yaml not found at {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise AiConfigError(f"ai.yaml must be a mapping, got {type(raw).__name__}")

    prices: dict[str, Price] = {}
    for model, entry in (raw.get("prices") or {}).items():
        try:
            prices[model] = Price(input=float(entry["input"]), output=float(entry["output"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise AiConfigError(f"ai.yaml prices.{model} needs numeric input/output") from exc

    tasks: dict[str, TaskConfig] = {}
    for name, entry in (raw.get("tasks") or {}).items():
        try:
            tasks[name] = TaskConfig(
                name=name,
                model=str(entry["model"]),
                prompt_version=str(entry["prompt_version"]),
                prompt_file=str(entry["prompt_file"]),
                prompt_sha256=str(entry["prompt_sha256"]),
                effort=str(entry["effort"]),
                max_tokens=int(entry["max_tokens"]),
                output_schema=dict(entry["output_schema"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AiConfigError(f"ai.yaml tasks.{name} is incomplete or mistyped: {exc}") from exc

    if not tasks:
        raise AiConfigError("ai.yaml defines no tasks")
    try:
        cap = float(raw["per_run_cost_cap_usd"])
        version = int(raw["config_version"])
        per_member = int(raw["max_statements_per_member_per_run"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AiConfigError(
            "ai.yaml needs `config_version` (int), `per_run_cost_cap_usd` (number) and "
            "`max_statements_per_member_per_run` (int)"
        ) from exc
    if cap <= 0:
        raise AiConfigError(f"ai.yaml per_run_cost_cap_usd must be positive, got {cap}")
    if per_member <= 0:
        raise AiConfigError(
            f"ai.yaml max_statements_per_member_per_run must be positive, got {per_member}"
        )
    return AiConfig(
        config_version=version,
        per_run_cost_cap_usd=cap,
        max_statements_per_member_per_run=per_member,
        prices=prices,
        tasks=tasks,
    )


def prompt_text(task: TaskConfig, repo: Path | None = None) -> str:
    """Read the task's prompt file and verify it against the hash `ai.yaml` claims.

    A `prompt_version` nobody can check is a label, not a version — so a prompt edited
    without bumping its version and re-recording its hash fails loudly here rather than
    silently changing what every published label means.
    """
    base = repo if repo is not None else repo_root()
    path = base / task.prompt_file
    if not path.exists():
        raise AiConfigError(f"prompt file for task {task.name!r} not found at {path}")
    # Normalize line endings before hashing. `.gitattributes` enforces `eol=lf` repo-wide,
    # so a checkout is LF on every platform — but a prompt edited by a CRLF-writing editor
    # would otherwise hash differently on Windows than in CI, failing the version check on
    # one machine only and silently splitting the cache key for identical prompt text.
    data = path.read_bytes().replace(b"\r\n", b"\n")
    actual = hashlib.sha256(data).hexdigest()
    if actual != task.prompt_sha256:
        raise AiConfigError(
            f"prompt file {task.prompt_file} does not match the hash ai.yaml records for "
            f"{task.name} ({task.prompt_sha256[:12]}… != {actual[:12]}…). Bump "
            f"prompt_version and re-record prompt_sha256 in the same commit."
        )
    return data.decode("utf-8")


def input_hash(task: TaskConfig, system: str, user: str) -> str:
    """sha256 over everything that could change the answer. Also the cache key."""
    payload = {
        "model": task.model,
        "prompt_version": task.prompt_version,
        "effort": task.effort,
        "max_tokens": task.max_tokens,
        "output_schema": task.output_schema,
        "system": system,
        "user": user,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cost_usd(price: Price, input_tokens: int, output_tokens: int) -> float:
    """Billed cost of one call. Output tokens include the model's own thinking tokens.

    Prompt-cache reads are not priced here because nothing caches prompts yet (one short
    system prompt per statement); add the cache-read rate to `ai.yaml` when that changes.
    """
    return (input_tokens * price.input + output_tokens * price.output) / 1_000_000


def estimate_cost(
    config: AiConfig,
    task_name: str,
    *,
    calls: int,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """What `calls` calls would cost — the number the count-before-spend report prints
    (owner decision 4, 2026-10-09) before the owner approves any spend."""
    task = config.task(task_name)
    return calls * cost_usd(config.price(task.model), input_tokens, output_tokens)


def max_cost_usd(task: TaskConfig, price: Price, system: str, user_text: str) -> float:
    """An UPPER BOUND on what one call can cost: every byte sent counted as a token, plus
    `FRAMING_TOKENS`, and the full `max_tokens` out. What `reserve=True` holds back."""
    sent = (
        len(system.encode("utf-8"))
        + len(user_text.encode("utf-8"))
        + len(json.dumps(task.output_schema).encode("utf-8"))
        + FRAMING_TOKENS
    )
    return cost_usd(price, sent, task.max_tokens)


@lru_cache(maxsize=1)
def _sdk_client() -> Any:
    """Build the Anthropic client lazily, so importing this module needs no credential and
    the whole test suite runs without one. The key is read through `ingest.env`, whose
    documented precedence (process env over `.env`) is what CI relies on. `max_retries=0`:
    see the module docstring."""
    import anthropic

    return anthropic.Anthropic(api_key=env.require("ANTHROPIC_API_KEY"), max_retries=0)


def _live_completer(request: dict[str, Any]) -> dict[str, Any]:
    raw = _sdk_client().messages.with_raw_response.create(**request)
    response = raw.parse()
    payload = response.to_dict(mode="json")
    payload["request_id"] = response._request_id
    payload[RATE_LIMITS_KEY] = rate_limit_headers(raw.headers)
    return payload


@dataclass
class Run:
    """One run's worth of AI calls, with its own spend ledger.

    A run is the unit the cap applies to: construct one per `uv run` invocation, make every
    call through it, and the cap stops the run rather than the individual call.
    """

    config: AiConfig
    completer: Completer = _live_completer
    data_dir: Path | None = None
    repo: Path | None = None
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    cap_usd: float | None = None
    spent_usd: float = field(default=0.0, init=False)
    calls: int = field(default=0, init=False)
    cache_hits: int = field(default=0, init=False)
    # Upper-bound cost held back for calls in flight (`reserve=True`).
    reserved_usd: float = field(default=0.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @property
    def cap(self) -> float:
        return self.cap_usd if self.cap_usd is not None else self.config.per_run_cost_cap_usd

    def _data(self) -> Path:
        return self.data_dir if self.data_dir is not None else repo_root() / "data"

    def _cache_path(self, task: TaskConfig, ihash: str) -> Path:
        return self._data() / "raw" / "anthropic" / task.name / f"{ihash}.json"

    def _log_path(self) -> Path:
        return self._data() / "quality" / "ai-calls" / f"{self.now():%Y-%m}.jsonl"

    def _log(self, line: dict[str, Any]) -> None:
        """Append one audit line. Callers hold `_lock`, so lines never interleave."""
        path = self._log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n")

    def call(self, task_name: str, user_text: str, *, reserve: bool = False) -> AiResult:
        """Ask one task one question about one piece of text. Safe to call from several
        threads at once; `reserve=True` keeps the cap exact while they do."""
        task = self.config.task(task_name)
        price = self.config.price(task.model)
        system = prompt_text(task, self.repo)
        ihash = input_hash(task, system, user_text)
        cache = self._cache_path(task, ihash)

        if cache.exists():
            payload = json.loads(cache.read_text(encoding="utf-8"))
            result = self._interpret(task, payload, ihash, cached=True, price=price)
            with self._lock:
                self.cache_hits += 1
                self._log(self._log_line(task, result, cached=True))
            return result

        hold = max_cost_usd(task, price, system, user_text) if reserve else 0.0
        with self._lock:
            if self.spent_usd >= self.cap or self.spent_usd + self.reserved_usd + hold > self.cap:
                raise AiCapReached(
                    f"run reached its ${self.cap:.2f} cap after {self.calls} calls "
                    f"(${self.spent_usd:.4f} spent, ${self.reserved_usd:.4f} held for calls "
                    f"in flight); stopping before {task.name} is called again"
                )
            self.reserved_usd += hold

        try:
            payload = self.completer(self._request(task, system, user_text))
        except BaseException:
            with self._lock:
                self.reserved_usd -= hold
            raise
        rate_limits = payload.pop(RATE_LIMITS_KEY, None) or {}
        usage = payload.get("usage") or {}
        spent = cost_usd(
            price,
            int(usage.get("input_tokens") or 0),
            int(usage.get("output_tokens") or 0),
        )
        with self._lock:
            self.reserved_usd -= hold
            self.calls += 1
            self.spent_usd += spent
        try:
            result = self._interpret(task, payload, ihash, cached=False, price=price)
        except AiResponseError as exc:
            with self._lock:
                self._log(
                    self._failed_log_line(task, payload, ihash, spent=spent, error=str(exc))
                )
            raise
        result = replace(result, rate_limits=rate_limits)
        cache.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(cache, json.dumps(payload, indent=2, sort_keys=True))
        with self._lock:
            self._log(self._log_line(task, result, cached=False))
        return result

    def _request(self, task: TaskConfig, system: str, user_text: str) -> dict[str, Any]:
        """The exact request sent to the API. No `temperature` — the current models reject
        sampling parameters; `effort` is the knob. Thinking stays adaptive (never disabled:
        a disabled-thinking Opus can write a tool call into its visible text)."""
        return {
            "model": task.model,
            "max_tokens": task.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_text}],
            "output_config": {
                "effort": task.effort,
                "format": {"type": "json_schema", "schema": task.output_schema},
            },
        }

    def _interpret(
        self,
        task: TaskConfig,
        payload: dict[str, Any],
        ihash: str,
        *,
        cached: bool,
        price: Price,
    ) -> AiResult:
        stop = payload.get("stop_reason")
        if stop == "refusal":
            raise AiResponseError(f"{task.name}: the model declined this input (refusal)")
        if stop == "max_tokens":
            raise AiResponseError(
                f"{task.name}: response hit max_tokens ({task.max_tokens}) and is truncated"
            )
        text = next(
            (b.get("text") for b in payload.get("content") or [] if b.get("type") == "text"),
            None,
        )
        if text is None:
            raise AiResponseError(f"{task.name}: response carried no text block")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AiResponseError(f"{task.name}: response was not valid JSON ({exc})") from exc
        if not isinstance(data, dict):
            raise AiResponseError(f"{task.name}: response JSON was {type(data).__name__}, "
                                  f"not an object")
        missing = [k for k in task.output_schema.get("required", []) if k not in data]
        if missing:
            raise AiResponseError(
                f"{task.name}: response is missing required field(s) {', '.join(missing)}"
            )
        usage = payload.get("usage") or {}
        in_tok = int(usage.get("input_tokens") or 0)
        out_tok = int(usage.get("output_tokens") or 0)
        return AiResult(
            task=task.name,
            data=data,
            input_hash=ihash,
            cached=cached,
            cost_usd=0.0 if cached else cost_usd(price, in_tok, out_tok),
            model=task.model,
            prompt_version=task.prompt_version,
            input_tokens=in_tok,
            output_tokens=out_tok,
            request_id=payload.get("request_id"),
            stop_reason=stop,
        )

    def _log_line(self, task: TaskConfig, result: AiResult, *, cached: bool) -> dict[str, Any]:
        """One audit line. Hashes and counts only — no prompt text, no response text, no
        credential. The response text is in the cache file `input_hash` names."""
        return {
            "ts": self.now().isoformat(),
            "task": task.name,
            "model": task.model,
            "prompt_version": task.prompt_version,
            "config_version": self.config.config_version,
            "effort": task.effort,
            "input_hash": result.input_hash,
            "output_sha256": hashlib.sha256(
                json.dumps(result.data, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "cached": cached,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": round(result.cost_usd, 6),
            "run_spent_usd": round(self.spent_usd, 6),
            "stop_reason": result.stop_reason,
            "request_id": result.request_id,
            "rate_limits": result.rate_limits,
        }

    def _failed_log_line(
        self,
        task: TaskConfig,
        payload: dict[str, Any],
        ihash: str,
        *,
        spent: float,
        error: str,
    ) -> dict[str, Any]:
        """A failed call is logged too — it was billed, and a silent failure is exactly the
        thing the §6 nightly alarm exists to catch."""
        usage = payload.get("usage") or {}
        return {
            "ts": self.now().isoformat(),
            "task": task.name,
            "model": task.model,
            "prompt_version": task.prompt_version,
            "config_version": self.config.config_version,
            "effort": task.effort,
            "input_hash": ihash,
            "cached": False,
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
            "cost_usd": round(spent, 6),
            "run_spent_usd": round(self.spent_usd, 6),
            "stop_reason": payload.get("stop_reason"),
            "request_id": payload.get("request_id"),
            "error": error,
        }

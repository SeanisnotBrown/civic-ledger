"""§5 Phase 3 task 1 — the AI gateway. No network, no credential, no spend.

Two layers, deliberately:

  * Most tests drive `Run` through a fake completer, so every branch of hashing, caching,
    logging, cost, the spend cap and response validation is exercised in-process.
  * `test_real_sdk_request_is_what_we_meant` drives the REAL Anthropic SDK through an
    `httpx2.MockTransport` and asserts on the bytes actually sent. The seam above proves
    our logic; only this proves we are speaking the API's language. (The SDK runs on
    `httpx2`, not the project's `httpx<0.28` — the two coexist, but `httpx.MockTransport`
    from `test_archive_org.py` does NOT plug into the Anthropic client.)

The real `data/config/ai.yaml` and the real prompt files are the fixtures wherever
possible, so the shipped configuration is itself under test.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest
import yaml

from ingest import ai

FIXED_NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)

CATEGORIZED = {
    "topic": "Agriculture and Food",
    "stance": "for",
    "proposition": "raising the crop insurance subsidy",
    "specificity": 1,
    "priority_signal": True,
    "confidence": "high",
}


def _payload(data: dict | str, *, stop: str | None = "end_turn", tokens=(1500, 1000)) -> dict:
    text = data if isinstance(data, str) else json.dumps(data)
    return {
        "id": "msg_01",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop,
        "usage": {"input_tokens": tokens[0], "output_tokens": tokens[1]},
        "request_id": "req_abc",
    }


def _run(tmp_path: Path, payloads: list[dict] | None = None, **kwargs) -> ai.Run:
    """A Run over the REAL ai.yaml, writing its cache and log into tmp_path."""
    queue = list(payloads if payloads is not None else [_payload(CATEGORIZED)])
    sent: list[dict] = []

    def completer(request: dict) -> dict:
        sent.append(request)
        return queue.pop(0)

    run = ai.Run(
        config=ai.load_config(), completer=completer, data_dir=tmp_path,
        now=lambda: FIXED_NOW, **kwargs,
    )
    run.sent = sent  # type: ignore[attr-defined]
    return run


def _log_lines(tmp_path: Path) -> list[dict]:
    path = tmp_path / "quality" / "ai-calls" / "2026-10.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# --- the shipped configuration ------------------------------------------------------


def test_real_config_loads_and_defines_both_phase_3_tasks() -> None:
    config = ai.load_config()
    assert set(config.tasks) == {"triage_statement", "categorize_statement"}
    assert config.tasks["categorize_statement"].model == "claude-opus-5-5"
    assert config.tasks["categorize_statement"].effort == "medium"
    assert config.tasks["triage_statement"].model == "claude-haiku-5-5"
    assert config.per_run_cost_cap_usd > 0
    assert config.max_statements_per_member_per_run == 25


def test_real_config_carries_no_sampling_parameter() -> None:
    """The current models reject `temperature` with a 400; `effort` is the knob."""
    raw = (ai.config_path()).read_text(encoding="utf-8")
    for task in yaml.safe_load(raw)["tasks"].values():
        assert "temperature" not in task
        assert "top_p" not in task
        assert "top_k" not in task


def test_every_task_has_a_price_so_the_cap_can_be_enforced() -> None:
    config = ai.load_config()
    for task in config.tasks.values():
        assert config.price(task.model).input > 0


def test_prompt_files_match_their_recorded_hash() -> None:
    """A `prompt_version` nobody can check is a label, not a version."""
    config = ai.load_config()
    for task in config.tasks.values():
        assert ai.prompt_text(task).strip()


def test_stance_enum_is_the_owners_four_values_and_proposition_is_nullable() -> None:
    schema = ai.load_config().tasks["categorize_statement"].output_schema
    props = schema["properties"]
    assert props["stance"]["enum"] == ["for", "against", "mixed", "none"]
    assert props["proposition"]["type"] == ["string", "null"]
    assert "proposition" in schema["required"]


def _prompt_policy_areas() -> list[str]:
    """The policy-area list exactly as the categorizer prompt prints it."""
    task = ai.load_config().tasks["categorize_statement"]
    text = ai.prompt_text(task)
    block = text.split("copied exactly from this list:", 1)[1].split("\n\n", 2)[1]
    return [a.strip() for a in " ".join(block.split("\n")).split("·")]


def test_topic_enum_is_the_owners_33_policy_areas_and_matches_the_prompt() -> None:
    """Owner ruling 2026-10-22: topic is one of the 33 official policy areas. The schema
    the API enforces and the list the prompt shows the model must be the same list."""
    topic = ai.load_config().tasks["categorize_statement"].output_schema["properties"]["topic"]
    strings, null = topic["anyOf"]
    assert null == {"type": "null"}
    assert len(strings["enum"]) == len(set(strings["enum"])) == 33
    assert _prompt_policy_areas() == strings["enum"]


def test_specificity_is_the_owners_three_levels() -> None:
    spec = ai.load_config().tasks["categorize_statement"].output_schema["properties"][
        "specificity"
    ]
    assert spec["anyOf"] == [{"type": "integer", "enum": [1, 2, 3]}, {"type": "null"}]


def test_no_shipped_prompt_or_config_names_the_stale_question_ids() -> None:
    """Q-E/Q-F are the Phase 7/8 questions; the priority and precision questions are
    Q-J and Q-K. The stubs keep their old text (editing them would change their hash)."""
    config = ai.load_config()
    assert "Q-E" not in ai.config_path().read_text(encoding="utf-8")
    assert "Q-F" not in ai.config_path().read_text(encoding="utf-8")
    for task in config.tasks.values():
        text = ai.prompt_text(task)
        assert "Q-E" not in text and "Q-F" not in text


# --- config parsing -----------------------------------------------------------------


def _write_config(tmp_path: Path, body: dict) -> Path:
    path = tmp_path / "config" / "ai.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(body), encoding="utf-8")
    return tmp_path


def _minimal(**overrides) -> dict:
    body = {
        "config_version": 1,
        "per_run_cost_cap_usd": 1.0,
        "max_statements_per_member_per_run": 5,
        "prices": {"m": {"input": 1.0, "output": 2.0}},
        "tasks": {
            "t": {
                "model": "m",
                "prompt_version": "v1",
                "prompt_file": "p.md",
                "prompt_sha256": "x",
                "effort": "medium",
                "max_tokens": 10,
                "output_schema": {"type": "object", "required": ["a"]},
            }
        },
    }
    body.update(overrides)
    return body


def test_missing_config_file_is_named(tmp_path: Path) -> None:
    with pytest.raises(ai.AiConfigError, match="not found"):
        ai.load_config(tmp_path)


def test_config_must_be_a_mapping(tmp_path: Path) -> None:
    path = tmp_path / "config" / "ai.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ai.AiConfigError, match="must be a mapping"):
        ai.load_config(tmp_path)


def test_a_price_without_numbers_is_rejected(tmp_path: Path) -> None:
    _write_config(tmp_path, _minimal(prices={"m": {"input": 1.0}}))
    with pytest.raises(ai.AiConfigError, match="prices.m"):
        ai.load_config(tmp_path)


def test_an_incomplete_task_is_rejected(tmp_path: Path) -> None:
    _write_config(tmp_path, _minimal(tasks={"t": {"model": "m"}}))
    with pytest.raises(ai.AiConfigError, match="tasks.t"):
        ai.load_config(tmp_path)


def test_a_config_with_no_tasks_is_rejected(tmp_path: Path) -> None:
    _write_config(tmp_path, _minimal(tasks={}))
    with pytest.raises(ai.AiConfigError, match="no tasks"):
        ai.load_config(tmp_path)


def test_a_config_without_a_cap_is_rejected(tmp_path: Path) -> None:
    body = _minimal()
    del body["per_run_cost_cap_usd"]
    _write_config(tmp_path, body)
    with pytest.raises(ai.AiConfigError, match="per_run_cost_cap_usd"):
        ai.load_config(tmp_path)


def test_a_nonpositive_per_member_cap_is_rejected(tmp_path: Path) -> None:
    _write_config(tmp_path, _minimal(max_statements_per_member_per_run=0))
    with pytest.raises(ai.AiConfigError, match="max_statements_per_member_per_run must be"):
        ai.load_config(tmp_path)


def test_a_config_without_the_per_member_cap_is_rejected(tmp_path: Path) -> None:
    body = _minimal()
    del body["max_statements_per_member_per_run"]
    _write_config(tmp_path, body)
    with pytest.raises(ai.AiConfigError, match="max_statements_per_member_per_run"):
        ai.load_config(tmp_path)


def test_a_nonpositive_cap_is_rejected(tmp_path: Path) -> None:
    _write_config(tmp_path, _minimal(per_run_cost_cap_usd=0))
    with pytest.raises(ai.AiConfigError, match="must be positive"):
        ai.load_config(tmp_path)


def test_unknown_task_lists_the_known_ones(tmp_path: Path) -> None:
    _write_config(tmp_path, _minimal())
    with pytest.raises(ai.AiConfigError, match="ai.yaml defines: t"):
        ai.load_config(tmp_path).task("nope")


def test_unpriced_model_is_refused_rather_than_run_uncosted(tmp_path: Path) -> None:
    _write_config(tmp_path, _minimal())
    with pytest.raises(ai.AiConfigError, match="no price recorded"):
        ai.load_config(tmp_path).price("other")


# --- prompt files -------------------------------------------------------------------


def test_missing_prompt_file_is_named(tmp_path: Path) -> None:
    task = ai.load_config().tasks["triage_statement"]
    with pytest.raises(ai.AiConfigError, match="prompt file for task"):
        ai.prompt_text(task, repo=tmp_path)


def test_a_crlf_prompt_file_hashes_the_same_as_its_lf_original(tmp_path: Path) -> None:
    """`.gitattributes` enforces LF, but a CRLF-writing editor must not break the version
    check on one platform only — nor split the cache key for identical prompt text."""
    task = ai.load_config().tasks["triage_statement"]
    path = tmp_path / task.prompt_file
    path.parent.mkdir(parents=True)
    original = (Path(ai.repo_root()) / task.prompt_file).read_bytes()
    path.write_bytes(original.replace(b"\n", b"\r\n"))

    assert ai.prompt_text(task, repo=tmp_path) == ai.prompt_text(task)


def test_edited_prompt_without_a_version_bump_fails_loudly(tmp_path: Path) -> None:
    task = ai.load_config().tasks["triage_statement"]
    path = tmp_path / task.prompt_file
    path.parent.mkdir(parents=True)
    path.write_text("a different prompt\n", encoding="utf-8")
    with pytest.raises(ai.AiConfigError, match="does not match the hash"):
        ai.prompt_text(task, repo=tmp_path)


# --- hashing and cost ---------------------------------------------------------------


def test_input_hash_is_stable_and_separates_different_questions() -> None:
    task = ai.load_config().tasks["categorize_statement"]
    a = ai.input_hash(task, "sys", "text")
    assert a == ai.input_hash(task, "sys", "text")
    assert a != ai.input_hash(task, "sys", "other text")
    assert a != ai.input_hash(task, "other sys", "text")


def test_cost_uses_the_rate_per_million_tokens() -> None:
    price = ai.Price(input=4.0, output=20.0)
    assert ai.cost_usd(price, 1_000_000, 0) == pytest.approx(4.0)
    assert ai.cost_usd(price, 1500, 1000) == pytest.approx(0.026)


def test_estimate_cost_is_what_the_count_before_spend_report_prints() -> None:
    config = ai.load_config()
    estimate = ai.estimate_cost(
        config, "categorize_statement", calls=1000, input_tokens=1500, output_tokens=1000
    )
    assert estimate == pytest.approx(26.0)


# --- calling ------------------------------------------------------------------------


def test_a_call_returns_validated_data_and_logs_one_auditable_line(tmp_path: Path) -> None:
    run = _run(tmp_path)
    result = run.call("categorize_statement", "I support raising crop insurance subsidies.")

    assert result.data == CATEGORIZED
    assert result.cached is False
    assert result.cost_usd == pytest.approx(0.026)
    assert run.spent_usd == pytest.approx(0.026)
    assert run.calls == 1

    (line,) = _log_lines(tmp_path)
    assert line["task"] == "categorize_statement"
    assert line["model"] == "claude-opus-5-5"
    assert line["prompt_version"] == "v2"
    assert line["input_hash"] == result.input_hash
    assert line["request_id"] == "req_abc"
    assert line["cost_usd"] == pytest.approx(0.026)
    assert line["ts"] == "2026-10-09T12:00:00+00:00"


def test_the_log_carries_no_prompt_text_no_response_text_and_no_key(tmp_path: Path) -> None:
    run = _run(tmp_path)
    run.call("categorize_statement", "crop insurance subsidies are my top priority")
    blob = (tmp_path / "quality" / "ai-calls" / "2026-10.jsonl").read_text(encoding="utf-8")
    assert "crop insurance" not in blob
    assert "Agriculture" not in blob
    assert "api_key" not in blob and "x-api-key" not in blob


def test_the_raw_response_is_cached_where_collectors_cache(tmp_path: Path) -> None:
    run = _run(tmp_path)
    result = run.call("categorize_statement", "text")
    cached = tmp_path / "raw" / "anthropic" / "categorize_statement" / f"{result.input_hash}.json"
    assert json.loads(cached.read_text(encoding="utf-8"))["stop_reason"] == "end_turn"


def test_an_unchanged_input_costs_nothing_the_second_time(tmp_path: Path) -> None:
    run = _run(tmp_path)
    first = run.call("categorize_statement", "text")

    # One payload was queued; a second live call would raise IndexError.
    second = run.call("categorize_statement", "text")

    assert second.data == first.data
    assert second.cached is True
    assert second.cost_usd == 0.0
    assert run.spent_usd == pytest.approx(first.cost_usd)
    assert run.calls == 1 and run.cache_hits == 1
    assert [line["cached"] for line in _log_lines(tmp_path)] == [False, True]


def test_the_run_stops_at_its_cap_rather_than_finishing_the_batch(tmp_path: Path) -> None:
    run = _run(tmp_path, payloads=[_payload(CATEGORIZED)], cap_usd=0.01)
    run.call("categorize_statement", "first")          # 0.026 > the 0.01 cap
    with pytest.raises(ai.AiCapReached, match=r"\$0.01 cap"):
        run.call("categorize_statement", "second")
    assert run.calls == 1


def test_the_cap_defaults_to_the_one_in_ai_yaml(tmp_path: Path) -> None:
    run = _run(tmp_path)
    assert run.cap == ai.load_config().per_run_cost_cap_usd


def test_a_cached_hit_is_served_even_after_the_cap_is_reached(tmp_path: Path) -> None:
    """The cap exists to stop SPENDING, not to stop work that costs nothing."""
    run = _run(tmp_path, cap_usd=0.01)
    run.call("categorize_statement", "text")
    assert run.call("categorize_statement", "text").cached is True


# --- responses that must not become data --------------------------------------------


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (_payload(CATEGORIZED, stop="refusal"), "declined"),
        (_payload(CATEGORIZED, stop="max_tokens"), "truncated"),
        (_payload("not json at all"), "not valid JSON"),
        (_payload("[1, 2]"), "not an object"),
        (_payload({"topic": "Agriculture"}), "missing required field"),
    ],
)
def test_an_unusable_response_raises_and_is_not_cached(
    tmp_path: Path, payload: dict, match: str
) -> None:
    run = _run(tmp_path, payloads=[payload])
    with pytest.raises(ai.AiResponseError, match=match):
        run.call("categorize_statement", "text")

    assert not (tmp_path / "raw").exists(), "a bad answer must not become a permanent one"
    (line,) = _log_lines(tmp_path)
    assert line["error"]
    assert line["cost_usd"] == pytest.approx(0.026), "it was billed, so it is logged as billed"


def test_a_response_with_no_text_block_raises(tmp_path: Path) -> None:
    payload = _payload(CATEGORIZED)
    payload["content"] = [{"type": "thinking", "thinking": ""}]
    run = _run(tmp_path, payloads=[payload])
    with pytest.raises(ai.AiResponseError, match="no text block"):
        run.call("categorize_statement", "text")


def test_a_response_with_no_usage_block_is_costed_at_zero(tmp_path: Path) -> None:
    payload = _payload(CATEGORIZED)
    del payload["usage"]
    run = _run(tmp_path, payloads=[payload])
    assert run.call("categorize_statement", "text").cost_usd == 0.0


# --- the request we actually send ----------------------------------------------------


def test_the_request_carries_effort_and_the_schema_but_never_temperature(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path)
    run.call("categorize_statement", "text")
    (request,) = run.sent  # type: ignore[attr-defined]

    assert request["model"] == "claude-opus-5-5"
    assert request["max_tokens"] == 4096
    assert request["output_config"]["effort"] == "medium"
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert "temperature" not in request
    assert "thinking" not in request, "thinking stays adaptive; disabling it is a known trap"
    assert request["messages"] == [{"role": "user", "content": "text"}]


def test_real_sdk_request_is_what_we_meant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive the real SDK through a mock transport: no network, real serialization."""
    import anthropic

    seen: dict = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        seen["key"] = request.headers.get("x-api-key")
        return httpx2.Response(
            200,
            headers={"request-id": "req_live"},
            json={
                "id": "msg_1", "type": "message", "role": "assistant",
                "model": "claude-opus-5-5",
                "content": [{"type": "text", "text": json.dumps(CATEGORIZED)}],
                "stop_reason": "end_turn", "stop_sequence": None,
                "usage": {"input_tokens": 1500, "output_tokens": 1000},
            },
        )

    client = anthropic.Anthropic(
        api_key="test-key",
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)),
        max_retries=0,
    )
    monkeypatch.setattr(ai, "_sdk_client", lambda: client)

    run = ai.Run(
        config=ai.load_config(), data_dir=tmp_path, now=lambda: FIXED_NOW
    )  # default completer — the live path
    result = run.call("categorize_statement", "I support raising crop insurance subsidies.")

    assert result.data == CATEGORIZED
    assert result.request_id == "req_live"
    assert seen["key"] == "test-key"
    assert seen["body"]["model"] == "claude-opus-5-5"
    assert seen["body"]["output_config"]["effort"] == "medium"
    assert seen["body"]["output_config"]["format"]["schema"]["properties"]["stance"]["enum"] == [
        "for", "against", "mixed", "none",
    ]
    assert "temperature" not in seen["body"]


def test_the_live_path_returns_the_rate_limit_headers_and_never_caches_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import anthropic

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            headers={
                "request-id": "req_rl",
                "anthropic-ratelimit-requests-limit": "1000",
                "anthropic-ratelimit-requests-remaining": "998",
                "anthropic-ratelimit-input-tokens-limit": "2000000",
                "anthropic-ratelimit-input-tokens-remaining": "1990000",
                "x-unrelated": "dropped",
            },
            json={
                "id": "msg_1", "type": "message", "role": "assistant",
                "model": "claude-haiku-5-5",
                "content": [{"type": "text", "text": '{"takes_policy_position": true}'}],
                "stop_reason": "end_turn", "stop_sequence": None,
                "usage": {"input_tokens": 1500, "output_tokens": 20},
            },
        )

    client = anthropic.Anthropic(
        api_key="test-key",
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)),
        max_retries=0,
    )
    monkeypatch.setattr(ai, "_sdk_client", lambda: client)
    run = ai.Run(config=ai.load_config(), data_dir=tmp_path, now=lambda: FIXED_NOW)
    result = run.call("triage_statement", "I will vote for the farm bill.")

    assert result.rate_limits == {
        "anthropic-ratelimit-requests-limit": "1000",
        "anthropic-ratelimit-requests-remaining": "998",
        "anthropic-ratelimit-input-tokens-limit": "2000000",
        "anthropic-ratelimit-input-tokens-remaining": "1990000",
    }
    cached = tmp_path / "raw" / "anthropic" / "triage_statement" / f"{result.input_hash}.json"
    assert ai.RATE_LIMITS_KEY not in json.loads(cached.read_text(encoding="utf-8"))
    (line,) = _log_lines(tmp_path)
    assert line["rate_limits"]["anthropic-ratelimit-requests-remaining"] == "998"


def test_the_upper_bound_is_never_below_what_a_call_costs() -> None:
    config = ai.load_config()
    task = config.task("triage_statement")
    price = config.price(task.model)
    system = ai.prompt_text(task)
    text = "I support the bill. " * 200
    bound = ai.max_cost_usd(task, price, system, text)
    # Even if every character were its own token and the answer ran to max_tokens:
    worst_real = ai.cost_usd(price, len(system) + len(text), task.max_tokens)
    assert bound >= worst_real


def test_a_reserved_call_is_refused_when_calls_in_flight_would_pass_the_cap(
    tmp_path: Path,
) -> None:
    """The cap holds with calls IN FLIGHT: each reserves an upper bound before it is sent,
    so the one that would carry the total past the cap is refused before it is sent."""
    import threading

    config = ai.load_config()
    task = config.task("triage_statement")
    bound = ai.max_cost_usd(task, config.price(task.model), ai.prompt_text(task), "text 0")
    release = threading.Event()
    sent: list[str] = []

    def completer(request: dict) -> dict:
        sent.append(request["messages"][0]["content"])
        release.wait(5)
        return _payload({"takes_policy_position": True}, tokens=(10, 1))

    # Room for exactly two reservations, not three.
    run = ai.Run(
        config=config, completer=completer, data_dir=tmp_path, now=lambda: FIXED_NOW,
        cap_usd=bound * 2.5,
    )
    workers = [
        threading.Thread(target=run.call, args=("triage_statement", f"text {i}"),
                         kwargs={"reserve": True})
        for i in range(2)
    ]
    for worker in workers:
        worker.start()
    while len(sent) < 2:
        pass
    assert run.reserved_usd == pytest.approx(bound * 2, rel=0.01)
    with pytest.raises(ai.AiCapReached, match="held for calls in flight"):
        run.call("triage_statement", "text 2", reserve=True)
    release.set()
    for worker in workers:
        worker.join()
    assert len(sent) == 2
    assert run.reserved_usd == pytest.approx(0.0)
    assert run.spent_usd <= run.cap
    assert len(_log_lines(tmp_path)) == 2


def test_a_failed_send_releases_its_reservation(tmp_path: Path) -> None:
    def completer(request: dict) -> dict:
        raise ConnectionError("network down")

    run = ai.Run(
        config=ai.load_config(), completer=completer, data_dir=tmp_path, now=lambda: FIXED_NOW
    )
    with pytest.raises(ConnectionError):
        run.call("triage_statement", "text", reserve=True)
    assert run.reserved_usd == 0.0 and run.calls == 0 and run.spent_usd == 0.0


def test_the_client_is_built_lazily_from_the_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Importing this module must not need a credential — CI has none at import time."""
    ai._sdk_client.cache_clear()
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        ai._sdk_client()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    ai._sdk_client.cache_clear()
    client = ai._sdk_client()
    assert client.api_key == "sk-test"
    # The batch caller paces and retries; the SDK must not retry a 429 behind its back.
    assert client.max_retries == 0
    ai._sdk_client.cache_clear()


def test_default_paths_point_into_the_repository() -> None:
    assert ai.config_path().as_posix().endswith("data/config/ai.yaml")
    run = ai.Run(config=ai.load_config(), completer=lambda request: {})
    assert run._data().name == "data"
    assert run._cache_path(run.config.task("triage_statement"), "abc").as_posix().endswith(
        "data/raw/anthropic/triage_statement/abc.json"
    )

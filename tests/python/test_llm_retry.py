"""Tests for the LLM retry layer (core/runtime/llm_retry.py)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.runtime import llm_retry
from core.runtime.llm_provider import (
    AnthropicDirectProvider,
    LLMResponse,
    LLMUnavailable,
    SubagentProvider,
)
from core.runtime.llm_retry import (
    RetryDecision,
    default_classifier,
    retry_completion,
)


# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_retry_file(tmp_path, monkeypatch):
    path = tmp_path / "llm-retries.jsonl"
    monkeypatch.setenv("ARKA_LLM_RETRY_PATH", str(path))
    yield path


@pytest.fixture()
def tmp_cost_file(tmp_path, monkeypatch):
    path = tmp_path / "llm-cost.jsonl"
    monkeypatch.setenv("ARKA_LLM_COST_PATH", str(path))
    yield path


@pytest.fixture()
def sleep_recorder(monkeypatch):
    """Record sleeps instead of sleeping; zero out jitter for determinism."""
    sleeps: list[float] = []
    monkeypatch.setattr(llm_retry.time, "sleep", sleeps.append)
    monkeypatch.setattr(llm_retry.random, "uniform", lambda a, b: 0.0)
    return sleeps


class _FakeSDKError(Exception):
    """Synthetic SDK-style exception with optional status/headers."""

    def __init__(self, msg, status_code=None, headers=None):
        super().__init__(msg)
        if status_code is not None:
            self.status_code = status_code
        if status_code is not None or headers is not None:
            self.response = SimpleNamespace(
                status_code=status_code, headers=headers or {}
            )


def _flaky(exceptions: list[Exception], result="ok"):
    """Callable raising queued exceptions before finally returning result."""
    queue = list(exceptions)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if queue:
            raise queue.pop(0)
        return result

    fn.calls = calls  # type: ignore[attr-defined]
    return fn


# ─── default_classifier ───────────────────────────────────────────────


class TestDefaultClassifier:
    def test_status_429_is_retryable(self):
        d = default_classifier(_FakeSDKError("boom", status_code=429))
        assert d.retryable and d.reason == "rate-limit"

    def test_rate_limit_message_is_retryable(self):
        d = default_classifier(LLMUnavailable("claude CLI exited 1: rate_limit_error"))
        assert d.retryable and d.reason == "rate-limit"

    def test_retry_after_header_extracted(self):
        exc = _FakeSDKError("429", status_code=429, headers={"retry-after": "17"})
        d = default_classifier(exc)
        assert d.retry_after == 17.0

    def test_retry_after_missing_is_none(self):
        d = default_classifier(_FakeSDKError("429", status_code=429))
        assert d.retry_after is None

    def test_retry_after_garbage_ignored(self):
        exc = _FakeSDKError("429", status_code=429, headers={"retry-after": "soon"})
        assert default_classifier(exc).retry_after is None

    def test_5xx_is_retryable(self):
        d = default_classifier(_FakeSDKError("ise", status_code=503))
        assert d.retryable and d.reason == "server-error"

    def test_overloaded_message_is_retryable(self):
        d = default_classifier(LLMUnavailable("overloaded_error: 529"))
        assert d.retryable and d.reason in ("overloaded", "rate-limit")

    def test_connection_error_is_retryable(self):
        d = default_classifier(LLMUnavailable("claude CLI timed out after 60s"))
        assert d.retryable and d.reason == "connection"

    def test_auth_message_not_retryable(self):
        d = default_classifier(LLMUnavailable("invalid api key"))
        assert not d.retryable and d.reason == "auth"

    def test_4xx_status_not_retryable(self):
        d = default_classifier(_FakeSDKError("bad request", status_code=400))
        assert not d.retryable and d.reason == "client-error"

    def test_unknown_not_retryable(self):
        d = default_classifier(ValueError("something else entirely"))
        assert not d.retryable and d.reason == "unknown"


# ─── retry_completion — schedule + semantics ──────────────────────────


class TestRetryCompletion:
    def test_success_first_try_no_sleep(self, sleep_recorder, tmp_retry_file):
        assert retry_completion(_flaky([])) == "ok"
        assert sleep_recorder == []

    def test_backoff_schedule_exponential(self, sleep_recorder, tmp_retry_file):
        errs = [_FakeSDKError("429", status_code=429) for _ in range(3)]
        assert retry_completion(_flaky(errs), provider="t") == "ok"
        assert sleep_recorder == [2.0, 4.0, 8.0]

    def test_max_delay_caps_backoff(self, sleep_recorder, tmp_retry_file):
        errs = [_FakeSDKError("429", status_code=429) for _ in range(3)]
        retry_completion(_flaky(errs), base_delay=40.0, max_delay=60.0)
        assert sleep_recorder == [40.0, 60.0, 60.0]

    def test_retry_after_honored_exactly(self, sleep_recorder, tmp_retry_file):
        errs = [_FakeSDKError("429", status_code=429, headers={"retry-after": "17"})]
        retry_completion(_flaky(errs))
        assert sleep_recorder == [17.0]

    def test_non_retryable_fails_fast(self, sleep_recorder, tmp_retry_file):
        fn = _flaky([LLMUnavailable("invalid api key"), LLMUnavailable("x")])
        with pytest.raises(LLMUnavailable, match="invalid api key"):
            retry_completion(fn)
        assert fn.calls["n"] == 1
        assert sleep_recorder == []

    def test_exhaustion_raises_llm_unavailable_with_count(
        self, sleep_recorder, tmp_retry_file
    ):
        errs = [_FakeSDKError("429", status_code=429) for _ in range(10)]
        with pytest.raises(LLMUnavailable, match="exhausted after 4 attempts"):
            retry_completion(_flaky(errs), provider="p")
        assert len(sleep_recorder) == 3  # no sleep after the final attempt

    def test_total_sleep_budget_capped_at_180(self, sleep_recorder, tmp_retry_file):
        errs = [
            _FakeSDKError("429", status_code=429, headers={"retry-after": "200"})
            for _ in range(10)
        ]
        with pytest.raises(LLMUnavailable, match="exhausted after 2 attempts"):
            retry_completion(_flaky(errs))
        assert sleep_recorder == [180.0]
        assert sum(sleep_recorder) <= llm_retry.MAX_TOTAL_SLEEP_SECONDS

    def test_custom_classifier_wins(self, sleep_recorder, tmp_retry_file):
        always = lambda exc: RetryDecision(retryable=True, reason="forced")  # noqa: E731
        assert retry_completion(
            _flaky([ValueError("nope")]), classify=always
        ) == "ok"
        assert len(sleep_recorder) == 1

    def test_telemetry_written_per_retry(self, sleep_recorder, tmp_retry_file):
        errs = [_FakeSDKError("429", status_code=429) for _ in range(2)]
        retry_completion(_flaky(errs), provider="anthropic-direct")
        rows = [
            json.loads(line)
            for line in tmp_retry_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(rows) == 2
        assert rows[0]["provider"] == "anthropic-direct"
        assert rows[0]["attempt"] == 1
        assert rows[1]["attempt"] == 2
        assert rows[0]["reason"] == "rate-limit"
        assert rows[0]["delay"] == 2.0
        assert "ts" in rows[0]

    def test_telemetry_failure_never_breaks_retry(
        self, sleep_recorder, monkeypatch
    ):
        monkeypatch.setenv("ARKA_LLM_RETRY_PATH", "/dev/null/impossible/x.jsonl")
        errs = [_FakeSDKError("429", status_code=429)]
        assert retry_completion(_flaky(errs)) == "ok"


# ─── Wiring: SubagentProvider ─────────────────────────────────────────


class _QueueAdapter:
    """Duck-typed adapter raising queued exceptions before succeeding."""

    def __init__(self, exceptions):
        self._queue = list(exceptions)
        self.calls = 0

    def headless_supported(self):
        return True

    def headless_complete(self, prompt, *, max_tokens=2000, system=""):
        self.calls += 1
        if self._queue:
            raise self._queue.pop(0)
        return LLMResponse(
            text="done", tokens_in=1, tokens_out=2, cached_tokens=0, model="m"
        )


class TestSubagentProviderRetry:
    def test_rate_limit_stderr_retries_then_succeeds(
        self, sleep_recorder, tmp_retry_file, tmp_cost_file
    ):
        adapter = _QueueAdapter(
            [LLMUnavailable("claude CLI exited 1: 429 rate limit exceeded")] * 2
        )
        provider = SubagentProvider(adapter=adapter)  # type: ignore[arg-type]
        response = provider.complete("hi")
        assert response.text == "done"
        assert adapter.calls == 3
        assert sleep_recorder == [2.0, 4.0]

    def test_non_rate_limit_exit_fails_fast(
        self, sleep_recorder, tmp_retry_file, tmp_cost_file
    ):
        adapter = _QueueAdapter(
            [LLMUnavailable("claude CLI exited 1: invalid api key")] * 3
        )
        provider = SubagentProvider(adapter=adapter)  # type: ignore[arg-type]
        with pytest.raises(LLMUnavailable, match="invalid api key"):
            provider.complete("hi")
        assert adapter.calls == 1

    def test_exhaustion_preserves_llm_unavailable(
        self, sleep_recorder, tmp_retry_file, tmp_cost_file
    ):
        adapter = _QueueAdapter(
            [LLMUnavailable("claude CLI exited 1: rate_limit")] * 10
        )
        provider = SubagentProvider(adapter=adapter)  # type: ignore[arg-type]
        with pytest.raises(LLMUnavailable, match="exhausted after 4 attempts"):
            provider.complete("hi")
        assert adapter.calls == 4


# ─── Wiring: AnthropicDirectProvider ──────────────────────────────────


def _anthropic_raw():
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="ok")],
        usage=SimpleNamespace(
            input_tokens=5,
            output_tokens=7,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
        model="claude-test",
    )


class _QueueClient:
    def __init__(self, exceptions):
        queue = list(exceptions)
        self.calls = 0
        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.calls += 1
                if queue:
                    raise queue.pop(0)
                return _anthropic_raw()

        self.messages = _Messages()


class TestAnthropicDirectRetry:
    @pytest.fixture(autouse=True)
    def _model_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test")

    def test_429_with_retry_after_honored(
        self, sleep_recorder, tmp_retry_file, tmp_cost_file
    ):
        client = _QueueClient(
            [_FakeSDKError("429", status_code=429, headers={"retry-after": "9"})]
        )
        provider = AnthropicDirectProvider(client=client)
        response = provider.complete("hi")
        assert response.text == "ok"
        assert client.calls == 2
        assert sleep_recorder == [9.0]

    def test_auth_error_fails_fast_as_llm_unavailable(
        self, sleep_recorder, tmp_retry_file, tmp_cost_file
    ):
        client = _QueueClient(
            [_FakeSDKError("authentication_error", status_code=401)] * 3
        )
        provider = AnthropicDirectProvider(client=client)
        with pytest.raises(
            LLMUnavailable, match="anthropic.messages.create failed"
        ):
            provider.complete("hi")
        assert client.calls == 1

    def test_exhaustion_raises_llm_unavailable(
        self, sleep_recorder, tmp_retry_file, tmp_cost_file
    ):
        client = _QueueClient(
            [_FakeSDKError("overloaded_error", status_code=529)] * 10
        )
        provider = AnthropicDirectProvider(client=client)
        with pytest.raises(LLMUnavailable, match="exhausted after 4 attempts"):
            provider.complete("hi")
        assert client.calls == 4

    def test_retry_telemetry_provider_field(
        self, sleep_recorder, tmp_retry_file, tmp_cost_file
    ):
        client = _QueueClient([_FakeSDKError("429", status_code=429)])
        AnthropicDirectProvider(client=client).complete("hi")
        rows = [json.loads(x) for x in tmp_retry_file.read_text(encoding="utf-8").splitlines()]
        assert rows and rows[0]["provider"] == "anthropic-direct"

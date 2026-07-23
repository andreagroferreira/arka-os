"""Tests for core.runtime.ollama_discovery — Model Fabric PR-C."""

from __future__ import annotations

import json
from unittest.mock import patch

from core.runtime.ollama_discovery import OllamaStatus, discover


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


def _tags_body() -> bytes:
    return json.dumps({"models": [
        {"name": "kimi-k2.6:cloud", "size": 0,
         "details": {"family": "kimi", "parameter_size": "1T"}},
        {"name": "qwen3-coder:30b", "size": 18_600_000_000,
         "details": {"family": "qwen3", "parameter_size": "30.5B"}},
    ]}).encode("utf-8")


class TestDiscover:
    def test_running_daemon_lists_models_sorted(self):
        with patch(
            "core.runtime.ollama_discovery.urllib.request.urlopen"
        ) as mock:
            mock.return_value = _FakeResponse(_tags_body())
            status = discover()
        assert status.installed and status.running
        assert [m.name for m in status.models] == [
            "kimi-k2.6:cloud", "qwen3-coder:30b",
        ]
        assert status.models[1].size_gb == 18.6
        assert status.models[0].family == "kimi"

    def test_daemon_down_binary_present(self):
        with patch(
            "core.runtime.ollama_discovery.urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ), patch(
            "core.runtime.ollama_discovery.shutil.which",
            return_value="/usr/local/bin/ollama",
        ):
            status = discover()
        assert status.installed is True
        assert status.running is False
        assert status.models == []

    def test_not_installed_at_all(self):
        with patch(
            "core.runtime.ollama_discovery.urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ), patch(
            "core.runtime.ollama_discovery.shutil.which", return_value=None
        ):
            status = discover()
        assert status.installed is False
        assert status.running is False

    def test_respects_ollama_host_env(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_HOST", "http://gpu-box:11434/")
        with patch(
            "core.runtime.ollama_discovery.urllib.request.urlopen"
        ) as mock:
            mock.return_value = _FakeResponse(_tags_body())
            status = discover()
        assert status.host == "http://gpu-box:11434"
        assert "gpu-box" in mock.call_args[0][0]

    def test_garbage_response_degrades_to_not_running(self):
        with patch(
            "core.runtime.ollama_discovery.urllib.request.urlopen"
        ) as mock:
            mock.return_value = _FakeResponse(b"<html>proxy error</html>")
            with patch(
                "core.runtime.ollama_discovery.shutil.which",
                return_value=None,
            ):
                status = discover()
        assert status.running is False

    def test_to_dict_is_json_serialisable(self):
        with patch(
            "core.runtime.ollama_discovery.urllib.request.urlopen"
        ) as mock:
            mock.return_value = _FakeResponse(_tags_body())
            payload = json.dumps(discover().to_dict())
        assert "kimi-k2.6:cloud" in payload


class TestCliIntegration:
    def test_usage_action_handles_none_cost(self, tmp_path, monkeypatch):
        """Regression: total_cost_usd None crashed the usage table."""
        telemetry = tmp_path / "llm-cost.jsonl"
        telemetry.write_text(json.dumps({
            "ts": "2026-07-05T10:00:00+00:00", "session_id": "s",
            "provider": "ollama", "model": "kimi-k2.6:cloud",
            "tokens_in": 10, "tokens_out": 5, "cached_tokens": 0,
            "estimated_cost_usd": None, "category": "",
        }) + "\n", encoding="utf-8")
        monkeypatch.setattr(
            "core.runtime.llm_cost_telemetry.DEFAULT_TELEMETRY_PATH",
            telemetry,
        )
        from core.runtime.model_router_cli import main
        assert main(["usage", "--period", "all"]) == 0

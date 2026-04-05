"""Integration tests for Synapse bridge and hook system."""

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BRIDGE_SCRIPT = BASE_DIR / "scripts" / "synapse-bridge.py"
HOOK_SCRIPT = BASE_DIR / "config" / "hooks" / "user-prompt-submit-v2.sh"


class TestSynapseBridge:
    """Test the standalone bridge script."""

    def _run_bridge(self, input_data: dict, extra_args: list | None = None) -> dict:
        args = ["python3", str(BRIDGE_SCRIPT), "--root", str(BASE_DIR)]
        if extra_args:
            args.extend(extra_args)
        result = subprocess.run(
            args,
            input=json.dumps(input_data),
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"Bridge failed: {result.stderr}"
        return json.loads(result.stdout)

    def test_bridge_returns_json(self):
        output = self._run_bridge({"user_input": "hello"})
        assert "context_string" in output

    def test_bridge_detects_dev_department(self):
        output = self._run_bridge({"user_input": "fix the authentication bug"})
        assert "[dept:dev]" in output["context_string"]

    def test_bridge_detects_marketing_department(self):
        output = self._run_bridge({"user_input": "create an email campaign"})
        assert "[dept:marketing]" in output["context_string"]

    def test_bridge_detects_saas_department(self):
        output = self._run_bridge({"user_input": "validate my saas idea"})
        assert "[dept:saas]" in output["context_string"]

    def test_bridge_detects_brand_department(self):
        output = self._run_bridge({"user_input": "design a brand identity"})
        assert "[dept:brand]" in output["context_string"]

    def test_bridge_detects_finance_department(self):
        output = self._run_bridge({"user_input": "prepare the budget forecast"})
        assert "[dept:finance]" in output["context_string"]

    def test_bridge_includes_constitution(self):
        output = self._run_bridge({"user_input": "test"})
        assert "[Constitution]" in output["context_string"]

    def test_bridge_includes_time(self):
        output = self._run_bridge({"user_input": "test"})
        assert "[time:" in output["context_string"]

    def test_bridge_includes_quality_gate(self):
        output = self._run_bridge({"user_input": "test"})
        assert "[qg:active]" in output["context_string"]

    def test_bridge_layers_output(self):
        output = self._run_bridge({"user_input": "deploy the app"}, ["--layers-only"])
        assert "layers" in output
        assert "total_ms" in output
        assert "cache_stats" in output
        layer_ids = [l["id"] for l in output["layers"]]
        assert "L0" in layer_ids  # Constitution
        assert "L7" in layer_ids  # Time

    def test_bridge_command_hints(self):
        output = self._run_bridge({"user_input": "validate my saas idea"})
        assert "[hint:" in output["context_string"]

    def test_bridge_performance(self):
        """Bridge should complete in under 500ms (including Python startup)."""
        start = time.time()
        self._run_bridge({"user_input": "quick test"})
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 500, f"Bridge took {elapsed_ms:.0f}ms, expected <500ms"

    def test_bridge_empty_input(self):
        output = self._run_bridge({})
        assert "context_string" in output

    def test_bridge_invalid_root(self):
        result = subprocess.run(
            ["python3", str(BRIDGE_SCRIPT), "--root", "/nonexistent"],
            input="{}",
            capture_output=True, text=True, timeout=10,
        )
        # Should degrade gracefully, not crash
        output = json.loads(result.stdout)
        assert "context_string" in output


class TestHookIntegration:
    """Test the actual Bash hook script."""

    def _run_hook(self, user_input: str) -> dict:
        env = os.environ.copy()
        env["ARKAOS_ROOT"] = str(BASE_DIR)
        result = subprocess.run(
            ["bash", str(HOOK_SCRIPT)],
            input=json.dumps({"userInput": user_input}),
            capture_output=True, text=True, timeout=15,
            env=env,
        )
        # Hook outputs JSON on stdout (may have metrics line too)
        lines = result.stdout.strip().split("\n")
        return json.loads(lines[0])

    def test_hook_returns_additional_context(self):
        output = self._run_hook("hello")
        assert "additionalContext" in output

    def test_hook_detects_department(self):
        output = self._run_hook("fix the security vulnerability")
        assert "[dept:dev]" in output["additionalContext"]

    def test_hook_includes_constitution(self):
        output = self._run_hook("test")
        assert "[Constitution]" in output["additionalContext"]

    def test_hook_includes_time(self):
        output = self._run_hook("test")
        assert "[time:" in output["additionalContext"]

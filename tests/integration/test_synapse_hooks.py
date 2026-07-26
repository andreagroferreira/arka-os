"""Integration tests for Synapse bridge and hook system."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BRIDGE_SCRIPT = BASE_DIR / "scripts" / "synapse-bridge.py"
HOOK_SCRIPT = BASE_DIR / "config" / "hooks" / "user-prompt-submit.sh"


class TestSynapseBridge:
    """Test the standalone bridge script."""

    def _run_bridge(self, input_data: dict, extra_args: list | None = None) -> dict:
        # sys.executable, not bare python3: the ambient interpreter lacks
        # PyYAML on dev machines (see test_python_resolver_consolidation).
        args = [sys.executable, str(BRIDGE_SCRIPT), "--root", str(BASE_DIR)]
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

    def test_bridge_excludes_time_tag(self):
        # L7 TimeLayer removed (prompt-surface P0 2026-07-08): the tag was a
        # per-turn cache-buster with no consumer rule.
        output = self._run_bridge({"user_input": "test"})
        assert "[time:" not in output["context_string"]

    def test_bridge_includes_quality_gate(self):
        output = self._run_bridge({"user_input": "test"})
        assert "[qg:active]" in output["context_string"]

    def test_bridge_layers_output(self):
        output = self._run_bridge({"user_input": "deploy the app"}, ["--layers-only"])
        assert "layers" in output
        assert "total_ms" in output
        assert "cache_stats" in output
        layer_ids = [layer["id"] for layer in output["layers"]]
        assert "L0" in layer_ids  # Constitution
        assert "L7" not in layer_ids  # TimeLayer removed (prompt-surface P0)

    def test_bridge_command_hints(self):
        output = self._run_bridge({"user_input": "validate my saas idea"})
        assert "[hint:" in output["context_string"]

    def test_bridge_performance(self):
        """Bridge completes within budget, including Python startup.

        2s, not the old 500ms: with a fully-provisioned interpreter the
        bridge loads the fastembed model (~1.1s measured on the reference
        machine) — the 500ms figure dated from a bridge that failed fast
        on a yaml-less python3. Tightening this back is the per-turn
        latency work tracked by the UserPromptSubmit budget PR (deadline
        + degraded emission), not a test-side constant.
        """
        start = time.time()
        self._run_bridge({"user_input": "quick test"})
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 2000, f"Bridge took {elapsed_ms:.0f}ms, expected <2000ms"

    def test_bridge_empty_input(self):
        output = self._run_bridge({})
        assert "context_string" in output

    def test_bridge_invalid_root(self):
        result = subprocess.run(
            [sys.executable, str(BRIDGE_SCRIPT), "--root", "/nonexistent"],
            input="{}",
            capture_output=True, text=True, timeout=10,
        )
        # Should degrade gracefully, not crash
        output = json.loads(result.stdout)
        assert "context_string" in output


class TestHookIntegration:
    """Test the actual Bash hook script."""

    def _run_hook(self, user_input: str) -> str:
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
        payload = json.loads(lines[0])
        hso = payload.get("hookSpecificOutput", {})
        assert hso.get("hookEventName") == "UserPromptSubmit", payload
        return hso.get("additionalContext", "")

    def test_hook_returns_additional_context(self):
        assert self._run_hook("hello")

    def test_hook_detects_department(self):
        context = self._run_hook("fix the security vulnerability")
        assert "[dept:dev]" in context

    def test_hook_includes_constitution(self):
        assert "[Constitution]" in self._run_hook("test")

    def test_hook_excludes_time_tag(self):
        # L7 TimeLayer removed (prompt-surface P0 2026-07-08).
        assert "[time:" not in self._run_hook("test")

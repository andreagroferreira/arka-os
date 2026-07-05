"""Tests for the fusion default-panel builder."""

from __future__ import annotations

from unittest.mock import patch

from core.fusion.panel_builder import default_panel, describe_panel
from core.runtime.model_router import FusionConfig, ModelsConfig, RoleChoice
from core.runtime.ollama_discovery import OllamaModel, OllamaStatus


def _config(panel=None):
    return ModelsConfig(
        aliases={"runtime": {"best": "opus", "default": "sonnet"}},
        roles={},
        fusion=FusionConfig(
            judge=RoleChoice(provider="runtime", model="best", effort="max"),
            panel=panel or [],
        ),
    )


class TestDefaultPanel:
    def test_explicit_panel_is_respected(self):
        explicit = [RoleChoice(provider="ollama", model="x", effort="max")]
        panel, judge = default_panel(_config(panel=explicit))
        assert panel == explicit
        assert judge.model == "best"

    def test_builds_from_running_ollama(self):
        status = OllamaStatus(installed=True, running=True, host="h", models=[
            OllamaModel(name="gemma4:31b", size_gb=19.9, family="gemma", parameter_size="31B"),
            OllamaModel(name="kimi:cloud", size_gb=0.0, family="kimi", parameter_size="1T"),
            OllamaModel(name="tiny:1b", size_gb=0.9, family="x", parameter_size="1B"),
        ])
        with patch("core.runtime.ollama_discovery.discover", return_value=status):
            panel, _ = default_panel(_config())
        providers = [c.provider for c in panel]
        assert providers[0] == "runtime"                # runtime seat first
        assert providers.count("ollama") == 2           # two panel-grade locals
        models = {c.model for c in panel}
        assert "tiny:1b" not in models                  # <4GB, not cloud → excluded

    def test_no_ollama_yields_runtime_only(self):
        status = OllamaStatus(installed=False, running=False, host="h", models=[])
        with patch("core.runtime.ollama_discovery.discover", return_value=status):
            panel, _ = default_panel(_config())
        assert len(panel) == 1 and panel[0].provider == "runtime"

    def test_discover_failure_degrades_to_runtime_only(self):
        with patch("core.runtime.ollama_discovery.discover",
                   side_effect=OSError("no ollama")):
            panel, _ = default_panel(_config())
        assert len(panel) == 1

    def test_describe_panel_names_seats(self):
        panel = [
            RoleChoice(provider="runtime", model="default", effort="high"),
            RoleChoice(provider="ollama", model="kimi:cloud", effort="max"),
        ]
        judge = RoleChoice(provider="runtime", model="best", effort="max")
        text = describe_panel(panel, judge)
        assert "judge runtime/best" in text
        assert "runtime/default" in text and "ollama/kimi:cloud" in text


class TestCliShow:
    def test_show_prints_panel_without_running(self, capsys, monkeypatch):
        from core.fusion import cli
        monkeypatch.setattr(cli, "load_config", lambda: (_config(), "user"))
        monkeypatch.setattr(
            cli, "default_panel",
            lambda c=None: ([RoleChoice(provider="runtime", model="default", effort="high"),
                             RoleChoice(provider="ollama", model="k", effort="max")],
                            RoleChoice(provider="runtime", model="best", effort="max")),
        )
        assert cli.main(["--show"]) == 0
        assert "Fusion panel" in capsys.readouterr().out

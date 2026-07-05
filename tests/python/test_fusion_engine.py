"""Tests for core.fusion.engine — panel → judge → synthesis (PR-D)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.fusion.engine import FusionUnavailable, fuse
from core.runtime.llm_provider import LLMResponse, LLMUnavailable
from core.runtime.model_router import FusionConfig, ModelsConfig, RoleChoice


class _FakeProvider:
    def __init__(self, text: str, fail: bool = False):
        self._text = text
        self._fail = fail
        self.prompts: list[str] = []
        self.systems: list[str] = []

    def complete(self, prompt, *, max_tokens=2000, system=""):
        if self._fail:
            raise LLMUnavailable("seat down")
        self.prompts.append(prompt)
        self.systems.append(system)
        return LLMResponse(text=self._text, tokens_in=10, tokens_out=5,
                           cached_tokens=0, model="fake")


def _config(panel_specs, judge=None) -> ModelsConfig:
    return ModelsConfig(
        aliases={"ollama": {"best": "kimi-k2.6:cloud"}},
        roles={},
        fusion=FusionConfig(
            judge=judge or RoleChoice(provider="runtime", model="best", effort="max"),
            panel=[RoleChoice(provider=p, model=m, effort="max")
                   for p, m in panel_specs],
        ),
    )


def _fake_factory(mapping):
    """mapping: provider name -> _FakeProvider"""
    def factory(choice, config):
        from core.runtime.model_router import _resolve_alias
        model = _resolve_alias(config, choice.provider, choice.model)
        return mapping[choice.provider], model
    return factory


class TestFuse:
    def test_judge_receives_all_panel_answers(self):
        judge = _FakeProvider("the synthesis")
        mapping = {
            "ollama": _FakeProvider("local answer"),
            "openrouter": _FakeProvider("remote answer"),
            "runtime": judge,
        }
        config = _config([("ollama", "best"), ("openrouter", "deepseek/v4")])
        with patch("core.fusion.engine._provider_for", _fake_factory(mapping)):
            result = fuse("hard question", config=config)
        assert result.text == "the synthesis"
        judge_prompt = judge.prompts[0]
        assert "local answer" in judge_prompt
        assert "remote answer" in judge_prompt
        assert "hard question" in judge_prompt
        assert "consensus" in judge.systems[0]

    def test_alias_resolution_reaches_panel_seat(self):
        mapping = {
            "ollama": _FakeProvider("a"),
            "runtime": _FakeProvider("s"),
        }
        config = _config([("ollama", "best")])
        with patch("core.fusion.engine._provider_for", _fake_factory(mapping)):
            result = fuse("q", config=config)
        assert result.answers[0].model == "kimi-k2.6:cloud"

    def test_dead_seat_is_skipped_not_fatal(self):
        mapping = {
            "ollama": _FakeProvider("", fail=True),
            "openrouter": _FakeProvider("only survivor"),
            "runtime": _FakeProvider("synthesis"),
        }
        config = _config([("ollama", "best"), ("openrouter", "x/y")])
        with patch("core.fusion.engine._provider_for", _fake_factory(mapping)):
            result = fuse("q", config=config)
        failed = [a for a in result.answers if a.failed]
        assert len(failed) == 1
        assert "seat down" in failed[0].error

    def test_empty_panel_raises_unavailable(self):
        config = _config([])
        with pytest.raises(FusionUnavailable, match="panel is empty"):
            fuse("q", config=config)

    def test_all_seats_dead_raises_with_details(self):
        mapping = {
            "ollama": _FakeProvider("", fail=True),
            "runtime": _FakeProvider("never called"),
        }
        config = _config([("ollama", "best")])
        with patch("core.fusion.engine._provider_for", _fake_factory(mapping)):
            with pytest.raises(FusionUnavailable, match="every panel participant"):
                fuse("q", config=config)

    def test_empty_text_counts_as_failure(self):
        mapping = {
            "ollama": _FakeProvider("   "),
            "openrouter": _FakeProvider("real"),
            "runtime": _FakeProvider("synthesis"),
        }
        config = _config([("ollama", "best"), ("openrouter", "x/y")])
        with patch("core.fusion.engine._provider_for", _fake_factory(mapping)):
            result = fuse("q", config=config)
        assert [a.failed for a in result.answers] == [True, False]


class TestCli:
    def test_cli_reports_unavailable_cleanly(self, capsys):
        from core.fusion.cli import main
        with patch("core.fusion.cli.fuse",
                   side_effect=FusionUnavailable("panel is empty")):
            assert main(["question"]) == 1
        assert "panel is empty" in capsys.readouterr().err

    def test_cli_requires_prompt(self):
        from core.fusion.cli import main
        assert main([]) == 1

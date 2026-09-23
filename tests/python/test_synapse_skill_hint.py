"""Synapse L5 x the JEV skill hint (JEV Decisions Layer PR2).

Mirror of ``test_synapse.py::TestDepartmentRouteHint`` for L1: the UPS
decisions stage puts ``skill_hint`` in the bridge payload, the bridge
carries it into ``ctx.extra``, and L5 ranks the hinted command first
(after a project signal), never inventing a command the registry lacks.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from core.synapse.command_menu import (
    MENU_CAP,
    MENU_TOP_KEYWORD,
    command_department,
    skill_hint_candidates,
)
from core.synapse.layers import (
    CommandHintsLayer,
    LayerResult,
    PromptContext,
    _hinted_command,
)

REPO = Path(__file__).resolve().parents[2]
COMMANDS = [
    {"id": "dev-feature", "command": "/dev feature <d>", "department": "dev",
     "keywords": ["feature", "build"]},
    {"id": "dev-test", "command": "/dev test", "department": "dev", "keywords": ["test"]},
    {"id": "brand-colors", "command": "/brand colors", "department": "brand",
     "keywords": ["palette", "colors"]},
    {"id": "content-video", "command": "/content hyperframes", "department": "content",
     "keywords": ["render"]},
]


def _l5(prompt: str, hint: object = None, cwd: str = "") -> LayerResult:
    extra = {} if hint is None else {"skill_hint": hint}
    ctx = PromptContext(user_input=prompt, cwd=cwd, extra=extra)
    return CommandHintsLayer(COMMANDS).compute(ctx)


def _registry() -> list[dict]:
    return json.loads((REPO / "knowledge" / "commands-registry.json").read_text())["commands"]


class TestCommandHintsSkillHint:
    def test_hint_overrides_keyword(self):
        baseline = _l5("build a feature and a test")
        assert baseline.content.split(" ")[0] == "/dev"
        hinted = _l5("build a feature and a test", {"id": "brand-colors", "p": 0.9})
        assert hinted.content.startswith("/brand colors")
        assert hinted.tag.startswith("[arka:skill-hint] Skill(arka-brand) -> /brand colors")

    def test_top_two_is_kept(self):
        out = _l5("build a feature and a test", {"id": "brand-colors"})
        assert out.tag.count("[arka:skill-hint]") == 2
        assert out.tokens_est == 4

    def test_hint_fills_a_prompt_without_keywords(self):
        out = _l5("desenha uma paleta quente", {"id": "brand-colors"})
        assert out.content == "/brand colors"

    def test_hint_already_in_the_keyword_list_is_not_duplicated(self):
        out = _l5("colors palette test", {"id": "brand-colors"})
        commands = [t.split(" -> ")[1] for t in out.tag.split("[arka:skill-hint] ")[1:]]
        assert commands[0].strip() == "/brand colors" and len(set(commands)) == len(commands)

    def test_unknown_or_malformed_hint_is_ignored(self):
        baseline = _l5("build a feature").content
        for hint in ({"id": "ghost"}, {"id": ""}, {"id": None}, {"id": ["dev-test"]},
                     "brand-colors", 42, {}, {"command": "/brand colors"}):
            assert _l5("build a feature", hint).content == baseline, hint

    def test_project_signal_still_wins(self, tmp_path, monkeypatch):
        from core.synapse import layers

        monkeypatch.setattr(layers, "PROJECT_SIGNALS", {"content-video": (("hyperframes.json",),)})
        (tmp_path / "hyperframes.json").write_text("{}")
        out = _l5("build a feature", {"id": "brand-colors"}, cwd=str(tmp_path))
        assert out.content == "/content hyperframes /brand colors"

    def test_explicit_prefix_still_wins(self):
        out = _l5("/dev feature login", {"id": "brand-colors"})
        assert (out.tag, out.content) == ("", "")

    def test_hinted_command_never_does_io(self, monkeypatch):
        import builtins

        def _no_io(*_a, **_k):
            raise AssertionError("L5 hint path must not do IO")

        monkeypatch.setattr(builtins, "open", _no_io)
        ctx = PromptContext(user_input="x", extra={"skill_hint": {"id": "dev-test"}})
        assert _hinted_command(ctx, COMMANDS)[1] == "/dev test"

    def test_bridge_carries_the_hint_into_l5(self, tmp_path, monkeypatch):
        bridge = REPO / "scripts" / "synapse-bridge.py"
        spec = importlib.util.spec_from_file_location("bridge_skill_t", bridge)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module._context_extra({"skill_hint": {"id": "dev-test"}}, "s") == {
            "session_id": "s", "skill_hint": {"id": "dev-test"}}
        assert module._context_extra({"skill_hint": "dev-test"}, "s") == {"session_id": "s"}
        monkeypatch.setenv("HOME", str(tmp_path))
        out, code = module.run_bridge(
            {"user_input": "prepara uma coisa nova", "session_id": "s-skill",
             "cwd": str(tmp_path), "skill_hint": {"id": "brand-colors", "source": "jev"}},
            REPO)
        assert code == 0
        assert "[arka:skill-hint] Skill(arka-brand) -> /brand colors" in out["context_string"]


class TestSkillHintCandidates:
    def test_keyword_hits_first_then_the_department(self):
        menu = skill_hint_candidates(COMMANDS, "a palette please", "dev")
        assert [c["id"] for c in menu] == ["brand-colors", "dev-feature", "dev-test"]
        assert set(menu[0]) == {"id", "command", "description"}

    def test_no_department_no_keyword_is_empty(self):
        assert skill_hint_candidates(COMMANDS, "olá", "") == []

    def test_caps_hold_on_the_real_registry(self):
        registry = _registry()
        menu = skill_hint_candidates(registry, "build test deploy review feature api", "dev")
        assert len(menu) <= MENU_CAP and len({c["id"] for c in menu}) == len(menu)
        assert all(len(c["description"]) <= 160 for c in menu)

    def test_keyword_top_is_never_cut_by_the_department(self):
        registry = _registry()
        prompt = "build test deploy review feature api brand colors palette"
        from core.synapse.layers import _score_commands

        by_command = {c["command"]: c["id"] for c in registry}
        top = [by_command[cmd] for _, cmd, _ in _score_commands(registry, prompt)]
        menu_ids = [c["id"] for c in skill_hint_candidates(registry, prompt, "dev")]
        assert menu_ids[:MENU_TOP_KEYWORD] == list(dict.fromkeys(top))[:MENU_TOP_KEYWORD]

    def test_command_department_uses_the_prefix(self):
        assert command_department({"command": "/mkt seo-audit"}) == "marketing"
        assert command_department({"command": "/lead 1on1"}) == "lead"
        assert command_department({"command": "/arka status"}) == ""

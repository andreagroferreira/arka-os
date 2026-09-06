"""PR-A4: the explicit Skill-invocation contract.

Routing used to be fulfilled in PROSE — the model announced the squad
([arka:routing] dev -> Paulo) and never invoked the Skill tool, so the
department's workflows never entered context. These tests pin the three
Python-side surfaces of the new contract: the SessionStart constant,
the imperative L5 hint format, and the department->hub mapping proved
against the real registry and the real departments/ tree.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.hooks.session_start import _SKILL_ROUTING_CONTRACT, build_context
from core.synapse.layers import (
    _DEPT_HUB_EXCEPTIONS,
    CommandHintsLayer,
    PromptContext,
    _hint_department,
    _hub_skill,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestSessionStartContract:
    def test_contract_constant_says_what_fulfilment_is(self):
        assert "[ARKA:SKILL-CONTRACT]" in _SKILL_ROUTING_CONTRACT
        assert "Skill(" in _SKILL_ROUTING_CONTRACT
        assert "is not routing" in _SKILL_ROUTING_CONTRACT
        # The WHY, not just the WHAT — this is the phrase that names the
        # failure mode (announce-only routing carries no payload), and
        # this pin kills the mutant that strips that WHY clause from the
        # contract while leaving the bare prohibition in place.
        assert "label without the payload" in _SKILL_ROUTING_CONTRACT
        # The contract must never teach hub-name concatenation — that
        # template produced Skill(arka-lead), a hub no deploy path
        # creates (QG A4 r1, Eduardo blocker 1).
        assert "arka-<dept>" not in _SKILL_ROUTING_CONTRACT
        assert "Never derive a hub name" in _SKILL_ROUTING_CONTRACT

    def test_contract_reaches_the_model_context(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        context = build_context(str(tmp_path))
        assert "[ARKA:SKILL-CONTRACT]" in context
        # FULL ordering pin (QG A4 r2: pinning only EVIDENCE < SKILL let
        # a contract-moved-after-meta mutant survive): the skill
        # contract rides between evidence-flow and meta-tag, the
        # constitution's own order.
        assert context.index("[ARKA:EVIDENCE-FLOW]") < context.index(
            "[ARKA:SKILL-CONTRACT]"
        )
        assert context.index("[ARKA:SKILL-CONTRACT]") < context.index(
            "[ARKA:META-TAG]"
        )


class TestHubMapping:
    def test_exceptions_resolve_to_real_hub_slugs(self):
        assert _hub_skill("mkt") == "arka-marketing"
        assert _hub_skill("fin") == "arka-finance"
        assert _hub_skill("strat") == "arka-strategy"
        assert _hub_skill("lead") == "arka-leadership"
        assert _hub_skill("arka") == "arka"

    def test_map_matches_the_repo_alias_table(self):
        """QG A4 r1 blocker 2: the map shipped with three aliases while
        the repo's own table pins four — this parity pin makes the two
        drift together or fail together."""
        from tests.python.test_skill_routing_integrity import _DEPT_ALIAS

        derived = {
            slug: f"arka-{directory}" for slug, directory in _DEPT_ALIAS.items()
        }
        # The two orchestrator entries: /arka-* subcommands and the
        # universal /do router both live in the main `arka` skill.
        derived["arka"] = "arka"
        derived["do"] = "arka"
        assert derived == _DEPT_HUB_EXCEPTIONS

    def test_identity_departments_pass_through(self):
        assert _hub_skill("dev") == "arka-dev"
        assert _hub_skill("landing") == "arka-landing"

    def test_unknown_department_falls_back_never_raises(self):
        assert _hub_skill("made-up-dept") == "arka-made-up-dept"

    def test_department_falls_back_to_command_prefix(self):
        """Registry entries predating the department field still hint."""
        assert _hint_department({"command": "/dev feature"}) == "dev"
        assert _hint_department({"command": "/arka-do build"}) == "arka"
        assert _hint_department({"command": "/mkt social", "department": "mkt"}) == "mkt"

    def test_every_registry_department_resolves_to_an_existing_hub(self):
        """Structural: the 17 live department values must all map to a
        deployable hub — either the main `arka` skill or a
        departments/<dept>/ tree the deployer ships as arka-<dept>. A
        new department value in the registry without a hub breaks the
        hint into a dead instruction, which is exactly the r2 blocker
        class of PR-B5."""
        registry = json.loads(
            (REPO_ROOT / "knowledge" / "commands-registry.json").read_text(
                encoding="utf-8"
            )
        )
        departments = {
            str(c.get("department", "")) for c in registry["commands"]
        }
        departments.discard("")
        shipped = {
            f"arka-{d.name}"
            for d in (REPO_ROOT / "departments").iterdir()
            if d.is_dir()
        }
        shipped.add("arka")  # the main orchestrator skill
        orphans = sorted(
            dept for dept in departments if _hub_skill(dept) not in shipped
        )
        assert orphans == [], (
            f"registry departments with no shipped hub: {orphans}"
        )


class TestImperativeHintFormat:
    def test_hint_names_the_exact_call(self):
        layer = CommandHintsLayer(commands=[
            {
                "command": "/mkt social <topic>",
                "department": "mkt",
                "keywords": ["social", "post"],
            },
        ])
        result = layer.compute(PromptContext(user_input="write a social post"))
        assert (
            "[arka:skill-hint] Skill(arka-marketing) -> /mkt social <topic>"
            in result.tag
        )

    def test_best_match_leads_and_zero_scores_never_appear(self):
        """Two behaviour pins the format tests alone cannot carry: the
        top-scoring command must come FIRST in the tag (a dropped sort
        still passes any presence/count assert), and a command with no
        keyword hit must never be hinted (score > 0, not >= 0)."""
        layer = CommandHintsLayer(commands=[
            {"command": "/dev api", "department": "dev",
             "keywords": ["build"]},
            {"command": "/dev feature", "department": "dev",
             "keywords": ["build", "feature"]},
            {"command": "/mkt social", "department": "mkt",
             "keywords": ["unrelated"]},
        ])
        result = layer.compute(
            PromptContext(user_input="build a feature")
        )
        assert result.tag.index("/dev feature") < result.tag.index("/dev api")
        assert "/mkt social" not in result.tag

    def test_single_match_never_drags_a_zero_score_in(self):
        """The top-2 window must never be padded with non-matches: with
        one real match and one zero-score command, exactly one hint —
        this is the pin that kills a `score > 0` -> `>= 0` mutant,
        which the three-command scenario above cannot (its top-2 cut
        hides the zero)."""
        layer = CommandHintsLayer(commands=[
            {"command": "/dev feature", "department": "dev",
             "keywords": ["feature"]},
            {"command": "/mkt social", "department": "mkt",
             "keywords": ["unrelated"]},
        ])
        result = layer.compute(PromptContext(user_input="new feature"))
        assert result.tag.count("[arka:skill-hint]") == 1
        assert "/mkt social" not in result.tag

    def test_each_hint_pairs_the_hub_with_its_own_command(self):
        """QG A4 Francisca B1 — the load-bearing pairing of the whole
        PR: when the top-2 spans TWO departments, each hint must carry
        its own command's hub. Every earlier hub-pairing pin used
        same-hub pairs or a single hint, so a mutant that binds every
        hint to the top-1 department's hub survived the full suite. Reachable on the live
        registry ('standup color palette' -> brand + pm)."""
        layer = CommandHintsLayer(commands=[
            {"command": "/dev feature", "department": "dev",
             "keywords": ["build", "feature"]},
            {"command": "/mkt social", "department": "mkt",
             "keywords": ["build"]},
        ])
        result = layer.compute(PromptContext(user_input="build a feature"))
        assert (
            "[arka:skill-hint] Skill(arka-dev) -> /dev feature"
            in result.tag
        )
        assert (
            "[arka:skill-hint] Skill(arka-marketing) -> /mkt social"
            in result.tag
        )

    def test_content_channel_still_carries_the_commands(self):
        """QG A4 r2: nothing pinned LayerResult.content, so a mutant
        emptying it survived. The content channel feeds token
        estimation and downstream consumers — it must keep listing the
        hinted commands."""
        layer = CommandHintsLayer(commands=[
            {"command": "/dev feature", "department": "dev",
             "keywords": ["feature"]},
        ])
        result = layer.compute(PromptContext(user_input="new feature"))
        assert "/dev feature" in result.content
        assert result.tokens_est > 0

    def test_legacy_hint_form_is_gone(self):
        layer = CommandHintsLayer(commands=[
            {"command": "/dev feature", "department": "dev",
             "keywords": ["feature"]},
        ])
        result = layer.compute(PromptContext(user_input="new feature"))
        assert "[hint:" not in result.tag

    def test_exception_map_is_exact(self):
        """The map is a contract: adding an entry means a hub whose
        directory diverges from its department slug — enumerate it
        deliberately (and keep test_map_matches_the_repo_alias_table
        green while doing it)."""
        assert _DEPT_HUB_EXCEPTIONS == {
            "mkt": "arka-marketing",
            "fin": "arka-finance",
            "strat": "arka-strategy",
            "lead": "arka-leadership",
            "arka": "arka",
            "do": "arka",
        }

    def test_every_command_prefix_resolves_to_an_existing_hub(self):
        """QG A4 r1: the registry-departments pin alone missed the lead
        alias, because _hint_department can also derive the slug from
        the COMMAND PREFIX (entries predating the department field).
        Both vocabularies must resolve — this one covers the prefixes
        of every live registry command."""
        registry = json.loads(
            (REPO_ROOT / "knowledge" / "commands-registry.json").read_text(
                encoding="utf-8"
            )
        )
        prefixes = {
            _hint_department({"command": str(c.get("command", ""))})
            for c in registry["commands"]
        }
        prefixes.discard("")
        shipped = {
            f"arka-{d.name}"
            for d in (REPO_ROOT / "departments").iterdir()
            if d.is_dir()
        }
        shipped.add("arka")
        orphans = sorted(p for p in prefixes if _hub_skill(p) not in shipped)
        assert orphans == [], (
            f"command prefixes with no shipped hub: {orphans}"
        )


# ── Project-shape signals (hyperframes-routing, 2026-09-06) ──────────────
# `_signal_commands` looks a PROJECT_SIGNALS key up by registry id and
# skips an unknown id in silence (fail-safe by design). Silence is also
# how a renamed command would disappear from routing without a trace, so
# every signal key is pinned to a real id in the committed registry.


def test_every_project_signal_key_is_a_registry_command_id():
    import json
    from pathlib import Path

    from core.synapse.layers import PROJECT_SIGNALS

    root = Path(__file__).resolve().parents[2]
    registry = json.loads(
        (root / "knowledge" / "commands-registry.json").read_text(encoding="utf-8")
    )
    ids = {cmd.get("id") for cmd in registry["commands"]}
    missing = sorted(key for key in PROJECT_SIGNALS if key not in ids)
    assert not missing, (
        f"PROJECT_SIGNALS keys with no registry command: {missing} — the "
        "signal would go silent (no crash, no hint). Rename the key or the "
        "command table row, then regenerate with `arka-py -m core.registry.generator`."
    )


def test_project_signal_groups_are_non_empty_file_tuples():
    from core.synapse.layers import PROJECT_SIGNALS

    for key, groups in PROJECT_SIGNALS.items():
        assert groups, f"{key}: no file groups"
        for group in groups:
            assert group and all(isinstance(name, str) and name for name in group), (
                f"{key}: malformed group {group!r}"
            )

"""core.harness.spec — parity pins against the installer JS sources.

The whole reason spec.py exists is to give Python a copy of the desired
state that today lives only in installer JavaScript. Two copies of one
truth drift silently — so these tests PARSE the JS sources and assert
equality. Editing installer/hard-deny.js or the claude-code adapter
without updating core/harness/spec.py (or vice versa) fails here.
"""

import json
import re
from pathlib import Path

import pytest

from core.harness.spec import (
    HARD_DENY_RULES,
    SUPPORTED_RUNTIMES,
    spec_for,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
HARD_DENY_JS = REPO_ROOT / "installer" / "hard-deny.js"
ADAPTER_JS = REPO_ROOT / "installer" / "adapters" / "claude-code.js"
SETTINGS_TEMPLATE = REPO_ROOT / "config" / "settings-template.json"
HOOKS_DIR = REPO_ROOT / "config" / "hooks"


def js_hard_deny_rules() -> list[str]:
    source = HARD_DENY_JS.read_text(encoding="utf-8")
    match = re.search(
        r"export const DEFAULT_HARD_DENY_RULES = \[(.*?)\];",
        source,
        re.DOTALL,
    )
    assert match, "DEFAULT_HARD_DENY_RULES array not found in hard-deny.js"
    return re.findall(r'"([^"]+)"', match.group(1))


def js_hook_registrations() -> set[tuple]:
    """(event, script, timeout, matcher) tuples the adapter registers."""
    source = ADAPTER_JS.read_text(encoding="utf-8")
    registrations = {
        (event, script, int(timeout), None)
        for event, script, timeout in re.findall(
            r"settings\.hooks\.(\w+)\s*=\s*\[\s*"
            r"\{\s*hooks:\s*\[hookEntry\(hooksDir,\s*\"([\w-]+)\",\s*(\d+)\)\]",
            source,
        )
    }
    push = re.search(
        r"settings\.hooks\.(\w+)\.push\(\{\s*matcher:\s*\"(\w+)\","
        r".*?command:\s*join\(hooksDir,\s*\"([\w-]+)\.sh\"\),"
        r".*?timeout:\s*(\d+)",
        source,
        re.DOTALL,
    )
    assert push, "Task-matcher push not found in the adapter"
    event, matcher, script, timeout = push.groups()
    registrations.add((event, script, int(timeout), matcher))
    return registrations


def template_hook_registrations() -> set[tuple]:
    """(event, script, timeout, matcher) tuples the settings template declares."""
    template = json.loads(SETTINGS_TEMPLATE.read_text(encoding="utf-8"))
    registrations = set()
    for event, entries in template["hooks"].items():
        for entry in entries:
            for hook in entry["hooks"]:
                command = hook["command"]
                assert command.startswith("{{HOOKS_DIR}}/"), command
                script = command.removeprefix("{{HOOKS_DIR}}/").removesuffix(".sh")
                registrations.add(
                    (event, script, int(hook["timeout"]), entry.get("matcher"))
                )
    return registrations


class TestHardDenyParity:
    def test_rules_match_the_js_source_in_content_and_order(self):
        assert list(HARD_DENY_RULES) == js_hard_deny_rules()

    def test_rule_list_is_not_trivially_small(self):
        """A parity test comparing two empty lists proves nothing — the
        extraction itself must have found a real corpus."""
        assert len(js_hard_deny_rules()) >= 20


class TestHookRegistrationParity:
    def test_registrations_match_the_adapter(self):
        spec = spec_for("claude-code")
        ours = {
            (r.event, r.script, r.timeout, r.matcher)
            for r in spec.hook_registrations
        }
        assert ours == js_hook_registrations()

    def test_task_matcher_flags_reflect_the_adapter_guard(self):
        """The agent-provision registration is POSIX-only and conditional
        on the deployed script — the adapter encodes that as an
        existsSync guard inside a !IS_WINDOWS branch. Pin the guard so
        a silent removal on either side surfaces here."""
        source = ADAPTER_JS.read_text(encoding="utf-8")
        assert re.search(
            r"!IS_WINDOWS && existsSync\("
            r"join\(hooksDir, \"agent-provision\.sh\"\)\)",
            source,
        )
        task_regs = [
            r
            for r in spec_for("claude-code").hook_registrations
            if r.matcher == "Task"
        ]
        assert len(task_regs) == 1
        assert task_regs[0].posix_only
        assert task_regs[0].conditional

    def test_hook_extraction_found_a_real_corpus(self):
        """Same guard the deny side has: an adapter reformat that
        defeats the extraction regex must read as an extraction break,
        not as a shrunken-but-equal set."""
        assert len(js_hook_registrations()) >= 10

    def test_event_names_are_unique_except_pre_tool_use(self):
        spec = spec_for("claude-code")
        events = [r.event for r in spec.hook_registrations]
        duplicated = {e for e in events if events.count(e) > 1}
        assert duplicated == {"PreToolUse"}

    def test_status_line_surface_is_backed_by_the_adapter(self):
        source = ADAPTER_JS.read_text(encoding="utf-8")
        assert "settings.statusLine = {" in source
        surfaces = {s.surface for s in spec_for("claude-code").surfaces}
        assert "settings:statusLine" in surfaces


class TestSettingsTemplateParity:
    """config/settings-template.json is a THIRD copy of the registrations.

    It is install.sh's executed path, not the npm installer's (the template
    is merged verbatim into settings.json, install.sh:1029), and the
    reference every other writer is pinned to
    (tests/installer/hook-consistency.test.js). It declared 7
    of the adapter's 11 registrations and a 5 s SessionStart for months
    (Runtime Sync PR1). Pin it to the spec, which is pinned to the adapter,
    and the three surfaces cannot drift again.
    """

    def test_template_registers_exactly_the_spec(self):
        spec = spec_for("claude-code")
        ours = {
            (r.event, r.script, r.timeout, r.matcher)
            for r in spec.hook_registrations
        }
        assert template_hook_registrations() == ours

    def test_template_extraction_found_a_real_corpus(self):
        assert len(template_hook_registrations()) >= 10

    def test_every_template_script_ships(self):
        missing = sorted(
            script
            for _, script, _, _ in template_hook_registrations()
            if not (HOOKS_DIR / f"{script}.sh").is_file()
        )
        assert missing == [], f"template points at hooks that do not ship: {missing}"


class TestRuntimeKeying:
    def test_supported_runtimes(self):
        assert SUPPORTED_RUNTIMES == ("claude-code",)

    def test_unknown_runtime_is_an_explicit_error(self):
        with pytest.raises(ValueError, match="unknown runtime 'betamax'"):
            spec_for("betamax")

    def test_spec_surfaces_carry_manifest_policy_values(self):
        from core.harness.manifest import OwnershipPolicy

        for surface in spec_for("claude-code").surfaces:
            OwnershipPolicy(surface.policy)

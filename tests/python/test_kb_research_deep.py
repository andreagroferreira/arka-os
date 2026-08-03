"""The kb/research-deep skill quotes the NotebookLM chokepoint contract
in prose. Prose drifts silently; this pins every quoted fact to the real
module, so a rename in core.kb.nlm_client fails here instead of leaving
an agent following a wrong instruction (QG D3 r1, Francisca B2).

Also pins the shell-injection fix (QG D3 r1, Francisca B1, reproduced
live): the documented commands must never interpolate research text
into a shell string.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.kb import nlm_client

_REPO = Path(__file__).resolve().parents[2]
_SOURCE = _REPO / "departments" / "kb" / "skills" / "research-deep" / "SKILL.md"
_MIRROR = (
    _REPO / "plugins" / "arkaos-kb" / "skills" / "research-deep" / "SKILL.md"
)


@pytest.fixture(scope="module")
def skill_text() -> str:
    return _SOURCE.read_text(encoding="utf-8")


def test_source_and_generated_mirror_both_exist(skill_text):
    assert skill_text
    assert _MIRROR.is_file(), "marketplace_gen must have mirrored the skill"


@pytest.mark.parametrize("action", sorted(nlm_client.ALLOWED_ACTIONS))
def test_every_allowed_action_is_documented(skill_text, action):
    assert action in skill_text, (
        f"ALLOWED_ACTIONS member {action!r} is undocumented — the skill "
        f"lists the actions an agent may pass to send()"
    )


def test_documented_output_format_is_allowed(skill_text):
    """The rung-2 command names a format; it must be in ALLOWED_FORMATS."""
    used = set(re.findall(r'output_format="([a-z]+)"', skill_text))
    assert used, "the rung-2 command must name an output_format"
    assert used <= nlm_client.ALLOWED_FORMATS


_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_SPAN_RE = re.compile(r"`([^`\n]+)`")


def _code_regions(text: str) -> list[str]:
    """Fenced blocks plus inline spans — the places a field NAME counts
    as documented.

    Fenced blocks are cut out BEFORE inline spans are matched: a naive
    inline regex pairs a fence's leftover backticks with the next
    backtick in the document and captures whole prose paragraphs as
    "spans", which is how the previous version of this pin stayed
    vacuous (QG D3 aggregation, Marta — reproduced by mutation).
    """
    fenced = _FENCE_RE.findall(text)
    prose = _FENCE_RE.sub("\n", text)
    return fenced + _INLINE_SPAN_RE.findall(prose)


@pytest.mark.parametrize(
    "field", ["ok", "denied", "degraded", "reason", "stdout", "payload_sha256"]
)
def test_documented_result_fields_exist_on_the_dataclass(skill_text, field):
    assert hasattr(nlm_client.NotebookLMResult(action="ask"), field)
    # A bare substring is vacuous for the short names — "ok" hides inside
    # "notebook", "reason" inside "egress_reason" (QG D3 r3, Francisca
    # M5). Require the field as a WHOLE TOKEN inside a code region.
    token = re.compile(rf"\b{re.escape(field)}\b")
    assert any(token.search(region) for region in _code_regions(skill_text)), (
        f"{field} appears in no code region as a whole token — the prose "
        f"does not actually document the field"
    )


def test_marker_prefix_matches_the_real_property(skill_text):
    marker = nlm_client.NotebookLMResult(
        action="ask", reason="tool absent"
    ).marker
    prefix = marker.split(" (")[0]
    assert prefix == "[arka:source-skipped] notebooklm"
    assert prefix in skill_text


def test_install_hint_matches_the_modules_own_guidance(skill_text):
    fragment = "uv tool install 'notebooklm-py[browser]'"
    assert fragment in nlm_client._ABSENT
    assert fragment in skill_text


def test_chokepoint_module_path_is_named(skill_text):
    assert "core.kb.nlm_client" in skill_text
    assert "from core.kb.nlm_client import" in skill_text


def test_no_shell_interpolation_of_research_text(skill_text):
    """The gap must reach Python through a file, never through the shell.

    `arka-py -c "..."` with a substituted question executes backticks
    and $(...) from the research text — reproduced live in QG D3 r1.
    """
    assert 'arka-py -c "' not in skill_text, (
        "double-quoted -c template reintroduces the injection: use a "
        "quoted heredoc plus a scratch file"
    )
    assert "<<'PY'" in skill_text, "the documented heredoc must be quoted"
    assert "read_text()" in skill_text, (
        "the gap must be read from a file, not interpolated"
    )
    # The path must be BUILT, not interpolated either (QG D3 r3,
    # Francisca M4: read_text() alone was satisfied by the old
    # agent-chosen-path form this fix replaced).
    assert 'Path.home() / ".arkaos" / "tmp"' in skill_text, (
        "the scratch path must be built from Path.home(), not pasted in"
    )
    assert "unlink()" in skill_text, (
        "the gap file must be consumed, so a stale read fails loudly "
        "instead of re-sending the previous session's question"
    )


def test_mandatory_mcp_tools_are_declared(skill_text):
    """Rung 1 and rung 4 instruct MCP tools; allowed-tools must list
    them or the KB-first rung silently degrades (Francisca B3)."""
    header = skill_text.split("---")[1]
    for tool in ("mcp__obsidian__search_notes", "mcp__obsidian__write_note"):
        assert tool in header, f"{tool} is instructed but not declared"


def test_provenance_is_first_party(skill_text):
    from core.provenance import FIRST_PARTY

    assert f"origin: {FIRST_PARTY}" in skill_text

"""Lock: compiled agent description windows never silently evict.

PR #462's gate found that prepending into expertise.domains is a silent
delete: the compiler renders only the head of the list into the
subagent-selection description. The first version of this lock substring-
matched whole files and false-passed on its own pinned token ("Krug" also
appears in a frameworks list). This version parses the rendered
description line itself and asserts a superset against a committed
per-agent fixture, on both surfaces.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_COMPILER_CAP = 8
_HARNESS_CAP = 8

# Identity domains that must render inside the window, per agent, per
# surface. These are the ten capabilities the PR-462 regression evicted,
# expressed as substrings of the PARSED description line only.
_FIXTURE = {
    "config/claude-agents/frontend-dev.md": ["Nuxt 3", "dev/diagram"],
    "config/claude-agents/visual-designer.md": ["logo concepts", "mockup generation"],
    "config/claude-agents/brand-director.md": ["UX/UI strategy"],
    "config/claude-agents/design-ops-lead.md": ["figma → code pipelines"],
    "config/claude-agents/extraction-script-writer.md": ["spacing and grid token inference"],
    "config/claude-agents/ux-designer.md": ["guerrilla / lightweight usability testing"],
    "harness/opencode/agents/arka-brand-director-valentina.md": ["brand voice"],
    "harness/opencode/agents/arka-design-ops-lead-iris.md": ["cross-platform tokenisation"],
}


def _description_line(path: Path) -> str:
    """The single rendered domains line, not the whole file."""
    text = path.read_text(encoding="utf-8")
    if "config/claude-agents" in str(path):
        # `description: >` is a folded scalar; the rendered domains live on
        # the indented "Executes: ..." continuation line.
        match = re.search(r"^  .*Executes: .*$", text, re.M)
    else:  # harness mirrors render a flat Expertise line
        match = re.search(r"^Expertise: .*$", text, re.M)
    assert match, f"no rendered domains line found in {path}"
    return match.group(0)


def test_compiler_cap_is_pinned():
    src = (_ROOT / "core/agents/behavioral_compiler.py").read_text(encoding="utf-8")
    matches = re.findall(r'\.get\("domains", \[\]\)\[:(\d+)\]', src)
    assert len(matches) == 1, "expected exactly one domains slice in the compiler"
    assert int(matches[0]) == _COMPILER_CAP


def test_harness_cap_is_pinned():
    src = (_ROOT / "scripts/harness_gen.py").read_text(encoding="utf-8")
    matches = re.findall(r'agent\.get\("expertise_domains", \[\]\)\[:(\d+)\]', src)
    assert len(matches) == 1, "expected exactly one expertise slice in harness_gen"
    assert int(matches[0]) == _HARNESS_CAP


def test_identity_domains_render_inside_the_window():
    missing = []
    for rel, tokens in _FIXTURE.items():
        line = _description_line(_ROOT / rel).lower()
        for token in tokens:
            if token.lower() not in line:
                missing.append(f"{rel}: {token!r} not in the rendered description")
    assert not missing, (
        "identity capabilities evicted from the rendered window "
        "(the PR-462 prepend class):\n  " + "\n  ".join(missing)
    )

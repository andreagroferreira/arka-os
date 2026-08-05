"""Lock: the compiled agent description window never silently evicts.

PR #462's Quality Gate found that prepending into expertise.domains is a
silent delete: behavioral_compiler renders only the head of the list into
the subagent-selection description, so a purely additive YAML diff can
evict identity capabilities from every shipped agent definition. Two live
routing breaks shipped that way (/brand logo and /brand mockup lost their
executing agent's advertisement) before review caught it.

Two locks:

1. The concrete regression: the ten capabilities the PR-462 round proved
   evicted must render in their agents' compiled descriptions.
2. The class: every agent whose domains exceed the render window carries
   its window-relevant identity in the head — enforced by requiring that
   the compiler's cap constant matches what this test expects, so a cap
   change is a conscious, reviewed act rather than drift.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# The compiler's render cap, pinned. If you change [:8] in
# behavioral_compiler.py, this test forces you to re-audit every agent
# whose list exceeds the window before the change ships.
_COMPILER_CAP = 8


def test_compiler_cap_is_pinned():
    src = (_ROOT / "core/agents/behavioral_compiler.py").read_text(encoding="utf-8")
    match = re.search(r'\.get\("domains", \[\]\)\[:(\d+)\]', src)
    assert match, "behavioral_compiler no longer slices domains — update this lock"
    assert int(match.group(1)) == _COMPILER_CAP, (
        f"compiler window changed to [:{match.group(1)}] — re-audit every "
        "agent with more domains than the window, then update _COMPILER_CAP"
    )


def test_pr462_evictions_stay_restored():
    """The ten capabilities evicted by the prepend regression, pinned."""
    expected = {
        "config/claude-agents/frontend-dev.md": ["Nuxt 3", "dev/diagram"],
        "config/claude-agents/visual-designer.md": [
            "logo concepts", "mockup generation"],
        "config/claude-agents/brand-director.md": ["UX/UI strategy"],
        "config/claude-agents/design-ops-lead.md": ["figma → code pipelines"],
        "config/claude-agents/extraction-script-writer.md": [
            "spacing and grid token inference"],
        "config/claude-agents/ux-designer.md": ["Krug"],
        "harness/opencode/agents/arka-brand-director-valentina.md": [
            "brand voice"],
        "harness/opencode/agents/arka-design-ops-lead-iris.md": [
            "cross-platform tokenisation"],
    }
    missing = []
    for rel, tokens in expected.items():
        text = (_ROOT / rel).read_text(encoding="utf-8").lower()
        for token in tokens:
            if token.lower() not in text:
                missing.append(f"{rel}: {token!r}")
    assert not missing, (
        "identity capabilities evicted from compiled agent descriptions "
        "(the PR-462 prepend regression):\n  " + "\n  ".join(missing)
    )

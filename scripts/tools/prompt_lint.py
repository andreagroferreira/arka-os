"""Prompt-surface linter (PR-2 of the 2026-07-08 prompt-surface plan).

Locks the coherence invariants that PR-1 (#255) restored, so they cannot
silently regress. Each check mirrors a defect class found by the prompt
audit (Obsidian: "Projects/WizardingCode Internal/ArkaOS/Prompt Audit —
system_prompts_leaks 2026-07-08"):

1. model-policy single source  — no "ALWAYS ... model: opus" restatements;
   constitution `quality_gate.model_policy` is the only authority.
2. AI-cliche list sync         — constitution `no-ai-cliches` items appear
   verbatim in eduardo-copy.md and equal copy-director.yaml avoid_patterns.
3. trivial-bypass wording      — the "imperative verb" drift may not return.
4. retired counts              — hand-typed agent/skill counts stay out of
   prompt surfaces (docs surfaces are covered by test_docs_consistency).
5. evidence-flow restatements  — the full 4-gate block lives only in the
   canonical spec + the runtime delivery surfaces.
6. [time:X] tag                — the cache-buster stays dead.
7. NON-NEGOTIABLE ratchet      — marker count may only go DOWN (the
   constitution-compaction PR lowers the baseline; growth fails CI).

Run: ``python -m scripts.tools.prompt_lint`` (or via arka-py). Exit 0 =
clean; exit 1 = violations printed one per line as ``file: message``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# Prompt surfaces governed by this linter (docs/wiki/README are covered by
# scripts/tools/docs_stats.py + test_docs_consistency.py).
_GOVERNED_GLOBS: tuple[str, ...] = (
    "CLAUDE.md",
    "arka/SKILL.md",
    "arka/skills/*/SKILL.md",
    "departments/*/SKILL.md",
    "departments/*/agents/*.yaml",
    "config/claude-agents/*.md",
    "config/constitution.yaml",
    "config/hooks/*.sh",
    "config/hooks/*.ps1",
    "core/hooks/*.py",
    "core/synapse/*.py",
)

# Decoupled proximity (QG B1): any restatement with up to 40 chars between
# ALWAYS and the model pin ("reviewers ALWAYS run on model: opus").
_MODEL_POLICY_RE = re.compile(
    r"ALWAYS\b[^\n]{0,40}?`?model:\s*opus`?", re.IGNORECASE
)
# Digit-anchored (QG B3): '165 agents' / '1190 skills' are legitimate
# future counts and must NOT be caught by the '65 agents' substring.
_RETIRED_COUNT_RES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"(?<!\d){re.escape(bad)}\b")
    for bad in (
        "65 agents", "106 agents", "56 agents", "244+ skills", "190 skills",
    )
)
_GATE_TOKENS: tuple[str, ...] = ("G1 CONTEXT", "G2 PLAN", "G3 EXECUTE", "G4 REVIEW")
# Canonical spec + the constitutional codification + runtime delivery
# surfaces (SessionStart systemMessage, per-turn [ARKA:WORKFLOW-REQUIRED])
# — the ONLY places the full block lives.
_GATE_BLOCK_ALLOWED: frozenset[str] = frozenset({
    "arka/skills/flow/SKILL.md",
    "config/constitution.yaml",
    "config/hooks/session-start.sh",
    "config/hooks/session-start.ps1",
    "core/hooks/user_prompt_submit.py",
})
# Ratchet: CASE-INSENSITIVE count across the governed globs (QG M5: a
# lowercase "non-negotiable" in prose dilutes instruction strength
# exactly like the shouted marker). May only DECREASE, with ZERO slack —
# the baseline equals the measured count so adding a single marker fails
# CI. History: 47 after PR-1 (#255); 28 after PR-3's KB-first pointer
# compaction (#257); 17 after Constitution 2.0 (PR-5) demoted 20 rules
# and realigned stale markers with the new levels. Never raise it to
# make CI pass; remove a marker instead.
_NON_NEGOTIABLE_BASELINE = 17


def _governed_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in _GOVERNED_GLOBS:
        files.extend(sorted(root.glob(pattern)))
    return [f for f in files if f.is_file()]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root))


def check_model_policy_single_source(root: Path) -> list[str]:
    """No surface may restate the QG model policy as 'ALWAYS ... opus'."""
    violations: list[str] = []
    for path in _governed_files(root):
        if _MODEL_POLICY_RE.search(_read(path)):
            violations.append(
                f"{_rel(root, path)}: restates QG model policy — reference "
                "constitution `quality_gate.model_policy` instead"
            )
    return violations


def canonical_cliche_list(root: Path) -> list[str]:
    """Extract the canonical AI-cliche items from constitution no-ai-cliches."""
    text = _read(root / "config" / "constitution.yaml")
    match = re.search(r"Zero AI cliches:\s*(.+)", text)
    if not match:
        return []
    return re.findall(r"'([^']+(?:'[^',]*)?)'(?=[,\"]|$)", match.group(1))


def check_cliche_list_sync(root: Path) -> list[str]:
    """Eduardo + copy-director must carry the canonical cliche list verbatim."""
    canonical = canonical_cliche_list(root)
    violations: list[str] = []
    if len(canonical) < 10:
        return [
            "config/constitution.yaml: no-ai-cliches list unparseable "
            f"(got {len(canonical)} items) — keep the 'Zero AI cliches:' format"
        ]
    eduardo = root / "config" / "claude-agents" / "eduardo-copy.md"
    eduardo_text = _read(eduardo)
    for item in canonical:
        if f'"{item}"' not in eduardo_text:
            violations.append(
                f"{_rel(root, eduardo)}: missing canonical cliche {item!r}"
            )
    yaml_path = (
        root / "departments" / "quality" / "agents" / "copy-director.yaml"
    )
    yaml_items = re.findall(r'^\s*-\s*"([^"]+)"\s*$', _read(yaml_path), re.M)
    missing = [i for i in canonical if i not in yaml_items]
    for item in missing:
        violations.append(
            f"{_rel(root, yaml_path)}: avoid_patterns missing canonical "
            f"cliche {item!r}"
        )
    return violations


def check_trivial_bypass_wording(root: Path) -> list[str]:
    """The '[arka:trivial] + imperative verb' drift may not return."""
    violations: list[str] = []
    for path in _governed_files(root):
        text = _read(path)
        if "imperative verb" in text and "arka:trivial" in text:
            violations.append(
                f"{_rel(root, path)}: trivial-bypass drift — canonical "
                "wording is 'single-file edit under 10 lines' (no "
                "imperative-verb clause; spec: arka/skills/flow/SKILL.md)"
            )
    return violations


def check_retired_counts(root: Path) -> list[str]:
    """Hand-typed counts that drifted from docs_stats.py stay banned."""
    violations: list[str] = []
    for path in _governed_files(root):
        text = _read(path)
        for pattern in _RETIRED_COUNT_RES:
            match = pattern.search(text)
            if match:
                violations.append(
                    f"{_rel(root, path)}: retired hand-typed count "
                    f"{match.group(0)!r} — counts come from "
                    "scripts/tools/docs_stats.py or are omitted"
                )
    return violations


def check_evidence_flow_restatements(root: Path) -> list[str]:
    """The full 4-gate block lives only in canonical + delivery surfaces.

    A one-line pointer summary naming the gates is allowed everywhere;
    a RESTATEMENT is all four gate tokens each on its own line (block
    form) or the detailed-block signature phrase.
    """
    violations: list[str] = []
    line_start = {
        token: re.compile(rf"^[\s>*#-]*{re.escape(token)}", re.M)
        for token in _GATE_TOKENS
    }
    for path in _governed_files(root):
        rel = _rel(root, path)
        if rel in _GATE_BLOCK_ALLOWED:
            continue
        text = _read(path)
        block_hits = sum(1 for rx in line_start.values() if rx.search(text))
        signature = "silence is not approval" in text.lower()
        if block_hits >= 3 or signature:
            detail = (
                f"{block_hits}/4 gate tokens in block form"
                if block_hits >= 3
                else "detailed-block signature phrase"
            )
            violations.append(
                f"{rel}: 4-gate restatement ({detail}) — reduce to a "
                "pointer at arka/skills/flow/SKILL.md"
            )
    return violations


def check_time_tag_absence(root: Path) -> list[str]:
    """The time-of-day per-turn cache-buster stays removed.

    Value-independent (QG B2): [time:night] or [time:noon] busts the
    prompt cache exactly like the original three values did.
    """
    violations: list[str] = []
    pattern = re.compile(r"\[time:[^\]]+\]")
    for path in _governed_files(root):
        if pattern.search(_read(path)):
            violations.append(
                f"{_rel(root, path)}: time-of-day tag reintroduced — it is a "
                "prompt-cache buster with no consumer rule (removed in #255)"
            )
    return violations


def check_non_negotiable_ratchet(root: Path) -> list[str]:
    """NON-NEGOTIABLE marker count may only decrease from the baseline."""
    marker = re.compile(r"NON-NEGOTIABLE", re.IGNORECASE)
    total = sum(
        len(marker.findall(_read(path))) for path in _governed_files(root)
    )
    if total > _NON_NEGOTIABLE_BASELINE:
        return [
            f"prompt surface: {total} NON-NEGOTIABLE markers > baseline "
            f"{_NON_NEGOTIABLE_BASELINE} — inflation dilutes instruction "
            "strength; demote to MUST/SHOULD or remove a marker (never "
            "raise the baseline)"
        ]
    return []


_ALL_CHECKS = (
    check_model_policy_single_source,
    check_cliche_list_sync,
    check_trivial_bypass_wording,
    check_retired_counts,
    check_evidence_flow_restatements,
    check_time_tag_absence,
    check_non_negotiable_ratchet,
)


def run_all(root: Path | None = None) -> list[str]:
    """Run every check; returns the flat list of violations."""
    base = root or _ROOT
    violations: list[str] = []
    for check in _ALL_CHECKS:
        violations.extend(check(base))
    return violations


def main() -> int:
    violations = run_all()
    for violation in violations:
        print(violation)
    if violations:
        print(f"\nprompt-lint: {len(violations)} violation(s)")
        return 1
    print("prompt-lint: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Link-integrity lock for skill docs (issue #464).

Skill docs are the agent's map of its own knowledge: a `## References`
section that promises `references/dpia-methodology.md` is an instruction to
go read that file. Nothing validated those pointers, so the promise could
rot silently — the 2026-08-06 triage found 6 compliance skills advertising
12 reference guides that were never written, plus a template that never
shipped and two cross-department paths that resolved into the wrong
department. An agent following any of them stalls or, worse, invents the
content it was told existed.

This module walks every `SKILL.md` and `references/**/*.md` under
`departments/`, pulls the pointers an agent would actually follow, and
resolves each one against disk.

Two extraction rules, both deliberately conservative — a false positive
here blocks the whole suite on prose:

1. Markdown links `[text](target)`, minus external schemes and anchors.
2. Backticked tokens that start with a repo top-level directory AND end in
   a file extension — the repo-relative convention used across the brand
   and dev skills (`departments/brand/references/uiux-knowledge-and-tools.md`).
   A bare `component-cookbook.md` in backticks is prose, not a path claim,
   and is NOT checked: hundreds of those name files in upstream skill repos
   that were never vendored here.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_BACKTICK = re.compile(r"`([^`\n]+)`")
# Schemes and fragments an agent resolves off-disk, plus template
# placeholders (`<slug>`, `{dept}`) that are patterns, not paths.
_OFF_DISK = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|#|//)")
_PLACEHOLDER = re.compile(r"[<>{}*]")
_FILE_EXT = re.compile(
    r"\.(?:md|markdown|html?|py|ya?ml|json|jsonc|toml|sh|mjs|jsx?|tsx?|css|txt|svg|png|jpe?g)$"
)

# A pointer whose own line declares it lives in someone else's repo is not
# a dead link — it is a correctly-attributed external reference. The
# wording is the one PR #461 established when the GSAP pack was absorbed
# without vendoring its `examples/` tree.
_UPSTREAM_ANNOTATION = re.compile(
    r"\b(?:in|from) the [\w.@/-]+ repo(?:sitory)?\b", re.IGNORECASE
)

# Vendored upstream skill trees are verbatim third-party copies. Their
# internal pointers describe the UPSTREAM layout and are correct there;
# rewriting them would corrupt the vendor provenance and be undone by the
# next re-vendor. Not ours to fix, so not ours to check.
_VENDOR_PART = "vendor"

# Illustrative targets inside example copy — the doc is SHOWING what a link
# looks like in a deliverable, not pointing at a repo file. Each entry is
# `<repo-relative doc>: {targets}` and must stay justified: a stale entry
# is caught by test_allowlist_has_no_stale_entries below.
_ALLOWLIST: dict[str, set[str]] = {
    # Example of a contextual in-body link on a SaaS marketing site.
    "departments/landing/skills/page-architect/SKILL.md": {"/features/analytics"},
    # Sample "alternatives" URL cluster in a competitor content architecture.
    "departments/marketing/skills/competitor-analysis/references/content-architecture.md": {
        "/alternatives/notion",
        "/alternatives/airtable",
        "/alternatives/monday",
    },
    # Placeholder hrefs in a copy-paste SMS consent disclosure template.
    "departments/marketing/skills/sms-campaign/references/compliance.md": {"link"},
}


def _docs() -> list[Path]:
    """Every skill doc an agent reads, minus vendored upstream trees."""
    found = set(_ROOT.glob("departments/**/SKILL.md"))
    found |= set(_ROOT.glob("departments/**/references/**/*.md"))
    return sorted(p for p in found if _VENDOR_PART not in p.parts)


def _top_level_dirs() -> tuple[str, ...]:
    return tuple(
        f"{p.name}/" for p in _ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


def _candidates(line: str, prefixes: tuple[str, ...]) -> list[str]:
    """Pointers on one line that claim to resolve against this repo."""
    out = [m.group(1).strip() for m in _MD_LINK.finditer(line)]
    for m in _BACKTICK.finditer(line):
        token = m.group(1).strip()
        if token.startswith(prefixes) and _FILE_EXT.search(token):
            out.append(token)
    return out


def _resolves(doc: Path, target: str) -> bool:
    """True if the target exists relative to its own doc or to the repo root."""
    path = target.split("#")[0].split("?")[0].strip()
    if not path:
        return True
    return (doc.parent / path).exists() or (_ROOT / path.lstrip("/")).exists()


def _dead_pointers() -> list[str]:
    """`file:line -> target` for every pointer that resolves nowhere."""
    prefixes = _top_level_dirs()
    dead: list[str] = []
    for doc in _docs():
        rel = doc.relative_to(_ROOT).as_posix()
        allowed = _ALLOWLIST.get(rel, set())
        for num, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if _UPSTREAM_ANNOTATION.search(line):
                continue
            for target in _candidates(line, prefixes):
                if target in allowed or _OFF_DISK.match(target) or _PLACEHOLDER.search(target):
                    continue
                if not _resolves(doc, target):
                    dead.append(f"{rel}:{num} -> {target}")
    return dead


def test_every_skill_doc_pointer_resolves():
    """No skill doc may point at a file that does not exist."""
    dead = _dead_pointers()
    assert not dead, (
        f"{len(dead)} dead pointer(s) in skill docs — write the file, fix the "
        f"path, or drop the promise:\n" + "\n".join(dead)
    )


def test_allowlist_has_no_stale_entries():
    """Every allowlisted target must still be an unresolved pointer.

    An allowlist entry that no longer matches anything is dead config that
    would silently start exempting a future real defect at the same path.
    """
    prefixes = _top_level_dirs()
    stale: list[str] = []
    for rel, targets in _ALLOWLIST.items():
        doc = _ROOT / rel
        if not doc.exists():
            stale.append(f"{rel}: allowlisted doc no longer exists")
            continue
        seen: set[str] = set()
        for line in doc.read_text(encoding="utf-8").splitlines():
            for target in _candidates(line, prefixes):
                if not _resolves(doc, target):
                    seen.add(target)
        for gone in sorted(targets - seen):
            stale.append(f"{rel}: '{gone}' is no longer an unresolved pointer")
    assert not stale, "Stale link-integrity allowlist entries:\n" + "\n".join(stale)

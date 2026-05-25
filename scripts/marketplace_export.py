"""Export ArkaOS skills as portable Agent Skills (PR51 v2.69.0).

Generates marketplace-ready copies of the ten outward-facing skills
identified in KB note [[2026-04-25-agent-skills-open-standard]]. The
in-tree skills under ``departments/dev/skills/<name>/`` stay
ArkaOS-specific; the exported copies under ``marketplace/skills/<name>/``
conform to the open Agent Skills spec at https://agentskills.io so
they run inside any compliant runtime (Claude Code, Codex CLI, Cursor,
VS Code Copilot, Atlassian, Figma…).

Transformations applied per skill:

1. Strip the ``<!-- arka:kb-first-prefix begin --> … <!-- arka:kb-first-prefix end -->``
   block — it depends on the Obsidian MCP which is ArkaOS-specific.
2. Rewrite the frontmatter ``name`` to drop the ``dev/`` prefix and
   keep just the slug ("code-review" instead of "dev/code-review")
   because the open spec doesn't model department namespaces.
3. Drop the ``allowed-tools`` frontmatter field — its grammar is
   Claude Code-specific.
4. Strip ArkaOS slash-command references (``/dev …``, ``/arka``) from
   prose so the skill is verb-driven, not invocation-bound.

Outputs:
  marketplace/skills/<name>/SKILL.md  — one per exported skill
  marketplace/skills/README.md        — catalog index

Non-destructive — the source skills are never modified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "departments" / "dev" / "skills"
EXPORT_DIR = REPO_ROOT / "marketplace" / "skills"


# Per KB note [[2026-04-25-agent-skills-open-standard]] §Angle-C.
EXPORTABLE_SKILLS: tuple[str, ...] = (
    "code-review",
    "tdd-cycle",
    "runbook",
    "spec",
    "db-design",
    "security-audit",
    "clean-code-review",
    "api-design",
    "refactor-plan",
    "architecture-design",
)


_KB_PREFIX_PATTERN = re.compile(
    r"<!--\s*arka:kb-first-prefix begin\s*-->.*?"
    r"<!--\s*arka:kb-first-prefix end\s*-->\n*",
    flags=re.DOTALL,
)
_SLASH_CMD_PATTERN = re.compile(
    r"\s*—\s*`/(?:dev|arka|mkt|brand|fin|strat|ecom|kb|ops|pm|saas|landing|"
    r"content|community|sales|lead|org)[^`]*`",
)
_NAME_FIELD_PATTERN = re.compile(
    r"^name:\s*(?:dev/|arka-dev-|arka-)?(.+)$", flags=re.MULTILINE
)
_ALLOWED_TOOLS_PATTERN = re.compile(
    r"^allowed-tools:\s*\[[^\]]*\]\n", flags=re.MULTILINE
)


@dataclass(frozen=True)
class ExportResult:
    """One skill's export outcome."""

    slug: str
    source_path: Path
    output_path: Path
    bytes_before: int
    bytes_after: int


def export_skill(slug: str) -> ExportResult:
    """Export a single skill to the marketplace directory.

    Raises FileNotFoundError if the source SKILL.md doesn't exist.
    """
    src = SOURCE_DIR / slug / "SKILL.md"
    if not src.exists():
        raise FileNotFoundError(f"source SKILL.md missing for {slug!r}: {src}")
    body = src.read_text(encoding="utf-8")
    converted = _convert(body)
    dst = EXPORT_DIR / slug / "SKILL.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(converted, encoding="utf-8")
    return ExportResult(
        slug=slug,
        source_path=src,
        output_path=dst,
        bytes_before=len(body),
        bytes_after=len(converted),
    )


def _convert(body: str) -> str:
    """Apply the four open-spec transformations."""
    out = _KB_PREFIX_PATTERN.sub("", body)
    out = _ALLOWED_TOOLS_PATTERN.sub("", out)
    out = _NAME_FIELD_PATTERN.sub(lambda m: f"name: {m.group(1).strip()}", out)
    out = _SLASH_CMD_PATTERN.sub("", out)
    return out.lstrip()


def export_all() -> list[ExportResult]:
    """Export every skill listed in EXPORTABLE_SKILLS."""
    return [export_skill(slug) for slug in EXPORTABLE_SKILLS]


def write_index(results: list[ExportResult]) -> Path:
    """Write the catalog README pointing at every exported skill."""
    lines = [
        "# ArkaOS — Portable Agent Skills",
        "",
        "Open-spec exports of ArkaOS's outward-facing development skills.",
        "Compatible with any Agent Skills runtime "
        "(see https://agentskills.io) — Claude Code, Codex CLI, Cursor, "
        "VS Code Copilot, Atlassian, Figma.",
        "",
        "## Install via Claude Code Plugin Marketplace",
        "",
        "Register this repository as a marketplace, then install the bundle:",
        "",
        "```",
        "/plugin marketplace add andreagroferreira/arka-os",
        "/plugin install arkaos-dev-skills@arkaos",
        "```",
        "",
        "After install, the ten skills below are available in your Claude "
        "Code session. Mention a skill by name (e.g., *\"use code-review on "
        "this PR\"*) and Claude loads the relevant `SKILL.md`.",
        "",
        "## Catalog",
        "",
    ]
    for r in sorted(results, key=lambda x: x.slug):
        lines.append(f"- [{r.slug}]({r.slug}/SKILL.md)")
    lines.append("")
    lines.append(
        "These exports are generated by `scripts/marketplace_export.py` "
        "from the in-tree skills under `departments/dev/skills/`. "
        "Do not hand-edit — re-run the export script instead."
    )
    lines.append("")
    out = EXPORT_DIR / "README.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> int:
    results = export_all()
    write_index(results)
    print(f"Exported {len(results)} skill(s) to {EXPORT_DIR}")
    for r in results:
        print(f"  {r.slug:24s} {r.bytes_before:>5}B → {r.bytes_after:>5}B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

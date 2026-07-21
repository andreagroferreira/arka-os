"""Commands registry generator — single canonical source (M2 consolidation).

Scans every SKILL.md command table in the repo (arka orchestrator,
department SKILL.md files, and department sub-skills) and generates
``knowledge/commands-registry.json`` — the one registry consumed by
runtime routing (system-prompt.sh), Synapse L5 hints (synapse-bridge),
``bin/arka commands``, the dashboard API, and ``bin/arkaos`` status.

Replaces the retired bash ``bin/arka-registry-gen`` and the parallel
``commands-registry-v2.json`` (2026-07-09): one deterministic generator,
repo sources only — machine-local ``arka-ext-*``/``arka-pro-*`` skills
are intentionally NOT scanned so the committed file is reproducible;
``tests/python/test_commands_registry.py`` locks committed-vs-regen
drift the same way the agents registry is locked.

Department naming follows the command prefixes (``mkt``/``fin``/
``strat``), matching the runtime tables in CLAUDE.md.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

# Directory name → command-prefix department slug.
DEPT_PREFIX = {
    "marketing": "mkt",
    "finance": "fin",
    "strategy": "strat",
}

# Fallback keywords per department slug when a command has no entry in
# knowledge/commands-keywords.json — feeds Synapse L5 hint matching.
DEPARTMENT_KEYWORDS: dict[str, list[str]] = {
    "dev": ["build", "code", "feature", "deploy", "test", "review", "scaffold", "debug",
            "refactor", "api", "migration", "implement", "fix", "bug", "database", "architecture"],
    "mkt": ["social", "content", "campaign", "post", "instagram", "linkedin", "twitter",
            "tiktok", "seo", "marketing", "ads", "email", "growth", "analytics"],
    "brand": ["brand", "logo", "colors", "palette", "mockup", "identity", "naming",
              "positioning", "voice", "guidelines", "ux", "wireframe", "design", "ui"],
    "fin": ["budget", "invoice", "revenue", "forecast", "profit", "financial", "invest",
            "valuation", "cashflow", "expense", "pitch", "model", "scenario"],
    "strat": ["strategy", "brainstorm", "market", "swot", "competitor", "roadmap",
              "position", "blue ocean", "five forces", "tam", "moat", "growth"],
    "ecom": ["store", "product", "shop", "shopify", "ecommerce", "catalog", "cart",
             "checkout", "pricing", "marketplace", "rfm", "conversion", "cro"],
    "kb": ["learn", "persona", "knowledge", "youtube", "transcribe", "research",
           "zettelkasten", "note", "moc", "taxonomy", "source"],
    "ops": ["automate", "workflow", "process", "sop", "bottleneck", "integration",
            "zapier", "n8n", "dashboard", "lean", "gtd"],
    "pm": ["sprint", "backlog", "standup", "retro", "scrum", "kanban", "story",
           "estimate", "roadmap", "agile", "discover", "shape"],
    "saas": ["saas", "micro-saas", "plg", "freemium", "churn", "mrr", "arr",
             "subscription", "onboarding", "metrics", "validate", "niche", "benchmark"],
    "landing": ["landing", "funnel", "copy", "headline", "offer", "launch", "affiliate",
                "webinar", "conversion", "sales page", "persuade", "cro"],
    "content": ["viral", "hook", "script", "repurpose", "youtube", "tiktok", "reels",
                "shorts", "newsletter", "creator", "thumbnail", "platform", "content system"],
    "community": ["community", "group", "membership", "discord", "telegram", "skool",
                  "circle", "gamification", "engagement", "moderate", "event"],
    "sales": ["pipeline", "proposal", "discovery", "objection", "negotiate", "deal",
              "close", "prospect", "spin", "challenger", "forecast"],
    "leadership": ["leadership", "delegation", "1on1", "feedback", "culture", "hiring",
                   "performance review", "team build", "conflict", "okr"],
    "org": ["org design", "hiring plan", "onboarding", "remote", "meeting",
            "compensation", "decision", "team assess", "sop"],
}

# Metadata rules ported verbatim from the retired bin/arka-registry-gen.
_DEV_BRANCH_WORDS = {"feature", "api", "debug", "refactor", "db"}
_DEV_MODIFY_WORDS = {"scaffold", "deploy", "test"}

_TABLE_ROW_RE = re.compile(r"\|\s*`([^`]+)`\s*\|\s*([^|]+)\|")
_FRONTMATTER_NAME_RE = re.compile(r"^name:\s*(\S+)", re.MULTILINE)


def derive_command_id(command_text: str) -> str:
    """``/arka costs [period]`` → ``arka-costs``.

    Drops everything from the first argument token (``<arg>``,
    ``[optional]``, ``--flag``) onward, so ids never embed argument
    syntax (the old ``dev-onboard---ecosystem`` class of bug).
    """
    tokens: list[str] = []
    for token in command_text.lstrip("/").split():
        if token.startswith(("<", "[", "--")):
            break
        tokens.append(token)
    return "-".join(tokens).lower()


def extract_lead_agent(text: str) -> str:
    match = _FRONTMATTER_NAME_RE.search(text)
    return match.group(1) if match else ""


def extract_commands_from_skill(skill_path: Path) -> list[dict]:
    """Extract commands from a SKILL.md file's command table.

    Parses markdown tables with | `/command` | Description | rows.
    """
    if not skill_path.exists():
        return []

    text = skill_path.read_text(encoding="utf-8")
    lead_agent = extract_lead_agent(text)
    commands = []
    for line in text.split("\n"):
        match = _TABLE_ROW_RE.match(line)
        if not match:
            continue
        command = match.group(1).strip()
        description = match.group(2).strip()
        # An ArkaOS command's head token (before the first space) is a
        # single word — `/mkt`, `/dev`. A slash INSIDE the head means it
        # is a URL example (`/features/analytics`), not a command; those
        # appear verbatim in imported site-architecture content. Slashes
        # in later `<file/pr>`-style placeholders are fine.
        if not command.startswith("/") or "Description" in description or description.startswith("-"):
            continue
        if "/" in command.split(" ")[0][1:]:
            continue
        commands.append({
            "command": command,
            "description": description,
            "lead_agent": lead_agent,
        })
    return commands


def command_metadata(command_text: str) -> dict:
    """tier / requires_branch / modifies_code — bash-generator rules."""
    if command_text.startswith("/dev "):
        first_arg = command_text.split()[1] if len(command_text.split()) > 1 else ""
        if first_arg in _DEV_BRANCH_WORDS:
            return {"tier": 1, "requires_branch": True, "modifies_code": True}
        if first_arg in _DEV_MODIFY_WORDS:
            return {"tier": 2, "requires_branch": False, "modifies_code": True}
        if first_arg == "security-audit":
            return {"tier": 1, "requires_branch": False, "modifies_code": False}
    return {"tier": 2, "requires_branch": False, "modifies_code": False}


def _load_keywords_seed(base_dir: Path) -> dict:
    seed_path = base_dir / "knowledge" / "commands-keywords.json"
    if not seed_path.exists():
        return {}
    return json.loads(seed_path.read_text(encoding="utf-8"))


def _department_slug(skill_path: Path) -> str:
    # departments/<dir>/SKILL.md and departments/<dir>/skills/<s>/SKILL.md
    parts = skill_path.parts
    dir_name = parts[parts.index("departments") + 1]
    return DEPT_PREFIX.get(dir_name, dir_name)


def _skill_sources(base_dir: Path) -> list[tuple[Path, str]]:
    """(skill_path, department) in deterministic scan order.

    Order matters: dedup keeps the FIRST occurrence of an id, so the
    orchestrator wins over departments, departments over sub-skills.
    """
    sources: list[tuple[Path, str]] = [(base_dir / "arka" / "SKILL.md", "arka")]
    for path in sorted(base_dir.glob("departments/*/SKILL.md")):
        sources.append((path, _department_slug(path)))
    for path in sorted(base_dir.glob("departments/*/skills/*/SKILL.md")):
        sources.append((path, _department_slug(path)))
    return sources


def generate_commands_registry(
    base_dir: str | Path,
    output_path: str | Path,
) -> dict:
    """Generate the canonical commands-registry.json from SKILL.md files."""
    base_dir = Path(base_dir)
    output_path = Path(output_path)
    keywords_seed = _load_keywords_seed(base_dir)

    all_commands: list[dict] = []
    seen_ids: set[str] = set()
    for skill_path, dept in _skill_sources(base_dir):
        for cmd in extract_commands_from_skill(skill_path):
            command_text = cmd["command"]
            cmd_id = derive_command_id(command_text)
            if not cmd_id or cmd_id in seen_ids:
                continue
            seen_ids.add(cmd_id)
            seed = keywords_seed.get(cmd_id, {})
            keywords = seed.get("keywords") or DEPARTMENT_KEYWORDS.get(dept, [])[:8]
            all_commands.append({
                "id": cmd_id,
                "command": command_text,
                "department": dept,
                "description": cmd["description"],
                "lead_agent": cmd["lead_agent"],
                "keywords": keywords,
                "examples": seed.get("examples", []),
                "source": "builtin",
                **command_metadata(command_text),
            })

    dept_counts: dict[str, int] = {}
    for cmd in all_commands:
        dept_counts[cmd["department"]] = dept_counts.get(cmd["department"], 0) + 1

    registry = {
        "_meta": {
            "version": "3.0.0",
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_commands": len(all_commands),
            "generator": "core/registry/generator.py",
            "departments": dict(sorted(dept_counts.items())),
        },
        "commands": all_commands,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return registry


if __name__ == "__main__":
    base = Path(__file__).parent.parent.parent
    reg = generate_commands_registry(
        base,
        base / "knowledge" / "commands-registry.json",
    )
    print(f"Registry generated: {reg['_meta']['total_commands']} commands")
    print(f"Departments: {reg['_meta']['departments']}")

"""Commands registry generator.

Scans all SKILL.md files, extracts command tables, and generates
a machine-readable JSON registry for /do routing and Synapse L5.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


# Keywords map: department → common keywords users might type
DEPARTMENT_KEYWORDS: dict[str, list[str]] = {
    "dev": ["build", "code", "feature", "deploy", "test", "review", "scaffold", "debug",
            "refactor", "api", "migration", "implement", "fix", "bug", "database", "architecture"],
    "marketing": ["social", "content", "campaign", "post", "instagram", "linkedin", "twitter",
                  "tiktok", "seo", "marketing", "ads", "email", "growth", "analytics"],
    "brand": ["brand", "logo", "colors", "palette", "mockup", "identity", "naming",
              "positioning", "voice", "guidelines", "ux", "wireframe", "design", "ui"],
    "finance": ["budget", "invoice", "revenue", "forecast", "profit", "financial", "invest",
                "valuation", "cashflow", "expense", "pitch", "model", "scenario"],
    "strategy": ["strategy", "brainstorm", "market", "swot", "competitor", "roadmap",
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
    "lead": ["leadership", "delegation", "1on1", "feedback", "culture", "hiring",
             "performance review", "team build", "conflict", "okr"],
    "org": ["org design", "hiring plan", "onboarding", "remote", "meeting",
            "compensation", "decision", "team assess", "sop"],
}


def extract_commands_from_skill(skill_path: Path) -> list[dict]:
    """Extract commands from a SKILL.md file's command table.

    Parses markdown tables with | Command | Description | format.
    """
    if not skill_path.exists():
        return []

    text = skill_path.read_text()
    commands = []

    # Find command tables (lines with | `/ ... ` | description | ...)
    for line in text.split("\n"):
        match = re.match(r"\|\s*`([^`]+)`\s*\|\s*([^|]+)\|", line)
        if match:
            command = match.group(1).strip()
            description = match.group(2).strip()
            if not command.startswith("/") or "Description" in description or description.startswith("-"):
                continue
            commands.append({
                "command": command,
                "description": description,
            })

    return commands


def determine_department(skill_path: Path) -> str:
    """Determine department from the skill file's directory."""
    # departments/dev/SKILL.md → dev
    # arka/SKILL.md → arka
    parent = skill_path.parent.name
    return parent


def extract_tier(description: str) -> int:
    """Guess command tier from description keywords."""
    desc_lower = description.lower()
    if any(w in desc_lower for w in ["full", "enterprise", "comprehensive", "complete"]):
        return 1
    if any(w in desc_lower for w in ["audit", "analysis", "strategy", "design"]):
        return 2
    return 3


def generate_commands_registry(
    base_dir: str | Path,
    output_path: str | Path,
) -> dict:
    """Generate commands-registry-v2.json from all SKILL.md files.

    Args:
        base_dir: Project root directory.
        output_path: Where to write the JSON registry.

    Returns:
        The registry dict.
    """
    base_dir = Path(base_dir)
    output_path = Path(output_path)

    all_commands = []

    # v2 department directories (exclude v1 legacy dirs)
    v2_departments = {
        "dev", "marketing", "brand", "finance", "strategy", "ecom", "kb",
        "ops", "pm", "saas", "landing", "content", "community", "sales",
        "leadership", "org", "quality",
    }

    # Scan department SKILL.md files
    for skill_file in sorted(base_dir.glob("departments/*/SKILL.md")):
        if skill_file.parent.name not in v2_departments:
            continue
        dept = determine_department(skill_file)
        raw_commands = extract_commands_from_skill(skill_file)
        keywords = DEPARTMENT_KEYWORDS.get(dept, [])

        for cmd in raw_commands:
            command_text = cmd["command"]
            # Generate ID: /dev feature → dev-feature
            cmd_id = command_text.lstrip("/").replace(" ", "-").split("<")[0].rstrip("-")

            # Determine if code-modifying
            modifies_code = dept == "dev" and any(
                w in command_text for w in ["feature", "api", "debug", "refactor", "db", "scaffold"]
            )

            all_commands.append({
                "id": cmd_id,
                "command": command_text,
                "department": dept,
                "description": cmd["description"],
                "keywords": keywords[:8],
                "tier": extract_tier(cmd["description"]),
                "modifies_code": modifies_code,
                "requires_branch": modifies_code,
            })

    # Scan orchestrator SKILL.md
    arka_skill = base_dir / "arka" / "SKILL.md"
    if arka_skill.exists():
        raw_commands = extract_commands_from_skill(arka_skill)
        for cmd in raw_commands:
            command_text = cmd["command"]
            cmd_id = command_text.lstrip("/").replace(" ", "-").split("<")[0].rstrip("-")
            all_commands.append({
                "id": cmd_id,
                "command": command_text,
                "department": "arka",
                "description": cmd["description"],
                "keywords": [],
                "tier": 3,
                "modifies_code": False,
                "requires_branch": False,
            })

    # Build department summary
    dept_counts: dict[str, int] = {}
    for cmd in all_commands:
        d = cmd["department"]
        dept_counts[d] = dept_counts.get(d, 0) + 1

    registry = {
        "_meta": {
            "version": "2.0.0",
            "generated": datetime.now().isoformat(),
            "total_commands": len(all_commands),
            "generator": "core/registry/generator.py",
            "departments": dept_counts,
        },
        "commands": all_commands,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    return registry


if __name__ == "__main__":
    base = Path(__file__).parent.parent.parent
    reg = generate_commands_registry(
        base,
        base / "knowledge" / "commands-registry-v2.json",
    )
    print(f"Generated: {reg['_meta']['total_commands']} commands")
    print(f"Departments: {reg['_meta']['departments']}")

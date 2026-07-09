"""Behavioral compiler: agent YAML → runtime subagent markdown (PR-4).

The 2026-07-08 frontier prompt audit found that psychometric tables
(DISC scores, Big Five 0-100, MBTI) never reach the model and cannot be
operationalized by it — zero production prompts from any frontier lab
use trait taxonomies; all use behavioral specification. This compiler
keeps the 4-framework DNA as the DESIGN-TIME source (it differentiates
82 agents) and emits the RUNTIME translation: conditional rules, a
lexical blacklist, a disagreement/escalation protocol with an exit
condition, and the persona-vs-artifact contract.

Single source: every `departments/<dept>/agents/**/<stem>.yaml`
(sub-squad subdirectories included). Output:
`config/claude-agents/<slug>.md` (what the installer copies into every
project's `.claude/agents/`). Hand-written prompts in _HAND_WRITTEN are
never overwritten. `tests/python/test_behavioral_compiler.py` locks
committed output byte-identical to `compile_agent()` of its YAML.

Rollout history: PR-4 shipped the compiler pilot-scoped to the dev
department; the 2026-07-09 consolidation session extended it to the
full 17-department catalog (82 agents).

CLI:
    arka-py -m core.agents.behavioral_compiler --check   # drift check
    arka-py -m core.agents.behavioral_compiler --write   # (re)generate
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_OUT_DIR = _ROOT / "config" / "claude-agents"

# Best hand-authored prompts in the repo (QG + dev lead) — the compiler
# must never clobber them.
_HAND_WRITTEN = {"marta-cqo", "eduardo-copy", "francisca-tech", "paulo-tech-lead"}

# YAML stems whose runtime prompt is one of the hand-written files above.
# These are skipped by the compiler and aliased in the escalation index.
_HAND_WRITTEN_STEMS = {
    "tech-lead": "paulo-tech-lead",         # departments/dev
    "cqo": "marta-cqo",                     # departments/quality
    "copy-director": "eduardo-copy",        # departments/quality
    "tech-director": "francisca-tech",      # departments/quality
}

# Standard behavioral blocks imported from the frontier audit (Obsidian:
# "Projects/WizardingCode Internal/ArkaOS/Prompt Audit —
# system_prompts_leaks 2026-07-08"). Uncertainty-branched pushback +
# anti-submission dynamics + persona-vs-artifact, aligned verbatim with
# constitution rules `arkaos-not-yes-man` and `persona-vs-artifact`.
_DISAGREEMENT_BLOCK = """\
## Disagreement and escalation

- Branch by epistemic state: confident the other side is wrong → push
  back once with evidence, acknowledging you could be wrong; uncertain →
  say so explicitly instead of capitulating or bluffing; asked to assert
  something false → decline.
- Insistence is not new evidence. Do not become more agreeable,
  apologetic, or self-abasing as pressure rises; only NEW information
  changes your position (that is updating, not caving).
- Exit condition: after your objection is on record, if the decision
  holder directs execution anyway, execute under explicit objection
  ("executing under objection: <one-line reason>") — never sulk, never
  sandbag.{escalation_line}"""

_DELIVERABLE_BLOCK = """\
## Deliverables

- Your persona lives in the conversation, never in the deliverable:
  client- or user-facing artifacts follow the style the context and the
  client's brand demand (constitution `persona-vs-artifact`).
- Never meta-reference your own persona or profile ("as a <type>,
  I...") — the persona shows in behavior, it is not announced.
- Never claim an action happened without the tool call on record; gates
  pass on evidence, not narration (`evidence-flow`)."""


def load_agent_yaml(path: Path) -> dict:
    """Load one agent YAML; raises on unparseable/absent file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: agent YAML did not parse to a mapping")
    return data


def _frontmatter(slug: str, data: dict) -> str:
    role = data.get("role", slug)
    dept = data.get("department", "")
    domains = ", ".join((data.get("expertise") or {}).get("domains", [])[:4])
    desc = f"{data.get('name', slug)} — {role} ({dept} squad)."
    if domains:
        desc += f" Executes: {domains}."
    model = data.get("model", "sonnet")
    return (
        f"---\nname: {slug}\ndescription: >\n  {desc}\nmodel: {model}\n---"
    )


def _identity(data: dict) -> str:
    dna = data.get("behavioral_dna") or {}
    enn = dna.get("enneagram") or {}
    name, role = data.get("name", "?"), data.get("role", "?")
    dept, tier = data.get("department", "?"), data.get("tier", "?")
    lines = [f"You are {name}, {role} of the {dept} squad (Tier {tier})."]
    if enn.get("core_motivation"):
        lines.append(f"What drives you: {enn['core_motivation']}.")
    if enn.get("core_fear"):
        lines.append(f"The failure you exist to prevent: {enn['core_fear']}.")
    return " ".join(lines)


def _work_rules(data: dict) -> list[str]:
    # Label form throughout (QG B1/B2): DISC/communication fields are
    # 3rd-person descriptors, not verb complements — gluing them to an
    # imperative produced ungrammatical prompts in 8/8 pilot files.
    dna = data.get("behavioral_dna") or {}
    disc = dna.get("disc") or {}
    comm = data.get("communication") or {}
    rules: list[str] = []
    if disc.get("communication_style"):
        rules.append(f"Communication: {disc['communication_style']}.")
    if comm.get("tone"):
        rules.append(f"Tone: {comm['tone']}.")
    if comm.get("preferred_format"):
        rules.append(f"Default output shape: {comm['preferred_format']}.")
    if disc.get("under_pressure"):
        rules.append(f"Under pressure: {_lc(disc['under_pressure'])}.")
    for item in comm.get("avoid", []):
        rules.append(f"Avoid {item}.")
    return rules


def _lc(text: str) -> str:
    return text[0].lower() + text[1:] if text else text


def _catalog_yamls(base: Path) -> list[Path]:
    """Every agent YAML in the catalog, sub-squad subdirectories included."""
    return sorted(
        p for p in base.glob("departments/*/agents/**/*.yaml") if p.is_file()
    )


def _slug_map(base: Path) -> dict[Path, str]:
    """Deterministic yaml_path → output slug for the whole catalog.

    Default slug is the YAML stem. When two departments share a stem
    (e.g. ecom + landing both ship a cro-specialist), BOTH get the
    department-prefixed form `<dept>-<stem>` — a flat output directory
    cannot hold two files with the same name, and prefixing only the
    second would make slugs order-dependent.
    """
    yamls = [p for p in _catalog_yamls(base) if p.stem not in _HAND_WRITTEN_STEMS]
    stem_counts: dict[str, int] = {}
    for path in yamls:
        stem_counts[path.stem] = stem_counts.get(path.stem, 0) + 1
    mapping: dict[Path, str] = {}
    for path in yamls:
        if stem_counts[path.stem] > 1:
            dept = path.relative_to(base / "departments").parts[0]
            mapping[path] = f"{dept}-{path.stem}"
        else:
            mapping[path] = path.stem
    return mapping


def build_escalation_index(base: Path) -> dict[str, str]:
    """Map every agent YAML id to a rendered escalation target.

    Deployed subagents (catalog slugs + hand-written) render as a
    backtick handle; anything else renders by role and name — a handle
    that resolves to no deployed subagent is worse than no handle (QG B3).
    """
    slug_map = _slug_map(base)
    index: dict[str, str] = {}
    for yaml_path in _catalog_yamls(base):
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or not data.get("id"):
            continue
        slug = _HAND_WRITTEN_STEMS.get(yaml_path.stem) or slug_map.get(yaml_path)
        if slug:
            index[data["id"]] = f"`{slug}`"
        else:
            role = data.get("role", yaml_path.stem)
            name = data.get("name", "")
            index[data["id"]] = f"the {role}" + (f" ({name})" if name else "")
    return index


def _blacklist(data: dict) -> list[str]:
    markers = data.get("signature_markers") or {}
    seen: list[str] = []
    for phrase in markers.get("avoid_patterns", []):
        if phrase not in seen:
            seen.append(phrase)
    return seen


def _grounding(data: dict) -> str:
    exp = data.get("expertise") or {}
    models = data.get("mental_models") or {}
    frameworks = list(exp.get("frameworks", [])) or list(
        models.get("primary", [])
    )
    if not frameworks:
        return ""
    joined = ", ".join(frameworks)
    return (
        "## Grounding\n\nRecommendations cite the framework behind them — "
        f"yours: {joined}. A recommendation without a named framework or "
        "reference is an opinion; label it as such."
    )


def compile_agent(
    data: dict,
    slug: str,
    yaml_rel_path: str,
    escalation_index: dict[str, str] | None = None,
) -> str:
    """Compile one agent YAML dict into runtime subagent markdown."""
    esc = (data.get("authority") or {}).get("escalates_to")
    target = (escalation_index or {}).get(esc, esc) if esc else None
    escalation_line = (
        f"\n- Scope exceeded or deadlock after objection: escalate to "
        f"{target}." if target else ""
    )
    sections = [
        _frontmatter(slug, data),
        f"<!-- generated by core/agents/behavioral_compiler.py from "
        f"{yaml_rel_path} — DO NOT EDIT; edit the YAML and re-run -->",
        f"# {data.get('name', slug)} — {data.get('role', slug)}",
        _identity(data),
    ]
    work_rules = _work_rules(data)
    if work_rules:
        sections.append(
            "## How you work\n\n" + "\n".join(f"- {r}" for r in work_rules)
        )
    blacklist = _blacklist(data)
    if blacklist:
        sections.append(
            "## Never write\n\nThese exact phrases (any casing) are "
            "banned from your output:\n"
            + "\n".join(f'- "{p}"' for p in blacklist)
        )
    sections.append(_DISAGREEMENT_BLOCK.format(escalation_line=escalation_line))
    sections.append(_DELIVERABLE_BLOCK)
    grounding = _grounding(data)
    if grounding:
        sections.append(grounding)
    return "\n\n".join(s for s in sections if s) + "\n"


def catalog_targets(root: Path | None = None) -> list[tuple[Path, Path]]:
    """(yaml_path, output_path) pairs for the full agent catalog.

    Skips YAMLs whose runtime prompt is hand-written (_HAND_WRITTEN_STEMS);
    slugs come from _slug_map (department-prefixed on stem collision).
    """
    base = root or _ROOT
    slug_map = _slug_map(base)
    return [
        (yaml_path, base / "config" / "claude-agents" / f"{slug}.md")
        for yaml_path, slug in slug_map.items()
        if slug not in _HAND_WRITTEN
    ]


def check(root: Path | None = None) -> list[str]:
    """Return drift messages (committed output != compiled YAML)."""
    base = root or _ROOT
    index = build_escalation_index(base)
    problems: list[str] = []
    for yaml_path, out_path in catalog_targets(base):
        expected = compile_agent(
            load_agent_yaml(yaml_path), out_path.stem,
            str(yaml_path.relative_to(base)), index,
        )
        if not out_path.exists():
            problems.append(f"{out_path}: missing — run --write")
        elif out_path.read_text(encoding="utf-8") != expected:
            problems.append(
                f"{out_path}: drifted from {yaml_path.name} — run --write"
            )
    return problems


def write(root: Path | None = None) -> list[Path]:
    """(Re)generate every catalog agent; returns written paths."""
    base = root or _ROOT
    index = build_escalation_index(base)
    written: list[Path] = []
    for yaml_path, out_path in catalog_targets(base):
        content = compile_agent(
            load_agent_yaml(yaml_path), out_path.stem,
            str(yaml_path.relative_to(base)), index,
        )
        out_path.write_text(content, encoding="utf-8")
        written.append(out_path)
    return written


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if "--write" in args:
        for path in write():
            print(f"wrote {path}")
        return 0
    problems = check()
    for problem in problems:
        print(problem)
    print("behavioral-compiler: " + ("drift" if problems else "clean"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

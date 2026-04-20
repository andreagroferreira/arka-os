"""Cataloger — classifies content and routes it to its taxonomic home.

Given raw content plus optional metadata, the Cataloger:
1. Classifies the note into a NoteType via deterministic heuristics.
2. Resolves the vault path from the taxonomy, filling template vars.
3. Builds frontmatter + tag set + list of MOCs to update.
4. Delegates actual writing to an ObsidianWriter (no duplicated logic).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from core.obsidian.taxonomy import (
    TAXONOMY,
    NoteType,
    TaxonomyEntry,
    extract_template_vars,
    missing_vars,
)
from core.obsidian.templates import resolve_template_vars
from core.obsidian.writer import ObsidianWriter


@dataclass(frozen=True)
class CatalogPlan:
    note_type: NoteType
    vault_path: str
    frontmatter: dict
    tags: list[str]
    applicable_mocs: list[str]
    confidence: float
    inline_moc: str | None = None


_STACK_KEYWORDS = {
    "Laravel": ("laravel", "artisan", "eloquent", "php"),
    "Vue": ("vue", "nuxt", "vuex", "pinia", "composition api"),
    "React": ("react", "next.js", "nextjs", "usestate", "useeffect", "jsx", "tsx"),
    "Python": ("python", "pydantic", "pytest", "fastapi", "django"),
    "Node": ("node.js", "express", "npm", "bun "),
}

_FRAMEWORK_NAMES = (
    "AIDA", "PAS", "PASTOR", "SPIN", "STEPPS", "Porter", "BMC", "Blue Ocean",
    "OKR", "RICE", "SMART", "SCRUM", "Kanban", "Lean", "BASB", "Zettelkasten",
    "Hormozi", "Grand Slam Offer", "Value Ladder",
)

_PERSONA_SIGNALS = ("disc", "enneagram", "mbti", "big five", "ocean")
_ADR_SIGNALS = ("adr", "decision drivers", "consequences", "alternatives considered", "status: accepted")
_RESEARCH_SIGNALS = ("finding:", "study by", "per ", "hypothesis:", "evidence:")
_MARKETING_SIGNALS = ("hypothesis", "variant", "ctr", "conversion", "a/b test", "control group")
_CODE_SIGNALS = ("class ", "def ", "function ", "import ", "public function", "const ", "interface ")


def classify(content: str, metadata: dict | None = None) -> NoteType:
    meta = metadata or {}
    low = content.lower()
    scores = _score_types(low, content, meta)
    best = max(scores.items(), key=lambda kv: kv[1])
    return best[0] if best[1] > 0 else NoteType.SESSION_LEARNING


def confidence(content: str, metadata: dict | None = None) -> float:
    meta = metadata or {}
    low = content.lower()
    scores = _score_types(low, content, meta)
    ranked = sorted(scores.values(), reverse=True)
    top = ranked[0] if ranked else 0
    runner = ranked[1] if len(ranked) > 1 else 0
    if top == 0:
        return 0.2
    return min(1.0, 0.5 + 0.1 * (top - runner))


def _score_types(low: str, raw: str, meta: dict) -> dict[NoteType, int]:
    scores = {nt: 0 for nt in NoteType}

    if _has_code_block(raw) and any(sig in low for sig in _CODE_SIGNALS):
        scores[NoteType.CODE_PATTERN] += 3
        if _detect_stack(low) or meta.get("stack"):
            scores[NoteType.CODE_PATTERN] += 2

    if any(sig in low for sig in _PERSONA_SIGNALS):
        scores[NoteType.PERSONA] += 3
        if meta.get("persona_name") or meta.get("name"):
            scores[NoteType.PERSONA] += 2

    if any(sig in low for sig in _ADR_SIGNALS):
        scores[NoteType.ARCHITECTURE_DECISION] += 4

    for name in _FRAMEWORK_NAMES:
        if name.lower() in low:
            scores[NoteType.FRAMEWORK] += 2
            break

    if any(sig in low for sig in _RESEARCH_SIGNALS):
        scores[NoteType.RESEARCH_FINDING] += 2

    if meta.get("client") or meta.get("client_name"):
        if any(sig in low for sig in _MARKETING_SIGNALS):
            scores[NoteType.MARKETING_TEST] += 4
        elif any(w in low for w in ("strategy", "positioning", "roadmap", "gtm")):
            scores[NoteType.CLIENT_STRATEGY] += 3

    return scores


def _has_code_block(content: str) -> bool:
    return "```" in content


def _detect_stack(low: str) -> str | None:
    for stack, needles in _STACK_KEYWORDS.items():
        if any(n in low for n in needles):
            return stack
    return None


def plan(content: str, metadata: dict | None = None) -> CatalogPlan:
    meta = dict(metadata or {})
    note_type = classify(content, meta)
    conf = confidence(content, meta)
    if conf < 0.5:
        note_type = NoteType.SESSION_LEARNING
    entry = TAXONOMY[note_type]
    template_vars = _build_template_vars(note_type, content, meta)
    _validate_vars(entry, template_vars, note_type)
    vault_path = resolve_template_vars(entry.path_template, template_vars)
    tags = _build_tags(note_type, meta, template_vars)
    frontmatter = _build_frontmatter_dict(note_type, meta, template_vars, conf)
    return CatalogPlan(
        note_type=note_type,
        vault_path=vault_path,
        frontmatter=frontmatter,
        tags=tags,
        applicable_mocs=list(entry.mocs),
        confidence=conf,
        inline_moc=entry.inline_moc,
    )


def _validate_vars(entry: TaxonomyEntry, vars: dict[str, str], note_type: NoteType) -> None:
    missing = missing_vars(entry, vars)
    if missing:
        raise ValueError(
            f"Cataloger: note_type={note_type.value} missing required vars: {missing}. "
            f"Provide them via the metadata dict."
        )


def _build_template_vars(note_type: NoteType, content: str, meta: dict) -> dict[str, str]:
    low = content.lower()
    vars_out: dict[str, str] = {"date": date.today().isoformat()}
    title = meta.get("title") or _derive_title(content)
    vars_out["title"] = title

    if note_type == NoteType.CODE_PATTERN:
        vars_out["stack"] = meta.get("stack") or _detect_stack(low) or "General"
    elif note_type == NoteType.PERSONA:
        vars_out["name"] = meta.get("persona_name") or meta.get("name") or title
    elif note_type in (NoteType.CLIENT_STRATEGY, NoteType.MARKETING_TEST):
        vars_out["client"] = meta.get("client") or meta.get("client_name") or "Unknown"
        if note_type == NoteType.MARKETING_TEST and meta.get("campaign"):
            vars_out["campaign"] = meta["campaign"]
    elif note_type == NoteType.ARCHITECTURE_DECISION:
        vars_out["number"] = str(meta.get("number") or "000")
        vars_out["slug"] = meta.get("slug") or _slugify(title)
    elif note_type == NoteType.RESEARCH_FINDING:
        vars_out["topic"] = meta.get("topic") or "General"
    elif note_type == NoteType.FRAMEWORK:
        vars_out["framework"] = meta.get("framework") or _detect_framework(content) or "General"
    return vars_out


def _detect_framework(content: str) -> str | None:
    for name in _FRAMEWORK_NAMES:
        if name.lower() in content.lower():
            return name
    return None


def _derive_title(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            cleaned = stripped.lstrip("#").strip()
            if cleaned:
                return cleaned[:80]
        if stripped:
            return stripped[:80]
    return "Untitled"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug[:60] or "untitled"


def _build_tags(note_type: NoteType, meta: dict, vars: dict) -> list[str]:
    entry = TAXONOMY[note_type]
    tags: list[str] = list(entry.default_tags)
    if dept := meta.get("dept") or meta.get("department"):
        tags.append(f"dept/{dept}")
    if stack := vars.get("stack"):
        tags.append(f"stack/{stack.lower()}")
    tags.append(date.today().isoformat())
    seen, dedup = set(), []
    for tag in tags:
        if tag and tag not in seen:
            seen.add(tag)
            dedup.append(tag)
    return dedup


def _build_frontmatter_dict(
    note_type: NoteType, meta: dict, vars: dict, conf: float
) -> dict:
    fm = {
        "note_type": note_type.value,
        "cataloged_at": date.today().isoformat(),
        "classification_confidence": round(conf, 2),
    }
    for key in ("stack", "client", "campaign", "framework", "topic", "name"):
        if val := vars.get(key):
            fm[key] = val
    for key in ("source", "dept", "department", "agent", "workflow"):
        if val := meta.get(key):
            fm[key] = val
    return fm


def execute(plan: CatalogPlan, content: str, writer: ObsidianWriter) -> Path:
    return writer.save(
        obsidian_path=plan.vault_path,
        content=content,
        department=plan.frontmatter.get("department", plan.frontmatter.get("dept", "")),
        agent=plan.frontmatter.get("agent", ""),
        workflow=plan.frontmatter.get("workflow", ""),
        tags=plan.tags,
        extra_frontmatter={
            k: v for k, v in plan.frontmatter.items()
            if k not in ("department", "dept", "agent", "workflow")
        },
    )

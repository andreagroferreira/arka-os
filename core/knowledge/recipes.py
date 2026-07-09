"""Validated feature recipes (Interaction Reform PR7).

A Recipe is the missing artifact between the Pattern Library (short text
hints) and scaffold (whole generic starter repos): a QG-APPROVED feature
implementation captured with its reference files so the same feature —
"Laravel login the ArkaOS-approved way" — is reused across projects
instead of re-derived from documentation every time.

Layout on disk (``~/.arkaos/recipes/<slug>/``):
    recipe.json   # structured metadata (source of truth for retrieval)
    RECIPE.md     # narrative: problem, approach, decisions, how to apply
    files/        # SANITIZED reference files (exemplary feature code)

Confidentiality is NON-NEGOTIABLE (v2.18.0 npm leak precedent): capture
runs every text field and every reference file through
``core.evals.sanitizer.sanitize_text`` BEFORE writing. No redaction
config → ``SanitizerConfigMissing`` → capture REFUSED. There is no write
path that skips sanitization, and ``sanitized`` must be True to persist.

Admission: only a verdict of APPROVED with a timestamp that ties back to
``~/.arkaos/telemetry/qg-verdicts.jsonl`` promotes a deliverable to a
recipe, and capture is always operator-confirmed (the QG skill proposes
it; it never fires silently).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from core.evals.sanitizer import sanitize_text
from core.governance.leak_scanner import load_redaction_patterns
from core.shared.safe_session_id import safe_session_id

MAX_FILES = 20
MAX_TOTAL_BYTES = 200 * 1024


def _recipes_root() -> Path:
    override = os.environ.get("ARKA_RECIPES_DIR", "").strip()
    return Path(override) if override else Path.home() / ".arkaos" / "recipes"


class RecipeProvenance(BaseModel):
    """Where a recipe came from — all fields already sanitized."""

    source_project: str = Field(description="Origin project ([CLIENT-N] if client)")
    qg_verdict: Literal["APPROVED"]
    qg_verdict_ts: str = Field(description="Ties to qg-verdicts.jsonl")
    captured_at: str
    department: str = ""


class Recipe(BaseModel):
    """A reusable, QG-approved feature implementation."""

    slug: str
    name: str
    problem: str = Field(min_length=10)
    stack: list[str] = Field(min_length=1)
    feature_keywords: list[str] = Field(min_length=1)
    files: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    apply_notes: str = ""
    provenance: RecipeProvenance
    sanitized: bool = False

    @field_validator("slug")
    @classmethod
    def _slug_is_path_safe(cls, value: str) -> str:
        if safe_session_id(value) != value:
            raise ValueError(
                f"unsafe recipe slug {value!r} — must be a path-safe token"
            )
        return value

    @field_validator("files")
    @classmethod
    def _within_file_cap(cls, value: list[str]) -> list[str]:
        if len(value) > MAX_FILES:
            raise ValueError(
                f"recipe has {len(value)} files, cap is {MAX_FILES}"
            )
        return value


class RecipeCaptureRefused(RuntimeError):
    """Capture cannot proceed safely (unsanitized, oversize, bad verdict)."""


def _recipe_dir(slug: str) -> Path:
    return _recipes_root() / slug


def _redaction_patterns(config_path: Path | None) -> tuple[str, ...]:
    """Lowercased client patterns for substring filename screening."""
    return tuple(p.lower() for p in load_redaction_patterns(config_path))


def _is_safe_relpath(rel_path: str) -> bool:
    """Reject absolute paths, '..' escapes, backslashes, and leading dots.

    Reference files live strictly under ``files/`` (CWE-22 guard). They
    cannot collide with the recipe's own metadata because they are
    written into the ``files/`` subdirectory, never the recipe root.
    """
    if not rel_path or rel_path.startswith(("/", ".")) or "\\" in rel_path:
        return False
    if Path(rel_path).is_absolute():
        return False
    return all(part not in ("..", "") for part in Path(rel_path).parts)


def capture_recipe(
    recipe: Recipe,
    narrative: str,
    reference_files: dict[str, str],
    config_path: Path | None = None,
) -> Path:
    """Sanitize everything, then persist a recipe. Fail-closed.

    ``reference_files`` maps a relative path under ``files/`` to its raw
    content. Every text field, the narrative, and each file are run
    through the sanitizer first; ``SanitizerConfigMissing`` propagates
    (capture refused). Raises ``RecipeCaptureRefused`` on oversize input
    or a non-APPROVED verdict.
    """
    if recipe.provenance.qg_verdict != "APPROVED":
        raise RecipeCaptureRefused("only APPROVED deliverables become recipes")
    if len(reference_files) > MAX_FILES:
        raise RecipeCaptureRefused(
            f"{len(reference_files)} files exceeds the {MAX_FILES} cap"
        )
    total = sum(len(c.encode("utf-8")) for c in reference_files.values())
    if total > MAX_TOTAL_BYTES:
        raise RecipeCaptureRefused(
            f"reference files total {total} B exceeds {MAX_TOTAL_BYTES} B"
        )
    def _clean(text: str) -> str:
        return sanitize_text(text, config_path=config_path)[0]

    patterns = _redaction_patterns(config_path)
    for rel_path in reference_files:
        if not _is_safe_relpath(rel_path):
            raise RecipeCaptureRefused(
                f"unsafe reference path {rel_path!r} — must stay under files/"
            )
        # A filename can carry a client identifier that reaches both
        # recipe.json and the on-disk path. Filenames are not free text
        # to rewrite, so REFUSE rather than mangle. The word-bounded
        # sanitizer misses a name GLUED into a CamelCase filename
        # (GlobexAuthService.php), so check the redaction patterns as
        # plain case-insensitive substrings here (confidentiality is
        # NON-NEGOTIABLE, QG 2026-07-09).
        lowered = rel_path.lower()
        if any(p in lowered for p in patterns):
            raise RecipeCaptureRefused(
                f"reference filename {rel_path!r} carries a client "
                f"identifier — rename it before capture"
            )

    clean_narrative = _clean(narrative)
    clean_files = {
        rel_path: _clean(content)
        for rel_path, content in reference_files.items()
    }

    # EVERY free-text field that reaches recipe.json must be sanitized.
    # The model_copy update dict is the single sanitize gate — if a new
    # free-text field is added to Recipe, add it here or it leaks
    # (confidentiality is NON-NEGOTIABLE).
    clean_provenance = recipe.provenance.model_copy(update={
        "source_project": _clean(recipe.provenance.source_project),
        "department": _clean(recipe.provenance.department),
    })
    stored = recipe.model_copy(update={
        "name": _clean(recipe.name),
        "problem": _clean(recipe.problem),
        "stack": [_clean(s) for s in recipe.stack],
        "feature_keywords": [_clean(k) for k in recipe.feature_keywords],
        "acceptance_criteria": [_clean(c) for c in recipe.acceptance_criteria],
        "apply_notes": _clean(recipe.apply_notes),
        "files": sorted(clean_files.keys()),
        "provenance": clean_provenance,
        "sanitized": True,
    })

    target = _recipe_dir(stored.slug)
    (target / "files").mkdir(parents=True, exist_ok=True)
    (target / "recipe.json").write_text(
        stored.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (target / "RECIPE.md").write_text(clean_narrative + "\n", encoding="utf-8")
    for rel_path, content in clean_files.items():
        dest = target / "files" / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return target


def load_recipe(slug: str) -> Recipe | None:
    if safe_session_id(slug) != slug:
        return None
    path = _recipe_dir(slug) / "recipe.json"
    if not path.exists():
        return None
    try:
        return Recipe.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — corrupt recipe is simply skipped
        return None


def list_recipes() -> list[Recipe]:
    root = _recipes_root()
    if not root.exists():
        return []
    out: list[Recipe] = []
    for entry in sorted(root.iterdir()):
        if entry.is_dir():
            recipe = load_recipe(entry.name)
            if recipe is not None:
                out.append(recipe)
    return out


def delete_recipe(slug: str) -> bool:
    if safe_session_id(slug) != slug:
        return False
    target = _recipe_dir(slug)
    if not target.exists():
        return False
    shutil.rmtree(target)
    return True

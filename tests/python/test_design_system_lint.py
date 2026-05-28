"""Tests for core.governance.design_system_lint (PR6 Squad Intelligence).

Per-project design system lock. Each project may declare a
`design-system.yaml` at its root with `tokens`, `allowed_components`,
`file_globs`, and `forbidden_patterns`. The linter scans the project,
matches regex against forbidden_patterns, and reports violations with a
file:line location plus the project's own suggestion text.

Opt-in: no YAML at project root → no violations. v1 is advisory only;
pre-commit hook integration lands in v3.77.x.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


design_system_lint = pytest.importorskip(
    "core.governance.design_system_lint",
    reason="design_system_lint not yet implemented (TDD red phase)",
)
DesignSystem = design_system_lint.DesignSystem
DesignViolation = design_system_lint.DesignViolation
lint_project = design_system_lint.lint_project


def _write_design_yaml(project_root: Path, spec: dict) -> Path:
    path = project_root / "design-system.yaml"
    path.write_text(yaml.safe_dump(spec), encoding="utf-8")
    return path


def _write_file(project_root: Path, rel_path: str, content: str) -> Path:
    path = project_root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ─── No YAML at project root ──────────────────────────────────────────


def test_no_design_yaml_returns_empty(tmp_path):
    _write_file(tmp_path, "src/App.vue", '<div style="color: #ff0000;">x</div>')
    assert lint_project(tmp_path) == []


def test_empty_forbidden_patterns_returns_empty(tmp_path):
    _write_design_yaml(tmp_path, {"version": 1, "forbidden_patterns": []})
    _write_file(tmp_path, "src/App.vue", '<div style="color: #ff0000;">x</div>')
    assert lint_project(tmp_path) == []


# ─── Forbidden pattern detection ──────────────────────────────────────


def test_hex_color_pattern_detected(tmp_path):
    _write_design_yaml(
        tmp_path,
        {
            "version": 1,
            "file_globs": ["**/*.vue"],
            "forbidden_patterns": [
                {
                    "pattern": r"#[a-fA-F0-9]{6}\b",
                    "suggestion": "Use a color token like var(--color-primary)",
                }
            ],
        },
    )
    _write_file(tmp_path, "src/App.vue", '<div style="color: #ff0000;">x</div>')
    violations = lint_project(tmp_path)
    assert len(violations) == 1
    assert violations[0].pattern == r"#[a-fA-F0-9]{6}\b"
    assert "color token" in violations[0].suggestion
    assert violations[0].file == "src/App.vue"
    assert violations[0].line == 1


def test_multiple_violations_in_one_file(tmp_path):
    _write_design_yaml(
        tmp_path,
        {
            "version": 1,
            "file_globs": ["**/*.vue"],
            "forbidden_patterns": [
                {"pattern": r"#[a-fA-F0-9]{6}\b", "suggestion": "use token"}
            ],
        },
    )
    _write_file(
        tmp_path,
        "src/App.vue",
        "line1 #abcdef\nline2 normal\nline3 #ff0000 #123456",
    )
    violations = lint_project(tmp_path)
    # Three hex colors total (one on line 1, two on line 3)
    assert len(violations) == 3
    lines = sorted(v.line for v in violations)
    assert lines == [1, 3, 3]


def test_multiple_patterns(tmp_path):
    _write_design_yaml(
        tmp_path,
        {
            "version": 1,
            "file_globs": ["**/*.vue"],
            "forbidden_patterns": [
                {"pattern": r"#[a-fA-F0-9]{6}\b", "suggestion": "use token"},
                {"pattern": r'style="', "suggestion": "use tailwind class"},
            ],
        },
    )
    _write_file(
        tmp_path, "src/App.vue", '<div style="color: #ff0000;">x</div>'
    )
    violations = lint_project(tmp_path)
    kinds = {v.pattern for v in violations}
    assert r"#[a-fA-F0-9]{6}\b" in kinds
    assert r'style="' in kinds
    assert len(violations) == 2


# ─── file_globs filter ─────────────────────────────────────────────────


def test_file_globs_filter_respected(tmp_path):
    _write_design_yaml(
        tmp_path,
        {
            "version": 1,
            "file_globs": ["**/*.vue"],  # only .vue
            "forbidden_patterns": [
                {"pattern": r"#[a-fA-F0-9]{6}\b", "suggestion": "use token"}
            ],
        },
    )
    _write_file(tmp_path, "src/App.vue", "color #ff0000")
    _write_file(tmp_path, "src/App.tsx", "color #00ff00")  # NOT scanned
    _write_file(tmp_path, "docs/README.md", "color #0000ff")  # NOT scanned
    violations = lint_project(tmp_path)
    assert len(violations) == 1
    assert violations[0].file == "src/App.vue"


def test_multiple_file_globs(tmp_path):
    _write_design_yaml(
        tmp_path,
        {
            "version": 1,
            "file_globs": ["**/*.vue", "**/*.tsx"],
            "forbidden_patterns": [
                {"pattern": r"#[a-fA-F0-9]{6}\b", "suggestion": "use token"}
            ],
        },
    )
    _write_file(tmp_path, "src/App.vue", "#ff0000")
    _write_file(tmp_path, "src/App.tsx", "#00ff00")
    _write_file(tmp_path, "docs/README.md", "#0000ff")
    violations = lint_project(tmp_path)
    files = sorted({v.file for v in violations})
    assert files == ["src/App.tsx", "src/App.vue"]


def test_default_file_globs_when_omitted(tmp_path):
    """When file_globs is missing, default to **/*.vue + **/*.tsx + **/*.jsx."""
    _write_design_yaml(
        tmp_path,
        {
            "version": 1,
            "forbidden_patterns": [
                {"pattern": r"#[a-fA-F0-9]{6}\b", "suggestion": "use token"}
            ],
        },
    )
    _write_file(tmp_path, "src/App.vue", "#ff0000")
    _write_file(tmp_path, "src/App.jsx", "#00ff00")
    violations = lint_project(tmp_path)
    files = sorted({v.file for v in violations})
    assert "src/App.vue" in files
    assert "src/App.jsx" in files


# ─── exclude_paths ─────────────────────────────────────────────────────


def test_exclude_paths_respected(tmp_path):
    _write_design_yaml(
        tmp_path,
        {
            "version": 1,
            "file_globs": ["**/*.vue"],
            "forbidden_patterns": [
                {
                    "pattern": r"#[a-fA-F0-9]{6}\b",
                    "suggestion": "use token",
                    "exclude_paths": ["src/Legacy.vue"],
                }
            ],
        },
    )
    _write_file(tmp_path, "src/App.vue", "#ff0000")
    _write_file(tmp_path, "src/Legacy.vue", "#00ff00")  # excluded
    violations = lint_project(tmp_path)
    assert len(violations) == 1
    assert violations[0].file == "src/App.vue"


def test_exclude_paths_glob_pattern(tmp_path):
    """exclude_paths can use ** glob."""
    _write_design_yaml(
        tmp_path,
        {
            "version": 1,
            "file_globs": ["**/*.vue"],
            "forbidden_patterns": [
                {
                    "pattern": r"#[a-fA-F0-9]{6}\b",
                    "suggestion": "use token",
                    "exclude_paths": ["legacy/**"],
                }
            ],
        },
    )
    _write_file(tmp_path, "src/App.vue", "#ff0000")
    _write_file(tmp_path, "legacy/Old.vue", "#00ff00")  # excluded
    violations = lint_project(tmp_path)
    files = {v.file for v in violations}
    assert files == {"src/App.vue"}


# ─── Robustness ─────────────────────────────────────────────────────


def test_malformed_yaml_returns_empty(tmp_path):
    (tmp_path / "design-system.yaml").write_text(
        ":::not yaml:::", encoding="utf-8"
    )
    assert lint_project(tmp_path) == []


def test_nonexistent_project_path_returns_empty(tmp_path):
    assert lint_project(tmp_path / "does-not-exist") == []


def test_design_system_yaml_itself_excluded_by_default(tmp_path):
    """The design-system.yaml file should not lint itself."""
    _write_design_yaml(
        tmp_path,
        {
            "version": 1,
            "file_globs": ["**/*.yaml", "**/*.vue"],
            "forbidden_patterns": [
                {"pattern": r"#[a-fA-F0-9]{6}\b", "suggestion": "use token"}
            ],
        },
    )
    # design-system.yaml contains the literal regex (which has hex pattern in it)
    # but should be excluded automatically
    _write_file(tmp_path, "src/App.vue", "#ff0000")
    violations = lint_project(tmp_path)
    files = {v.file for v in violations}
    assert "design-system.yaml" not in files
    assert "src/App.vue" in files


# ─── DesignViolation shape ─────────────────────────────────────────────


def test_design_violation_has_required_fields():
    v = DesignViolation(
        file="src/App.vue",
        line=42,
        pattern=r"#[a-fA-F0-9]{6}\b",
        suggestion="use token",
        matched_text="#ff0000",
    )
    assert v.file == "src/App.vue"
    assert v.line == 42
    assert v.pattern.startswith("#")
    assert v.matched_text == "#ff0000"


# ─── Marta QG-PR6 first-pass B1/B2 regression tests ───────────────────
# `**/x` is supposed to match `x` at any depth, INCLUDING zero (gitignore
# convention). The senior-dev's first pass produced `.*/` which requires
# at least one directory segment — silently missed root-level files.
# These two tests reproduce that bug; do not delete them on the fix.


def test_default_file_globs_match_root_level_file(tmp_path):
    """`**/*.vue` MUST scan App.vue at the project root, not only nested."""
    _write_design_yaml(
        tmp_path,
        {
            "version": 1,
            "forbidden_patterns": [
                {"pattern": r"#[a-fA-F0-9]{6}\b", "suggestion": "use token"}
            ],
        },
    )
    _write_file(tmp_path, "App.vue", "color #ff0000 here")  # ROOT level
    _write_file(tmp_path, "src/Other.vue", "color #00ff00 here")  # NESTED
    violations = lint_project(tmp_path)
    files = sorted({v.file for v in violations})
    assert "App.vue" in files
    assert "src/Other.vue" in files


def test_exclude_paths_root_directory_glob(tmp_path):
    """`**/legacy/**` MUST exclude `legacy/Old.vue` at the project root."""
    _write_design_yaml(
        tmp_path,
        {
            "version": 1,
            "file_globs": ["**/*.vue"],
            "forbidden_patterns": [
                {
                    "pattern": r"#[a-fA-F0-9]{6}\b",
                    "suggestion": "use token",
                    "exclude_paths": ["**/legacy/**"],
                }
            ],
        },
    )
    _write_file(tmp_path, "legacy/Old.vue", "#ff0000")  # ROOT/legacy/
    _write_file(tmp_path, "src/App.vue", "#00ff00")  # not excluded
    violations = lint_project(tmp_path)
    files = {v.file for v in violations}
    assert files == {"src/App.vue"}, (
        f"expected only src/App.vue, got {files}. "
        "Bug: **/legacy/** does not match root-level legacy/ directory."
    )


# ─── DesignSystem dataclass ────────────────────────────────────────────


def test_design_system_shape(tmp_path):
    _write_design_yaml(
        tmp_path,
        {
            "version": 1,
            "project": "test",
            "tokens": {"colors": {"primary": "#3b82f6"}},
            "allowed_components": ["UButton"],
            "file_globs": ["**/*.vue"],
            "forbidden_patterns": [
                {"pattern": r"#[0-9a-f]{6}", "suggestion": "use token"}
            ],
        },
    )
    ds = design_system_lint.load_design_system(tmp_path)
    assert ds is not None
    assert ds.project == "test"
    assert "primary" in ds.tokens.get("colors", {})
    assert "UButton" in ds.allowed_components

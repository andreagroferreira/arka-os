"""harness/ is generated, never hand-edited, never over budget.

The multi-runtime instruction bundles are compiled by
``scripts/harness_gen.py`` from the generated registries. These locks
keep the committed tree byte-identical to a fresh run, the target set
deliberate, and every file inside the context budget that makes an
instruction file actually get read.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from harness_gen import (  # noqa: E402
    DEPT_LEADS,
    MAIN_FILE_BUDGET_BYTES,
    _load_agents,
    check_budget,
    generate,
    write_bundle,
)

HARNESS_DIR = REPO_ROOT / "harness"

# Deliberate target set — update alongside the generator, never by
# accident. One entry per supported harness, keyed by its main file.
EXPECTED_MAIN_FILES = {
    "codex/AGENTS.md",
    "opencode/AGENTS.md",
    "gemini/GEMINI.md",
    "zed/.rules",
    "copilot/copilot-instructions.md",
    "cursor/rules/arkaos.mdc",
}


def _committed_files() -> dict[str, str]:
    return {
        str(p.relative_to(HARNESS_DIR)): p.read_text(encoding="utf-8")
        for p in sorted(HARNESS_DIR.rglob("*"))
        if p.is_file()
    }


def test_committed_harness_matches_fresh_regen():
    fresh = generate()
    committed = _committed_files()
    assert committed == fresh, (
        "harness/ drifted — regenerate with "
        "`arka-py scripts/harness_gen.py`, never hand-edit"
    )


def test_every_expected_target_is_present():
    files = set(generate())
    missing = EXPECTED_MAIN_FILES - files
    assert not missing, f"missing harness targets: {sorted(missing)}"


def test_no_unexpected_top_level_targets():
    targets = {rel.split("/")[0] for rel in generate()}
    expected = {rel.split("/")[0] for rel in EXPECTED_MAIN_FILES}
    assert targets == expected, (
        "harness target set changed — update EXPECTED_MAIN_FILES "
        "deliberately"
    )


def test_every_file_respects_the_budget():
    over = check_budget(generate())
    assert not over, f"budget exceeded: {over}"
    assert MAIN_FILE_BUDGET_BYTES <= 20_000, (
        "budget creep — raising the ceiling needs a deliberate decision"
    )


def test_bundles_carry_the_real_version():
    version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    for rel in EXPECTED_MAIN_FILES:
        content = (HARNESS_DIR / rel).read_text(encoding="utf-8")
        assert f"v{version}" in content, f"{rel} carries a stale version"


def test_bundles_route_through_every_department():
    # The routing table must name every department prefix and lead — a
    # dropped department in the export is a silently amputated product.
    content = (HARNESS_DIR / "codex" / "AGENTS.md").read_text(
        encoding="utf-8")
    for prefix, lead in DEPT_LEADS.items():
        assert f"`/{prefix}`" in content, f"missing department /{prefix}"
        assert lead in content, f"missing lead {lead}"


def test_cursor_stack_rules_mirror_the_sources():
    sources = sorted(
        p.stem
        for p in (REPO_ROOT / "config" / "standards" / "stack-rules").glob(
            "*.md")
    )
    exported = sorted(
        p.name.removeprefix("arkaos-stack-").removesuffix(".mdc")
        for p in (HARNESS_DIR / "cursor" / "rules").glob(
            "arkaos-stack-*.mdc")
    )
    assert exported == sources, (
        "cursor stack rules out of sync with config/standards/stack-rules"
    )


def test_bundles_declare_their_generated_nature():
    for rel in EXPECTED_MAIN_FILES:
        content = (HARNESS_DIR / rel).read_text(encoding="utf-8")
        assert "harness_gen.py" in content, (
            f"{rel} must name its generator — hand-edits get overwritten"
        )


def test_dept_leads_drift_locked_to_routing_table():
    # DEPT_LEADS is the generator's one hand-maintained mapping; the
    # canonical routing table lives in arka/SKILL.md. Lock them together
    # so a lead change in one place cannot silently fork the other.
    skill_md = (REPO_ROOT / "arka" / "SKILL.md").read_text(encoding="utf-8")
    for prefix, lead in DEPT_LEADS.items():
        assert f"[arka:routing] {prefix} -> {lead}" in skill_md, (
            f"DEPT_LEADS ({prefix} -> {lead}) diverged from the "
            "arka/SKILL.md routing table"
        )


def test_opencode_agents_mirror_the_curated_registry_cut():
    # Foundation PR-6: the native agent files are the tier<=1 cut
    # (C-suite + squad leads) of the REAL registry — derived, never
    # hand-typed, and locked to the registry so a roster change cannot
    # silently fork the export.
    curated = [a for a in _load_agents() if a["tier"] <= 1]
    files = generate()
    agent_files = {r for r in files if r.startswith("opencode/agents/")}
    assert len(agent_files) == len(curated)
    for agent in curated:
        rel = f"opencode/agents/arka-{agent['id']}.md"
        assert rel in files, f"missing agent file {rel}"
        content = files[rel]
        assert content.startswith("---\n"), f"{rel} missing frontmatter"
        assert "mode: subagent" in content
        assert agent["name"] in content
        assert "harness_gen.py" in content


def test_opencode_commands_cover_every_department():
    files = generate()
    for prefix, lead in DEPT_LEADS.items():
        rel = f"opencode/commands/arka-{prefix}.md"
        assert rel in files, f"missing command file {rel}"
        assert f"[arka:routing] {prefix} -> {lead}" in files[rel]
        assert "$ARGUMENTS" in files[rel], (
            f"{rel} must template the user request (opencode.ai/docs/commands)"
        )


def test_opencode_config_fragment_is_valid_json_with_arka_tools():
    import json

    config = json.loads(generate()["opencode/opencode.json"])
    assert config["$schema"] == "https://opencode.ai/config.json"
    server = config["mcp"]["arka-tools"]
    assert server["type"] == "local"
    assert server["command"][:2] == ["npx", "-y"]
    assert server["enabled"] is True


def test_write_bundle_removes_stale_files(tmp_path):
    # A renamed or dropped target must not leave its old file behind —
    # a stale bundle is a hand-edit nobody made.
    write_bundle({"codex/AGENTS.md": "v1", "zed/.rules": "v1"}, tmp_path)
    assert (tmp_path / "zed" / ".rules").exists()
    write_bundle({"codex/AGENTS.md": "v2"}, tmp_path)
    assert not (tmp_path / "zed" / ".rules").exists(), "stale file survived"
    assert (tmp_path / "codex" / "AGENTS.md").read_text() == "v2"

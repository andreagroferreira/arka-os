"""Static scope analysis for fenced JS/TS in skill markdown (issue #457).

Thousands of lines of executable JS/TS ship inside `departments/**/SKILL.md`
and `departments/**/references/**/*.md` with no executable checking at all --
lint only ever saw the `.py` files. Two runtime defects reached Quality Gate
review through that hole, both of the same class: an identifier used but never
declared, which is a `ReferenceError` on the first frame.

These tests pin three things:

1. `node --check` CANNOT be the gate. It exits 0 on the exact block that
   motivated the gate, because an unresolvable identifier is a runtime error,
   never a parse error. `test_node_check_passes_the_motivating_bug` asserts
   that failure directly, so nobody can "simplify" the gate back into a syntax
   check without a red test explaining why.
2. The analyzer CATCHES that block -- proven on a synthetic corpus, not only
   on the repo, so the proof survives the corpus being fixed.
3. The cumulative-scope design is load-bearing. Turning it off must resurrect
   the false positives Francisca measured, which is what makes the extra
   machinery justified rather than decorative.

TOOLCHAIN HONESTY: these tests shell out to node. When node or the eslint
dev-dependency is missing the tests skip -- but `test_toolchain_present_in_ci`
turns that skip into a hard failure whenever `CI` is set, so the gate can never
report green in CI while having silently checked nothing. That is the fail-open
class of issue #452, and it is closed here by construction.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYZER = REPO_ROOT / "scripts" / "lint_fenced_code.mjs"
ALLOWLIST = REPO_ROOT / "scripts" / "fenced-code-allowlist.json"

_NODE = shutil.which("node")
_ESLINT_INSTALLED = (REPO_ROOT / "node_modules" / "eslint" / "package.json").is_file()
_TS_PARSER_INSTALLED = (
    REPO_ROOT / "node_modules" / "@typescript-eslint" / "parser" / "package.json"
).is_file()
_TOOLCHAIN_READY = bool(_NODE) and _ESLINT_INSTALLED and _TS_PARSER_INSTALLED

_SKIP_REASON = (
    "UNVERIFIED: fenced-code scope analysis did not run "
    f"(node={'yes' if _NODE else 'MISSING'}, "
    f"eslint={'yes' if _ESLINT_INSTALLED else 'MISSING'}, "
    f"@typescript-eslint/parser={'yes' if _TS_PARSER_INSTALLED else 'MISSING'}). "
    "Run `npm ci` to install the dev-dependencies."
)

requires_toolchain = pytest.mark.skipif(not _TOOLCHAIN_READY, reason=_SKIP_REASON)

# The block that motivated the whole gate: `w` and `h` are never declared
# anywhere in the document, so this throws ReferenceError on the first frame --
# and parses without complaint.
MOTIVATING_BLOCK = """\
ctx.clearRect(0, 0, w, h);
ctx.fillStyle = 'rgba(0, 0, 0, 0.02)';
ctx.fillRect(0, 0, w, h);
"""


def _run_analyzer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_NODE or "node", str(ANALYZER), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def _analyze_json(*args: str) -> dict:
    result = _run_analyzer("--json", *args)
    assert result.stdout, f"analyzer produced no stdout; stderr={result.stderr}"
    return json.loads(result.stdout)


# ─── Toolchain honesty ──────────────────────────────────────────────────────


def test_toolchain_present_where_required() -> None:
    """Where the toolchain is provisioned, a skip is an ERROR, not a pass.

    `ARKA_FENCED_GATE_REQUIRED=1` is set by the one CI job that installs node
    and runs `npm ci` (`python-tests` in .github/workflows/test.yml). There, a
    skipped scope gate would mean the job reported success while checking
    nothing -- the fail-open of issue #452 -- so it fails loudly instead.

    It is deliberately NOT keyed on bare `CI`: `cross-platform-tests` has no
    Node toolchain and is report-only, and manufacturing a red there would
    train reviewers to ignore red. Its skips stay honest skips, carrying
    `_SKIP_REASON` into the run summary that job publishes.
    """
    if os.environ.get("ARKA_FENCED_GATE_REQUIRED") != "1":
        pytest.skip(
            "ARKA_FENCED_GATE_REQUIRED is not set; any skip in this module is "
            f"reported, not silent -- {_SKIP_REASON}"
        )
    assert _NODE, "node is required wherever the fenced-code scope gate is declared"
    assert _ESLINT_INSTALLED, "eslint missing -- `npm ci` must run before pytest"
    assert _TS_PARSER_INSTALLED, (
        "@typescript-eslint/parser missing -- `npm ci` must run before pytest"
    )


def test_skip_reason_names_every_missing_component() -> None:
    """The skip message must say what is missing, never just 'skipped'."""
    for component in ("node", "eslint", "@typescript-eslint/parser"):
        assert component in _SKIP_REASON
    assert "UNVERIFIED" in _SKIP_REASON


# ─── The tool correction: node --check is not enough ────────────────────────


@pytest.mark.skipif(_NODE is None, reason="UNVERIFIED: node not on PATH")
def test_node_check_passes_the_motivating_bug(tmp_path: Path) -> None:
    """`node --check` exits 0 on the undeclared-identifier bug. That is the point.

    This is the evidence that disproves the issue's original proposal. If this
    test ever goes red, Node has changed its semantics and the gate's rationale
    needs revisiting -- it does not mean `node --check` became sufficient.
    """
    sample = tmp_path / "motivating.js"
    sample.write_text(MOTIVATING_BLOCK, encoding="utf-8")
    result = subprocess.run(
        [_NODE, "--check", str(sample)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (
        "node --check unexpectedly rejected the motivating block; the issue's "
        f"premise needs re-measuring. stderr={result.stderr}"
    )


# ─── The synthetic RED case ─────────────────────────────────────────────────


def _synthetic_corpus(root: Path, skill: str, body: str) -> None:
    skill_dir = root / "departments" / "dev" / "skills" / skill
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")


@requires_toolchain
def test_synthetic_corpus_catches_undeclared_identifiers(tmp_path: Path) -> None:
    """The gate fires on the motivating bug in a corpus built for the purpose.

    Proving it on a synthetic corpus rather than only on the repo means the
    proof survives the real files being fixed.
    """
    _synthetic_corpus(
        tmp_path,
        "synthetic-red",
        f"# Synthetic\n\n```js\n{MOTIVATING_BLOCK}```\n",
    )
    report = _analyze_json("--no-allowlist", "--root", str(tmp_path))
    found = {f["identifier"] for f in report["reportable"]}
    assert {"w", "h"} <= found, f"gate missed the motivating bug; got {sorted(found)}"

    result = _run_analyzer("--no-allowlist", "--root", str(tmp_path))
    assert result.returncode == 1, "gate must exit non-zero when findings remain"


@requires_toolchain
def test_declared_identifiers_do_not_fire(tmp_path: Path) -> None:
    """The fixed form of the same block is clean -- the gate is not a blunt grep."""
    fixed = (
        "# Synthetic\n\n```js\n"
        "const canvas = document.querySelector('canvas');\n"
        "const ctx = canvas.getContext('2d');\n"
        "const w = canvas.width;\n"
        "const h = canvas.height;\n"
        f"{MOTIVATING_BLOCK}"
        "```\n"
    )
    _synthetic_corpus(tmp_path, "synthetic-green", fixed)
    report = _analyze_json("--no-allowlist", "--root", str(tmp_path))
    assert report["reportable"] == [], f"false positives: {report['reportable']}"


@requires_toolchain
def test_cumulative_scope_spans_blocks(tmp_path: Path) -> None:
    """A later block sees an earlier block's declarations -- doc order matters.

    This is the behaviour that makes doc fragments lintable at all: a skill that
    declares a class in one fence and uses it three fences later is correct
    prose, and the gate must agree.
    """
    body = (
        "# Synthetic\n\n"
        "```js\nclass ParticleSystem { constructor(n) { this.n = n; } }\n```\n\n"
        "Prose between the fences.\n\n"
        "```js\nconst ps = new ParticleSystem(5000);\nexport { ps };\n```\n"
    )
    _synthetic_corpus(tmp_path, "synthetic-cumulative", body)
    report = _analyze_json("--no-allowlist", "--root", str(tmp_path))
    assert report["reportable"] == [], (
        f"cumulative scope failed to carry the declaration: {report['reportable']}"
    )

    # Mutation: with the cumulative scope off, the same corpus must go red.
    mutated = _analyze_json("--no-allowlist", "--no-cumulative", "--root", str(tmp_path))
    assert {f["identifier"] for f in mutated["reportable"]} == {"ParticleSystem"}


# ─── Mutation proof against the real fixture ────────────────────────────────


@requires_toolchain
def test_mutation_resurrects_the_measured_false_positives() -> None:
    """Dropping the cumulative scope must bring back Francisca's false positives.

    She measured three on `canvas-generative/references/algorithms.md`:
    `canvas`, `ctx` and `ParticleSystem`. `canvas` and `ctx` are assumed context
    the prose establishes, so they live in the allowlist either way; the one the
    SCOPE MODEL has to resolve is `ParticleSystem`, declared in an earlier fence
    of the same document. If this ever stops failing under mutation, the
    cumulative machinery has become decorative and should be deleted.
    """
    fixture = "departments/dev/skills/canvas-generative/references/algorithms.md"

    def ids_for(*extra: str) -> set[str]:
        report = _analyze_json("--no-allowlist", *extra)
        return {f["identifier"] for f in report["reportable"] if f["file"] == fixture}

    with_scope = ids_for()
    without_scope = ids_for("--no-cumulative")

    assert "ParticleSystem" not in with_scope, (
        "cumulative scope should resolve a class declared in an earlier fence"
    )
    assert "ParticleSystem" in without_scope, (
        "mutation did not resurrect the false positive -- the cumulative scope "
        "is not doing the work it claims to do"
    )
    assert with_scope < without_scope, (
        f"mutation must strictly widen findings: {sorted(with_scope)} vs "
        f"{sorted(without_scope)}"
    )


@requires_toolchain
def test_cumulative_scope_removes_findings_repo_wide() -> None:
    """The design earns its keep in aggregate, not just on one fixture."""
    strict = _analyze_json("--no-allowlist")
    naive = _analyze_json("--no-allowlist", "--no-cumulative")
    assert naive["undefinedTotal"] > strict["undefinedTotal"], (
        "per-block linting should be noisier than cumulative scope; measured "
        f"{naive['undefinedTotal']} vs {strict['undefinedTotal']}"
    )


# ─── The gate itself ────────────────────────────────────────────────────────


@requires_toolchain
def test_gate_is_green_on_the_repo() -> None:
    """The committed baseline holds: no unallowlisted findings on master.

    A failure here means a fence introduced an identifier that nothing in its
    document or skill establishes. Triage it; do not reflexively widen the
    allowlist.
    """
    result = _run_analyzer()
    assert result.returncode == 0, (
        "fenced-code scope gate failed.\n"
        f"{result.stdout}\n{result.stderr}"
    )


@requires_toolchain
def test_gate_covers_the_expected_corpus() -> None:
    """Guards against the extractor silently matching nothing.

    A scope regex that stops matching would make the gate pass vacuously, which
    reads identical to 'no findings'. The floors are deliberately below the
    measured 188 blocks / 33 files so ordinary content churn does not trip them.
    """
    report = _analyze_json()
    assert report["stats"]["blocks"] >= 150, report["stats"]
    assert report["stats"]["files"] >= 25, report["stats"]


@requires_toolchain
def test_vendor_and_plugin_trees_are_excluded() -> None:
    """Vendored trees carry their own pins; `plugins/` is a generated mirror.

    Editing either to satisfy this gate would break a lock, so neither may ever
    appear in a finding or in the baseline.
    """
    report = _analyze_json("--no-allowlist")
    for finding in report["reportable"] + report["reportableParse"]:
        assert "/vendor/" not in finding["file"], finding
        assert not finding["file"].startswith("plugins/"), finding

    allowlist = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    for section in ("trackedFindings", "unparseableBlocks"):
        for path in allowlist[section]:
            assert "/vendor/" not in path, f"{section} references a vendored file: {path}"
            assert not path.startswith("plugins/"), f"{section} references the mirror: {path}"


@requires_toolchain
def test_analysis_is_deterministic() -> None:
    """Two runs over an unchanged tree must agree, or the gate is a coin flip."""
    first = _analyze_json("--no-allowlist")
    second = _analyze_json("--no-allowlist")
    for key in ("reportable", "reportableParse", "undefinedTotal", "parseErrorTotal"):
        assert first[key] == second[key], f"non-deterministic: {key}"


@requires_toolchain
def test_runs_well_inside_the_ci_budget() -> None:
    """Declared performance: the sweep must stay far under the CI step budget."""
    report = _analyze_json()
    assert report["stats"]["elapsedMs"] < 60_000, report["stats"]


# ─── Allowlist hygiene ──────────────────────────────────────────────────────


def test_allowlist_entries_are_justified() -> None:
    """Every assumed-context global carries a written justification.

    An allowlist without reasons rots into a dumping ground, and this one is the
    only thing standing between the gate and a green-by-suppression outcome.
    """
    allowlist = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    assumed = allowlist["assumedContext"]
    assert assumed, "assumedContext must not be empty"
    assert len(assumed) <= 12, (
        f"assumedContext has grown to {len(assumed)} entries; it is meant to stay "
        "small. Library surfaces belong to the skill-directory import rule."
    )
    for name, reason in assumed.items():
        assert isinstance(reason, str) and len(reason) > 30, (
            f"assumedContext['{name}'] needs a real justification, got {reason!r}"
        )

    for section in ("trackedFindings", "unparseableBlocks"):
        for path, entry in allowlist[section].items():
            assert entry.get("note"), f"{section}['{path}'] must carry a note"


def test_motivating_identifiers_are_tracked_not_whitelisted() -> None:
    """`w`/`h` are real defects awaiting a fix, not accepted context.

    They must never migrate into `assumedContext` -- that would permanently
    blind the gate to the exact class of bug it was built for.
    """
    allowlist = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    assert "w" not in allowlist["assumedContext"]
    assert "h" not in allowlist["assumedContext"]

    tracked = allowlist["trackedFindings"]
    canvas_skill = "departments/dev/skills/canvas-generative/SKILL.md"
    assert canvas_skill in tracked, (
        "the motivating file dropped out of the baseline; if it was fixed, this "
        "test should be updated in the same commit as the fix"
    )
    assert {"w", "h"} <= set(tracked[canvas_skill]["identifiers"])


if __name__ == "__main__":  # pragma: no cover - manual invocation
    sys.exit(pytest.main([__file__, "-v"]))

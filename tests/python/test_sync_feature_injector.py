"""Regression lock for the Phase-4 feature injector (issue #509).

The live defect: a Phase-4 run wrote four marker blocks into an installed
SKILL.md at an offset that sat between a `<!--` on line 20 and its `-->`
on line 74. The first feature marker's own `-->` closed the OUTER comment,
so that marker went invisible to every literal consumer, and the outer
comment's tail rendered as garbage above the skill's commands table.

Both halves of the contract are locked here:
- the injector REFUSES such an offset and returns the document untouched;
- the state it refuses to create is the same one `marker_audit` classifies
  as "swallowed" — proven by forcing the injection and reading the audit's
  verdict on the result, rather than by asserting a string.

The spec is built here rather than loaded from `core/sync/features/`: this
file locks the injector, and editing a registry YAML must not be able to
turn it green or red.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.sync.feature_injector import (
    inject_feature,
    open_comment_line,
    split_line_at,
)
from core.sync.marker_audit import scan_text
from core.sync.reporter import build_report, format_report
from core.sync.schema import FeatureSpec, InjectionRefusal

_HOST_PATH = Path("/tmp/skills/arka-example/SKILL.md")

_SPEC = FeatureSpec(
    name="workflow-tiers",
    added_in="2.12.0",
    mandatory=True,
    section_title="Workflow Tiers",
    detection_pattern="arka:feature:workflow-tiers|## Workflow Tiers",
    content=(
        "<!-- arka:feature:workflow-tiers:start -->\n"
        "## Workflow Tiers\n"
        "\n"
        "Three workflow tiers based on task complexity.\n"
        "<!-- arka:feature:workflow-tiers:end -->\n"
    ),
)

# The live corruption, reduced: a comment opens on line 5 to explain the
# table and only closes after it. Every offset in between is inside it.
_OPEN_COMMENT_HOST = (
    "# Ecosystem\n"
    "\n"
    "## Commands\n"
    "\n"
    "<!-- Column convention: the second column is the squad that owns the\n"
    "command and the third is what the operator gets back\n"
    "\n"
    "| Command | Squad | Deliverable |\n"
    "|---------|-------|-------------|\n"
    "| `/build` | dev | a shipped feature |\n"
    "-->\n"
    "\n"
    "## Orchestration Workflows\n"
)
_INSIDE_THE_COMMENT = _OPEN_COMMENT_HOST.index("| Command |")
_OPENING_LINE = 5

_CLEAN_HOST = (
    "# Ecosystem\n"
    "\n"
    "## Commands\n"
    "\n"
    "| Command | Squad |\n"
    "|---------|-------|\n"
    "| `/build` | dev |\n"
    "\n"
    "## Orchestration Workflows\n"
)


def _inject(text: str, at: int | None = None):
    return inject_feature(text, _SPEC, path=_HOST_PATH, at=at)


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------


def test_refuses_to_inject_inside_an_open_html_comment():
    result = _inject(_OPEN_COMMENT_HOST, at=_INSIDE_THE_COMMENT)

    assert result.status == "refused"
    assert result.text == _OPEN_COMMENT_HOST, "the document must come back untouched"
    assert result.refusal is not None
    assert result.refusal.feature == "workflow-tiers"
    assert result.refusal.path == _HOST_PATH
    assert result.refusal.line == _OPENING_LINE, "the line of the `<!--`, not of the point"
    assert "unterminated" in result.refusal.reason


def test_the_refusal_names_the_file_and_the_line_for_the_operator():
    refusal = _inject(_OPEN_COMMENT_HOST, at=_INSIDE_THE_COMMENT).refusal

    assert refusal is not None
    described = refusal.describe()
    assert described.startswith("Injection: ")
    assert f"{_HOST_PATH}:{_OPENING_LINE}:" in described
    assert "workflow-tiers" in described


def test_the_refused_state_is_the_one_the_audit_calls_swallowed():
    """Force the write the guard declines, then read the damage.

    This is what makes the refusal more than a policy: the audit — written
    independently, for the post-mortem — reports the forced result as a
    swallowed marker, which is exactly the live defect of issue #509.
    """
    forced = (
        _OPEN_COMMENT_HOST[:_INSIDE_THE_COMMENT]
        + _SPEC.content
        + _OPEN_COMMENT_HOST[_INSIDE_THE_COMMENT:]
    )

    reasons = [v.reason for v in scan_text(forced, _HOST_PATH)]

    assert any("swallows this feature marker" in r for r in reasons), reasons
    assert _inject(_OPEN_COMMENT_HOST, at=_INSIDE_THE_COMMENT).status == "refused"


def test_a_closed_comment_above_the_point_does_not_block_injection():
    host = "# Ecosystem\n\n<!-- a note that closes -->\n\n## Orchestration Workflows\n"

    result = _inject(host, at=host.index("## Orchestration Workflows"))

    assert result.status == "injected"
    assert result.refusal is None


def test_an_unclosed_comment_inside_a_code_fence_does_not_block_injection():
    """Reference docs SHOW how a marker opens; that is documentation.

    The opener below is deliberately unpaired — read literally it swallows
    the rest of the file, and every injection under it would refuse for
    ever. The injector reads documents through the same `blank_code` the
    audit uses, so a fenced example cannot make a host uninjectable.
    """
    host = (
        "# Ecosystem\n"
        "\n"
        "A feature section opens with:\n"
        "\n"
        "```markdown\n"
        "<!-- arka:feature:<name>:start\n"
        "```\n"
        "\n"
        "## Orchestration Workflows\n"
    )

    result = _inject(host, at=host.index("## Orchestration Workflows"))

    assert result.status == "injected"
    assert open_comment_line(host, len(host)) is None


def test_open_comment_line_points_at_the_opening_and_is_none_when_balanced():
    assert open_comment_line(_OPEN_COMMENT_HOST, _INSIDE_THE_COMMENT) == _OPENING_LINE
    assert open_comment_line(_OPEN_COMMENT_HOST, len(_OPEN_COMMENT_HOST)) is None
    assert open_comment_line(_CLEAN_HOST, len(_CLEAN_HOST)) is None


# Every host that Phase 4 touches already carries injected marker blocks,
# i.e. CLOSED comments, before any prose comment. So "a closed pair, then an
# open note" is the ORDINARY shape — and until this fixture existed the scan
# could be cut down to examining only the first comment and stay green.
_CLOSED_THEN_OPEN_HOST = (
    "# Ecosystem\n"
    "\n"
    "<!-- arka:feature:quality-gate:start -->\n"
    "## Quality Gate\n"
    "<!-- arka:feature:quality-gate:end -->\n"
    "\n"
    "<!-- a maintainer note whose close was lost in an edit\n"
    "\n"
    "## Orchestration Workflows\n"
)


def test_a_closed_comment_before_an_open_one_does_not_hide_it():
    """The scan must keep walking past a balanced pair, and name the second."""
    at = _CLOSED_THEN_OPEN_HOST.index("## Orchestration Workflows")

    result = _inject(_CLOSED_THEN_OPEN_HOST, at=at)

    assert result.status == "refused"
    assert result.refusal is not None
    assert result.refusal.line == 7, "the OPEN note, not the closed pair above it"


def test_a_comment_opening_mid_line_is_found():
    """`<!--` is not required to start its line; a trailing note opens one."""
    host = (
        "# Ecosystem\n"
        "\n"
        "| Command | Squad | <!-- the third column was dropped\n"
        "\n"
        "## Orchestration Workflows\n"
    )

    result = _inject(host, at=host.index("## Orchestration Workflows"))

    assert result.status == "refused"
    assert result.refusal is not None
    assert result.refusal.line == 3


def test_a_bare_empty_looking_comment_is_still_open():
    """`<!-->` has no `-->` AFTER its opener, so it does not close itself.

    The close must be searched from past the opener, never from the opener:
    the last three characters of `<!-->` look like a terminator and are not
    one for this purpose.
    """
    host = "# Ecosystem\n\n<!-->\n\n## Orchestration Workflows\n"

    result = _inject(host, at=host.index("## Orchestration Workflows"))

    assert result.status == "refused"
    assert result.refusal is not None
    assert result.refusal.line == 3


# ---------------------------------------------------------------------------
# The position guard
# ---------------------------------------------------------------------------

# A populated table row: an offset inside it splices the block between two
# halves of the same line. Worse than the comment case, because the markers
# written are canonical and `scan_text` calls the wreckage clean.
_TABLE_HOST = (
    "# Ecosystem\n"
    "\n"
    "| Command | Squad |\n"
    "|---------|-------|\n"
    "| `/build` | dev |\n"
    "\n"
    "## Orchestration Workflows\n"
)
_MID_ROW = _TABLE_HOST.index("| dev |")


def test_refuses_an_offset_that_splits_a_line():
    result = _inject(_TABLE_HOST, at=_MID_ROW)

    assert result.status == "refused"
    assert result.text == _TABLE_HOST, "the document must come back untouched"
    assert result.refusal is not None
    assert result.refusal.line == 5
    assert "splits this line" in result.refusal.reason


def test_the_split_a_line_wreckage_is_the_kind_the_audit_cannot_see():
    """Why position needs its own guard: the audit is no backstop here.

    Force the write and the markers come out canonical, so `scan_text`
    returns clean over a gutted table — unlike the open-comment case, where
    the audit at least names the damage after the fact.
    """
    forced = _TABLE_HOST[:_MID_ROW] + _SPEC.content + _TABLE_HOST[_MID_ROW:]

    assert scan_text(forced, _HOST_PATH) == [], "the audit sees nothing wrong"
    assert "| `/build` <!-- arka:feature:workflow-tiers:start -->" in forced
    assert "\n| dev |\n" in forced, "the rest of the row is orphaned below"
    assert _inject(_TABLE_HOST, at=_MID_ROW).status == "refused"


def test_every_line_boundary_still_injects():
    """Line start, end of line and EOF are all boundaries.

    End of line matters: the documented point is straight after an existing
    `:end -->`, where the rest of that line is empty.
    """
    end_marker = "<!-- arka:feature:quality-gate:end -->"
    host = (
        "# Ecosystem\n"
        "\n"
        "<!-- arka:feature:quality-gate:start -->\n"
        "## Quality Gate\n"
        f"{end_marker}\n"
        "\n"
        "## Orchestration Workflows\n"
    )
    boundaries = {
        "line start": host.index("## Orchestration Workflows"),
        "end of line": host.index(end_marker) + len(end_marker),
        "end of file": len(host),
    }

    for label, at in boundaries.items():
        assert split_line_at(host, at) is None, label
        assert _inject(host, at=at).status == "injected", label


# ---------------------------------------------------------------------------
# Injection and detection
# ---------------------------------------------------------------------------


def test_injects_at_the_requested_point_and_leaves_the_file_auditable():
    at = _CLEAN_HOST.index("## Orchestration Workflows")

    result = _inject(_CLEAN_HOST, at=at)

    assert result.status == "injected"
    block = _SPEC.content.strip()
    assert block in result.text
    assert result.text.index(block) < result.text.index("## Orchestration Workflows")
    assert scan_text(result.text, _HOST_PATH) == [], "the injected markers must be canonical"


def test_the_injected_block_stands_on_its_own_lines():
    result = _inject(_CLEAN_HOST, at=_CLEAN_HOST.index("## Orchestration Workflows"))

    assert "\n\n<!-- arka:feature:workflow-tiers:start -->" in result.text
    assert "<!-- arka:feature:workflow-tiers:end -->\n\n## Orchestration" in result.text
    assert result.text.endswith("\n")


def test_the_default_point_is_the_end_of_the_document():
    result = _inject(_CLEAN_HOST)

    assert result.status == "injected"
    assert result.text.rstrip("\n").endswith("<!-- arka:feature:workflow-tiers:end -->")


def test_a_feature_already_present_is_never_injected_twice():
    host = f"# Ecosystem\n\n{_SPEC.content}"

    result = _inject(host)

    assert result.status == "present"
    assert result.text == host
    assert result.refusal is None


def test_detection_runs_before_the_guard_so_a_settled_host_is_not_reported():
    """A host that needs nothing must not produce a refusal to chase.

    Its open comment is a defect of that file, and the audit reports it —
    but blaming an injection that was never needed would send the operator
    after the wrong line.
    """
    host = f"{_SPEC.content}\n<!-- an unterminated note below the section\n"

    result = _inject(host)

    assert result.status == "present"
    assert result.refusal is None


def test_an_offset_outside_the_document_is_a_programming_error():
    with pytest.raises(ValueError, match="outside"):
        _inject(_CLEAN_HOST, at=len(_CLEAN_HOST) + 1)


# ---------------------------------------------------------------------------
# The report surface
# ---------------------------------------------------------------------------


class TestRefusalsReachTheOperator:
    """A refusal the report drops is as invisible as the corruption was.

    The host is left WITHOUT a mandatory section when the injector declines,
    so silence here would trade a corrupt file for a quietly incomplete one.
    """

    def _refusal(self) -> InjectionRefusal:
        refusal = _inject(_OPEN_COMMENT_HOST, at=_INSIDE_THE_COMMENT).refusal
        assert refusal is not None
        return refusal

    def _report(self):
        return build_report(
            "5.14.0", "5.15.0", [], [], [], [], injection_refusals=[self._refusal()]
        )

    def test_a_refusal_counts_as_an_error(self):
        errors = self._report().errors

        assert len(errors) == 1
        assert "refused to inject" in errors[0]

    def test_the_structured_record_survives_next_to_the_prose(self):
        report = self._report()

        record = report.injection_refusals[0]
        assert (record.feature, record.line) == ("workflow-tiers", _OPENING_LINE)
        assert report.injection_refusals != report.errors

    def test_the_record_is_json_serialisable_for_the_phase_4_consumer(self):
        payload = json.loads(self._report().model_dump_json())["injection_refusals"][0]

        assert payload["feature"] == "workflow-tiers"
        assert payload["line"] == _OPENING_LINE
        assert payload["path"].endswith("arka-example/SKILL.md")

    def test_the_formatted_report_names_the_host_and_the_line(self):
        output = format_report(self._report())

        assert "Injections refused" in output
        assert f"arka-example/SKILL.md:{_OPENING_LINE}" in output
        assert "Errors: 1" in output

    def test_a_clean_run_says_nothing_about_refusals(self):
        output = format_report(build_report("5.14.0", "5.15.0", [], [], [], []))

        assert "Injections refused" not in output
        assert "Errors: 0" in output

    def test_control_characters_never_reach_the_terminal(self):
        """CWE-117: a refusal is rendered into the operator's terminal."""
        refusal = InjectionRefusal(
            path=_HOST_PATH, feature="\x1b[2Jwiped", line=1, reason="ok"
        )

        assert "\x1b" not in refusal.feature
        assert "\\x1b" in refusal.describe()

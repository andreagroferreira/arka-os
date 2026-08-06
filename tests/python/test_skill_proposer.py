"""Tests for core.governance.skill_proposer (PR44 v2.63.0)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from core.governance.skill_proposer import SkillProposal, evaluate


def _revoke_read_or_skip(path: Path) -> None:
    """Make ``path`` writable-but-unreadable, or skip the test.

    root ignores the read bit, so a suite running as root would exercise
    the readable branch while claiming to test the unreadable one.
    Skipping beats passing vacuously.
    """
    path.chmod(0o222)
    if os.access(path, os.R_OK):
        path.chmod(0o644)
        pytest.skip("read permission not enforced (running as root?)")


#: Two topics rendered from this template differ in content but share
#: the slug `capability-workflow` (the first hint that matches) — the
#: exact shape that used to overwrite silently.
BASE = (
    "[arka:gate:4] Shipped the {topic} as a reusable workflow with a "
    "template and a checklist covering the whole procedure end to end."
)

#: Readable, valid UTF-8, and none of our business. The ladder must
#: route around it without a single chmod in sight.
FOREIGN = "somebody else's proposal, do not touch\n"


def _rungs(text: str, scratch: Path, today: str = "2026-05-25") -> list[str]:
    """The three filenames `text` can legally land on, in ladder order.

    Rendered by the module itself rather than rebuilt by hand, so the
    test cannot drift from the naming scheme it is pinning.
    """
    probe = evaluate(text, output_dir=scratch, today=today)
    digest = hashlib.sha256(probe.proposal_markdown.encode("utf-8")).hexdigest()
    stem = f"{today}-{probe.suggested_slug}"
    return [f"{stem}.md", f"{stem}-{digest[:8]}.md", f"{stem}-{digest}.md"]


class TestBypass:
    def test_trivial_marker_short_circuits(self, tmp_path: Path):
        result = evaluate("[arka:trivial] one-line typo fix", output_dir=tmp_path)
        assert result.should_propose is False
        assert result.reason == "bypass-marker"

    def test_skill_skip_marker_short_circuits(self, tmp_path: Path):
        result = evaluate(
            "[arka:phase:13] done. [arka:skill-skip] one-off cleanup",
            output_dir=tmp_path,
        )
        assert result.should_propose is False


class TestCompletionGate:
    def test_no_completion_signal_no_proposal(self, tmp_path: Path):
        text = (
            "Working on the workflow with multiple phases and a checklist. "
            "Still in flight, no closure yet."
        )
        result = evaluate(text, output_dir=tmp_path)
        assert result.should_propose is False
        assert result.reason == "no-completion-signal"

    def test_phase13_unlocks_proposal(self, tmp_path: Path):
        text = (
            "[arka:phase:13] Built a 10-phase workflow with a template, "
            "a playbook, a checklist, and a procedure for the recurring "
            "task that will be repeated across many contexts."
        )
        result = evaluate(text, output_dir=tmp_path)
        assert result.should_propose is True
        assert result.reason == "proposed"


class TestTrivialLength:
    def test_short_completion_signal_is_trivial(self, tmp_path: Path):
        result = evaluate("[arka:phase:13] done", output_dir=tmp_path)
        assert result.should_propose is False
        assert result.reason == "trivial-length"


class TestSkillHintFloor:
    def test_below_hint_floor_no_proposal(self, tmp_path: Path):
        text = (
            "[arka:phase:13] Finished the workflow but the actual change "
            "was a one-off bug fix that does not generalise into anything "
            "repeatable, just a localised tweak in a specific config file "
            "under conditions that are unlikely to recur in this codebase."
        )
        result = evaluate(text, output_dir=tmp_path)
        assert result.should_propose is False
        assert result.reason == "below-skill-hint-floor"

    def test_two_plus_hints_meets_floor(self, tmp_path: Path):
        text = (
            "[arka:phase:13] Built a 10-phase workflow with a checklist "
            "and a template that will be repeated for similar projects "
            "going forward in many contexts and teams."
        )
        result = evaluate(text, output_dir=tmp_path)
        assert result.should_propose is True


class TestProposalFile:
    def test_proposal_is_written(self, tmp_path: Path):
        text = (
            "[arka:phase:13] Built a 10-phase workflow with a playbook "
            "and a template for the recurring procedure that will "
            "be reused across many similar projects in the future."
        )
        result = evaluate(text, output_dir=tmp_path, today="2026-05-25")
        assert result.proposal_path is not None
        assert result.proposal_path.exists()
        assert "2026-05-25" in result.proposal_path.name


class TestProposalCollisions:
    """`_suggest_slug` anchors on the first matching hint, so same-day
    slug collisions are the norm, not the edge case: six word hints plus
    the fallback give seven fixed names, and the numeric `N-phase` hint
    mints one more per number it matches. Measured on a live install:
    seven proposals collapsed onto three files."""

    def test_distinct_proposals_do_not_overwrite_each_other(
        self, tmp_path: Path
    ):
        first = evaluate(
            BASE.format(topic="release pipeline"),
            output_dir=tmp_path, today="2026-05-25",
        )
        second = evaluate(
            BASE.format(topic="incident runbook"),
            output_dir=tmp_path, today="2026-05-25",
        )

        assert first.should_propose and second.should_propose
        assert first.suggested_slug == second.suggested_slug
        assert first.proposal_path != second.proposal_path
        assert first.proposal_path.exists()
        assert second.proposal_path.exists()
        assert len(list(tmp_path.glob("*.md"))) == 2
        # The first capture survives verbatim.
        assert "release pipeline" in first.proposal_path.read_text(
            encoding="utf-8"
        )

    def test_rerunning_the_same_closing_message_is_idempotent(
        self, tmp_path: Path
    ):
        text = BASE.format(topic="release pipeline")
        first = evaluate(text, output_dir=tmp_path, today="2026-05-25")
        second = evaluate(text, output_dir=tmp_path, today="2026-05-25")

        assert first.proposal_path == second.proposal_path
        assert len(list(tmp_path.glob("*.md"))) == 1

    def test_first_proposal_keeps_the_plain_name(self, tmp_path: Path):
        result = evaluate(
            BASE.format(topic="release pipeline"),
            output_dir=tmp_path, today="2026-05-25",
        )
        assert result.proposal_path.name == (
            f"2026-05-25-{result.suggested_slug}.md"
        )


class TestUnreadableExistingProposal:
    """A proposal file that cannot be read back is unknown content, not
    "the same content". Returning the plain path on a failed read handed
    `write_text` the predecessor to destroy — the very loss this module
    exists to prevent."""

    def test_unreadable_file_is_not_clobbered_by_different_content(
        self, tmp_path: Path
    ):
        first = evaluate(
            BASE.format(topic="release pipeline"),
            output_dir=tmp_path, today="2026-05-25",
        )
        original = first.proposal_path.read_bytes()
        _revoke_read_or_skip(first.proposal_path)
        try:
            second = evaluate(
                BASE.format(topic="incident runbook"),
                output_dir=tmp_path, today="2026-05-25",
            )
            assert second.should_propose is True
            assert second.proposal_path != first.proposal_path
            assert len(list(tmp_path.glob("*.md"))) == 2
        finally:
            first.proposal_path.chmod(0o644)
        assert first.proposal_path.read_bytes() == original

    def test_unreadable_file_is_not_clobbered_by_identical_content(
        self, tmp_path: Path
    ):
        text = BASE.format(topic="release pipeline")
        first = evaluate(text, output_dir=tmp_path, today="2026-05-25")
        original = first.proposal_path.read_bytes()
        _revoke_read_or_skip(first.proposal_path)
        try:
            # Content-identical, but unprovably so: the rewrite must go
            # somewhere else rather than gamble on the existing bytes.
            second = evaluate(text, output_dir=tmp_path, today="2026-05-25")
            assert second.proposal_path != first.proposal_path
        finally:
            first.proposal_path.chmod(0o644)
        assert first.proposal_path.read_bytes() == original

    def test_unreadable_digest_twin_escalates_to_the_full_digest(
        self, tmp_path: Path
    ):
        """The short digest name is no more sacred than the plain one:
        if it is opaque too, the ladder climbs to the full digest."""
        plain = evaluate(
            BASE.format(topic="release pipeline"),
            output_dir=tmp_path, today="2026-05-25",
        )
        text = BASE.format(topic="incident runbook")
        short = evaluate(text, output_dir=tmp_path, today="2026-05-25")
        original = short.proposal_path.read_bytes()
        _revoke_read_or_skip(short.proposal_path)
        try:
            again = evaluate(text, output_dir=tmp_path, today="2026-05-25")
            full = hashlib.sha256(
                again.proposal_markdown.encode("utf-8")
            ).hexdigest()
            assert again.proposal_path.name == (
                f"2026-05-25-{again.suggested_slug}-{full}.md"
            )
            assert plain.proposal_path.read_text(encoding="utf-8") == (
                plain.proposal_markdown
            )
        finally:
            short.proposal_path.chmod(0o644)
        assert short.proposal_path.read_bytes() == original

    def test_ladder_of_opaque_names_refuses_to_write(self, tmp_path: Path):
        """Terminal rung: both digest names unreadable, the plain one
        holding a different proposal. No name is left that can be proved
        free or ours, so nothing is written — the capture is dropped
        rather than laid over bytes we cannot account for."""
        plain = evaluate(
            BASE.format(topic="release pipeline"),
            output_dir=tmp_path, today="2026-05-25",
        )
        text = BASE.format(topic="incident runbook")
        short = evaluate(text, output_dir=tmp_path, today="2026-05-25")
        _revoke_read_or_skip(short.proposal_path)
        opaque = [short.proposal_path]
        try:
            escalated = evaluate(text, output_dir=tmp_path, today="2026-05-25")
            _revoke_read_or_skip(escalated.proposal_path)
            opaque.append(escalated.proposal_path)

            refused = evaluate(text, output_dir=tmp_path, today="2026-05-25")

            assert refused.should_propose is False
            assert refused.reason == "no-safe-filename"
            assert refused.proposal_path is None
            # The rendered capture still comes back, so a caller that
            # wants it has something to work with.
            assert refused.proposal_markdown is not None
            assert len(list(tmp_path.glob("*.md"))) == 3
        finally:
            for path in opaque:
                path.chmod(0o644)
        assert plain.proposal_path.read_text(encoding="utf-8") == (
            plain.proposal_markdown
        )
        assert escalated.proposal_path.read_text(encoding="utf-8") == (
            escalated.proposal_markdown
        )


class TestForeignContentOnTheLadder:
    """Each rung occupied by readable, valid UTF-8 bytes that are simply
    not ours — no chmod, no corruption, nothing exotic. A filename built
    from our digest says nothing about the bytes inside it (any file can
    carry any name), so every occupied rung must divert and a full ladder
    must refuse."""

    TEXT = BASE.format(topic="incident runbook")

    def _ladder(self, tmp_path: Path) -> tuple[Path, list[Path]]:
        out = tmp_path / "out"
        out.mkdir()
        names = _rungs(self.TEXT, tmp_path / "probe")
        return out, [out / name for name in names]

    def test_foreign_plain_diverts_to_the_short_digest(self, tmp_path: Path):
        out, (plain, short, _full) = self._ladder(tmp_path)
        plain.write_text(FOREIGN, encoding="utf-8")

        result = evaluate(self.TEXT, output_dir=out, today="2026-05-25")

        assert result.proposal_path == short
        assert plain.read_text(encoding="utf-8") == FOREIGN
        assert len(list(out.glob("*.md"))) == 2

    def test_foreign_short_digest_diverts_to_the_full_digest(
        self, tmp_path: Path
    ):
        out, (plain, short, full) = self._ladder(tmp_path)
        plain.write_text(FOREIGN, encoding="utf-8")
        short.write_text(FOREIGN, encoding="utf-8")

        result = evaluate(self.TEXT, output_dir=out, today="2026-05-25")

        assert result.proposal_path == full
        assert plain.read_text(encoding="utf-8") == FOREIGN
        assert short.read_text(encoding="utf-8") == FOREIGN
        assert len(list(out.glob("*.md"))) == 3

    def test_foreign_full_digest_leaves_a_free_plain_name_alone(
        self, tmp_path: Path
    ):
        out, (plain, _short, full) = self._ladder(tmp_path)
        full.write_text(FOREIGN, encoding="utf-8")

        result = evaluate(self.TEXT, output_dir=out, today="2026-05-25")

        assert result.proposal_path == plain
        assert full.read_text(encoding="utf-8") == FOREIGN
        assert len(list(out.glob("*.md"))) == 2

    def test_full_ladder_of_foreign_content_writes_nothing(
        self, tmp_path: Path
    ):
        out, rungs = self._ladder(tmp_path)
        for rung in rungs:
            rung.write_text(FOREIGN, encoding="utf-8")

        result = evaluate(self.TEXT, output_dir=out, today="2026-05-25")

        assert result.should_propose is False
        assert result.reason == "no-safe-filename"
        assert result.proposal_path is None
        assert result.proposal_markdown is not None
        assert [r.read_text(encoding="utf-8") for r in rungs] == [FOREIGN] * 3
        assert len(list(out.glob("*.md"))) == 3


class TestNonUtf8ExistingProposal:
    """`UnicodeDecodeError` is a `ValueError`, not an `OSError`. Catching
    only `OSError` let it escape `evaluate` into the Stop hook's blanket
    `except Exception: pass` — the proposal vanished with no file and no
    error, a failure mode the pre-digest code never had."""

    CORRUPT = b"\xff\xfe not utf-8 \x80"

    def test_non_utf8_neighbour_neither_raises_nor_clobbers(
        self, tmp_path: Path
    ):
        first = evaluate(
            BASE.format(topic="release pipeline"),
            output_dir=tmp_path, today="2026-05-25",
        )
        first.proposal_path.write_bytes(self.CORRUPT)

        second = evaluate(
            BASE.format(topic="incident runbook"),
            output_dir=tmp_path, today="2026-05-25",
        )

        assert second.should_propose is True
        assert first.proposal_path.read_bytes() == self.CORRUPT
        digest = hashlib.sha256(
            second.proposal_markdown.encode("utf-8")
        ).hexdigest()[:8]
        assert second.proposal_path.name == (
            f"2026-05-25-{second.suggested_slug}-{digest}.md"
        )
        assert len(list(tmp_path.glob("*.md"))) == 2


class TestDeleteThenRefire:
    """Every proposal ends with "Delete this proposal file once acted
    on." Once the operator deletes the plain twin, the hook re-firing on
    the survivor found the plain name free and wrote a byte-identical
    duplicate. The digest name has to be consulted first."""

    def test_refire_after_deleting_the_plain_twin_writes_nothing_new(
        self, tmp_path: Path
    ):
        plain = evaluate(
            BASE.format(topic="release pipeline"),
            output_dir=tmp_path, today="2026-05-25",
        )
        suffixed = evaluate(
            BASE.format(topic="incident runbook"),
            output_dir=tmp_path, today="2026-05-25",
        )
        assert plain.proposal_path.name == (
            f"2026-05-25-{plain.suggested_slug}.md"
        )
        assert suffixed.proposal_path != plain.proposal_path

        plain.proposal_path.unlink()  # operator acted on it
        again = evaluate(
            BASE.format(topic="incident runbook"),
            output_dir=tmp_path, today="2026-05-25",
        )

        assert again.proposal_path == suffixed.proposal_path
        survivors = list(tmp_path.glob("*.md"))
        assert len(survivors) == 1
        assert "incident runbook" in survivors[0].read_text(encoding="utf-8")


class TestResultShape:
    def test_frozen(self, tmp_path: Path):
        result = evaluate("[arka:trivial]", output_dir=tmp_path)
        assert isinstance(result, SkillProposal)
        with pytest.raises((AttributeError, Exception)):
            result.should_propose = True

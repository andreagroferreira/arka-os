"""PR-B4: the QG agent contracts are load-bearing dispatch shape.

``config/claude-agents/`` is the SOURCE (``.claude/agents/`` is a
deployed artifact — ``deployProjectAgents`` copies the source files
byte-for-byte). The aggregate guard and the reviewer ledger depend on
what these contracts prescribe: the ``arka-qgverdict`` fence is what
the hook-boundary capture parses, ``evidence_digest`` is what the
guard's digest chain verifies, and the verbatim/carry obligations are
what keep the aggregate honest. A contract that silently loses one of
these markers re-opens the relay this campaign exists to close.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "config" / "claude-agents"
DEPLOYED = ROOT / ".claude" / "agents"

FENCE = "```arka-qgverdict"

# tools are PINNED: Eduardo reviews prose and never needs Bash or Write
# (a copy reviewer with write access could edit what it reviews);
# Francisca's Bash is deliberate — she reproduces blockers by execution.
REVIEWERS = {
    "eduardo-copy": {
        "tools": "Read, Grep, Glob",
        "reviewer_id": "copy-director-eduardo",
    },
    "francisca-tech": {
        "tools": "Read, Grep, Glob, Bash",
        "reviewer_id": "tech-director-francisca",
    },
}
AGGREGATOR = "marta-cqo"
ALL_AGENTS = [*REVIEWERS, AGGREGATOR]


def _source(name: str) -> str:
    return (SOURCE / f"{name}.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ALL_AGENTS)
def test_frontmatter_shape(name):
    text = _source(name)
    assert text.startswith("---\n")
    assert re.search(rf"^name: {name}$", text, re.M)
    assert re.search(r"^tools: ", text, re.M)
    assert re.search(r"^model: ", text, re.M)


@pytest.mark.parametrize("name", ALL_AGENTS)
def test_fence_contract_present(name):
    """Every QG agent must emit the fence the ledger captures —
    including the aggregator (the B1 gate closed with Marta's fence
    present only by ad-hoc instruction; PR-B4 makes it contract)."""
    assert FENCE in _source(name)


@pytest.mark.parametrize("name", ALL_AGENTS)
def test_evidence_digest_in_contract(name):
    """The guard refuses an APPROVED aggregate over a digest-less
    artifact (PR-B4) — a contract that stops asking for the digest
    makes every honest dispatch refusable."""
    assert "evidence_digest" in _source(name)


@pytest.mark.parametrize(("name", "meta"), sorted(REVIEWERS.items()))
def test_reviewer_tools_are_pinned(name, meta):
    match = re.search(r"^tools: (.+)$", _source(name), re.M)
    assert match is not None
    assert match.group(1).strip() == meta["tools"]


@pytest.mark.parametrize(("name", "meta"), sorted(REVIEWERS.items()))
def test_reviewer_identity_named(name, meta):
    """The verdict's ``reviewer`` field must name the constitution id —
    identity attribution in the ledger keys on it."""
    assert meta["reviewer_id"] in _source(name)


def test_marta_contract_carries_the_b4_obligations():
    text = _source(AGGREGATOR)
    assert "### <Reviewer> — verbatim" in text
    assert "digest_carries" in text
    assert "## Conflict Handling" in text
    assert "never resolved silently" in text
    # The no-op review_workflow recording step stays deleted: it was a
    # cross-process no-op documented as a safeguard (G8).
    assert "review_workflow" not in text


@pytest.mark.parametrize("name", ALL_AGENTS)
def test_deployed_copy_carries_the_contract(name):
    """Deployment parity: when a deployed copy exists on this machine,
    it must carry the load-bearing markers — a stale deploy reviews
    under a contract the guard no longer accepts."""
    deployed = DEPLOYED / f"{name}.md"
    if not deployed.is_file():
        pytest.skip("no deployed agents on this machine (CI)")
    text = deployed.read_text(encoding="utf-8")
    assert FENCE in text
    assert "evidence_digest" in text

"""Merge the PR5 blind relabel into the shipped decision corpora.

Reproducible and offline: reads the two labellers' batches (``--relabel
DIR`` holding ``A/`` and ``B/``), the shipped corpora, and writes

* ``config/decisions/corpora/refine.jsonl`` and ``forge-complexity.jsonl``:
  the existing cases with ``expected`` (and refine's ``gap``) replaced by
  the labellers' consensus, the operator's arbitration where they
  disagreed, then the labellers' new cases;
* ``config/decisions/corpora/heldout/<site>.jsonl`` for
  :data:`core.decisions.replay.HELDOUT_SITES`, never mixed into the above.

Rules (spec PR5 D7 and the 2026-09-25 arbitration):

* A disagreement without an arbitration entry is an error (exit 1).
* Near-duplicate prompts (normalised token Jaccard ≥ :data:`DUP_JACCARD`)
  are dropped: existing cases win over new ones, A's over B's. A held-out
  case that near-duplicates any prompt of its site's training corpus is
  dropped too (``duplicate-of-training``): a held-out set measures
  generalisation only if it never repeats what the corpus already holds.
* A prompt matching the operator's client-redaction patterns
  (``~/.arkaos/redaction-clients.json``) is dropped; no patterns = refuse
  (exit 2), since nothing would prove the corpus clean. A prompt the
  egress credential detector flags is dropped after
  :data:`PLACEHOLDERS` are applied (the fake ``hunter2`` credential
  becomes ``changeme``: still a hard-coded literal, no longer a detector
  hit).
* Re-running on a merged checkout reproduces it: only ``source="seed"``
  rows count as existing.
* The merged corpus must be ≥ :data:`MIN_NEW_SHARE` new and ≥
  :data:`MIN_PT_SHARE` pt-PT, else exit 1 and nothing is written.
* A held-out set must be ≥ :data:`HELDOUT_MIN_PT_SHARE` pt-PT (the
  replay floor), else exit 1; below :data:`MIN_PT_SHARE` it only warns.

``~/.arkaos/bin/arka-py scripts/tools/corpus_merge.py --relabel DIR
[--check]``; ``--check`` validates and prints the counts without writing.
Client names are never printed: a dropped case is reported by id only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from core.decisions.replay import (  # noqa: E402
    EXPECTED,
    HELDOUT_SITES,
    ReplayCase,
    default_corpus_path,
    heldout_corpus_path,
)
from core.decisions.replay import MIN_PT_SHARE as HELDOUT_MIN_PT_SHARE  # noqa: E402
from core.decisions.sites.quality import SLOP_DIMENSIONS  # noqa: E402
from core.egress.credentials import egress_secret_labels  # noqa: E402
from core.governance.leak_scanner import load_redaction_patterns  # noqa: E402

DUP_JACCARD = 0.8
MIN_NEW_SHARE = 0.5
MIN_PT_SHARE = 0.55
SEED_SOURCE = "seed"
# Operator arbitration, 2026-09-25 (recorded in the PR5 spec): a genre
# noun ("uma app", "a dashboard") is not a target; a purely vague request
# is not maximal reach.
REFINE_ARBITRATION: dict[str, str] = {
    "rf-pt-01": "target", "rf-pt-03": "target", "rf-en-02": "target", "rf-en-06": "target",
}
FORGE_ARBITRATION: dict[str, str] = {"forge-complexity-29": "STANDARD"}
PLACEHOLDERS: dict[str, str] = {"hunter2": "changeme"}
CASE_KEYS = ("id", "lang", "prompt", "prior", "context", "expected", "gap", "source")

Row = dict[str, Any]


class MergeError(RuntimeError):
    """The inputs cannot be merged as the rules require."""


class NoPatternsError(MergeError):
    """No client-redaction patterns on disk: the corpus cannot be certified."""


@dataclass
class Merged:
    """One output file's cases and what was dropped on the way."""

    site: str
    cases: list[ReplayCase] = field(default_factory=list)
    dropped: dict[str, list[str]] = field(default_factory=dict)

    def drop(self, why: str, case_id: str) -> None:
        self.dropped.setdefault(why, []).append(case_id)


# --- io ------------------------------------------------------------------------


def read_jsonl(path: Path) -> list[Row]:
    """Every non-blank line of ``path`` as a dict."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def case_line(case: ReplayCase) -> str:
    """One corpus line: fixed key order, defaults left out, UTF-8 kept."""
    data = case.model_dump()
    row = {k: data[k] for k in CASE_KEYS if not _is_default(k, data[k])}
    return json.dumps(row, ensure_ascii=False)


def _is_default(key: str, value: object) -> bool:
    return (key in ("prior", "context") and not value) or (key == "gap" and value is None)


def write_corpus(path: Path, cases: Iterable[ReplayCase]) -> None:
    """Write ``cases`` as JSONL (parent directory created)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(case_line(c) + "\n" for c in cases), encoding="utf-8")


# --- labels --------------------------------------------------------------------


def refine_consensus(case_id: str, a: Row, b: Row) -> tuple[bool, str]:
    """``(vague, gap)`` both labellers give, or the arbitrated gap."""
    vague_a, vague_b = a["label"] != "none", bool(b["label"])
    if vague_a != vague_b:
        raise MergeError(f"refine {case_id}: vague disagreement without arbitration")
    gap = REFINE_ARBITRATION.get(case_id)
    if gap is None:
        if a["label"] != b["gap"]:
            raise MergeError(f"refine {case_id}: gap {a['label']} vs {b['gap']} unarbitrated")
        gap = a["label"]
    return vague_a, gap


def forge_consensus(case_id: str, a: Row, b: Row) -> str:
    """The tier both labellers give, or the arbitrated one."""
    tier = FORGE_ARBITRATION.get(case_id)
    if tier is not None:
        return tier
    if a["tier"] != b["label"]:
        raise MergeError(f"forge-complexity {case_id}: {a['tier']} vs {b['label']} unarbitrated")
    return str(a["tier"])


def new_refine_label(row: Row, labeller: str) -> dict[str, Any]:
    """``expected``/``gap`` of a new refine case in either labeller's format."""
    if labeller == "A":
        return {"expected": row["label"] != "none", "gap": row["label"]}
    return {"expected": bool(row["label"]), "gap": row["gap"]}


def new_forge_label(row: Row, labeller: str) -> dict[str, Any]:
    """``expected`` tier of a new forge-complexity case."""
    return {"expected": row["tier"] if labeller == "A" else row["label"]}


def heldout_label(site: str, row: Row) -> object:
    """The replay label of one held-out row, A's dict format or B's list/str."""
    label = row["label"]
    if not isinstance(label, dict):
        return label
    if site == "learning-signal":
        return label["signal"]
    if site == "qg-prescreen":
        return [label["verdict"], label["blocker"]]
    return [label[d] for d in SLOP_DIMENSIONS]


# --- filters ---------------------------------------------------------------------


def _tokens(text: str) -> frozenset[str]:
    plain = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    return frozenset(re.findall(r"[a-z0-9_]+", plain))


def jaccard(a: str, b: str) -> float:
    """Token-set Jaccard of two prompts, case- and accent-insensitive."""
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb) if ta | tb else 1.0


def client_matcher(patterns: Sequence[str]) -> Callable[[str], bool]:
    """True when a text names a client (same boundaries as the sanitizer)."""
    if not patterns:
        raise NoPatternsError("no client-redaction patterns: refusing to certify the corpus")
    alternation = "|".join(re.escape(p) for p in sorted(patterns, key=len, reverse=True))
    regex = re.compile(r"(?<![a-z0-9])(" + alternation + r")(?![a-z0-9])", re.IGNORECASE)
    return lambda text: regex.search(text) is not None


def with_placeholders(prompt: str) -> str:
    """``prompt`` with each fake credential swapped for its placeholder."""
    for fake, placeholder in PLACEHOLDERS.items():
        prompt = prompt.replace(fake, placeholder)
    return prompt


def admit(
    merged: Merged,
    case: ReplayCase,
    names_client: Callable[[str], bool],
    training: Sequence[str] = (),
) -> None:
    """Append ``case`` unless it is a client hit, a secret or a near-duplicate.

    ``training`` holds the prompts a held-out case must not near-duplicate
    (its site's training corpus); a hit is dropped as ``duplicate-of-training``.
    """
    texts = [case.prompt, *case.prior]
    if any(names_client(t) for t in texts):
        merged.drop("client-name", case.id)
    elif any(egress_secret_labels(t) for t in texts):
        merged.drop("secret", case.id)
    elif any(jaccard(case.prompt, prompt) >= DUP_JACCARD for prompt in training):
        merged.drop("duplicate-of-training", case.id)
    elif any(jaccard(case.prompt, kept.prompt) >= DUP_JACCARD for kept in merged.cases):
        merged.drop("near-duplicate", case.id)
    else:
        merged.cases.append(case)


def validated(site: str, row: Row) -> ReplayCase:
    """A :class:`ReplayCase` whose ``expected`` is a ``site`` label."""
    case = ReplayCase.model_validate({k: row[k] for k in CASE_KEYS if k in row})
    if not EXPECTED[site](case.expected):
        raise MergeError(f"{site} {case.id}: {case.expected!r} is not a {site} label")
    return case


# --- merge -----------------------------------------------------------------------


def _existing(site: str, relabel: Path) -> tuple[list[Row], dict[str, Row], dict[str, Row]]:
    # Only the seed rows: after a merge the shipped file also holds the new
    # cases, and a re-run must reproduce it byte for byte.
    rows = [r for r in read_jsonl(default_corpus_path(site))
            if r.get("source", SEED_SOURCE) == SEED_SOURCE]
    a = {r["id"]: r for r in read_jsonl(relabel / "A" / f"{site}.A.jsonl")}
    b = {r["id"]: r for r in read_jsonl(relabel / "B" / f"{site}.B.jsonl")}
    ids = {r["id"] for r in rows}
    if set(a) != ids or set(b) != ids:
        raise MergeError(f"{site}: the labellers did not label exactly the shipped ids")
    return rows, a, b


def _relabelled(site: str, row: Row, a: Row, b: Row) -> Row:
    base: Row = {k: row[k] for k in ("id", "lang", "prompt", "prior", "context") if k in row}
    if site == "refine":
        vague, gap = refine_consensus(row["id"], a, b)
        return {**base, "expected": vague, "gap": gap, "source": row.get("source", SEED_SOURCE)}
    return {**base, "expected": forge_consensus(row["id"], a, b),
            "source": row.get("source", SEED_SOURCE)}


def _new_rows(site: str, relabel: Path) -> list[Row]:
    label = new_refine_label if site == "refine" else new_forge_label
    out: list[Row] = []
    for labeller in ("A", "B"):
        for row in read_jsonl(relabel / labeller / f"{site}.new.{labeller}.jsonl"):
            keep: Row = {k: row[k] for k in ("id", "lang", "prompt", "prior") if k in row}
            out.append({**keep, **label(row, labeller), "source": row["source"]})
    return out


def merge_site(site: str, relabel: Path, names_client: Callable[[str], bool]) -> Merged:
    """Existing cases relabelled by consensus, then the new ones, filtered."""
    rows, a, b = _existing(site, relabel)
    merged = Merged(site)
    for row in rows:
        admit(merged, validated(site, _relabelled(site, row, a[row["id"]], b[row["id"]])),
              names_client)
    for row in _new_rows(site, relabel):
        admit(merged, validated(site, row), names_client)
    return merged


def training_prompts(site: str) -> list[str]:
    """Every prompt of ``site``'s shipped training corpus (missing file = error)."""
    return [str(row["prompt"]) for row in read_jsonl(default_corpus_path(site))]


def merge_heldout(relabel: Path, names_client: Callable[[str], bool]) -> dict[str, Merged]:
    """One held-out set per site from A then B (placeholders applied).

    A case near-duplicating any training prompt of its site is dropped.
    """
    out = {site: Merged(site) for site in HELDOUT_SITES}
    training = {site: training_prompts(site) for site in HELDOUT_SITES}
    for labeller in ("A", "B"):
        for row in read_jsonl(relabel / labeller / f"heldout.{labeller}.jsonl"):
            site = row["site"]
            case = validated(site, {"id": row["id"], "lang": row["lang"],
                                    "prompt": with_placeholders(row["prompt"]),
                                    "expected": heldout_label(site, row),
                                    "source": row["source"]})
            admit(out[site], case, names_client, training[site])
    return out


# --- report ----------------------------------------------------------------------


def shares(merged: Merged) -> dict[str, Any]:
    """Counts the spec asks for: existing/new, pt-PT share, sources."""
    cases = merged.cases
    total = len(cases) or 1
    new = sum(1 for c in cases if c.source != SEED_SOURCE)
    sources: dict[str, int] = {}
    for c in cases:
        sources[c.source] = sources.get(c.source, 0) + 1
    return {"site": merged.site, "cases": len(cases), "existing": len(cases) - new, "new": new,
            "new_share": round(new / total, 4),
            "pt_share": round(sum(1 for c in cases if c.lang == "pt") / total, 4),
            "sources": dict(sorted(sources.items())),
            "dropped": {k: sorted(v) for k, v in sorted(merged.dropped.items())}}


def constraint_failures(stats: dict[str, Any]) -> list[str]:
    """Why a merged corpus breaks the new-share or pt-PT floor."""
    failures = []
    if stats["new_share"] < MIN_NEW_SHARE:
        failures.append(f"{stats['site']}: new share {stats['new_share']:.1%} < 50 %")
    if stats["pt_share"] < MIN_PT_SHARE:
        failures.append(f"{stats['site']}: pt-PT share {stats['pt_share']:.1%} < 55 %")
    return failures


def heldout_findings(stats: dict[str, Any]) -> tuple[list[str], list[str]]:
    """``(failures, warnings)`` of a held-out set's pt-PT share.

    Below :data:`HELDOUT_MIN_PT_SHARE` (the replay floor) fails; between it
    and the :data:`MIN_PT_SHARE` target only warns.
    """
    share = stats["pt_share"]
    if share < HELDOUT_MIN_PT_SHARE:
        return [f"{stats['site']} held-out: pt-PT share {share:.1%} "
                f"< {HELDOUT_MIN_PT_SHARE:.0%}"], []
    if share < MIN_PT_SHARE:
        return [], [f"{stats['site']} held-out: pt-PT share {share:.1%} "
                    f"below the {MIN_PT_SHARE:.0%} target"]
    return [], []


def run(relabel: Path, check: bool) -> tuple[int, dict[str, Any]]:
    """Merge everything; write unless ``check`` or a constraint fails."""
    names_client = client_matcher(load_redaction_patterns(None))
    corpora = {site: merge_site(site, relabel, names_client)
               for site in ("refine", "forge-complexity")}
    heldout = merge_heldout(relabel, names_client)
    stats: dict[str, Any] = {"corpora": [shares(m) for m in corpora.values()],
                             "heldout": [shares(m) for m in heldout.values()]}
    findings = [heldout_findings(s) for s in stats["heldout"]]
    failures = [f for s in stats["corpora"] for f in constraint_failures(s)]
    failures += [f for fails, _ in findings for f in fails]
    stats["failures"] = failures
    stats["warnings"] = [w for _, warns in findings for w in warns]
    if failures or check:
        return (1 if failures else 0), stats
    for site, merged in corpora.items():
        write_corpus(default_corpus_path(site), merged.cases)
    for site, merged in heldout.items():
        write_corpus(heldout_corpus_path(site), merged.cases)
    return 0, stats


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: 0 merged (or valid with ``--check``), 1 constraint/label failure, 2 usage."""
    parser = argparse.ArgumentParser(prog="corpus_merge.py")
    parser.add_argument("--relabel", type=Path, required=True, help="directory with A/ and B/")
    parser.add_argument("--check", action="store_true", help="validate and count, write nothing")
    ns = parser.parse_args(argv)
    try:
        code, stats = run(ns.relabel, ns.check)
    except NoPatternsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except MergeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

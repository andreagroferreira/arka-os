"""Integrity lock for the vendored reference trees of the absorbed skills.

Four absorption campaigns imported third-party documentation into
``departments/*/skills/*/references/``. Those trees carry someone else's
copyright: the licences that let ArkaOS ship them are conditioned on the
attribution recorded in ``docs/THIRD-PARTY-NOTICES.md``, and that record
only stays true while the files stay what the record says they are.
Nothing enforced that until now — ``tests/python/diagram/test_vendor_integrity.py``
pinned the one 520KB blob under ``dev/diagram/vendor/`` and nothing else.

This module generalises that pin to the four reference trees.

Scope (each tree is vendored end to end — every file in it is pinned):

* ``departments/dev/skills/gsap/references/`` — gsap-skills (GreenSock)
* ``departments/brand/skills/motion-design/references/`` — motion-design-skill (LottieFiles)
* ``departments/brand/skills/design-dna/references/`` — design-dna (zanwei)
* ``departments/dev/skills/threejs/references/`` — genjutsu (AThevon)

Not every pinned file is byte-identical to its upstream: several are
"near-verbatim", with the deviations already classified in
``docs/THIRD-PARTY-NOTICES.md`` (two-line derivation headers on the gsap
modules and ``threejs/references/r3f.md``; sibling cross-references
rewritten from upstream skill slugs to in-repo ``references/<name>.md``
paths). The pin is therefore of the file **as it stands in this repo**,
not of the upstream original — it is a tamper guard, not a verbatimness
proof. See ``_DRIFT_INSTRUCTIONS`` for what a future change must do.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTICES = REPO_ROOT / "docs" / "THIRD-PARTY-NOTICES.md"

#: The vendored trees this module locks, in full. Every file found under
#: them must appear in :data:`VENDORED` — see
#: :func:`test_every_vendored_file_is_pinned`.
VENDORED_TREES = (
    "departments/dev/skills/gsap/references",
    "departments/brand/skills/motion-design/references",
    "departments/brand/skills/design-dna/references",
    "departments/dev/skills/threejs/references",
)

_DRIFT_INSTRUCTIONS = (
    "Vendored third-party material is pinned. If this change is intentional "
    "(an upstream bump, or a new ArkaOS deviation), it is only complete when "
    "BOTH of these happen:\n"
    "  (a) the sha256 in the VENDORED table of this file is updated IN THE "
    "SAME COMMIT as the content change; and\n"
    "  (b) the deviation is reclassified in docs/THIRD-PARTY-NOTICES.md — "
    "restate whether the file is now verbatim or near-verbatim, and say what "
    "changed.\n"
    "Recompute a hash with:  shasum -a 256 <path>\n"
    "Editing a vendored file without both makes the attribution ArkaOS "
    "publishes a false statement about material it does not own."
)


class Pin(NamedTuple):
    """One vendored file: its content hash and how the NOTICES name it."""

    sha256: str
    #: The exact string ``docs/THIRD-PARTY-NOTICES.md`` must contain for this
    #: file. ``None`` means the NOTICES spell out the full repo-relative path
    #: (directly, or inside a ``{a,b,c}`` group). A relative value is used
    #: where the NOTICES name a whole vendored subdirectory instead.
    notice: str | None = None


# --------------------------------------------------------------------------
# The pin table. Hashes record the state that shipped through the absorption
# campaigns and their Quality Gates; this lock protects them from here on.
# Changing any of them requires (a) + (b) of _DRIFT_INSTRUCTIONS.
# --------------------------------------------------------------------------
VENDORED: dict[str, Pin] = {
    # -- gsap-skills (GreenSock), NOTICES "## gsap-skills (GreenSock)" -------
    # Eight official modules, near-verbatim: each carries a two-line
    # derivation header and rewritten sibling cross-references.
    "departments/dev/skills/gsap/references/core.md": Pin(
        "b0bb66495337fd998116167c6e7054b37c18216ffdff30e87c810060b3550760"
    ),
    "departments/dev/skills/gsap/references/frameworks.md": Pin(
        "6551a3554487d8480f7b0973f98e9a00f76a87f9d84a1ffe449494b73b8ba8a5"
    ),
    "departments/dev/skills/gsap/references/performance.md": Pin(
        "9195ccf7d33154c9f0741e953624161fecf9a912e214257939e2b312f1dc7e6f"
    ),
    "departments/dev/skills/gsap/references/plugins.md": Pin(
        "772f1be0ea49f05c547add5d5dcb5efe89ec4608929eab7efd34d1232e5f5677"
    ),
    "departments/dev/skills/gsap/references/react.md": Pin(
        "acff0c3639ddad476fe79d245373088a1f6bd477f4c770fc6a6a45a2cec73c3e"
    ),
    "departments/dev/skills/gsap/references/scrolltrigger.md": Pin(
        "9538704a09726f291350f96fd3baa0f83e1e4850ed28bcd093172f40186399a4"
    ),
    "departments/dev/skills/gsap/references/timeline.md": Pin(
        "97f3a5e9829dc6e13075565c52c4cc7802fcaadd64ef15372bdcae79b57a68f2"
    ),
    "departments/dev/skills/gsap/references/utils.md": Pin(
        "8aa2709aa3065bbc461d68c8e16081e866a801acd47fc4af063dd6249cf5ff50"
    ),
    "departments/dev/skills/gsap/references/greensock-gsap-skills.LICENSE": Pin(
        "51b04b06556662dd817e8f4aa6d06bc7139dc73739e1319a7233cfde3e147b90"
    ),
    # -- motion-design-skill (LottieFiles), NOTICES "## motion-design-skill" --
    # Verbatim; the NOTICES name the three subdirectories, not each file.
    "departments/brand/skills/motion-design/references/director/choreography.md": Pin(
        "c81257b56160b9b2f3d99f78d4b8172b425c22d9ca73be06d3ffaa7305a34deb",
        "references/director/",
    ),
    "departments/brand/skills/motion-design/references/director/context-adaptation.md": Pin(
        "550e96a1c8c369513304ee74c0e89b63168bc7287b83e9ed5685bb65609986b3",
        "references/director/",
    ),
    "departments/brand/skills/motion-design/references/director/core-philosophy.md": Pin(
        "7aaa8a065d9940dad0198cf9cfe74979008495e6daf87f46f9022fff1b6a85e9",
        "references/director/",
    ),
    "departments/brand/skills/motion-design/references/director/decision-framework.md": Pin(
        "4b6758da6742475c928b4f8be8c662f4b5ed0964468ba7760df8f7635c779358",
        "references/director/",
    ),
    "departments/brand/skills/motion-design/references/director/disney-principles.md": Pin(
        "39024711890c2684a3434659a4d95a52ca8231facea74e87e79503054aaca671",
        "references/director/",
    ),
    "departments/brand/skills/motion-design/references/director/emotion-mapping.md": Pin(
        "a279e55a3f52a9f5830d38dc54679c652d9a5c26f0dd360700c16e23766d468b",
        "references/director/",
    ),
    "departments/brand/skills/motion-design/references/director/motion-personality.md": Pin(
        "66a3623b6654869482c02157ca791034a614ca6dcb02a8112049e28d292ee18a",
        "references/director/",
    ),
    "departments/brand/skills/motion-design/references/director/narrative-structure.md": Pin(
        "d49db19db40425dec027c3012d553b50fd74ed79e27ace9dec1226796469061b",
        "references/director/",
    ),
    "departments/brand/skills/motion-design/references/patterns/ambient-continuous.md": Pin(
        "f9cfa00d3325dceadcb9ffd77dcb5dcbc51d34121f3b1f162979939006056773",
        "references/patterns/",
    ),
    "departments/brand/skills/motion-design/references/patterns/entrance-exit.md": Pin(
        "70b3fc3a8d58ebe58e293e643b78fd13750d9c8ef1c8fc5fe85e52f7378cbd91",
        "references/patterns/",
    ),
    "departments/brand/skills/motion-design/references/patterns/multi-element.md": Pin(
        "46c8da91843c593deb763a4a7fa32849bdaeb7a7ecd4d559e3b21bcc976f2c46",
        "references/patterns/",
    ),
    "departments/brand/skills/motion-design/references/patterns/state-feedback.md": Pin(
        "dac86388c2d8fcdfc2f194b4f8877caedcdc010df9ce29d27dfc99d08cf8c60e",
        "references/patterns/",
    ),
    "departments/brand/skills/motion-design/references/reference/property-selection.md": Pin(
        "053d830795fc824fed27618fbd18084207af6aeed55b73c0a6e1d5665de894ae",
        "references/reference/",
    ),
    "departments/brand/skills/motion-design/references/reference/quality-checklist.md": Pin(
        "c11bf193b700d9c9ebc5d871f1d5f193bccc441c4eccc0509b53a40d6e8dc558",
        "references/reference/",
    ),
    "departments/brand/skills/motion-design/references/reference/timing-easing-tables.md": Pin(
        "e478f3b99c4cac3f96eca008e20f8808d4cfae165f5799f260092baf9b6ebcff",
        "references/reference/",
    ),
    "departments/brand/skills/motion-design/references/reference/troubleshooting.md": Pin(
        "69e5aaeee108231d51187143ae3fce4db7a42936f10682908ca9462a008a047a",
        "references/reference/",
    ),
    "departments/brand/skills/motion-design/references/motion-design-skill.LICENSE": Pin(
        "9fc2e8685daa09e28d54b6afa8a38f168417c5735a3cd676c80c159785e93a80"
    ),
    # -- design-dna (zanwei), NOTICES "## design-dna" ------------------------
    "departments/brand/skills/design-dna/references/schema.md": Pin(
        "7437729591e892ccd6c373beb316c28025c05bb78633cbe4912ee40523a03dcf"
    ),
    "departments/brand/skills/design-dna/references/generation-guide.md": Pin(
        "7073c2b297854daa49c2f2474a678a438fa65db59a2cf07bd71ca373174b4ef8"
    ),
    "departments/brand/skills/design-dna/references/design-dna.LICENSE": Pin(
        "2de108bcd0d904f8756e1135ca77ce1e3e9ca0edb1ae6abecb97dea76d27d174"
    ),
    # -- genjutsu (AThevon) -> dev/threejs, NOTICES "## three.js documentation"
    # r3f.md is near-verbatim (derivation header + two rewritten handoff
    # rows); scene-setup.md and shaders.md are verbatim.
    "departments/dev/skills/threejs/references/r3f.md": Pin(
        "9581eb7d49c4a5fa82d642608408d48fef2a460ed1d7e4e3e523577a4ae2ae40"
    ),
    "departments/dev/skills/threejs/references/scene-setup.md": Pin(
        "094e4cfd77b19627a38200631df2b4888237d91ec3308de1a7195503b0c9a45d"
    ),
    "departments/dev/skills/threejs/references/shaders.md": Pin(
        "cf58c3fa6970b2f79fb018f317cccfe508c30e02da67d928b889ffab6e1bda54"
    ),
    "departments/dev/skills/threejs/references/genjutsu.LICENSE": Pin(
        "b37092034fa60870302c3ed67c29fb355ed87ee233c17d11076f0b3e8be970ac"
    ),
}

#: Every vendored tree must keep its upstream licence text beside it.
LICENSE_COPYRIGHTS = {
    "departments/dev/skills/gsap/references/greensock-gsap-skills.LICENSE": (
        "Copyright (c) 2026 GreenSock"
    ),
    "departments/brand/skills/motion-design/references/motion-design-skill.LICENSE": (
        "Copyright (c) 2025 LottieFiles"
    ),
    "departments/brand/skills/design-dna/references/design-dna.LICENSE": (
        "Copyright (c) 2026 the design-dna authors"
    ),
    "departments/dev/skills/threejs/references/genjutsu.LICENSE": (
        "Copyright (c) 2026 Adrien Thevon"
    ),
}


def _notice_for(path: str) -> str:
    """The string the NOTICES must contain for ``path``."""
    return VENDORED[path].notice or path


def _notice_denotes_path(path: str, notice: str) -> bool:
    """Whether ``notice`` is a component-aligned, specific reference to ``path``.

    "Specific" rules out one-component references such as a bare
    ``references/``: true of every vendored file here, and therefore
    worthless as the attribution trail this cross-check is meant to keep.
    """
    if len([part for part in notice.split("/") if part]) < 2:
        return False
    if notice.endswith("/"):
        return path.startswith(notice) or f"/{notice}" in path
    return path == notice or path.endswith(f"/{notice}")


def _digest(path: str) -> str | None:
    """sha256 of a vendored file, or ``None`` when it is gone."""
    target = REPO_ROOT / path
    if not target.is_file():
        return None
    return hashlib.sha256(target.read_bytes()).hexdigest()


def _files_on_disk() -> set[str]:
    return {
        child.relative_to(REPO_ROOT).as_posix()
        for tree in VENDORED_TREES
        for child in (REPO_ROOT / tree).rglob("*")
        if child.is_file()
    }


def _expanded_notices() -> str:
    """The NOTICES text with ``prefix{a,b,c}suffix`` groups expanded.

    The absorption sections name whole module sets in brace form, e.g.
    ``references/{core,timeline}.md``. Expanding lets the cross-check ask
    for a plain repo-relative path and still find it.
    """
    raw = NOTICES.read_text(encoding="utf-8")
    expansions = [
        f"{prefix}{option.strip()}{suffix}"
        for prefix, group, suffix in re.findall(
            r"([^\s`]*)\{([^{}]+)\}([^\s`]*)", raw
        )
        for option in group.split(",")
    ]
    return "\n".join([raw, *expansions])


def test_every_vendored_file_is_pinned() -> None:
    """No file may enter or leave a vendored tree without moving this table."""
    on_disk = _files_on_disk()
    pinned = set(VENDORED)
    assert on_disk == pinned, (
        f"vendored trees drifted from the pin table.\n"
        f"  unpinned files on disk: {sorted(on_disk - pinned) or 'none'}\n"
        f"  pinned files missing from disk: {sorted(pinned - on_disk) or 'none'}\n"
        f"{_DRIFT_INSTRUCTIONS}"
    )


def test_vendored_files_match_pinned_sha256() -> None:
    """The lock itself: vendored bytes are exactly what the table records."""
    drifted = [
        path for path, pin in sorted(VENDORED.items()) if _digest(path) != pin.sha256
    ]
    assert not drifted, (
        f"vendored file(s) changed: {', '.join(drifted)}\n{_DRIFT_INSTRUCTIONS}"
    )


def test_every_pinned_path_is_named_in_third_party_notices() -> None:
    """Cross-check: a pinned file with no attribution entry is a licence hole."""
    notices = _expanded_notices()
    orphans = {
        path: _notice_for(path)
        for path in sorted(VENDORED)
        if _notice_for(path) not in notices
    }
    assert not orphans, (
        "vendored file(s) pinned here but no longer named in "
        "docs/THIRD-PARTY-NOTICES.md — expected reference string per file: "
        f"{orphans}.\n"
        "Every vendored file must stay traceable to the upstream section that "
        "licenses it. Restore the entry, or drop the pin together with the "
        "file it covers."
    )


def test_notice_reference_points_at_the_pinned_path() -> None:
    """Guard the cross-check: a ``notice`` must actually denote its own file.

    Without this, the previous test could be satisfied by any string that
    happens to occur somewhere in the NOTICES.
    """
    mismatched = {
        path: _notice_for(path)
        for path in sorted(VENDORED)
        if not _notice_denotes_path(path, _notice_for(path))
    }
    assert not mismatched, (
        "notice reference(s) are not a component-aligned prefix, suffix or "
        f"parent directory of the file they claim to cover: {mismatched}"
    )


def test_license_files_are_pinned_and_carry_their_copyright() -> None:
    """Each vendored tree keeps its licence text, pinned like the rest."""
    for path, copyright_line in sorted(LICENSE_COPYRIGHTS.items()):
        assert path in VENDORED, f"{path} is not in the pin table"
        text = (REPO_ROOT / path).read_text(encoding="utf-8")
        assert copyright_line in text, f"{path} lost its copyright line"

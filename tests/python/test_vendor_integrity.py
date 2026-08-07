"""Integrity lock for the vendored reference trees of the absorbed skills.

Nine absorption campaigns imported third-party documentation into
``departments/*/skills/*/references/`` and ``arka/skills/*/references/``.
Those trees carry someone else's copyright: the licences that let ArkaOS
ship them are conditioned on the attribution recorded in
``docs/THIRD-PARTY-NOTICES.md``, and that record only stays true while the
files stay what the record says they are. Nothing enforced that until now
— ``tests/python/diagram/test_vendor_integrity.py`` pinned the one 520KB
blob under ``dev/diagram/vendor/`` and nothing else.

This module generalises that pin to every vendored reference tree, by
upstream:

* gsap-skills (GreenSock) — ``dev/gsap``
* motion-design-skill (LottieFiles) — ``brand/motion-design``
* design-dna (zanwei) — ``brand/design-dna``
* genjutsu (AThevon) — ``dev/threejs``, ``dev/canvas-generative``,
  ``dev/framer-motion``, ``dev/css-native``
* hallmark (Hassan El Mghari) + impeccable (Paul Bakaus, Apache-2.0) —
  ``landing/page-architect``, ``brand/design-review``,
  ``brand/design-system``, ``brand/colors``, ``dev/animated-website``
* scroll-world (cyw) — ``dev/scroll-world`` (includes executable
  ``scrub-engine.js`` and ``knockout.py``)
* stop-slop (Hardik Pandya) + marketing-skills (Corey Haines) —
  ``arka/skills/human-writing``
* claude-video (Bradley Bonanno) — ``dev/watch``

Three facts this module refuses to paper over:

1. **The pin is of the file as it stands in this repo**, not of the
   upstream original. Several files are "near-verbatim", with deviations
   already classified in the NOTICES (derivation headers, cross-references
   rewritten to in-repo paths). This is a tamper guard, not a verbatimness
   proof — proving that would need a diff against the upstream SHAs.
2. **Not every file in a vendored tree is vendored.** ArkaOS wrote some of
   them; they are listed in :data:`ARKAOS_AUTHORED` with the evidence, and
   are deliberately not pinned or attributed.
3. **Some vendored files have no per-file trail in the NOTICES yet.** They
   are recorded in :data:`NOTICES_GAP` — still integrity-locked, but
   flagged as an open attribution debt rather than silently waved through.

See ``_DRIFT_INSTRUCTIONS`` for what a future change must do.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTICES = REPO_ROOT / "docs" / "THIRD-PARTY-NOTICES.md"

#: The vendored trees this module locks, in full. Every file found under
#: them must be classified — pinned in :data:`VENDORED` or declared ArkaOS's
#: own in :data:`ARKAOS_AUTHORED`. See
#: :func:`test_every_file_in_a_vendored_tree_is_classified`. Paths are
#: repo-relative, so trees outside ``departments/`` (``arka/skills/...``)
#: need nothing special.
VENDORED_TREES = (
    "departments/dev/skills/gsap/references",
    "departments/brand/skills/motion-design/references",
    "departments/brand/skills/design-dna/references",
    "departments/dev/skills/threejs/references",
    "departments/landing/skills/page-architect/references",
    "departments/brand/skills/design-review/references",
    "departments/brand/skills/design-system/references",
    "arka/skills/human-writing/references",
    "departments/dev/skills/scroll-world/references",
    "departments/brand/skills/colors/references",
    "departments/dev/skills/animated-website/references",
    "departments/dev/skills/canvas-generative/references",
    "departments/dev/skills/framer-motion/references",
    "departments/dev/skills/css-native/references",
    "departments/dev/skills/watch/references",
)

#: Notices that name a vendored tree root (``references/``) rather than a
#: file or a subdirectory inside it are true of every file in that tree and
#: therefore attribute nothing. :func:`_notice_denotes_path` rejects them.
_TREE_ROOT_REFERENCES = frozenset(
    name for tree in VENDORED_TREES for name in (tree, tree.rsplit("/", 1)[-1])
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
def _tree(root: str, entries: dict[str, Pin]) -> dict[str, Pin]:
    """Re-root a tree's entries onto their full repo-relative paths."""
    return {f"{root}/{rel}": pin for rel, pin in entries.items()}


VENDORED: dict[str, Pin] = {
    # -- gsap-skills (GreenSock) — eight official modules, near-verbatim: each
    # carries a two-line derivation header and rewritten cross-references.
    **_tree(
        "departments/dev/skills/gsap/references",
        {
            "core.md": Pin(
                "b0bb66495337fd998116167c6e7054b37c18216ffdff30e87c810060b3550760",
            ),
            "frameworks.md": Pin(
                "6551a3554487d8480f7b0973f98e9a00f76a87f9d84a1ffe449494b73b8ba8a5",
            ),
            "greensock-gsap-skills.LICENSE": Pin(
                "51b04b06556662dd817e8f4aa6d06bc7139dc73739e1319a7233cfde3e147b90",
            ),
            "performance.md": Pin(
                "9195ccf7d33154c9f0741e953624161fecf9a912e214257939e2b312f1dc7e6f",
            ),
            "plugins.md": Pin(
                "772f1be0ea49f05c547add5d5dcb5efe89ec4608929eab7efd34d1232e5f5677",
            ),
            "react.md": Pin(
                "acff0c3639ddad476fe79d245373088a1f6bd477f4c770fc6a6a45a2cec73c3e",
            ),
            "scrolltrigger.md": Pin(
                "9538704a09726f291350f96fd3baa0f83e1e4850ed28bcd093172f40186399a4",
            ),
            "timeline.md": Pin(
                "97f3a5e9829dc6e13075565c52c4cc7802fcaadd64ef15372bdcae79b57a68f2",
            ),
            "utils.md": Pin(
                "8aa2709aa3065bbc461d68c8e16081e866a801acd47fc4af063dd6249cf5ff50",
            ),
        },
    ),
    # -- motion-design-skill (LottieFiles) — verbatim; the NOTICES name the three
    # subdirectories rather than each file.
    **_tree(
        "departments/brand/skills/motion-design/references",
        {
            "director/choreography.md": Pin(
                "c81257b56160b9b2f3d99f78d4b8172b425c22d9ca73be06d3ffaa7305a34deb",
                "references/director/",
            ),
            "director/context-adaptation.md": Pin(
                "550e96a1c8c369513304ee74c0e89b63168bc7287b83e9ed5685bb65609986b3",
                "references/director/",
            ),
            "director/core-philosophy.md": Pin(
                "7aaa8a065d9940dad0198cf9cfe74979008495e6daf87f46f9022fff1b6a85e9",
                "references/director/",
            ),
            "director/decision-framework.md": Pin(
                "4b6758da6742475c928b4f8be8c662f4b5ed0964468ba7760df8f7635c779358",
                "references/director/",
            ),
            "director/disney-principles.md": Pin(
                "39024711890c2684a3434659a4d95a52ca8231facea74e87e79503054aaca671",
                "references/director/",
            ),
            "director/emotion-mapping.md": Pin(
                "a279e55a3f52a9f5830d38dc54679c652d9a5c26f0dd360700c16e23766d468b",
                "references/director/",
            ),
            "director/motion-personality.md": Pin(
                "66a3623b6654869482c02157ca791034a614ca6dcb02a8112049e28d292ee18a",
                "references/director/",
            ),
            "director/narrative-structure.md": Pin(
                "d49db19db40425dec027c3012d553b50fd74ed79e27ace9dec1226796469061b",
                "references/director/",
            ),
            "motion-design-skill.LICENSE": Pin(
                "9fc2e8685daa09e28d54b6afa8a38f168417c5735a3cd676c80c159785e93a80",
            ),
            "patterns/ambient-continuous.md": Pin(
                "f9cfa00d3325dceadcb9ffd77dcb5dcbc51d34121f3b1f162979939006056773",
                "references/patterns/",
            ),
            "patterns/entrance-exit.md": Pin(
                "70b3fc3a8d58ebe58e293e643b78fd13750d9c8ef1c8fc5fe85e52f7378cbd91",
                "references/patterns/",
            ),
            "patterns/multi-element.md": Pin(
                "46c8da91843c593deb763a4a7fa32849bdaeb7a7ecd4d559e3b21bcc976f2c46",
                "references/patterns/",
            ),
            "patterns/state-feedback.md": Pin(
                "dac86388c2d8fcdfc2f194b4f8877caedcdc010df9ce29d27dfc99d08cf8c60e",
                "references/patterns/",
            ),
            "reference/property-selection.md": Pin(
                "053d830795fc824fed27618fbd18084207af6aeed55b73c0a6e1d5665de894ae",
                "references/reference/",
            ),
            "reference/quality-checklist.md": Pin(
                "c11bf193b700d9c9ebc5d871f1d5f193bccc441c4eccc0509b53a40d6e8dc558",
                "references/reference/",
            ),
            "reference/timing-easing-tables.md": Pin(
                "e478f3b99c4cac3f96eca008e20f8808d4cfae165f5799f260092baf9b6ebcff",
                "references/reference/",
            ),
            "reference/troubleshooting.md": Pin(
                "69e5aaeee108231d51187143ae3fce4db7a42936f10682908ca9462a008a047a",
                "references/reference/",
            ),
        },
    ),
    # -- design-dna (zanwei) — verbatim.
    **_tree(
        "departments/brand/skills/design-dna/references",
        {
            "design-dna.LICENSE": Pin(
                "2de108bcd0d904f8756e1135ca77ce1e3e9ca0edb1ae6abecb97dea76d27d174",
            ),
            "generation-guide.md": Pin(
                "7073c2b297854daa49c2f2474a678a438fa65db59a2cf07bd71ca373174b4ef8",
            ),
            "schema.md": Pin(
                "7437729591e892ccd6c373beb316c28025c05bb78633cbe4912ee40523a03dcf",
            ),
        },
    ),
    # -- genjutsu (AThevon) — r3f.md is near-verbatim (derivation header + two
    # rewritten handoff rows); the rest verbatim. One licence text, four copies.
    **_tree(
        "departments/dev/skills/threejs/references",
        {
            "genjutsu.LICENSE": Pin(
                "b37092034fa60870302c3ed67c29fb355ed87ee233c17d11076f0b3e8be970ac",
            ),
            "r3f.md": Pin(
                "9581eb7d49c4a5fa82d642608408d48fef2a460ed1d7e4e3e523577a4ae2ae40",
            ),
            "scene-setup.md": Pin(
                "094e4cfd77b19627a38200631df2b4888237d91ec3308de1a7195503b0c9a45d",
            ),
            "shaders.md": Pin(
                "cf58c3fa6970b2f79fb018f317cccfe508c30e02da67d928b889ffab6e1bda54",
            ),
        },
    ),
    **_tree(
        "departments/dev/skills/canvas-generative/references",
        {
            "algorithms.md": Pin(
                "8a636acf9104e87bc7f425031f5df1a58edd31c3cd5baea25e2c50fb1d4d357f",
                "references/algorithms.md",
            ),
            "genjutsu.LICENSE": Pin(
                "b37092034fa60870302c3ed67c29fb355ed87ee233c17d11076f0b3e8be970ac",
            ),
        },
    ),
    **_tree(
        "departments/dev/skills/framer-motion/references",
        {
            "api.md": Pin(
                "0c94ed64d454fbb63722e5c75370730871173a15899f43282aa52ace72d9c7eb",
                "references/api.md",
            ),
            "genjutsu.LICENSE": Pin(
                "b37092034fa60870302c3ed67c29fb355ed87ee233c17d11076f0b3e8be970ac",
            ),
        },
    ),
    **_tree(
        "departments/dev/skills/css-native/references",
        {
            "genjutsu.LICENSE": Pin(
                "b37092034fa60870302c3ed67c29fb355ed87ee233c17d11076f0b3e8be970ac",
            ),
            "modern-css.md": Pin(
                "db824e7046ffaca1c67393d3acdfc15ea6729eb71bab2988761b60506087aeb9",
                "references/modern-css.md",
            ),
        },
    ),
    # -- hallmark (Hassan El Mghari, MIT) + impeccable (Paul Bakaus, Apache-2.0) —
    # near-verbatim ports and W2 merges across five skills.
    **_tree(
        "departments/brand/skills/design-review/references",
        {
            "anti-patterns.md": Pin(
                "c08dc0dbe3d4c1fdfb3c1afaa9c2be3bba40f87528ca38e1f078ba06a4ba3912",
            ),
            "critique-protocol.md": Pin(
                "9528d3e0a0acb67f2aee3e22bcb5c47ce50e052209a0e73a5eea631dac746127",
            ),
            "design-registers.md": Pin(
                "de26c09b64ee9e3e416f53261c7eb1ed61ef48b20891e7f642d88ce15a0e842c",
            ),
            "genres/atmospheric.md": Pin(
                "7fd1c0feb18a4bee075715a1a39d5fc254cd206193c22b5f34c863a2aed3fa12",
                "departments/brand/skills/design-review/references/genres/",
            ),
            "genres/editorial.md": Pin(
                "c3a7d868e3e84ea8c23d2a0f1563d482d75067d2f376bde658e586fde705f4bb",
                "departments/brand/skills/design-review/references/genres/",
            ),
            "genres/modern-minimal.md": Pin(
                "25af3ded5ea608bacde327fe6c1f31c6980ce702c472db819fd1dc9e484b0e31",
                "departments/brand/skills/design-review/references/genres/",
            ),
            "genres/playful.md": Pin(
                "c09bf90a7f19800ca39b3ff0e0eafadfce4fae7026b20990e61f685680c31482",
                "departments/brand/skills/design-review/references/genres/",
            ),
            "hallmark.LICENSE": Pin(
                "06088a8b94598626f27612dea42300154bf7be967c85d9d3eee4490cb056af7d",
            ),
            "impeccable.LICENSE": Pin(
                "02bb8c3b4e70190e3986c0404ad2fd8d639b4f534252d82379cc1b502b6d1812",
            ),
            "impeccable.NOTICE": Pin(
                "c60a093c2845fd9fb82f9c6f742ece31f379f8190b535309d32d66c45ccffdcb",
            ),
            "slop-test.md": Pin(
                "b3d66d40d54a207e77bf2c3b6a05809c3cb1dec5f65c4ce414774c10e7573b1d",
            ),
        },
    ),
    **_tree(
        "departments/brand/skills/design-system/references",
        {
            "design-dna-study.md": Pin(
                "e1acc9d41ed8153bb87e1ac875712a5c5c56b6c6624a8136b31784fa1fdf0db1",
            ),
            "design-md-spec.md": Pin(
                "c46d4fcfa962d0c9b7d3530ec88ff11d1b4bd466fc64202065ff266fb78ce3e2",
            ),
            "hallmark.LICENSE": Pin(
                "06088a8b94598626f27612dea42300154bf7be967c85d9d3eee4490cb056af7d",
            ),
            "impeccable.LICENSE": Pin(
                "02bb8c3b4e70190e3986c0404ad2fd8d639b4f534252d82379cc1b502b6d1812",
            ),
            "interaction-states.md": Pin(
                "815a8f566a8c826f574b4ad7ba2737c32f091cfe86fabf83275bff4566bc95c3",
                "interaction-states.md",
            ),
            "themes/carnival.md": Pin(
                "8bbe2d2e510faf5386d71e22ebd8122835683c077a249153a42970c68044fce9",
                "departments/brand/skills/design-system/references/themes/",
            ),
            "themes/cobalt.md": Pin(
                "896f7a0f8aa58a4d8ce1323779b153ec2bed900e4147da270c0bed45c47c6385",
                "departments/brand/skills/design-system/references/themes/",
            ),
            "themes/hum.md": Pin(
                "d40627a078fafbc2fc2f6262939e3311eac4f73586421a7f0109ad4624957941",
                "departments/brand/skills/design-system/references/themes/",
            ),
            "themes/lumen.md": Pin(
                "072f777aef8e58fc8d60e0399c672fecbd3a40dc3fc44d121179604195e69e8c",
                "departments/brand/skills/design-system/references/themes/",
            ),
            "typography-craft.md": Pin(
                "8ddc84ac8e2f47c55e8a27b4c75447f6124c469eb679e5f3faee0dfb19c2210c",
            ),
        },
    ),
    **_tree(
        "departments/landing/skills/page-architect/references",
        {
            "component-cookbook.md": Pin(
                "0ca22cd4ede2e7efea057c33b07b3927b723cb410d60419c794f456d06b81eca",
            ),
            "components/c1-outlined-chip.md": Pin(
                "ea53ac0707b05d3b7839de32b391367fb1e2d5ef15ae087ea16de59bcc34f648",
                "components/",
            ),
            "components/c2-inline-form-as-cta.md": Pin(
                "63d0b0e70354db41e5024ca909362efc929cb78eaee9c213fbc2ae7b456695f4",
                "components/",
            ),
            "components/c3-typographic-link.md": Pin(
                "8a88f6c28623c9e97ba8eea890707975fc76504d0e6740c5d0fecd1f5a8d6359",
                "components/",
            ),
            "components/c4-sticky-bottom-bar.md": Pin(
                "164075c16183daadb1230ece27238a95e802cd6fceedc79af66d2bb12d8d9ba0",
                "components/",
            ),
            "components/f1-bento-grid.md": Pin(
                "874d5c2aa20bd5de3459ff08c7882edea67c6873353c6b0634f33b93b6993e42",
                "components/",
            ),
            "components/f2-sticky-scroll-stack.md": Pin(
                "63dc2c6c46e257a675683e47dea070acb8ab5489e8746ccd86a182befb1e4910",
                "components/",
            ),
            "components/f3-tabular-spec-sheet.md": Pin(
                "a900853c0a393197e94ff48ded2c0920c0e317b877cb345e4c1ee1ce07a4ee59",
                "components/",
            ),
            "components/f4-step-sequence.md": Pin(
                "a58d6320288d193872f1421a8dd1dea9caf010b70a1e17f1eb75dfad166c7d58",
                "components/",
            ),
            "components/f5-annotated-screenshot.md": Pin(
                "961bdb5c669202cc1bb9fc8905c2dd38886642cbefec240ca090ee832a7dbed1",
                "components/",
            ),
            "components/f6-product-card-grid.md": Pin(
                "90e7c92c4c1dc85e8a385ce46791300befcb4bafcb6d086d4e72c13b4ffd6ea0",
                "components/",
            ),
            "components/ft1-mast-headed.md": Pin(
                "10e15e3bdefe4221e5b8caf3df9a1e771f5137abcfebb5b2935ea2f1d9123664",
                "components/",
            ),
            "components/ft2-inline-rule-single-line.md": Pin(
                "35d3f906c69281fa267f5fbd9acc97238690db4954cf77f71c4d2fb822ffa8d8",
                "components/",
            ),
            "components/ft3-index-style-category-list.md": Pin(
                "e5f0c254c82f1914c70e6e9622e6f5c93eafd387ba2cd82caea3025f15e7157c",
                "components/",
            ),
            "components/ft4-dense-typographic.md": Pin(
                "e21c0caba34fa779626c09bbf72b653d09cf5dea5d593bf57143f6cf86ef3ef6",
                "components/",
            ),
            "components/ft5-statement.md": Pin(
                "5b6b82b763e1f869d541aec376f2674381f5cd7b5ddfc19a147ac4e84e87d5f9",
                "components/",
            ),
            "components/ft6-letter-close.md": Pin(
                "7eb2a9fb2e639e9689f1d13dff022575e3866c6ff7ffbec37dfccea40124d277",
                "components/",
            ),
            "components/ft7-newsletter-first.md": Pin(
                "56e316416173f4e520a273cbb58d784bfdb4278ad2fd471d272ea1d52ce2008d",
                "components/",
            ),
            "components/ft8-marquee-scroll.md": Pin(
                "be9a6cf51462b4c8a539f46287d68479a6c219b5456ee9fa51c4207e79e2e4b5",
                "components/",
            ),
            "components/h1-marquee.md": Pin(
                "0995466fae077f85d97018b1988b11601402134b648b81ee125c73c84783a263",
                "components/",
            ),
            "components/h2-split-diptych.md": Pin(
                "71c452f7e137fe4ac6e0e3955b34c7306fab43bc4f99a787f3bade0868930bd5",
                "components/",
            ),
            "components/h3-quote-led.md": Pin(
                "9284860f425b10b3ab37708a97406e98a6ac7d651e706efc3110b989db6519db",
                "components/",
            ),
            "components/h4-stat-led.md": Pin(
                "ea18f14ba797e4f0a00e96db5469e4d10e39951d8a864cd06ba0a13ad78803f3",
                "components/",
            ),
            "components/h5-letter-hero.md": Pin(
                "188fe5636615dad166ca47a7f84f26576b8aa562d0c39fe1495337c51412bba4",
                "components/",
            ),
            "components/h6-photographic-fold.md": Pin(
                "fb5773483ec08737faf1f30cee9c593894b53de030c73b88a282bf1ba3a65b75",
                "components/",
            ),
            "components/h7-demo-video-clipped-by-viewport-edge.md": Pin(
                "55b6d73de1bf93572171d4bfde7a510b61e73a15fb20181c6e07230ba8a0c025",
                "components/",
            ),
            "components/h8-mockup-split-browser-framed.md": Pin(
                "36e954ef76ff0b2b9d8173a736e370e411b728b9d95996cb542a052eeb138fb6",
                "components/",
            ),
            "components/h9-custom-illustration-centerpiece.md": Pin(
                "5f9c93a05daee9aa1790659fa685a8818988ff89d1527c109ba3a620055f622b",
                "components/",
            ),
            "components/n1-wordmark-2-links.md": Pin(
                "7317e8e826de412377d959f2b69fc6b194c5d3696dcd67e85fa4513f9697b58c",
                "components/",
            ),
            "components/n10-floating-on-scroll-morph.md": Pin(
                "2644a50c39b4cc2569e7790948294249773edcfd0d66beb63c5d985ba5d29968",
                "components/",
            ),
            "components/n11-mega-menu.md": Pin(
                "439dde27a9b6c52123cbfeec7341d2b65fbb0f7dd575bebb1fa88ddd3482d6fd",
                "components/",
            ),
            "components/n12-banner-retract.md": Pin(
                "46db97193183852344ef2e0619ffdfcfa073e101f8f2496476cf3f3da97afb1c",
                "components/",
            ),
            "components/n13-inline-cmdk-pill.md": Pin(
                "66a76175e63c446b420934c224d422965da45536a71f0cc2705764de33180109",
                "components/",
            ),
            "components/n1b-saas-three-section.md": Pin(
                "8e636d6ffb6ad5251dd6dedfbc5a487711bac49dc379fef8f6b0e36997a3570c",
                "components/",
            ),
            "components/n2-floating-chip.md": Pin(
                "41b946bfe1c36b69246ab44a9866a4ce6d80b45679dfdf972084e25df6d64149",
                "components/",
            ),
            "components/n3-side-rail.md": Pin(
                "79a67c666f781a6b421a42966f5fb2eae46326721fa1dea0dcb6573b3dea2596",
                "components/",
            ),
            "components/n4-hidden-behind-k.md": Pin(
                "229b619492bbe0e051ee2dc44f93f98bd2c73c3e70174aeab65851605459b601",
                "components/",
            ),
            "components/n5-floating-pill.md": Pin(
                "08c817787c872fa13f15f4a2079c819549029e73fceacc3bbd28ed515b280a27",
                "components/",
            ),
            "components/n6-newspaper-masthead.md": Pin(
                "96f015562b3b022559b6b91ce02758f86120215f5bcd76a3da0cfed25a7906e0",
                "components/",
            ),
            "components/n7-brutal-slab.md": Pin(
                "0c483de0e935e76d421bbadee407fb9ca85239fe7d28f8dc05a13f780efd0c04",
                "components/",
            ),
            "components/n8-terminal-command.md": Pin(
                "6aac7095b08837e493b5a517dabc4d96a61546fce6939774c158150b0838b099",
                "components/",
            ),
            "components/n9-edge-aligned-minimal.md": Pin(
                "aabfcb037a0bd18fb4e67b8a6a07f9e6d9edd5fff23962fa292a2d63553dd007",
                "components/",
            ),
            "components/s1-left-margin-numbered.md": Pin(
                "d8c7a2974d173219ba98b9eaeb624aaf6290f50549eaeb83b3b8082bcae84560",
                "components/",
            ),
            "components/s2-hanging.md": Pin(
                "de22b92ad57d750654f0452b314c73e32d4223fb170572de07f8ed58a7698291",
                "components/",
            ),
            "components/s3-sticky-pinned.md": Pin(
                "71d2e4a81e21ed98599bb531dd91c20bb55fbfd2fbd2f5ed6776607e363dc1ee",
                "components/",
            ),
            "components/s4-inline-no-break.md": Pin(
                "afc673cb900a58cc7b82cbd4075245a6e90981fde9e2d77ac717f9a6660d8e6b",
                "components/",
            ),
            "components/s5-bottom-anchored.md": Pin(
                "f3f9f25021df1ac731aaf05a9195da1f0931689dd3c96fc7c18a2b6aa310ec76",
                "components/",
            ),
            "components/t1-pull-quote-with-marginalia.md": Pin(
                "5d263b1a349b3440e74aebe73e93514fb459259b497de69a892715773548e420",
                "components/",
            ),
            "components/t2-logo-wall-hairline.md": Pin(
                "d75a81b9fdbf2f8e8b5c311793f7b5c78633b7d8d718281df7661c58e8a4389e",
                "components/",
            ),
            "components/t3-single-huge-quote.md": Pin(
                "9d597cb310550d6553f7d6683daca78a5f36ad22a37f9c274524ed37206baf03",
                "components/",
            ),
            "components/t4-numbered-stat-strip.md": Pin(
                "ab775fdd7305fd07e3786e703a74f3cdf3fafa2b96935fabd6f7af6d0c53261f",
                "components/",
            ),
            "floating-nav.md": Pin(
                "30a8dc3eac60c6e383210913b2ffde47d3fb4de48dcfd87b7d6834313b4a9b2e",
                "floating-nav.md",
            ),
            "hallmark.LICENSE": Pin(
                "06088a8b94598626f27612dea42300154bf7be967c85d9d3eee4490cb056af7d",
            ),
            "hero-enrichment.md": Pin(
                "cef46b967f519a6b91e24220ed069e9db34dc6cf76fbd27faa1ed45b42764b85",
            ),
            "impeccable.LICENSE": Pin(
                "02bb8c3b4e70190e3986c0404ad2fd8d639b4f534252d82379cc1b502b6d1812",
            ),
            "layout-craft.md": Pin(
                "2c925743102066b8fe5cdf6644c268089789d45fa60ac78ac1baecf99e81a359",
            ),
            "macrostructures/01-bento-grid.md": Pin(
                "5a44b4db7d97348124e8309100bc51c026e1951aeaf5780f1e6b6d9376d00b0a",
                "macrostructures/",
            ),
            "macrostructures/02-long-document.md": Pin(
                "c4bf3b72603bd5d33f34ff26a278ddb6ae92697a981788dd5e07caf007949020",
                "macrostructures/",
            ),
            "macrostructures/03-marquee-hero.md": Pin(
                "688df38d69a50c1cfe6efe8fa9d2d86635d3f7851ca947a84e539fb8e4a1b5e8",
                "macrostructures/",
            ),
            "macrostructures/04-stat-led.md": Pin(
                "578e4215f446f262bcbaaedd264046451c04a8f81e5343e93bada5bdd3ce9adb",
                "macrostructures/",
            ),
            "macrostructures/05-workbench.md": Pin(
                "eed320e0c8eed282243727bb030cf6e76ac4ba409bcb4f577dfee7d8461605e3",
                "macrostructures/",
            ),
            "macrostructures/06-conversational-faq.md": Pin(
                "30f8af54329f4a1bee27636b7000894e9e9a3319fd9f49163ec2186661f62d56",
                "macrostructures/",
            ),
            "macrostructures/07-manifesto.md": Pin(
                "9785c8b4b781f1e38f0ffd639d3c145d397b697a436df611fee332307b18be71",
                "macrostructures/",
            ),
            "macrostructures/08-photographic.md": Pin(
                "d54ca022aaa01b9933b05cda747eb12daf1ca651b0546cc4e487df3d012e8bfd",
                "macrostructures/",
            ),
            "macrostructures/09-quote-led.md": Pin(
                "cefa35f5d8f3e7cba0546abf5742ed17abc8493837a0e2bc4425cef528edc455",
                "macrostructures/",
            ),
            "macrostructures/10-specimen.md": Pin(
                "521db68e4cb0c13046f45dc359c4b6c19f12f1e1e0344df97fff85ec591034c6",
                "macrostructures/",
            ),
            "macrostructures/11-catalogue.md": Pin(
                "e5767e677a14e294cf632ccebfc77cc593f44f74dedf5a1dc8a5fa55cacdb5ce",
                "macrostructures/",
            ),
            "macrostructures/12-letter.md": Pin(
                "e9474501064756830ed7aa6df29e9c4a9c28545afd61e2221dfdc161cfd1a0b2",
                "macrostructures/",
            ),
            "macrostructures/13-index-first.md": Pin(
                "7713812d3c6ab658b07acbb957c85f1a03bfabd56b2de8d84db96278856df9aa",
                "macrostructures/",
            ),
            "macrostructures/14-narrative-workflow.md": Pin(
                "9080ee22d6bf15b393c13e6601c7f8d154d3e6aa2a31cf875374e1872e60cf13",
                "macrostructures/",
            ),
            "macrostructures/15-split-studio.md": Pin(
                "cb60b8b94aec95b7a55555cca92c807e71dfece5efa8fc8307ccb15a92f5c1ed",
                "macrostructures/",
            ),
            "macrostructures/16-feature-stack.md": Pin(
                "f0b92e7f943b57df369a916dbbd86f8f1f9f2783ab9cbdeaf80a9ef5361e6933",
                "macrostructures/",
            ),
            "macrostructures/17-type-specimen.md": Pin(
                "4af408d36cc91c6130ad401e80e037d499c980579404320ca12179d5a2c7fc14",
                "macrostructures/",
            ),
            "macrostructures/18-portfolio-grid.md": Pin(
                "be84628d3665f049198bf134899cd2f261c7ac636aa1e24be8b456b595db00e3",
                "macrostructures/",
            ),
            "macrostructures/19-map-diagram.md": Pin(
                "e03c713eaa162da8b5085b7bbc7e32c4eaf16e18abdd3a4f10d5c1186af9fb1a",
                "macrostructures/",
            ),
            "macrostructures/20-ecosystem-index.md": Pin(
                "3d459ce24715521546ce840360603cb47971c37ebe21c487f276014323aa5609",
                "macrostructures/",
            ),
            "macrostructures/21-component-playground.md": Pin(
                "8285b1f5aaf3324e2bf16e42f892a468aeda8d529ebd5710cc10b57207a043e0",
                "macrostructures/",
            ),
            "macrostructures.md": Pin(
                "d5cc094f6b869af8136f3572838997959e3383738fd947fee4dcb3c2afd70e4e",
            ),
            "mermaid-templates.md": Pin(
                "362190c7d3f419d5f445170f1fb17beecc163937d2068922893b7a69eeb25f0f",
            ),
            "navigation-patterns.md": Pin(
                "2efa772709b753e33d5018c007147ca30aaa95a04b04dc0df6227ea5a053078b",
            ),
            "site-type-templates.md": Pin(
                "3c3cd7ce5e31c502dc071baf82bb58cb30f5edf4a2fd8ca052fbc8f3777db140",
            ),
            "ui-copy.md": Pin(
                "91fde22dafc0fdffb10cc964220a50699dd4cee8bdf23e27236207a316816c8e",
                "ui-copy.md",
            ),
        },
    ),
    **_tree(
        "departments/brand/skills/colors/references",
        {
            "hallmark.LICENSE": Pin(
                "06088a8b94598626f27612dea42300154bf7be967c85d9d3eee4490cb056af7d",
            ),
            "impeccable.LICENSE": Pin(
                "02bb8c3b4e70190e3986c0404ad2fd8d639b4f534252d82379cc1b502b6d1812",
            ),
            "oklch-theme.md": Pin(
                "860e2558658a714b4acaba5bd9f27c4a2f4e52ad748b63ff439950b6da8b2377",
            ),
        },
    ),
    **_tree(
        "departments/dev/skills/animated-website/references",
        {
            "hallmark.LICENSE": Pin(
                "06088a8b94598626f27612dea42300154bf7be967c85d9d3eee4490cb056af7d",
            ),
            "impeccable.LICENSE": Pin(
                "02bb8c3b4e70190e3986c0404ad2fd8d639b4f534252d82379cc1b502b6d1812",
            ),
            "motion-recipes.md": Pin(
                "be23e22cea3b9f2cd8d105edf830d74066cbb0188e0efb32f2603cdc1234e993",
            ),
        },
    ),
    # -- scroll-world (cyw) — verbatim, and the only vendored tree with
    # executable payload: scrub-engine.js and knockout.py.
    **_tree(
        "departments/dev/skills/scroll-world/references",
        {
            "index-template.html": Pin(
                "b59814abbe21bff1f39321eb53f9c9cd8ddf9d6a16fc861558647bf30213e3c0",
            ),
            "knockout.py": Pin(
                "c06bfc916592ba4f3dfd3e37070b20529298707ca3f94c9dcc51d508222e7792",
                "knockout.py",
            ),
            "pipeline.md": Pin(
                "e95cbd8dbb31ae2d4284de72066011f3f3271e9fcca9280f875103bea43a4edf",
            ),
            "prompts.md": Pin(
                "e14f5bd18040f5954b33843fa4ee59a25f2bde7d42c821581bc80b5a18fbfcf2",
            ),
            "scroll-world.LICENSE": Pin(
                "c4b96a7a050b85026eb68ac5b5fee2778384b14371aaeac50891dbadd848d309",
            ),
            "scrub-engine.js": Pin(
                "630bb1ab6101e5ed54eb1a24ab0be3f29e3744a95e156835b89541ea7c04752b",
            ),
        },
    ),
    # -- stop-slop (Hardik Pandya) + marketing-skills (Corey Haines) — two ArkaOS-
    # authored files in this tree are declared in ARKAOS_AUTHORED instead.
    **_tree(
        "arka/skills/human-writing/references",
        {
            "anti-slop-phrases.md": Pin(
                "81ce7c6442acbaf88b96c260037e4ad257cae016f374711fafce0c9864967bdd",
            ),
            "checklist.md": Pin(
                "db143b969b45b0933fe6eb772992890d1472d036a6c887fc98665e4fb48da43c",
            ),
            "content-refresh.md": Pin(
                "8a3a2d301bb2b8b2a780f5bef43093ab42295041b2fea2a9caeca2421ef3c79b",
            ),
            "plain-english-alternatives.md": Pin(
                "df4f820d4c63ae8a517c64a243c101658352cd07d002355bf3c97de0a00f3775",
            ),
            "stop-slop.LICENSE": Pin(
                "2e2b2beaf41cc0ce28485455a62aed81777cdcdf68702e142427aef1cd720f2c",
            ),
            "structural-patterns.md": Pin(
                "cd9749c4add37ecfefacd11451d4c56344a688e01da8ad77815dfa690297c3c3",
            ),
        },
    ),
    # -- claude-video (Bradley Bonanno) — licence text only; the scripts live
    # under the skill's scripts/, outside any references/ tree.
    **_tree(
        "departments/dev/skills/watch/references",
        {
            "claude-video.LICENSE": Pin(
                "add78957ea8124a8ae6eccd7a55c948543a9f32ea26917bf562b8cafacb01d3e",
            ),
        },
    ),
}


#: Files that live inside a vendored tree but are ArkaOS's own work. They are
#: deliberately NOT pinned and NOT attributed — the value here is the reason,
#: which is the evidence that keeps the boundary honest. Moving a file into
#: this table is how vendored material would be laundered, so the reason must
#: name the commit or the record that establishes ArkaOS authorship.
ARKAOS_AUTHORED: dict[str, str] = {
    "arka/skills/human-writing/references/forbidden-patterns.md": (
        "ArkaOS-authored; predates every absorption campaign (added in "
        "v2.17.4, commit 18f57462)"
    ),
    "arka/skills/human-writing/references/pt-pt-anti-slop.md": (
        "ArkaOS-authored pt-PT companion that cites the vendored catalogues; "
        "added by the stop-slop campaign (fc47d279) but not derived from it — "
        "the NOTICES stop-slop section does not claim it"
    ),
}

#: Vendored files with no per-file trail in docs/THIRD-PARTY-NOTICES.md. They
#: are still integrity-locked; what is missing is the attribution row. This
#: table is an open debt that must only ever shrink — see
#: :func:`test_known_notices_gaps_do_not_grow`.
NOTICES_GAP: dict[str, str] = {
    path: (
        "marketing-skills (Corey Haines, MIT) wave 2 — imported verbatim by "
        "commit 8f9e45c0 (#378). The skill directory is recorded as derived in "
        "config/skills-provenance.yaml, but the NOTICES marketing-skills "
        "section names only departments/marketing/tools/ and the SKILL.md "
        "files, so these reference files have no per-file row."
    )
    for path in (
        "departments/landing/skills/page-architect/references/mermaid-templates.md",
        "departments/landing/skills/page-architect/references/navigation-patterns.md",
        "departments/landing/skills/page-architect/references/site-type-templates.md",
        "arka/skills/human-writing/references/checklist.md",
        "arka/skills/human-writing/references/content-refresh.md",
        "arka/skills/human-writing/references/plain-english-alternatives.md",
    )
}


class LicenseText(NamedTuple):
    """An upstream licence or notice text carried beside derived material."""

    #: A line that must survive inside the file — the attribution itself.
    marker: str
    #: The one copy docs/THIRD-PARTY-NOTICES.md names. Copies beside other
    #: derived skills are verified byte-identical to this one instead of
    #: being individually named.
    canonical: str
    #: Trees where the file's presence is a licence obligation, not a
    #: convenience, and so may never be deleted while the tree exists.
    mandatory_in: tuple[str, ...] = ()


#: Keyed by file name, because the same text is carried beside every skill
#: derived from that upstream.
LICENSE_TEXTS: dict[str, LicenseText] = {
    "greensock-gsap-skills.LICENSE": LicenseText(
        "Copyright (c) 2026 GreenSock",
        "departments/dev/skills/gsap/references/greensock-gsap-skills.LICENSE",
    ),
    "motion-design-skill.LICENSE": LicenseText(
        "Copyright (c) 2025 LottieFiles",
        "departments/brand/skills/motion-design/references/motion-design-skill.LICENSE",
    ),
    "design-dna.LICENSE": LicenseText(
        "Copyright (c) 2026 the design-dna authors",
        "departments/brand/skills/design-dna/references/design-dna.LICENSE",
    ),
    "genjutsu.LICENSE": LicenseText(
        "Copyright (c) 2026 Adrien Thevon",
        "departments/dev/skills/canvas-generative/references/genjutsu.LICENSE",
    ),
    "hallmark.LICENSE": LicenseText(
        "Copyright (c) 2026 Hallmark contributors",
        "departments/brand/skills/design-review/references/hallmark.LICENSE",
    ),
    "impeccable.LICENSE": LicenseText(
        "Copyright 2025 Paul Bakaus",
        "departments/brand/skills/design-review/references/impeccable.LICENSE",
    ),
    # Apache License 2.0 §4(d): a derivative work must carry the NOTICE text
    # of the original. This file is a licence obligation, not decoration.
    "impeccable.NOTICE": LicenseText(
        "https://github.com/ehmo/platform-design-skills",
        "departments/brand/skills/design-review/references/impeccable.NOTICE",
        mandatory_in=("departments/brand/skills/design-review/references",),
    ),
    "stop-slop.LICENSE": LicenseText(
        "Copyright (c) 2025 Hardik Pandya",
        "arka/skills/human-writing/references/stop-slop.LICENSE",
    ),
    "scroll-world.LICENSE": LicenseText(
        "Copyright (c) 2026 cyw",
        "departments/dev/skills/scroll-world/references/scroll-world.LICENSE",
    ),
    "claude-video.LICENSE": LicenseText(
        "Copyright (c) 2026 Bradley Bonanno",
        "departments/dev/skills/watch/references/claude-video.LICENSE",
    ),
}


def _notice_for(path: str) -> str:
    """The string the NOTICES must contain for ``path``."""
    return VENDORED[path].notice or path


def _notice_denotes_path(path: str, notice: str) -> bool:
    """Whether ``notice`` is a specific, component-aligned reference to ``path``."""
    if notice.rstrip("/") in _TREE_ROOT_REFERENCES:
        return False
    if notice.endswith("/"):
        return path.startswith(notice) or f"/{notice}" in path
    return path == notice or path.endswith(f"/{notice}")


def _is_license_text(path: str) -> bool:
    return path.rsplit("/", 1)[-1] in LICENSE_TEXTS


def _notices_claim(path: str, notices: str) -> bool:
    """Whether the NOTICES attribute ``path`` upstream, by path or by row.

    A bare file name is deliberately not enough. ``forbidden-patterns.md``
    is ArkaOS's own list and the NOTICES only mention it as the thing an
    imported catalogue was deduplicated against — a mention, not a claim.
    """
    if path in notices:
        return True
    tree = next(t for t in VENDORED_TREES if path.startswith(f"{t}/"))
    directories = path[len(tree) + 1:].split("/")[:-1]
    return any(
        f"{tree}/{'/'.join(directories[:depth])}/" in notices
        or f"{directories[depth - 1]}/" in notices
        for depth in range(1, len(directories) + 1)
    )


def _attributable(path: str) -> bool:
    """Whether ``path`` is cross-checked against the NOTICES per file."""
    return not _is_license_text(path) and path not in NOTICES_GAP


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
        for prefix, group, suffix in re.findall(r"([^\s`]*)\{([^{}]+)\}([^\s`]*)", raw)
        for option in group.split(",")
    ]
    return "\n".join([raw, *expansions])


def test_every_file_in_a_vendored_tree_is_classified() -> None:
    """No file enters or leaves a vendored tree without a decision recorded."""
    on_disk = _files_on_disk()
    classified = set(VENDORED) | set(ARKAOS_AUTHORED)
    assert on_disk == classified, (
        f"vendored trees drifted from the tables.\n"
        f"  unclassified files on disk: {sorted(on_disk - classified) or 'none'}\n"
        f"  tabled files missing from disk: {sorted(classified - on_disk) or 'none'}\n"
        f"Pin third-party files in VENDORED; declare ArkaOS's own work in "
        f"ARKAOS_AUTHORED with the evidence for that claim.\n"
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


def test_arkaos_authored_claims_are_not_contradicted_by_the_notices() -> None:
    """Closes the laundering route out of the pin table.

    Moving a vendored file into ARKAOS_AUTHORED would drop it from the
    sha256 lock and the attribution cross-check in one edit. It cannot be
    done for any file the NOTICES already claim as derived.
    """
    both = sorted(set(VENDORED) & set(ARKAOS_AUTHORED))
    assert not both, f"claimed as both vendored and ArkaOS-authored: {both}"

    unexplained = sorted(p for p, reason in ARKAOS_AUTHORED.items() if not reason.strip())
    assert not unexplained, f"ARKAOS_AUTHORED entries with no evidence: {unexplained}"

    notices = _expanded_notices()
    contradicted = sorted(p for p in ARKAOS_AUTHORED if _notices_claim(p, notices))
    assert not contradicted, (
        f"{contradicted} are claimed as ArkaOS-authored, but "
        "docs/THIRD-PARTY-NOTICES.md names them as derived third-party "
        "material. A file the NOTICES attribute upstream must stay in "
        "VENDORED, pinned."
    )


def test_every_pinned_path_is_named_in_third_party_notices() -> None:
    """Cross-check: a pinned file with no attribution entry is a licence hole."""
    notices = _expanded_notices()
    orphans = {
        path: _notice_for(path)
        for path in sorted(VENDORED)
        if _attributable(path) and _notice_for(path) not in notices
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
    happens to occur somewhere in the NOTICES — including a bare
    ``references/``, which is true of every vendored file and attributes none.
    """
    mismatched = {
        path: _notice_for(path)
        for path in sorted(VENDORED)
        if _attributable(path) and not _notice_denotes_path(path, _notice_for(path))
    }
    assert not mismatched, (
        "notice reference(s) are not a specific, component-aligned prefix, "
        f"suffix or parent directory of the file they claim to cover: {mismatched}"
    )


def test_known_notices_gaps_do_not_grow() -> None:
    """The attribution debt is enforced as a shrinking list, not a footnote."""
    notices = _expanded_notices()
    # The gap set is FROZEN to the six provenance-traced #378 files. Adding
    # an entry here would switch _attributable() off for that file — the
    # exact laundering vector this table must never become (QG batch B1).
    # Entries may only ever be REMOVED, when the NOTICES gain their row.
    frozen = {
        "departments/landing/skills/page-architect/references/mermaid-templates.md",
        "departments/landing/skills/page-architect/references/navigation-patterns.md",
        "departments/landing/skills/page-architect/references/site-type-templates.md",
        "arka/skills/human-writing/references/checklist.md",
        "arka/skills/human-writing/references/content-refresh.md",
        "arka/skills/human-writing/references/plain-english-alternatives.md",
    }
    assert set(NOTICES_GAP) <= frozen, (
        f"NOTICES_GAP grew: {sorted(set(NOTICES_GAP) - frozen)} — new vendored "
        "files get a NOTICES row, never a gap entry."
    )
    assert set(NOTICES_GAP) <= set(VENDORED), (
        f"NOTICES_GAP entries that are not pinned: "
        f"{sorted(set(NOTICES_GAP) - set(VENDORED))}"
    )
    closed = sorted(path for path in NOTICES_GAP if _notices_claim(path, notices))
    assert not closed, (
        f"docs/THIRD-PARTY-NOTICES.md now names {closed} — good. Remove those "
        "entries from NOTICES_GAP so the remaining debt stays honest; they are "
        "then covered by the ordinary per-file cross-check."
    )


def test_license_texts_are_declared_identical_and_attributed() -> None:
    """Every licence copy is the declared text, byte for byte."""
    notices = _expanded_notices()
    for name, license_text in sorted(LICENSE_TEXTS.items()):
        assert license_text.canonical in notices, (
            f"docs/THIRD-PARTY-NOTICES.md no longer names {license_text.canonical} "
            f"— the declared location of {name}"
        )
        canonical_digest = _digest(license_text.canonical)
        assert canonical_digest is not None, f"{license_text.canonical} is missing"
        assert license_text.marker in (REPO_ROOT / license_text.canonical).read_text(
            encoding="utf-8"
        ), f"{license_text.canonical} lost its attribution line: {license_text.marker!r}"
        copies = sorted(p for p in VENDORED if p.rsplit("/", 1)[-1] == name)
        divergent = [p for p in copies if _digest(p) != canonical_digest]
        assert not divergent, (
            f"{name} copies differ from the declared text at "
            f"{license_text.canonical}: {divergent}. The NOTICES describe these "
            "as identical copies; they must stay identical or be named "
            "separately."
        )


def test_apache_notice_is_mandatory_while_its_tree_exists() -> None:
    """Apache-2.0 §4(d): the NOTICE's attribution notices travel with the work.

    Section 4(d) is satisfiable three ways (a NOTICE file, the docs
    shipped with the work, or a generated display); ArkaOS satisfies it
    by carrying the file itself, and this test holds that choice in
    place — the file may only disappear when the whole derived tree
    does, or when the notices provably move to one of the other two
    sanctioned carriers.
    """
    for name, license_text in sorted(LICENSE_TEXTS.items()):
        for tree in license_text.mandatory_in:
            if not (REPO_ROOT / tree).is_dir():
                continue
            required = f"{tree}/{name}"
            assert (REPO_ROOT / required).is_file(), (
                f"{required} is missing while {tree}/ still ships derived "
                f"material. Apache License 2.0 §4(d) requires the NOTICE text "
                f"to be carried with the derivative work — restore it, or "
                f"remove the derived tree."
            )
            assert required in VENDORED, f"{required} must be pinned like any vendored file"

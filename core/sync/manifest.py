"""Change Manifest Builder — loads feature specs and computes version diffs."""

from pathlib import Path

import yaml

from core.sync.schema import ChangeManifest, FeatureSpec

_FIRST_SYNC_MARKERS = {"pending-sync", "none", ""}


def load_features(features_dir: Path) -> list[FeatureSpec]:
    """Load all FeatureSpec instances from YAML files in features_dir."""
    if not features_dir.exists():
        return []

    features: list[FeatureSpec] = []
    for path in sorted(features_dir.iterdir()):
        if path.suffix != ".yaml":
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        features.append(FeatureSpec(**data))

    return features


def build_manifest(
    previous_version: str,
    current_version: str,
    features_dir: Path,
) -> ChangeManifest:
    """Build a ChangeManifest comparing previous_version to current_version."""
    features = load_features(features_dir)
    is_first = previous_version in _FIRST_SYNC_MARKERS

    new_features = _find_new_features(features, previous_version, is_first)
    deprecated_features = _find_deprecated_features(features, previous_version, is_first)

    return ChangeManifest(
        previous_version=previous_version,
        current_version=current_version,
        is_first_sync=is_first,
        features=features,
        new_features=new_features,
        deprecated_features=deprecated_features,
    )


def compare_versions(version: str, baseline: str) -> bool | None:
    """True if version > baseline, False if not, None if unorderable.

    ``None`` is deliberately distinct from ``False``. A baseline of
    ``unknown`` — which ``engine._read_current_version`` emits on a degraded
    run and ``write_sync_state`` then persists — is not the same fact as "no
    feature is newer", and collapsing the two makes a broken install report
    "nothing changed" forever, with no error anywhere.
    """
    def parse(v: str) -> tuple[int, ...]:
        return tuple(int(part) for part in v.split("."))

    try:
        return parse(version) > parse(baseline)
    except ValueError:
        return None


def is_version_newer(version: str, baseline: str) -> bool:
    """True only when the pair is orderable and version is strictly newer.

    The conservative reading, for callers where doing nothing is the safe
    answer. Callers that must distinguish "unknown baseline" from "nothing
    is new" call :func:`compare_versions` instead.
    """
    return compare_versions(version, baseline) is True


# Backwards-compatible private alias (used by existing call sites and tests).
_is_version_newer = is_version_newer


def _baseline_is_unorderable(previous_version: str) -> bool:
    """True when previous_version itself cannot be ordered.

    Tested against a known-good literal, never against the feature versions:
    comparing the *pair* meant one malformed ``added_in`` in the registry
    made an otherwise fine baseline look unorderable, and deprecated
    features then stopped being removed — silently.
    """
    return compare_versions("0.0.0", previous_version) is None


def _find_new_features(
    features: list[FeatureSpec],
    previous_version: str,
    is_first: bool,
) -> list[str]:
    """Return names of features that are new relative to previous_version.

    An unorderable baseline is treated as a first sync rather than as "nothing
    is new": answering "nothing" would leave a degraded install permanently
    convinced it is up to date.
    """
    if is_first or _baseline_is_unorderable(previous_version):
        return [f.name for f in features if f.deprecated_in is None]

    return [
        f.name
        for f in features
        if compare_versions(f.added_in, previous_version) is True
    ]


def _find_deprecated_features(
    features: list[FeatureSpec],
    previous_version: str,
    is_first: bool,
) -> list[str]:
    """Return names of features deprecated after previous_version."""
    if is_first or _baseline_is_unorderable(previous_version):
        return []

    return [
        f.name
        for f in features
        if f.deprecated_in is not None
        and compare_versions(f.deprecated_in, previous_version) is True
    ]

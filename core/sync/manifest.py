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
        data = yaml.safe_load(path.read_text())
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


def _is_version_newer(version: str, baseline: str) -> bool:
    """Return True if version is strictly newer than baseline (semver int tuple)."""
    def parse(v: str) -> tuple[int, ...]:
        return tuple(int(part) for part in v.split("."))

    return parse(version) > parse(baseline)


def _find_new_features(
    features: list[FeatureSpec],
    previous_version: str,
    is_first: bool,
) -> list[str]:
    """Return names of features that are new relative to previous_version."""
    if is_first:
        return [f.name for f in features if f.deprecated_in is None]

    return [
        f.name
        for f in features
        if _is_version_newer(f.added_in, previous_version)
    ]


def _find_deprecated_features(
    features: list[FeatureSpec],
    previous_version: str,
    is_first: bool,
) -> list[str]:
    """Return names of features deprecated after previous_version."""
    if is_first:
        return []

    return [
        f.name
        for f in features
        if f.deprecated_in is not None
        and _is_version_newer(f.deprecated_in, previous_version)
    ]

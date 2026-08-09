"""Regression lock: pytest must import core.* from THIS checkout (#504/#515).

The venv's editable-install `.pth` pointed at a frozen npx cache, so the
console script `~/.arkaos/venv/bin/pytest` imported `core.*` from that
snapshot: local runs produced green evidence about the wrong code, which
is a false green on evidence-flow G3. `python -m pytest` was immune only
because it puts the cwd on `sys.path[0]`.

`pythonpath = ["."]` in `[tool.pytest.ini_options]` is the fix — pytest
front-inserts it ahead of any site-packages `.pth`. It is one line in a
config file, exactly the kind of change that gets dropped in a merge or
"tidied" by someone who cannot see what it defends, so it is pinned
here.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _pytest_ini_options() -> dict:
    data = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    return data.get("tool", {}).get("pytest", {}).get("ini_options", {})


def test_pyproject_declares_pythonpath_dot():
    """The pin itself. Removing the line fails here, loudly."""
    options = _pytest_ini_options()
    assert "pythonpath" in options, (
        "pythonpath is missing from [tool.pytest.ini_options] — the venv's "
        "editable-install .pth can again resolve core.* to a frozen npx "
        "cache, making `pytest` report green about code that is not in "
        "this checkout (issues #504, #515)"
    )
    assert "." in options["pythonpath"], (
        f"pythonpath must contain the checkout root: {options['pythonpath']}"
    )


def test_the_checkout_root_precedes_site_packages_on_sys_path():
    """The property the line BUYS, not just its presence.

    A test that only greps the config passes even if pytest stops
    honouring the option. This one asserts the resulting import order,
    which is what actually keeps a stale .pth from winning.
    """
    root = str(REPO_ROOT)
    entries = [str(Path(p).resolve()) for p in sys.path if p]
    assert root in entries, (
        f"the checkout root is not on sys.path at all: {sys.path}"
    )
    site_packages = [
        i for i, p in enumerate(entries)
        if "site-packages" in p or "dist-packages" in p
    ]
    if site_packages:
        assert entries.index(root) < min(site_packages), (
            "site-packages precedes the checkout on sys.path — an editable "
            f".pth can shadow core.*: {entries[:8]}"
        )


def test_core_is_imported_from_this_checkout():
    """The end state both of the above exist to guarantee."""
    import core

    assert Path(core.__file__).resolve().is_relative_to(REPO_ROOT), (
        f"core was imported from {core.__file__}, not from {REPO_ROOT} — "
        "the suite is reporting on the wrong code"
    )

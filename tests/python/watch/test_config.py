"""WATCH_DETAIL resolution and frame_cap mapping.

The autouse `_isolated_home` fixture redirects HOME, so config paths
resolve under a temp dir — no test touches the real ~/.arkaos.
"""
from __future__ import annotations

from pathlib import Path

import config


def test_default_detail_is_balanced(monkeypatch):
    monkeypatch.delenv("WATCH_DETAIL", raising=False)
    assert config.get_config()["detail"] == "balanced"


def test_env_overrides_detail(monkeypatch):
    monkeypatch.setenv("WATCH_DETAIL", "efficient")
    assert config.get_config()["detail"] == "efficient"


def test_invalid_detail_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("WATCH_DETAIL", "bogus")
    assert config.get_config()["detail"] == "balanced"


def test_get_config_keys(monkeypatch):
    monkeypatch.delenv("WATCH_DETAIL", raising=False)
    cfg = config.get_config()
    assert set(cfg) == {"detail", "config_file"}


def test_watch_env_file_sets_detail(_isolated_home: Path):
    cfg_file = _isolated_home / ".arkaos" / "watch.env"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text("WATCH_DETAIL=token-burner\n", encoding="utf-8")
    assert config.get_config()["detail"] == "token-burner"


def test_paths_resolve_at_call_time(monkeypatch, tmp_path):
    """A redirected ARKAOS_HOME must take effect on the NEXT call (no
    import-time binding — the Wave 3 B1 failure mode)."""
    first = config.config_file()
    monkeypatch.setenv("ARKAOS_HOME", str(tmp_path / "other"))
    second = config.config_file()
    assert first != second
    assert second == tmp_path / "other" / "watch.env"


def test_frame_cap_mapping():
    assert config.frame_cap("efficient") == 50
    assert config.frame_cap("balanced") == 100
    assert config.frame_cap("token-burner") is None
    assert config.frame_cap("transcript") is None
    assert config.frame_cap("anything-else") == 100

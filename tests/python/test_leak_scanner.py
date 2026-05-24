"""Tests for core.governance.leak_scanner (PR22 v2.44.0).

Scans source files for client identifiers from the user-local
``~/.arkaos/redaction-clients.json``. Empty/missing config is a no-op.

All test fixtures use SYNTHETIC client names (acmecorp / globexsa /
initechinc) — never real ones. See feedback_npm_publish_safety in
user memory; v2.18.0 leaked through fixture-style strings.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.governance.leak_scanner import (
    LeakHit,
    ScanReport,
    scan_paths,
    scan_text,
)


# ─── Fixtures ───────────────────────────────────────────────────────────


def _write_config(path: Path, clients: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"clients": clients}), encoding="utf-8")


@pytest.fixture()
def synthetic_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "redaction-clients.json"
    _write_config(cfg, ["acmecorp", "globexsa", "initechinc"])
    return cfg


# ─── Empty / missing config (no-op contract) ────────────────────────────


class TestNoOp:
    def test_missing_config_returns_clean_no_op(self, tmp_path: Path):
        # Source has a synthetic name but no config → no rules → no hits
        src = tmp_path / "src.py"
        src.write_text("client = 'acmecorp'\n", encoding="utf-8")
        report = scan_paths(
            [src],
            config_path=tmp_path / "absent.json",
        )
        assert isinstance(report, ScanReport)
        assert report.hits == []
        assert report.clean is True
        assert report.pattern_count == 0

    def test_empty_clients_list_is_no_op(self, tmp_path: Path):
        cfg = tmp_path / "redaction-clients.json"
        _write_config(cfg, [])
        src = tmp_path / "src.py"
        src.write_text("client = 'acmecorp'\n", encoding="utf-8")
        report = scan_paths([src], config_path=cfg)
        assert report.clean is True

    def test_malformed_config_is_no_op(self, tmp_path: Path):
        cfg = tmp_path / "redaction-clients.json"
        cfg.write_text("{ not valid json", encoding="utf-8")
        src = tmp_path / "src.py"
        src.write_text("client = 'acmecorp'\n", encoding="utf-8")
        report = scan_paths([src], config_path=cfg)
        assert report.clean is True


# ─── Detection ──────────────────────────────────────────────────────────


class TestDetection:
    def test_match_in_source_produces_leak_hit(
        self, tmp_path: Path, synthetic_config: Path,
    ):
        src = tmp_path / "src.py"
        src.write_text(
            "VENDORS = ['acmecorp', 'other']\n",
            encoding="utf-8",
        )
        report = scan_paths([src], config_path=synthetic_config)
        assert len(report.hits) == 1
        hit = report.hits[0]
        assert isinstance(hit, LeakHit)
        assert hit.line_number == 1
        assert hit.matched_token == "acmecorp"
        assert "acmecorp" in hit.line_excerpt

    def test_match_in_comment_still_flagged(
        self, tmp_path: Path, synthetic_config: Path,
    ):
        src = tmp_path / "src.py"
        src.write_text(
            "# We learned this from globexsa-billing-quirk\n",
            encoding="utf-8",
        )
        report = scan_paths([src], config_path=synthetic_config)
        assert report.clean is False

    def test_word_boundary_no_false_positive(
        self, tmp_path: Path, synthetic_config: Path,
    ):
        # "acmecorpfoo" should NOT match "acmecorp"
        src = tmp_path / "src.py"
        src.write_text("var = 'acmecorpfoo'\n", encoding="utf-8")
        report = scan_paths([src], config_path=synthetic_config)
        assert report.clean is True

    def test_hyphen_boundary_matches(
        self, tmp_path: Path, synthetic_config: Path,
    ):
        # "acmecorp-something" SHOULD match "acmecorp"
        src = tmp_path / "src.py"
        src.write_text("var = 'acmecorp-project'\n", encoding="utf-8")
        report = scan_paths([src], config_path=synthetic_config)
        assert report.clean is False

    def test_case_insensitive(
        self, tmp_path: Path, synthetic_config: Path,
    ):
        src = tmp_path / "src.py"
        src.write_text("client = 'ACMECORP'\n", encoding="utf-8")
        report = scan_paths([src], config_path=synthetic_config)
        assert report.clean is False

    def test_multiple_hits_in_same_file(
        self, tmp_path: Path, synthetic_config: Path,
    ):
        src = tmp_path / "src.py"
        src.write_text(
            "a = 'acmecorp'\n"
            "b = 'globexsa'\n"
            "c = 'safe'\n"
            "d = 'INITECHINC'\n",
            encoding="utf-8",
        )
        report = scan_paths([src], config_path=synthetic_config)
        assert len(report.hits) == 3


# ─── File handling ──────────────────────────────────────────────────────


class TestFileHandling:
    def test_recursive_directory_scan(
        self, tmp_path: Path, synthetic_config: Path,
    ):
        # Source root lives in a sibling dir so the config file (which
        # itself contains the patterns) isn't part of the scan target.
        src_root = tmp_path / "source"
        src_root.mkdir()
        (src_root / "sub").mkdir()
        (src_root / "sub" / "deep.py").write_text(
            "x = 'acmecorp'\n", encoding="utf-8",
        )
        (src_root / "top.py").write_text(
            "y = 'globexsa'\n", encoding="utf-8",
        )
        report = scan_paths([src_root], config_path=synthetic_config)
        assert len(report.hits) == 2

    def test_skips_unsupported_extensions(
        self, tmp_path: Path, synthetic_config: Path,
    ):
        # .png binary-ish — should be skipped
        (tmp_path / "img.png").write_bytes(b"\x89PNG acmecorp \x00\xff")
        report = scan_paths([tmp_path / "img.png"], config_path=synthetic_config)
        assert report.clean is True

    def test_binary_decode_errors_swallowed(
        self, tmp_path: Path, synthetic_config: Path,
    ):
        # .py file but with binary content — decode errors should not crash
        weird = tmp_path / "weird.py"
        weird.write_bytes(b"\xff\xfe\x00acmecorp\x00")
        # Should not raise — graceful fallback
        report = scan_paths([weird], config_path=synthetic_config)
        assert isinstance(report, ScanReport)

    def test_oversize_file_skipped(
        self, tmp_path: Path, synthetic_config: Path,
    ):
        big = tmp_path / "big.py"
        big.write_text("# pad " * 2_000_000 + "acmecorp\n", encoding="utf-8")
        report = scan_paths([big], config_path=synthetic_config)
        # File is >10MB → skipped → no hit even though acmecorp is in it
        assert report.clean is True


# ─── scan_text helper ───────────────────────────────────────────────────


class TestScanText:
    def test_scan_text_returns_matched_tokens(
        self, synthetic_config: Path,
    ):
        matches = scan_text(
            "we got acmecorp and INITECHINC and globexsa-foo",
            config_path=synthetic_config,
        )
        assert "acmecorp" in matches
        assert "initechinc" in matches
        assert "globexsa" in matches

    def test_scan_text_empty_config_returns_empty(self, tmp_path: Path):
        matches = scan_text(
            "acmecorp", config_path=tmp_path / "absent.json",
        )
        assert matches == []

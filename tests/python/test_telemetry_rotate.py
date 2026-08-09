"""Size-capped telemetry rotation (Gate Economy PR-10) — one kept
generation, fail-open plumbing, corpora untouched by construction."""

from __future__ import annotations

from core.shared.telemetry_rotate import (
    DEFAULT_MAX_BYTES,
    rotate_if_oversized,
)


class TestRotateIfOversized:
    def test_under_cap_is_untouched(self, tmp_path):
        target = tmp_path / "enforcement.jsonl"
        target.write_text("x" * 100, encoding="utf-8")
        assert rotate_if_oversized(target, max_bytes=1000) is False
        assert target.read_text(encoding="utf-8") == "x" * 100

    def test_over_cap_rotates_to_dot_one(self, tmp_path):
        target = tmp_path / "enforcement.jsonl"
        target.write_text("x" * 2000, encoding="utf-8")
        assert rotate_if_oversized(target, max_bytes=1000) is True
        assert not target.exists()
        rotated = tmp_path / "enforcement.jsonl.1"
        assert rotated.read_text(encoding="utf-8") == "x" * 2000

    def test_second_rotation_replaces_previous_generation(self, tmp_path):
        target = tmp_path / "t.jsonl"
        target.write_text("old" * 500, encoding="utf-8")
        rotate_if_oversized(target, max_bytes=100)
        target.write_text("new" * 500, encoding="utf-8")
        rotate_if_oversized(target, max_bytes=100)
        assert (tmp_path / "t.jsonl.1").read_text(
            encoding="utf-8"
        ) == "new" * 500

    def test_missing_file_is_noop(self, tmp_path):
        assert rotate_if_oversized(tmp_path / "nope.jsonl", 100) is False

    def test_zero_cap_disables(self, tmp_path):
        target = tmp_path / "t.jsonl"
        target.write_text("x" * 2000, encoding="utf-8")
        assert rotate_if_oversized(target, max_bytes=0) is False
        assert target.exists()

    def test_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ARKA_TELEMETRY_MAX_BYTES", "50")
        target = tmp_path / "t.jsonl"
        target.write_text("x" * 200, encoding="utf-8")
        assert rotate_if_oversized(target) is True

    def test_bad_env_falls_back_to_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ARKA_TELEMETRY_MAX_BYTES", "banana")
        target = tmp_path / "t.jsonl"
        target.write_text("x" * 200, encoding="utf-8")
        assert DEFAULT_MAX_BYTES > 200
        assert rotate_if_oversized(target) is False


class TestWiredIntoEnforcerAppends:
    def test_flow_enforcer_append_rotates_oversized_file(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("ARKA_TELEMETRY_MAX_BYTES", "100")
        from core.workflow.flow_enforcer import _locked_append

        target = tmp_path / "enforcement.jsonl"
        target.write_text("x" * 500, encoding="utf-8")
        with _locked_append(target) as fh:
            fh.write("fresh line\n")
        assert (tmp_path / "enforcement.jsonl.1").exists()
        assert target.read_text(encoding="utf-8") == "fresh line\n"

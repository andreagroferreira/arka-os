"""core.harness.json_store — tolerant loads, atomic writes, merges."""

import json
import os
import tempfile

import pytest

from core.harness.json_store import (
    MAX_JSON_BYTES,
    load_json,
    merge_unique,
    write_json_atomic,
)


class TestLoadJson:
    def test_valid_object_loads(self, tmp_path):
        path = tmp_path / "s.json"
        path.write_text('{"a": 1}', encoding="utf-8")
        result = load_json(path)
        assert result.ok
        assert result.data == {"a": 1}
        assert result.error is None

    def test_missing_file(self, tmp_path):
        result = load_json(tmp_path / "absent.json")
        assert not result.ok
        assert result.error == "missing"
        assert result.data is None

    def test_invalid_json(self, tmp_path):
        path = tmp_path / "s.json"
        path.write_text('{"a": ', encoding="utf-8")
        assert load_json(path).error == "invalid-json"

    def test_binary_garbage_is_unreadable_not_a_traceback(self, tmp_path):
        path = tmp_path / "s.json"
        path.write_bytes(b"\xff\xfe\x00garbage")
        assert load_json(path).error == "unreadable"

    def test_non_object_top_level(self, tmp_path):
        path = tmp_path / "s.json"
        path.write_text("[1, 2]", encoding="utf-8")
        assert load_json(path).error == "not-an-object"

    def test_oversized_file_is_refused(self, tmp_path):
        path = tmp_path / "s.json"
        path.write_text(
            '{"pad": "' + "x" * MAX_JSON_BYTES + '"}', encoding="utf-8"
        )
        assert load_json(path).error == "oversized"

    def test_directory_is_reported_not_raised(self, tmp_path):
        assert load_json(tmp_path).error == "missing"


class TestWriteJsonAtomic:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "out.json"
        write_json_atomic(path, {"b": [1, 2], "a": "á"})
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert json.loads(text) == {"b": [1, 2], "a": "á"}

    def test_creates_parent_directories(self, tmp_path):
        path = tmp_path / "deep" / "er" / "out.json"
        write_json_atomic(path, {})
        assert path.is_file()

    def test_preserves_existing_permission_bits(self, tmp_path):
        """0o644 discriminates: mkstemp creates 0o600 on its own, so
        this passes only when the preservation chmod actually runs."""
        path = tmp_path / "out.json"
        path.write_text("{}", encoding="utf-8")
        path.chmod(0o644)
        write_json_atomic(path, {"a": 1})
        assert path.stat().st_mode & 0o7777 == 0o644

    def test_serialization_failure_leaves_target_untouched(self, tmp_path):
        """This failure fires in json.dumps, BEFORE the tmp file exists
        — it pins the pre-serialization path only. The crash-safety of
        the replace path is pinned by the two tests below."""
        path = tmp_path / "out.json"
        path.write_text('{"kept": true}', encoding="utf-8")
        with pytest.raises(TypeError):
            write_json_atomic(path, {"bad": {1, 2}})
        assert json.loads(path.read_text(encoding="utf-8")) == {"kept": True}
        leftovers = [p.name for p in tmp_path.iterdir() if p.name != "out.json"]
        assert leftovers == []

    def test_replace_failure_keeps_previous_content_and_cleans_tmp(
        self, tmp_path, monkeypatch
    ):
        """Crash at the swap: the target keeps its previous bytes, the
        exception propagates, and no tmp file is left behind. Kills the
        non-atomic-write and no-cleanup mutants."""
        path = tmp_path / "out.json"
        path.write_text('{"kept": true}', encoding="utf-8")
        before = path.read_bytes()

        def boom(src, dst):
            raise OSError("simulated crash at replace")

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(OSError, match="simulated crash"):
            write_json_atomic(path, {"new": 1})
        assert path.read_bytes() == before
        leftovers = [p.name for p in tmp_path.iterdir() if p.name != "out.json"]
        assert leftovers == []

    def test_tmp_file_is_created_in_the_target_directory(
        self, tmp_path, monkeypatch
    ):
        """dir=path.parent is what keeps os.replace a same-filesystem
        rename: with the tmp in the system temp dir the replace fails
        outright (EXDEV) on any machine whose temp dir is a different
        filesystem, so every write raises instead of swapping
        atomically."""
        seen: dict = {}
        real_mkstemp = tempfile.mkstemp

        def spy(*args, **kwargs):
            seen.update(kwargs)
            return real_mkstemp(*args, **kwargs)

        monkeypatch.setattr(tempfile, "mkstemp", spy)
        target = tmp_path / "deep" / "out.json"
        write_json_atomic(target, {"a": 1})
        assert seen.get("dir") == target.parent

    def test_success_leaves_no_tmp_behind(self, tmp_path):
        path = tmp_path / "out.json"
        write_json_atomic(path, {"a": 1})
        assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


class TestMergeUnique:
    def test_order_preserved_first_occurrence_wins(self):
        assert merge_unique(["b", "a"], ["a", "c", "b"]) == ["b", "a", "c"]

    def test_operator_first_precedence_contract(self):
        """Caller ordering IS the precedence: operator entries placed
        first stay ahead of shipped defaults — the mergeUnique contract
        from installer/hard-deny.js."""
        operator = ["Bash(rm -rf /*)", "Read(~/.secret)"]
        defaults = ["Bash(sudo *)", "Bash(rm -rf /*)"]
        assert merge_unique(operator, defaults) == [
            "Bash(rm -rf /*)", "Read(~/.secret)", "Bash(sudo *)",
        ]

    def test_empty_inputs(self):
        assert merge_unique() == []
        assert merge_unique([], []) == []

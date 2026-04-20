"""Tests for Obsidian taxonomy module."""

from pathlib import PurePosixPath

import pytest

from core.obsidian.taxonomy import (
    TAXONOMY,
    NoteType,
    TaxonomyEntry,
    extract_template_vars,
    get_entry,
    missing_vars,
)


class TestTaxonomyCompleteness:
    def test_every_note_type_has_entry(self):
        for note_type in NoteType:
            assert note_type in TAXONOMY, f"Missing taxonomy entry for {note_type}"

    def test_all_entries_are_typed(self):
        for entry in TAXONOMY.values():
            assert isinstance(entry, TaxonomyEntry)

    def test_path_templates_are_relative(self):
        for note_type, entry in TAXONOMY.items():
            assert not entry.path_template.startswith("/"), \
                f"{note_type} has absolute path: {entry.path_template}"

    def test_path_templates_end_with_md(self):
        for note_type, entry in TAXONOMY.items():
            assert entry.path_template.endswith(".md"), \
                f"{note_type} path must end with .md"


class TestTemplateVarConsistency:
    def test_required_vars_are_in_template(self):
        for note_type, entry in TAXONOMY.items():
            template_vars = extract_template_vars(entry.path_template)
            for required in entry.required_vars:
                assert required in template_vars, (
                    f"{note_type}: required_var '{required}' "
                    f"not in path_template vars {template_vars}"
                )

    def test_extract_simple_vars(self):
        assert extract_template_vars("foo/{bar}/baz.md") == {"bar"}

    def test_extract_multiple_vars(self):
        result = extract_template_vars("{a}/{b}/{c}.md")
        assert result == {"a", "b", "c"}

    def test_extract_no_vars(self):
        assert extract_template_vars("plain.md") == set()


class TestEntryLookup:
    def test_get_entry_returns_taxonomy_entry(self):
        entry = get_entry(NoteType.CODE_PATTERN)
        assert "Patterns" in entry.path_template

    def test_code_pattern_tags(self):
        entry = get_entry(NoteType.CODE_PATTERN)
        assert "code" in entry.default_tags
        assert "pattern" in entry.default_tags

    def test_adr_has_inline_moc(self):
        entry = get_entry(NoteType.ARCHITECTURE_DECISION)
        assert entry.inline_moc is not None
        assert "ArkaOS v2 Architecture Decisions" in entry.inline_moc

    def test_session_learning_is_fallback_friendly(self):
        entry = get_entry(NoteType.SESSION_LEARNING)
        assert "date" in entry.required_vars
        assert "title" in entry.required_vars


class TestMissingVars:
    def test_none_missing_when_all_provided(self):
        entry = get_entry(NoteType.CODE_PATTERN)
        assert missing_vars(entry, {"stack": "Laravel", "title": "Service"}) == []

    def test_missing_listed(self):
        entry = get_entry(NoteType.CODE_PATTERN)
        result = missing_vars(entry, {"stack": "Laravel"})
        assert "title" in result

    def test_empty_string_treated_as_missing(self):
        entry = get_entry(NoteType.CODE_PATTERN)
        result = missing_vars(entry, {"stack": "", "title": "X"})
        assert "stack" in result

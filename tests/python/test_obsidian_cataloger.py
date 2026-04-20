"""Tests for Obsidian cataloger module."""

from pathlib import Path

import pytest

from core.obsidian.cataloger import (
    CatalogPlan,
    classify,
    confidence,
    execute,
    plan,
)
from core.obsidian.taxonomy import NoteType
from core.obsidian.writer import ObsidianWriter


CODE_SAMPLE = """# Service Pattern

```php
class OrderService {
    public function create(array $data): Order {
        return DB::transaction(fn () => Order::create($data));
    }
}
```

In Laravel we always delegate business logic to services.
"""

PERSONA_SAMPLE = """# Seth Godin

DISC profile: Ci (conscientious-influential). Enneagram 5. MBTI: INTP.
Known for permission marketing and tribes.
"""

ADR_SAMPLE = """# ADR-042: Use Pydantic v2

## Status
Accepted

## Decision drivers
- Performance
- Type safety

## Alternatives considered
- dataclasses + manual validation
- attrs

## Consequences
Positive: faster serialization. Negative: migration cost.
"""

MARKETING_SAMPLE = """# Winter Campaign Test

Hypothesis: adding urgency copy increases CTR.
Variant A: control. Variant B: countdown.
Conversion target: +15%.
"""

RESEARCH_SAMPLE = """# Context Window Scaling

Finding: larger windows improve recall on long documents.
Study by Anthropic per Kaplan et al. (2024).
Evidence: F1 jumps 12 points at 200K tokens.
"""

FRAMEWORK_SAMPLE = """# AIDA for landing pages

AIDA: Attention, Interest, Desire, Action. Structure any direct-response page with these four beats.
"""

STRATEGY_SAMPLE = """# Retail Growth Strategy

Positioning: premium. GTM: partnerships + influencer. Roadmap: launch Q3.
"""

VAGUE_SAMPLE = """# Notes

Talked about stuff. Need to follow up on things next week.
"""


class TestClassify:
    def test_code_pattern(self):
        assert classify(CODE_SAMPLE) == NoteType.CODE_PATTERN

    def test_persona(self):
        assert classify(PERSONA_SAMPLE, {"persona_name": "Seth"}) == NoteType.PERSONA

    def test_architecture_decision(self):
        assert classify(ADR_SAMPLE) == NoteType.ARCHITECTURE_DECISION

    def test_marketing_test(self):
        got = classify(MARKETING_SAMPLE, {"client": "Rockport"})
        assert got == NoteType.MARKETING_TEST

    def test_research_finding(self):
        assert classify(RESEARCH_SAMPLE) == NoteType.RESEARCH_FINDING

    def test_framework(self):
        assert classify(FRAMEWORK_SAMPLE) == NoteType.FRAMEWORK

    def test_client_strategy(self):
        got = classify(STRATEGY_SAMPLE, {"client": "Acme"})
        assert got == NoteType.CLIENT_STRATEGY

    def test_fallback_for_vague(self):
        assert classify(VAGUE_SAMPLE) == NoteType.SESSION_LEARNING


class TestConfidence:
    def test_high_confidence_for_clear_adr(self):
        assert confidence(ADR_SAMPLE) >= 0.5

    def test_low_confidence_for_vague(self):
        assert confidence(VAGUE_SAMPLE) < 0.5

    def test_confidence_bounded(self):
        c = confidence(CODE_SAMPLE)
        assert 0.0 <= c <= 1.0


class TestPlan:
    def test_code_pattern_path_resolves_stack(self):
        p = plan(CODE_SAMPLE, {"title": "Service Pattern"})
        assert p.note_type == NoteType.CODE_PATTERN
        assert "Laravel Patterns" in p.vault_path
        assert p.vault_path.endswith("Service Pattern.md")

    def test_explicit_stack_wins(self):
        p = plan(CODE_SAMPLE, {"title": "Pattern", "stack": "Vue"})
        assert "Vue Patterns" in p.vault_path

    def test_adr_path_contains_number_and_slug(self):
        p = plan(ADR_SAMPLE, {"number": "042", "slug": "pydantic-v2"})
        assert p.note_type == NoteType.ARCHITECTURE_DECISION
        assert "042-pydantic-v2.md" in p.vault_path

    def test_persona_path(self):
        p = plan(PERSONA_SAMPLE, {"persona_name": "Seth Godin", "title": "Profile"})
        assert p.note_type == NoteType.PERSONA
        assert "Personas/Seth Godin" in p.vault_path

    def test_marketing_test_path(self):
        p = plan(
            MARKETING_SAMPLE,
            {"client": "Rockport", "campaign": "Winter", "title": "Urgency Test"},
        )
        assert "Projects/Rockport/Campaigns/Winter/Tests/Urgency Test.md" == p.vault_path

    def test_session_fallback_when_vague(self):
        p = plan(VAGUE_SAMPLE)
        assert p.note_type == NoteType.SESSION_LEARNING
        assert "Sessions/" in p.vault_path

    def test_missing_required_vars_raises(self):
        with pytest.raises(ValueError, match="missing required vars"):
            plan(MARKETING_SAMPLE, {"client": "Rockport"})

    def test_tags_include_defaults_and_date(self):
        p = plan(CODE_SAMPLE, {"title": "X", "dept": "dev"})
        assert "code" in p.tags
        assert "pattern" in p.tags
        assert "dept/dev" in p.tags
        assert any("-" in t and len(t) == 10 for t in p.tags)

    def test_frontmatter_includes_note_type_and_confidence(self):
        p = plan(CODE_SAMPLE, {"title": "X"})
        assert p.frontmatter["note_type"] == "code_pattern"
        assert "classification_confidence" in p.frontmatter

    def test_mocs_for_code_pattern(self):
        p = plan(CODE_SAMPLE, {"title": "X"})
        assert "Topics MOC.md" in p.applicable_mocs

    def test_inline_moc_on_adr(self):
        p = plan(ADR_SAMPLE, {"number": "001", "slug": "foo"})
        assert p.inline_moc is not None
        assert "Architecture Decisions" in p.inline_moc

    def test_plan_is_frozen_dataclass(self):
        p = plan(CODE_SAMPLE, {"title": "X"})
        with pytest.raises(Exception):
            p.note_type = NoteType.PERSONA  # type: ignore


class TestExecute:
    def test_execute_writes_file(self, tmp_path: Path):
        writer = ObsidianWriter(vault_path=tmp_path)
        p = plan(CODE_SAMPLE, {"title": "Service", "dept": "dev"})
        saved = execute(p, CODE_SAMPLE, writer)
        assert saved.exists()
        text = saved.read_text(encoding="utf-8")
        assert "note_type: code_pattern" in text
        assert "# Service Pattern" in text

    def test_execute_respects_taxonomy_path(self, tmp_path: Path):
        writer = ObsidianWriter(vault_path=tmp_path)
        p = plan(CODE_SAMPLE, {"title": "Service", "stack": "Laravel"})
        saved = execute(p, CODE_SAMPLE, writer)
        assert "Laravel Patterns" in str(saved)

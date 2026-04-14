"""Rule-based context compactor for subagent handoff.

Builds a compact summary of recent conversation turns, files touched,
and decisions, sized to fit a token budget. No LLM calls — deterministic
and zero-latency. An LLM-backed variant may be added later behind a flag
(see spec: docs/superpowers/specs/2026-04-14-subagent-context-handoff-design.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Turn:
    """A single conversation turn for compaction."""
    role: str  # "user" | "assistant"
    content: str
    files_touched: list[str] = field(default_factory=list)


class ContextCompactor:
    """Builds compact context summaries for subagent handoff."""

    def build(self, turns: list[Turn], max_tokens: int = 600) -> str:
        if not turns:
            return ""

        files: list[str] = []
        for t in turns:
            for f in t.files_touched:
                if f not in files:
                    files.append(f)

        # Walk turns from most recent backwards, fitting into budget.
        budget = max_tokens
        if files:
            files_line = "Files touched: " + ", ".join(files[:20])
            budget -= len(files_line.split())
        else:
            files_line = ""

        recent_summaries: list[str] = []
        for turn in reversed(turns):
            snippet = turn.content.strip().replace("\n", " ")
            words = snippet.split()
            if not words:
                continue
            label = "USER" if turn.role == "user" else "ASSISTANT"
            line_words = [label + ":"] + words
            if len(line_words) > budget:
                line_words = line_words[: max(1, budget)]
                if len(line_words) <= 1:
                    break
            recent_summaries.insert(0, " ".join(line_words))
            budget -= len(line_words)
            if budget <= 0:
                break

        parts = ["## Prior Context"]
        if files_line:
            parts.append(files_line)
        parts.extend(recent_summaries)
        return "\n".join(parts)

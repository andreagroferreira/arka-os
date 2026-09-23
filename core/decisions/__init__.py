"""Typed decisions layer — System 1 under the ArkaOS agents.

A thin client for the OpenRouter Decisions endpoint (TypeSafe Jev):
typed questions in (``noul`` / ``choice`` / ``score``), typed answers
out, never generated text. Every call site keeps its heuristic as the
unavailability fallback; :func:`core.decisions.engine.decide` never
raises. See ADR ``docs/adr/2026-09-23-jev-decisions-layer.md``.
"""

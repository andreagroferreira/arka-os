"""Consolidated hook entrypoints (PR-6 v4.1.0 — hook hygiene).

One python process per hook event. Each module exposes
``main(stdin_json) -> int`` and is invoked by the thin bash wrappers in
``config/hooks/*.sh`` as ``python3 -m core.hooks.<event>``.

CRITICAL degradation contract: ambient python3 lacks PyYAML on some
machines. This package and every entrypoint import ONLY stdlib at module
level; anything that can pull yaml (core.workflow.*, core.governance.*,
core.synapse engine, ...) is imported lazily inside try/except so
stdlib-only paths (budget check, gotchas, nudges) still run.
"""

"""Harness ownership foundation (workstream C, PR-C1).

The harness — the Claude Code configuration that decides what actually
executes on the operator's machine — has had no owner: the installer
re-writes the surface only when the operator runs install or update
(``installer/update.js``), nothing detects or repairs drift between
those runs, ``harness_scanner`` grades it but nothing closes the loop,
and the executed desired state lives only inside installer JavaScript.
This package is the read-only foundation the ``ClaudeConfigManager``
(C2) builds on:

- ``paths``      — canonical locations, resolved at call time
- ``json_store`` — tolerant reads, atomic writes, ``merge_unique``
- ``manifest``   — Pydantic schema for ``~/.arkaos/ownership.json``
- ``spec``       — desired state keyed by runtime (parity-pinned to the
  installer sources by ``test_harness_spec.py``)
- ``drift``      — spec-vs-disk comparison, never raises

Nothing in this package mutates the operator's machine. The only writer
(``json_store.write_json_atomic``) is a primitive exercised by tests and
reserved for C2's assert/restore paths.
"""

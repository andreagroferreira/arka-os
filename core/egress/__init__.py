"""Egress policy — deny-by-default guard for anything leaving the machine.

Workstream D of the 2026-07 repair campaign integrates notebooklm-py,
and everything uploaded there leaves for a Google account. The operator
serves confidential clients, so this package ships FIRST and every
other D-slice depends on it:

- ``policy``    — ``evaluate`` (never raises) / ``enforce`` (raises
  :class:`~core.egress.policy.EgressDeniedError`), ordered checks
- ``redact``    — fail-closed redaction over
  ``core.evals.sanitizer.sanitize_text``
- ``allowlist`` — expiring exceptions; client identifiers are never
  allowlistable
- ``audit``     — hashed JSONL trail; no raw payloads, ever

Fail-closed is the operator's standing directive (2026-07-26): with no
``~/.arkaos/redaction-clients.json`` on disk there is nothing to prove
a payload clean, so nothing leaves. ADR:
``docs/adr/2026-07-31-egress-policy.md``.
"""

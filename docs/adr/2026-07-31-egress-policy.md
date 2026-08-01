# ADR: Deny-by-default egress policy (`core/egress/`)

- **Status:** accepted
- **Date:** 2026-07-31
- **Deciders:** operator (fail-closed directive 2026-07-26), dev squad
- **Campaign:** 2026-07 repair, workstream D (notebooklm-py), slice D1

## Context

Workstream D integrates notebooklm-py as a heavy-research primitive.
Everything uploaded to NotebookLM leaves the machine for a Google
account, and the operator serves confidential clients — the v2.18.0
npm release leaked client names once already, which is why the
operator's standing confidentiality directive exists (client names
never enter the repo) and why the redaction identifier list
(`~/.arkaos/redaction-clients.json`) exists. The `security-gate`
constitution rule puts this surface inside a mandatory security
phase.

The 2026-07-26 campaign plan records the operator's decision verbatim:
*"Egress NotebookLM: guard fail-closed deny-by-default (popular
[populate] `~/.arkaos/redaction-clients.json`)"*. D1 ships that guard as an
independent primitive — before any notebooklm client code exists, so
no call path can ever predate the policy.

## Decision

One package, `core/egress/`, no network code, reusing the existing
identifier and secret vocabularies instead of inventing parallel ones:

1. **`policy.evaluate` never raises; `enforce` raises
   `EgressDeniedError`.**
   Check order: redaction (fail-closed) → residual client identifiers
   → secrets (`core.governance.harness_scanner.secret_labels`) →
   operator home paths → audit. What leaves is ALWAYS the redacted
   text, never the original.
2. **Fail-closed on missing config.** No `redaction-clients.json` (or
   an empty one) means the payload cannot be proven clean:
   `redaction-config-missing`, denied. A silent pass-through would be
   the open-by-default this package exists to prevent.
3. **One identifier source of truth.** `redact.py` wraps
   `core.evals.sanitizer.sanitize_text` (same list, same `[CLIENT-N]`
   placeholders, same append-only invariant) and re-scans the
   redacted text against the same identifier list via
   `core.governance.leak_scanner.load_redaction_patterns`, matched as
   SUBSTRINGS rather than the sanitizer word boundary, so a compound
   token the sanitizer cannot redact is denied instead of leaking.
4. **Allowlist with mandatory expiry, never for clients.** Only
   `secret` and `home-path` findings are allowlistable, per exact
   finding token, optionally per destination. For `home-path` the
   token is the exact path; for `secret` it is the pattern LABEL from
   `secret_labels` (e.g. "Slack token"), so one entry covers every
   secret of that shape to that destination until expiry — a class,
   not a value. Size entries and expiries accordingly.
   `client-identifier` and `redaction-config-missing` are
   unallowlistable by construction. An
   entry without a valid timezone-aware expiry permits nothing — an
   exception that cannot expire is a permanent hole. A malformed
   allowlist narrows permissions, never widens them.
5. **Hashed audit, itself fail-closed.** Every decision (allow AND
   deny) appends to `~/.arkaos/egress/audit.jsonl` (dir 0700, file
   0600): timestamps, digests, finding kinds with 16-hex tokens keyed
   by a per-install random salt (HMAC-SHA256; the salt lives at
   `~/.arkaos/egress/.audit-salt`, 0600, created on first use). The
   token vocabulary is low-entropy and enumerable — the client list,
   the fixed secret-label set, paths under a known home — so an
   unsalted digest would confirm a guess for anyone holding the
   candidate list (QG D1 r2 F-M1). A salt that cannot be read or
   created degrades to an empty key, which loses only the
   guess-confirmation resistance. Never the payload, a client name, a
   secret value or a raw path — the audit file must be safe to read
   aloud. An ALLOW whose audit write fails flips to denied
   (`audit-unavailable`): no unaudited egress.

## Consequences

- D2's `nlm_client.py` chokepoint calls `egress.policy.evaluate` on
  every payload; D3/D4 inherit the guard for free.
- Until the operator populates `redaction-clients.json` (runbook step
  8), every egress is denied — that is the intended posture, not a
  bug. The denial reason is `redaction-config-missing`; the exception
  message carries finding KINDS only, deliberately — finding tokens
  (paths, labels) in an exception string would leak into whatever
  logs the caller keeps.
- Findings carry raw tokens IN MEMORY (the caller may need them);
  only hashes are persisted.
- The home-path check covers all local project trees (`~/Herd`,
  `~/Work`, `~/AIProjects`) by prefix; paths outside home (e.g.
  `/tmp`) are not findings.

## Alternatives considered

- **Redact-and-allow with no deny path** — rejected: secrets and paths
  are not redactable by the client list, and "always allow something"
  removes the operator's ability to hold data back.
- **Allowlistable client identifiers** — rejected: confidentiality is
  non-negotiable; the override for a client name is removing it from
  the config, an explicit operator act on the canonical list.
- **Best-effort audit (allow even when the trail fails)** — rejected:
  an unaudited egress is indistinguishable from an exfiltration after
  the fact.

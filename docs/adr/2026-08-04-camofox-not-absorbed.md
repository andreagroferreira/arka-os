# ADR: camofox-browser is not absorbed

- **Status:** accepted
- **Date:** 2026-08-04
- **Deciders:** operator (2026-08-04), dev squad
- **Campaign:** 2026-08 animation/design absorption, PR-1

## Context

`jo-inc/camofox-browser` (MIT, 8302★) was proposed for absorption as a
browsing capability for agents. It wraps Camoufox — a Firefox fork that
spoofs fingerprints at the C++ level — behind a REST API, and advertises
bypassing "Google, Cloudflare, and most bot detection", residential proxy
routing, cookie injection, and accessibility-tree snapshots that are ~90%
smaller than raw HTML.

The token-efficiency argument is real. Everything else about the fit is not.

ArkaOS already runs two browser layers, and they are the most exercised
integration in the system. All-time MCP telemetry
(`~/.arkaos/telemetry/mcp-usage.jsonl`, 3474 calls across 19 servers) gives
playwright 1421 calls and claude-in-chrome 1327 — together 2748, or 79% of
every MCP call ever made. `firecrawl` adds 108 for scraping proper.
`ecom/browse-competitor` already performs competitive collection through
that stack. No open work item is blocked on a page these layers cannot
reach.

## Decision

camofox-browser is not absorbed — neither as a skill nor as an MCP entry in
`mcps/registry.json`. Four reasons, in descending weight:

1. **The capability is duplicated, and the incumbent works.** Adding a third
   browser layer splits agent attention across three tools with overlapping
   triggers, which is the routing ambiguity the TRIGGER/SKIP contract exists
   to prevent. The 79% figure is not a gap.

2. **Its outbound telemetry is incompatible with this environment.** Per
   the upstream README (read 2026-08-04; the source is not vendored here,
   so this rests on the project's own description and was not verified
   against `lib/reporter.js`), camofox-browser automatically files
   anonymised crash and hang reports **as GitHub Issues**; opting out
   requires `CAMOFOX_CRASH_REPORT_ENABLED=false`. Private domains are
   HMAC-hashed and paths stripped, but the operator serves confidential
   clients under a standing directive that client names never
   leave the machine — the v2.18.0 npm release leaked client data once
   already, which is why `~/.arkaos/redaction-clients.json` and the
   deny-by-default `core/egress/` policy exist. A default-on channel that
   publishes to a public issue tracker is the exact shape those controls
   were built to stop, and an opt-out flag is the wrong side of
   fail-closed.

3. **Its core function violates the terms of service of most sites it would
   be pointed at.** Defeating bot detection is not incidental to
   camofox-browser; it is the product. Competitive research on public pages
   is legitimate,
   and ArkaOS does it today with ordinary browsers that identify themselves
   honestly. Building fingerprint evasion into the platform's default
   capability set changes what the system is, for a class of access nobody
   has yet needed.

4. **The operational cost is not small.** A separate Node server on
   `localhost:9377`, Docker for the supported path, a 15MB payload, and an
   optional `yt-dlp` dependency — against a YouTube transcript feature that
   `dev/watch` already covers natively.

## Consequences

- No new registry entry, no policy classification, no skill. `mcps/registry.json`
  and `config/mcp-policy.yaml` are untouched by this decision.
- Browser work continues on playwright, claude-in-chrome, and firecrawl.
- **Reopening condition:** a specific, authorised collection target that the
  existing layers demonstrably cannot reach, named with the failure on record.
  Everything that follows describes what a reopening would have to do; none of
  it exists today. The entry would take `category: optional` in
  `mcps/registry.json`, never `base` — `optional` because no stack in
  `_STACK_TO_CATEGORIES` (`core/sync/mcp_syncer.py`) maps to it, so the server
  could not reach a project's `.mcp.json` without an explicit user action. It
  would also need listing under `deferred` for every stack in
  `config/mcp-policy.yaml`, whose bucket vocabulary is unrelated to the
  registry's categories. It would pin `CAMOFOX_CRASH_REPORT_ENABLED=false` in
  the server config. And it would need an egress path that actually covers
  browsing: today `core/egress/` is consulted only by `core/kb/nlm_client.py`,
  so no browser layer passes through it and that gap would have to close
  first.
- This ADR exists so the question is not re-litigated from the star count.

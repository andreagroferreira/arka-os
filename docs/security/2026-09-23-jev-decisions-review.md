# Security review: JEV Decisions Layer, PR1

- **Date:** 2026-09-23
- **Branch:** `feature/jev-decisions-1`
- **Reviewer:** Bruno (security-eng, dev squad), requested by Paulo
- **Scope:** `core/decisions/{privacy,shadow,cache,backoff,transport,client}.py`, reading `engine.py`, `site.py`, `telemetry.py`, `core/egress/*` and `core/evals/sanitizer.py` for context. Follow-up from QA: `core/governance/leak_scanner.py` (`.jsonl` coverage).
- **References:** ADR `docs/adr/2026-07-31-egress-policy.md`, ADR `docs/adr/2026-09-23-jev-decisions-layer.md`, campaign plan ("Architecture" and "Counter-arguments" sections)
- **Frameworks:** STRIDE (per finding), OWASP Top 10:2025, CWE
- **Verdict:** APPROVED-WITH-FIXES. Both major findings of the first pass are fixed and covered by tests. The first pass left four actions for the owners of `engine.py`, `site.py` and the ADR (see "Actions outside my scope"); all four are now closed. Quality Gate round 1 rejected the PR on three majors and two minors in this lane; they are fixed below (findings 14-18).

Every piece of evidence below comes from execution: probes in a temporary directory with a fake HOME and fictional client names, local HTTP servers, and mutation runs. The operator's redaction config was never read out or printed.

## Findings

| # | Finding | Sev. | STRIDE / OWASP / CWE | Evidence (command → result) | Fix or recommendation | Owner |
|---|---|---|---|---|---|---|
| 1 | **The OpenRouter Bearer key followed a redirect to another host.** urllib turns a 301/302/303 answer to a POST into a GET and copies every non-content header to the host named in `Location`, `Authorization` included, even on a downgrade to `http://`. That host's response was then parsed as the decision. | **major** (low likelihood, since it needs a redirect from OpenRouter's side; high impact, since it is a paid key) | I + T / A02:2025 Security Misconfiguration / CWE-522 | Probe with 2 local servers (origin 302 → another port): `REDIRECT followed; B saw auth: True /steal`. Source: `HTTPRedirectHandler.redirect_request` copies `req.headers`. | **Fixed** in `client.py`: `Authorization` travels as an *unredirected header* (urllib never copies those), and a response whose final URL differs from the request is refused with `reason=redirected`. urllib already drops the body (the state) on the GET. 307/308 still surface as `http-307/308`. I kept the `urllib.request.urlopen` patch seam that the engine, replay and shadow tests rely on, so I did not use `build_opener(_NoRedirect)` as `layers_kb.py:216` does. The effect is the same. | Bruno (done) |
| 2 | **The 96k cap ran BEFORE redaction and the secret check.** An identifier or secret cut in half no longer matched its pattern, and the surviving part left in clear text. | **major** (rare today, since prompts are short; routine once later PRs send diffs and transcripts) | I / A06:2025 Insecure Design / CWE-200 | Probe with a fictional two-word client name straddling the cut: `CLIENT-SPLIT tail: '… Zorblax…[truncated]'` (the first word of the name left in clear). | **Fixed** in `privacy.py`: normalise home → run the checks on the whole text (bounded at `MAX_SCAN_CHARS=1M`, 17 ms measured for 1 MB) → cap last. If the 1M bound cuts the text, the last 4096 chars are dropped as well (`_TAIL_GUARD`), so no token split at that boundary reaches the send. | Bruno (done) |
| 3 | **A missing redaction config turned the JEV off for every npm user** (item 2 of the request; decision below). | major (product availability) | D / A10:2025 Mishandling of Exceptional Conditions | `evaluate` with `{"clients": []}` → `False ['redaction-config-missing']`; with no file → the same; with a fictional list → `True [] … [CLIENT-2] … [CLIENT-1]`. So (a) **no**: the sanitizer raises on the empty list, and (b) seeding `{"clients": []}` in the installer **does not help**. | **Implemented (c)** in `privacy.py`. See "Item 2 decision". | Bruno (done); ADR and engine: Paulo/Gabriel |
| 4 | With `redactClients: false` the state left **without an egress audit line**, which breaks the egress ADR invariant ("no audit, no egress"). | minor | R / A09:2025 Logging & Alerting Failures | Reading plus a test: with `redact=False`, `evaluate` never runs, and before this fix no audit line was written. | **Fixed**: `_unredacted` refuses secrets and writes an audit line with `override=redact-disabled`. If the audit write fails, the result is `egress-denied:audit-unavailable`. | Bruno (done) |
| 5 | **8 orphaned spools turned shadow mode off for good.** The sweep only ran in the worker's `finally`, and a killed worker (SIGKILL, reboot) left its spool behind. With 8 orphans, `spawn_shadow` returned False on every turn, with no live worker left to sweep. | minor | D / A10:2025 | New test: 8 spools with an mtime older than 1 h → without the fix, `spawn_shadow` returns `False`. | **Fixed**: `spawn_shadow` calls `sweep_stale()` before counting. | Bruno (done) |
| 6 | **A planted or corrupt `backoff.json` with a distant `until` blocked the JEV indefinitely**, and stopped a real trip from overwriting it (`current > until`). | minor | D / A08:2025 Software or Data Integrity Failures | New test with `until=1e12`. | **Fixed**: `MAX_BLOCK_S=3600`. `blocked()` ignores deadlines more than 1 h out, and `trip()` caps its seconds at 1 h and overwrites an invalid deadline. | Bruno (done) |
| 7 | Backoff shows up in telemetry, but **without its cause**: after a 401, `/arka decisions` shows `http-401 — 1` and then `backoff — N` for an hour, without saying why. Rotating the key does not reopen the breaker either (up to 1 h blocked with a good key). | minor | R / A09:2025 | Probe in a temporary HOME: turn 1 `http-401`, turn 2 `backoff`, `net called turn2: False`. CLI `telemetry_cli today` → `http-401 — 1`, `backoff — 1`, exit 0. | **Recommendation** (engine): `reason=f"backoff:{blocked()}"`. In `trip`, store a key fingerprint (sha256[:8]) and make `blocked()` ignore the state when the current key differs. | Gabriel (engine) / Bruno (backoff, in a later PR) |
| 8 | **`~/.arkaos/egress/audit.jsonl` has no rotation.** Every `evaluate` fsyncs one line, cache hits included, because `prepare_state` runs before the cache. The degraded path (item 2) writes 2 lines. | minor | D / A09:2025 | `grep -n "rotate\|max_bytes" core/egress/audit.py` → exit 1 (no rotation). Measured line: 299 bytes. | **Recommendation**: `rotate_if_oversized` (`core/shared/telemetry_rotate.py`, 10 MB), keeping N generations, since the audit is evidence. Expected growth: ~300 turns/day ≈ 90 KB/day ≈ 33 MB/year in PR1. With the command sites of later PRs (~2000 calls/day) it reaches ≈ 220 MB/year. | owner of `core/egress` (Carlos/Paulo) |
| 9 | `decisions.jsonl` is created with 0644 (readable by other users on the machine). It stores `state_sha16`, an unsalted sha256 of the state: for short prompts ("yes", "continue") it works as a confirm-a-guess oracle. The cache file names (unsalted sha256 of the redacted state) have the same issue, but their directories are 0700. | minor | I / A04:2025 Cryptographic Failures / CWE-759 | `stat -f %Lp …/t.jsonl` → `644`. | **Recommendation** (telemetry.py): create the file with 0600, as `core/egress/audit.py` does. Use an HMAC keyed with the per-install audit salt (`load_or_create_salt`) for `state_sha16`. | Gabriel (telemetry) |
| 10 | The shadow spool stores the state **before** `prepare_state` (unredacted, secrets included if present) for a few seconds. | info (accepted by design) | I | Existing test: files 0600, spool 0700; `main` refuses paths outside the spool (exit 2), including a symlink pointing outside (new test); sweep > 1 h; cap 8; `Popen(start_new_session=True)`, stdio DEVNULL; `PYTHONPATH` derived from `__file__` (`paths.repo_root`); argv = `[sys.executable, -m, core.decisions.shadow, <uuid>.json]` (a new test proves `session_id` and state never reach argv). | Accepted. Redacting before spooling (evaluate + fsync inside the hook) costs more than it protects: this is the user's own data, in 0600 files that live for one turn. | — |
| 11 | The request said `DecisionUnavailable.detail` is cut at 300 chars, but **the code has no such cut**. Nothing is exposed: no path reads the error body. `detail` is `HTTPError.reason` (the status phrase), `str(URLError.reason)` or the exception name. | info | I | Probe: local server answering 401 with a body that echoes `Authorization` → `detail: 'Unauthorized'`, key absent from `str(e)`, `detail` and the formatted traceback. `repr(Transport)` has no key. A new test pins this. | No change. If the error body is ever read, cut it and run it through `secret_labels` before storing it. | — |
| 12 | Checks that passed: every send path goes through `prepare_state` (`grep post_decision(\|urlopen` → a single `urlopen` in `client.py`, called only by `engine._fetch`, after `prepare_state`; `replay.py` and the shadow worker enter through `run_sync` → `_fetch`); `data_collection=deny` in every payload (fixed `body_extras` in `resolve_transport`, checked on the sent body); `timeout` always passed (`call_args.kwargs == {"timeout": 1.5}`); `redact=False` still refuses secrets; home paths normalised (absolute, case-insensitive, and `~/`); the cache stores only responses (new end-to-end test through `run_sync`: no cache file holds the state marker, all are 0600), cache keys validated as sha256 hex by regex (traversal rejected), corruption = miss. | — | — | See "Verification". | — | — |
| 13 | **The release leak scanner never read `.jsonl` files**, so the preflight never scanned the replay corpora (`config/decisions/corpora/*.jsonl`), where prompts are the most likely place for a client name to land. | minor (blind spot in a release gate; the 4 corpora are clean today) | I / A09:2025 / CWE-200 | `_SCAN_EXTENSIONS` lacked `.jsonl`. After the fix, the real corpora scanned against the real config: `files 4 hits 0` (counts only). | **Fixed** in `core/governance/leak_scanner.py` (QA follow-up from Rita): `.jsonl` added, plus 2 tests in `tests/python/test_leak_scanner.py` (single file and directory walk). Note: files over 10 MB are still skipped silently (`_MAX_FILE_BYTES`); if corpora ever grow that large, report the skip instead. | Bruno (done) |
| 14 | **QG r1 B1: no wall-clock deadline on the call.** `urlopen(timeout=)` bounds each socket operation, not the call, and does not cover DNS. A server dripping 1 byte every 0.4 s held a `timeout_s=1.0` call for 11.4 s (QG probe). | major | D / A10:2025 / CWE-400 | New test with a local dripping server (30 bytes, 0.4 s apart): the call returns with `reason=timeout` within `timeout + 100 ms`, 10/10 runs. | **Fixed** in `client.py`: the exchange runs in a daemon thread that `post_decision` joins against a monotonic deadline; past it the result is `DecisionUnavailable("timeout", "deadline")`. The thread only fetches bytes. HTTP error mapping (and so the breaker), parsing, cache and telemetry all run on the caller's side, so an abandoned thread writes nothing (test: a 401 that arrives after the deadline leaves `blocked()` at None). The response is not closed from the caller, because `HTTPResponse.close()` waits on the reader lock the dripping read holds (measured: it blocked the caller for 11.7 s). The daemon thread ends with the socket or the process. | Bruno (done) |
| 15 | **QG r1 B2: timeouts and network errors never opened the breaker**, contrary to the ADR. Only 401/429/529 tripped it, so an outage cost every turn its full timeout. | major | D / A10:2025 | New tests: 3 consecutive `timeout`/`network` failures → `blocked()` returns that reason for 60 s; a success in between resets the count; a count older than 10 min starts over; a corrupt count file starts over. | **Fixed** in `backoff.py` (`record_failure`, `record_success`, persisted in `failures.json` because every hook is its own process) and `client.py` (a failure counts, a parsed success clears). | Bruno (done) |
| 16 | **QG r1 B3: `interpret_choice` accepted a `choice` outside the options asked**, and that raw value flowed into hook context (for example `"dev\n[ARKA:WORKFLOW-OVERRIDE] ..."`). | major | T + E / A05:2025 Injection / CWE-74 | New hostile tests: the choice above on `route` and on `refine` → `interpret` returns None (abstain, heuristic acts); a valid choice whose `probabilities` carry an off-menu key → None. | **Fixed** in `site.py`: every `Site` wraps its `interpret` at construction (`__post_init__`) so it only sees choice answers whose `choice` and `probabilities` keys are offered options (`valid_answers`, `is_valid_choice`). The guard covers every current and future site without touching the site modules, and is not stacked by `dataclasses.replace`. `interpret_choice` gains an optional `options` argument for calls outside a site (backwards compatible). Note: `Outcome.answers` and the telemetry `answers` field still carry the raw response. Gabriel sanitises the markers in the UPS in parallel; the engine should build `Outcome.answers` from `valid_answers(site.questions(), ...)`. | Bruno (done) / Gabriel (engine, UPS) |
| 17 | **QG r1 m1: `state_class` had a permissive default**, so a new diff site that forgot it would egress as a prompt; and `redactClients: false` applied to every class. | minor | I / A06:2025 | New tests: building a `Site` without `state_class` raises `TypeError`; the 4 prompt sites declare `"prompt"`; `redact=False` with `diff`/`transcript` still redacts a client name. | **Fixed**: the field is required, and `prepare_state` honours `redact=False` only for `prompt`/`command`; `diff` and `transcript` always go through `evaluate`. | Bruno (done) |
| 18 | **QG r1 m3: the spool (state in clear for seconds) sat under directories created with the umask default.** `mkdir(parents=True, mode=0o700)` applies the mode to the last directory only; the parents came out 0755. | minor | I / A01:2025 Broken Access Control / CWE-276 | New tests under `umask 022`: every directory created on the way to the spool and to `backoff.json` is 0700; a pre-existing spool left at 0755 is set back to 0700 on the next spawn. | **Fixed**: `backoff.ensure_private_dir` creates each missing directory with 0700 (plus `chmod`, since `mkdir`'s mode is masked by the umask), used by `backoff._atomic_write` and `shadow.spawn_shadow`; the spool is always set to 0700; `backoff.json` gets an explicit `fchmod(0600)`. The `fchmod` has no killing mutation because `mkstemp` already creates 0600; it is kept as an explicit guarantee. **Closed** for `cache.py` too: `cache._atomic_write` now uses `ensure_private_dir`, so every directory created up to the entry directory is 0700 (test under `umask 022`: `test_created_directory_chain_is_private` in `test_decisions_cache.py`). | Bruno (done) |

## Item 2 decision (missing redaction config)

**Fact (from execution):** `core.evals.sanitizer.sanitize_text` raises `SanitizerConfigMissing` whenever `load_redaction_patterns` returns `()`. That happens with no file, with `{"clients": []}` **and also** with a corrupt, unreadable or wrongly shaped file. Seeding an empty list in the installer does not help.

**Policy implemented (`privacy.py`):**

1. If `evaluate` denies with **exactly** `[redaction-config-missing]`, **and** the config is *truly* absent (no file, or a file that is exactly `{"clients": []}`), **and** the state class is `prompt` or `command`: the state leaves, with secrets refused (`secret_labels`) and the home normalised.
2. The override is written to the egress audit (`allowed: true`, `override: "redaction-config-missing:<class>"`). **If the audit write fails, nothing is sent.**
3. It is recorded **once per session** in telemetry (`site="egress-notice"`, `reason="redaction-config-missing"`, `fallback_used=false`), guarded by an `O_EXCL` marker under `<cache>/notices/`.
4. **Still fail-closed:** the `diff` and `transcript` classes and any unknown class; a corrupt, unreadable or wrongly shaped file (the operator has a list we cannot read, and degrading would send their client names in clear); a dangling symlink; and `redaction-failed`.

**Threat model (STRIDE, Information Disclosure):** the redaction list protects the confidentiality of *third parties*, the operator's clients. An npm user without a list has no identifier to protect, so fail-closed protects nothing there and turns the feature off. The state of a prompt or command is the user's own text, sent with their own key to the provider they configured, with `data_collection=deny`. The high-impact classes that apply to every user (secrets, home paths) are still enforced. Diffs and transcripts carry third-party material (client code, tool output), so they stay fail-closed.

**Follow-up recommendation:** the installer should not seed `{"clients": []}`. It would only change the denial reason, and under this policy an explicit `[]` is already treated as absent. Onboarding (`/arka setup`) should ask for the list when the user turns on the diff or transcript sites.

## Actions outside my scope (all four closed)

| Action | Why | Owner |
|---|---|---|
| `engine._fetch`: `prepare_state(state, redact=redact, state_class=strictest_state_class(c.site.state_class for c in calls), session_id=session_id)` | Without `session_id`, "once per session" becomes "once per install". Without `state_class`, everything counts as `prompt`. **This blocks any PR that registers a diff or transcript site**; PR1 is safe because it only has prompt sites. | Gabriel |
| `tests/python/test_decisions_engine.py::test_egress_denial_is_a_fallback` now fails: it encodes the old behaviour (missing config → denial on a prompt site). Fix validated by execution on a temporary copy: replace `.unlink()` with `.write_text("{nope", encoding="utf-8")` (a corrupt config stays fail-closed) → `1 passed`. | This is the intended consequence of the item 2 decision. | Gabriel |
| Update ADR `2026-09-23-jev-decisions-layer.md` (the "Consequences" bullet on the new egress path, originally "fail-closed on a missing redaction list") with the per-class policy. | The ADR contradicted the code. Done: now lines 244-264 of the ADR. | Paulo |
| Field `Site.state_class` in `site.py`. First pass: defaulted to `"prompt"`. After QG round 1 (m1): **required, no default** (`field(kw_only=True)`), and the 4 prompt sites in `sites/prompt.py` declare `state_class="prompt"`. I touched only those four `state_class=` lines in that file. | Heads-up for Gabriel, who edits the refine instructions in `sites/prompt.py` in parallel. | Gabriel |

## Mutation proof (each new test has a mutation that kills it)

Scratchpad script: apply the mutation, run the test file, restore the original file. The restore was verified: the suite passes again.

| Mutation | Tests that kill it |
|---|---|
| M1 remove `and _config_absent()` | `test_unreadable_config_is_not_degradable[×4]`, `test_dangling_config_symlink_is_not_absent`, `test_config_dir_unreadable_is_not_absent` |
| M2 cap before the checks | `test_cap_never_splits_a_client_name`, `test_cap_never_ships_a_secret_prefix`, `test_scan_cut_drops_the_straddling_tail` |
| M3 `diff` in `DEGRADABLE` | `test_missing_config_diff_transcript_unknown_fail_closed[diff]` |
| M4 degraded path without the secret refusal | `test_missing_config_still_refuses_secrets` |
| M5 ignore the audit result | `test_missing_config_prompt_and_command_still_leave[×2]`, `test_missing_config_without_audit_does_not_leave`, `test_audit_path_failure_does_not_leave` |
| M6 marker without `O_EXCL` | `test_missing_config_noted_once_per_session` |
| M7 no `_TAIL_GUARD` | `test_scan_cut_drops_the_straddling_tail` |
| M8 `Authorization` as a normal header | `test_redirect_never_carries_the_key_nor_its_answer`, `test_key_is_an_unredirected_header` |
| M9 no final-URL check | `test_redirect_never_carries_the_key_nor_its_answer` |
| M10 no sweep on spawn | `test_stale_orphans_do_not_block_shadow_forever` |
| M11 no cap in `blocked()` | `test_planted_far_future_deadline_neither_blocks_nor_sticks` |
| M12 no cap in `trip()` | `test_trip_is_capped_at_an_hour` |
| (M13 `_unredacted` without the audit) | `test_redaction_disabled_is_still_audited` (by construction: it is the only audit write when `redact=False`) |
| M14 remove `.jsonl` from `_SCAN_EXTENSIONS` | `TestJsonlCorpora::test_jsonl_file_is_scanned`, `TestJsonlCorpora::test_jsonl_found_when_walking_a_directory` (run: `2 failed`) |
| R1 (B1) call `_send` directly, without the deadline | `test_dripping_server_is_cut_at_the_deadline`, `test_abandoned_call_never_trips_the_breaker_late`, and every HTTP-mapping test in the file |
| R2 (B1) map HTTP errors (trip the breaker) inside the worker thread | `test_abandoned_call_never_trips_the_breaker_late` |
| R3 (B2) drop `record_failure` in `post_decision` | `test_three_timeouts_open_the_breaker_and_success_resets` |
| R4 (B2) drop `record_success` in `post_decision` | `test_three_timeouts_open_the_breaker_and_success_resets` |
| R5 (B2) no `trip` at the failure threshold | `test_three_transport_failures_trip_and_success_resets` |
| R6 (B3) no `interpret` guard in `Site.__post_init__` | `test_hostile_route_choice_abstains`, `test_off_menu_probability_keys_abstain`, `test_hostile_refine_gap_abstains`, `test_guard_is_not_stacked_by_replace` |
| R7 (B3) ignore `probabilities` keys | `test_off_menu_probability_keys_abstain` |
| R8 (m1) default `state_class="prompt"` | `test_state_class_is_required` |
| R9 (m1) honour `redact=False` for every class | `test_redaction_disabled_never_applies_to_diff_or_transcript[diff, transcript]` |
| R10 (m3) `mkdir(parents=True)` for `backoff.json` | `test_created_directory_chain_is_private` |
| R11 (m3) `mkdir(parents=True)` for the spool | `test_spool_chain_is_private` |
| R12 (m3) no `chmod` of a pre-existing loose spool | `test_spool_chain_is_private` |
| R13 (m3) `mkdir(parents=True)` in `cache._atomic_write` | `test_created_directory_chain_is_private` (`test_decisions_cache.py`) |

Regression tests without a dedicated mutation: `test_full_path_never_writes_the_state_to_disk` (cache; the property already held, and the test pins it end to end), `test_error_body_is_never_read_into_the_exception`, `test_worker_refuses_symlink_escaping_spool`, `test_popen_argv_has_no_caller_input`, `test_state_file_is_private`, `test_fictional_clients_redacted_in_structured_state`, `test_empty_client_list_is_treated_as_missing`, `test_client_list_present_writes_no_notice`, `test_strictest_state_class`.

## Verification (first pass; superseded by "Status at merge")

- `~/.arkaos/bin/arka-py -m pytest tests/python/test_decisions_*.py -q --cov=core.decisions --cov-fail-under=80` → **exit 1**: 211 passed, 1 failed. The only failure is `test_decisions_engine.py::test_egress_denial_is_a_fallback`, which is expected and has an owner (see above). Total coverage 98.47% (privacy 100%, client 100%, transport 100%, site 100%, shadow 97%, cache 93%, backoff 91%).
- The 6 test files in my scope (`privacy, client, shadow, backoff, cache, transport`) → **exit 0**, all passing.
- `tests/python/test_ups_decisions.py` → 27 passed.
- `~/.arkaos/bin/arka-py -m pytest tests/python/test_leak_scanner*.py -q` → **exit 0**, 17 passed.
- `~/.arkaos/bin/arka-py -m ruff check core/decisions <the 5 changed test files>` → **exit 0** ("All checks passed!"). In this shell `ruff` only exists inside the venv. `ruff` on `leak_scanner.py` and `test_leak_scanner.py` reports 2 fixable findings (UP035, I001) that already exist at `HEAD` (checked with `git show HEAD:<file>`); they are not from this change.
- `mypy` on the touched modules → 0 errors in `core/decisions/` (the 257 errors reported come from other packages).
- Redirect test run 30 times in a row → 30/30 passed. An earlier version failed intermittently on a socket RST, because the server closed the connection with the body unread; fixed in the test itself.

## Status at merge (2026-09-23)

Numbers after the Quality Gate round 1 fixes, all from runs on this branch:

- `~/.arkaos/bin/arka-py -m pytest tests/python/test_decisions_*.py -q --cov=core.decisions --cov-fail-under=80` → **exit 0**, 243 passed. Total coverage 98.63% (client 100%, privacy 100%, site 100%, shadow 97%, backoff 95%, cache 93%). The engine test that failed at the first pass (`test_egress_denial_is_a_fallback`) was updated by its owner and passes.
- `~/.arkaos/bin/arka-py -m ruff check core/decisions tests/python/test_decisions_*.py` → **exit 0**.
- `mypy core/decisions` → 0 errors in `core/decisions/`.
- `tests/python/test_ups_decisions.py` → 35 passed.
- `tests/python/test_decisions_client.py` 10 runs in a row → 10/10 passed (the dripping-server test included).
- Mutations: M1-M14 (first pass and QA follow-up) and R1-R13 (QG round 1) each killed by at least one test.
- Open recommendations (not blocking, owners in the findings table): 7 (key fingerprint only; the cause already rides as `backoff:<cause>`, `engine.py:198-200`), 8 (egress audit rotation), 16 (off-menu text on non-choice or unasked answers still reaches `decisions.jsonl`; QG round 2 m4, carried to PR2). Finding 9 is fixed (`telemetry.py:97-99` creates the file with the 0600 mode set at `telemetry.py:46`; `telemetry.py:81-93` computes `state_sha16` as an HMAC-SHA256 keyed by the per-install salt). Finding 18 is closed.


## PR2 (2026-09-23)

- **Branch:** `feature/jev-decisions-2` (PR1 merged in `6e4ad3eb`)
- **Reviewer:** Bruno (security-eng), lane C, dispatched by Paulo
- **Scope:** `core/egress/{audit,policy,credentials}.py` (changed or new) and, after Quality Gate round 1, `core/decisions/privacy.py` (raw-leaf scan, finding 23); read-only review of `core/decisions/backoff.py`, `core/decisions/transport.py`, `core/decisions/client.py` and the new `core/decisions/sites/command.py` (work in progress in the `core/decisions` lane, not committed yet)
- **Frameworks:** STRIDE, OWASP Top 10:2025, CWE, NIST CSF 2.0 PR.DS (data security) and DE.AE (audit evidence)
- **Verdict for this lane:** APPROVED-WITH-FIXES. The two majors of the first pass (19, 20) and the carried finding 7 are fixed: R-P1, R-C1 and R-B1 landed in the `core/decisions` lane and their strict-xfail markers were removed with them. Quality Gate round 1 rejected PR2 on two blockers in this lane (findings 23, 24); round 2 on a blocker present since round 1 (finding 25, a secret glued to `;`, `)` or `,`) and a major (finding 26, httpie basic auth); round 3 on a major (finding 27, credentials holding `[ ] { }`, even single-quoted); round 4 on a major (finding 29, an apostrophe in the prose flipping the quote reading) and on finding 28 omitting a residual class. All six are fixed; round 4 also fixed an escaped-quote leak it found (finding 30) and a userinfo `@` leak (finding 31). Round 5 rejected on a major introduced by the finding 29 fix: the scan went quadratic on a JSON-serialised paste (finding 32, fixed, together with two older quadratic regex windows found in the same sweep; a 200 KB paste now scans in 0.10 s, down from 15.6 s). Finding 19 is **Fixed on the probed forms**: 57 forms x 14 suffixes x 3 paths (2394/2394 refused), 60 reviewer rows (47 reviewer shapes verbatim plus 13 round-4 rows) x 3 paths (180/180 refused) and 84 benign forms x 3 paths (252/252 sent). Regex detection cannot prove absence; finding 28 states the residual. The probe is a parametrized test in the repository, not a scratchpad script.

Every piece of evidence comes from execution in a temporary HOME with fictional client names (`acmecorp`, `betacorp`). Secret values in tests are built at runtime from synthetic fragments. The operator's redaction config was never read.

### Findings

| # | Finding | Sev. | STRIDE / OWASP / CWE | Evidence (command → result) | Fix or recommendation | Owner |
|---|---|---|---|---|---|---|
| 8 | `audit.jsonl` had no rotation (PR1, carried). | minor | D / A09:2025 | `test_oversized_file_rotates_exactly_once`: file over the cap → one `.1`, prefill intact, the next line in a fresh file. | **Fixed** in `audit.py`: `rotate_if_oversized(path, AUDIT_MAX_BYTES)` before each append, same flock (`audit.jsonl.rotlock`) and `.1` generation as the telemetry. The cap is a 10 MB constant, not the `ARKA_TELEMETRY_MAX_BYTES` knob: a cap of 1 byte would overwrite `.1` on every write and erase the evidence. Rotation is never a gate: a helper that raises is suppressed, and if the file is still over the cap after the attempt the line is written in place with `"rotation": "failed"`. The fail-closed rule for the write itself is unchanged (`test_rotation_failure_still_fails_closed_when_write_fails`). | Bruno (done) |
| 19 | **Command-line credentials without a vendor prefix left in clear.** `secret_labels` only knows prefixed keys (`sk-ant-`, `AKIA`, `xoxb-` ...). Probe on `prepare_state({"command": ...}, state_class="command")`: `export API_TOKEN=<opaque>`, `curl -H 'Authorization: Bearer <opaque>'`, `mysql -p<password>`, `https://user:<password>@host`, `PGPASSWORD=<opaque> psql` → **all five SENT**, with `redact=True` and with `redact=False`. | **major** | I / A04:2025 Cryptographic Failures (exposure of credentials) / CWE-200, CWE-522 | Probe before the fix: 10/10 sent. After: `redact=True` 5/5 `egress-denied:secret`; `redact=False` still 5/5 sent (see R-P1). | **Fixed on the probed forms** (findings 23-27; the probe and its limits are in the table below and in finding 28). On the policy path: new `core/egress/credentials.py` detects credentials by context (secret-named assignment, `--password`/`--token`/`--api-key` flag, `Authorization`/`X-Api-Key` header, `curl -u user:pass`, `mysql -p…`/`sshpass -p`, URL userinfo), and rejects shell expansions, placeholders and, for assignments, paths, URLs and calls. What the detectors reject, exactly (since round 3): `$` or a backtick in a bare or double-quoted value (substitution: the text names the secret); a single-quoted value only when it is nothing but `$NAME`, `${NAME}` or `$(…)`; for bare assignment and flag values, a code shape (`name[…]` or `name{…}` running to the end of the value, a call `fn(`); paths, URLs, placeholders and values that do not look like a token. `[ ] { }` are not rejected. History: up to round 2, `_REFERENCE` rejected ANY value holding `$(){}[]<>,;` or a backtick (the cause of finding 25); round 2's `_is_expansion` still rejected a bare value holding `[ ] { }` and applied that bare rule to fragments inside single quotes (the cause of finding 27). A value that starts inside quotes runs to the closing quote; a bare value ends at whitespace, quotes and `; & \| ( ) < > ,` and backtick. `policy.evaluate` now uses `egress_secret_labels` (prefixes + context). Labels only reach the audit, never values (`test_policy_denies_a_bearer_header_and_audits_no_value`). **Fixed (R-P1)** for the two paths that skip the policy (`redactClients:false` and the missing-config degrade): `privacy.py:45` imports `egress_secret_labels` and `_refuse_secrets` calls it at `privacy.py:200`. | Bruno (policy) / `core/decisions` lane (R-P1), both done |
| 20 | **`command_state` caps at 4000 chars BEFORE the privacy checks**: the PR1 finding 2 (M2) shape again, one layer up. A client name or a key straddling the cut ships as a fragment that no longer matches its pattern. | **major** | I / A06:2025 Insecure Design / CWE-200 | `prepare_state(command_state("echo " + "a"*3991 + " acmecorp"))` → SENT, tail `'… acm'`; same with a Slack-shaped key → SENT, tail `'… xox'`. With the full string: the name is redacted, the key is denied. | **Fixed (R-C1)**: `command_state` cuts at the last whitespace before the limit and drops the token the cut would split (`sites/command.py:31-37`). Pinned by `test_command_cap_never_ships_a_split_client_name` and `test_command_cap_never_ships_a_secret_prefix`, now plain tests. | `core/decisions` lane, done |
| 7 | After a 401 the breaker stays open for up to 1 h even when the operator rotates the key (PR1, carried). `backoff:{cause}` (`engine.py:206-210`) fixes the observability half only; recovery is unchanged. | minor | D / A09:2025 | Reading `client.py:146` (`trip("http-401", 3600)`) and `backoff.blocked()`: no key input. | **Fixed (R-B1)**: `transport.key_fingerprint()` (`transport.py:61`); a 401 trip stores it (`backoff.py:116`); `blocked()` ignores a block earned by another key (`backoff.py:97`), and `trip()` keeps a later deadline only when the same key set it (`backoff.py:111`, `_set_by_other_key` at `backoff.py:121-123`). Pinned by `test_rotating_the_key_reopens_a_401_breaker` and `test_non_401_trips_are_not_key_bound` (`test_decisions_backoff.py`, 15 passed). | `core/decisions` lane, done |
| 16 | Off-menu text on non-choice or unasked answers reaching `decisions.jsonl` (PR1 QG r2 m4, carried). | minor | T / A05:2025 / CWE-74 | Working tree of the `core/decisions` lane: `site.clean_answer` drops `choice` on non-choice questions and `score` on non-score ones; `engine.valid_site_answers` feeds `Outcome.answers`, which is what telemetry records (`engine.py:368`). Not committed yet, so not verified here by test. | **In progress** in the `core/decisions` lane. To verify at the Quality Gate with a hostile non-choice answer that carries a `choice` string. | `core/decisions` lane |
| 21 | Audit retention is one kept generation: about 20 MB, about a month at the PR2 rate (~2000 calls a day, ~300 bytes a line). Older lines are dropped. | info | R / A09:2025 | Arithmetic from finding 8's measured line size. | Accepted for PR2: the lines carry only digests and hashed labels, so their evidence value is correlation within a recent window. If a longer window is ever required, add N generations under the same lock in `telemetry_rotate`, not a second mechanism. | — |
| 22 | With `redactClients: false`, a command naming a client leaves with the name in clear (probe: `cd <home>/Work/acmecorp-api` → sent as is). | info | I / — | Probe above, `redact=False` row. | By design (operator's explicit choice, audited as `override=redact-disabled`). Secrets are still refused once R-P1 lands. No change. | — |
| 23 | **QG r1 B1 (blocker): quoted credentials hidden by JSON escaping.** `prepare_state` ran `json.dumps` before the secret checks, so `API_TOKEN="v"` became `API_TOKEN=\"v\"` and the value patterns captured only the backslash. `export API_TOKEN="…"`, `PGPASSWORD="…" psql`, `curl -s -u "bob:…"` and `tool --password "…"` were labelled on the raw text and `[]` on the serialised text, so they were SENT on all three paths. Reproduced by Marta and Francisca. | **blocker** | I / A04:2025 / CWE-200, CWE-522 | Probe (temp HOME, the 4 commands, `redact=True`, `redact=False`, missing config): after the fix, 12/12 REFUSED. | **Fixed** in `privacy.py`: `prepare_state` first calls `_refuse_leaf_secrets(state)` (`privacy.py:72`), which runs `egress_secret_labels` on every raw string of the state before serialisation: dict keys and values, list items, and `str()` of any non-JSON leaf, exactly what `json.dumps(default=str)` would ship (`privacy.py:154-195`). The walk is iterative (a 5000-deep list does not overflow the stack) and bounded by `MAX_SCAN_CHARS`. The scan of the serialised text stays as the second layer. The four commands are rows in `SECRET_COMMANDS`, run on the three paths. | Bruno, done |
| 24 | **QG r1 B2 (blocker): gaps in the credential patterns.** (a) `_ASSIGNMENT` required a character before the secret word, so a bare `TOKEN=`, `PASSWORD=`, `KEY=`, `SECRET=` or `export token=` passed; (b) no query-string detector (`?token=`, `&sig=` …); (c) `mysql -p'pw'` and `-p"pw"` passed; (d) `DB_PASS=`/`PASS=` (the word list had no `PASS`), `docker login -p`, `redis-cli -a` and `aws configure set aws_secret_access_key <v>` passed. | **blocker** | I / A04:2025 / CWE-522 | Same probe, 19 commands × 3 paths: after the fix, 57/57 REFUSED. | **Fixed** in `credentials.py`: (a) the name takes zero or more characters before the word, with the pointer-suffix guard kept; (b) `_QUERY` for `access_token`, `refresh_token`, `id_token`, `client_secret`, `api_key`, `token`, `key`, `password`, `passwd`, `pwd`, `secret`, `sig`, `signature`, `auth`; (c) the password flags take a quoted value; (d) the word list has `PASS` and `PWD`, and `_PASSWORD_FLAGS` covers `docker`/`podman`/`nerdctl login -p` and `redis-cli -a`; `_CLI_SETTING` covers `aws configure set` for the secret key and the session token. The widening brought one false positive (`COMPASS_URL=http://…`); URL values and the `_URL`/`_URI`/`_HOST`/`_ENDPOINT` suffixes are now excluded, since credentials inside a URL are the userinfo and query detectors' job. One regression row per case, and 19 rows of ordinary commands pin the false-positive side. | Bruno, done |
| 25 | **QG r2 B3 (blocker): a secret glued to `;`, `)` or `,` left in clear on all three paths.** Reproduced by Francisca and Marta: `export API_TOKEN=abc123XYZ99; ./deploy`, `export TOKEN=…; ./d`, `mysql -uroot -p…;`, `(export API_TOKEN=…)`, `PGPASSWORD=…,psql`, `curl ?token=…;`, `sshpass -p …;ssh h`, `docker login -p …;`, `Authorization: Bearer …;`. Present since round 1 and missed by every reviewer, me included: my probes never glued a separator to a value. | **blocker** | I / A04:2025 / CWE-200, CWE-522 | Probe after round 2: 44 leak forms x 14 suffixes x 3 paths → 1848/1848 REFUSED; re-run inside the round-3 set (table below). | **Fixed** in `credentials.py`, two independent changes. (1) Every bare value group ends at the shell metacharacters (`_STOP`: whitespace, quotes, `; & \| ( ) < > ,`, backtick) in `_VALUE`, `_AUTH_HEADER`, `_KEY_HEADER`, `_BASIC_FLAGS`, `_QUERY` (atomic groups, so the regex cannot back off a character). (2) `_REFERENCE` is replaced by a quote-aware rule (refined again in round 3, finding 27): a `;` or `,` inside quotes is data, not a reference, so `export TOKEN="ab;cd…"` is caught too. **Deliberate deviation for `_USERINFO`:** it is bounded by `:` and `@`, not by shell syntax, so the terminator class there would make a password containing `;` or `)` leak; mutation U below proves it (43 tests fail when the proposed class is applied to it). Userinfo keeps its class and relies on (2). A call guard (`fn(x)`, `cfg[k]` after a bare value is code) and "space is not a symbol" in the opacity rule keep the widening off code and prose. | Bruno, done |
| 26 | **QG r2 M1 (major): httpie basic auth not detected.** `http --auth bob:pw` and `http -a bob:pw` (also `https`, `xh`, `xhs`) were sent on all three paths, while `curl -u`, the same shape, was caught. | major | I / A04:2025 / CWE-522 | Probe: the 3 httpie forms x 14 suffixes x 3 paths → 126/126 REFUSED. | **Fixed**: `_BASIC_FLAGS` gains a pattern for `-a`/`--auth` (`=` or space) only after `http`, `https`, `xh` or `xhs`. Negative rows: `ls -a /tmp`, `git commit -a -m …`, `http GET …` without auth, `http -a $USER:$PASS …`, `http --auth-type=bearer …`. | Bruno, done |
| 27 | **QG r3 M2 (major): credentials holding `[ ] { }` left in clear, even single-quoted.** Reproduced by Francisca and Marta: `curl -u 'admin:Xk9]pL2vQ' …` SENT (without the `]`: REFUSED), `-H 'Authorization: Basic Xk9{pL2vQ}'`, `'…?api_key=Xk9]pL2vQ'`, `git clone 'https://bob:Xk9]pL2vQ@…'`, `http -a 'bob:Xk9]pL2vQ'`, and the bare `API_TOKEN=abc123XYZ99}`, `export API_TOKEN=abc[123]XYZ`. Cause: the sub-token detectors captured a fragment inside the quoted word, and the round-2 rule treated `[ ] { }` in a bare value as expansion. This contradicted the docstring and finding 19, which said a single-quoted value never counts as an expansion. | major | I / A04:2025 / CWE-522 | Probe: the 5 M2 forms, the 2 bare forms and 6 more bracket/quote forms x 14 suffixes x 3 paths, plus the reviewers' 47 shapes x 3 paths → all REFUSED (table below). | **Fixed** in `credentials.py`: (1) `[ ] { }` are no longer expansion markers anywhere; only `$` and backtick are, and only outside single quotes (`_EXPANSION`). (2) `_quote_context` reads the quotes of the whole text once, as a POSIX shell does, and a sub-token value that starts inside quotes runs to the closing quote. So `'admin:ab;cd…'` and `'admin:Pa$$w0rd…'` are caught, which neither round-2 rule caught. Inside double quotes the extension stops at whitespace, quotes and backslashes, so the JSON-serialised layer does not run a value into the rest of the command. (3) The bracket rule is now only a code guard for bare assignment and flag values, and it is narrower than the one prescribed (`name[…]`/`name{…}` running to the end of the value). A blanket `[ ] { }` guard on bare assignments would have kept Marta's `API_TOKEN=abc123XYZ99}` and `abc[123]XYZ` leaking. (4) A single-quoted value that is nothing but a reference (`'Bearer $TOKEN'`) is still a reference. (5) Header values must look like a token, so `grep "Authorization: Bearer" logs/` and `grep -n "X-Api-Key: missing header"` stay benign (the probe found both as false positives while the fix was in progress). The guard in (3) has a leak side: a bare value that is a secret shaped like code is SENT; finding 28 lists it as a residual class. The whole-text quote reading in (2) was itself defeated by an unmatched apostrophe earlier in the text (`can't`), so `'admin:Pa$$w0rd…'` after one was SENT until round 4; that is finding 29, **fixed**. | Bruno, done |
| 28 | **Residual: regex detection cannot prove absence.** Every independent probe so far found one more class (round 1: quoting under JSON; round 2: glued separators, httpie; round 3: brackets and quote context; round 4: an apostrophe flipping the quote reading, escaped quotes found while fixing it, and an unencoded `@` in userinfo (finding 31); round 5: the N1 fix made the scan quadratic (finding 32)). The residual is bounded by the probe set, listed in `tests/python/test_egress_credentials.py`: `LEAK_FORMS` (57), `SUFFIXES` (14), `REVIEWER_LEAKS` (60), `BENIGN_FORMS` (84), `PATHS` (3). Known and accepted inside that bound: (a) a password shorter than 6 characters; (b) a password with spaces in an unquoted or double-quoted `-u`; (c) credential syntaxes of tools without a detector (a new CLI flag, a config file echoed into a command); (d) **the unquoted code-shape class (leak side of finding 27(3)):** a bare assignment or flag value shaped `name[…]` or `name{…}` running to the end of the value is read as code and SENT. Executed on this tree, all SENT: `API_TOKEN=tok9{a}`, `API_TOKEN=abcdef9[1]`, `API_TOKEN=abc123[XYZ99`, `SECRET=f00[bar]`, `TOKEN=Abc9{x}`, `token=secret9[0]`, `--password Hunter2[x]`, `--token=Qx9{abc}`; `API_TOKEN=x9[a]` is SENT too, but by (a) first (5 characters). Quoted, code-shaped values are refused (`export API_TOKEN='x9[ab]'`, `--token "Qx9{abc}"`, both in the probe). The guard exists because diffs are full of `token = tokens2[0]` and `cfg_key = cfg[k1]` (15 false refusals when it is removed, mutation Mf); (e) escaping nested deeper than 8 levels: `_escape_layers` stops at 8 un-escapes (a work bound, see finding 30); the probe goes to 3; (f) on the benign side, a false refusal: `echo it's; curl -H "Authorization: Bearer $TOKEN" x` is refused, because the whole-text reading puts `$TOKEN` inside the apostrophe's quote and a refusal wins when either reading says literal (finding 29); its sibling `I can't: echo "$HOME" && http -a "$U:$P" x.io` is refused for the same reason (`['basic-auth flag']`, executed on this tree); (g) the work bounds of finding 32: a password flag more than 512 characters after its tool's name (`mysql … -p`, `docker login … -p`, `redis-cli … -a`, `http … -a`) is not read, and a quoted value is read to 256 characters past its regex match (a longer value is still refused: its head decides every test, rows in `test_bounded_reads_keep_long_values`). N1 (finding 29) is fixed, not accepted. | residual | I / A04:2025 | The probe table below; the test file is the list. The (d) rows were run through `egress_secret_labels` on this tree: 9/9 `[]`. | Accepted for PR2. Every new class goes into the probe set before its fix, and the probe runs in the suite. (d) and (f), both shapes of (f), go to PR5; a candidate for (d), not yet tried, is to read a code shape as code only when the name before the bracket also appears elsewhere in the text (`core/decisions` hardening). | Bruno (security-eng), 2026-09-23; (d), (f): PR5 |
| 29 | **QG r4 N1 (major): an unmatched apostrophe earlier in the text flipped the whole-text quote reading, so a single-quoted value holding `$` or a backtick was read as a variable reference and SENT.** Reproduced by Paulo: `egress_secret_labels("I can't log in with curl -u 'admin:Summer$2026x' https://api.example.com, why?")` → `[]` (with "cannot": `['basic-auth flag']`); also `[]`: `it's: http -a 'bob:Pa$$w0rd9' x.io`, `can't auth: curl -H 'Authorization: Bearer ab$c9Zq9k7k7' x`. SENT on the redacted, redaction-disabled and config-missing paths. Prompt states are English prose full of apostrophes. | major | I / A04:2025 / CWE-522 | After the fix, the 3 shapes → `['basic-auth flag']`, `['basic-auth flag']`, `['auth header']`; in `REVIEWER_LEAKS`, 9/9 refused (3 shapes x 3 paths), plus one row in `test_decisions_privacy_command.py` x 3 paths. | **Fixed** in `credentials.py` (Francisca's proposal, deny-leaning): for the sub-token detectors, `_readings` returns the whole-text reading AND a local one (`_local`), and a refusal wins when EITHER is literal. The local reading takes the nearest quote before the value on its line; if that quote opens a word (line start, whitespace or `=` before it) and the same quote character appears later on the line, the value is re-read under that quote and runs to the closing quote (`_extend`). Round 4 did this by re-reading the rest of the line (`_quote_context(text[q:le])`), which finding 32 replaced with bisects on the quote and newline marks. The either-rule is required, not a choice: `echo don't -H "Authorization: Bearer ab$c…" x'` is one the shell really single-quotes from the apostrophe, so there the local `"…"` reading is the wrong one (row in the probe; mutation R6). m4 (`echo it's; curl -H "Authorization: Bearer $TOKEN" x`) is **not** closed: the local reading says reference, the whole-text one says literal, and the either-rule refuses. It stays on record as a benign-side residual (finding 28(f)). | Bruno, done |
| 30 | **Found this round (major): a string state holding escaped quotes (`\"`) was SENT, raw and serialised.** Francisca's round-4 note said such a string is scanned only by the serialised layer. Executed, neither layer caught it: `prepare_state({"command": 'export API_TOKEN=\"<opaque>\"'})` SENT with `redact=True` and `redact=False`; same for `curl -u \"bob:<pw>\" x` and a JSON document carried as a string. The realistic shape is nested shell quoting: `ssh host "export API_TOKEN=\"<opaque>\" && ./run"`, `bash -c "curl -u \"bob:<pw>\" x"`, `bash -c "mysql -p\"<pw>\" app"`, all `[]` before the fix. Cause: read as written, the value is a lone backslash (under 6 characters). | major | I / A04:2025 / CWE-522 | After: the 4 escaped shapes (`ssh host "export API_TOKEN=\"…\" && ./run"`, `bash -c "curl -u \"bob:…\" x"`, `bash -c "mysql -p\"…\" app"`, `export API_TOKEN=\"…\"`) + a 2-level `bash -c "ssh h \"export API_TOKEN=\\\"…\\\"\""` in `REVIEWER_LEAKS` (15/15 refused over 3 paths); `test_every_escape_layer_is_scanned[0..3]` (0 to 7 backslashes before the quote) at the detector; one row in `test_decisions_privacy_command.py` x 3 paths. | **Fixed** in `credentials.py`: `credential_labels` scans every escape layer (`_escape_layers`: the text, then successive un-escapes of `\"`, `\'` and `\\` until nothing changes, at most 8), and a label on any layer refuses. The benign side holds: `ssh h "export API_TOKEN=\"\$API_TOKEN\""` is sent (a `\$` is not un-escaped, and the value stays a reference). | Bruno, done |
| 31 | **QG r4 m3 (minor): an unencoded `@` inside a URL userinfo password was SENT.** `git clone 'https://bob:p@ss{w0}rd@g.io/r'` → `[]`. RFC 3986 §3.2.1 wants a literal `@` in userinfo percent-encoded, but a typed `p@ss` is still the password, and what leaves is the secret whatever the RFC says. | minor | I / A04:2025 / CWE-522 | After: that shape and the bare `git clone https://bob:p@ssw0rd9@g.io/r` → `['url userinfo']`, 6/6 refused over 3 paths. | **Fixed** (my call, rather than listing it): `_USERINFO` takes the password up to the LAST `@` of the authority (the class stops at `/ ? #`, where the authority ends). Inside quotes the extension would stop at the first `@`; `_extend` skips its stops inside the span the regex already matched (the `floor`), so the password runs to the last `@`; beyond the floor it still applies the double-quote stops (whitespace, quotes, backslash), which keeps `grep "Authorization: Bearer" logs/` benign on the serialised layer (mutations R7, R8). | Bruno, done |
| 32 | **QG r5 B1 (major): the credential scan was quadratic on a JSON-serialised paste, introduced by the finding 29 fix.** `_local` did O(line) work for every sub-token match: two `rfind` back to the line start, the slice `text[start:le]` and a pure-Python `_quote_context(text[q:le])` over the rest of the line. `privacy._serialise` runs `json.dumps` on the state, so newlines become `\n` and the serialised text is ONE line of up to `MAX_SCAN_CHARS` (1,000,000). `engine._fetch` runs `prepare_state` synchronously before the POST, so `timeout_ms` does not bound it: one large paste blows `ARKA_UPS_BUDGET_MS` (6000) and can pass the 20 s UserPromptSubmit ceiling. Reproduced by Marta, Francisca and Paulo with N lines of `curl -sS -H "Authorization: Bearer $TOKEN" "https://api.example.com/v1/items/{i}?page=1" \| jq .`, serialised: 49 KB 0.93 s, 98 KB 3.70 s, 198 KB 14.58 s (multiline 0.06 s); adversarial `('a' "-u x:y" )*n` 109 s at 195 KB. The same sweep found two older quadratic windows, not from round 5: the tool-argument window `[^\n|;&]*?` of the password-flag and httpie patterns (every `mysql`, `http`, `redis-cli`, `docker login` scanned the rest of the one-line text: 100 KB of `mysql x ` 6.0 s, `http x ` 8.1 s) and the userinfo scheme `\b[a-z][a-z0-9+.\-]*` (a start at every letter after `.` or `-`: 100 KB of `a.` 13.8 s, of `--a-` 6.9 s, the shape of a url-safe base64 blob). | major | D / A06:2025 / CWE-407 | Timings on this machine, `credential_labels` (before → after): serialised paste 50 KB 0.97 → 0.02 s, 101 KB 3.91 → 0.05 s, 203 KB 15.62 → 0.10 s; adversarial 100 KB raw 26.95 → 0.04 s, 195 KB raw 109 (Marta) → 0.07 s; `mysql x ` 100 KB 6.01 → 0.08 s; `a.` 100 KB 13.76 → 0.04 s; at the 1 MB cap: paste 0.50 s, `a.` 0.39 s, `mysql x ` 0.86 s, adversarial 0.68 s. `test_serialised_many_match_paste_scans_in_linear_time` (200 KB ≤ 1.0 s and ≤ 3x the 100 KB time + 0.05 s; round-5 code: 14.57 s, after 0.10 s) and `test_adversarial_text_scans_under_a_second` (8 shapes, raw and serialised). Equivalence: a differential fuzz of the round-5 module against this one, 400,000 random shapes from 35 credential-syntax tokens (raw and serialised), 0 label differences. | **Fixed** in `credentials.py`. (1) `_scan` indexes each layer once: the quote context plus the sorted positions of `'`, `"` and the newline; `_local` finds the nearest quote, the line bounds and the closing quote by bisect (O(log n)), with no slice and no re-read. (2) `_extend` no longer walks characters: in single quotes only `'` ends the value, in double quotes the stops (whitespace, quotes, backslash) are also where the quoted run can end, so the end is one stop-character search, read to at most 256 characters past the regex match (`_VALUE_CAP`). (3) The tool-argument window is `[^\n|;&]{0,512}?` (`_ARGS`). (4) The userinfo scheme is `[a-z][a-z0-9+.\-]{0,62}` without a word boundary, so a longer scheme matches on its tail (deny side). The bounds are residual 28(g). N1 and finding 30 stay closed: the 3 N1 shapes and the 3 nested-quoting shapes of finding 30 are refused raw and serialised; mutations R1 and R6 still kill (table below). | Bruno (security-eng), 2026-09-23 |

Blast radius of finding 19's fix: `policy.evaluate` is also the NotebookLM choke point (`core/kb/nlm_client.py`). A note that contains a literal credential is now denied there too. That is the deny direction, the finding kind is `secret` with a named label, and it is allowlistable per exact label like every other secret. `test_egress_policy.py`, `test_notebooklm_chokepoint.py` and `test_leak_scanner*.py` pass unchanged.

### Changes recommended to the other lanes (all three landed)

**R-P1** (`core/decisions/privacy.py`, 2 lines). `_refuse_secrets` must use the same vocabulary as the policy:

```python
from core.egress.credentials import egress_secret_labels   # replaces the secret_labels import
...
    if egress_secret_labels(text):                          # in _refuse_secrets
```

Landed at `privacy.py:45` and `privacy.py:200`. Before it landed, applying the swap through a pytest plugin flipped the 10 R-P1 xfails to XPASS(strict) while `test_decisions_privacy.py` still passed; the markers were removed with the fix.

**R-C1** (`core/decisions/sites/command.py`, `command_state`). Never cut inside a token; drop the token the cut would split:

```python
_TRUNCATED = " [truncated]"

def command_state(command: str) -> dict[str, Any]:
    if len(command) <= MAX_COMMAND_CHARS:
        return {"command": command}
    head = command[: MAX_COMMAND_CHARS - len(_TRUNCATED)]
    cut = max(head.rfind(" "), head.rfind("\n"), head.rfind("\t"))
    return {"command": (head[:cut] if cut > 0 else "") + _TRUNCATED}
```

Landed at `sites/command.py:21` and `:31-37` (the constant as shipped is `" [truncated]"`). Before it landed, patching this function in through a plugin flipped both R-C1 xfails to XPASS(strict); the markers were removed with the fix.

**R-B1** (`core/decisions/transport.py` + `backoff.py`, 9 lines). Tie a 401 trip to the key that earned it:

```python
# transport.py
def key_fingerprint() -> str:
    return hashlib.sha256(_resolve_key().encode("utf-8")).hexdigest()[:8]

# backoff.py — trip(): add the fingerprint for 401 only
    payload = {"reason": reason, "until": until}
    if reason == "http-401":
        payload["key"] = key_fingerprint()   # lazy import inside trip()
# backoff.py — blocked(): a 401 block earned by another key is not ours
    if state.get("key") and state["key"] != key_fingerprint():
        return None
# backoff.py — trip(): only keep a later deadline set by the SAME key
    if ... and until < current <= ref + MAX_BLOCK_S and _read().get("key") in (None, payload.get("key")):
```

The last line matters: without it, a 401 on the new key cannot land while the old key's longer block exists, so every turn pays a failing call for up to an hour. Eight hex chars of a SHA-256 of a high-entropy API key do not help anyone recover it (unlike the low-entropy client names, which need the salted HMAC). Landed at `transport.py:61` and `backoff.py:97, 111-123`, with the suggested tests (`test_rotating_the_key_reopens_a_401_breaker`, `test_non_401_trips_are_not_key_bound`).

### Mutation proof (PR2)

Scratchpad script: copy the file aside, apply the mutation, run the named test files, restore by copy. The suite passes again after every restore.

| Mutation | Tests that kill it |
|---|---|
| A1 no rotation call in `record` | `test_oversized_file_rotates_exactly_once`, `test_rotated_and_fresh_files_stay_private`, `test_rotation_crash_does_not_deny_egress`, `test_refused_rename_does_not_deny_egress`, `test_concurrent_processes_lose_no_line[×3]` |
| A2 rotation call outside `suppress` | `test_rotation_crash_does_not_deny_egress` (the raise flips the ALLOW to denied) |
| A3 no post-rotation size check | `test_refused_rename_does_not_deny_egress`, `test_rotation_crash_does_not_deny_egress` |
| A4 unlocked rotator (size check, sleep, `os.replace`, no flock) | `test_concurrent_processes_lose_no_line[×3]`, 5 runs out of 5 (four writers released together by a start file) |
| C1 policy back to `secret_labels` | `test_redacted_path_refuses_command_secrets[×5]`, `test_secret_at_the_end_of_a_long_command_is_still_refused`, `test_policy_denies_a_bearer_header_and_audits_no_value` |
| C2 no reference filter | `test_references_placeholders_and_pointers_pass` (5 rows) |
| C3 no placeholder filter | `test_references_placeholders_and_pointers_pass[psql postgres://app:password@…]` |
| C4 no pointer-suffix filter | `test_references_placeholders_and_pointers_pass` (`SECRET_NAME`, `API_TOKEN_CMD` rows; the first run survived because every pointer row was also a path, and the two rows were added for this) |
| C5 no path filter | `test_references_placeholders_and_pointers_pass[GOOGLE_APPLICATION_CREDENTIALS=…]` |
| C6 no opacity rule | `test_references_placeholders_and_pointers_pass` (`SORT_KEY=created_at`, `api_key = settings.API_KEY`) |
| C7 no auth-header detector | 2 positive rows, `test_redacted_path_refuses_command_secrets[curl …]`, `test_policy_denies_a_bearer_header_and_audits_no_value` |
| C8 no URL-userinfo detector | 2 positive rows, `test_redacted_path_refuses_command_secrets[git …]` |
| C9 no password-flag detector | 2 positive rows, `test_redacted_path_refuses_command_secrets[mysql …]` |
| C10 no assignment detector | 3 positive rows, `test_redacted_path_refuses_command_secrets[export …, PGPASSWORD …]`, `test_secret_at_the_end_of_a_long_command_is_still_refused` |
| C11 no credential-flag detector | 2 positive rows |
| C12 no basic-auth detector | 1 positive row |
| P1 (R-P1 applied, before it landed) | the 10 R-P1 xfails turned into XPASS(strict) failures |
| P2 (R-C1 applied, before it landed) | the 2 R-C1 xfails turned into XPASS(strict) failures |
| B1 remove `_refuse_leaf_secrets(state)` (scan only the serialised text again) | 17 tests: the 4 quoted rows × 3 paths, `test_raw_leaves_are_scanned_before_serialisation`, `test_nested_leaves_and_keys_are_scanned[×2]`, `test_deep_state_does_not_blow_the_stack` |
| B1k dict keys not walked | `test_nested_leaves_and_keys_are_scanned[state2]` |
| B2a a character required before the secret word | 6 rows: `TOKEN=`, `PASSWORD=`, `KEY=`, `SECRET=`, `export token=`, `PASS=` |
| B2b no query detector | 7 query-string rows |
| B2c password flags without the quoted form | `mysql -p'…'`, `mysql -p"…"` |
| B2d `PASS`/`PWD` dropped from the word list | `DB_PASS=`, `PASS=`, `MYSQL_PWD=` |
| B2d no `docker login -p` | the `docker login` row |
| B2d no `redis-cli -a` | the `redis-cli` row |
| B2d no `aws configure set` detector | the 2 `aws configure set` rows |
| G1 URL values not excluded | `export API_KEY_DOCS=https://…` |
| G2 `_URL`/`_URI`/`_HOST`/`_ENDPOINT` suffixes dropped | `export TOKEN_URL=auth-v2.example.org` |

Round 2 (findings 25, 26). Each value-class mutation reverts ONE pattern to its old class and leaves the others fixed. The counts are failing probe tests for that pattern's own forms, per separator:

| Mutation | `;` | `)` | `,` | Total failing tests |
|---|---|---|---|---|
| V `_VALUE` back to `[^\s'"]+` (assignment, flag, password flags, aws) | 57 | 57 | 57 | 350 (including the call-guard rows) |
| AH `_AUTH_HEADER` back to the old class | 3 | 3 | 3 | 18 |
| KH `_KEY_HEADER` back to the old class | 3 | 3 | 3 | 18 |
| BF `_BASIC_FLAGS` (curl `-u`, httpie) back to the old class | 12 | 12 | 12 | 72 |
| Q `_QUERY` back to `[^&\s'"#]+` | 3 | 3 | 3 | 15 |
| U the terminator class applied to `_USERINFO` (the proposed fix) | 6 | 3 | 3 | 43 |
| E old `_REFERENCE` semantics restored in `_literal` | 12 | 6 | 6 | 86 |
| H no httpie pattern | 18 | 9 | 9 | 129 |
| G no call/subscript guard after a bare value | — | — | — | 4 (`api_key = compute_key2(x)` as negative row and benign probe) |
| S space counted as a symbol in the opacity rule | — | — | — | 4 (`SORT_KEY="created at"`) |

For V, AH, KH, BF and Q the kills come from the separator-then-`$` suffixes (`;$next`, `)$(next)`, `,${next}`). With the quote-aware expansion rule in place, a swallowed separator on its own no longer throws the value away; the swallowed `$` does, and only the terminator class stops it. For E, U and H the plain separators kill as well. The `;` column for U, E and H also counts the spaced ` ; next` control.

Round 3 (finding 27). Each mutation changes one line of `credentials.py`; the counts are failing tests in `test_egress_credentials.py` and `test_decisions_privacy_command.py` (leak side = a secret sent; benign side = a false refusal):

| Mutation | Leak side | Benign side | Example of a killing test |
|---|---|---|---|
| Ma `[ ] { }` restored as expansion markers (the round-2 rule in the sub-token detectors) | 194 | 0 | `API_TOKEN=abc123XYZ99}`, `curl -u 'admin:Xk9]pL2vQ'` |
| Mb bare-value rule applied inside single quotes | 128 | 0 | `curl -u 'admin:Pa$$w0rd…'` |
| Mc quote context ignored (every value read as bare) | 129 | 0 | `basic-single-dollar`, `basic-single-separator` |
| Md no extension to the closing quote for sub-tokens | 43 | 0 | `curl -u 'admin:ab;cd…'` |
| Me no whole-reference rule in single quotes | 0 | 4 | `curl -H 'Authorization: Bearer $TOKEN'` |
| Mf no code-shape guard | 0 | 15 | `cfg_key = cfg[k1]`, `token = tokens2[0]` |
| Mg double-quote extension without its whitespace/quote/backslash stops | 0 | 12 | `docker run -u 1000:1000 image && echo done` (serialised layer) |
| Mj header values need not look like a token | 0 | 4 | `grep -n "X-Api-Key: missing header" app.log` |
| V round-2 `_VALUE` class restored (B3, re-checked) | 460 | 11 | the separator suffixes |
| H httpie pattern removed (M1, re-checked) | 199 | 0 | `http --auth bob:…` |

Round 4 (findings 29-31, QG r4 m2). Same method: one line of `credentials.py` changed, the two test files run, restore by copy, `shasum` equal before and after (`d3850bb4…`). Counts are failing tests:

| Mutation | Leak side | Benign side | Example of a killing test |
|---|---|---|---|
| R1 local reading removed (`local = None`) | 12 | 0 | `I can't log in with curl -u 'admin:Summer$2026x' …` |
| R2 code-shape guard applied to quoted values too (QG r4 m2; survived round 4 with 3005 passed) | 6 | 0 | `export API_TOKEN='x9[ab]'`, `--token "Qx9{abc}"` |
| R3 `_USERINFO` back to the first `@` | 6 | 0 | `git clone 'https://bob:p@ss{w0}rd@g.io/r'` |
| R4 escape layers off | 18 | 0 | `ssh host "export API_TOKEN=\"…\" && ./run"` |
| R5a escape layers: 1 | 2 | 0 | `test_every_escape_layer_is_scanned[2]`, `[3]` |
| R5b escape layers: 2 | 1 | 0 | `test_every_escape_layer_is_scanned[3]` |
| R6 local reading only (whole-text reading dropped when a local one exists) | 3 | 0 | `echo don't -H "Authorization: Bearer ab$c…" x'` |
| R7 `extend` stops applied inside the regex's own match (no `floor`) | 3 | 0 | `git clone 'https://bob:p@ss{w0}rd@g.io/r'` |
| R8 `floor` overrides the double-quote stops | 0 | 3 | `grep "Authorization: Bearer" logs/` (serialised layer) |
| R9 word-opening requirement dropped | 0 | 3 | `it's Bob's: curl -u bob:$PASS 'x'` |
| R10 closes-later requirement dropped | 0 | 3 | `echo x'y 'curl -u bob:$PASS z` |
| R11 local reading skipped for the headers only | 3 | 0 | `can't auth: curl -H 'Authorization: Bearer ab$c9Zq9k7k7' x` |

m2's two rows: `export API_TOKEN='x9[a]'` as prescribed is 5 characters, under `_MIN_VALUE`, and was SENT before and after this change (not "refused today"); the row uses `'x9[ab]'`. No mutation kills an escape depth of 3 against 8: 8 is a work bound (each layer halves a run of backslashes), not a detector, and finding 28(e) states it. One check I wrote this round, `local[start - q] == _NONE`, could never be true (`q` is the nearest quote before the value, so the value is inside it), and I removed it.

Two guards I tried while fixing (a backslash stop in bare values, scheme words such as `Bearer` as placeholders) survived their mutations, because the double-quote stops and the header token rule already cover them. I removed them rather than keep code no test can kill.

The concurrency test with the real helper: 10 runs out of 10 green.

Round 5 (finding 32). Same method, restore by copy, `shasum` equal before and after (`975205e9…`). Counts are failing tests in `test_egress_credentials.py` and `test_decisions_privacy_command.py`:

| Mutation | Failing | Example of a killing test |
|---|---|---|
| Whole fix reverted (round-5 `credentials.py`, run on the timed tests) | 4 of 4 run | `test_serialised_many_match_paste_scans_in_linear_time` (14.57 s against 1.0 s); `[quotes]` 26.95 s, `[mysql]` 5.98 s, `[dotted]` 13.80 s |
| B1a tool-argument window unbounded again | 4 | `test_adversarial_text_scans_under_a_second[mysql]`, `[httpie]`, `[redis]`, `[docker]` |
| B1b userinfo scheme back to `\b[a-z][…]*` | 2 | `test_adversarial_text_scans_under_a_second[dotted]`, `[dashed]` |
| B1c scheme bounded but word boundary kept | 1 | `test_bounded_reads_keep_long_values` (an 80-character scheme) |
| B1d value read without its cap | 1 | `test_adversarial_text_scans_under_a_second[one-quoted-span]` |
| R1 local reading removed (re-run) | 13 (leak side) | the 9 N1 rows, 3 privacy rows, `test_bounded_reads_keep_long_values` (a long single-quoted value after `can't`) |
| R6 local reading only (re-run) | 3 (leak side) | `echo don't -H "Authorization: Bearer ab$c…" x'` |
| R7 no `floor` (re-run) | 3 (leak side) | `git clone 'https://bob:p@ss{w0}rd@g.io/r'` |
| R8 `floor` overrides the double-quote stops (re-run) | 3 (benign side) | `grep "Authorization: Bearer" logs/` |
| R9 word-opening requirement dropped (re-run) | 3 (benign side) | `it's Bob's: curl -u bob:$PASS 'x'` |
| R10 closes-later requirement dropped (re-run) | 3 (benign side) | `echo x'y 'curl -u bob:$PASS z` |

B1d first survived at 100 KB: a literal value short-circuits `any()`, so the far-quote span cost only one read. The killing shape uses reference values (`-u a:$(x)`), which never short-circuit, at 300 KB (0.69 s at 90 KB without the cap, quadratic; 0.04 s with it).

### Verification (PR2, this lane)

Re-run after Quality Gate round 5 (venv `~/.arkaos/venv/bin`):

- `pytest tests/python/test_egress*.py tests/python/test_decisions_privacy*.py tests/python/test_decisions_policy.py -q` → **exit 0**, 3207 passed (round 4: 3194; +13 timed and bounded-read tests). The timed tests, 5 runs in a row: 5/5 green, about 4 s each run.
- `ruff check core/egress` → **exit 0**.
- `mypy core/egress core/decisions/privacy.py --follow-imports=silent` → **exit 0**. Without the flag: exit 1, 51 errors, all in imported modules outside this lane (`core/governance/harness_scanner.py` 14, `core/runtime/*` 31, others 6); 0 in `core/egress` or `privacy.py`.
- `uvx codespell core/ tests/ docs/security/` → **exit 0**.
- `~/.arkaos/bin/arka-py -m core.governance.evidence_checks . --checks security-grep,lint` → **exit 0**, both PASS.
- Probe: `pytest tests/python/test_egress_credentials.py -k test_probe` → **exit 0**, 2826 passed (2394 + 180 + 252).
- Functions ≤ 30 lines: `credentials.py` max 27 (`_quote_context`), `test_egress_credentials.py` max 16 (`_send`), `audit.py` max 27 (`load_or_create_salt`; `record` is now 22, with the rotation stamp moved into `_stamped`, QG r4 m5), the two test files max 16.

Round 3, kept for the record:

- `~/.arkaos/bin/arka-py -m pytest tests/python/test_egress*.py tests/python/test_decisions_privacy*.py tests/python/test_decisions_policy.py -q` → **exit 0**, 3127 passed.
- `~/.arkaos/bin/arka-py -m ruff check core/egress core/decisions/privacy.py` → **exit 0**.
- `uvx codespell core/ tests/ docs/security/` → **exit 0**.
- `~/.arkaos/bin/arka-py -m core.governance.evidence_checks . --checks security-grep` → **exit 0**, PASS; the synthetic fixture lines carry `arka:sec-ok(hardcoded-password)`.
- `~/.arkaos/bin/arka-py -m mypy core/egress core/decisions/privacy.py --follow-imports=silent` → **exit 0**.
- Probe: `pytest tests/python/test_egress_credentials.py -k test_probe` → **exit 0**, 2769 passed (2394 form x suffix x path cases + 141 reviewer cases + 234 benign cases).
- Wider regression (`test_decisions_*`, `test_ups_decisions`, `test_notebooklm_chokepoint`, `test_leak_scanner*`, `test_egress_policy`, `test_telemetry_rotate`) → 763 passed.

### Probe: 57 forms x 14 suffixes x 3 paths (after Quality Gate round 4)

Source: `tests/python/test_egress_credentials.py` (`LEAK_FORMS`, `SUFFIXES`, `REVIEWER_LEAKS`, `BENIGN_FORMS`, `PATHS`; tests `test_probe_leak_form_is_refused`, `test_probe_reviewer_leak_is_refused`, `test_probe_benign_form_is_sent`). Each case calls `prepare_state({"command": …}, state_class="command")` in a temporary HOME on three paths: `redact=True` with a redaction config, `redactClients:false`, and no config.

What the set contains:
- my round-1 probe;
- every shape named in the round-2 and round-3 findings;
- every POSITIVE and NEGATIVE row of the credential tests;
- verbatim, the reviewers' scratchpad probes: `probe3.py` (13 leak, 10 benign, 11 bracket shapes), `probe4.py` (7) and `probe_r2.py` (16), 47 leak shapes in all;
- round 4: Paulo's 3 N1 shapes verbatim, the 2 m2 rows, the 2 m3 rows, 5 escaped-quote rows and the either-rule row (13 more rows: 47 reviewer shapes verbatim plus 13 round-4 rows, 60 in all), and 6 benign rows for the local reading and the escape layers.

The Quality Gate notes mention 37 leak and 25 benign shapes for Marta's round-3 probe, but those files hold fewer. Every shape they hold is here.

Leak forms, refused / cases (each cell = forms x 3 paths; `∅` = no suffix):

| Detector (forms) | `∅` | `;next` | `)next` | `,next` | `&&next` | `\|next` | `>out.txt` | ` ; next` | `;$next` | `)$(next)` | `,${next}` | `&&$next` | `\|$next` | `>$out` | Refused |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| assign (18) | 54/54 | 54/54 | 54/54 | 54/54 | 54/54 | 54/54 | 54/54 | 54/54 | 54/54 | 54/54 | 54/54 | 54/54 | 54/54 | 54/54 | 756/756 |
| flag (3) | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 126/126 |
| authhdr (3) | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 126/126 |
| keyhdr (1) | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 42/42 |
| basic (5) | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 210/210 |
| httpie (4) | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 168/168 |
| pwflag (8) | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 336/336 |
| aws (2) | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 84/84 |
| userinfo (4) | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 168/168 |
| query (8) | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 336/336 |
| vendor (1) | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 42/42 |
| **all (57)** | 171/171 | 171/171 | 171/171 | 171/171 | 171/171 | 171/171 | 171/171 | 171/171 | 171/171 | 171/171 | 171/171 | 171/171 | 171/171 | 171/171 | **2394/2394** |

Reviewer rows (47 reviewer shapes verbatim plus 13 round-4 rows, own separators, not crossed with the suffixes): 60/60 refused on each of the three paths (180/180).

Benign forms: 84/84 sent on each of the three paths (252/252), 0 false refusals among them (finding 28(f) is a false refusal outside the set). The round-3 additions are `curl -u 'bob:$PASS'`, `cfg_key = cfg[k1]`, `key = f(x)`, `TOKEN=${TOK}`, `export API_TOKEN=$(vault read x)`, the header-name greps, and `docker run -u 1000:1000 image && echo done`.

Earlier rounds, kept for the record: after round 2, the same suite gave 2364 passed and the probe 1848/1848 on its 44 forms; round 3 showed those forms did not cover brackets or quote context (finding 27). After round 1, `~/.arkaos/bin/arka-py -m pytest tests/python/test_egress*.py tests/python/test_decisions_privacy*.py -q` gave 241 passed, and the round-1 probe gave 69/69 REFUSED on the forms it probed; round 2 showed that those forms did not cover a value glued to a separator (finding 25). Unchanged since round 1: `tests/python/test_decisions_backoff.py` → 15 passed (R-B1); regression `test_egress_policy.py`, `test_notebooklm_chokepoint.py`, `test_telemetry_rotate.py`, `test_decisions_privacy.py`, `test_leak_scanner*.py` → 307 passed.

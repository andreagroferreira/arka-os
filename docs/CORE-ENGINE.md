# ArkaOS Core Engine

Module map of the Python core engine. Each subsystem is a first-class package under `core/`; this document describes what every package owns and the key files within it.

For the broader data-flow picture (hooks, bridge, dashboard) see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Subsystem Overview

| Package | Purpose |
|---|---|
| `core/synapse/` | 12-layer context injection into every prompt |
| `core/workflow/` | YAML workflow execution, gate evaluation, enforcement |
| `core/agents/` | Agent YAML schema, validation, registry, and DNA |
| `core/squads/` | Squad YAML loading and in-memory registry |
| `core/governance/` | Constitution loader, Quality Gate, telemetry, compliance |
| `core/runtime/` | Multi-runtime adapters, subagent dispatch, LLM cost |
| `core/knowledge/` | Vector store, chunker, embedder, pattern cards |
| `core/forge/` | Multi-agent planning with complexity escalation |
| `core/memory/` | Session store, context compaction, resume rehydration |
| `core/cognition/` | Dreaming, research scheduler, auto-documentation |
| `core/orchestration/` | Coordination patterns (Solo Sprint, handoff, chain) |
| `core/budget/` | Per-department token tracking and daily limits |
| `core/personas/` | Persona builder from knowledge sources |
| `core/tasks/` | Background SQLite job queue for async operations |
| `core/obsidian/` | Vault writer, taxonomy, cataloger, relator |
| `core/specs/` | Living spec manager and schema |
| `core/conclave/` | Multi-advisor planning session (Gate 2 PLAN) |
| `core/terminal/` | Persistent terminal session tracking |
| `core/sync/` | Project sync and install-state management |
| `core/registry/` | Unified agent/skill/command registry |
| `core/profile/` | User profile and preference persistence |
| `core/release/` | Preflight checks for the release pipeline |
| `core/shared/` | Cross-cutting utilities (session ID validation, etc.) |

---

## core/synapse — Context Injection

Synapse is the context injection engine. It runs on every prompt via `scripts/synapse-bridge.py`, evaluates all registered layers, and produces a compact context string injected as a system-level prefix before the model sees the user's input. The engine targets under 100ms total with 65% context reduction compared to injecting everything unconditionally.

Layers execute in priority order. Each layer returns a `LayerResult` containing a short tag (e.g. `[dept:dev]`), full content, estimated token count, compute time, and a cache flag. Layers with `cache_ttl > 0` are stored in a TTL-keyed in-process `LayerCache`; the cache key is `{layer_id}:{cwd}:{active_agent}`.

**Registered layers (12 total in `create_default_engine`):**

| Layer | ID | File | TTL | Priority | Purpose |
|---|---|---|---|---|---|
| Constitution | L0 | `layers.py` | 300s | 0 | Compressed governance rules from `config/constitution.yaml` |
| Department | L1 | `layers.py` | none | 10 | Keyword/command-prefix routing to a department slug |
| Agent | L2 | `layers.py` | 30s | 20 | Active agent ID + DISC label from registry |
| AgentExperiences | L2.6 | `agent_experiences_layer.py` | 30s | 25 | Past REJECTED QG verdicts for the dispatched specialist |
| KBContext | L2.5 | `layers.py` | none | 25 | Obsidian notes relevant to the prompt (vector or Jaccard) |
| Project | L3 | `layers.py` | 30s | 30 | Active project name and stack from `PromptContext` |
| KnowledgeRetrieval | L3.5 | `layers.py` | 30s | 35 | Semantic search from the vector store (when configured) |
| Branch | L4 | `layers.py` | none | 40 | Current git branch (suppressed for main/master/dev) |
| CommandHints | L5 | `layers.py` | 30s | 50 | Top-2 matching commands from the command registry |
| QualityGate | L6 | `layers.py` | 60s | 60 | Pending QG reviews and recent approved verdicts |
| Time | L7 | `layers.py` | 3600s | 70 | Time-of-day period (morning/afternoon/evening) |
| PatternLibrary | L7.5 | `pattern_library_layer.py` | 60s | 75 | Prior pattern cards matching the prompt keywords |
| ForgeContext | L8 | `layers.py` | none | 80 | Active Forge plan: decisions, risks, rejected approaches |
| SessionMemory | L9 | `layers.py` | none | 90 | Restored workflow position and violations from prior session |

Note: L2.5 and L3.5 are both conditional — L2.5 is registered when either a vector store or a vault path is provided; L3.5 is registered only when a vector store is available.

| File | Responsibility |
|---|---|
| `engine.py` | `SynapseEngine` class: layer registration, `inject()` loop, metrics ring buffer (500 entries) |
| `layers.py` | Abstract `Layer` base class, `PromptContext`, `LayerResult`, and implementations L0–L9 including `KBContextLayer` (L2.5) |
| `agent_experiences_layer.py` | `AgentExperiencesLayer` (L2.6): parses `[arka:dispatch]` markers, queries `core.governance.agent_experiences` |
| `pattern_library_layer.py` | `PatternLibraryLayer` (L7.5): keyword extraction with Latin-1 Supplement support, queries `core.knowledge.pattern_cards` |
| `cache.py` | `LayerCache`: TTL-based in-process cache, hit/miss statistics, `evict_expired()` |
| `kb_cache.py` | `KBSessionCache`: per-session overlap detection for L3.5; `record_obsidian_query` / `obsidian_queried_this_turn` for the KB-first gate |
| `__init__.py` | Package exports |

---

## core/workflow — Workflow Execution

The workflow engine executes declarative YAML workflows: sequences of phases each carrying agent assignments, a gate, and optional outputs. It enforces the Constitution's `sequential-validation` and `full-visibility` rules by design — no phase starts until its predecessor completes and passes its gate. See [WORKFLOW-ENGINE.md](WORKFLOW-ENGINE.md) for full execution detail.

| File | Responsibility |
|---|---|
| `schema.py` | Pydantic models: `Workflow`, `Phase`, `Gate`, `AgentAssignment`, `PhaseOutput`, `GateType` (auto, user\_approval, quality\_gate, condition, budget\_check), `WorkflowTier` |
| `engine.py` | `WorkflowEngine`: sequential phase executor, gate evaluator, dependency checks, Obsidian output saving |
| `loader.py` | `load_workflow(path)` — YAML to `Workflow` via Pydantic; `load_all_squads` variant unused here |
| `state.py` | JSON state file at `~/.arkaos/workflow-state.json`: atomic writes (temp-rename), `init_workflow`, `update_phase`, `add_violation`, `is_phase_completed`. Fed by `gate_checkpoint.py` since v4.1.0 |
| `gate_checkpoint.py` | Stop-hook checkpointer (v4.1.0): scans the turn for `[arka:gate:N]` markers and persists the furthest gate + Gate-3 test evidence to `state.py` AND the per-session `SessionStore` snapshot, enabling structured resume after rate-limit/context interruptions |
| `announcer.py` | `PhaseAnnouncer`: formats `[PHASE] Starting:` / `[PHASE] Completed:` messages, tracks per-phase durations |
| `enforcer.py` | `WorkflowEnforcer`: evaluates all 14 NON-NEGOTIABLE Constitution rules, returns violations with BLOCK/ESCALATE/WARN severity |
| `flow_enforcer.py` | `evaluate()`: PreToolUse gate — checks EFFECT tools require a flow marker (`[arka:routing]`, `[arka:trivial]`, `[arka:gate:N]`, legacy `[arka:phase:N]`) in the last 20 assistant messages; feature-flagged via `hooks.hardEnforcement` |
| `research_gate.py` | KB-first gate for external research tools (Context7, WebSearch, Firecrawl); first violation nudges, second denies; feature-flagged via `hooks.kbFirst` |
| `rules_registry.py` | Static `RULES_REGISTRY` mapping rule IDs to `RuleDefinition` objects |
| `marker_cache.py` | Per-session flow marker cache (avoids repeated transcript reads) |
| `kb_first_decider.py` | Helper deciding whether Obsidian was consulted this turn |
| `specialist_enforcer.py` | Validates `[arka:dispatch]` marker presence before specialist tool calls |
| `dashboard.py` | Workflow status aggregation for the FastAPI `/api/workflow` endpoint |
| `recovery.py` | Resume an interrupted workflow from `workflow-state.json` |
| `session_summary.py` | Generates end-of-session workflow summaries for PreCompact hook |
| `state_reader.sh` | Bash helper — reads `workflow-state.json` for hook scripts without requiring Python |

---

## core/agents — Agent Schema and DNA

Every agent is defined as a YAML file under `departments/{dept}/agents/{agent}.yaml`. This package owns the schema, validation, loading, and the in-process registry. The 4-framework behavioral DNA (DISC, Enneagram, Big Five, MBTI) is validated for cross-framework consistency: a high-C DISC score should correlate with high Conscientiousness in Big Five.

| File | Responsibility |
|---|---|
| `schema.py` | Pydantic `Agent` model: tier, department, role, behavioral\_dna (DISC/Enneagram/OCEAN/MBTI), model preference |
| `loader.py` | Loads all agent YAMLs from `departments/*/agents/*.yaml` into `Agent` instances |
| `validator.py` | Cross-framework consistency checks (DISC vs OCEAN vs MBTI coherence) |
| `dna_registry.py` | In-memory registry of loaded agents keyed by `agent.id` |
| `registry_gen.py` | Generates `knowledge/agents-registry-v2.json` from loaded YAMLs |
| `behavior_enforcer.py` | Enforces that agent output style matches DISC communication profile |
| `draft_builder.py` | Scaffolds a new agent YAML from a minimal description |
| `field_suggester.py` | Suggests DISC/Enneagram fields for draft agents |
| `string_suggester.py` | Suggests wording for agent role and description fields |
| `obsidian_export.py` | Exports agent profiles to Obsidian vault as structured notes |
| `adapters/disc_adapter.py` | Converts raw DISC scores to a normalized `DISCProfile` dataclass |

---

## core/squads — Squad Assembly

Squads are the runtime grouping unit: a department squad is permanent (lead + specialists), a project squad is assembled ad-hoc from agents borrowed across departments. There is no `router.py` in this package — routing is performed by Synapse's `DepartmentLayer` (L1). Squad assembly and lookup live in `loader.py` and `registry.py`.

| File | Responsibility |
|---|---|
| `schema.py` | Pydantic `Squad` and `SquadMember` models; `SquadType` (department, project); `TeamTopologyType` (stream-aligned, platform, enabling) |
| `loader.py` | `load_squad(path)` for a single YAML; `load_all_squads(base_dir)` scans `*/squad.yaml`; `load_matrix_squads(squads_dir)` scans `*/*.yaml` for mission/transversal squads |
| `registry.py` | `SquadRegistry`: `get_by_department()`, `get_by_prefix()`, `create_project_squad()` (borrows agents cross-department), `disband_project_squad()`, `find_agent_across_squads()` |

---

## core/governance — Constitution and Quality Gate

Governance enforces the Constitution at runtime. The Quality Gate (Marta orchestrates Eduardo and Francisca) is mandatory on every workflow — neither reviewer can be skipped. Beyond the quality gate, this package tracks compliance telemetry, agent activation, DNA fidelity, and sycophancy detection.

| File | Responsibility |
|---|---|
| `constitution.py` | `Constitution` Pydantic model; `load_constitution(path)`; `compress_for_context()` — produces the L0 Synapse string |
| `quality_api.py` | `list_pending()`, `list_approved(limit)` — used by Synapse L6 and the dashboard; owns QG record persistence |
| `quality_router.py` | Routes incoming review requests to the correct QG reviewer (Eduardo for copy, Francisca for tech) |
| `review_workflow.py` | Step-by-step QG review workflow: orchestrates Eduardo + Francisca, collects APPROVED/REJECTED verdicts |
| `agent_experiences.py` | `Experience` model; `query_experiences(agent_id, limit)` — used by Synapse L2.6 |
| `agent_experiences_cli.py` | CLI for recording and querying agent experiences |
| `cqo_experience_recorder.py` | Records QG outcomes as experiences for the dispatched specialist |
| `compliance_telemetry.py` | Structured JSONL telemetry for constitution rule evaluations |
| `enforcement_telemetry.py` | Structured JSONL telemetry for flow-enforcer decisions |
| `specialist_telemetry.py` | Telemetry for specialist dispatch events |
| `activation_tracker.py` | Tracks which agents have been activated per session |
| `dna_fidelity.py` | Validates that agent output style is consistent with its YAML DNA |
| `closing_marker_check.py` | Checks that workflows end with a `[arka:gate:4]` closing marker (legacy `[arka:phase:13]` accepted during the v4.1 window) |
| `kb_cite_check.py` | Verifies that deliverables cite KB sources when relevant notes were injected |
| `meta_tag_check.py` | Checks that Obsidian output notes have required frontmatter tags |
| `leak_scanner.py` | Scans output for client names and confidential strings before publish |
| `learning_detector.py` | Detects when a session produces a pattern worth recording |
| `skill_proposer.py` | Proposes a new skill YAML when a repeated pattern is detected |
| `sycophancy_detector.py` | Flags responses that agree with the user without critical evaluation |
| `design_system_lint.py` | Lints frontend output against the design system token set |

---

## core/runtime — Multi-Runtime Adapters

Runtime adapters translate ArkaOS concepts (agent dispatch, context injection) into the conventions of each supported AI coding tool. The subagent pattern gives every dispatched task a fresh context window; the orchestrator uses only 10–15% of its own context for dispatch and result collection.

| File | Responsibility |
|---|---|
| `base.py` | `RuntimeAdapter` abstract base class |
| `claude_code.py` | Claude Code adapter: CLAUDE.md injection, hook registration |
| `codex_cli.py` | Codex CLI adapter |
| `gemini_cli.py` | Gemini CLI adapter |
| `cursor.py` | Cursor adapter: `.cursorrules` injection |
| `subagent.py` | `HandoffArtifact`, `SubagentResult`, `SubagentDispatcher`; `to_prompt()` serialises to ~82 word-tokens (660 chars) for a representative task |
| `context_compactor.py` | `ContextCompactor.build()` — compresses prior session content into a `context_summary` for handoff artifacts |
| `llm_provider.py` | LLM provider abstraction (Claude API, Ollama, etc.) |
| `ollama_provider.py` | Ollama-specific provider for local inference |
| `pricing.py` | Token cost tables per model |
| `llm_cost_telemetry.py` | Tracks and persists per-model LLM spend |
| `registry.py` | Runtime registry mapping runtime IDs to adapter instances |
| `path_resolver.py` | Resolves hook/config paths across OS and installation modes |
| `user_paths.py` | Canonical paths under `~/.arkaos/` for user-mutable data |

---

## core/knowledge — Vector Store and Pattern Cards

The knowledge subsystem ingests external content (YouTube, PDFs, articles, web) into a SQLite-backed vector store for semantic retrieval by Synapse L3.5. It also maintains a pattern card library used by Synapse L7.5 to surface prior implementations.

| File | Responsibility |
|---|---|
| `vector_store.py` | sqlite-vss vector storage and semantic search |
| `embedder.py` | Embedding generation (OpenAI ada-002 or local model) |
| `chunker.py` | Splits documents into overlapping ~500-token chunks |
| `ingest.py` | End-to-end ingest pipeline: source detection, download, transcribe, chunk, embed, store |
| `sources.py` | Source type detection and metadata extraction |
| `indexer.py` | Full-text index maintenance for hybrid (vector + keyword) search |
| `agent_match.py` | Matches knowledge chunks to the agents most likely to use them |
| `pattern_cards.py` | `PatternCard` model; `query_patterns(keywords, limit)` — queried by Synapse L7.5 |
| `pattern_cards_cli.py` | CLI for recording and listing pattern cards |

---

## core/forge — Multi-Agent Planning

The Forge handles complex tasks that require planning before execution. It runs multiple reviewer advisors in parallel (positive, devil's advocate, Q&A, KB research, best-solution validator, pessimistic) to produce a synthesised plan, then dispatches implementation to specialists.

| File | Responsibility |
|---|---|
| `schema.py` | `ForgePlan`, `CriticSynthesis`, `RiskEntry`, `RejectedElement` models |
| `complexity.py` | Classifies task complexity (simple/focused/complex/super) to select workflow tier |
| `orchestrator.py` | Runs the 6 parallel reviewers, synthesises output via `CriticSynthesis` |
| `persistence.py` | `get_active_plan()` / `save_plan()` — used by Synapse L8 to inject active plan context |
| `renderer.py` | Formats a `ForgePlan` for human-readable plan presentation |
| `handoff.py` | Produces the implementation handoff from Forge plan to workflow engine |
| `runtime_dispatcher.py` | Dispatches Forge phases to the appropriate runtime adapter |

---

## core/memory — Session Store and Rehydration

Memory persists session state across Claude Code compaction events so that workflow position, agent context, and violations survive context window resets.

| File | Responsibility |
|---|---|
| `session_store.py` | Appends and reads session events (phase transitions, violations, decisions) to a per-session JSONL file under `~/.arkaos/sessions/` |
| `compressor.py` | Summarises a session store into a compact digest for the PreCompact hook |
| `rehydrator.py` | `build_resume_context()` — reconstructs a resume string from the latest session digest; consumed by Synapse L9 |

---

## core/cognition — Dreaming and Research Scheduler

Cognition runs autonomously in the background. The Dreaming subsystem consolidates knowledge and generates synthetic insights. The research scheduler queues and executes research tasks triggered by agent interactions.

| File | Responsibility |
|---|---|
| `dreaming.py` | Consolidates recent experiences and KB content into durable insights |
| `dreams_reader.py` | Reads and surfaces completed dream outputs |
| `retrieval.py` | Cross-session knowledge retrieval for the dreaming pipeline |
| `auto_documentor.py` | Automatically documents patterns discovered during dreaming |
| `reorganizer.py` | Reorganises Obsidian vault structure based on accumulated insights |
| `reorganizer_cli.py` | CLI entrypoint for vault reorganisation |
| `reorganizer_scheduler.py` | Cron-style scheduler for vault reorganisation runs |
| `capture/` | Subdirectory: tools for capturing raw content for dreaming |
| `insights/` | Subdirectory: insight storage and tagging |
| `memory/` | Subdirectory: cognition-specific memory (distinct from `core/memory/`) |
| `research/` | Subdirectory: research task queue and executor |
| `scheduler/` | Subdirectory: generic scheduler used by dreaming and research |

---

## core/orchestration — Coordination Patterns

Four coordination patterns for multi-agent work. The correct pattern is selected based on task complexity and whether cross-department agents are needed.

| Pattern | File | When used |
|---|---|---|
| Solo Sprint | `protocol.py` | Single department, lead assigns to one specialist |
| Domain Deep-Dive | `protocol.py` | One agent runs multiple skills in sequence |
| Multi-Agent Handoff | `protocol.py` | Cross-department pipeline with structured handoffs |
| Skill Chain | `protocol.py` | Procedural pipeline without agent identity (e.g., ingest-chunk-embed-store) |

| File | Responsibility |
|---|---|
| `protocol.py` | `OrchestrationProtocol` enum and dispatcher |
| `patterns.py` | Concrete pattern implementations |
| `checkpoint.py` | Mid-execution checkpointing for long-running orchestrations |

---

## core/budget — Token Tracking

Tracks token usage by department and tier against daily quotas. The workflow engine evaluates `budget_check` gates by calling the budget manager before starting a phase.

| File | Responsibility |
|---|---|
| `schema.py` | `BudgetSummary`, `TierLimit` models |
| `manager.py` | `BudgetManager`: `record_usage()`, `check_budget(tier, tokens)`, `needs_approval(tier)`, `get_summary(tier)`, daily reset |

---

## core/obsidian — Vault Writer

All workflow outputs are saved to the Obsidian vault. This package handles writing, taxonomy, cataloguing, and linking between notes.

| File | Responsibility |
|---|---|
| `writer.py` | `ObsidianWriter.save(obsidian_path, content, department, workflow)` |
| `templates.py` | Note templates per output type (ADR, feature doc, review) |
| `taxonomy.py` | Tag and folder taxonomy for the vault |
| `cataloger.py` | Indexes saved notes for the Synapse L2.5 fallback |
| `relator.py` | Generates wikilinks between related notes |

---

## core/specs — Living Specifications

Living specs maintain bidirectional sync between spec documents and code. When code changes, the spec delta is surfaced; when a spec changes, implementation gaps are flagged.

| File | Responsibility |
|---|---|
| `schema.py` | `Spec` Pydantic model: sections, acceptance criteria, linked files |
| `manager.py` | `SpecManager`: load/save specs, compute deltas, detect implementation gaps |

---

## core/governance telemetry paths

All telemetry is written to `~/.arkaos/telemetry/` as JSONL. Audit bypass logs go to `~/.arkaos/audit/`. These paths are documented in `core/runtime/user_paths.py`.

---

Related: [ARCHITECTURE.md](ARCHITECTURE.md) | [WORKFLOW-ENGINE.md](WORKFLOW-ENGINE.md) | [BENCHMARKS.md](BENCHMARKS.md)

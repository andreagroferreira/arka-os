---
title: ArkaOS Runtime — Estratégia de Evolução para Multi-Provider Agent OS
date: 2026-05-27
status: decided (2026-07-19 — ver docs/adr/2026-07-19-arkaos-runtime-pivot.md)
author: Strategy synthesis
deciders: Andre Groferreira (owner)
related:
  - docs/adr/2026-04-20-llm-agnostic.md
  - docs/adr/2026-05-13-differentiation-vs-anthropic-memory.md
  - docs/adr/2026-05-13-cognitive-layer-pivot-to-hooks.md
  - core/runtime/llm_provider.py
  - core/runtime/pricing.py
  - core/runtime/llm_cost_telemetry.py
tags: [strategy, runtime, byok, multi-provider, hermes, openclaw, north-star]
---

# ArkaOS Runtime — Estratégia de Evolução

> *Pivot proposto: passar de "ArkaOS como skill dentro do Claude Code" para "ArkaOS como runtime próprio multi-provider com governance de custos por scope de task". Manter o que é moat (behavioral DNA, departments, Constitution, Quality Gate, 13-phase flow). Construir por baixo o que falta (provider abstraction executiva, model router activo, cost governor com budgets enforceable, execution loop independente).*

---

## 1. Sumário executivo

**Tese.** O modelo "ArkaOS = orchestrator a viver dentro do Claude Code" tem dois plafonds estruturais: (a) o Claude Code sobrepõe-se ao ArkaOS apesar de instruções explícitas — é arquitectura, não prompting; (b) toda a economia depende da subscrição Max da Anthropic, que está sujeita a apertos unilaterais (Maio 2026: subida de limites por 50% só "até Julho", evidência de constraint contínuo). Continuar assim significa ter um plafond definido por outra empresa.

**Proposta.** Evoluir o ArkaOS para o que o Andre descreve como *"competidor do Hermes e OpenClaw"*: um agent OS runtime-próprio com BYOK multi-provider e cost governance por scope. Não é construir do zero — é re-eixar peças que já existem (`core/runtime/llm_provider.py`, `pricing.py`, `llm_cost_telemetry.py`) e adicionar o que falta (router activo, mais providers, budget caps enforceable, execution loop standalone).

**Moat.** Hermes e OpenClaw têm runtime + multi-provider mas **não têm**: (1) behavioral DNA com 4 frameworks por agent (DISC + Enneagram + OCEAN + MBTI); (2) 16 departamentos com knowledge frameworks reais (Porter, Damodaran, AARRR, etc.); (3) Constitution com 4 enforcement levels e Quality Gate como veto absoluto; (4) 13-phase mandatory flow com gates. Isto é o que ArkaOS *já* tem. O moat não está em risco — está subvalorizado por estar preso a um runtime.

**Validação de mercado.** BYOK é o standard emergente para enterprise agent rollouts: a plataforma cobra pelo *value-add* (routing, governance, observability), os tokens vão para a conta do cliente. Em 2026 a literatura diz que *"a diferença entre smart routing e one-model-fits-all é a diferença entre estratégia AI sustentável e crise de orçamento"*. A janela de oportunidade está aberta agora porque Hermes e OpenClaw não cobrem governance vertical de domínio — só horizontal.

**Recomendação táctica.** Aprovar a evolução em fases preservando 100% do uso actual (Claude Code continua a ser um *backend de primeira classe*, não desaparece). Primeiro fechar o ângulo *strategy/competitive*, depois decidir arquitectura, depois decidir negócio. Roadmap (fase 3 da conversa do Andre) só depois destas três decisões.

**Decisões pendentes (lista curta no §10).** Pelo menos 6 decisões estratégicas requerem input directo do Andre antes de avançar para arquitectura detalhada e roadmap de fases.

---

## 2. Diagnóstico actual (Maio 2026, v3.70.9)

### 2.1 O que ArkaOS já tem que viabiliza o pivot

A leitura do código actual (não do `CLAUDE.md` que está desactualizado a marcar v2.0.0-alpha.1) mostra que o trabalho fundacional para multi-provider **já está parcialmente feito**:

| Peça existente | Localização | Estado |
|---|---|---|
| Protocol `LLMProvider` | `core/runtime/llm_provider.py` | Estável — abstracção fina (`complete`, `is_available`, `name`) |
| `SubagentProvider` (default) | mesmo ficheiro | Shell-out para o CLI do runtime activo |
| `OllamaProvider` | `core/runtime/ollama_provider.py` | Provider local já existe |
| `AnthropicDirectProvider` | `llm_provider.py` | SDK directo, com prompt caching |
| `StubProvider` | mesmo ficheiro | Fallback final (template) |
| Fallback chain | `_FALLBACK_ORDER` | `subagent → ollama → anthropic-direct → stub` |
| Cost telemetry | `core/runtime/llm_cost_telemetry.py` | JSONL append por call, agregação `/arka costs` |
| Pricing table | `core/runtime/pricing.py` | Estimativa por modelo (informational) |
| Runtime adapters | `core/runtime/{claude_code,codex_cli,gemini_cli,cursor}.py` | 4 runtimes mapeados |
| Three-pillar differentiation | ADR 2026-05-13 | Local-only, Vault-integrated, Multi-runtime |

ADR `2026-04-20-llm-agnostic` consagra hoje **"runtime decide o modelo, ArkaOS delega"** como princípio. É um princípio coerente — mas é exactamente o eixo que o pivot proposto inverte.

### 2.2 Onde está o plafond

| Dor | Causa estrutural | Impacto observável |
|---|---|---|
| Claude Code sobrepõe-se ao ArkaOS | ArkaOS corre *dentro* de um host com o seu próprio system prompt, hooks, e regras. CLAUDE.md não tem precedência sobre system prompt do host. | Squad routing ignorado em ~30-40% dos turns complexos (estimativa qualitativa do Andre); mandatory-flow é skipped sem aviso. |
| Custo é refém da Anthropic | Toda a inferência via subscrição Max → limites semanais/mensais → throttling em peak hours → upgrades forçados. | Maio 2026 a Anthropic subiu limites 50% "até Julho" — admissão de constraint contínuo. Plafond definido externamente. |
| Modelo escolhe-se à mão por agent YAML | Constitution define `model:` por agent mas a aplicação fica entregue ao runtime. Não há routing por *task complexity* ou *budget remaining*. | Tier-2 mecânico (commit writers, routing, fetchers) corre Sonnet quando podia correr Haiku/Gemini Flash/Qwen local. Estimativa: 30-50% do custo pode ser cortado sem perda. |
| Sem budget caps reais | ADR-011: telemetria é "informational, not restrictive". Avisa a $5/sessão, nunca bloqueia. | Cliente enterprise não consegue dar luz verde. "Andre vai gastar quanto este mês?" é uma pergunta sem teto definido. |
| ArkaOS Runtime ≠ ArkaOS-as-skill | Hoje não há "modo standalone" — sem Claude/Codex/Gemini/Cursor, ArkaOS só corre o stub template. | Não é vendável como produto autónomo. É um plugin de um plugin. |

### 2.3 Onde estão os moats subvalorizados

Antes de propor o pivot, vale destacar o que **só o ArkaOS tem** (verificado contra docs Hermes e OpenClaw):

1. **Behavioral DNA com 4 frameworks por agent.** Hermes tem `SOUL.md` (texto livre). OpenClaw tem `SOUL.md` (mesmo conceito). Nenhum dos dois tem DISC + Enneagram + OCEAN + MBTI estruturado. Replicar isto exige meses de design organizacional, não de código.
2. **16 departamentos com knowledge frameworks reais.** Porter, Damodaran DCF, AARRR, Schwartz, Lencioni, SOLID, OWASP, Baymard, Zettelkasten — não são "personas vagas", são metodologias enterprise-grade que cada agente *aplica*. Hermes e OpenClaw são domain-agnostic.
3. **Constitution com Quality Gate e veto absoluto.** Marta (CQO) + Eduardo + Francisca em Opus, com APROVADO/REJEITADO binário em cada workflow. Hermes e OpenClaw têm `command approval` (sudo-style) mas não têm governance executiva.
4. **13-phase mandatory flow.** Input verbatim → context → routing → hierarchy → research → team → plan (6 reviewers paralelos) → save → wait approval → TODO → per-todo loop com QA+Security+Quality Gate → document → summary. Isto é o que o cliente enterprise compra: previsibilidade.
5. **The Forge (multi-agent planning com complexity escalation).** Sem equivalente.
6. **Living Specs com sync bidirecional.** Sem equivalente.

A consequência operacional: **o moat não está no runtime. Está acima do runtime.** O pivot tem de extrair o runtime e mantê-lo *modular*, preservando 100% das camadas superiores.

---

## 3. Validação de mercado

### 3.1 BYOK virou standard enterprise

A pesquisa de Maio 2026 confirma a tendência:

- **Augment Code (enterprise guide):** *"BYOK envolve enterprises a fornecer credenciais LLM próprias (OpenAI, Anthropic, AWS Bedrock) directamente à plataforma agent, com chamadas faturadas e logadas na conta do provider do cliente, governadas pelos seus DPAs e Zero Data Retention."*
- **Pristan.chat (BYOK vs Managed AI 2026):** *"Plataformas geralmente cobram separadamente por features de value-add — observability, routing, guardrails, access controls — enquanto custos de token vão directamente para a conta do provider do cliente."*
- **DataStudios (OpenRouter BYOK):** *"OpenRouter BYOK funciona como uma camada de provider-key e routing-control que separa a relação com o provider da camada de integração da aplicação."*

A consequência: **o que o cliente paga à plataforma é o cérebro de governance, não o inference**. Isto encaixa exactamente no perfil do ArkaOS — o valor cobrável é o agent OS, não o token.

### 3.2 Smart routing é o diferenciador

- **ClawRouters (AI Token Costs 2026):** *"Com agentes a fazer centenas de calls por task e context windows a consumir milhões de tokens, o diferencial de custo entre smart routing e 'one model fits all' é a diferença entre uma estratégia AI sustentável e uma crise de orçamento."*
- **MaximAI (Top 5 LLM Router Solutions 2026):** lista 5 routers comerciais que justificam pricing premium *apenas* pela governance de routing e budgets.

ArkaOS já tem `pricing.py` com tabela por modelo. Falta o *router activo* que use essa tabela ao vivo.

### 3.3 Anthropic está a apertar — confirmação pública

- **Anthropic news (Maio 2026):** *"Higher usage limits for Claude and a compute deal with SpaceX"* — admissão pública de compute shortage.
- **Pasquale Pillitteri (Maio 13, 2026):** *"Anthropic raised Claude Code weekly limits by 50% through July 13 for Pro, Max, Team and Enterprise"* — subida temporária, com data de fim, indicando que o constraint estrutural permanece.
- **MindStudio (Anthropic Compute Shortage):** *"Why Claude Limits Are Getting Worse"* — narrativa de mercado a consolidar-se contra a Anthropic.
- **Anthropic Help Center:** *"Para gerir capacidade e assegurar fair access, a Anthropic pode limitar uso de outras formas — caps semanais e mensais, modelo e feature usage — à sua discrição."*

A leitura do Andre — *"as empresas vão começar a diminuir os limites das subscrições"* — não é especulação. Está documentada nas comunicações oficiais da Anthropic neste mês.

### 3.4 A janela é agora

Três janelas a fechar simultaneamente:
1. **Pre-LLM-router-commodification.** Hoje router solutions ainda têm pricing premium. Daqui a 18 meses, será commodity (igual ao que aconteceu com API gateways).
2. **Pre-Anthropic-aperto-pesado.** Cada constraint da Anthropic empurra utilizadores enterprise para alternativas. O custo de mudar de "Claude Code" para "ArkaOS Runtime que usa Claude por baixo" é mais baixo do que mudar de Anthropic para OpenAI.
3. **Pre-Hermes-saturation.** Hermes é open-source MIT da Nous Research, com Discord activo e GitHub trending. Cada semana que passa, Hermes acumula skills, integrações, e mind-share. A diferenciação do ArkaOS via *governance vertical de domínio* tem de ser visível **antes** de o Hermes virar "o agent OS default".

---

## 4. Análise competitiva detalhada

### 4.1 Hermes Agent (Nous Research) — perfil

| Dimensão | Hermes |
|---|---|
| Origem | Nous Research (mesmos da família de modelos Hermes/Nomos/Psyche) |
| Linguagem | Python |
| Licença | MIT |
| Posicionamento | *"Self-improving AI agent with built-in learning loop"* |
| Arquitectura central | `AIAgent` em `run_agent.py` — synchronous conversation loop com prompt builder, provider resolution, tool dispatch, compression, persistence |
| Providers suportados | 18+ via `runtime_provider.py`, com 3 API modes: `chat_completions`, `codex_responses`, `anthropic_messages` |
| Roteamento | Map `(provider, model)` → `(api_mode, api_key, base_url)`. Sem routing por task complexity — é o utilizador que escolhe |
| Tools | 70+ tools em ~28 toolsets, auto-registo via `tools/registry.py` |
| Terminal backends | 7 (local, Docker, SSH, Daytona, Modal, Singularity, Vercel Sandbox) |
| Messaging adapters | 20 (Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Mattermost, Email, SMS, DingTalk, Feishu, WeCom, BlueBubbles, QQBot, etc.) |
| Memória | SQLite + FTS5, MEMORY.md + USER.md, Honcho dialectic user modeling |
| Skills | Compatible com agentskills.io, agent auto-creates skills, self-improves, Skills Hub |
| Personality | `SOUL.md` (texto livre) |
| Cron | Built-in scheduler, jobs em JSON |
| ACP | VS Code / Zed / JetBrains via stdio/JSON-RPC |
| Sandboxing | 6 terminal backends, command approval (sudo-style), authorization |
| Multi-agent | `delegate_tool.py` — subagent spawning para parallel workstreams |
| Cost governance | **Ausente como produto vendável** — não há budget caps, dashboards, ou enforcement |
| Domain knowledge | **Ausente** — agnostic, "qualquer skill" |
| Behavioral DNA | **Ausente** — só `SOUL.md` livre |
| Quality gates | **Ausentes** — só `command approval` |

**O que Hermes faz brilhantemente:** persistência (corre num VPS $5/mês, hibernates idle), multi-platform reach (20+ messaging surfaces de uma vez), provider neutrality, self-improving skills.

**O que Hermes não cobre:** governance enterprise, domínio vertical, behavioral profiles estruturados, quality gates com veto absoluto.

### 4.2 OpenClaw — perfil

| Dimensão | OpenClaw |
|---|---|
| Origem | Equipa OpenClaw (independente, MIT) |
| Linguagem | Node.js (Node 24 recomendado, 22.19+ LTS) |
| Posicionamento | *"Multi-channel gateway for AI agents that runs on any OS"* — mas as docs mostram um runtime completo, não só gateway |
| Arquitectura central | Gateway daemon (long-lived) + clients (mac app, CLI, web admin) via WebSocket em `127.0.0.1:18789` + nodes (iOS/Android/headless) |
| Providers suportados | **50+** — Anthropic, OpenAI, Google, Groq, DeepSeek, Cerebras, Bedrock, OpenRouter, LiteLLM, vLLM, Ollama, LM Studio, Mistral, Moonshot, Qwen, xAI, Z.AI, Together, Fireworks, NVIDIA, etc. |
| Roteamento | Provider directory + model failover documented em `concepts/model-failover` |
| Tools | "ClawHub" — marketplace de capabilities |
| Terminal backends | Local-first via Gateway |
| Messaging adapters | Discord, Google Chat, iMessage, Matrix, Microsoft Teams, Signal, Slack, Telegram, WhatsApp, Zalo (built-in + bundled plugins) |
| Memória | Multiple engines: builtin, QMD, Honcho. Active memory, inferred commitments, dreaming, compaction |
| Skills | Sessions, multi-agent routing, parallel specialist lanes, delegate architecture |
| Personality | `SOUL.md` (mesmo conceito do Hermes) |
| Cron | Implícito via agent runtime |
| Pairing/Security | Device-based pairing, signed challenge nonces, Tailscale, TLS+pinning, allowlists |
| Special | Mobile nodes com Canvas, camera, screen.record, location.get; macOS app; Web Control UI |
| Cost governance | **Parcial** — model failover existe, budget caps não documentados |
| Domain knowledge | **Ausente** |
| Behavioral DNA | **Ausente** |
| Quality gates | **Ausentes** — só `command approval` style |
| Curiosidade | Tem um *"Claude Max API Proxy"* para usar credenciais de subscrição via API — exactamente o hack que muitos utilizadores ArkaOS fazem informalmente |

**O que OpenClaw faz brilhantemente:** breadth de providers (50+, mais que Hermes), Web Control UI, mobile nodes nativos, model failover.

**O que OpenClaw não cobre:** mesmo gap do Hermes — governance vertical, domain knowledge, behavioral DNA estruturado, quality gates absolutos.

### 4.3 Frameworks adjacentes (referência rápida)

| Framework | Posicionamento | Overlap com ArkaOS |
|---|---|---|
| LangGraph | Stateful agent workflows, graph-based | Workflow engine (overlap ~30%); sem domain knowledge |
| CrewAI | Multi-agent crews com roles | Roles (overlap ~40%); sem behavioral DNA estruturado, sem governance |
| AutoGen (Microsoft) | Multi-agent conversation patterns | Conversation patterns; sem cost gov, sem domain |
| Letta (ex-MemGPT) | Memory-first agents com state persistence | Memory layer overlap parcial |
| LiteLLM | Pure provider gateway | Apenas LLM routing — complementar, não competidor |
| OpenRouter | Provider aggregation com BYOK | Apenas LLM routing — complementar |
| Mastra | TS-first agent framework | Agnostic; novo |

**Leitura:** os frameworks adjacentes ocupam o espaço *technical agent framework*. Hermes e OpenClaw ocupam o espaço *agent OS*. ArkaOS ocupa um espaço que **ninguém ocupa**: *agent OS com governance vertical de domínio + behavioral DNA + Quality Gate*. É um quadrante vazio no mercado.

### 4.4 Matriz comparativa final

Legenda: 🟢 = mature/completo, 🟡 = parcial, 🔴 = ausente, ⚪ = não aplicável

| Capability | ArkaOS hoje | ArkaOS Runtime (proposto) | Hermes | OpenClaw | LangGraph | CrewAI |
|---|---|---|---|---|---|---|
| **Runtime layer** | | | | | | |
| Standalone execution loop | 🔴 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| BYOK multi-provider | 🟡 (4 providers) | 🟢 (15+) | 🟢 (18+) | 🟢 (50+) | 🟢 | 🟢 |
| Provider abstraction | 🟢 (Protocol) | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 |
| API modes (Anthropic + OpenAI + Codex) | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 |
| Model failover | 🟡 (chain) | 🟢 (active) | 🟢 | 🟢 | 🟡 | 🔴 |
| **Cost governance** | | | | | | |
| Cost telemetry per call | 🟢 | 🟢 | 🟡 | 🟡 | 🔴 | 🔴 |
| Budget caps (per task/workflow/project) | 🔴 (informational) | 🟢 (enforceable) | 🔴 | 🟡 | 🔴 | 🔴 |
| Smart routing per task complexity | 🔴 | 🟢 | 🔴 | 🔴 | 🔴 | 🔴 |
| Stop conditions / spend alerts | 🟡 (advisory) | 🟢 | 🔴 | 🟡 | 🔴 | 🔴 |
| Cost attribution per agent/dept | 🟡 | 🟢 | 🔴 | 🔴 | 🔴 | 🔴 |
| **Governance & domain** | | | | | | |
| Constitution com enforcement levels | 🟢 | 🟢 | 🔴 | 🔴 | 🔴 | 🔴 |
| Quality Gate com veto absoluto | 🟢 | 🟢 | 🔴 | 🔴 | 🔴 | 🔴 |
| 13-phase mandatory flow | 🟢 | 🟢 | 🔴 | 🔴 | 🔴 | 🔴 |
| 16 domain departments | 🟢 | 🟢 | 🔴 | 🔴 | 🔴 | 🔴 |
| Knowledge frameworks (Porter, AARRR, SOLID, etc.) | 🟢 | 🟢 | 🔴 | 🔴 | 🔴 | 🔴 |
| Behavioral DNA (DISC+Enneagram+OCEAN+MBTI) | 🟢 | 🟢 | 🔴 | 🔴 | 🔴 | 🔴 |
| The Forge (planning escalation) | 🟢 | 🟢 | 🔴 | 🔴 | 🔴 | 🔴 |
| Living Specs | 🟢 | 🟢 | 🔴 | 🔴 | 🔴 | 🔴 |
| **Memory & knowledge** | | | | | | |
| Persistent memory (SQLite+FTS) | 🟡 | 🟢 | 🟢 | 🟢 | 🟡 | 🟡 |
| Vault integration (Obsidian) | 🟢 | 🟢 | 🔴 | 🔴 | 🔴 | 🔴 |
| Local-only mode (Ollama+vec) | 🟡 | 🟢 | 🟡 | 🟢 | 🟡 | 🟡 |
| **Messaging & surfaces** | | | | | | |
| Telegram/Discord/Slack adapters | 🔴 | 🟡 (roadmap) | 🟢 | 🟢 | 🔴 | 🔴 |
| WhatsApp/Signal/iMessage | 🔴 | 🔴 | 🟢 | 🟢 | 🔴 | 🔴 |
| ACP (VS Code/Zed/JetBrains) | 🟡 | 🟢 | 🟢 | 🟡 | 🔴 | 🔴 |
| CLI standalone | 🟡 | 🟢 | 🟢 | 🟢 | ⚪ | ⚪ |
| Web Control UI | 🔴 | 🟡 (roadmap) | 🔴 | 🟢 | 🔴 | 🔴 |
| **Ecosystem** | | | | | | |
| Skill marketplace | 🟡 (plugins) | 🟢 | 🟢 (agentskills.io) | 🟢 (ClawHub) | 🔴 | 🔴 |
| MCP support | 🟢 | 🟢 | 🟢 | 🟡 | 🟡 | 🟡 |
| Cron / scheduled tasks | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🔴 |

**Leitura da matriz:**

1. O *quadrante vazio* de **Cost governance + Governance vertical** é literalmente exclusivo do ArkaOS Runtime proposto. Nenhum competidor sequer atinge 🟡 nas duas categorias simultaneamente.
2. O ArkaOS está **atrás** em: standalone runtime, breadth de providers, messaging adapters, Web Control UI. Tudo isto é construível em 3-9 meses por engenharia, não é defensável como moat alheio.
3. O ArkaOS está **à frente** em: governance, domain knowledge, behavioral DNA, Quality Gate, mandatory flow, vault integration. Tudo isto requer design organizacional e domain expertise, não só engenharia. *Não se constrói em 3 meses.*
4. A janela competitiva é: **fechar o gap horizontal antes que Hermes/OpenClaw acordem para o vertical**.

---

## 5. Posicionamento estratégico do ArkaOS Runtime

### 5.1 Frase de posicionamento (rascunho)

> *"ArkaOS Runtime is the agent operating system for teams that need agents to act like a real organisation — with departments, behavioral profiles, quality gates, and budget governance — not like a single LLM with tools attached. BYOK across 15+ providers. Smart routing per task. Constitution-enforced. Quality-gated."*

Versão curta (homepage hero): *"The Operating System for AI Agent Teams. BYOK. Governed. Audit-trailed."*

Versão PT (público nacional): *"O Sistema Operativo para Equipas de Agentes IA. Cada um com personalidade, departamento e accountability."*

### 5.2 Quadrante competitivo

```
                  alto governance vertical
                            │
                  ArkaOS    │
                  Runtime   │
                            │
agnostic ───────────────────┼─────────────────── domain-specialised
                            │
                  Hermes    │   (vazio
                  OpenClaw  │    explorável)
                  LangGraph │
                  CrewAI    │
                            │
                  baixo governance vertical
```

ArkaOS Runtime ocupa o quadrante superior-direito sozinho. Todo o mercado actual está no quadrante inferior. A entrada de competidores no quadrante superior-direito exige construir *behavioral DNA + 16 departments + Constitution + Quality Gate*, o que é trabalho de anos.

### 5.3 Narrative: três frases para repetir

1. **"O ArkaOS é o que acontece quando levas a sério a ideia de que agentes deviam comportar-se como uma empresa."** — captura governance + departments.
2. **"BYOK. Smart routing. Budget caps por workflow. Os teus tokens, controlados pelo teu cérebro de orquestração."** — captura cost governance.
3. **"Local-first, vault-integrated, multi-runtime. A tua memória nunca é SaaS."** — captura os três pilares do ADR 2026-05-13.

### 5.4 Não-objectivos (boundaries explícitas)

Para evitar diluição de posicionamento:

- **Não-objectivo 1:** Não competir em *breadth de messaging surfaces* com Hermes (20+ adapters). Manter foco em developer surfaces (CLI, ACP, Web UI). Telegram/Discord/Slack via MCP, não nativamente.
- **Não-objectivo 2:** Não competir em *self-improving skills loop* com Hermes. ArkaOS aprende via vault (Obsidian) — uma filosofia diferente. Não reproduzir o Hermes Skills Hub.
- **Não-objectivo 3:** Não competir em *mobile nodes nativos* com OpenClaw (iOS/Android com camera, screen.record). Pode vir depois — não está no domínio core.
- **Não-objectivo 4:** Não tornar-se LLM gateway puro. LiteLLM e OpenRouter fazem isso melhor. ArkaOS *usa* esses gateways como backends quando útil; não os substitui.

---

## 6. Arquitectura técnica do ArkaOS Runtime

### 6.1 Princípios arquitecturais

1. **Camada-de-cima preservada.** Constitution, departments, agents YAML, workflows, Forge, Living Specs, mandatory-flow — *zero* mudanças. Tudo o que está acima do runtime continua exactamente como está.
2. **Eixo invertido no provider layer.** Hoje: runtime decide modelo, ArkaOS delega. Pivot: ArkaOS Router decide modelo por `(agent_tier, phase_type, task_complexity, budget_remaining, provider_health)`, runtime *executa*.
3. **Runtimes ficam opcionais como backends.** Claude Code, Codex, Gemini, Cursor continuam suportados como `SubagentProvider`. Mas deixam de ser o caminho obrigatório.
4. **Modo standalone como primeira classe.** `arka run <workflow>` sem precisar de Claude Code aberto.
5. **Governance NON-NEGOTIABLE preservada.** O 13-phase corre seja qual for o backend. A diferença é que num modo standalone, *é o ArkaOS quem corre o loop*.
6. **Backward compatibility absoluta.** Quem usa ArkaOS dentro do Claude Code hoje, continua a usar igual. O pivot adiciona, não substitui.

### 6.2 Diagrama de blocos (alto nível)

```
┌──────────────────────────────────────────────────────────────────────┐
│  USER SURFACES                                                       │
│  CLI │ ACP (VS Code, Zed, JetBrains) │ Web Control UI │ MCP server  │
└──────────────────────────────────────┬───────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────┐
│  GOVERNANCE LAYER  (existing, untouched)                             │
│  ─────────────────────────────────────────────────────────────────  │
│  Constitution │ Quality Gate │ Mandatory 13-phase Flow │ Forge     │
│  Living Specs │ Synapse v2 (8-layer context)                       │
└──────────────────────────────────────┬───────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────┐
│  AGENT LAYER  (existing)                                            │
│  ─────────────────────────────────────────────────────────────────  │
│  56 agents × 16 departments × behavioral DNA × knowledge frameworks │
│  Workflows YAML │ Squads │ Subagent pattern                         │
└──────────────────────────────────────┬───────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────┐
│  EXECUTION LOOP  (NEW — standalone path)                            │
│  ─────────────────────────────────────────────────────────────────  │
│  arkaos_runtime.run(agent, prompt, tools)                           │
│   ├─ prompt builder (existing Synapse)                              │
│   ├─ MODEL ROUTER (NEW)                                             │
│   ├─ provider.complete(...) → tool calls → loop                     │
│   ├─ COST GOVERNOR (NEW — enforceable)                              │
│   └─ telemetry + audit trail                                        │
└──────────────────────────────────────┬───────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────┐
│  PROVIDER ABSTRACTION LAYER  (expanded from existing)               │
│  ─────────────────────────────────────────────────────────────────  │
│  3 API modes: anthropic_messages │ chat_completions │ codex_resp.  │
│                                                                      │
│  Direct providers:    Anthropic, OpenAI, Google, Groq, DeepSeek,    │
│                       xAI, Mistral, Cerebras, Moonshot              │
│  Meta-providers:      OpenRouter, LiteLLM, Vercel AI Gateway        │
│  Local providers:     Ollama (✓ existing), vLLM, LM Studio, SGLang  │
│  Runtime-delegating:  Claude Code, Codex CLI, Gemini CLI, Cursor    │
│                       (existing — preserved as Subagent backends)   │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.3 Componentes novos detalhados

#### 6.3.1 Model Router (NOVO)

```python
# core/runtime/model_router.py  (proposed)

@dataclass
class RoutingDecision:
    provider: str
    model: str
    estimated_cost_usd: float
    estimated_latency_ms: int
    reason: str  # human-readable: why this model

class ModelRouter:
    def route(
        self,
        *,
        agent_tier: int,           # 0=C-suite, 1=lead, 2=specialist, 3=mechanical
        phase_type: str,           # "research"|"plan"|"implement"|"qa"|"summary"
        task_complexity: str,      # "trivial"|"medium"|"complex"|"super"
        budget_remaining_usd: float,
        prefer_local: bool = False,
        provider_health: dict[str, ProviderHealth] = None,
    ) -> RoutingDecision: ...
```

Regras (declarativas em `config/routing-rules.yaml`):

```yaml
routing_rules:
  - match: { phase_type: "qa", quality_gate: true }
    use: { provider: "anthropic", model: "claude-opus-4-6" }
    rationale: "Quality Gate is NON-NEGOTIABLE Opus"

  - match: { agent_tier: 0 }
    use: { provider: "anthropic", model: "claude-opus-4-6" }
    fallback: { provider: "openai", model: "gpt-5" }

  - match: { agent_tier: 3, phase_type: "mechanical" }
    use: { provider: "groq", model: "llama-3.3-70b" }
    fallback: { provider: "ollama", model: "qwen2.5:14b" }

  - match: { task_complexity: "super" }
    use: { provider: "anthropic", model: "claude-opus-4-6" }

  - match: { budget_remaining_usd: "<1.00" }
    use: { provider: "ollama", model: "qwen2.5:14b" }
    rationale: "Budget low — downgrade to local"
```

**Princípio chave:** o `agent.yaml` continua a ter `model: sonnet` como *hint* (semantic tier), não como hard binding. O router resolve `sonnet` para um provider concreto baseado em disponibilidade, custo e saúde.

#### 6.3.2 Cost Governor (NOVO — versão enforceable)

```python
# core/runtime/cost_governor.py  (proposed)

@dataclass
class Budget:
    scope: str  # "task" | "workflow" | "session" | "day" | "project"
    cap_usd: float
    soft_limit_pct: float = 0.8  # warn at 80%
    on_exceed: str = "downgrade"  # "downgrade" | "block" | "ask" | "warn_only"

class CostGovernor:
    def can_spend(self, estimated_usd: float, *, scope: str) -> Decision: ...
    def record(self, actual_usd: float, *, scope: str) -> None: ...
    def downgrade_decision(self, current: RoutingDecision) -> RoutingDecision:
        """Find a cheaper model within the same family/tier when budget is tight."""
```

Configuração (em `~/.arkaos/config.json` ou `.arkaos.json` per project):

```json
{
  "budgets": {
    "task":     { "cap_usd": 0.50, "on_exceed": "downgrade" },
    "workflow": { "cap_usd": 5.00, "on_exceed": "ask" },
    "session":  { "cap_usd": 20.00, "on_exceed": "warn_only" },
    "day":      { "cap_usd": 50.00, "on_exceed": "block" },
    "project":  { "cap_usd": 500.00, "on_exceed": "block" }
  }
}
```

**Distinção crítica vs ADR-011:** o ADR-011 hoje diz "informational, not restrictive". O Cost Governor proposto é a versão *enforceable* — opt-in via config, sem quebrar quem prefere informational-only. ADR-011 não precisa de ser revogado, apenas estendido.

#### 6.3.3 Provider Abstraction Layer (expandido)

Hoje existe o `LLMProvider` Protocol com 4 providers. Expansão proposta:

| Provider | API mode | Novo? | Prioridade |
|---|---|---|---|
| Anthropic | `anthropic_messages` | existe (direct) | mantém |
| OpenAI | `chat_completions` | **NOVO** | alta — paridade com Hermes |
| OpenAI Responses (Codex) | `codex_responses` | **NOVO** | média |
| Google Gemini | `chat_completions` | **NOVO** | alta |
| Groq | `chat_completions` | **NOVO** | alta — para tier-3 mecânico |
| DeepSeek | `chat_completions` | **NOVO** | alta |
| xAI Grok | `chat_completions` | **NOVO** | baixa |
| Mistral | `chat_completions` | **NOVO** | baixa |
| OpenRouter | `chat_completions` | **NOVO** | alta — meta-provider crítico para BYOK |
| LiteLLM | gateway | **NOVO** | alta — meta-provider |
| Cerebras | `chat_completions` | **NOVO** | baixa |
| Ollama | local | existe | mantém |
| vLLM | local OpenAI-compat | **NOVO** | média |
| LM Studio | local OpenAI-compat | **NOVO** | baixa |
| Bedrock | AWS SDK | **NOVO** | baixa (enterprise) |
| Claude Code (subagent) | shell-out | existe | mantém |
| Codex CLI (subagent) | shell-out | existe | mantém |
| Gemini CLI (subagent) | shell-out | existe | mantém |
| Cursor (subagent) | shell-out | existe | mantém (sem headless) |

**Decisão arquitectural:** os providers directos vão para `core/runtime/providers/<name>.py`, um por ficheiro, auto-registo via `core/runtime/providers/registry.py` (mesmo padrão que o Hermes usa para tools).

#### 6.3.4 Execution Loop standalone (NOVO)

```python
# core/runtime/loop.py  (proposed)

class ArkaOSRuntime:
    def __init__(
        self,
        *,
        router: ModelRouter,
        governor: CostGovernor,
        synapse: SynapseV2,
        constitution: Constitution,
    ): ...

    async def run_agent(
        self,
        agent_id: str,
        prompt: str,
        *,
        workflow_phase: str | None = None,
        budget_scope: str = "task",
        tools: list[Tool] | None = None,
    ) -> AgentResponse:
        """
        1. Load agent YAML → behavioral DNA + tier
        2. Synapse builds system prompt (8 layers)
        3. Router resolves (provider, model) given tier+phase+complexity+budget
        4. Governor pre-checks budget
        5. Provider.complete() → tool calls → tool dispatch → loop
        6. Governor records actual cost
        7. Telemetry + audit trail
        """

    async def run_workflow(
        self,
        workflow_id: str,
        inputs: dict,
    ) -> WorkflowResult:
        """Run a full YAML workflow standalone — phases, gates, parallel."""

    async def run_flow(
        self,
        user_input: str,
    ) -> FlowResult:
        """Run the canonical 13-phase mandatory-flow end-to-end."""
```

**Hooks de observabilidade:** cada passo emite eventos para `~/.arkaos/runs/<run_id>/trace.jsonl` (modelo, tokens, custo, latência, decisão do router, tool calls). Esta trace é o audit trail que vende para enterprise.

#### 6.3.5 Backend adapters (Claude Code, Codex, Gemini, Cursor)

Continuam exactamente como estão hoje, mas passam a ser *uma das opções* do provider layer, não a obrigatória. Quando o user escolhe `--backend claude-code`, o ArkaOS Runtime delega ao Claude Code (via `claude -p`). Mas pode também escolher `--backend direct` (chamadas LLM directas) ou `--backend hybrid` (Claude Code para algumas phases, direct API para outras).

Caso de uso típico (hybrid):
- Phases 1-3 (input, context, routing): direct API (rapid, no overhead)
- Phases 4-6 (hierarchy, research, team): Claude Code (use subscription)
- Phase 11 Quality Gate: **direct API com Opus**, NON-NEGOTIABLE (não pode ficar refém de Claude Code limits)

#### 6.3.6 Web Control UI (mid-term, não core)

Inspirado no OpenClaw dashboard. Browser UI servido localmente em `127.0.0.1:18789` ou similar. Mostra:
- Runs activos com trace ao vivo
- Custos por workflow / projecto / dia / mês
- Histórico de routing decisions (com rationale)
- Configuração de providers (BYOK key entry)
- Configuração de budgets
- Vault Obsidian explorer

Mid-term — não bloqueia o pivot core.

### 6.4 Mudanças no Constitution / ADRs

O pivot exige actualizar 2 ADRs e criar 3 novos:

| ADR | Acção |
|---|---|
| `2026-04-20-llm-agnostic.md` | **Actualizar** — adicionar secção *"v2 (post-pivot): router activo, runtime delegation passa a ser uma opção dentro da chain, não o default principal"*. Não revogar — estender. |
| `2026-04-17-binding-flow-enforcement.md` | **Validar** — confirmar que `mandatory-flow` continua aplicável quando o runtime é standalone. |
| ADR novo `2026-XX-arkaos-runtime-pivot.md` | **Criar** — decisão estratégica deste documento. |
| ADR novo `2026-XX-model-router.md` | **Criar** — design do `ModelRouter`. |
| ADR novo `2026-XX-cost-governor.md` | **Criar** — design do `CostGovernor` enforceable, estendendo ADR-011 sem o revogar. |

### 6.5 O que NÃO muda (importante)

- Estrutura de departamentos.
- Agent YAMLs e behavioral DNA.
- Workflow engine YAML.
- Synapse v2 (8-layer context).
- Constitution rules existentes (apenas extensões).
- Forge.
- Living Specs.
- Knowledge base (16 frameworks).
- Quality Gate (Marta+Eduardo+Francisca).
- Vault/Obsidian integration.
- Local-first cognitive layer.
- Three-pillar differentiation vs Anthropic.
- ArkaOS dentro do Claude Code continua a funcionar 100% como hoje.

---

## 7. Modelo de negócio e GTM

### 7.1 ICP (Ideal Customer Profile)

Três segmentos, ordenados por densidade de valor:

**ICP-1: Solo operators e founders técnicos** (volume alto, ticket baixo, conversão rápida)
- Perfil: developers + product builders que correm 3-6 agents em paralelo, gastam $100-500/mês em LLM APIs, querem governance e cost control
- Dor: subscrições "ilimitadas" são throttled; APIs directas são caras sem routing; nenhum tooling decente para governance pessoal
- Willingness to pay: $20-50/mês por features de governance
- Aquisição: organic (blog, X/Twitter, GitHub trending, Discord communities)
- Volume potencial: milhares

**ICP-2: Equipas pequenas técnicas (2-15 pessoas)** (ticket médio, conversão deliberada)
- Perfil: startups Series A/B, agências dev, consultancies — equipas que correm agents partilhados, precisam attribution de custo por team member
- Dor: spend visibility é zero; cada developer escolhe modelo sem governance; quality varia agent-a-agent
- Willingness to pay: $50-200/seat/mês
- Aquisição: outbound founder-led + design partners + case studies
- Volume potencial: centenas

**ICP-3: Enterprise mid-market (50-500 pessoas)** (ticket alto, conversão longa, viabiliza ARR)
- Perfil: organizações que querem agent OS interno mas com BYOK (compliance, contratos DPA já assinados com Anthropic/OpenAI), audit trail, e governance vertical (HR, Finance, Engineering separados com policies próprias)
- Dor: compliance + cost runaway risk + auditability + departamentalização
- Willingness to pay: $5K-50K/mês (platform fee) + tokens BYOK
- Aquisição: founder-led sales, design partner program, partnerships com integrators
- Volume potencial: dezenas (primeiros 24 meses)

**Foco recomendado nos primeiros 6 meses:** ICP-2 com 5-10 design partners. ICP-1 é o funnel orgânico. ICP-3 é o sonho de receita mas requer SOC 2, on-prem deployment, e features enterprise que pesam o roadmap.

### 7.2 Open-Source vs Comercial

Decisão fundamental que requer input do Andre (§10). Análise das três opções:

**Opção A: 100% OSS, MIT (como Hermes e OpenClaw).**
- Pros: máxima adopção, comunidade auto-amplificável, alinhado com a ética do espaço
- Cons: monetização exige hosted offering (sem o qual não há receita), GTM mais lento, copy-cats sem fricção
- Modelo de receita: hosted multi-tenant SaaS + enterprise support contracts + consultancy
- Exemplo de referência: Letta, LangChain

**Opção B: Open-core (core OSS, enterprise features fechadas).**
- Pros: receita recorrente desde o início, OSS funnel para enterprise, comunidade existe mas com tetos claros
- Cons: tensão eterna entre "o que é OSS e o que não é", risk de comunidade hostil se a linha mexer
- Modelo de receita: enterprise license (multi-tenant governance, SSO, audit, on-prem)
- Exemplo de referência: GitLab, Sentry, n8n

**Opção C: Source-available (BSL/SSPL-like).**
- Pros: protecção contra cloud providers a re-hospedar, monetização clara
- Cons: comunidade descontente, fricção mental "isto é open ou não?"
- Exemplo de referência: MongoDB, Elastic

**Recomendação preliminar:** Opção B (open-core) com a linha desenhada assim:

| Camada | OSS (Apache 2.0 ou MIT) | Enterprise (licença comercial) |
|---|---|---|
| ArkaOS Runtime core (loop, provider abstraction, router) | ✓ | |
| Constitution, departments, agents, workflows | ✓ | |
| Cost Governor (single-user, single-project) | ✓ | |
| Cost Governor (multi-user, multi-project, dashboards) | | ✓ |
| ACP integration | ✓ | |
| Web Control UI (single-user) | ✓ | |
| Web Control UI (multi-tenant, SSO, RBAC) | | ✓ |
| Vault integration | ✓ | |
| Local-first cognitive layer | ✓ | |
| Quality Gate, Forge, Living Specs | ✓ | |
| Audit trail (local JSONL) | ✓ | |
| Audit trail (centralizado, SIEM-ready) | | ✓ |
| Compliance reports (SOC 2, ISO 27001) | | ✓ |
| On-prem deployment + support | | ✓ |
| Premium connectors (Salesforce, SAP, Workday) | | ✓ |

Esta linha é defensável: o core (o cérebro) é OSS. O *enterprise wrapper* (multi-tenant, compliance, premium connectors) é comercial. Igual ao GitLab/n8n.

### 7.3 Pricing tentativo (a validar com design partners)

**ArkaOS Cloud (hosted, SaaS):**
- Free tier: até 3 projects, até 5 agents activos, governance básica — $0
- Solo: $29/mês, projects ilimitados, todos os agents, full governance, BYOK
- Team: $49/seat/mês (min 3 seats), multi-user, attribution, dashboards
- Business: $99/seat/mês, SSO, audit centralizado, priority support
- Enterprise: custom, on-prem option, dedicated support, SLA

**ArkaOS Self-Hosted (OSS + Enterprise license):**
- Community (OSS): $0
- Enterprise license: $25K/ano up to 50 seats; $50K/ano up to 250 seats; custom acima
- Includes: enterprise features, support, SLA, priority bug fixes

**Notas:**
- Em todos os tiers, tokens são BYOK (não há margem em tokens). Receita = platform fee.
- Possibilidade de tier "Managed BYOK" onde ArkaOS opera as provider keys e marca-up (~5-10%) por simplicidade — mas é segundo passo.
- Pricing está em linha com benchmarks do espaço (CrewAI, Letta, LangSmith).

### 7.4 GTM nos primeiros 90 dias (pós-decisão de pivot)

| Semana | Acção |
|---|---|
| 1-2 | Documento estratégico aprovado, ADRs criados, branch `v3-runtime` aberto |
| 3-6 | MVP do Provider Abstraction layer expandido: OpenAI, Google, OpenRouter, Groq directos |
| 7-8 | MVP do Model Router com rules YAML |
| 9-10 | MVP do Cost Governor com budget caps enforceable |
| 11-12 | Execution loop standalone (`arka run` sem Claude Code aberto) |
| 6-8 (paralelo) | Recrutar 5 design partners ICP-2 — devem ser pagantes pré-MVP ($500/mês early-bird) |
| 10-12 (paralelo) | Landing page nova, narrative dos três pilares + cost governance, demo video |
| 12-13 | Launch alpha pública (Show HN, X/Twitter, Discord arkaos + nous + claude) |

### 7.5 Design partners — perfil para os primeiros 10

Procurar:
- Founders técnicos / CTOs / Heads of Engineering com equipa 5-20
- Já usam Claude Code / Cursor + têm dor real de cost runaway
- Têm 3+ agents/skills em uso recorrente
- Têm orçamento real para pagar early-bird ($500-$2000/mês para upgrades semanais)
- Estão dispostos a fazer feedback estruturado (call semanal de 30min)

Sources para encontrar:
- Comunidades: Anthropic Discord, AI Engineer Discord, Cursor Discord, GitHub Trending agent repos
- LinkedIn: outreach a "CTO" / "Head of Engineering" + "agent" / "ai" em bio
- X/Twitter: monitor de quem usa MCP, Claude Code, agents em produção
- Comunidade portuguesa: Web Summit alumni, Building Global PT, Founders PT

### 7.6 Posicionamento competitivo no GTM

Mensagem core a repetir em todos os surfaces:

> *"O Hermes ensina-te a correr um agente. O ArkaOS ensina os teus agentes a comportarem-se como uma empresa real — com Marta a vetar entregas que não cumprem standards, com a Helena a controlar o orçamento de tokens, e com o Paulo a fazer code review como se fosse uma engenharia sénior. BYOK, governed, audit-trailed. Não é um framework. É um sistema operativo."*

Anti-mensagens (não falar disto em GTM):
- "ArkaOS vs Hermes" head-to-head — perdemos no breadth, ganhamos no depth
- "ArkaOS é melhor que LangGraph" — categoria errada
- "ArkaOS é open-source 100%" — depende da decisão B (open-core)

---

## 8. Riscos e mitigations

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| **Anthropic ship governance layer** | Média | Alto | Differentiation pillars já definidos no ADR 2026-05-13 (local-only, vault, multi-runtime). Acrescentar: governance vertical de domínio. Anthropic não vai construir 16 departamentos com behavioral DNA. |
| **Hermes ou OpenClaw add Constitution-like governance** | Baixa-Média | Alto | Speed-to-market. Lançar pivot em 90-120 dias. Construir behavioral DNA visível como brand asset (página dedicada a "como cada agente pensa"). |
| **Provider rotativo: BYOK exige updates por cada novo modelo** | Alta | Médio | LiteLLM e OpenRouter como meta-providers absorvem o churn. Direct providers só para os top-5 (Anthropic, OpenAI, Google, Groq, DeepSeek). |
| **Cost Governor enforcement quebra workflows existentes** | Média | Alto | Default = `warn_only` (paridade com ADR-011). Enforcement opt-in. Modo "informational vs restrictive" como flag explícita. |
| **Migração do utilizador existente assusta** | Média | Médio | Modo "ArkaOS-in-Claude-Code" continua a funcionar identicamente. v3 não força nada. Pivot adiciona path standalone. |
| **Engenharia: re-escrever 50+ providers exausto** | Alta | Médio | Priorizar 5 directos + LiteLLM/OpenRouter como meta. Restantes via meta-providers. |
| **OSS vs comercial — escolha errada cementa-se** | Média | Alto | Decisão deliberada nesta sessão (§10). Reversível em 6 meses se sinal de mercado mudar. |
| **Confusão de mercado: "ArkaOS é o quê exactamente?"** | Alta | Médio | Narrative dos três pilares (vault, local, multi-runtime) + um quarto pilar (governance vertical). Página homepage com framing claro. |
| **Compute shortage da Anthropic intensifica e os utilizadores actuais saem** | Média | Alto (para os existentes) | Pivot acelerado — exactamente o cenário que o pivot resolve. Cada release que adia o pivot é exposição contínua. |
| **Andre individual-bottleneck no design e governance** | Alta | Alto | Cada decisão deste documento precisa de Andre. Sem framework de delegação, pivot bloqueia. Mitigação: design partners pagos pré-MVP — força ownership distribuída. |

---

## 9. Resumo das decisões já tomadas neste documento

(Recap antes da lista de open decisions.)

| # | Decisão | Justificação |
|---|---|---|
| 1 | Pivot é desejável | Mercado valida (BYOK standard, Anthropic apertando, smart routing como diferenciador) |
| 2 | Pivot preserva 100% da camada-de-cima | Moat está acima do runtime, não no runtime |
| 3 | ArkaOS Runtime é uma evolução, não substituição | Backward compatibility absoluta |
| 4 | Hermes não é competidor head-to-head em breadth | Foco em depth (governance vertical) |
| 5 | OpenClaw é competidor mais sério do que aparentava | Tem 50+ providers, model failover, multi-agent routing |
| 6 | Quadrante "governance vertical + cost governance" está vazio no mercado | Tese de posicionamento defensável |
| 7 | Web Control UI é mid-term, não bloqueia core | Prioridade para cost governance + runtime standalone |
| 8 | LiteLLM e OpenRouter como meta-providers absorvem provider churn | Reduz superficie de manutenção |
| 9 | ADR-011 estende-se, não se revoga | Telemetria informational continua a ser default; enforcement é opt-in |
| 10 | Backend adapters (Claude Code, etc.) continuam first-class | Modo híbrido suporta uso actual |

---

## 10. Decisões abertas (input do Andre necessário antes do roadmap)

Para avançar para a fase 3 (roadmap de migração faseada) com clareza, são necessárias **6 decisões estratégicas** do Andre:

### Decisão A — Licenciamento e modelo OSS/comercial

**Opções:**
- A1: 100% OSS (Apache 2.0 ou MIT), monetização via hosted SaaS
- A2: Open-core (recomendado neste documento) — core OSS, enterprise features fechadas
- A3: Source-available (BSL/SSPL), protege contra cloud re-hosting

**Implicação:** decide a linha entre código aberto e código pago, decide a narrativa de comunidade, decide a estratégia de receita primária.

---

### Decisão B — Primeiro segmento de receita

**Opções:**
- B1: ICP-1 (solo) primeiro — funnel orgânico, validação rápida, ticket baixo
- B2: ICP-2 (equipas pequenas) primeiro — design partners pagos pré-MVP, ticket médio
- B3: ICP-3 (enterprise) primeiro — long sales, ticket alto, mas exige SOC 2 + on-prem

**Implicação:** decide foco do produto MVP, decide o que é "feature" vs "feature enterprise", decide cadência de releases.

---

### Decisão C — Velocidade vs profundidade no provider layer

**Opções:**
- C1: Velocidade — apenas LiteLLM como meta-provider, sem providers directos. Cobre 50+ providers via LiteLLM imediatamente
- C2: Profundidade — 5 providers directos (Anthropic, OpenAI, Google, Groq, DeepSeek) + LiteLLM como fallback. Trade-off: melhor caching/optimization para top-5, dependência LiteLLM para restantes
- C3: Híbrido completo — 10 providers directos + LiteLLM + OpenRouter + Vercel Gateway. Trade-off: mais código, mais manutenção, mais controlo

**Implicação:** decide engenharia de provider abstraction nos primeiros 90 dias.

---

### Decisão D — Enforcement do Cost Governor

**Opções:**
- D1: Sempre informational (sem mudar ADR-011, sem enforcement)
- D2: Enforcement opt-in por config (recomendado neste documento)
- D3: Enforcement default-on com opt-out

**Implicação:** decide a UX de cost control, decide quanto risk de quebra de workflows existentes, decide o discurso de marketing ("governed by default" vs "governance opt-in").

---

### Decisão E — Web Control UI: timing

**Opções:**
- E1: Não construir Web UI no v3 — CLI + ACP + MCP server bastam
- E2: Construir Web UI single-user no v3 — base para a versão enterprise multi-tenant
- E3: Construir Web UI multi-tenant directamente — empurra cronograma 3-6 meses

**Implicação:** decide se ArkaOS tem dashboard visual nos primeiros 90 dias ou se é puramente CLI-first.

---

### Decisão F — Naming e marca

O nome "ArkaOS Runtime" é descritivo mas estranho. Opções:

- F1: "ArkaOS Runtime" — explícito mas longo
- F2: "ArkaOS v3" — versionado, deixa o "v3" carregar o pivot na narrativa
- F3: "ArkaOS Core" + "ArkaOS Cloud" — separa OSS de hosted
- F4: Novo nome para o runtime (ex: "Loom", "Pivot", "Hub") — separa narrativamente do legacy "ArkaOS"
- F5: Manter só "ArkaOS" sem suffix — o pivot é interno, externamente é a mesma marca

**Implicação:** decide como o mundo vê a transição, decide se há legacy/v2 vs novo, decide se "ArkaOS" tem variantes ou é monolítico no nome.

---

## 11. Próximos passos sugeridos

Assumindo aprovação geral da tese e este documento como ponto de partida:

1. **Andre responde §10 (decisões A–F)** — pode ser em conversa, num documento, ou em reunião dedicada (sugiro fazer com Tomas + Marco + Helena + Marta do Conclave, mesmo formato do ADR 2026-05-13).
2. **Criar ADR oficial** `2026-XX-arkaos-runtime-pivot.md` com as decisões cristalizadas.
3. **Avançar para fase 3** (roadmap de migração faseada — a opção 3 da pergunta inicial que o Andre não escolheu, mas que agora faz sentido depois das três primeiras estarem fechadas).
4. **Identificar e fazer outreach aos primeiros 5 design partners** (ICP-2) em paralelo com engenharia, *antes* de o MVP estar pronto. Pré-venda valida tese e financia roadmap.
5. **Publicar manifesto público** (blog post + X/Twitter thread) com a narrativa do quadrante vazio + os três pilares + cost governance. Aproveitar o momento de aperto da Anthropic.

---

## Anexo A — Referências externas

- [Hermes Agent Documentation](https://hermes-agent.nousresearch.com/docs/) — Nous Research
- [Hermes Architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture) — internals
- [OpenClaw Documentation](https://docs.openclaw.ai/) — overview
- [OpenClaw Gateway Architecture](https://docs.openclaw.ai/concepts/architecture) — WebSocket protocol
- [OpenClaw Provider Directory](https://docs.openclaw.ai/providers) — 50+ providers
- [Augment Code: BYOK for Enterprise Agent Rollouts](https://www.augmentcode.com/guides/byok-enterprise-agent-rollouts)
- [DataStudios: OpenRouter BYOK analysis](https://www.datastudios.org/post/openrouter-byok-provider-keys-cost-control-privacy-and-routing-flexibility-across-multi-provider)
- [Pristan: BYOK vs Managed AI cost comparison 2026](https://www.pristan.chat/blog/byok-vs-managed-ai-costs/)
- [ClawRouters: AI Token Costs 2026 — Smart Routing](https://www.clawrouters.com/blog/ai-token-costs-2026-smart-routing)
- [MaximAI: Top 5 LLM Router Solutions 2026](https://www.getmaxim.ai/articles/top-5-llm-router-solutions-in-2026/)
- [Anthropic news: Higher limits + SpaceX compute deal](https://www.anthropic.com/news/higher-limits-spacex)
- [Pasquale Pillitteri: Claude Code +50% weekly limits May 2026](https://pasqualepillitteri.it/en/news/2494/claude-code-weekly-limits-50-percent-anti-codex-anthropic-2026)
- [MindStudio: Anthropic Compute Shortage](https://www.mindstudio.ai/blog/anthropic-compute-shortage-claude-limits)

## Anexo B — Referências internas

- `docs/adr/2026-04-20-llm-agnostic.md` — LLM Agnostic Auto-Documentor (precursor do pivot)
- `docs/adr/2026-05-13-differentiation-vs-anthropic-memory.md` — três pilares de diferenciação
- `docs/adr/2026-05-13-cognitive-layer-pivot-to-hooks.md` — north-star do local personal AGI
- `docs/adr/2026-04-17-binding-flow-enforcement.md` — flow enforcement (preserva-se)
- `core/runtime/llm_provider.py` — Protocol existente
- `core/runtime/llm_cost_telemetry.py` — telemetria existente
- `core/runtime/pricing.py` — pricing table existente
- `core/runtime/{claude_code,codex_cli,gemini_cli,cursor}.py` — adapters existentes
- `config/constitution.yaml` — Constitution v2
- `~/.arkaos/plans/` — onde irá o plano aprovado

---

*Documento aberto para discussão. Versão 0.1 — 2026-05-27. Próxima revisão: após decisões §10.*

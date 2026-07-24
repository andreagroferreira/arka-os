---
id: STRAT-2026-07-24-fase3-roadmap
title: "Fase 3 — Roadmap de 90 dias: do runtime shipped à primeira receita"
status: accepted — aprovado pelo operador 2026-07-24; gate dia-60 (≥2 partners, vs os 3 do critério interim do SWOT) ratificado conscientemente na mesma decisão
date: 2026-07-24
author: Tomas (Strategy), com re-baseline técnico de Marco (CTO)
related:
  - docs/adr/2026-07-19-arkaos-runtime-pivot.md
  - docs/strategy/2026-05-27-arkaos-runtime-strategy.md
  - docs/strategy/2026-05-27-arkaos-runtime-swot-viability.md
  - docs/adr/2026-07-04-cost-governor.md
---

# Fase 3 — Roadmap de 90 dias: do runtime shipped à primeira receita

## 1. O que este documento é

A execução das três consequências do ADR do pivot (2026-07-19): roadmap
de migração com o ICP-2 a mandar no corte do MVP, recrutamento de 5
design partners pagos, e manifesto público. Janela: **2026-07-27 a
2026-10-25 (13 semanas)**.

Não reabre nenhuma decisão A–F. Qualquer alteração a essas decisões
passa por novo ADR.

## 2. Assunções e gates

### 2.1 Assunção estrutural: solo-founder

Este roadmap assume **execução solo** (SWOT W1/W2: severidade 9,
peso 5). Não há evidência de movimento no bottleneck 1 (co-founder ou
contratação) desde maio. Consequências práticas:

- **Uma frente primária por semana.** Tracks paralelas existem no papel;
  na prática cada semana tem UMA entrega dominante e timeboxes fixos
  para o resto.
- **Corte de MVP agressivo** — tudo o que não é vendável ao ICP-2 nos
  próximos 90 dias é não-objetivo (ver §7).
- **Checkpoint ao dia 60:** se existir sinal de receita (≥2 partners
  pagos), a decisão de contratação reabre com justificação de receita —
  deixa de ser aposta, passa a ser reinvestimento.

Assunção **revisável**: se o operador fechar co-founder/contratação, o
corte re-abre num addendum a este documento.

### 2.2 Estado real dos 3 bottlenecks do SWOT (advance-only-if)

| # | Bottleneck (SWOT §10.2) | Estado 2026-07-24 |
|---|---|---|
| 1 | Co-founder técnico OU contratação | **ABERTO** — sem movimento registado; mitigado por scope discipline (§2.1) e checkpoint dia 60 |
| 2 | Design partners pagos pré-MVP | **ABERTO** — é a Track B deste roadmap; nenhuma conversa iniciada |
| 3 | GitHub público com comunidade | **PARCIAL** — o repo está público e recebe PRs externos reais (contribuidor Windows recorrente, dependabot, até spam-PRs — sinal involuntário de visibilidade). Falta a camada *ativa*: Discord, discussões, contributors regulares. Track C fecha o resto |

O veredicto do SWOT mantém-se em vigor: sem os bottlenecks fechados,
alta probabilidade de o projeto "virar ferramenta interna sem virar
produto". Este roadmap é a máquina de os fechar — com critérios de
paragem explícitos (§6).

## 3. Re-baseline: o §7.4 de maio contra a v4.38.0 de hoje

A descoberta central desta fase: **o plano de 90 dias de maio está ~70%
executado no produto — e 0% executado no GTM.** A restrição mudou de
sítio.

| §7.4 (maio) previa | Estado v4.38.0 (2026-07-24) |
|---|---|
| Semanas 3-6: Provider Abstraction (OpenAI, Google, OpenRouter, Groq diretos) | ✅ Resolvido por C1-refined: gateway LiteLLM (meta-provider, 50+ upstreams) + path Anthropic direto mantido; modos mixed e local-only shipped |
| Semanas 7-8: Model Router com rules YAML | ✅ Model Fabric (`~/.arkaos/models.yaml`, 7 roles, dashboard + CLI) + routing por tipo de trabalho |
| Semanas 9-10: Cost Governor enforceable | ✅ Shipped opt-in (ADR 2026-07-04, ratificado D2) + telemetria de custos por sessão (`llm_cost_telemetry`) |
| Web UI | ✅ Pulse dashboard single-user (E2, QG-passed 2026-07-11) |
| — (não previsto) | ✅ Multi-runtime a 6 runtimes com bundles compilados; OpenCode first-class com plugin de governance; auto-update daemon; menu bar; installer com perfis |
| Semanas 11-12: **`arka run` standalone** (execution loop sem host) | ❌ **Gap central de produto** — ArkaOS ainda exige um runtime host |
| — (dor nº1 do ICP-2) | ❌ **Attribution de custo por seat** — telemetria existe por sessão, não por pessoa |
| Semanas 6-8: 5 design partners pagos | ❌ Zero conversas |
| Semanas 10-12: landing nova, narrative, demo video | ❌ Zero execução |
| Semanas 12-13: launch alpha pública | ❌ Não aplicável ainda |

**Implicação estratégica:** em maio, recrutar partners exigia esperar
pelo MVP. Hoje a demo já existe — governance real em 6 runtimes, cost
telemetry, model fabric, dashboard. O recrutamento pode começar na
semana 1, não na semana 6. Os 90 dias invertem-se: **GTM-heavy com
produto dirigido pela venda**, não o contrário.

## 4. Corte do MVP — o ICP-2 manda (decisão B2)

Dores do ICP-2 (§7.1 da estratégia) mapeadas ao que falta construir:

| Dor ICP-2 | O que já responde (v4.38.0) | O que falta (MVP fase 3) |
|---|---|---|
| "Spend visibility é zero" | Telemetria de custos + dashboard single-user | **Attribution por seat** — `ARKA_SEAT` / identidade por operador na telemetria, agregação por pessoa no Pulse |
| "Cada developer escolhe modelo sem governance" | Model Fabric + gateway (routing físico) | **Governance defaults de equipa** — um `models.yaml` de equipa versionável + policy de override |
| "Quality varia agent-a-agent" | Quality Gate, constitution, behavioral DNA | Nada novo — é o pitch, já existe. Empacotar em demo |
| Dependência do host (Claude Code aberto) | Headless completions (OpenCode, Gemini) já live-verified | **`arka run` MVP** — loop standalone sobre o gateway BYOK, escopo mínimo: executar um workflow YAML com dispatch de agents e QG |

**Fora do MVP** (não-objetivos §7): multi-tenant, SSO/RBAC, audit
centralizado SIEM, compliance reports, providers diretos adicionais
(C1: só com ganho medido), ICP-3.

A linha open-core (A2) mantém-se: attribution multi-user e dashboards
de equipa são camada enterprise — exatamente o que os design partners
pagam para ter primeiro.

## 5. Roadmap 13 semanas — 3 tracks, sequenciamento solo

Cadência solo-founder: **cada semana tem UMA entrega dominante**;
Track B leva um timebox fixo de 4h/semana a partir da semana 1 (outbound
não pode esperar pelo produto — é a lição do re-baseline); Track C
concentra-se em janelas curtas.

| Sem. | Datas | Entrega dominante | Track |
|---|---|---|---|
| 1 | 07-27 → 08-02 | **Materiais de venda**: one-pager ICP-2, pricing early-bird ($500/mês), guião de demo sobre a v4.38.0 real; lista de 30 alvos qualificados (fontes §7.5) | B |
| 2 | 08-03 → 08-09 | **Manifesto público** (draft → QG → publicado no repo + site) — abre a Track C cedo porque alimenta o outbound da B | C |
| 3 | 08-10 → 08-16 | Outbound wave 1 (15 contactos founder-led) + demo calls; produto só em bugfix | B |
| 4-5 | 08-17 → 08-30 | **`arka run` MVP** — spec + loop mínimo (workflow YAML → dispatch → QG, sobre gateway BYOK, headless) | A |
| 6 | 08-31 → 09-06 | Outbound wave 2 (15 contactos) com `arka run` na demo; **checkpoint dia ~40**: ≥10 conversas qualificadas? | B |
| 7-8 | 09-07 → 09-20 | **Cost attribution por seat** — identidade de operador na telemetria + vista por pessoa no Pulse (camada partner/enterprise) | A |
| 9 | 09-21 → 09-27 | **Checkpoint dia 60**: ≥2 partners pagos? → decisão de contratação reabre; senão, diagnóstico honesto das objeções e correção de pitch/preço | B |
| 10-11 | 09-28 → 10-11 | **Governance defaults de equipa** (models.yaml partilhado + policy) — construído COM os partners ativos, feedback semanal §7.5 | A |
| 12 | 10-12 → 10-18 | Landing refresh: narrative 3 pilares + cost governance + manifesto; demo video | C |
| 13 | 10-19 → 10-25 | **Dia 90**: 5 partners pagos? → launch alpha pública (Show HN, X, Discords); senão → §6 | B/C |

Regra de proteção do roadmap: as semanas de produto (4-5, 7-8, 10-11)
não são interrompíveis por features fora do corte §4 — pedidos de
partners entram no backlog da semana seguinte de produto, nunca
inline (mitigação do risco "individual-bottleneck", §8 da estratégia).

## 6. Métricas e critérios de paragem (herdados do SWOT, agora com datas)

| Dia | Gate | Falhou → |
|---|---|---|
| ~40 (sem. 6) | ≥10 conversas qualificadas ICP-2 | Rever fontes de outbound e mensagem; Track C acelera (comunidade como funnel) |
| 60 (sem. 9) | ≥2 design partners **pagos** | Diagnóstico estruturado das objeções; ajustar pricing/oferta; NÃO adicionar features fora do corte por pânico |
| 90 (sem. 13) | 5 partners pagos ($2.5K MRR) | **Conversa honesta de continuação**: o SWOT dava 38% a >$10K MRR em 18 meses *condicionado a isto*. Sem nenhum pagante em 90 dias de outbound real, o cenário "ferramenta interna excelente" deixa de ser risco e passa a ser o resultado provável — e deve ser decidido conscientemente, não por deriva |

O que estes gates NÃO são: razão para baixar qualidade, saltar QG, ou
inflacionar o produto. São o instrumento de honestidade que o SWOT
exigiu.

## 7. Não-objetivos da fase 3

- ICP-3 / enterprise (SOC 2, on-prem, SSO, RBAC, SIEM) — fase 4+, só
  com receita ICP-2 a validar
- Providers diretos além do path Anthropic existente (C1: só com ganho
  de caching/latência **medido**)
- Multi-tenant Web UI (E2 ratificou single-user)
- Rebrand ou sub-marcas (F5: "ArkaOS", ponto)
- Hosted SaaS — a linha A2 monetiza enterprise self-hosted primeiro;
  hosted é decisão futura com o split F3 disponível

## 8. Riscos específicos desta fase

| Risco | Mitigação |
|---|---|
| Outbound solo consome a energia de engenharia (context-switching) | Timebox rígido 4h/sem + semanas de produto protegidas (§5) |
| Partners pedem features enterprise fora do corte | Linha A2 escrita no contrato early-bird: o que é OSS, o que é partner-only, o que não existe ainda |
| `arka run` MVP derrapa (é a peça técnica mais funda) | Escopo mínimo escrito em spec ANTES (arka-dev-spec, semana 4); tudo o que não é loop+dispatch+QG corta |
| Zero conversões apesar de demo forte | Gate dia 60 força diagnóstico de preço/mensagem cedo, com 30 dias de margem para corrigir |
| Burnout (T12, composto com W1) | O roadmap tem UMA entrega/semana por design; falhar uma semana desliza o plano, não o comprime |

## 9. Primeira ação

Segunda-feira 2026-07-27, semana 1: one-pager ICP-2 + pricing
early-bird + lista de 30 alvos. O produto já está pronto para vender —
está provado desde o re-baseline. O que os 90 dias testam é se alguém
paga. Tudo o resto é decoração.

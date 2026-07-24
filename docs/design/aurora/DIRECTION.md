# Aurora — Brand Direction da ArkaOS APP

> Fase 0 da campanha "ArkaOS APP". Direção validada pelo operador em
> 2026-07-24 sobre o protótipo `prototype-mission-control.html`
> (sha256 `9d81c9f1151b59a1…`). Este documento é a fonte de verdade da
> Fase 2 (implementação dos tokens no novo frontend); o
> `dashboard/DESIGN-SYSTEM.md` v1 fica obsoleto quando a Fase 2 arrancar.

## 1. Decisões (operador, brainstorm de 2026-07-24)

| Dimensão | Decisão |
|---|---|
| Direção | **Aurora** — evolução, não página em branco |
| Base | Indigo-carbon profundo (as inspirações sci-fi), nunca preto puro nem slate default |
| Cor de assinatura | Verde `#00FF88` mantém a equity — papel **estritamente** "vida" |
| 2ª voz | Violeta — "mente": IA, insights, fila, segunda série de dados |
| Logo | **The Levitation F6 mantém** (símbolo + barra flutuante); refinamento geométrico permitido, substituição não |
| Tipografia | **Sem serifas.** Geist (UI/display) + JetBrains Mono (dados) |
| Organização | ClickUp-like: rail de ícones + painel contextual, view tabs, grupos colapsáveis |
| Benchmarks | Disciplina **Linear** · organização **ClickUp** · alma **JARVIS** (funcional, nunca cenário) |

## 2. Tokens Aurora v2

### Cor — superfícies e texto

| Token | Valor | Papel |
|---|---|---|
| `void` | `#0B0D16` | Fundo raiz (indigo-black) |
| `panel` | `#0F121D` | Rail + painel lateral |
| `surface` | `#141827` | Cartões |
| `surface-2` | `#181D30` | Hover / elevado |
| `line` | `#20263C` | Bordas |
| `line-soft` | `#181D2E` | Divisores |
| `text` | `#E9EBF5` | Texto primário |
| `text-2` | `#9AA1BD` | Secundário |
| `text-3` | `#5D6480` | Mudo / labels |

### Cor — semântica

| Token | Valor | Papel |
|---|---|---|
| `signal` | `#00FF88` | **VIDA** — ver regra §3 |
| `signal-dim` | `rgba(0,255,136,.14)` | Fundos de estado vivo |
| `signal-glow` | `rgba(0,255,136,.35)` | Glow (só elementos vivos) |
| `mind` | `#8B87F9` | **MENTE** — IA, fila, insights, dataviz série 2 |
| `mind-dim` | `rgba(139,135,249,.14)` | Fundos mind |
| `warn` | `#FFB454` | Aviso |
| `alert` | `#FF5C77` | Erro / destrutivo |
| `info` | `#4CC2FF` | Informativo / dataviz série 3 |

### Tipografia

| Papel | Fonte | Pesos | Notas |
|---|---|---|---|
| UI + display | **Geist** | 400 / 500 / 600 / 700 | Headings com `letter-spacing:-.02em`; nunca serif |
| Dados | **JetBrains Mono** | 400 / 500 / 600 | SEMPRE `tabular-nums` em métricas, custos, tempos |

Escala: 11 · 12.5 · 14 (base) · 16 · 18 · 22 · 26. Body ≥ 14px; labels
uppercase a 10.5px com `letter-spacing:.07em` são a única exceção.

### Forma e profundidade

Radii: 6 / 10 / 14. Elevação por **cor de superfície + borda**, nunca por
sombras pesadas. Glow é reservado (§3).

### Motion

| Token | Valor |
|---|---|
| Duração micro | 150–250ms (`--dur: 180ms`) |
| Easing | `cubic-bezier(.22,.7,.35,1)` — ease-out a entrar; saídas ~65% da duração |
| Entrada de listas | Stagger 40ms/item, `translateY(8px)→0` |
| Pulse | **Só** em elementos genuinamente vivos (agent a correr, sistema live) |
| `prefers-reduced-motion` | Desliga TODA a animação ambiente — obrigatório |

## 3. A regra que governa tudo: verde é vida, violeta é mente

**`signal` (verde) pode aparecer APENAS em:**
1. Agents/processos **a correr agora** (dot pulsante, stream, linha da constelação)
2. A ação primária do ecrã (um único CTA)
3. Estado de saúde do sistema ("all systems live", crédito disponível)
4. Sucesso confirmado (exit 0, APPROVED, deltas positivos)

**`mind` (violeta) pode aparecer APENAS em:**
1. Trabalho em fila / agendado
2. Superfícies de inteligência (insights, Dreaming, cognition)
3. Segunda série em gráficos; avatares neutros

**Tudo o resto é neutro.** Se um ecrã tem verde em mais de ~5% da área,
está errado. O erro do Pulse v1 — tudo brilha, nada significa — é o
anti-pattern nº 1 desta marca.

## 4. Anti-patterns (bloqueiam QG)

- Glow decorativo em elementos não-vivos
- Serifas em qualquer superfície da APP
- Emoji como ícone (SVG stroke 1.75 consistente — família única)
- Slate/`#0F172A` + Inter (o default de todas as apps AI)
- Preto puro `#000` como fundo
- Verde e violeta misturados no mesmo elemento
- Animação > 400ms ou sem guarda reduced-motion
- Numerais proporcionais em dados (sempre tabulares)

## 5. Organização (herda do protótipo)

Rail 56px (ícones, logo no topo, definições no fundo) → painel 236px
(workspace, pesquisa ⌘K, grupos WORKSPACE/RECURSOS, **medidor Agent SDK
credit sempre visível**, perfil) → main (breadcrumb + view tabs + ações;
conteúdo em grid 12 col, máx 1240px). Listas operacionais em grupos
colapsáveis com pills de estado (A CORRER / NA FILA / CONCLUÍDO).

## 6. Assinatura

**A constelação viva** — o mapa dos 89 agents por departamento onde a
atividade real acende os nós: verde pulsante a trabalhar, violeta em
fila, neutro adormecido. É o único elemento com licença para espetáculo,
e só porque cada fotão transporta informação verdadeira.

## 7. Próximos consumidores

- **Fase 1** (spec/arquitetura): herda a organização §5 como requisito de IA
- **Fase 2** (fundação frontend): implementa §2–§6 como tokens CSS/Tailwind
  do novo shell; substitui `dashboard/DESIGN-SYSTEM.md`
- **QG/frontend gate**: §4 é a checklist de rejeição visual

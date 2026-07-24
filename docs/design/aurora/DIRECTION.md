# Aurora v4 — Brand Direction da ArkaOS APP

> Fase 0 da campanha "ArkaOS APP". Direção validada pelo operador em
> 2026-07-24 após 4 iterações visuais sobre 18 referências fornecidas
> ("agora sim estamos no caminho certo"). Protótipo canónico:
> `prototype-mission-control.html` (sha256 `2fdbfa854a60f9d9…`).
> Este documento é a fonte de verdade da implementação Nuxt (página a
> página, com confirmação do operador por página); substitui o
> `dashboard/DESIGN-SYSTEM.md` v1 e as revisões v1-v3 desta direção.

## 1. Decisões (operador, sessões de 2026-07-24)

| Dimensão | Decisão |
|---|---|
| Base | **Preto verdadeiro** com superfícies grafite neutras — zero azul, zero navy, zero slate |
| Voz primária | **Gradiente magenta→violeta** (`#FF4D9A → #8B5CF6`) — energia, ação, vida |
| Verde | Despromovido a **acento de sucesso/saúde** (`#2EE6A8`); a era "verde é vida" termina |
| Logo | Forma **Levitation F6 mantém**; na APP rende em gradiente rosa→violeta (aplicações externas: rever no brandbook) |
| Tipografia | **Geist** (UI) + **JetBrains Mono** (dados, tabular) — sem serifas, decisão explícita |
| Forma | Raios grandes (12/20px), **pills** (nav, tabs, botões, tags), chips circulares |
| Organização | ClickUp-like: rail + painel contextual + view tabs + grupos colapsáveis |
| Assinaturas | **Agent Orbit** (quem trabalha agora) + **Knowledge Galaxy** (o vault vivo) — duas irmãs, mesma linguagem |
| Motion | **GSAP** é a lib oficial de glue motion |
| Cadência | Implementação Nuxt **página a página**; operador confirma antes da seguinte |

Referências-mestre (18 imagens, sessão 2026-07-24): dashboards
Rezonate-style (preto + rosa/violeta, pills, segmented bars, gauges),
XSIAM Command Center (streams de luz para o núcleo), radiais orbitais de
partículas, coleções Dataism/Neurones (dendrites de dados), e o graph
real do Obsidian do operador (4131 notas) como base da Knowledge Galaxy.

## 2. Tokens Aurora v4

### Superfícies e texto

| Token | Valor | Papel |
|---|---|---|
| `void` | `#0A0A0C` | Fundo raiz — preto verdadeiro |
| `panel` | `#0E0E11` | Rail + painel lateral |
| `surface` | `#131316` | Cartões |
| `surface-2` | `#18181C` | Hover / elevado |
| `line` | `#26262C` | Bordas |
| `line-soft` | `#1C1C21` | Divisores |
| `text` | `#F2F2F6` | Primário |
| `text-2` | `#A2A2AC` | Secundário |
| `text-3` | `#67676F` | Mudo / labels |

### Cor semântica

| Token | Valor | Papel |
|---|---|---|
| `pink` | `#FF4D9A` | Polo quente do gradiente; live/ativo |
| `violet` | `#8B5CF6` | Polo frio; fila, sessão, contexto |
| `grad` | `linear-gradient(90deg, #FF4D9A, #8B5CF6)` | **A voz da marca** — ver §3 |
| `blue-v` | `#6E8BFF` | Terceira série de dataviz (só dados) |
| `ok` | `#2EE6A8` | Sucesso, saúde do sistema, poupança, concluído |
| `warn` | `#FFB454` | Aviso |
| `alert` | `#FF5C77` | Erro / destrutivo |
| `*-dim` | alpha `.13-.14` | Fundos de estado |
| `*-glow` | alpha `.40-.45` | Glow — só em elementos vivos |

### Tipografia e forma

Geist 400/500/600/700; headings `letter-spacing:-.02em`. JetBrains Mono
com `tabular-nums` OBRIGATÓRIO em métricas/custos/tempos. Escala: 10.5
(labels uppercase `.08em`) · 12.5 · 14 base · 15 · 24 · 28. Radii:
12 (`r-md`) / 20 (`r-lg`) / 999 (`r-pill`). Elevação por cor+borda;
sombras só em overlays (tooltips, popovers).

### Motion (GSAP oficial)

| Token | Valor |
|---|---|
| Micro | 150–250ms, `cubic-bezier(.22,.7,.35,1)` |
| Entrada de página | Orquestrada: stagger 70-80ms, `y:16→0`, power3.out |
| Count-ups | 1.1-1.2s power2.out sobre mono tabular (zero layout shift) |
| Magnetic | Botões/rail seguem cursor ±25% (quickTo .3s power3) |
| Lift | Cartões `y:-2` no hover |
| Spotlight | Borda gradiente radial a seguir o cursor nos cartões |
| Pulse/glow | SÓ em elementos genuinamente vivos |
| `prefers-reduced-motion` | Mata TODA a animação ambiente — obrigatório |

## 3. A regra do gradiente

O gradiente magenta→violeta é a assinatura sonora da marca. Pode aparecer em:

1. **Marca**: logo na APP, wordmark, badge de workspace (tinta subtil)
2. **Ação primária**: o único CTA primário do ecrã (pill gradiente)
3. **Vida**: agents ativos (avatares, dots, streams, anéis de pulso),
   texto de streaming
4. **Marcadores finos**: seleção de navegação (barra 3px), ponta de
   progresso, ponto final de gráfico
5. **Dataviz**: linha/área principal (com bloom), barras segmentadas de
   consumo

**Proibido:** gradiente em fundos de cartões ou superfícies grandes,
em texto de corpo, em bordas estáticas permanentes, em ícones neutros.
Estrutura é neutra; energia é gradiente; se tudo tem energia, nada tem.

**Verde `ok`:** sucesso confirmado (exit 0, APPROVED, poupança), saúde
("all systems live"), concluído. Nunca como acento de marca.

**Foco de teclado:** `pink` sólido (contraste a11y) — carve-out único.

## 4. Anti-patterns (bloqueiam QG)

- Azul/navy/slate em superfícies (o assassino das revisões v1-v3)
- Verde como voz de marca (era anterior)
- Gradiente em superfícies grandes ou texto de corpo
- Glow decorativo em elementos não-vivos
- Serifas; emoji como ícone; ícones de famílias misturadas (stroke 1.75 única)
- Preto puro `#000`; sombras pesadas em cartões
- Numerais proporcionais em dados
- Animação >400ms, sem stagger, ou sem guarda reduced-motion
- Canvas sem DPR (retina obrigatório, cap 2×)

## 5. Organização (ClickUp-like)

Rail 60px (logo em tile 12px, ícones pill 40px, definições no fundo) →
painel 236px (workspace badge, pesquisa pill ⌘K, grupos WORKSPACE /
RECURSOS com contadores, **medidor Agent SDK credit em barra segmentada
sempre visível**, perfil com avatar gradiente) → main (topbar 58px:
breadcrumb + view tabs em pill container + ações; conteúdo grid 12 col,
gap 16, máx 1320px). Listas operacionais em grupos colapsáveis com
status pills com dot (`● A CORRER` rosa · `● NA FILA` violeta ·
`● CONCLUÍDO` verde).

## 6. As assinaturas

**Agent Orbit** (Mission Control): núcleo com bloom gradiente + anel a
respirar, órbitas pontilhadas por departamento, agents como partículas
orbitantes; ativos em rosa com glow e **streams de luz com partículas a
fluir para o core**; fila violeta; idle neutro; hover → tooltip com a
task real; labels de departamento em mono 9px.

**Knowledge Galaxy** (/knowledge): o graph REAL do vault (Graphify é a
fonte) como galáxia — massa central + clusters + arco, milhares de
notas; base monocromática com vida por cima: **rosa = citada agora,
violeta = ligada à sessão, verde = escrita hoje**, hubs maiores com
título; respiração global + rotação subtil + parallax; contadores reais
no rodapé. Implementação real: WebGL (Cosmograph ou Sigma.js — decisão
na spec da página; canvas 2D com sprites só aguenta ~3k nós).

## 7. Consumidores e cadência

- **Implementação Nuxt página a página** (ordem proposta: Mission
  Control+shell → Live Ops → Agents → Knowledge → Scheduler →
  Providers/Perfis → restantes). Cada página: branch → implementação →
  QG com screenshots vs protótipo → **confirmação do operador** → merge
  → página seguinte.
- A primeira página implementa também a fundação: tokens CSS, shell
  (rail+painel+topbar), setup GSAP, padrão de data-fetching correto
  (root-cause do bug do refresh da app antiga).
- Este doc + protótipo são o contrato de QG visual; §4 é a checklist de
  rejeição.

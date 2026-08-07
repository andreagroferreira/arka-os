# Strategy

← [Departments index](README.md) · [Home](../Home.md)

> **Prefix:** `/strat` · **Lead:** Tomas (Tier 1) · **Agents:** 4 · **Skills:** 12

The Strategy department handles competitive analysis, business model design, market positioning, scenario planning, and decision quality. Tomas operates as a provocation layer — every strategy engagement surfaces explicit trade-offs (what we choose to do and what we explicitly choose not to do) before any execution begins.

The squad covers the full strategic stack: market sizing and competitive intelligence (Lucas), business model and revenue architecture (Marta S.), and decision framing with cognitive debiasing (Guilherme). For cross-cutting strategic questions that affect capital allocation or organizational direction, Tomas escalates to Marco (CTO) and the C-Suite tier.

## Command surface

| Commands | Skills | Agents |
| --- | --- | --- |
| 10 | 12 | 4 |

**Commands** (10 via `/strat`):

| Command | What it does |
| --- | --- |
| `/strat analyze <topic>` | Comprehensive strategic analysis (multi-framework) |
| `/strat blue-ocean <market>` | Blue Ocean strategy canvas + ERRC grid |
| `/strat bmc <business>` | Business Model Canvas |
| `/strat five-forces <industry>` | Porter's Five Forces analysis |
| `/strat growth <business>` | Growth strategy (Ansoff, adjacencies) |
| `/strat moat <company>` | 7 Powers moat analysis (Helmer) |
| `/strat position <product>` | Competitive positioning map |
| `/strat scenario <context>` | Scenario planning (3-5 scenarios) |
| `/strat swot <business>` | SWOT analysis |
| `/strat tam <market>` | TAM/SAM/SOM market sizing |

**Skills** (12 — 11 sub-skills plus the `/strategy` hub):

| Skill | What it does |
| --- | --- |
| `blue-ocean` | Blue Ocean Strategy analysis (Kim & Mauborgne): Strategy Canvas mapping your offering vs competitors, ERRC... |
| `bmc` | Business Model Canvas (Osterwalder): maps a business across the 9 blocks with a value proposition deep dive... |
| `board-advisor` | Board meeting preparation and structured multi-perspective executive deliberation: 6-phase protocol (contex... |
| `cto-advisor` | CTO-level advisory on technology strategy: build-vs-buy decision matrix, DORA metrics assessment, ADR gover... |
| `extract-data` | Navigates a web page via browser integration and extracts structured data (tables, lists, prices, product l... |
| `five-forces` | Porter's Five Forces industry analysis: rates rivalry, threat of new entrants, supplier power, buyer power,... |
| `growth-strategy` | Strategic growth-vector selection (Ansoff Matrix + Zook adjacencies + Greiner phases): decides WHERE to gro... |
| `moat-analysis` | Competitive moat analysis using Hamilton Helmer's 7 Powers: identifies which power applies to a company, sc... |
| `position` | Competitive positioning (Ries/Trout + April Dunford): maps competitive alternatives, unique capabilities, v... |
| `premortem` | Decision-quality ritual for irreversible bets, owned by the Governance squad: premortem before (assume fail... |
| `scenario-plan` | Scenario planning with PESTLE: builds 3-5 plausible futures (base, optimistic, pessimistic, black swan) and... |
| `strategy-hub` | Strategy & Innovation department. Competitive analysis, positioning, business model design, market sizing,... |

## The squad

| Agent | Role | Tier |
|---|---|---|
| Tomas | Chief Strategist | 1 |
| Guilherme | Decision Quality & Strategic Foresight | 2 |
| Marta S. | Business Model Designer | 2 |
| Lucas | Market & Competitive Intelligence Analyst | 2 |

## Frameworks

- **Porter's Five Forces** — industry structure analysis: rivalry, buyer power, supplier power, threat of entry, threat of substitutes
- **Blue Ocean Strategy / ERRC Grid (Kim/Mauborgne)** — eliminate-reduce-raise-create canvas to find uncontested market space
- **Business Model Canvas (Osterwalder)** — nine-block model covering value proposition, segments, channels, revenue streams, cost structure
- **Wardley Maps (Wardley)** — value chain evolution mapping; reveals what to build vs. buy vs. commoditize
- **7 Powers (Helmer)** — durable competitive advantages: scale economies, network effects, counter-positioning, switching costs, branding, cornered resource, process power
- **Playing to Win Cascade (Roger Martin)** — winning aspiration, where to play, how to win, capabilities, management systems
- **7 Strata + BHAG (Harnish)** — long-range vision anchored by a Big Hairy Audacious Goal and seven strategic layers
- **Premortem + Two-Way Doors (Bezos)** — Guilherme runs premortems to surface failure modes and flags irreversible decisions before they are made
- **TAM/SAM/SOM** — Lucas applies market sizing to anchor opportunity assessments in real numbers
- **SWOT/PESTLE** — contextual environmental scans used to frame scenario inputs

## What you can ask for

- "Map the competitive forces in this market" — `/strat five-forces`
- "Find the blue ocean in this industry" — `/strat blue-ocean`
- "Design or redesign our business model" — `/strat bmc`
- "Build a scenario plan for the next 3 years" — `/strat scenario-plan`
- "Analyze our moat and identify what to strengthen" — `/strat moat-analysis`
- "Define our positioning against these three competitors" — `/strat position`
- "Run a premortem on this strategic decision" — `/strat premortem`
- "Build a growth strategy for this market" — `/strat growth-strategy`
- "Give me a board-level strategic briefing" — `/strat board-advisor`
- "Advise on the technical strategy from a CTO perspective" — `/strat cto-advisor`

## When to use it

Route to Strategy when the question is upstream of execution: market entry, competitive positioning, business model design, scenario planning, or any decision that sets the direction for other departments. For operational efficiency and process work, use `/ops`. For financial modeling and valuation, use `/fin`.

---

Related: [Core Concepts](../02-Core-Concepts.md) · [The Evidence Flow (4 Gates)](../03-The-13-Phase-Flow.md) · [Quality Gate](../10-Quality-Gate.md)

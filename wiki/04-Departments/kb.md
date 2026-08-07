# Knowledge Management

← [Departments index](README.md) · [Home](../Home.md)

> **Prefix:** `/kb` · **Lead:** Clara (Tier 1) · **Agents:** 4 · **Skills:** 18

Knowledge Management is the squad responsible for building, organizing, and querying the team's institutional memory. It ingests raw sources — YouTube videos, PDFs, articles, research papers — processes them into permanent, linked notes, and surfaces the right context to every other department on demand. The vault lives in Obsidian; everything in it is linked, attributed, and evergreen.

Reach for this squad when you need to research a topic, evaluate whether a source is trustworthy, distill learning from content you've collected, build a callable AI persona from a body of work, or keep the vault itself healthy.

## Command surface

| Commands | Skills | Agents |
| --- | --- | --- |
| 23 | 18 | 4 |

**Commands** (23 via `/kb`):

| Command | What it does |
| --- | --- |
| `/kb ai-research <topic>` | AI-augmented research (Elicit, Perplexity, Claude) |
| `/kb capabilities` | Show available tools and API keys |
| `/kb cleanup [--older-than 90d]` | Remove old media files |
| `/kb evaluate <source>` | Source evaluation using CRAAP test |
| `/kb intel <competitor>` | Competitive intelligence research |
| `/kb learn <url>` | Ingest content (YouTube, article, PDF) into KB |
| `/kb learn-text <file/url> --persona "Name"` | Learn from text/article content (synchronous) |
| `/kb moc <cluster>` | Create/update Map of Content |
| `/kb para-review` | PARA organization review cycle |
| `/kb persona <name>` | Build or view a persona from the KB |
| `/kb personas` | List all personas and their stats |
| `/kb process <job-id>` | Analyze a ready transcription (interactive choices) |
| ... | 11 more — full list in [docs/COMMANDS.md](../../docs/COMMANDS.md) |

**Skills** (18 — 17 sub-skills plus the `/kb` hub):

| Skill | What it does |
| --- | --- |
| `ai-research` | AI-augmented research: uses Perplexity, Elicit, and Claude for source gathering and synthesis, delivering a... |
| `competitive-intel` | Competitive intelligence on a named competitor — product, pricing, positioning, marketing, team, funding —... |
| `doc-extraction` | Turns documents — PDFs, scans, images, office exports — into verified structured data: chooses text-layer v... |
| `doc-redaction` | Removes sensitive content from documents before they are shared, published, or ingested — client identifier... |
| `kb-hub` | Knowledge Management & Research department. Zettelkasten, BASB, research methodology, persona building, Obs... |
| `knowledge` | Knowledge Base department entry point powered by Obsidian: queues YouTube downloads, transcribes with Whisp... |
| `knowledge-ops` | Writes a note to the Obsidian vault the evidence-first way and verifies it landed — a note is not "saved" u... |
| `knowledge-review` | Knowledge freshness review of the Obsidian vault: identifies stale notes, updates progressive summaries, an... |
| `learn-content` | Ingests a content source (YouTube video, article, PDF): downloads, transcribes, and analyzes it with 5 para... |
| `moc-create` | Creates or updates a Map of Content (LYT, Nick Milo) when a topic cluster reaches 10+ notes, producing an O... |
| `persona-build` | Builds or refines a callable persona from KB content: source inventory, cited belief inventory, voice signa... |
| `research-deep` | Heavy-research ladder over the operator's own knowledge: Obsidian vault first (cite or declare the gap), th... |
| `research-plan` | Plans and executes structured research: defines the question, gathers academic/industry/expert sources, eva... |
| `search-kb` | Searches the Obsidian knowledge base: keyword, semantic, and cross-reference search across the vault, retur... |
| `source-evaluate` | Evaluates a single source's reliability with the CRAAP test — Currency, Relevance, Authority, Accuracy, Pur... |
| `taxonomy-manage` | Manages the knowledge base taxonomy: tags, categories, naming conventions, and hierarchy, delivering an upd... |
| `write-as-persona` | Writes content in a learned persona's voice, applying their frameworks, style, and KB knowledge, with frame... |
| `zettelkasten-process` | Processes content through the Zettelkasten workflow (Luhmann/Ahrens): fleeting -> literature -> permanent n... |

## The squad

| Agent | Role | Tier |
|---|---|---|
| Clara | Knowledge Director | 1 |
| Francisco | Research Analyst | 2 |
| Helena C. | Knowledge Curator | 2 |
| Tomas Jr | Data Collector | 3 |

## Frameworks

- **Zettelkasten (Niklas Luhmann, modernized by Sönke Ahrens):** the atomic-note method — fleeting → literature → permanent, every note linked, never isolated
- **Building a Second Brain / CODE / PARA (Tiago Forte):** Capture → Organize → Distill → Express; folder architecture (Projects / Areas / Resources / Archive)
- **SECI Model (Nonaka / Takeuchi):** Socialization → Externalization → Combination → Internalization — how tacit knowledge becomes explicit and spreads
- **LYT / Maps of Content (Nick Milo):** structural notes that index topic clusters once they exceed ~10 atomic notes
- **Progressive Summarization:** layer-by-layer highlighting that surfaces the most useful content without losing the original
- **Feynman Technique:** Clara's quality test — if you can't explain it simply, you don't know it well enough to add it to the vault
- **CRAAP Test (source evaluation):** Currency, Relevance, Authority, Accuracy, Purpose — Francisco's filter on every external source
- **AI Research Workflow (Elicit / Perplexity / Claude):** Francisco's toolchain for AI-augmented literature review and synthesis

## What you can ask for

- "Research the current state of vector database options for our RAG pipeline" → `/kb ai-research`
- "Map out our three main competitors — product, pricing, positioning, funding" → `/kb competitive-intel`
- "Process this YouTube video into permanent Zettelkasten notes" → `/kb zettelkasten-process`
- "Ingest this PDF and extract the key ideas into the vault" → `/kb learn-content`
- "Is this blog post a reliable source? Run the CRAAP test on it" → `/kb source-evaluate`
- "Build a research plan for our market-sizing work next quarter" → `/kb research-plan`
- "Search the vault for everything we know about PLG onboarding" → `/kb search-kb`
- "Build a callable persona from Alex Hormozi's body of work" → `/kb persona-build`
- "Write a section of the sales doc in the voice of the learned persona" → `/kb write-as-persona`
- "Create a Map of Content for the SaaS metrics topic cluster" → `/kb moc-create`
- "Audit the vault for stale notes and broken links" → `/kb knowledge-review`
- "Redesign the tag taxonomy — it's gotten out of hand" → `/kb taxonomy-manage`
- "Ingest this knowledge source into the ArkaOS vault" → `/kb knowledge`

## When to use it

Use Knowledge Management whenever a question requires synthesis across multiple sources rather than a single answer, before starting a strategy or research phase in another department, or when institutional knowledge needs to be codified so the team doesn't lose it. Other squads pull from this vault constantly — keeping it healthy is a force multiplier across all 17 departments.

---

Related: [Core Concepts](../02-Core-Concepts.md) · [The Evidence Flow (4 Gates)](../03-The-13-Phase-Flow.md) · [Quality Gate](../10-Quality-Gate.md)

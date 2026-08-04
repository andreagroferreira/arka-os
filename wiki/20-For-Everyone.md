# 20 · For Everyone

← [Home](Home.md) · [19 · Token Economy](19-Token-Economy.md)

ArkaOS is a team of specialised AI agents that runs inside your coding
tool. You do not need to be a programmer to get value from it — you do
need someone to install it once. This page is the plain-language guide:
what it can do, how to talk to it, and where the limits are.

## What ArkaOS is

Think of it as an operating system for AI work. Instead of one generic
assistant, you get departments staffed by specialised agents — each
trained on proven frameworks in its field:

| Say... | You get a squad that handles |
|---|---|
| Marketing | SEO, campaigns, content strategy, email sequences |
| Brand & Design | Identity, voice, UX, design systems |
| Finance | Models, unit economics, budgets, valuations |
| Strategy | Positioning, competitors, business models |
| E-Commerce | Store audits, conversion, customer segments |
| Content | Scripts, hooks, repurposing, video |
| Sales | Proposals, pipelines, negotiation |
| Knowledge | Research, note-taking, learning from videos/articles |
| Operations | Automations, workflows, processes |
| Project & Product | Roadmaps, sprints, backlogs |

There are 17 departments in total, with 89 specialist agents.

## How to talk to it

**Use plain language.** The `/do` command is the universal translator:
it reads what you want, works out which department handles it, and runs
the right workflow.

```
/do "we launch the new course in March, plan the marketing"
/do "how much should we charge for the premium tier"
/do "turn my blog post into a newsletter and a LinkedIn thread"
```

You can also talk directly to a department (`/mkt "campaign for the
launch"`, `/fin "cash flow forecast"`, `/content "script for a video
about X"`).

## What you get without code

- **Research and learning** — give it a YouTube video, article, or PDF
  and it transcribes, analyses, and files the knowledge where it can be
  reused (see [09 · Knowledge Base](09-Knowledge-Base.md)).
- **Documents and plans** — strategy documents, marketing plans, offer
  design, financial models, all saved to your notes.
- **Content** — scripts, hooks, thumbnails concepts, repurposing plans.
- **Visibility** — `/arka status` shows system health and what was
  learned; `/arka costs` shows what each session spent.
- **A vault that grows smarter** — every session is reflected on at
  night (Dreaming) and knowledge is injected back at the right moment
  (see [06 · Cognitive Layer](06-Cognitive-Layer.md)).

## What still needs a developer

- Installing and updating ArkaOS (one-time, by someone with terminal
  access — [01 · Getting Started](01-Getting-Started.md)).
- Building or deploying actual software — agents plan, write, and
  review code, but the code lives in your repositories and ships
  through your usual process (branch, review, deploy).
- Connecting external tools with API keys.

## How to stay in control

- Everything the agents produce passes a **Quality Gate** — a
  designated reviewer approves or rejects before delivery
  ([10 · Quality Gate](10-Quality-Gate.md)).
- Agents plan before they act and wait for your approval on
  non-trivial work — you see the plan first.
- You decide the budget: the CostGovernor can cap session or daily
  spend per project ([19 · Token Economy](19-Token-Economy.md)).
- Nothing is deleted automatically; deliverables are saved as notes you
  own.

## First things to try

1. `/do "explain what ArkaOS can do for my business"` — a live tour.
2. `/arka status` — see your system working.
3. Feed one video or article to the knowledge base and ask about it
   the next day.

---

Related: [01 · Getting Started](01-Getting-Started.md), [02 · Core Concepts](02-Core-Concepts.md), [Home](Home.md)

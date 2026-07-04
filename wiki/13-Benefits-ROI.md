# 13 · Benefits & ROI

← [Home](Home.md) · Related: [Benchmarks](11-Benchmarks.md) · [Competitive Analysis](12-Competitive-Analysis.md)

This page estimates value. **Every number here is an illustrative assumption,
labelled as such.** ArkaOS does not claim these as measured outcomes — they are
a transparent model you can adjust to your own situation. Where a figure is a
measured fact (test count, agent count, latency), it links to
[Benchmarks](11-Benchmarks.md).

> How to read this page: treat every "Assume…" line as a dial. Change it to
> your real rates and the conclusion changes. The point is the *structure* of
> the value, not the specific euros.

---

## The four benefit categories

ArkaOS creates value in four distinct ways. Each is qualitative first; the ROI
model below only quantifies the ones you can reasonably estimate.

### 1. Breadth — one tool instead of many

A solo founder or small agency otherwise stitches together a coding assistant,
a copywriter, a strategist, a bookkeeper's spreadsheet, and a project tracker.
ArkaOS covers all of these as 17 departments. The benefit is **fewer tools,
fewer context switches, one knowledge store**.

### 2. Quality — review is structural, not optional

Every deliverable passes the [Quality Gate](10-Quality-Gate.md) (Marta +
Eduardo + Francisca) before you see it. A lone assistant reviews its own work
only when it remembers to. The benefit is **fewer defects reaching you** —
caught text errors, security issues, and broken implementations.

### 3. Compounding — the system gets smarter

The [Cognitive Layer](06-Cognitive-Layer.md) captures every solution and
critiques it overnight. The benefit grows over time: **work on project N is
faster because the system remembers projects 1…N-1**.

### 4. Discipline — the evidence flow

Grounded context, an explicit approval gate, a real test run, and executable
review checks happen in order, every time. Gates pass on **evidence** —
command output, exit codes, report files — not on the model narrating that
work happened. The benefit is **predictability without ceremony tax**: you are
not relying on the model to "remember" to test, and you are not paying tokens
for role-played rigor either.

## An illustrative ROI model

The model below is for a **solo developer / small agency**. Adjust every
assumption to your reality.

**Assumptions (illustrative — change these):**

- Assume a blended rate of **€60/hour** for the operator's time.
- Assume ArkaOS saves **5 hours/week** by collapsing tool-switching, drafting,
  and review into one flow. (Conservative for a multi-domain operator; could be
  far higher or lower for you.)
- Assume **46 working weeks/year**.
- Assume ArkaOS's direct cost is the underlying AI runtime subscription you
  already pay (ArkaOS itself is installed via `npx`); treat incremental tooling
  cost as **near-zero** for this model.

**Resulting estimate:**

```
5 hours/week  ×  €60/hour  ×  46 weeks  =  €13,800 / year of recovered time
```

> This is recovered-time value, not new revenue, and it rests entirely on the
> 5-hours assumption. At 2 hours/week it is ~€5,520; at 10 hours/week it is
> ~€27,600. Pick the number you can defend for your own workflow.

### Quality value (harder to quantify, stated honestly)

The Quality Gate's value is **avoided cost**: a security issue caught before
production, a pricing typo caught before a campaign, a broken migration caught
before it ships. These are real but situational — a single avoided incident can
dwarf the time-savings figure, or a quiet month can contribute nothing. We do
**not** put a number on this, because any number would be invented.

## Who benefits most

| Profile | Primary benefit | Why |
|---|---|---|
| Solo founder | Breadth | One operator covering many functions |
| Small agency | Compounding + quality | Knowledge reused across client ecosystems |
| Indie developer | Discipline | Spec → test → review → document, enforced |
| Consultant | Breadth + memory | Cross-domain work, recalled per client |

Larger orgs with dedicated specialists in each function gain less from breadth
and more from the discipline and quality layers.

## What ArkaOS does not promise

- It does not replace human judgment on strategy, hiring, or pricing — it
  structures and accelerates the work.
- It does not guarantee revenue outcomes. The ROI above is recovered time, not
  sales.
- It is not a substitute for an AI IDE's inner-loop coding ergonomics (see
  [Competitive Analysis](12-Competitive-Analysis.md)).

---

Related: [Benchmarks](11-Benchmarks.md) for the measured facts behind these
claims; [Competitive Analysis](12-Competitive-Analysis.md) for how the
capabilities compare.

---
name: pm/shape-pitch
description: >
  Shape Up pitch (Ryan Singer) for the betting table: problem, appetite as
  a time budget, fat-marker solution sketch, rabbit holes, and explicit
  no-gos, with hill-chart tracking. TRIGGER: "shape this feature", "escreve
  o pitch", "prepara a betting table", "define o appetite", "Shape Up
  pitch", "/pm shape". SKIP: detailed requirements and acceptance criteria
  -> dev/spec (spec defines the buildable WHAT; a pitch sells a bet);
  sprint-based commitment -> pm/sprint-plan; deciding which bets enter
  which quarter -> pm/roadmap-build.
allowed-tools: [Read, Write, Edit, Agent]
---

# Shape Up Pitch — `/pm shape <feature>`

> **Agent:** Carolina (Product Manager) | **Framework:** Shape Up (Ryan Singer / Basecamp)

## Pitch Structure

### 1. Problem
What's the raw problem or request? Who is affected? How painful is it?

### 2. Appetite
How much time is this worth? Not an estimate — a budget.
- Small Batch: 1-2 weeks (1-2 people)
- Big Batch: 6 weeks (2-3 people)

### 3. Solution (Fat Marker Sketch)
Rough solution at the right level of abstraction:
- Not a wireframe (too detailed)
- Not a word description only (too vague)
- Fat marker sketches: key screens, flows, interactions

### 4. Rabbit Holes
Known risks and complexities to avoid:
- "If we go down path X, we'll spend 3 weeks on it. Don't."
- Explicitly mark what's OUT of scope

### 5. No-Gos
What we're explicitly NOT doing:
- Features that would be nice but blow the appetite
- Edge cases we won't handle in this cycle

## Betting Table
- Senior leadership reviews pitches
- Bets are placed: "We bet 6 weeks on this pitch"
- No backlog: unbetted pitches are discarded (they can be re-pitched later)
- Circuit breaker: if not done in 6 weeks, it's cancelled by default

## Hill Chart Tracking
```
    /\
   /  \
  / UP \ DOWN \
 / hill \hill  \
```
Uphill = figuring it out (uncertainty)
Downhill = executing (certainty)

## Output → Pitch document ready for betting table

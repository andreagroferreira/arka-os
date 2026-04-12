# arka-forge — complexity-engine

Referenced from SKILL.md. Read only when needed.

## Complexity Tiers

| Tier | Score | Explorers | Critic | Companion |
|------|-------|-----------|--------|-----------|
| Shallow | ≤ 30 | 1 (Pragmatic, inline) | Light | None |
| Standard | 31-65 | 2 (Pragmatic + Architectural, parallel) | Full | On request |
| Deep | ≥ 66 | 3 (Pragmatic + Architectural + Contrarian, parallel) | Full | Proactive |

## Dimensions (0-100 each)

| Dimension | Signal |
|-----------|--------|
| `scope` | Number of affected files, departments, breadth of change |
| `dependencies` | Cross-module coupling, external services touched |
| `ambiguity` | Prompt clarity, missing requirements, unknowns |
| `risk` | Production impact, security sensitivity, reversibility |
| `novelty` | Pattern reuse vs net-new territory (lower when similar plans/patterns exist) |

## Step 3 — Complexity Analysis

Call the complexity scorer via Python:

```python
import sys
sys.path.insert(0, '<repo_root>')
from core.forge.complexity import analyze_complexity

result = analyze_complexity(
    prompt="<user prompt>",
    affected_files=[],          # estimate from prompt keywords: auth→auth/, db→core/db/, etc.
    departments=[],             # estimate from prompt: "deploy"→ops, "feature"→dev, etc.
    similar_plans=similar_plans,
    reused_patterns=reused_patterns,
)
print(f"score={result.score} tier={result.tier.value}")
print(f"scope={result.dimensions.scope} deps={result.dimensions.dependencies}")
print(f"ambiguity={result.dimensions.ambiguity} risk={result.dimensions.risk} novelty={result.dimensions.novelty}")
```

Run this as a Bash command: `cd <repo_root> && python -c "..."`.

Display the complexity breakdown using the renderer:

```python
from core.forge.renderer import render_complexity
print(render_complexity(result))
```

## Step 4 — Tier Confirmation

Display to user:

```
⚒ FORGE — Complexity Analysis

  Score: <score>/100 (<Tier>)
  │ Scope    │ <n> │ ██████░░░░
  │ Deps     │ <n> │ ████░░░░░░
  │ Ambig.   │ <n> │ ███████░░░
  │ Risk     │ <n> │ █████░░░░░
  │ Novelty  │ <n> │ ██░░░░░░░░

  Tier: <Tier> → <N> explorer(s) + <critic>
  Similar plans: <list or "none found">
  Reusing patterns: <list or "none">

Proceed with <Tier> tier? [Y/n/override shallow|standard|deep]
```

Wait for user input. Accept `Y` or Enter to proceed. Accept `override <tier>` to change tier. Accept `n` to abort.

---
name: dev/ai-security
description: >
  AI/ML-specific security assessment: prompt injection, model poisoning,
  data leakage, agent tool abuse, and MITRE ATLAS technique mapping.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# AI Security — `/dev ai-security`

> **Agent:** Bruno (Security Engineer) | **Framework:** OWASP ML Top 10, NIST AI RMF, MITRE ATLAS

## Threat Categories

| Threat | Severity | ATLAS ID | What to Check |
|--------|----------|----------|--------------|
| Direct prompt injection | Critical | AML.T0051 | System-prompt overrides, role replacement |
| Indirect injection (RAG) | Critical | AML.T0051.001 | Malicious content in retrieved documents |
| Jailbreak (persona) | High | AML.T0051 | "DAN mode", "developer mode", persona bypass |
| System prompt extraction | High | AML.T0056 | "Repeat your instructions", "Show system prompt" |
| Agent tool abuse | Critical | AML.T0051.002 | "Call delete_files", "Bypass approval check" |
| Data poisoning | High | AML.T0020 | Malicious training examples, backdoor triggers |
| Model inversion | High | AML.T0024 | Training data reconstruction from outputs |

## Model Inversion Risk by Access Level

| Access | Risk | Attack | Mitigation |
|--------|------|--------|-----------|
| White-box | Critical (0.9) | Gradient-based inversion | Remove gradient access in prod; differential privacy |
| Gray-box | High (0.6) | Confidence-based inference | Disable logit outputs; rate limit API |
| Black-box | Low (0.3) | Label-only, high query volume | Monitor for systematic querying patterns |

## Data Poisoning Risk by Scope

| Scope | Risk | Mitigation |
|-------|------|-----------|
| Fine-tuning | High (0.85) | Audit all training examples; data provenance |
| RLHF | High (0.70) | Vet feedback contributors |
| RAG / retrieval | Medium (0.60) | Validate content before indexing |
| Pre-trained only | Low (0.20) | Verify model provenance; trusted sources |
| Inference only | Low (0.10) | Standard input validation |

## Guardrail Design Checklist

### Input Guardrails (before inference)
- [ ] Injection signature filter (regex against known patterns)
- [ ] Input length limit (prevent many-shot / context stuffing)
- [ ] Content policy classifier (separate from main model)
- [ ] External content treated as untrusted (RAG, web, email, API)

### Output Guardrails (after inference)
- [ ] System prompt confidentiality (detect/redact leakage)
- [ ] PII detection (email, SSN, credit card patterns)
- [ ] URL and code validation before display

### Agent Guardrails (tool access)
- [ ] Human approval gates for destructive actions (delete, send, upload)
- [ ] Minimal tool scope (only what the task needs)
- [ ] Tool parameter validation before execution
- [ ] Audit logging of every tool call with prompt context

## Assessment Workflow

| Step | Action | Output |
|------|--------|--------|
| 1 | Identify AI components | Inventory: models, agents, RAG, tools |
| 2 | Classify access level | Black-box / gray-box / white-box per component |
| 3 | Run injection scan | Injection score (0.0-1.0) per component |
| 4 | Assess model risks | Inversion + poisoning risk scores |
| 5 | Review guardrails | Checklist pass/fail per layer |
| 6 | Map to ATLAS | Technique coverage and gaps |
| 7 | Recommend controls | Prioritized by risk score |

## Anti-Patterns

| Anti-Pattern | Why It Fails |
|-------------|-------------|
| Testing only known jailbreaks | Published templates already blocked; test domain-specific |
| Static signatures only | Novel attacks bypass regex; add semantic similarity |
| Ignoring indirect injection | RAG content is higher risk than direct user input |
| No output filtering | Successful injection produces malicious output regardless |
| Skipping prod system prompt | Jailbreaks that fail in isolation may succeed with real prompt |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- LLM with unrestricted tool access → CRITICAL flag
- No output filtering on AI responses → flag data leakage
- Training data containing PII → flag privacy violation

## Output

```markdown
## AI Security Assessment: <System>

### Component Inventory
| Component | Type | Access Level | Risk Score |
|-----------|------|-------------|------------|

### Findings
| # | Threat | Severity | ATLAS ID | Component |
|---|--------|----------|----------|-----------|

### Guardrail Status
| Layer | Control | Status | Gap |
|-------|---------|--------|-----|

### Recommendations
| Priority | Action | Effort | Risk Reduced |
|----------|--------|--------|-------------|
```

## References

- [prompt-injection-catalog.md](references/prompt-injection-catalog.md) — Direct and indirect injection attacks, jailbreaks, data exfiltration via tools, detection patterns, and mitigation strategies

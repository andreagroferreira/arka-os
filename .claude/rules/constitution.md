---
paths:
  - "config/constitution.yaml"
  - "CONSTITUTION.md"
  - "core/governance/**/*.py"
---

# Constitution Rules

- Constitution changes require explicit user approval
- Rule LEVELS may be recalibrated only by a recorded amendment approved by
  the operator (Constitution 2.0, 2026-07-08: 26 NON-NEGOTIABLE -> 6).
  Admission test for NON-NEGOTIABLE: verifiable by evidence at a gate, or
  a standing operator mandate. The fixed floor that can never be demoted:
  branch-isolation, security-gate, mandatory-qa, evidence-flow,
  arkaos-not-yes-man, excellence-mandate.
- Rule TEXT/SCOPE is never silently changed by a re-tiering — moving a
  rule between levels preserves its rule and enforcement fields verbatim
- Every rule must have: id, level (non-negotiable/must/should), description, enforcement
- Quality Gate (Marta/Eduardo/Francisca) is always mandatory, never optional
- Every level change or rule addition records an amendments.history entry
  (version + date + what moved) in config/constitution.yaml

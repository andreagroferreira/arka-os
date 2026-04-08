---
paths:
  - "core/**/*.py"
  - "scripts/**/*.py"
  - "tests/**/*.py"
---

# Python Core Rules

- Type hints on all function signatures (Pydantic models, dataclasses)
- Use Pydantic for validation and serialization
- Virtual environments only (never global pip install)
- pytest for all tests, fixtures over setUp/tearDown
- Max function length: 30 lines
- Docstrings only on public API functions

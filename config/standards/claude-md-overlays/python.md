## Python Stack Conventions

- Type hints on every function signature.
- Pydantic for validation; dataclasses for pure data.
- `pytest` with fixtures; no `unittest.TestCase`.
- Functions under 30 lines; one responsibility.
- Docstrings on public API only; self-documenting code elsewhere.
- Virtual environments; never global `pip install`.

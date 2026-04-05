# Contributing to ArkaOS

Thank you for your interest in contributing to ArkaOS!

## How to Contribute

### Reporting Issues

- Use [GitHub Issues](https://github.com/andreagroferreira/arka-os/issues) to report bugs or request features
- Include steps to reproduce, expected behavior, and actual behavior

### Submitting Changes

1. **Fork** the repository
2. **Create a feature branch** from `master`: `git checkout -b feat/your-feature`
3. **Follow conventions:**
   - Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
   - Skills follow v2 format (see `departments/dev/skills/` for examples)
   - Python: type hints, Pydantic models, pytest tests
   - Keep SKILL.md files between 60-120 lines
4. **Add tests** for new functionality
5. **Run the test suite:** `python -m pytest tests/ -q`
6. **Run the skill validator:** `python scripts/skill_validator.py departments/ --summary`
7. **Submit a Pull Request** against `master`

### Pull Request Guidelines

- PRs require review before merging — direct pushes to `master` are blocked
- All CI checks must pass (Python tests, Node.js syntax, skill validation)
- Keep PRs focused — one feature or fix per PR
- Update `CHANGELOG.md` for user-facing changes

### Branch Naming

| Prefix | Purpose |
|--------|---------|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation |
| `refactor/` | Code improvements |
| `test/` | Test additions |

### What We Look For

- Follows existing patterns and conventions
- Tests included and passing
- Skills use validated enterprise frameworks
- Clean, self-documenting code (SOLID principles)
- No secrets or credentials committed

## Code of Conduct

Be respectful, constructive, and collaborative. We're building something together.

## Questions?

Open an issue or start a discussion on the repository.

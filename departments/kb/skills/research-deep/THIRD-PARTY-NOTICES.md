# Third-party notices — kb/research-deep

This skill's content is ArkaOS-native. At runtime, its NotebookLM rung
shells out — exclusively through the `core.kb.nlm_client` chokepoint —
to the `notebooklm` CLI provided by the **notebooklm-py** project:

- Project: notebooklm-py — https://github.com/teng-lin/notebooklm-py
- License: MIT (PyPI metadata, verified 2026-08-03 at version 0.8.0)
- Relationship: runtime dependency only. ArkaOS does not vendor,
  redistribute, or auto-install notebooklm-py; the operator installs it
  themselves (`uv tool install 'notebooklm-py[browser]'`) and the skill
  degrades gracefully when it is absent.

No notebooklm-py source code or documentation text is included in this
skill.

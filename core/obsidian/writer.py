"""Obsidian vault writer — save workflow outputs to knowledge base.

Resolves vault path from:
1. Constructor argument
2. knowledge/obsidian-config.json → vault_path
3. ARKAOS_VAULT environment variable
4. Fallback: ~/.arkaos/vault/
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from core.obsidian.templates import build_frontmatter, resolve_template_vars


class ObsidianWriter:
    """Writes markdown files to an Obsidian vault with frontmatter."""

    def __init__(self, vault_path: str | Path | None = None, arkaos_root: str | Path | None = None) -> None:
        self._vault_path = self._resolve_vault_path(vault_path, arkaos_root)

    def save(
        self,
        obsidian_path: str,
        content: str,
        department: str = "",
        agent: str = "",
        workflow: str = "",
        tags: list[str] | None = None,
        template_vars: dict[str, str] | None = None,
        extra_frontmatter: dict[str, Any] | None = None,
    ) -> Path:
        """Save content to the Obsidian vault.

        Args:
            obsidian_path: Relative path within vault (may contain template vars).
            content: Markdown content to save.
            department: Source department.
            agent: Agent that produced the output.
            workflow: Workflow that generated this output.
            tags: Additional tags for frontmatter.
            template_vars: Variables to resolve in path ({project}, {date}, etc.).
            extra_frontmatter: Additional frontmatter fields.

        Returns:
            Absolute path to the saved file.
        """
        # Resolve template variables in path
        resolved_path = resolve_template_vars(obsidian_path, template_vars)

        # Build full path
        full_path = self._vault_path / resolved_path

        # If path doesn't end with .md, treat as directory and add filename
        if not full_path.suffix:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
            filename = f"{department or 'output'}-{timestamp}.md"
            full_path = full_path / filename
        elif full_path.suffix != ".md":
            full_path = full_path.with_suffix(".md")

        # Handle duplicate filenames
        if full_path.exists():
            stem = full_path.stem
            timestamp = datetime.now().strftime("%H%M%S")
            full_path = full_path.with_stem(f"{stem}-{timestamp}")

        # Create directories
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Build frontmatter
        frontmatter = build_frontmatter(
            department=department,
            agent=agent,
            workflow=workflow,
            tags=tags,
            extra=extra_frontmatter,
        )

        # Write file
        file_content = f"{frontmatter}\n\n{content}"
        full_path.write_text(file_content, encoding="utf-8")

        return full_path

    def ensure_vault(self) -> bool:
        """Verify the vault directory exists."""
        return self._vault_path.exists()

    def list_outputs(self, department: str = "", limit: int = 50) -> list[Path]:
        """List recent ArkaOS outputs in the vault."""
        if not self._vault_path.exists():
            return []

        pattern = "**/*.md"
        files = sorted(self._vault_path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

        results = []
        for f in files:
            if len(results) >= limit:
                break
            try:
                head = f.read_text(encoding="utf-8")[:200]
                if "source: arkaos" in head:
                    if not department or f"department: {department}" in head:
                        results.append(f)
            except (OSError, UnicodeDecodeError):
                continue

        return results

    @property
    def vault_path(self) -> Path:
        return self._vault_path

    def _resolve_vault_path(self, explicit: str | Path | None, arkaos_root: str | Path | None) -> Path:
        """Resolve vault path from multiple sources."""
        # 1. Explicit argument
        if explicit:
            return Path(explicit)

        # 2. Config file
        if arkaos_root:
            config_path = Path(arkaos_root) / "knowledge" / "obsidian-config.json"
        else:
            config_path = Path(__file__).resolve().parent.parent.parent / "knowledge" / "obsidian-config.json"

        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
                vault = config.get("vault_path", "")
                if vault and Path(vault).exists():
                    return Path(vault)
            except (json.JSONDecodeError, OSError):
                pass

        # 3. Environment variable
        env_vault = os.environ.get("ARKAOS_VAULT", "")
        if env_vault and Path(env_vault).exists():
            return Path(env_vault)

        # 4. Fallback
        fallback = Path.home() / ".arkaos" / "vault"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

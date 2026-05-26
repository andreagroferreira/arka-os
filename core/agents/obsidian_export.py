"""Export agent profiles to the Obsidian vault (PR86c v3.17.0).

Writes a Markdown file with YAML frontmatter + readable sections to
``<vault>/Agents/<id>.md``. Sibling to ``core/personas/obsidian_store``
but write-only — agents are still source-of-truth in their YAML files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.profile import ProfileManager


_AGENTS_SUBDIR = "Agents"


class AgentExportError(RuntimeError):
    """Raised when the vault is missing or the write fails."""


@dataclass(frozen=True)
class AgentExportResult:
    path: Path
    vault_path: Path


def export_agent_to_vault(agent: dict) -> AgentExportResult:
    """Render `agent` as Markdown and write it to the configured vault.

    `agent` is the YAML-loaded dict for the agent (the same shape
    returned by ``/api/agents/{id}``).
    """
    if not isinstance(agent, dict) or not agent.get("id"):
        raise AgentExportError("agent payload must include 'id'")
    vault = _resolve_vault_path()
    if vault is None:
        raise AgentExportError(
            "Obsidian vault is not configured (set vaultPath in profile)"
        )
    target_dir = vault / _AGENTS_SUBDIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{agent['id']}.md"
    md = _render(agent)
    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        tmp.write_text(md, encoding="utf-8")
        tmp.replace(target)
    except OSError as exc:
        raise AgentExportError(f"write failed: {exc}") from exc
    return AgentExportResult(path=target, vault_path=vault)


def _resolve_vault_path() -> Path | None:
    try:
        profile = ProfileManager().read()
    except Exception:  # noqa: BLE001
        return None
    if not profile.vaultPath:
        return None
    path = Path(profile.vaultPath).expanduser()
    return path if path.exists() else None


def _render(agent: dict) -> str:
    """Compose the Markdown body — YAML frontmatter + readable sections."""
    fm_lines = [
        "---",
        "type: agent",
        f"id: {agent.get('id', '')}",
        f"name: {_yaml_str(agent.get('name', ''))}",
        f"role: {_yaml_str(agent.get('role', ''))}",
        f"department: {agent.get('department', '')}",
        f"tier: {agent.get('tier', '')}",
        f"model: {agent.get('model', '')}",
        "---",
        "",
    ]
    sections: list[str] = []
    sections.append(f"# {agent.get('name') or agent.get('id', '(unnamed)')}")
    if agent.get("role"):
        sections.append(f"*{agent['role']}* · `{agent.get('department', '')}`")
    sections.append("")

    dna = agent.get("behavioral_dna") or {}
    if dna:
        sections.append("## Behavioural DNA")
        disc = dna.get("disc") or {}
        enn = dna.get("enneagram") or {}
        bf = dna.get("big_five") or {}
        mbti = dna.get("mbti")
        mbti_type = mbti.get("type") if isinstance(mbti, dict) else mbti
        sections.append(f"- **DISC:** {disc.get('primary', '?')}/{disc.get('secondary', '?')}")
        sections.append(f"- **Enneagram:** {enn.get('type', '?')}w{enn.get('wing', '?')}")
        sections.append(f"- **MBTI:** {mbti_type or '—'}")
        if bf:
            ocean = " · ".join(
                f"{k[:1].upper()}{int(v)}"
                for k, v in bf.items()
                if isinstance(v, (int, float))
            )
            if ocean:
                sections.append(f"- **OCEAN:** {ocean}")
        sections.append("")

    exp = agent.get("expertise") or {}
    if exp:
        sections.append("## Expertise")
        domains = exp.get("domains") or []
        frameworks = exp.get("frameworks") or []
        if domains:
            sections.append("**Domains**")
            sections.extend(f"- {d}" for d in domains)
            sections.append("")
        if frameworks:
            sections.append("**Frameworks**")
            sections.extend(f"- {f}" for f in frameworks)
            sections.append("")
        sections.append(f"*Depth: {exp.get('depth', '—')} · {exp.get('years_equivalent', '—')}y equivalent*")
        sections.append("")

    mm = agent.get("mental_models") or {}
    if mm:
        primary = mm.get("primary") or []
        secondary = mm.get("secondary") or []
        if primary or secondary:
            sections.append("## Mental Models")
            if primary:
                sections.append("**Primary**")
                sections.extend(f"- {m}" for m in primary)
                sections.append("")
            if secondary:
                sections.append("**Secondary**")
                sections.extend(f"- {m}" for m in secondary)
                sections.append("")

    comm = agent.get("communication") or {}
    if comm and any(comm.values()):
        sections.append("## Communication")
        if comm.get("tone"):
            sections.append(f"- **Tone:** {comm['tone']}")
        if comm.get("vocabulary_level"):
            sections.append(f"- **Vocabulary:** {comm['vocabulary_level']}")
        if comm.get("preferred_format"):
            sections.append(f"- **Preferred format:** {comm['preferred_format']}")
        if comm.get("language"):
            sections.append(f"- **Language:** {comm['language']}")
        avoid = comm.get("avoid") or []
        if avoid:
            sections.append(f"- **Avoid:** {', '.join(avoid)}")
        sections.append("")

    linked = agent.get("linked_personas") or []
    if linked:
        sections.append("## Linked Personas")
        sections.extend(f"- [[{p}]]" for p in linked)
        sections.append("")

    sections.append("")
    sections.append("*Generated by ArkaOS — source of truth lives in the YAML file.*")
    return "\n".join(fm_lines + sections)


def _yaml_str(value: object) -> str:
    """Quote a YAML scalar if it contains special characters."""
    s = "" if value is None else str(value)
    if any(c in s for c in ":#'\"\n"):
        escaped = s.replace('"', '\\"')
        return f'"{escaped}"'
    return s

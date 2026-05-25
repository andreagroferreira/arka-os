"""Obsidian-backed persona store (PR73 v2.91.0).

Reads personas from ``<vaultPath>/Personas/*.md`` and writes new
personas back to the same folder. The vault path comes from
``~/.arkaos/profile.json::vaultPath``; when that's empty / missing,
the store gracefully degrades to a no-op (the JSON store keeps
working).

Per the operator's instruction: "personas podiamos ir buscar a lista
aqui o que esta no obsidian acho que é o mais sensato e quando criamos
guardamos no obsidian tambem". This module implements both directions.

Schema (frontmatter):
  type: persona
  name: <full name>
  source: <one-line summary>
  title: <role label>
  tagline: <essence>
  mbti: <4-letter>
  disc: { primary, secondary }
  enneagram: { type, wing }
  big_five: { openness, ... }
  mental_models: [list]
  expertise: [list]  # legacy alias for expertise_domains
  expertise_domains: [list]
  frameworks: [list]
  key_quotes: [list]
  communication: { tone, vocabulary_level, preferred_format, avoid }

Unknown frontmatter keys are ignored. Body markdown is preserved
when reading but not re-injected into the Persona model (the model
doesn't carry free-form notes).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from core.personas.schema import (
    Persona,
    PersonaBigFive,
    PersonaCommunication,
    PersonaDISC,
    PersonaEnneagram,
)
from core.profile import ProfileManager


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)
_PERSONAS_SUBDIR = "Personas"


_UNSET = object()


class ObsidianPersonaStore:
    """Read / write personas as Markdown files in an Obsidian vault."""

    def __init__(self, vault_path: Path | None | object = _UNSET) -> None:
        # Distinguish "not passed" (auto-resolve from profile) from
        # "passed as None" (explicitly no vault — tests use this).
        if vault_path is _UNSET:
            self._vault_path = self._resolve_vault_path()
        else:
            self._vault_path = vault_path  # type: ignore[assignment]

    @property
    def available(self) -> bool:
        return bool(self._vault_path and self.personas_dir.exists())

    @property
    def personas_dir(self) -> Path:
        return (self._vault_path or Path()) / _PERSONAS_SUBDIR

    @staticmethod
    def _resolve_vault_path() -> Path | None:
        try:
            profile = ProfileManager().read()
        except Exception:  # noqa: BLE001
            return None
        if not profile.vaultPath:
            return None
        path = Path(profile.vaultPath).expanduser()
        return path if path.exists() else None

    # ─── Read ────────────────────────────────────────────────────────────

    def list_all(self) -> list[Persona]:
        """Return every parseable persona in <vault>/Personas/."""
        if not self.available:
            return []
        out: list[Persona] = []
        for md_path in sorted(self.personas_dir.glob("*.md")):
            persona = self._read_file(md_path)
            if persona is not None:
                out.append(persona)
        return out

    def _read_file(self, md_path: Path) -> Persona | None:
        try:
            text = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        fm = self._parse_frontmatter(text)
        if not fm:
            return None
        # MOC files etc. can also live in this folder; skip anything not
        # explicitly typed as persona.
        if str(fm.get("type", "")).lower() != "persona":
            return None
        return self._frontmatter_to_persona(fm, md_path)

    @staticmethod
    def _parse_frontmatter(text: str) -> dict[str, Any] | None:
        match = _FRONTMATTER_RE.match(text)
        if not match:
            return None
        try:
            import yaml  # noqa: PLC0415
        except ImportError:
            return None
        try:
            data = yaml.safe_load(match.group(1)) or {}
        except Exception:  # noqa: BLE001 — yaml parsers raise many shapes
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _frontmatter_to_persona(fm: dict, md_path: Path) -> Persona:
        name = str(fm.get("name") or md_path.stem)
        disc_fm = fm.get("disc") if isinstance(fm.get("disc"), dict) else {}
        enneagram_fm = fm.get("enneagram") if isinstance(fm.get("enneagram"), dict) else {}
        big_five_fm = fm.get("big_five") if isinstance(fm.get("big_five"), dict) else {}
        comm_fm = fm.get("communication") if isinstance(fm.get("communication"), dict) else {}
        expertise = _as_str_list(fm.get("expertise_domains") or fm.get("expertise"))

        return Persona(
            id=ObsidianPersonaStore._slug_from_name(name),
            name=name,
            title=str(fm.get("title") or ""),
            tagline=str(fm.get("tagline") or ""),
            source=str(fm.get("source") or name),
            disc=PersonaDISC(**_filter_known(PersonaDISC, disc_fm)),
            enneagram=PersonaEnneagram(**_filter_known(PersonaEnneagram, enneagram_fm)),
            big_five=PersonaBigFive(**_filter_known(PersonaBigFive, big_five_fm)),
            mbti=str(fm.get("mbti") or "INTJ"),
            mental_models=_as_str_list(fm.get("mental_models")),
            expertise_domains=expertise,
            frameworks=_as_str_list(fm.get("frameworks")),
            key_quotes=_as_str_list(fm.get("key_quotes")),
            communication=PersonaCommunication(
                **_filter_known(PersonaCommunication, comm_fm),
            ),
            created_at=str(fm.get("created_at") or ""),
            updated_at=str(fm.get("updated_at") or ""),
        )

    @staticmethod
    def _slug_from_name(name: str) -> str:
        return (
            name.lower()
            .replace(" ", "-")
            .replace(".", "")
            .replace("'", "")
        ) or str(uuid.uuid4())

    # ─── Write ───────────────────────────────────────────────────────────

    def write(self, persona: Persona) -> Path | None:
        """Persist a persona as <vault>/Personas/<name>.md.

        Returns the path written, or None when the vault isn't
        configured. Existing files are overwritten — the operator
        is the source of truth.
        """
        if not self._vault_path:
            return None
        self.personas_dir.mkdir(parents=True, exist_ok=True)
        target = self.personas_dir / f"{persona.name}.md"
        body = self._render(persona)
        tmp = target.with_suffix(target.suffix + ".tmp")
        try:
            tmp.write_text(body, encoding="utf-8")
            tmp.replace(target)
        except OSError:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
            return None
        return target

    @staticmethod
    def _render(persona: Persona) -> str:
        try:
            import yaml  # noqa: PLC0415
        except ImportError:
            yaml = None  # type: ignore[assignment]
        now = datetime.now(timezone.utc).isoformat()
        frontmatter = {
            "type": "persona",
            "name": persona.name,
            "source": persona.source or persona.name,
            "title": persona.title,
            "tagline": persona.tagline,
            "mbti": persona.mbti,
            "disc": {
                "primary": persona.disc.primary,
                "secondary": persona.disc.secondary,
            },
            "enneagram": {
                "type": persona.enneagram.type,
                "wing": persona.enneagram.wing,
            },
            "big_five": {
                "openness": persona.big_five.openness,
                "conscientiousness": persona.big_five.conscientiousness,
                "extraversion": persona.big_five.extraversion,
                "agreeableness": persona.big_five.agreeableness,
                "neuroticism": persona.big_five.neuroticism,
            },
            "mental_models": list(persona.mental_models),
            "expertise_domains": list(persona.expertise_domains),
            "frameworks": list(persona.frameworks),
            "key_quotes": list(persona.key_quotes),
            "communication": {
                "tone": persona.communication.tone,
                "vocabulary_level": persona.communication.vocabulary_level,
                "preferred_format": persona.communication.preferred_format,
                "avoid": list(persona.communication.avoid),
            },
            "created_at": persona.created_at or now,
            "updated_at": now,
        }
        if yaml is not None:
            fm_block = yaml.safe_dump(
                frontmatter,
                sort_keys=False,
                allow_unicode=True,
                default_flow_style=False,
            )
        else:
            fm_block = "\n".join(f"{k}: {v}" for k, v in frontmatter.items()) + "\n"
        body = "# " + persona.name + "\n\n"
        if persona.tagline:
            body += f"> {persona.tagline}\n\n"
        body += "## Source\n\n" + (persona.source or persona.name) + "\n\n"
        if persona.mental_models:
            body += "## Mental Models\n\n"
            body += "\n".join(f"- {m}" for m in persona.mental_models) + "\n\n"
        if persona.key_quotes:
            body += "## Key Quotes\n\n"
            body += "\n".join(f"> {q}" for q in persona.key_quotes) + "\n\n"
        return f"---\n{fm_block}---\n\n{body}"


# ─── Helpers ────────────────────────────────────────────────────────────


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def _filter_known(model: type, data: dict) -> dict:
    """Drop keys the Pydantic model doesn't declare so unknown
    frontmatter keys (e.g. older schema variants) don't crash."""
    if not isinstance(data, dict):
        return {}
    known: Iterable[str] = model.model_fields.keys()  # type: ignore[attr-defined]
    return {k: v for k, v in data.items() if k in known}

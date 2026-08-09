"""Sync Engine schema — Pydantic models for the ArkaOS /arka update pipeline."""

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ViolationKind = Literal["stamped", "malformed", "unreadable"]

# Text lifted out of scanned files is untrusted: it reaches the operator's
# terminal through format_report and sync-state.json through write_sync_state.
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_MAX_QUOTED_TEXT = 200


def _neutralize(value: str) -> str:
    """Escape C0/DEL control characters, then cap the result.

    Escaping first, capping second, so the cap bounds what is actually
    emitted: one ESC expands to four characters, and a 2 MB marker would
    otherwise be held three times over (report, errors, state file).
    """
    escaped = _CONTROL_RE.sub(lambda m: f"\\x{ord(m.group()):02x}", value)
    if len(escaped) <= _MAX_QUOTED_TEXT:
        return escaped
    return f"{escaped[:_MAX_QUOTED_TEXT]}…(+{len(escaped) - _MAX_QUOTED_TEXT})"


class MarkerViolation(BaseModel):
    """One `arka:feature` marker that no literal consumer would ever match.

    Structured rather than a prose string: the /arka update Phase-4 JSON
    consumer needs `kind` to choose between restamp, repair and warn, and
    recovering it by substring-matching a sentence is not an interface.
    """

    model_config = ConfigDict(frozen=True)

    path: Path
    line: int
    kind: ViolationKind
    marker: str
    reason: str

    @field_validator("marker", "reason")
    @classmethod
    def _sanitize(cls, value: str) -> str:
        """Neutralize untrusted text at the only door into the model.

        A validator, not a formatting step: a marker carrying `\\x1b[2J`
        would otherwise clear the operator's screen (CWE-117), and no caller
        — including one rehydrating this model from JSON — can bypass it.
        """
        return _neutralize(value)

    def describe(self) -> str:
        """Phase-prefixed, linter-style `path:line: reason` terminal line."""
        tail = f" — {self.marker}" if self.marker else ""
        return f"Markers: {self.path}:{self.line}: {self.reason}{tail}"


class InjectionRefusal(BaseModel):
    """One feature injection the injector declined to perform.

    Structured and named for the same reason as `MarkerViolation`: the
    state it refuses to create — marker blocks sealed inside somebody
    else's unterminated HTML comment — is precisely what the audit
    classifies as "swallowed" once the file is already corrupt (issue
    #509). A refusal recorded here is the same finding, one step earlier,
    while the document is still intact.

    `line` points at the unterminated `<!--`, not at the insertion point:
    that opening is what the operator has to close.
    """

    model_config = ConfigDict(frozen=True)

    path: Path
    feature: str
    line: int
    reason: str

    @field_validator("feature", "reason")
    @classmethod
    def _sanitize(cls, value: str) -> str:
        """Neutralize untrusted text at the only door into the model."""
        return _neutralize(value)

    def describe(self) -> str:
        """Phase-prefixed, linter-style `path:line: reason` terminal line."""
        return (
            f"Injection: {self.path}:{self.line}: refused to inject "
            f"{self.feature!r} — {self.reason}"
        )


class FeatureSpec(BaseModel):
    """A versioned feature that the sync engine can add, update, or deprecate."""

    name: str
    added_in: str
    mandatory: bool
    section_title: str
    detection_pattern: str
    content: str
    deprecated_in: str | None = None


class ChangeManifest(BaseModel):
    """Describes what changed between two ArkaOS versions during a sync run."""

    previous_version: str
    current_version: str
    is_first_sync: bool
    features: list[FeatureSpec] = Field(default_factory=list)
    new_features: list[str] = Field(default_factory=list)
    deprecated_features: list[str] = Field(default_factory=list)


class Project(BaseModel):
    """A project registered in the ArkaOS ecosystem."""

    path: str
    name: str
    ecosystem: str | None = None
    stack: list[str] = Field(default_factory=list)
    descriptor_path: str | None = None
    has_mcp_json: bool = False
    has_settings: bool = False


class McpSyncResult(BaseModel):
    """Result of syncing the .mcp.json file for a single project."""

    path: str
    status: str
    mcps_added: list[str] = Field(default_factory=list)
    mcps_removed: list[str] = Field(default_factory=list)
    mcps_updated: list[str] = Field(default_factory=list)
    mcps_preserved: list[str] = Field(default_factory=list)
    mcps_deferred: list[str] = Field(default_factory=list)
    final_mcp_list: list[str] = Field(default_factory=list)
    error: str | None = None
    optimizer_warnings: list[str] = Field(default_factory=list)


class SettingsSyncResult(BaseModel):
    """Result of syncing .claude/settings.local.json for a single project."""

    path: str
    status: str
    servers_added: list[str] = Field(default_factory=list)
    servers_removed: list[str] = Field(default_factory=list)
    error: str | None = None


class DescriptorSyncResult(BaseModel):
    """Result of syncing the project descriptor YAML for a single project."""

    path: str
    status: str
    changes: list[str] = Field(default_factory=list)
    error: str | None = None


class SkillSyncResult(BaseModel):
    """Result of syncing a single ecosystem skill file."""

    skill_name: str
    status: str
    features_added: list[str] = Field(default_factory=list)
    features_removed: list[str] = Field(default_factory=list)
    error: str | None = None


class ContentSyncResult(BaseModel):
    """Result of syncing content artefacts (CLAUDE.md, rules, hooks, constitution) for a project."""

    path: str
    status: str
    artefacts_updated: list[str] = Field(default_factory=list)
    artefacts_restamped: list[str] = Field(default_factory=list)
    artefacts_drifted: list[str] = Field(default_factory=list)
    artefacts_unchanged: list[str] = Field(default_factory=list)
    artefacts_errored: list[str] = Field(default_factory=list)
    error: str | None = None


class AgentProvisionResult(BaseModel):
    """Result of syncing baseline agents for a project."""

    path: str
    status: str
    agents_added: list[str] = Field(default_factory=list)
    agents_unchanged: list[str] = Field(default_factory=list)
    agents_errored: list[str] = Field(default_factory=list)
    error: str | None = None


class SyncReport(BaseModel):
    """Aggregated report produced at the end of a full /arka update run."""

    previous_version: str
    current_version: str
    new_features: list[str] = Field(default_factory=list)
    deprecated_features: list[str] = Field(default_factory=list)
    mcp_results: list[McpSyncResult] = Field(default_factory=list)
    settings_results: list[SettingsSyncResult] = Field(default_factory=list)
    descriptor_results: list[DescriptorSyncResult] = Field(default_factory=list)
    skill_results: list[SkillSyncResult] = Field(default_factory=list)
    content_results: list[ContentSyncResult] = Field(default_factory=list)
    agent_results: list[AgentProvisionResult] = Field(default_factory=list)
    # Non-canonical `arka:feature` markers found in the installed skills
    # tree. Structured, and not only folded into `errors`, so the JSON the
    # /arka update skill consumes can branch on `kind`: the stamped markers
    # of issue #492 were invisible precisely because no channel named them.
    marker_violations: list[MarkerViolation] = Field(default_factory=list)
    # Injections Phase 4 refused rather than perform. Filled by the Phase-4
    # consumer, like `skill_results`: choosing WHERE a section goes needs
    # judgement about the host's custom content, so the deterministic engine
    # owns the guard (core/sync/feature_injector.py) and not the placement.
    injection_refusals: list[InjectionRefusal] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class SyncError(BaseModel):
    """Structured sync error with grep-able code and context."""

    phase: str
    project_path: str
    code: str
    message: str
    context: dict = Field(default_factory=dict)
    retry_count: int = 0

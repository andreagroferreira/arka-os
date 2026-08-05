"""Sync Engine schema — Pydantic models for the ArkaOS /arka update pipeline."""

from pydantic import BaseModel, Field


class FeatureSpec(BaseModel):
    """A versioned feature that the sync engine can add, update, or deprecate."""

    name: str
    added_in: str
    mandatory: bool
    section_title: str
    detection_pattern: str
    content: str
    deprecated_in: str | None = None


class MigrationSpec(BaseModel):
    """A codemod that repairs a pattern predating some ArkaOS feature.

    Migrations answer the half of "align my projects" that content sync
    cannot: a project built before a feature existed may carry a shape the
    feature has since replaced. They only ever *propose* a diff — code is
    never rewritten under the operator (Terraform plan-before-apply).
    """

    name: str
    added_in: str
    description: str
    detect: str
    paths: list[str] = Field(default_factory=lambda: ["**/*.md"])
    replace: str | None = None
    guidance: str = ""


class MigrationHit(BaseModel):
    """One occurrence of a migration's pattern in one project file."""

    migration: str
    project: str
    file: str
    line: int
    excerpt: str
    proposed: str | None = None


class MigrationScanResult(BaseModel):
    """Aggregated migration scan for one sync run."""

    migrations_run: list[str] = Field(default_factory=list)
    hits: list[MigrationHit] = Field(default_factory=list)
    truncated: list[str] = Field(default_factory=list)
    proposal_path: str | None = None


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
    features_updated: list[str] = Field(default_factory=list)
    features_restamped: list[str] = Field(default_factory=list)
    features_adopted: list[str] = Field(default_factory=list)
    features_pending: list[str] = Field(default_factory=list)
    proposal_path: str | None = None
    error: str | None = None


class ContentSyncResult(BaseModel):
    """Result of syncing content artefacts (CLAUDE.md, rules, hooks, constitution) for a project."""

    path: str
    status: str
    artefacts_updated: list[str] = Field(default_factory=list)
    artefacts_restamped: list[str] = Field(default_factory=list)
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
    migrations: MigrationScanResult | None = None
    errors: list[str] = Field(default_factory=list)


class SyncError(BaseModel):
    """Structured sync error with grep-able code and context."""

    phase: str
    project_path: str
    code: str
    message: str
    context: dict = Field(default_factory=dict)
    retry_count: int = 0

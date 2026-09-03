"""Desired-state harness spec, keyed by runtime (PR-C1).

Until now the desired state of the operator's harness lived only inside
installer JavaScript: ``installer/hard-deny.js`` (the curated hard-deny
rules) and ``installer/adapters/claude-code.js`` (which hook events get
registered, with which scripts and timeouts). This module is the Python
port that ``drift`` (C1) and the ``ClaudeConfigManager`` (C2) read.

PARITY IS PINNED, NOT PROMISED: ``tests/python/test_harness_spec.py``
parses both JS sources and asserts this module matches them — rule
list in full, same content and order, hook registrations by
event/script/timeout/matcher. Editing either side without the other
fails the suite. The installer files remain the EXECUTED path until C4
flips ownership.

``config/settings-template.json`` is NOT a source here — the template
is not the npm installer's executed path (PR-B5 lesson: it declared
agent-provision for months while the adapter never registered it). It IS
pinned to this module the other way round (Runtime Sync PR1,
``TestSettingsTemplateParity``): install.sh, which ships but is not the
npm path, merges the template verbatim, and it carried 7 of these 11
registrations with a 5 s SessionStart until the pin existed.
"""

from __future__ import annotations

from dataclasses import dataclass

# Port of DEFAULT_HARD_DENY_RULES in installer/hard-deny.js — same
# rules, same order. Parity-pinned by test_harness_spec.py.
HARD_DENY_RULES: tuple[str, ...] = (
    # Destructive git operations
    "Bash(git push --force*)",
    "Bash(git push -f*)",
    "Bash(git reset --hard*)",
    "Bash(git clean -fd*)",
    "Bash(git branch -D*)",
    # Filesystem destruction
    "Bash(rm -rf /*)",
    "Bash(rm -rf ~/*)",
    "Bash(rm -rf ~)",
    "Bash(rm -rf .*)",
    # Secrets and credential paths
    "Read(~/.ssh/*)",
    "Read(~/.ssh/**)",
    "Read(~/.aws/credentials)",
    "Read(~/.aws/config)",
    "Read(~/.gnupg/*)",
    "Read(~/.gnupg/**)",
    "Read(~/.npmrc)",
    "Read(~/.docker/config.json)",
    "Read(~/.config/gh/*)",
    "Read(/etc/shadow)",
    "Read(/etc/sudoers)",
    # Writes to credential / config dirs
    "Write(~/.ssh/*)",
    "Write(~/.aws/credentials)",
    "Write(~/.gnupg/*)",
    "Write(~/.npmrc)",
    # Process / privilege escalation
    "Bash(sudo *)",
    "Bash(su -*)",
    "Bash(chmod 777*)",
    "Bash(curl * | sh*)",  # arka:sec-ok(curl-pipe-shell): deny-rule literal
    "Bash(curl * | bash*)",  # arka:sec-ok(curl-pipe-shell): deny-rule literal
    "Bash(wget * | sh*)",
    "Bash(wget * | bash*)",
)


@dataclass(frozen=True)
class HookRegistration:
    """One hook entry the adapter writes into ``settings.json``.

    ``script`` is the basename without extension — the adapter picks
    ``.sh`` / ``.ps1`` / ``.cjs`` per platform and fastpath, so drift
    matching accepts any of the three.
    """

    event: str
    script: str
    timeout: int
    matcher: str | None = None
    posix_only: bool = False
    conditional: bool = False


# Port of the settings.hooks registrations in
# installer/adapters/claude-code.js — parity-pinned.
_CLAUDE_CODE_HOOKS: tuple[HookRegistration, ...] = (
    HookRegistration("SessionStart", "session-start", 15),
    HookRegistration("UserPromptSubmit", "user-prompt-submit", 20),
    HookRegistration("PostToolUse", "post-tool-use", 5),
    HookRegistration("PostToolUseFailure", "post-tool-use", 5),
    HookRegistration("PreToolUse", "pre-tool-use", 10),
    HookRegistration(
        "PreToolUse",
        "agent-provision",
        10,
        matcher="Task",
        posix_only=True,
        conditional=True,
    ),
    HookRegistration("Stop", "stop", 5),
    HookRegistration("SubagentStop", "subagent-stop", 10),
    HookRegistration("SessionEnd", "session-end", 15),
    HookRegistration("PreCompact", "pre-compact", 30),
    HookRegistration("CwdChanged", "cwd-changed", 5),
)


@dataclass(frozen=True)
class SurfaceSpec:
    """One harness surface ArkaOS claims, with its default policy.

    ``policy`` values are the ``manifest.OwnershipPolicy`` vocabulary;
    kept as strings here so ``spec`` stays import-light (manifest
    imports spec, not the reverse).
    """

    surface: str
    policy: str
    detail: str


_CLAUDE_CODE_SURFACES: tuple[SurfaceSpec, ...] = (
    SurfaceSpec(
        "settings:hooks",
        "own-subset",
        "ArkaOS hook entries per event; user hooks on the same events stay",
    ),
    SurfaceSpec(
        "settings:autoMode.hard_deny",
        "own-subset",
        "Curated deny rules merged in; operator rules are never removed",
    ),
    SurfaceSpec(
        "settings:statusLine",
        "seed",
        "Branded status bar; an operator replacement is adopted once "
        "C2 owns the surface",
    ),
    SurfaceSpec(
        "settings:worktree",
        "seed",
        "worktree.baseRef default; an operator change is adopted once "
        "C2 owns the surface",
    ),
)


@dataclass(frozen=True)
class RuntimeSpec:
    """The desired harness state for one runtime."""

    runtime: str
    hook_registrations: tuple[HookRegistration, ...]
    hard_deny_rules: tuple[str, ...]
    surfaces: tuple[SurfaceSpec, ...]


_RUNTIME_SPECS: dict[str, RuntimeSpec] = {
    "claude-code": RuntimeSpec(
        runtime="claude-code",
        hook_registrations=_CLAUDE_CODE_HOOKS,
        hard_deny_rules=HARD_DENY_RULES,
        surfaces=_CLAUDE_CODE_SURFACES,
    ),
}

SUPPORTED_RUNTIMES: tuple[str, ...] = tuple(sorted(_RUNTIME_SPECS))


def spec_for(runtime: str) -> RuntimeSpec:
    """The :class:`RuntimeSpec` for ``runtime``.

    Raises ``ValueError`` for an unknown runtime — a silent empty spec
    would make drift report a perfectly-owned harness for a runtime
    this package knows nothing about.
    """
    try:
        return _RUNTIME_SPECS[runtime]
    except KeyError:
        raise ValueError(
            f"unknown runtime {runtime!r}; supported: {', '.join(SUPPORTED_RUNTIMES)}"
        ) from None

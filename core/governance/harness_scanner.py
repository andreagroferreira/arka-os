"""Harness config scanner — the agent's own configuration as attack surface.

Everything ArkaOS ships assumes the harness under it is trustworthy, and
nothing in the tree ever checked. ``doctor`` asks whether the install is
*healthy*; ``leak_scanner`` asks whether our *source* leaks client names;
``mcp-policy`` is about load performance. None of them read the settings
file, the hook commands, or the MCP servers that actually execute on the
operator's machine and ask whether they are safe.

The threat is concrete. A ``permissions.allow`` list with no ``deny`` is
a blank cheque the moment auto mode is on. A hook command that
interpolates an agent-controlled variable into a shell string is command
injection with the agent as the delivery mechanism. An MCP server pinned
to ``@latest`` hands a third party the right to change what runs on the
machine tomorrow, silently.

Read-only by contract. ``scan()`` takes a directory and returns findings
with a letter grade; it prints nothing, exits nothing, and touches
nothing. The ``--fix`` path is a later slice and must be able to trust
that a scan never mutated what it measured.

Never raises on hostile input. A settings file that is truncated,
binary, or full of nulls is a FINDING, not a traceback — a scanner that
dies on the config it was pointed at reports nothing at all, which is
the worst possible outcome for a security tool.

Engine behind ``npx arkaos shield`` and the ``doctor`` advisory section.
"""

from __future__ import annotations

import json
import re
import stat
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

_MAX_FILE_BYTES = 2 * 1024 * 1024


class Severity(StrEnum):
    """How much a finding costs. Declaration order is report order."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Points deducted from 100, per finding.
PENALTY: dict[Severity, int] = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 12,
    Severity.MEDIUM: 5,
    Severity.LOW: 2,
}

_GRADE_FLOORS = ((90, "A"), (80, "B"), (70, "C"), (60, "D"))


@dataclass(frozen=True)
class Finding:
    """One defect in the harness configuration.

    ``fix`` is not optional. A severity with no remediation is noise the
    operator learns to scroll past.
    """

    rule: str
    severity: Severity
    where: str
    detail: str
    fix: str

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity.value,
            "where": self.where,
            "detail": self.detail,
            "fix": self.fix,
        }


@dataclass
class ScanReport:
    """The result of scanning one harness config tree."""

    root: Path
    files_scanned: int = 0
    findings: list[Finding] = field(default_factory=list)

    @property
    def score(self) -> int:
        deducted = sum(PENALTY[f.severity] for f in self.findings)
        return max(0, 100 - deducted)

    @property
    def grade(self) -> str:
        # A single CRITICAL is a fail, whatever the arithmetic says. The
        # letter a human reads and the exit code CI gates on must point
        # the same direction — one CRITICAL scoring 75 (a "C") while the
        # process exits 2 is a mixed signal, and mixed signals get
        # security tools ignored.
        if self.by_severity(Severity.CRITICAL):
            return "F"
        for floor, letter in _GRADE_FLOORS:
            if self.score >= floor:
                return letter
        return "F"

    def by_severity(self, severity: Severity) -> list[Finding]:
        return [f for f in self.findings if f.severity is severity]

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "files_scanned": self.files_scanned,
            "score": self.score,
            "grade": self.grade,
            "findings": [f.to_dict() for f in self.findings],
        }


# --- secrets ---------------------------------------------------------------

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("AWS key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)
_SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I)
# Name suffixes that mean "a pointer TO the secret", not the secret:
# GOOGLE_APPLICATION_CREDENTIALS is a path, API_KEY_HELPER is a command.
_POINTER_NAME = re.compile(
    r"(_FILE|_PATH|_HELPER|_CMD|_COMMAND|_DIR|CREDENTIALS)$", re.I
)
# A value bound to a reference, a placeholder, or a filesystem path /
# command is not a leaked secret.
_NOT_A_SECRET = re.compile(
    r"^(\$\{?\w+\}?|<[^>]+>|x{3,}|your[-_ ]|changeme|\.{3}|example|"
    r"[~/.]|[A-Za-z]:[\\/])",
    re.IGNORECASE,
)


def secret_labels(text: str) -> list[str]:
    """Named secret patterns present in a blob of text."""
    if not isinstance(text, str):
        return []
    return [label for label, pat in _SECRET_PATTERNS if pat.search(text)]


def is_secret_binding(name: str, value: object) -> bool:
    """A KEY/TOKEN-named variable bound to a literal secret, not to a
    reference, a placeholder, or a path/command that POINTS at one.

    The false positive that kills a security tool is flagging
    ``GOOGLE_APPLICATION_CREDENTIALS=/path/sa.json`` — a pointer, not a
    secret. A name-based match only survives if the value also looks
    like an opaque credential; a value matching a real secret pattern
    (``secret_labels``) fires regardless of the name.
    """
    if not isinstance(value, str) or len(value.strip()) < 20:
        return False
    if secret_labels(value):
        return True  # value IS a credential — name is irrelevant
    if _NOT_A_SECRET.match(value.strip()):
        return False
    if not isinstance(name, str) or _POINTER_NAME.search(name):
        return False
    return bool(_SECRET_NAME.search(name))


# --- permissions -----------------------------------------------------------

# Claude Code permission-rule syntax is `Tool` or `Tool(pattern)`, where
# a Bash pattern is `command:args` (`Bash(git status:*)`). A rule is
# UNSCOPED when it grants the whole tool: bare `Bash`, `Bash()`,
# `Bash(*)`, or `Bash(*:*)` / `Bash(:*)` — the last two are the runtime's
# own "allow everything" forms, which the first draft missed entirely.
_UNSCOPED_RULE = re.compile(
    r"^(Bash|Write|Edit|MultiEdit|WebFetch|NotebookEdit|Read)"
    r"(\(\s*\*?\s*(:\s*\*\s*)?\))?$"
)
# The command a Bash rule authorises is the part before the first `:`.
_BASH_RULE = re.compile(r"^Bash\((?P<body>.*)\)$", re.DOTALL)
# Commands that are dangerous the moment they are allowed at all — a
# rule like `Bash(rm:*)` grants every rm, so the bare command name in
# the authorised position is enough. Matched against the command word
# of a Bash rule (`Bash(<cmd>:args)`), not against free text.
#
# Interpreters and shells are the load-bearing entries: allowing one is
# arbitrary code execution the instant the rule is active
# (`python -c '...'`, `sh -c '<anything>'`, `node -e`). They are a strict
# superset of `eval`, which is flagged — and the MCP surface
# (mcp-shell-command) and hook surface (_EVAL_OF_AGENT_VAR) already treat
# a raw shell as dangerous, so leaving them clean HERE was the scanner
# contradicting itself.
_SHELL_COMMANDS = ("sh", "bash", "zsh", "fish", "dash", "ksh")
# Lowercase only — the command word is lowercased before lookup, so a
# capitalized key here can never match (the Rscript bug: an entry the
# data declared dangerous that the code reported safe).
_INTERPRETERS = (
    "python", "python3", "node", "deno", "bun", "perl", "ruby", "php",
    "osascript", "rscript",
)
_DANGEROUS_COMMANDS = {
    "rm": "delete", "sudo": "privilege escalation", "eval": "eval",
    "chmod": "permission change", "chown": "ownership change",
    "curl": "network fetch", "wget": "network fetch", "nc": "raw socket",
    "ncat": "raw socket", "dd": "raw disk write", "mkfs": "filesystem format",
    "shutdown": "shutdown", "reboot": "reboot",
    **{s: "arbitrary shell execution" for s in _SHELL_COMMANDS},
    **{i: "arbitrary code execution" for i in _INTERPRETERS},
}
# Dangerous phrasings that need the full string, not just the command.
_DANGEROUS_RULE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\brm\b.*(-[a-z]*r|--recursive)"), "recursive delete"),
    (re.compile(r"\bsudo\b"), "privilege escalation"),
    (re.compile(r"\b(curl|wget)\b[^|]*\|\s*(ba|z)?sh"), "download piped to a shell"),
    (re.compile(r"\bchmod\b.*(777|-R\s+7)"), "world-writable chmod"),
    (re.compile(r"\beval\b"), "eval of arbitrary input"),
    (re.compile(r"\bgit\s+push\s+(--force|-f)\b"), "force push"),
    (re.compile(r"dangerously-skip-permissions"), "permission bypass"),
    (re.compile(r"git\s+reset\s+--hard"), "hard reset"),
)


def _as_list(value: object) -> list:
    """A config value that should be a list, made safe to iterate.

    ``permissions.allow`` bound to a scalar is not just invalid — it is
    the shape an attacker or a typo produces, and ``len()``/iteration on
    it is the crash this scanner exists to survive.
    """
    return value if isinstance(value, list) else []


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _bash_command_word(rule: str) -> str | None:
    """The command a `Bash(cmd:args)` rule authorises, lowercased."""
    match = _BASH_RULE.match(rule.strip())
    if not match:
        return None
    body = match.group("body").split(":", 1)[0].strip()
    words = body.split()
    if not words:
        return None
    return words[0].rsplit("/", 1)[-1].lower() or None


def _unscoped_finding(rule: str, where: str) -> Finding:
    tool = rule.split("(")[0]
    return Finding(
        rule="settings-unscoped-allow",
        severity=Severity.CRITICAL,
        where=where,
        detail=f"allow rule {rule!r} grants the whole tool — every "
               f"invocation, with no pattern to constrain it.",
        fix=f"Scope it: {tool}({_SCOPE_HINT.get(tool, '<pattern>')}).",
    )
_BYPASS_MODES = {"bypassPermissions", "acceptEdits"}
# A remediation the operator can paste. A generic "<pattern>" for a tool
# whose patterns are paths is a hint nobody acts on.
_SCOPE_HINT = {
    "Bash": "git status*",
    "Write": "src/**",
    "Edit": "src/**",
    "MultiEdit": "src/**",
    "NotebookEdit": "notebooks/**",
    "WebFetch": "domain:docs.anthropic.com",
}


def _no_deny_finding(allow: list, where: str) -> Finding:
    return Finding(
        rule="settings-no-deny",
        severity=Severity.HIGH,
        where=where,
        detail=(
            f"{len(allow)} allow rules and no deny list. An allow list "
            f"cannot express 'never do this even when a broader rule "
            f"matches' — in auto mode that is a blank cheque."
        ),
        fix="Add a permissions.deny list — see the hard-deny defaults in "
            "the ArkaOS install, or Claude Code's permission docs.",
    )


def _bypass_mode_finding(mode: str, where: str) -> Finding:
    return Finding(
        rule="settings-bypass-mode",
        severity=Severity.CRITICAL,
        where=where,
        detail=f"defaultMode is {mode!r} with no permissions.deny list to "
               f"stop it.",
        fix='Set defaultMode to "default", or add a permissions.deny list.',
    )


def _check_permissions(perms: dict, where: str) -> list[Finding]:
    """allow/deny/defaultMode — the blast radius of auto mode."""
    findings: list[Finding] = []
    allow = _as_list(perms.get("allow"))
    deny = _as_list(perms.get("deny"))
    if allow and not deny:
        findings.append(_no_deny_finding(allow, where))
    if perms.get("defaultMode") in _BYPASS_MODES and not deny:
        findings.append(_bypass_mode_finding(perms["defaultMode"], where))
    findings.extend(_check_allow_rules(allow, where))
    return findings


def _dangerous_allow_finding(rule: str, where: str) -> Finding | None:
    """A CRITICAL if the allow rule authorises a dangerous command,
    whether by its command word (`Bash(rm:*)`) or its phrasing."""
    command = _bash_command_word(rule)
    if command in _DANGEROUS_COMMANDS:
        return Finding(
            rule="settings-dangerous-allow",
            severity=Severity.CRITICAL,
            where=where,
            detail=f"allow rule {rule!r} authorises `{command}` "
                   f"({_DANGEROUS_COMMANDS[command]}) — every invocation "
                   f"of it, whatever the arguments.",
            fix="Remove it, or narrow the pattern to the exact "
                "invocations you trust.",
        )
    for pattern, label in _DANGEROUS_RULE:
        if pattern.search(rule):
            return Finding(
                rule="settings-dangerous-allow",
                severity=Severity.CRITICAL,
                where=where,
                detail=f"allow rule {rule!r} permits {label}.",
                fix="Remove it. If it is genuinely needed, gate it behind "
                    "an explicit prompt rather than an allow.",
            )
    return None


def _check_allow_rules(allow: list, where: str) -> list[Finding]:
    findings: list[Finding] = []
    for rule in allow:
        if not isinstance(rule, str):
            continue
        if _UNSCOPED_RULE.match(rule.strip()):
            findings.append(_unscoped_finding(rule, where))
            continue
        danger = _dangerous_allow_finding(rule, where)
        if danger is not None:
            findings.append(danger)
    return findings


def _check_env(env: dict, where: str) -> list[Finding]:
    """Secrets bound literally into the config."""
    return [
        Finding(
            rule="settings-secret-in-env",
            severity=Severity.CRITICAL,
            where=where,
            detail=f"{name} is bound to a literal value in the config file.",
            fix="Move it to the OS keychain or ~/.arkaos/keys.json and "
                "reference it, then rotate the exposed value.",
        )
        for name, value in env.items()
        if is_secret_binding(str(name), value)
    ]


# --- hooks -----------------------------------------------------------------

# An agent-controlled value interpolated into a shell string, unquoted.
# Everything the agent touches — the file it edited, the command it ran —
# reaches a hook through one of these.
_AGENT_VAR = r"\$\{?(CLAUDE_[A-Z_]+|TOOL_[A-Z_]+|file|file_path)\b"
_UNQUOTED_INTERPOLATION = re.compile(rf"""(?<!['"]){_AGENT_VAR}""")
# `eval "$X"` / `sh -c "$X"` runs the value even when it IS quoted —
# the quoting protects the surrounding shell, not the eval'd string.
_EVAL_OF_AGENT_VAR = re.compile(
    rf"""\b(eval|(ba|z)?sh\s+-c)\b[^\n]*{_AGENT_VAR}"""
)
_SILENCED = re.compile(r"(2>\s*/dev/null|\|\|\s*true)\s*$")


def _check_hook_command(command: str, where: str) -> list[Finding]:
    findings: list[Finding] = []
    if _UNQUOTED_INTERPOLATION.search(command) or \
            _EVAL_OF_AGENT_VAR.search(command):
        findings.append(Finding(
            rule="hook-command-injection",
            severity=Severity.CRITICAL,
            where=where,
            detail=(
                "an agent-controlled variable is interpolated into the "
                "shell command unquoted — a filename containing `; rm -rf ~` "
                "executes."
            ),
            fix='Quote it: "$CLAUDE_FILE_PATH". Better: read the payload '
                "from stdin instead of the environment.",
        ))
    if _SILENCED.search(command):
        findings.append(Finding(
            rule="hook-silences-errors",
            severity=Severity.MEDIUM,
            where=where,
            detail="the hook discards its own errors, so a hook that has "
                   "stopped working looks identical to one that works.",
            fix="Let it fail loudly, or log to a file you actually read.",
        ))
    return findings


def _check_hook_script(command: str, where: str) -> list[Finding]:
    """The file the hook executes — does it exist, can anyone rewrite it?"""
    path = _script_path(command)
    if path is None:
        return []
    if not path.exists():
        return [Finding(
            rule="hook-script-missing",
            severity=Severity.HIGH,
            where=where,
            detail=f"the hook points at {path}, which does not exist — the "
                   f"hook silently does nothing.",
            fix="Restore the script, or remove the hook. If it is an "
                "ArkaOS hook, `npx arkaos install --force` reinstalls it.",
        )]
    if _is_group_or_world_writable(path):
        return [Finding(
            rule="hook-world-writable",
            severity=Severity.HIGH,
            where=where,
            detail=f"{path} is writable by group or others — any local "
                   f"process can rewrite what the agent executes on every "
                   f"tool call.",
            fix=f"chmod go-w {path}",
        )]
    return []


def _script_path(command: str) -> Path | None:
    """The leading absolute path of a hook command, when it has one.

    ``expanduser`` on ``~unknownuser/x`` raises RuntimeError on some
    platforms — and a ``~baduser`` path is exactly the attacker-authored
    input this scanner must survive, not crash on.
    """
    words = command.strip().split()
    first = words[0] if words else ""
    if not first.startswith(("/", "~")):
        return None
    try:
        return Path(first).expanduser()
    except (RuntimeError, ValueError):
        return Path(first)


def _is_group_or_world_writable(path: Path) -> bool:
    try:
        mode = path.stat().st_mode
    except OSError:
        return False
    return bool(mode & (stat.S_IWGRP | stat.S_IWOTH))


def _check_hooks(hooks: dict, where: str) -> list[Finding]:
    findings: list[Finding] = []
    for event, entries in _as_dict(hooks).items():
        for command in _hook_commands(entries):
            at = f"{where} [{event}]"
            findings.extend(_check_hook_command(command, at))
            findings.extend(_check_hook_script(command, at))
    return findings


def _hook_commands(entries: object) -> list[str]:
    """Every `command` string under one hook event, however nested."""
    found: list[str] = []
    if isinstance(entries, dict):
        command = entries.get("command")
        if isinstance(command, str):
            found.append(command)
        for value in entries.values():
            found.extend(_hook_commands(value))
    elif isinstance(entries, list):
        for item in entries:
            found.extend(_hook_commands(item))
    return found


# --- MCP servers -----------------------------------------------------------

_RUNNERS = {"npx", "bunx", "pnpm", "uvx"}
_SHELLS = {"sh", "bash", "zsh", "fish", "dash"}
# A version pin at the END of the package spec — `@1.2.3`, `@^2`. A
# leading `@` (npm scope like `@1password/...`) is NOT a version, so the
# pattern must not match a scope that merely starts with a digit.
_PINNED = re.compile(r"[^@/]@[\dvV^~*x]")


def _check_mcp_server(name: str, config: dict, where: str) -> list[Finding]:
    findings: list[Finding] = []
    command = str(config.get("command") or "")
    args = [str(a) for a in _as_list(config.get("args"))]
    if command in _SHELLS and "-c" in args:
        findings.append(Finding(
            rule="mcp-shell-command",
            severity=Severity.HIGH,
            where=f"{where} [{name}]",
            detail="the server is a shell running an arbitrary string.",
            fix="Point the server at an executable, not at `sh -c`.",
        ))
    findings.extend(_check_mcp_package(name, command, args, where))
    findings.extend(
        Finding(
            rule="mcp-secret-in-env",
            severity=Severity.CRITICAL,
            where=f"{where} [{name}]",
            detail=f"{key} is bound to a literal value in the MCP config.",
            fix="Reference it as ${VAR} and rotate the exposed value.",
        )
        for key, value in _as_dict(config.get("env")).items()
        if is_secret_binding(str(key), value)
    )
    return findings


def _check_mcp_package(
    name: str, command: str, args: list[str], where: str
) -> list[Finding]:
    """Supply chain: what version of someone else's code runs tomorrow."""
    if command not in _RUNNERS:
        return []
    at = f"{where} [{name}]"
    findings: list[Finding] = []
    if any(a in ("-y", "--yes") for a in args):
        findings.append(Finding(
            rule="mcp-auto-install",
            severity=Severity.MEDIUM,
            where=at,
            detail=f"`{command} -y` installs without asking.",
            fix="Drop -y, or vendor the server.",
        ))
    package = next((a for a in args if not a.startswith("-")), None)
    if package and _is_unpinned(package):
        findings.append(_unpinned_finding(package, at))
    return findings


def _is_unpinned(package: str) -> bool:
    return package.endswith("@latest") or not _PINNED.search(package)


def _unpinned_finding(package: str, at: str) -> Finding:
    return Finding(
        rule="mcp-unpinned-package",
        severity=Severity.HIGH,
        where=at,
        detail=(
            f"{package!r} is not pinned to a version. Whatever the "
            f"publisher ships tomorrow runs on this machine, silently, "
            f"with the agent's permissions."
        ),
        fix=f"Pin it: {package.split('@latest')[0]}@<version>.",
    )


# --- instruction files -----------------------------------------------------

_INJECTION = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|your)\b", re.I),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.I),
)
# Zero-width and bidirectional-override characters: an invisible payload
# in a file a human reviewed and believed they had read.
_INVISIBLE = re.compile(r"[​-‏‪-‮⁦-⁩﻿]")


def _instruction_secrets(text: str, where: str) -> list[Finding]:
    return [
        Finding(
            rule="instructions-secret",
            severity=Severity.CRITICAL,
            where=where,
            detail=f"a {label} appears in an instruction file the agent "
                   f"loads into context on every session.",
            fix="Remove it and rotate the key.",
        )
        for label in secret_labels(text)
    ]


def _check_instruction_file(path: Path, where: str) -> list[Finding]:
    text = _read_text(path)
    if text is None:
        return []
    findings = _instruction_secrets(text, where)
    if any(pattern.search(text) for pattern in _INJECTION):
        findings.append(Finding(
            rule="instructions-injection",
            severity=Severity.HIGH,
            where=where,
            detail="the file contains prompt-injection phrasing.",
            fix="Delete the injection lines. Instruction files are trusted "
                "input — text pasted from elsewhere does not belong here.",
        ))
    if _INVISIBLE.search(text):
        findings.append(Finding(
            rule="instructions-invisible-characters",
            severity=Severity.HIGH,
            where=where,
            detail="the file contains zero-width or bidirectional-override "
                   "characters — instructions a reviewer cannot see.",
            fix="Strip them. No legitimate instruction needs them.",
        ))
    return findings


# --- reading ---------------------------------------------------------------


def _read_text(path: Path) -> str | None:
    """File contents, or None when unreadable. Never raises."""
    try:
        if path.stat().st_size > _MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _unparseable(where: str, detail: str) -> Finding:
    return Finding(
        rule="config-unparseable",
        severity=Severity.HIGH,
        where=where,
        detail=detail,
        fix="Fix the JSON, or reinstall with `npx arkaos install --force`.",
    )


def _parse_json(text: str, where: str) -> tuple[dict | None, list[Finding]]:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        return None, [_unparseable(where, (
            f"the file is not valid JSON ({exc}). The runtime is either "
            f"ignoring it or failing on it — either way, nothing in it is "
            f"in force."
        ))]
    except RecursionError:
        # Deeply nested JSON under the size cap. json can parse it into a
        # structure Python cannot walk — hostile, not fatal.
        return None, [_unparseable(
            where, "the file nests too deeply to process safely."
        )]
    if not isinstance(data, dict):
        return None, [
            _unparseable(where, "the file parses but is not an object.")
        ]
    return data, []


def _read_json(path: Path, where: str) -> tuple[dict | None, list[Finding]]:
    """Parsed JSON, or a finding.

    A config we cannot read is itself a finding. Skipping it silently
    would report a clean bill of health for a file nobody has validated
    — the one outcome a security tool must never produce.
    """
    text = _read_text(path)
    if text is None:
        return None, [Finding(
            rule="config-unreadable",
            severity=Severity.HIGH,
            where=where,
            detail="the file exists but cannot be read (too large, or "
                   "permissions).",
            fix="Check the file size and its permissions.",
        )]
    return _parse_json(text, where)


# --- the scan --------------------------------------------------------------

SETTINGS_FILES = ("settings.json", "settings.local.json")
MCP_FILES = (".mcp.json", "mcp.json")
INSTRUCTION_FILES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md")


def _scan_settings(path: Path, where: str) -> list[Finding]:
    data, problems = _read_json(path, where)
    if data is None:
        return problems
    findings: list[Finding] = []
    perms = data.get("permissions")
    if isinstance(perms, dict):
        findings.extend(_check_permissions(perms, where))
    env = data.get("env")
    if isinstance(env, dict):
        findings.extend(_check_env(env, where))
    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        findings.extend(_check_hooks(hooks, where))
    return findings


def _scan_mcp(path: Path, where: str) -> list[Finding]:
    data, problems = _read_json(path, where)
    if data is None:
        return problems
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return []
    return [
        finding
        for name, config in servers.items()
        if isinstance(config, dict)
        for finding in _check_mcp_server(str(name), config, where)
    ]


def _safe_scan_file(
    scanner, path: Path, name: str
) -> list[Finding]:
    """Run one file scanner behind a backstop.

    Every input path is type-guarded upstream, but "never raises" is a
    contract, not a hope: an unforeseen input must degrade to a finding,
    never to a traceback that the CLI reads as exit 1 and the doctor
    advisory reads as silence. This is the last line.
    """
    try:
        return scanner(path, name)
    except Exception as exc:  # deliberate backstop — never let a file crash the scan
        return [Finding(
            rule="scanner-error",
            severity=Severity.LOW,
            where=name,
            detail=f"the scanner could not process this file ({type(exc).__name__}). "
                   f"It was skipped — treat as unaudited, not as clean.",
            fix="Report this config shape to the ArkaOS maintainers.",
        )]


def scan(root: Path) -> ScanReport:
    """Scan a harness config tree. Read-only. Never raises."""
    try:
        root = Path(root).expanduser()
    except (RuntimeError, ValueError):
        root = Path(root)
    report = ScanReport(root=root)
    groups = (
        (SETTINGS_FILES, _scan_settings),
        (MCP_FILES, _scan_mcp),
        (INSTRUCTION_FILES, _check_instruction_file),
    )
    for names, scanner in groups:
        for name in names:
            path = root / name
            if path.is_file():
                report.files_scanned += 1
                report.findings.extend(_safe_scan_file(scanner, path, name))
    report.findings.sort(key=lambda f: (-PENALTY[f.severity], f.rule))
    return report

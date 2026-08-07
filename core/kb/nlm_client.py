"""NotebookLM chokepoint — the one door, and the guard stands at it.

D1 shipped ``core.egress`` with zero call sites. This module is the
first, and for NotebookLM the only one: every payload passes
``egress.policy.evaluate`` BEFORE a subprocess is constructed, so a
denied payload never reaches argv, an environment variable, a temp
file, or the CLI. What leaves is the redacted text the guard returned,
never the caller's original.

``evaluate`` rather than ``enforce`` — deliberately. ``enforce`` raises
:class:`~core.egress.policy.EgressDeniedError` and hands back only the
cleared text; this module needs the decision, because the telemetry
line carries both digests and the finding kinds. ``evaluate`` is
documented never to raise; the call is wrapped anyway, and a guard
that fails is a denial (``egress guard error: <type>``), never a send.

The tool is not vendored. ``notebooklm-py`` drives undocumented Google
endpoints and is a moving target, so the operator installs it (``uv
tool install``) and this module shells out to whatever is on PATH — or
reports its absence. Nothing here installs anything.

Degradation is a contract. Tool absent, timeout, nonzero exit,
rejected option, unusable or refused home — every one returns a
:class:`NotebookLMResult` carrying an ``[arka:source-skipped]``
marker, so the caller falls back to ``arka-research`` with the gap
declared. :func:`send` and :func:`check` never raise: every failure,
including a hostile argument, comes back as a result. The path
helpers below them take a ``Path`` at their word.

``QG D2 r<N>, <Reviewer> <ID>`` citations below record why a
non-obvious choice is there. The round numbers are PER REVIEWER —
Eduardo's r1 ran after Francisca's r4 — so two citations reading r1
are not the same moment.
"""

from __future__ import annotations

import contextlib
import errno
import importlib
import json
import math
import os
import pkgutil
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import core.egress as egress
from core.egress import policy

# The injected process runner. Only ``subprocess.run``'s shape is ever
# passed; typing it keeps `.returncode` and `.stdout` checked rather
# than reached on an ``object`` (QG D2 r2, Francisca M9).
CompletedProcess = subprocess.CompletedProcess[str]
Runner = Callable[..., CompletedProcess]

BINARY = "notebooklm"
DEFAULT_TIMEOUT = 180
_MAX_TIMEOUT = 86_400  # one day; beyond this the value is a mistake

# argv is the guard's blind spot: anything appended after the guarded
# --input is a file the policy never saw, and duplicate-option
# handling in argparse/click/typer is last-wins, so the UNGUARDED file
# is the one that uploads (QG D2 r1, Francisca B3).
#
# There is no argv pass-through. A validated pass-through was tried and
# was wrong: it screened tokens starting with a dash and let a bare
# positional straight through, and `add-source` is exactly the kind of
# subcommand that takes a positional source — so `/etc/passwd` reached
# argv with the guard reporting ok (QG D2 r2, Francisca B1). Callers
# now pass typed options and this module renders argv, so an
# unvalidated string has no path to it by construction.
ALLOWED_ACTIONS: frozenset[str] = frozenset(
    {"add-source", "ask", "report", "mindmap"}
)
ALLOWED_FORMATS: frozenset[str] = frozenset({"markdown", "json", "text"})
# Notebook names: alphanumeric, dot, underscore, dash. No separator,
# so no traversal path — but the first character excludes the dot too,
# because a leading-dot first class let the bare string ".." through
# (QG D2 r1, Eduardo B7). No leading dash either, or the value itself
# reads as an option to the CLI's parser (``--notebook --input`` is
# not the pair it looks like).
_NOTEBOOK_PATTERN = "[A-Za-z0-9_][A-Za-z0-9._-]{0,63}"
_NOTEBOOK_RE = re.compile(rf"\A{_NOTEBOOK_PATTERN}\Z")


def notebooklm_home(home: Path | None = None) -> Path:
    """``NOTEBOOKLM_HOME`` or ``~/.arkaos/notebooklm``, at call time.

    The env value is expanded and required to be absolute. The
    ``home`` ARGUMENT was hardened to ``Path`` while the environment
    — the door operators actually use — took anything: a relative
    value put the 0600 payload under the process's cwd, routinely a
    git working tree, and a literal ``~/nlm`` from a file parsed
    without shell expansion created a directory named ``~`` there
    (QG D2 r5, Francisca B1).
    """
    override = os.environ.get("NOTEBOOKLM_HOME", "").strip()
    if override:
        return _absolute_override(override)
    return _default_payload_dir(home or _own_home())


def _default_payload_dir(home: Path) -> Path:
    """Where the payload directory lives when no env override is set.

    One source of truth: the screen restated the same literal and the
    two disagreed on the fallback, so a move of the default would have
    left the screen guarding a path nothing uses (QG D2 r11,
    Francisca M4 — the r2 M4 defect, recurring).
    """
    return home / ".arkaos" / "notebooklm"


def _absolute_override(override: str) -> Path:
    """The env value, expanded and required to be absolute."""
    try:
        resolved = Path(override).expanduser()
    except RuntimeError as exc:
        # ``~teammate/x``, ``~+/x``, ``~-/x``: expanduser raises
        # RuntimeError, which check() does not catch, so the fix for
        # the relative-path hole opened a raising one (QG D2 r6,
        # Francisca B1).
        raise ValueError("NOTEBOOKLM_HOME could not be expanded") from exc
    if not resolved.is_absolute():
        raise ValueError("NOTEBOOKLM_HOME must be an absolute path")
    return resolved


def _own_home() -> Path:
    """``Path.home()``, as a refusal rather than a RuntimeError.

    No HOME and no passwd entry — a container or a CI runner.
    """
    try:
        return Path.home()
    except RuntimeError as exc:
        raise ValueError("home directory could not be determined") from exc


def telemetry_path(home: Path | None = None) -> Path:
    return (
        (home or Path.home())
        / ".arkaos" / "telemetry" / "notebooklm-usage.jsonl"
    )


def redaction_config_path(home: Path | None = None) -> Path:
    """The identifier list ``home`` implies.

    Delegates to D1: this was a verbatim copy of the very function the
    previous round made public so callers would stop duplicating it,
    which left two sources of truth for one path
    (QG D2 r2, Francisca M4).
    """
    return policy.default_redaction_config_path(home)


@dataclass
class NotebookLMResult:
    """Outcome of one call.

    ``ok`` is False whenever the caller must fall back; ``denied`` (the
    guard refused) and ``degraded`` (the run produced no usable
    result) say which.
    Branching on ``degraded`` alone reads a DENIED payload as a success
    path — the field said "must fall back" and only half meant it
    (QG D2 r1, Eduardo B6).
    """

    action: str
    ok: bool = False
    denied: bool = False
    degraded: bool = False
    reason: str = ""
    finding_kinds: list[str] = field(default_factory=list)
    stdout: str = ""
    # The resolved CLI path, set by check(). Its own field: stdout used
    # to carry it, so one attribute meant "what the tool printed" on
    # one path and "where the tool is" on the other
    # (QG D2 r1, Francisca M9).
    binary: str = ""
    # The original payload's digest — what an operator greps to ask
    # "did this ever leave?". redacted_sha256 is what actually left
    # (QG D2 r1, Francisca M2: one field meant both, so the grep
    # answered False for a payload that DID leave).
    payload_sha256: str = ""
    redacted_sha256: str = ""

    @property
    def marker(self) -> str:
        """The line a caller puts on record when this result is unusable."""
        return (
            f"[arka:source-skipped] notebooklm ({self.reason})"
            if not self.ok
            else ""
        )

    def to_telemetry(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "ok": self.ok,
            "denied": self.denied,
            "degraded": self.degraded,
            "reason": self.reason,
            # KINDS only — see _denial for why.
            "finding_kinds": list(self.finding_kinds),
            "payload_sha256": self.payload_sha256,
            "redacted_sha256": self.redacted_sha256,
        }


# The package spec carries its OWN quotes, and the sentence carries
# none: wrapping the whole command in quotes meant the operator pasted
# it bare, and in zsh the square brackets are glob syntax — the line
# died with "no matches found" before uv ever ran (QG D2 r1, Eduardo B12).
_ABSENT = (
    f"{BINARY} not on PATH; install it with: "
    f"uv tool install 'notebooklm-py[browser]'"
)


def check(home: Path | None = None) -> NotebookLMResult:
    """Is the CLI usable? Reports, never installs.

    The standalone probe: it prepares the payload directory to prove it
    is usable. ``send`` deliberately does NOT go through here — it
    resolves the binary itself and prepares the directory only after
    the guard has cleared the payload, so nothing is created on disk
    for a payload that will be denied (QG D2 r2, Francisca M6).
    """
    # check() does not go through _rejected_input, so it screens the
    # same two home failures itself: a non-Path (QG D2 r1 Eduardo B4,
    # narrowed r2 Eduardo B1) and an unresolvable one, which otherwise
    # fell into the NOTEBOOKLM_HOME arm below and sent the operator to
    # inspect a variable they never set (QG D2 r7, Francisca M2).
    rejected = _rejected_home(home)
    if rejected is not None:
        return _degraded("check", rejected)
    binary = shutil.which(BINARY)
    if not binary:
        return _degraded("check", _ABSENT)
    try:
        _prepare_home(home)
    except OSError as exc:
        return _degraded("check", f"payload home unusable: {_why(exc)}")
    except ValueError as exc:
        return _degraded("check", f"payload home rejected: {exc}")
    return NotebookLMResult(action="check", ok=True, binary=binary)


def _rejected_ancestor(target: Path) -> str | None:
    """Refuse a path reached through an attacker-plantable link.

    Every component, the final one included: the leaf was guarded
    while ``mkdir(parents=True)`` followed everything above it (r9),
    and ``Path.parents`` excludes the node, so a link at ``.arkaos``
    went through (r10). Ownership, not existence — ``/tmp`` is itself
    a link on macOS, so a link owned by the current user or root is
    the operator's own.
    """
    for component in [*reversed(target.parents), target]:
        try:
            info = component.lstat()
        except (FileNotFoundError, NotADirectoryError):
            # Nothing there to follow. Absent components are routine,
            # and a plain file where a directory belongs gets its
            # accurate reason from the mkdir, not from here.
            continue
        except (OSError, ValueError, TypeError) as exc:
            # One lstat, not is_symlink()+lstat, which raised before
            # this handler saw it (r10 M1). ValueError: `lstat` on a
            # NUL byte, which escaped the boundary (r13 B1).
            # TypeError is defensive only (r14, Francisca M3).
            return f"path is not a usable filesystem path: {_why(exc)}"
        if not stat.S_ISLNK(info.st_mode):
            continue
        if info.st_uid not in (os.getuid(), 0):
            return "path traverses a symlink owned by another user"
    return None


def _prepare_home(home: Path | None) -> Path:
    """The payload directory, created 0700 — never through a symlink.

    Three layers, learned one per round: the ancestors are screened
    (QG D2 r9, Francisca B1), the leaf is refused before mkdir would
    follow it (r1, Francisca M5), and ownership and mode are settled
    on one ``O_NOFOLLOW`` descriptor rather than across separate
    lookups an attacker could swap between (r2, Francisca M5).
    """
    target = notebooklm_home(home)
    traversal = _rejected_ancestor(target)
    if traversal is not None:
        raise ValueError(traversal)
    if target.is_symlink():
        # Before mkdir: a symlink to a path that does not exist yet
        # would otherwise be FOLLOWED and the directory created at the
        # attacker's end of it.
        raise ValueError("path is a symlink")
    target.mkdir(parents=True, exist_ok=True)
    fd = _open_dir_nofollow(target)
    try:
        if os.fstat(fd).st_uid != os.getuid():
            raise ValueError("path is not owned by the current user")
        os.fchmod(fd, 0o700)
    finally:
        os.close(fd)
    return target


def _open_dir_nofollow(target: Path) -> int:
    """A descriptor on *target* that provably did not follow a link."""
    try:
        return os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        # mkdir has already succeeded, so the leaf was a directory
        # a moment ago: failing to open it without following a link
        # means the leaf is a symlink now. Linux reports ELOOP here,
        # macOS ENOTDIR.
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise ValueError("path is a symlink") from exc
        raise


def send(
    text: object,
    action: str = "add-source",
    *,
    home: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    notebook: str | None = None,
    output_format: str | None = None,
    runner: Runner = subprocess.run,
) -> NotebookLMResult:
    """Send one payload to NotebookLM, or explain why nothing was sent.

    The guard runs FIRST: a denial returns before any process
    plumbing exists. ``runner`` is injectable so tests can prove the
    subprocess was never built. ``notebook`` and ``output_format`` are
    rendered into argv by THIS module — no raw pass-through.
    """
    # ONCE, before the try: computing it inside the handler re-entered
    # a screen that can refuse, and the second raise left the public
    # boundary — the r1 Eduardo B5 shape again (r13, Francisca B1).
    trail = _trail_home(home)
    try:
        return _send(text, action, home, timeout, notebook,
                     output_format, runner)
    except Exception as exc:  # the boundary claim is absolute
        return _record(
            _degraded(_label(action), f"client error: {type(exc).__name__}"),
            trail,
        )


def _label(action: object) -> str:
    """The action name safe to PERSIST.

    ``reason`` was scrubbed of paths and the caller's ``action`` string
    was not, so a refused call with an action of
    ``/Users/<operator>/clients/<name>/Q3.md`` wrote that path and that
    identifier into the telemetry file — on a call that never left the
    machine (QG D2 r2, Francisca B2). Only a known action is echoed.

    The isinstance guard is load-bearing, not defensive typing: an
    unhashable action (a list or dict, the natural shape from a
    JSON-driven caller) makes the membership test raise TypeError.
    That happened twice per call — once inside ``_send`` and again in
    ``send``'s own handler — so the second escaped and the public
    boundary raised (QG D2 r1, Eduardo B5).
    """
    if not isinstance(action, str) or action not in ALLOWED_ACTIONS:
        return "invalid-action"
    return action


def _send(
    text: object,
    action: str,
    home: Path | None,
    timeout: int,
    notebook: str | None,
    output_format: str | None,
    runner: Runner,
) -> NotebookLMResult:
    label = _label(action)
    trail = _trail_home(home)
    options = _options(
        label, action, home, timeout, notebook, output_format, runner
    )
    if isinstance(options, NotebookLMResult):
        return _record(options, trail)
    binary = shutil.which(BINARY)
    if not binary:
        return _record(_degraded(label, _ABSENT), trail)
    cleared = _cleared_to_send(text, label, home)
    if isinstance(cleared, NotebookLMResult):
        return _record(cleared, trail)
    text_out, digest = cleared
    return _record(
        _run(text_out, digest, label, home, timeout, options, binary, runner),
        trail,
    )


def _options(
    label: str,
    action: object,
    home: object,
    timeout: object,
    notebook: str | None,
    output_format: str | None,
    runner: object,
) -> list[str] | NotebookLMResult:
    """The validated option tokens, or the refusal.

    Every caller-influenced value is matched against a closed set or a
    closed pattern, so nothing reaches argv — or ``subprocess`` —
    unscreened (QG D2 r2, Francisca B1; QG D2 r3, Francisca M7
    added ``timeout``, the one left out of its own thesis).

    Union return, not a ``(value, sentinel)`` tuple: dropping the
    isinstance check fails typecheck, where dropping a tuple sentinel
    is silent — and this is the argv refusal (QG D2 r3, Francisca M6).
    """
    rejection = _rejected_input(action, home, timeout, notebook,
                                output_format, runner)
    if rejection is not None:
        return _degraded(label, rejection)
    options: list[str] = []
    if notebook is not None:
        options += ["--notebook", notebook]
    if output_format is not None:
        options += ["--format", output_format]
    return options


def _trail_home(home: object) -> Path | None:
    """Where the telemetry line goes for a call using *home*.

    A REFUSED home must not be the trail's destination: recording
    against it re-created the very directory the refusal exists to
    prevent — ``_record`` mkdirs ``home/.arkaos/telemetry`` — so a
    refusal wrote into the cwd it had just declined to use (QG D2 r8,
    found closing Francisca B1).
    """
    try:
        rejected = _rejected_home(home)
    except Exception:
        # TOTAL by construction: `send` resolves the trail BEFORE its
        # try, so a raise here would leave the public boundary — and
        # resolving it inside the handler instead is what let the
        # second raise escape in the first place (QG D2 r13,
        # Francisca B1).
        return None
    if rejected is not None:
        return None
    return home if isinstance(home, Path) else None


def _rejected_input(
    action: object,
    home: object,
    timeout: object,
    notebook: str | None,
    output_format: str | None,
    runner: object,
) -> str | None:
    """Why these inputs may not be used, or None.

    Membership is tested only on strings: an unhashable action or
    format raises TypeError from ``in`` (QG D2 r1, Eduardo B5).
    """
    if not isinstance(action, str) or action not in ALLOWED_ACTIONS:
        return f"action not allowed; known: {sorted(ALLOWED_ACTIONS)}"
    rejected_home = _rejected_home(home)
    if rejected_home is not None:
        return rejected_home
    rejected_option = _rejected_option(timeout, notebook, output_format)
    if rejected_option is not None:
        return rejected_option
    # runner was the last public argument still reaching the
    # catch-all with an unnamed reason (QG D2 r8, Francisca M3).
    if not callable(runner):
        return "runner must be callable"
    return None


def _rejected_option(
    timeout: object, notebook: str | None, output_format: str | None
) -> str | None:
    """Why one of the CLI options may not be used, or None."""
    if not _valid_timeout(timeout):
        return (
            "timeout must be a finite number of seconds in "
            f"(0, {_MAX_TIMEOUT}]"
        )
    if notebook is not None and not _valid_notebook(notebook):
        return f"notebook must match {_NOTEBOOK_PATTERN}"
    if output_format is not None and not _valid_format(output_format):
        return f"format not allowed; known: {sorted(ALLOWED_FORMATS)}"
    return None


def _valid_format(output_format: object) -> bool:
    return (
        isinstance(output_format, str) and output_format in ALLOWED_FORMATS
    )


def _valid_timeout(timeout: object) -> bool:
    """A finite, positive, day-bounded number of seconds.

    bool is an int subclass, so True would otherwise pass as a 1s
    timeout. inf and 10**30 passed a sign-and-type check and made
    ``subprocess.run`` raise OverflowError, which ``_invoke`` does not
    catch — so the validator whose whole job is to say "positive
    number" handed the runner a number it cannot take (QG D2 r7,
    Francisca M3).
    """
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        return False
    return math.isfinite(timeout) and 0 < timeout <= _MAX_TIMEOUT


def _rejected_home(home: object) -> str | None:
    """Why *home* may not be used, or None.

    Both screens run BEFORE anything touches disk, because
    ``policy.evaluate`` writes D1's audit trail and SALT under
    ``home/.arkaos/egress`` before ``_prepare_home`` sees anything:
    guarding only the payload home left the salt — the value that
    makes D1's token digests non-reversible — at a planted link's
    target (QG D2 r9, Francisca B1), and ``Path.home()`` raising
    reached D1's path helper as "client error" (r6, Francisca B1).
    """
    if home is None:
        if _home_unresolvable():
            return "home directory could not be determined"
        return _rejected_resources(None)
    if not isinstance(home, Path):
        return f"home must be a Path, not {type(home).__name__}"
    return _rejected_shape(home) or _rejected_resources(home)


def _rejected_resources(home: Path | None) -> str | None:
    """Screen every path a call reads or writes under *home*.

    Screening ``home/.arkaos`` alone left two positions and one whole
    door open: ``Path.parents`` excludes the node, and the ``home is
    None`` branch — the door every production caller uses — had no
    screen at all. An attacker owning the link owns
    ``redaction-clients.json``, hence the guard's whole notion of a
    client identifier, so a real client name left the machine
    unredacted with ok=True (QG D2 r10, Francisca B1).
    """
    for resource in _resources_under(home):
        traversal = _rejected_ancestor(resource)
        if traversal is not None:
            return f"payload home rejected: {traversal}"
    return None


def _resources_under(home: Path | None) -> tuple[Path, ...]:
    """Every path a call reads or writes. The payload directory is
    listed by its DEFAULT location; an env override is screened in
    ``_prepare_home``, which owns that door."""
    return (
        _default_payload_dir(home or Path.home()),
        telemetry_path(home),
        *(helper(home) for helper in _EGRESS_PATH_HELPERS),
    )


def _egress_path_helpers() -> tuple[Callable[[Path | None], Path], ...]:
    """Every ``default_*_path`` D1 exports, discovered rather than
    listed.

    A hand-written list missed ``allowlist.default_allowlist_path``,
    which ``policy.evaluate`` READS — and an attacker owning that file
    turns a denial into an allow (QG D2 r12, Francisca B1). Discovery
    means a fifth helper is screened the day D1 adds it, instead of
    the day someone notices.
    """
    return tuple(
        getattr(module, name)
        for module in _egress_modules()
        for name in sorted(dir(module))
        if name.startswith("default_") and name.endswith("_path")
    )


def _egress_modules() -> list[ModuleType]:
    """Every module in ``core.egress``, enumerated from the package.

    A literal tuple was self-maintaining over HELPERS and hand-listed
    over MODULES: ``redact`` was in neither the code's tuple nor the
    test's, and the spec asserted a universal that held only because
    ``redact`` happens to export no path helper today — by
    coincidence, not construction (QG D2 r13, Francisca B2).
    """
    return [
        importlib.import_module(f"{egress.__name__}.{info.name}")
        for info in pkgutil.iter_modules(egress.__path__)
    ]


_EGRESS_PATH_HELPERS = _egress_path_helpers()


def _rejected_shape(home: Path) -> str | None:
    """The env door was hardened for absoluteness in r5 and the
    ARGUMENT door was not, so a relative home put the 0600 payload,
    the telemetry trail, the egress audit trail AND the audit salt
    under the process's cwd — routinely a git working tree, where
    `git add -A` stages them (QG D2 r8, Francisca B1). When a value
    has two doors into one resource, a fix on one is a spec change
    for both."""
    if not home.is_absolute():
        return "home must be an absolute path"
    return None


def _home_unresolvable() -> bool:
    """True when no ``home`` was given and the OS cannot supply one.

    Tested unconditionally. A first version skipped the probe whenever
    ``NOTEBOOKLM_HOME`` was set, on the premise that an override makes
    the default irrelevant — false, because D1's
    ``default_redaction_config_path`` also falls back to
    ``Path.home()`` and never consults that variable. A container with
    no HOME and a hand-set NOTEBOOKLM_HOME is the realistic config,
    and it reached the catch-all (QG D2 r7, Francisca B1).
    """
    try:
        Path.home()
    except RuntimeError:
        return True
    return False


def _valid_notebook(notebook: object) -> bool:
    return isinstance(notebook, str) and bool(_NOTEBOOK_RE.match(notebook))


def _cleared_to_send(
    text: object, action: str, home: Path | None
) -> tuple[str, str] | NotebookLMResult:
    """``(redacted_text, payload_digest)``, or the result that denies it.

    Runs BEFORE any process plumbing exists, so a denied payload never
    reaches argv, an env var or a temp file. ``evaluate`` rather than
    ``enforce``: the decision carries BOTH digests, and the telemetry
    must key on the original payload — an operator asking "did this
    ever leave?" greps the text they wrote, not its redaction (QG D2
    r1, Francisca M2).

    Union return: this is the egress denial, the module's core safety
    property, and it was the last refusal still riding a tuple
    sentinel the type checker cannot enforce (QG D2 r3, Francisca M6).
    """
    try:
        decision = policy.evaluate(
            text, "notebooklm", home=home,
            config_path=redaction_config_path(home),
        )
    except Exception as exc:  # the guard itself failed — deny, not send
        return _degraded(action, f"egress guard error: {type(exc).__name__}")
    if not decision.allowed or decision.redacted_text is None:
        return _denial(action, decision)
    return decision.redacted_text, decision.payload_sha256


def _denial(action: str, decision: policy.EgressDecision) -> NotebookLMResult:
    """KINDS only — a finding token names a client identifier, a secret
    label or a home path (D1 audit contract)."""
    kinds = [f.kind for f in decision.findings]
    return NotebookLMResult(
        action=action, denied=True,
        reason="egress denied: " + ", ".join(kinds),
        finding_kinds=kinds,
        payload_sha256=decision.payload_sha256,
    )


def _run(
    cleared: str,
    digest: str,
    action: str,
    home: Path | None,
    timeout: int,
    options: list[str],
    binary: str,
    runner: Runner,
) -> NotebookLMResult:
    redacted_digest = policy.payload_digest(cleared)
    target = _payload_dir(action, home, digest)
    if isinstance(target, NotebookLMResult):
        return target
    try:
        payload_file = _write_payload(cleared, target)
    except OSError as exc:
        return _degraded(action, f"payload not writable: {_why(exc)}", digest)
    argv = [binary, action, "--input", str(payload_file), *options]
    try:
        return _outcome(
            argv, action, timeout, digest, redacted_digest, runner
        )
    finally:
        # A real finally: the plain call this replaced left the
        # operator's research on disk on every unhandled path, and on
        # Ctrl-C during the 180s timeout (QG D2 r1, Francisca B2).
        _unlink_quiet(payload_file)


def _outcome(
    argv: list[str],
    action: str,
    timeout: int,
    digest: str,
    redacted_digest: str,
    runner: Runner,
) -> NotebookLMResult:
    """What the CLI's run amounts to. Called inside ``_run``'s finally,
    so the payload file is removed whichever way this returns."""
    proc = _invoke(argv, action, timeout, digest, runner)
    if isinstance(proc, NotebookLMResult):
        return proc
    if proc.returncode != 0:
        return _degraded(action, f"{BINARY} exited {proc.returncode}", digest)
    return NotebookLMResult(
        action=action, ok=True, stdout=proc.stdout or "",
        payload_sha256=digest, redacted_sha256=redacted_digest,
    )


def _invoke(
    argv: list[str], action: str, timeout: int, digest: str, runner: Runner
) -> CompletedProcess | NotebookLMResult:
    """Run the CLI. Failures are degradations, never exceptions."""
    try:
        return runner(
            argv, capture_output=True, text=True, timeout=timeout,
            shell=False,  # argv list, never a command string
        )
    except subprocess.TimeoutExpired:
        return _degraded(action, f"timed out after {timeout}s", digest)
    except (OSError, ValueError) as exc:
        # ValueError too: a NUL in argv raises it, and the contract
        # says degrade, not crash (QG D2 r1, Francisca B1).
        return _degraded(
            action, f"could not run {BINARY}: {_why(exc)}", digest
        )


def _payload_dir(
    action: str, home: Path | None, digest: str
) -> Path | NotebookLMResult:
    """The prepared directory, or the degradation that explains itself.

    Separate from the write so an unusable home is not reported as an
    unwritable payload: the two have different remedies, and the
    wrong label sends the operator to the wrong one.
    """
    try:
        return _prepare_home(home)
    except OSError as exc:
        return _degraded(
            action, f"payload home unusable: {_why(exc)}", digest
        )
    except ValueError as exc:
        return _degraded(action, f"payload home rejected: {exc}", digest)


def _write_payload(cleared: str, target: Path) -> Path:
    """The redacted payload in a 0600 file under NOTEBOOKLM_HOME.

    A file rather than argv: a command line is visible to every
    process on the machine, and the redacted text may still be the
    operator's research.
    """
    fd, name = tempfile.mkstemp(prefix="payload-", suffix=".txt", dir=target)
    # surrogatepass mirrors policy.payload_digest: a lone surrogate is
    # routine input the guard already judged, and crashing here
    # re-opened the hole D1 closed one layer down (QG D2 r1, Francisca B1).
    with os.fdopen(fd, "w", encoding="utf-8", errors="surrogatepass") as fh:
        fh.write(cleared)
    os.chmod(name, 0o600)
    return Path(name)


def _degraded(action: str, reason: str, digest: str = "") -> NotebookLMResult:
    return NotebookLMResult(
        action=action, degraded=True, reason=reason, payload_sha256=digest
    )


def _record(result: NotebookLMResult, home: Path | None) -> NotebookLMResult:
    """Append one telemetry line. Best-effort: never fails the call.

    0700 dir, 0600 file, matching the D1 audit trail: the record of a
    decision must not be protected less than the payload it describes
    (QG D2 r1, Francisca B4 — it was 0644 in a 0755 dir).

    Symlink-hardened on the same terms as ``_prepare_home``: the
    directory was chmod'ed and the trail opened THROUGH the path, so a
    link under ``~/.arkaos`` took a victim directory to 0700 and got
    the trail written inside it — the hardening stopped three
    functions short (QG D2 r3, Francisca M2).
    """
    try:
        path = telemetry_path(home)
        line = json.dumps(
            {"ts": datetime.now(UTC).isoformat(), **result.to_telemetry()},
            sort_keys=True,
        )
        _write_trail(path, line)
    except Exception:
        pass
    return result


def _write_trail(path: Path, line: str) -> None:
    """Append *line* to a 0600 trail in a 0700 directory, following no
    link at either level.

    Three mechanisms, all proven load-bearing by mutation: the
    ancestors via ``_rejected_ancestor``, the directory via
    ``_open_dir_nofollow``, the file via ``O_NOFOLLOW``.

    No ``is_symlink()`` pre-check here, unlike :func:`_prepare_home`,
    and the distinction is the diagnostic rather than reachability:
    that pre-check is reachable — it fires on a dangling
    symlink and gives the operator "rejected: path is a symlink"
    instead of "unusable: FileExistsError". Here the exception is
    swallowed by :func:`_record`, so a pre-check buys no reason anyone
    will read (QG D2 r3, Francisca M2; refined QG D2 r1, Eduardo B9).
    """
    traversal = _rejected_ancestor(path)
    if traversal is not None:
        raise ValueError(traversal)
    path.parent.mkdir(parents=True, exist_ok=True)
    dir_fd = _open_dir_nofollow(path.parent)
    try:
        os.fchmod(dir_fd, 0o700)
    finally:
        os.close(dir_fd)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as handle:
        os.fchmod(fd, 0o600)
        handle.write(line + "\n")


def _why(exc: BaseException) -> str:
    """An error's SHAPE, never its message.

    ``str(OSError)`` embeds the path it failed on, which for this
    module is routinely under the operator's home — the reason field
    is persisted, so it must carry no more than the type and errno
    (QG D2 r1, Francisca B4).
    """
    errno = getattr(exc, "errno", None)
    return (
        f"{type(exc).__name__}(errno={errno})"
        if errno is not None
        else type(exc).__name__
    )


def _unlink_quiet(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink()

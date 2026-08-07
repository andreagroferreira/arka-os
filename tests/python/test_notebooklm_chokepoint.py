"""core.kb.nlm_client — order, argv, and what reaches disk.

The load-bearing property is ORDER: the egress guard runs before any
process plumbing exists. A test that only checks "denied payloads are
not sent" would pass on an implementation that builds the command,
writes the file, and then decides — so the spy below fails the test if
the builder ran at all.
"""

import ast
import errno
import json
import os
import subprocess
from pathlib import Path

import pytest

from core.kb import nlm_client
from core.kb.nlm_client import NotebookLMResult, check, send

REPO_ROOT = Path(__file__).resolve().parents[2]


def _name(code: int) -> str:
    """The OSError subclass name Python raises for *code*."""
    return type(OSError(code, "x")).__name__


CLIENTS = ("acme-alpha", "betacorp")


def _imported_names(node: ast.AST, package: str) -> set[str]:
    """Absolute module names one import statement pulls in.

    ``from ..kb import x`` inside ``core.workflow`` resolves to
    ``core.kb`` — the relative form slipped past the first version of
    the import-graph test (QG D2 r1, Francisca M3).
    """
    if isinstance(node, ast.Import):
        return {alias.name for alias in node.names}
    if not isinstance(node, ast.ImportFrom):
        return set()
    if not node.level:
        return {node.module or ""}
    parts = package.split(".")
    base = parts[: len(parts) - node.level + 1]
    return {".".join([*base, node.module or ""]).rstrip(".")}


def _module_kb_imports(path: Path, package: str) -> list[str]:
    """Modules under ``core.kb`` that *path* imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        found += [
            name
            for name in _imported_names(node, package)
            if name == "core.kb" or name.startswith("core.kb.")
        ]
    return found


def _module_path(module: str) -> Path | None:
    base = REPO_ROOT / Path(*module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _core_imports(path: Path, package: str) -> set[str]:
    """Every ``core.*`` module *path* imports, relative forms resolved."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        names |= _imported_names(node, package)
    return {name for name in names if name.startswith("core.")}


def _imports_kb_transitively(root: str) -> list[str]:
    """``["core.workflow.x -> core.kb", ...]`` — the CLOSURE, not one hop.

    A one-hop check passes while a gate reaches ``core.kb`` through any
    intermediate module, which is the same outage
    (QG D2 r1, Francisca M3).
    """
    offenders: list[str] = []
    seen: set[str] = set()
    frontier = [root]
    while frontier:
        module = frontier.pop()
        if module in seen:
            continue
        seen.add(module)
        path = _module_path(module)
        if path is None:
            continue
        files = (
            sorted(path.parent.rglob("*.py"))
            if path.name == "__init__.py"
            else [path]
        )
        for file in files:
            rel = file.relative_to(REPO_ROOT).with_suffix("")
            pkg = ".".join(rel.parts[:-1])
            for hit in _module_kb_imports(file, pkg):
                offenders.append(f"{file.relative_to(REPO_ROOT)} -> {hit}")
            frontier += [
                dep for dep in _core_imports(file, pkg) if dep not in seen
            ]
    return sorted(offenders)


@pytest.fixture(autouse=True)
def sandboxed_home(tmp_path, monkeypatch):
    """No test in this file may reach the operator's real home.

    Writing the tilde test the first time, an absolute-expanding value
    in a REFUSAL parametrisation created a directory in the real home
    before the assertion could fail. A guard that depends on nobody
    adding such a value again is discipline; this is structure
    (QG D2 r6, Francisca M2)."""
    fake = tmp_path / "sandbox-home"
    fake.mkdir()
    monkeypatch.setenv("HOME", str(fake))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake))
    return fake


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A tmp HOME with a redaction config, and NOTEBOOKLM_HOME inside it."""
    home = tmp_path / "home"
    (home / ".arkaos").mkdir(parents=True)
    (home / ".arkaos" / "redaction-clients.json").write_text(
        json.dumps({"clients": list(CLIENTS)}), encoding="utf-8"
    )
    monkeypatch.setenv("NOTEBOOKLM_HOME", str(home / ".arkaos" / "notebooklm"))
    monkeypatch.setattr(
        nlm_client.shutil, "which", lambda name: f"/usr/local/bin/{name}"
    )
    return home


class Spy:
    """Records the argv it was handed, so a test can assert it never was."""

    def __init__(self, returncode=0, stdout="ok", raises=None):
        self.calls: list[list[str]] = []
        self.kwargs: list[dict] = []
        self.returncode = returncode
        self.stdout = stdout
        self.raises = raises

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        self.kwargs.append(kwargs)
        if self.raises:
            raise self.raises
        return subprocess.CompletedProcess(
            argv, self.returncode, stdout=self.stdout, stderr=""
        )


class PayloadReader:
    """Reads the payload DURING the call — it is removed afterwards.

    Reading it after ``send`` returns would fail, and rightly so: the
    file's removal in a finally is itself a pinned contract.
    """

    def __init__(self):
        self.text = None
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        path = Path(argv[argv.index("--input") + 1])
        # surrogatepass mirrors the writer: a lone surrogate is a
        # payload shape the guard judges and the file carries.
        self.text = path.read_text(
            encoding="utf-8", errors="surrogatepass"
        )
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")


class TestGuardRunsFirst:
    def test_denied_payload_never_reaches_a_subprocess(self, env):
        spy = Spy()
        result = send("report on acme-alpha2026", home=env, runner=spy)
        assert result.denied is True
        assert result.ok is False
        assert spy.calls == []  # the builder never ran

    def test_denied_result_names_kinds_not_tokens(self, env):
        """Finding TOKENS are client identifiers, secret labels and
        home paths — the D1 audit contract keeps them out of anything
        persisted or returned."""
        spy = Spy()
        result = send("acme-alpha2026 numbers", home=env, runner=spy)
        assert result.finding_kinds == ["client-identifier"]
        assert "acme" not in result.reason.lower()
        assert "acme" not in json.dumps(result.to_telemetry()).lower()

    def test_missing_redaction_config_denies_and_sends_nothing(
        self, tmp_path, monkeypatch
    ):
        home = tmp_path / "bare"
        (home / ".arkaos").mkdir(parents=True)
        monkeypatch.setenv("NOTEBOOKLM_HOME", str(home / "nlm"))
        monkeypatch.setattr(
            nlm_client.shutil, "which", lambda name: "/usr/local/bin/x"
        )
        spy = Spy()
        result = send("anything at all", home=home, runner=spy)
        assert result.denied is True
        assert "redaction-config-missing" in result.finding_kinds
        assert spy.calls == []

    def test_guard_failure_denies_rather_than_sending(self, env, monkeypatch):
        monkeypatch.setattr(
            nlm_client.policy, "evaluate",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        spy = Spy()
        result = send("clean text", home=env, runner=spy)
        assert result.ok is False
        assert "egress guard error: RuntimeError" in result.reason
        assert spy.calls == []


class TestNothingTouchesDiskBeforeTheGuard:
    """QG D2 r1, Francisca M1: the spy proved only that the RUNNER
    never ran. Criterion 1 also names a temp file — and a mutant that
    wrote the caller's RAW text to a 0600 file before the guard
    survived the whole suite."""

    def test_denied_send_leaves_no_file_behind(self, env):
        spy = Spy()
        result = send("report on acme-alpha2026", home=env, runner=spy)
        assert result.denied is True
        target = nlm_client.notebooklm_home(env)
        # Stronger than "empty": since the home is prepared only after
        # the guard clears the payload, a denied send does not even
        # create the directory (QG D2 r2, Francisca M6).
        assert not target.exists()

    def test_mkstemp_never_runs_before_the_guard(self, env, monkeypatch):
        order: list[str] = []
        real_mkstemp = nlm_client.tempfile.mkstemp
        real_evaluate = nlm_client.policy.evaluate

        def spy_mkstemp(*args, **kwargs):
            order.append("mkstemp")
            return real_mkstemp(*args, **kwargs)

        def spy_evaluate(*args, **kwargs):
            order.append("evaluate")
            return real_evaluate(*args, **kwargs)

        monkeypatch.setattr(nlm_client.tempfile, "mkstemp", spy_mkstemp)
        monkeypatch.setattr(nlm_client.policy, "evaluate", spy_evaluate)
        send("clean research question", home=env, runner=Spy())
        assert order[0] == "evaluate"
        assert "mkstemp" in order

    def test_denied_send_never_reaches_mkstemp_at_all(
        self, env, monkeypatch
    ):
        monkeypatch.setattr(
            nlm_client.tempfile, "mkstemp",
            lambda *a, **k: pytest.fail("payload file created before guard"),
        )
        result = send("acme-alpha2026 numbers", home=env, runner=Spy())
        assert result.denied is True


class TestArgvIsClosed:
    """QG D2 r1, Francisca B3 and QG D2 r2, Francisca B1: argv was
    an unvalidated pass-through placed after the guarded --input, so a
    caller could hand the CLI a local file the guard never saw. The
    first fix screened only tokens starting with a dash and let a bare
    positional through, and `add-source` is exactly the subcommand
    that takes one. There is no pass-through any more: the module
    renders argv from typed options.
    """

    def test_there_is_no_raw_pass_through_parameter(self):
        """The structural half: a signature with no free-form argv
        sequence cannot leak one, whatever the validation does."""
        import inspect

        params = inspect.signature(send).parameters
        assert "extra_args" not in params
        assert set(params) == {
            "text", "action", "home", "timeout", "notebook",
            "output_format", "runner",
        }

    @pytest.mark.parametrize(
        "notebook",
        [
            "/etc/passwd",            # the r2 B1 positional
            "../../etc/shadow",       # traversal
            "a b",                    # whitespace
            "a\x00b",                 # NUL
            "a\nb",                   # newline
            # TRAILING newline: $ matches just before one and \Z does
            # not, so swapping the anchor let `--notebook research\n`
            # reach argv and no test noticed (QG D2 r5, Francisca B3).
            "research\n",
            "a\n",
            "--input",                # an option in value position
            "x" * 65,                 # over the length bound
            "",                       # empty
            123,                      # not even a string
        ],
    )
    def test_hostile_notebook_values_are_refused(self, env, notebook):
        spy = Spy()
        result = send(
            "clean text", home=env, runner=spy, notebook=notebook
        )
        assert result.ok is False
        assert "notebook must match" in result.reason
        assert spy.calls == []

    def test_a_valid_notebook_is_rendered_by_this_module(self, env):
        spy = Spy()
        result = send(
            "clean text", home=env, runner=spy, notebook="research-2026"
        )
        assert result.ok is True
        assert spy.calls[0][-2:] == ["--notebook", "research-2026"]

    @pytest.mark.parametrize("fmt", sorted(nlm_client.ALLOWED_FORMATS))
    def test_every_allowed_format_is_exercised(self, env, fmt):
        """--format was a member of the allowed set no test touched
        (QG D2 r2, Francisca M2): parametrized over the set itself, so
        adding a member cannot silently skip it."""
        spy = Spy()
        result = send("clean text", home=env, runner=spy, output_format=fmt)
        assert result.ok is True
        assert spy.calls[0][-2:] == ["--format", fmt]

    @pytest.mark.parametrize("fmt", ["exe", "/etc/passwd", "", 7])
    def test_formats_outside_the_set_are_refused(self, env, fmt):
        spy = Spy()
        result = send("clean text", home=env, runner=spy, output_format=fmt)
        assert result.ok is False
        assert "format not allowed" in result.reason
        assert spy.calls == []

    def test_nothing_a_caller_supplies_lands_after_the_payload(self, env):
        """The property B1 was about: everything after --input <file>
        is rendered from validated options, in this module's order."""
        spy = Spy()
        send(
            "clean text", home=env, runner=spy,
            notebook="research-2026", output_format="json",
        )
        argv = spy.calls[0]
        assert argv[:3] == ["/usr/local/bin/notebooklm", "add-source",
                            "--input"]
        assert argv[4:] == ["--notebook", "research-2026",
                            "--format", "json"]

    @pytest.mark.parametrize(
        "action",
        [
            "--input", "add-source\x00evil", "rm-rf", 123, None,
            # Unhashable: `action in ALLOWED_ACTIONS` raises TypeError
            # on these, and it ran twice per call — once in _send and
            # again in send's own handler — so the second escaped and
            # the public boundary RAISED (QG D2 r1, Eduardo B5). The
            # natural shape from a JSON-driven caller.
            [], {}, set(), ["add-source"],
        ],
    )
    def test_action_outside_the_allowed_set_is_refused(self, env, action):
        spy = Spy()
        result = send("clean text", action=action, home=env, runner=spy)
        assert result.ok is False
        assert "action not allowed" in result.reason
        assert spy.calls == []

    @pytest.mark.parametrize("fmt", [[], {}, set()])
    def test_unhashable_format_is_refused_not_raised(self, env, fmt):
        """The same membership hazard on the other closed set."""
        spy = Spy()
        result = send("clean text", home=env, runner=spy, output_format=fmt)
        assert result.ok is False
        assert "format not allowed" in result.reason
        assert spy.calls == []

    @pytest.mark.parametrize("notebook", ["..", "...", ".", ".hidden"])
    def test_a_dot_leading_notebook_is_refused(self, env, notebook):
        """The first character class allowed a dot, so the bare string
        '..' matched a pattern whose comment claimed 'no traversal'
        (QG D2 r1, Eduardo B7)."""
        spy = Spy()
        result = send("clean text", home=env, runner=spy, notebook=notebook)
        assert result.ok is False
        assert "notebook must match" in result.reason
        assert spy.calls == []


class TestWhatLeaves:
    def test_only_the_redacted_text_reaches_the_cli(self, env):
        reader = PayloadReader()
        result = send(
            "the Acme-Alpha quarterly numbers", home=env, runner=reader
        )
        assert result.ok is True
        assert "Acme-Alpha" not in reader.text
        assert "[CLIENT-1]" in reader.text

    def test_payload_goes_in_a_file_not_the_command_line(self, env):
        spy = Spy()
        send("plain research question", home=env, runner=spy)
        argv = spy.calls[0]
        assert "plain research question" not in " ".join(argv)
        assert argv[0].endswith("notebooklm")
        assert "--input" in argv

    def test_subprocess_is_never_a_shell(self, env):
        spy = Spy()
        send("plain text", home=env, runner=spy)
        assert spy.kwargs[0]["shell"] is False
        assert isinstance(spy.calls[0], list)

    def test_payload_file_is_0600_and_removed_afterwards(self, env):
        seen = {}

        def capture(argv, **kwargs):
            path = Path(argv[argv.index("--input") + 1])
            seen["mode"] = path.stat().st_mode & 0o777
            seen["path"] = path
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        send("text", home=env, runner=capture)
        assert seen["mode"] == 0o600
        assert not seen["path"].exists()

    def test_notebooklm_home_is_0700(self, env):
        send("text", home=env, runner=Spy())
        target = nlm_client.notebooklm_home(env)
        assert target.stat().st_mode & 0o777 == 0o700


class TestDegradationContract:
    def assert_degraded(self, result: NotebookLMResult, fragment: str):
        assert result.ok is False
        assert result.degraded is True
        assert fragment in result.reason
        assert result.marker.startswith("[arka:source-skipped] notebooklm (")

    def test_unwritable_payload_degrades(self, env, monkeypatch):
        """Criterion 7 names this failure mode and no test reached it:
        every test set NOTEBOOKLM_HOME, so the branch never ran (QG D2
        r1, Francisca M8)."""
        def refuse(*args, **kwargs):
            raise OSError(13, "denied")

        monkeypatch.setattr(nlm_client.tempfile, "mkstemp", refuse)
        spy = Spy()
        result = send("clean text", home=env, runner=spy)
        self.assert_degraded(result, "payload not writable")
        assert spy.calls == []
        # The reason is persisted: shape and errno, never the path.
        assert "denied" not in result.reason
        assert "PermissionError(errno=13)" in result.reason

    def test_a_symlinked_home_is_refused_not_followed(
        self, env, tmp_path, monkeypatch
    ):
        """A project .envrc pointing NOTEBOOKLM_HOME at a symlink used
        to narrow the victim directory to 0700 and write the operator's
        research inside it (QG D2 r1, Francisca M5)."""
        victim = tmp_path / "victim"
        victim.mkdir(mode=0o755)
        link = tmp_path / "link"
        link.symlink_to(victim)
        monkeypatch.setenv("NOTEBOOKLM_HOME", str(link))
        spy = Spy()

        result = send("clean text", home=env, runner=spy)

        self.assert_degraded(result, "payload home rejected")
        assert "symlink" in result.reason
        assert spy.calls == []
        assert list(victim.iterdir()) == []
        assert victim.stat().st_mode & 0o777 == 0o755

    def test_a_leaf_swapped_after_the_check_is_still_refused(
        self, env, tmp_path, monkeypatch
    ):
        """The TOCTOU the O_NOFOLLOW descriptor exists for: an attacker
        with write access to the parent swaps the leaf between the
        symlink check and the chmod. Simulated deterministically by
        performing the swap inside the check itself — without
        O_NOFOLLOW the victim directory gets chmod'ed to 0700 (QG D2
        r2, Francisca M5)."""
        victim = tmp_path / "victim"
        victim.mkdir(mode=0o755)
        target = tmp_path / "nlm-home"
        target.mkdir()
        monkeypatch.setenv("NOTEBOOKLM_HOME", str(target))
        real_is_symlink = Path.is_symlink

        def swap_then_answer(self):
            answer = real_is_symlink(self)
            if self == target and not answer:
                self.rmdir()
                self.symlink_to(victim)
            return answer

        monkeypatch.setattr(Path, "is_symlink", swap_then_answer)
        spy = Spy()

        result = send("clean text", home=env, runner=spy)

        self.assert_degraded(result, "payload home rejected")
        assert spy.calls == []
        assert victim.stat().st_mode & 0o777 == 0o755
        assert list(victim.iterdir()) == []

    def test_a_home_owned_by_someone_else_is_refused(
        self, env, tmp_path, monkeypatch
    ):
        foreign = tmp_path / "foreign"
        foreign.mkdir()
        monkeypatch.setenv("NOTEBOOKLM_HOME", str(foreign))
        real_fstat = os.fstat

        def not_ours(fd, *args, **kwargs):
            info = real_fstat(fd, *args, **kwargs)
            return type(
                "S", (), {"st_uid": os.getuid() + 1, "st_mode": info.st_mode}
            )()

        monkeypatch.setattr(nlm_client.os, "fstat", not_ours)
        spy = Spy()

        result = send("clean text", home=env, runner=spy)

        self.assert_degraded(result, "payload home rejected")
        assert "owned" in result.reason
        assert spy.calls == []

    def test_an_unusable_home_degrades_without_leaking_the_path(
        self, env, tmp_path, monkeypatch
    ):
        """No monkeypatch: a real unusable home — a plain file where a
        parent directory should be."""
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("x", encoding="utf-8")
        blocked = blocker / "notebooklm"
        monkeypatch.setenv("NOTEBOOKLM_HOME", str(blocked))

        result = send("clean text", home=env, runner=Spy())

        self.assert_degraded(result, "payload home unusable")
        assert str(blocked) not in result.reason
        assert "NotADirectoryError" in result.reason

    @pytest.mark.parametrize("value", ["relative-dir", "./x", "..", "nlm/x"])
    def test_a_non_absolute_env_home_is_refused(
        self, env, tmp_path, monkeypatch, value
    ):
        """The ARGUMENT door was hardened to Path and the ENVIRONMENT
        door — the one operators use — took anything: a relative value
        put the 0600 payload under the process's cwd, and a literal
        `~/nlm` from a file parsed without shell expansion created a
        directory named `~` there (QG D2 r5, Francisca B1)."""
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        monkeypatch.setenv("NOTEBOOKLM_HOME", value)
        spy = Spy()

        probe = check(env)
        sent = send("clean text", home=env, runner=spy)

        for result in (probe, sent):
            assert result.ok is False
            assert "must be an absolute path" in result.reason
        assert spy.calls == []
        # Nothing was created relative to the process's cwd.
        assert list(cwd.iterdir()) == []

    @pytest.mark.parametrize(
        "value", ["~nosuchuser42/nlm", "~+/x", "~-/x"]
    )
    def test_an_unresolvable_tilde_form_is_refused_not_raised(
        self, env, monkeypatch, value
    ):
        """`expanduser()` raises RuntimeError on a `~user` that has no
        passwd entry, and check() catches only OSError and ValueError —
        so the fix for the relative-path hole opened a RAISING one
        (QG D2 r6, Francisca B1)."""
        monkeypatch.setenv("NOTEBOOKLM_HOME", value)
        spy = Spy()

        probe = check(env)
        sent = send("clean text", home=env, runner=spy)

        for result in (probe, sent):
            assert isinstance(result, NotebookLMResult)
            assert result.ok is False
            assert "could not be expanded" in result.reason
        assert spy.calls == []

    @pytest.mark.parametrize("relative", ["worktree-home", ".", "", "a/b"])
    def test_a_relative_home_argument_is_refused_on_both_doors(
        self, tmp_path, monkeypatch, relative
    ):
        """The env door got absoluteness in r5 and the ARGUMENT door
        did not, so `send(home=Path("worktree-home"))` returned ok=True
        and wrote the payload, the telemetry trail, the egress audit
        trail AND the audit salt under the process's cwd — a git
        working tree, where `git add -A` stages them. The salt is what
        makes D1's token digests non-reversible (QG D2 r8, Francisca
        B1). A value with two doors into one resource needs the fix on
        both, and the test parametrised over the doors."""
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)
        monkeypatch.setattr(
            nlm_client.shutil, "which", lambda name: f"/usr/local/bin/{name}"
        )
        spy = Spy()
        home = Path(relative)

        probe = check(home)
        sent = send("clean text", home=home, runner=spy)

        for result in (probe, sent):
            assert result.ok is False
            assert "home must be an absolute path" in result.reason
        assert spy.calls == []
        assert list(cwd.iterdir()) == []

    @pytest.mark.parametrize("runner", ["not-callable", 7, None, object()])
    def test_a_non_callable_runner_is_named_not_caught(self, env, runner):
        """The last public argument that still reached the catch-all
        with an unnamed 'client error' (QG D2 r8, Francisca M3)."""
        result = send("clean text", home=env, runner=runner)
        assert result.ok is False
        assert "runner must be callable" in result.reason
        assert "client error" not in result.reason

    @pytest.mark.parametrize("override_set", [True, False])
    def test_an_unresolvable_home_is_refused_on_both_axes(
        self, tmp_path, monkeypatch, override_set
    ):
        """Every home test varied ONE axis. B1 lived where they cross:
        with NOTEBOOKLM_HOME SET, a short-circuit skipped the probe on
        the premise that an override makes the default irrelevant —
        but D1's config-path helper also falls back to `Path.home()`
        and never reads that variable, so the RuntimeError reached the
        catch-all as "client error" (QG D2 r7, Francisca B1)."""
        if override_set:
            target = tmp_path / "nlm"
            target.mkdir()
            monkeypatch.setenv("NOTEBOOKLM_HOME", str(target))
        else:
            monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)

        def no_home(cls):
            raise RuntimeError("Could not determine home directory")

        monkeypatch.setattr(Path, "home", classmethod(no_home))
        monkeypatch.setattr(
            nlm_client.shutil, "which", lambda name: f"/usr/local/bin/{name}"
        )
        spy = Spy()

        probe = check()
        sent = send("clean text", runner=spy)

        for result in (probe, sent):
            assert result.ok is False
            assert "home directory could not be determined" in result.reason
            assert "client error" not in result.reason
            assert "guard error" not in result.reason
            # The operator never set this variable in the False case.
            assert "payload home rejected" not in result.reason
        assert spy.calls == []

    @pytest.mark.parametrize(
        "timeout", [float("inf"), float("-inf"), 10**30, 86_401, float("nan")]
    )
    def test_a_non_finite_or_absurd_timeout_is_refused(self, env, timeout):
        """A sign-and-type check blessed `inf` and `10**30`, and the
        real runner then raised OverflowError — which `_invoke` does
        not catch — so the validator whose job is to say "positive
        number" produced "client error: OverflowError" instead
        (QG D2 r7, Francisca M3)."""
        spy = Spy()
        result = send("clean text", home=env, runner=spy, timeout=timeout)
        assert result.ok is False
        assert "timeout must be a finite number" in result.reason
        assert "86400" in result.reason
        assert spy.calls == []

    def test_the_path_helper_itself_refuses_an_unresolvable_home(
        self, monkeypatch
    ):
        """`notebooklm_home` is public, so its own guard needs its own
        test: the early screening in `_rejected_input` reaches it first
        through send/check, which left a bare `raise` there surviving
        the whole file (QG D2 r6)."""
        monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)

        def no_home(cls):
            raise RuntimeError("Could not determine home directory")

        monkeypatch.setattr(Path, "home", classmethod(no_home))
        with pytest.raises(ValueError, match="could not be determined"):
            nlm_client.notebooklm_home()

    def test_an_unresolvable_home_is_refused_not_blamed_on_the_guard(
        self, tmp_path, monkeypatch
    ):
        """No HOME and no passwd entry — a container or a CI runner.
        `Path.home()` raises, and the reason read 'egress guard error'
        because the config path was built inside the guard's try
        (QG D2 r6, Francisca B1)."""
        monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)

        def no_home(cls):
            raise RuntimeError("Could not determine home directory")

        monkeypatch.setattr(Path, "home", classmethod(no_home))
        monkeypatch.setattr(
            nlm_client.shutil, "which", lambda name: f"/usr/local/bin/{name}"
        )
        spy = Spy()

        result = send("clean text", runner=spy)

        assert result.ok is False
        assert "guard error" not in result.reason
        assert "home directory could not be determined" in result.reason
        assert spy.calls == []

    def test_a_tilde_env_home_is_expanded_not_taken_literally(
        self, monkeypatch, tmp_path
    ):
        """A literal `~` value used to create a directory NAMED `~`
        under the cwd. HOME is repointed here so the expansion can
        never reach the operator's real home — writing this test the
        first time did exactly that."""
        monkeypatch.setenv("HOME", str(tmp_path))
        assert Path("~").expanduser() == tmp_path  # the guard's guard
        monkeypatch.setenv("NOTEBOOKLM_HOME", "~/nlm")
        assert nlm_client.notebooklm_home() == tmp_path / "nlm"

    def test_the_production_home_is_the_arkaos_default(self, tmp_path,
                                                       monkeypatch):
        """The ~/.arkaos/notebooklm branch is what ships, and it was the
        one line no test exercised — every test set the env var
        (QG D2 r1, Francisca M8)."""
        monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)
        assert nlm_client.notebooklm_home(tmp_path) == (
            tmp_path / ".arkaos" / "notebooklm"
        )
        # A blank value is not an override.
        monkeypatch.setenv("NOTEBOOKLM_HOME", "   ")
        assert nlm_client.notebooklm_home(tmp_path) == (
            tmp_path / ".arkaos" / "notebooklm"
        )

    def test_tool_absent(self, env, monkeypatch):
        monkeypatch.setattr(nlm_client.shutil, "which", lambda name: None)
        spy = Spy()
        result = send("text", home=env, runner=spy)
        self.assert_degraded(result, "not on PATH")
        assert spy.calls == []

    def test_timeout(self, env):
        spy = Spy(raises=subprocess.TimeoutExpired(cmd="x", timeout=180))
        result = send("text", home=env, runner=spy)
        self.assert_degraded(result, "timed out after 180s")

    def test_nonzero_exit(self, env):
        result = send("text", home=env, runner=Spy(returncode=3))
        self.assert_degraded(result, "exited 3")

    def test_unrunnable_binary(self, env):
        result = send("text", home=env, runner=Spy(raises=OSError("denied")))
        self.assert_degraded(result, "could not run notebooklm")

    def test_payload_file_removed_even_on_timeout(self, env):
        seen = {}

        def capture(argv, **kwargs):
            seen["path"] = Path(argv[argv.index("--input") + 1])
            raise subprocess.TimeoutExpired(cmd="x", timeout=1)

        send("text", home=env, runner=capture, timeout=1)
        assert not seen["path"].exists()

    def test_unwritable_notebooklm_home(self, env, monkeypatch):
        blocked = env / "blocked"
        blocked.write_text("not a directory", encoding="utf-8")
        monkeypatch.setenv("NOTEBOOKLM_HOME", str(blocked))
        spy = Spy()
        result = send("text", home=env, runner=spy)
        self.assert_degraded(result, "payload home unusable")
        assert spy.calls == []

    def test_public_boundary_never_raises(self, env, monkeypatch):
        """Every hostile shape a caller can hand us is a result."""
        for payload in (None, 123, b"\xff", object(), "x" * 100_000):
            result = send(payload, home=env, runner=Spy())
            assert isinstance(result, NotebookLMResult)

    def test_lone_surrogate_payload_is_sent_not_crashed(self, env):
        """QG D2 r1, Francisca B1: D1 digests a lone surrogate with
        surrogatepass precisely because it is routine input; writing
        the payload file with strict utf-8 re-opened the hole one
        layer up, and the caller's degradation path never ran."""
        reader = PayloadReader()
        result = send(json.loads('"lead \\ud800 report"'), home=env,
                      runner=reader)
        assert result.ok is True
        assert "\ud800" in reader.text

    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            ({"home": object()}, "home must be a Path"),
            ({"notebook": object()}, "notebook must match"),
            ({"output_format": object()}, "format not allowed"),
            ({"timeout": "not-a-number"}, "timeout must be a finite number"),
            ({"timeout": -1}, "timeout must be a finite number"),
            ({"timeout": 0}, "timeout must be a finite number"),
            ({"timeout": True}, "timeout must be a finite number"),
        ],
    )
    def test_hostile_kwargs_degrade_with_the_right_reason(
        self, env, kwargs, expected
    ):
        """Asserting only `ok is False` let the timeout case pass for a
        reason unrelated to timeout — the runner was the REAL
        subprocess.run and the reason was FileNotFoundError on a
        which()-faked path (QG D2 r3, Francisca M7)."""
        spy = Spy()
        merged = {"home": env, "runner": spy, **kwargs}
        result = send("clean text", **merged)
        assert isinstance(result, NotebookLMResult)
        assert result.ok is False
        assert expected in result.reason
        assert spy.calls == []

    def test_a_valid_timeout_reaches_the_runner_unchanged(self, env):
        spy = Spy()
        send("clean text", home=env, runner=spy, timeout=7)
        assert spy.kwargs[0]["timeout"] == 7

    def test_a_runner_valueerror_names_the_run_not_the_client(self, env):
        """`_invoke`'s ValueError arm (a NUL reaching argv raises it)
        was unpinned: narrowing the except to OSError left the suite
        green and silently downgraded the reason from 'could not run'
        to 'client error' (QG D2 r2, Francisca M3)."""
        result = send(
            "clean text", home=env,
            runner=Spy(raises=ValueError("embedded null byte")),
        )
        self.assert_degraded(result, "could not run notebooklm")
        assert "ValueError" in result.reason
        assert "client error" not in result.reason
        assert "null byte" not in result.reason

    def test_runner_raising_anything_degrades(self, env):
        result = send(
            "clean text", home=env, runner=Spy(raises=RuntimeError("boom"))
        )
        assert isinstance(result, NotebookLMResult)
        assert result.ok is False

    def test_no_payload_file_survives_any_failure(self, env):
        """QG D2 r1, Francisca B2: there was no finally, so the
        operator's research was orphaned on every unhandled path."""
        for runner in (
            Spy(raises=RuntimeError("boom")),
            Spy(raises=subprocess.TimeoutExpired(cmd="x", timeout=1)),
            Spy(raises=OSError("denied")),
            Spy(returncode=7),
        ):
            send("plain research question", home=env, runner=runner)
        target = nlm_client.notebooklm_home(env)
        assert list(target.iterdir()) == []


class TestTheDocumentedDefault:
    """QG D2 r5, Francisca B2: every parametrisation in this file
    varies the VALUE of a supplied argument; none varied whether it is
    supplied. So `send(text)` and `check()` with no kwargs — the
    documented default and the shape every production caller will use
    — had zero behavioural coverage, and mutants that break them
    survived the whole file at 100% line coverage."""

    @pytest.fixture
    def default_home(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        (tmp_path / ".arkaos").mkdir(parents=True)
        (tmp_path / ".arkaos" / "redaction-clients.json").write_text(
            json.dumps({"clients": list(CLIENTS)}), encoding="utf-8"
        )
        monkeypatch.setattr(
            nlm_client.shutil, "which", lambda name: f"/usr/local/bin/{name}"
        )
        return tmp_path

    def test_the_default_resolves_under_arkaos(self, default_home):
        assert nlm_client.notebooklm_home() == (
            default_home / ".arkaos" / "notebooklm"
        )

    def test_send_works_with_no_keyword_arguments(self, default_home):
        spy = Spy()
        result = send("clean text", runner=spy)
        assert result.ok is True
        assert len(spy.calls) == 1

    def test_check_works_with_no_arguments(self, default_home):
        result = check()
        assert result.ok is True
        assert result.binary == "/usr/local/bin/notebooklm"

    def test_the_default_still_passes_the_guard(self, default_home):
        spy = Spy()
        result = send("report on acme-alpha2026", runner=spy)
        assert result.denied is True
        assert spy.calls == []


class TestCheckNeverInstalls:
    def test_absent_tool_reports_the_install_command(self, env, monkeypatch):
        monkeypatch.setattr(nlm_client.shutil, "which", lambda name: None)
        result = check(env)
        assert result.ok is False
        assert "uv tool install" in result.reason

    def test_a_usable_install_reports_the_resolved_binary(self, env):
        """check() is the standalone probe: send() no longer goes
        through it (QG D2 r2, Francisca M6), so its branches need
        their own coverage."""
        result = check(env)
        assert result.ok is True
        assert result.binary == "/usr/local/bin/notebooklm"
        assert result.stdout == ""
        assert nlm_client.notebooklm_home(env).stat().st_mode & 0o777 == 0o700

    def test_probe_refuses_a_non_path_home_like_send_does(self, env):
        """send() refused a non-Path home by name while check() let it
        reach `home / '.arkaos'` and raise — two public entry points
        making opposite promises (QG D2 r1, Eduardo B4)."""
        result = check(object())
        assert result.ok is False
        assert "home must be a Path" in result.reason

    @pytest.mark.parametrize("home", ["/tmp/x", object(), 7])
    def test_neither_entry_point_raises_on_a_non_path_home(
        self, tmp_path, monkeypatch, home
    ):
        """The str case had no test at all: the env fixture
        always sets NOTEBOOKLM_HOME, so notebooklm_home()
        returns on the override branch and never divides `home`. With
        the variable UNSET — the documented default — `str / str`
        raised straight out of check() (QG D2 r2, Eduardo B1), and in
        send() it surfaced as 'egress guard error: TypeError',
        blaming the guard for a client-side type error (B2)."""
        monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)
        monkeypatch.setattr(
            nlm_client.shutil, "which", lambda name: f"/usr/local/bin/{name}"
        )
        spy = Spy()

        probe = check(home)
        sent = send("clean text", home=home, runner=spy)

        for result in (probe, sent):
            assert isinstance(result, NotebookLMResult)
            assert result.ok is False
            assert "home must be a Path" in result.reason
            assert type(home).__name__ in result.reason
            assert "guard error" not in result.reason
        assert spy.calls == []

    def test_the_install_hint_survives_a_zsh_paste(self):
        """The operator's shell is zsh, where notebooklm-py[browser] is
        glob syntax: the hint died with 'no matches found' before uv
        ever ran (QG D2 r1, Eduardo B12)."""
        import shlex

        result = nlm_client._ABSENT
        command = result.split("install it with: ", 1)[1]
        # shlex round-trips exactly what a shell would see.
        assert shlex.split(command)[-1] == "notebooklm-py[browser]"

    def test_probe_reports_an_unusable_home(self, env, tmp_path, monkeypatch):
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("x", encoding="utf-8")
        monkeypatch.setenv("NOTEBOOKLM_HOME", str(blocker / "nlm"))
        result = check(env)
        assert result.ok is False
        assert "payload home unusable" in result.reason
        assert "NotADirectoryError" in result.reason

    def test_probe_reports_a_symlinked_home(self, env, tmp_path, monkeypatch):
        victim = tmp_path / "victim"
        victim.mkdir()
        link = tmp_path / "link"
        link.symlink_to(victim)
        monkeypatch.setenv("NOTEBOOKLM_HOME", str(link))
        result = check(env)
        assert result.ok is False
        assert "payload home rejected" in result.reason
        assert "symlink" in result.reason

    @pytest.mark.parametrize("code", [errno.ELOOP, errno.ENOTDIR])
    def test_both_symlink_errnos_are_refused(self, env, monkeypatch, code):
        """macOS raises ENOTDIR here and Linux ELOOP. CI runs
        ubuntu-latest, so the ELOOP arm is the LIVE one there and no
        test on this machine could reach it — line coverage read 100%
        because a tuple membership test is one line
        (QG D2 r3, Francisca M1)."""
        real_open = nlm_client.os.open

        def raise_code(path, flags, *args, **kwargs):
            if flags & os.O_DIRECTORY:
                raise OSError(code, "swapped")
            return real_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(nlm_client.os, "open", raise_code)
        result = check(env)
        assert result.ok is False
        assert "payload home rejected" in result.reason
        assert "symlink" in result.reason

    def test_an_unrelated_open_failure_is_not_relabelled_a_symlink(
        self, env, monkeypatch
    ):
        """Only ELOOP/ENOTDIR mean 'the leaf became a link'. Anything
        else must keep its own identity rather than be reported as a
        symlink the operator does not have."""
        real_open = nlm_client.os.open

        def refuse(path, flags, *args, **kwargs):
            if flags & os.O_DIRECTORY:
                raise OSError(errno.EACCES, "denied")
            return real_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(nlm_client.os, "open", refuse)
        result = check(env)
        assert result.ok is False
        assert "payload home unusable" in result.reason
        assert "PermissionError(errno=13)" in result.reason
        assert "symlink" not in result.reason

    def test_the_only_process_the_module_can_start_is_the_injected_one(self):
        """QG D2 r1, Francisca M4: the previous version searched for a
        literal nobody writes and rejected a bare 'uv' string — theatre.
        The property that matters is structural: the module reaches a
        process ONLY through the injected runner, and the argv it
        builds starts with the which() result."""
        source = (REPO_ROOT / "core" / "kb" / "nlm_client.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        forbidden = {
            "system", "popen", "execv", "execvp", "execve", "spawnv",
            "spawnl", "run_module", "check_output", "call", "check_call",
            "Popen",
        }
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.attr if isinstance(func, ast.Attribute)
                else getattr(func, "id", "")
            )
            if name in forbidden:
                offenders.append(f"line {node.lineno}: {name}")
        assert offenders == [], offenders
        # subprocess is imported for its exception types and the
        # DEFAULT runner argument only — never called directly here.
        assert "subprocess.run(" not in source
        assert "runner(" in source

    def test_argv_always_starts_with_the_resolved_binary(self, env):
        reader = PayloadReader()
        send("clean text", home=env, runner=reader)
        assert reader.calls[0][0] == "/usr/local/bin/notebooklm"


class TestTelemetry:
    def lines(self, env):
        raw = nlm_client.telemetry_path(env).read_text(encoding="utf-8")
        return [json.loads(line) for line in raw.splitlines()]

    def test_one_line_per_call_with_no_payload(self, env):
        send("the Acme-Alpha numbers", home=env, runner=Spy())
        send("acme-alpha2026", home=env, runner=Spy())
        entries = self.lines(env)
        assert [e["ok"] for e in entries] == [True, False]
        assert [e["denied"] for e in entries] == [False, True]
        raw = nlm_client.telemetry_path(env).read_text(encoding="utf-8")
        assert "Acme-Alpha" not in raw
        assert "acme-alpha2026" not in raw
        assert all(len(e["payload_sha256"]) in (0, 64) for e in entries)

    def test_telemetry_failure_never_fails_the_call(self, env, monkeypatch):
        monkeypatch.setattr(
            nlm_client, "telemetry_path", lambda home=None: Path("/proc/x/y")
        )
        result = send("text", home=env, runner=Spy())
        assert result.ok is True

    def test_a_hostile_action_is_not_persisted(self, env):
        """The reason field was scrubbed of paths and the sibling
        action field was not, so a REFUSED call persisted an operator
        home path and a client identifier — for a payload that never
        left the machine (QG D2 r2, Francisca B2)."""
        hostile = "/Users/operator/clients/acme-alpha/Q3-numbers.md"
        spy = Spy()

        result = send("clean text", action=hostile, home=env, runner=spy)

        assert result.ok is False
        assert spy.calls == []
        raw = nlm_client.telemetry_path(env).read_text(encoding="utf-8")
        assert hostile not in raw
        assert "acme-alpha" not in raw
        assert "/Users/" not in raw
        assert self.lines(env)[-1]["action"] == "invalid-action"

    def test_the_trail_is_0600_in_a_0700_dir(self, env):
        """The permissions ARE the r1 blocker; nothing pinned them, so
        both 0600->0644 and 0700->0755 survived a full suite run
        (QG D2 r2, Francisca B3)."""
        send("clean text", home=env, runner=Spy())
        path = nlm_client.telemetry_path(env)
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700

    def test_a_symlinked_trail_directory_is_not_followed(self, env, tmp_path):
        """_prepare_home was symlink-hardened and _record was not, three
        functions away: one send() took a victim directory to 0700 and
        wrote the trail inside it (QG D2 r3, Francisca M2)."""
        victim = tmp_path / "victim"
        victim.mkdir(mode=0o755)
        (victim / "someones-file").write_text("x", encoding="utf-8")
        trail_dir = env / ".arkaos" / "telemetry"
        trail_dir.parent.mkdir(parents=True, exist_ok=True)
        trail_dir.symlink_to(victim)

        result = send("clean text", home=env, runner=Spy())

        # Telemetry is best-effort: the CALL still succeeds.
        assert result.ok is True
        assert victim.stat().st_mode & 0o777 == 0o755
        assert [p.name for p in victim.iterdir()] == ["someones-file"]

    def test_a_symlinked_trail_file_is_not_appended_through(
        self, env, tmp_path
    ):
        """The other half of M2: the DIRECTORY is real and the trail
        file itself is the link. Without O_NOFOLLOW the JSON lines
        append to whatever it points at."""
        victim = tmp_path / "someones-notes.txt"
        victim.write_text("private\n", encoding="utf-8")
        path = nlm_client.telemetry_path(env)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(victim)

        result = send("clean text", home=env, runner=Spy())

        assert result.ok is True
        assert victim.read_text(encoding="utf-8") == "private\n"

    def test_the_trail_is_never_created_wide_even_for_an_instant(
        self, env, monkeypatch
    ):
        """The post-hoc mode check cannot see the creation instant: the
        chmod that follows masks it, so mutating the os.open mode to
        0644 survived a suite that asserts the final 0600. The race
        window is the point of passing the mode to open at all."""
        modes: list[int] = []
        real_open = nlm_client.os.open

        def spy_open(path, flags, mode=0o777, *args, **kwargs):
            if str(path).endswith("notebooklm-usage.jsonl"):
                modes.append(mode)
            return real_open(path, flags, mode, *args, **kwargs)

        monkeypatch.setattr(nlm_client.os, "open", spy_open)
        send("clean text", home=env, runner=Spy())
        assert modes == [0o600]

    def test_a_preexisting_loose_trail_is_narrowed(self, env):
        """The record of a decision must not stay wider than the
        payload it describes just because it already existed."""
        path = nlm_client.telemetry_path(env)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        path.chmod(0o644)
        path.parent.chmod(0o755)

        send("clean text", home=env, runner=Spy())

        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700


class TestNotOnTheCriticalPath:
    @pytest.mark.parametrize(
        "package", ["governance", "workflow", "release"]
    )
    def test_critical_packages_never_import_the_client(self, package):
        """A tool Google can break must never be able to stall a gate
        or a release — enforced by import graph.

        The closure, not one hop, and relative imports resolved: a
        `from ..kb import nlm_client` slipped past the first version
        of this test (QG D2 r1, Francisca M3).
        """
        assert _imports_kb_transitively(f"core.{package}") == []

    def test_the_import_graph_check_actually_discriminates(self, tmp_path):
        """The guard's own guard: a relative import must be caught."""
        package = tmp_path / "core" / "fake"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")
        (package / "mod.py").write_text(
            "from ..kb import nlm_client\n", encoding="utf-8"
        )
        found = _module_kb_imports(package / "mod.py", "core.fake")
        assert found == ["core.kb"]

    def test_the_client_imports_nothing_from_those_packages(self):
        source = (REPO_ROOT / "core" / "kb" / "nlm_client.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        assert not any(
            name.startswith(("core.governance", "core.workflow",
                             "core.release"))
            for name in imported
        )


class TestNothingIsReachedThroughAPlantedLink:
    """The matrix, not the finding (QG D2 r9, Francisca B1).

    Eight rounds probed the LEAF — `is_symlink` on it, `O_NOFOLLOW`
    opening it — and a link one component higher walked past all of
    it, because `mkdir(parents=True)` follows every ancestor. Round-by
    -round repair was never going to find that, so this sweeps the
    product: every position a planted link can occupy above a path the
    module creates, crossed with every door the home arrives through,
    and both paths the module creates.
    """

    @staticmethod
    def foreign(monkeypatch):
        """Make a link look planted by another user.

        `nlm_client.os` IS the `os` module, so a lambda calling
        `os.getuid()` would call the patched version — the same
        same-object trap as `check.__globals__ is vars(nlm_client)`.
        """
        real = os.getuid()
        monkeypatch.setattr(nlm_client.os, "getuid", lambda: real + 1)

    @staticmethod
    def planted(root: Path, depth: int) -> tuple[Path, Path]:
        """``(home_under_the_link, victim)`` — link at *depth* above."""
        victim = root / "victim"
        victim.mkdir()
        (victim / "someones-file").write_text("x", encoding="utf-8")
        link = root / "link"
        link.symlink_to(victim)
        return link.joinpath(*["deep"] * depth), victim

    # The contract is stated over RESOURCES, so the generator is
    # DERIVED from the module's own list — not four segments picked by
    # hand. Hand-picked positions left three of five entries deletable
    # with the full suite green, and one of those deletions restored
    # the r10 leak verbatim (QG D2 r11, Francisca B1).
    # Derived at COLLECTION time from a synthetic home, so the
    # parametrisation names every real position — no index range to
    # overshoot, and therefore no skips for the sweep to hide behind.
    POSITIONS = sorted({
        "/".join(resource.relative_to(Path("/h")).parts[:i])
        for resource in nlm_client._resources_under(Path("/h"))
        for i in range(1, len(resource.relative_to(Path("/h")).parts) + 1)
    })

    @staticmethod
    def plant_at(node: Path, victim: Path, monkeypatch) -> None:
        """A foreign-owned link exactly at *node*."""
        node.parent.mkdir(parents=True, exist_ok=True)
        node.symlink_to(victim)
        real_lstat, real_uid = Path.lstat, os.getuid()

        def foreign(self):
            info = real_lstat(self)
            if self == node:
                return type(
                    "S", (), {"st_uid": real_uid + 1, "st_mode": info.st_mode}
                )()
            return info

        monkeypatch.setattr(Path, "lstat", foreign)

    @pytest.mark.parametrize("door", ["argument", "default"])
    @pytest.mark.parametrize("position", POSITIONS)
    def test_no_position_of_any_resource_is_reachable(
        self, tmp_path, monkeypatch, door, position
    ):
        """resource x position x door, generated. A link anywhere on
        the path of anything the module reads or writes is refused."""
        home = tmp_path / "home"
        home.mkdir()
        node = home.joinpath(*position.split("/"))
        victim = tmp_path / "victim"
        victim.mkdir()
        self.plant_at(node, victim, monkeypatch)
        if door == "default":
            monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
            passed = None
        else:
            passed = home

        rejection = nlm_client._rejected_home(passed)

        assert rejection is not None, f"unscreened position: {node}"
        assert "symlink" in rejection
        assert "payload home" in rejection
        assert list(victim.iterdir()) == []

    def test_every_path_a_call_creates_is_in_the_screened_set(
        self, tmp_path, monkeypatch
    ):
        """The completeness pin, and it does NOT read the list as its
        source of truth — a matrix derived from `_resources_under`
        covers additions to it but cannot see a deletion, because
        removing an entry removes its generated positions too
        (QG D2 r11, Francisca B2). This walks what BOTH public entry
        points create and fails on anything the set does not cover.

        Its boundary, stated rather than overclaimed (QG D2 r12,
        Francisca M1): a walk sees only what is WRITTEN, UNDER the
        passed home, on a path these two calls take. Reads are pinned
        by the derivation test below; anything a call writes outside
        the scoped home is a declared residual in the spec."""
        home = tmp_path / "home"
        (home / ".arkaos").mkdir(parents=True)
        (home / ".arkaos" / "redaction-clients.json").write_text(
            json.dumps({"clients": list(CLIENTS)}), encoding="utf-8"
        )
        monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)
        monkeypatch.setattr(
            nlm_client.shutil, "which", lambda name: f"/usr/local/bin/{name}"
        )
        before = {p for p in home.rglob("*")}

        # BOTH public entry points: a resource created only on the
        # check() path survived a send-only walk (QG D2 r12, B2).
        assert check(home).ok is True
        result = send("clean text", home=home, runner=Spy())
        assert result.ok is True

        screened = nlm_client._resources_under(home)
        uncovered = [
            p for p in home.rglob("*") if p not in before
            and not any(
                p == s or s in p.parents or p in s.parents for s in screened
            )
        ]
        assert uncovered == [], f"created but unscreened: {uncovered}"

    def test_every_egress_path_helper_is_in_the_screened_set(
        self, tmp_path
    ):
        """A walk cannot observe a READ, so the read half needs its
        own pin — and it must be DERIVED, not listed. A four-line
        hand-written assertion missed
        `allowlist.default_allowlist_path`, which `policy.evaluate`
        reads and whose capture flips a denial into an allow (QG D2
        r12, Francisca B1). This enumerates D1's exports, so a fifth
        helper fails on the day it lands rather than the day someone
        notices."""
        import importlib
        import inspect
        import pkgutil

        import core.egress as egress

        home = tmp_path / "home"
        screened = nlm_client._resources_under(home)
        found = []
        # The PACKAGE, not a literal tuple of modules: `redact` was in
        # neither the code's list nor this one, and the claim held only
        # because it exports none today (QG D2 r13, Francisca B2).
        modules = [
            importlib.import_module(f"core.egress.{info.name}")
            for info in pkgutil.iter_modules(egress.__path__)
        ]
        assert len(modules) >= 4, modules
        for module in modules:
            for name, helper in inspect.getmembers(module, callable):
                if name.startswith("default_") and name.endswith("_path"):
                    found.append(f"{module.__name__}.{name}")
                    assert helper(home) in screened, name
        assert len(found) >= 4, found

    @pytest.mark.parametrize("depth", [0, 1, 2, 5])
    def test_the_ancestor_guard_sees_every_depth(
        self, tmp_path, monkeypatch, depth
    ):
        """The property itself, at the layer that owns it."""
        home, _ = self.planted(tmp_path, depth)
        self.foreign(monkeypatch)
        assert "symlink" in (
            nlm_client._rejected_ancestor(home / "nlm") or ""
        )

    @pytest.mark.parametrize("code", [errno.EACCES, errno.EPERM, errno.EIO])
    def test_an_unreadable_component_is_refused_fail_closed(
        self, tmp_path, monkeypatch, code
    ):
        """The fail-closed arm INSIDE the screen, and the module's
        only uncovered lines — an untested branch in the newest
        safety primitive (QG D2 r12, Francisca M3)."""
        home = tmp_path / "home"
        home.mkdir()
        blocked = home / ".arkaos"
        real_lstat = Path.lstat

        def unreadable(self):
            if self == blocked:
                raise OSError(code, "denied")
            return real_lstat(self)

        monkeypatch.setattr(Path, "lstat", unreadable)

        rejection = nlm_client._rejected_home(home)

        assert rejection is not None
        assert "not a usable filesystem path" in rejection
        # The SHAPE, not just the prefix: without it EACCES, EIO and a
        # NUL read identically to an operator during an incident, and
        # dropping the suffix survived the suite (QG D2 r9, Eduardo).
        assert _name(code) in rejection

    def test_a_nul_in_the_home_path_is_refused_not_raised(self):
        """`lstat` raises ValueError on a NUL, which the screen did
        not catch — and in `send` the escape was INSIDE its own
        handler, which recomputed the trail and re-entered the raising
        screen: the QG D2 r1 Eduardo B5 shape with a new trigger
        (QG D2 r13, Francisca B1). The env door is immune because
        os.environ refuses a NUL; this is the `Path(config["home"])`
        shape."""
        hostile = Path("/tmp/a\x00b")
        spy = Spy()

        probe = check(hostile)
        sent = send("clean text", home=hostile, runner=spy)

        for result in (probe, sent):
            assert isinstance(result, NotebookLMResult)
            assert result.ok is False
            assert "not a usable filesystem path" in result.reason
            assert "client error" not in result.reason
        assert spy.calls == []

    def test_the_trail_resolver_is_total(self, env, monkeypatch):
        """`send` resolves the trail BEFORE its try, so a raise there
        would leave the public boundary (QG D2 r13, Francisca B1)."""
        monkeypatch.setattr(
            nlm_client, "_rejected_home",
            lambda home: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert nlm_client._trail_home(env) is None
        result = send("clean text", home=env, runner=Spy())
        assert isinstance(result, NotebookLMResult)
        assert result.ok is False

    def test_a_root_owned_link_is_not_refused(self, tmp_path, monkeypatch):
        """`/tmp` is a ROOT-owned symlink on macOS. Narrowing the
        ownership test to the current user alone would refuse every
        NOTEBOOKLM_HOME under it — and that mutation survived until
        this case existed."""
        home, _ = self.planted(tmp_path, 1)
        link = tmp_path / "link"
        real_lstat = Path.lstat

        def root_owns(self):
            info = real_lstat(self)
            if self == link:
                return type("S", (), {"st_uid": 0, "st_mode": info.st_mode})()
            return info

        monkeypatch.setattr(Path, "lstat", root_owns)
        self.foreign(monkeypatch)  # not the operator's uid either

        assert nlm_client._rejected_ancestor(home / "nlm") is None

    def test_a_link_the_operator_owns_is_not_refused(self, tmp_path):
        """`/tmp` is itself a link on macOS, so refusing every
        symlinked ancestor would refuse a legitimate home. Ownership,
        not existence, is the test — no uid patch here."""
        home, _ = self.planted(tmp_path, 1)
        assert nlm_client._rejected_ancestor(home / "nlm") is None

    @pytest.mark.parametrize("depth", [0, 1, 2])
    def test_the_payload_never_lands_in_the_victim(
        self, env, tmp_path, monkeypatch, depth
    ):
        """End to end through the env door: whatever reason the call
        degrades with, the victim is untouched and nothing ran."""
        root = tmp_path / f"d{depth}"
        root.mkdir()
        home, victim = self.planted(root, depth)
        monkeypatch.setenv("NOTEBOOKLM_HOME", str(home / "nlm"))
        self.foreign(monkeypatch)
        spy = Spy()

        probe = check(env)
        sent = send("clean text", home=env, runner=spy)

        assert probe.ok is False
        assert "symlink" in probe.reason
        assert sent.ok is False
        assert spy.calls == []
        assert [p.name for p in victim.iterdir()] == ["someones-file"]

    @pytest.mark.parametrize("depth", [0, 1, 2])
    def test_d1s_audit_salt_never_lands_in_the_victim(
        self, tmp_path, monkeypatch, depth
    ):
        """The third path a call causes to exist, and the one nobody
        was watching: D1 writes `home/.arkaos/egress/audit.jsonl` and
        `.audit-salt` during `policy.evaluate`, which runs BEFORE
        `_prepare_home` screens anything. Guarding only the payload
        home left the salt — the value that makes D1's token digests
        non-reversible — at the link's target (QG D2 r9, Francisca B1)."""
        root = tmp_path / f"a{depth}"
        root.mkdir()
        home_root, victim = self.planted(root, depth)
        home = home_root / "home"
        assert victim.exists()  # the link's target, which must stay clean
        (home / ".arkaos").mkdir(parents=True)
        (home / ".arkaos" / "redaction-clients.json").write_text(
            json.dumps({"clients": list(CLIENTS)}), encoding="utf-8"
        )
        monkeypatch.setenv("NOTEBOOKLM_HOME", str(tmp_path / "elsewhere"))
        monkeypatch.setattr(
            nlm_client.shutil, "which", lambda name: f"/usr/local/bin/{name}"
        )
        self.foreign(monkeypatch)
        spy = Spy()

        result = send("clean text", home=home, runner=spy)

        assert result.ok is False
        assert "symlink" in result.reason
        assert spy.calls == []
        assert not (home / ".arkaos" / "egress").exists()
        assert not (home / ".arkaos" / "telemetry").exists()
        assert "someones-file" in [p.name for p in victim.iterdir()]

    @pytest.mark.parametrize("depth", [0, 1, 2])
    def test_the_trail_never_lands_in_the_victim(
        self, tmp_path, monkeypatch, depth
    ):
        """The second path the module creates had the same leaf-only
        defence. Driven at the helper because the uid patch that makes
        a link look planted would also fail the legitimate payload
        home's own ownership check — `_record` swallows the refusal by
        design (telemetry is best-effort), so the observable property
        is that the victim is untouched."""
        root = tmp_path / f"t{depth}"
        root.mkdir()
        home, victim = self.planted(root, depth)
        self.foreign(monkeypatch)

        with pytest.raises(ValueError, match="symlink"):
            nlm_client._write_trail(home / "usage.jsonl", "{}")

        assert [p.name for p in victim.iterdir()] == ["someones-file"]

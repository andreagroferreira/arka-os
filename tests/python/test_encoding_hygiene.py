"""Shipped Python must never read or write text with the locale encoding.

`open()`, `Path.read_text()` and `Path.write_text()` fall back to
`locale.getpreferredencoding()` when no `encoding=` is passed. That is UTF-8
on Linux and macOS but **cp1252 on Windows**, so any file with a non-Latin-1
byte raises `UnicodeDecodeError` there and nowhere else - the failure never
reproduces for a maintainer on POSIX. ArkaOS ships em dashes and accented
names (Andre, Ines, Tomas) inside its own YAML and markdown, so this is a
live crash, not a hypothetical.

This is a repository hygiene test: it parses every shipped module and fails
on any text-mode call that omits an explicit encoding. Test fixtures under
tests/ are out of scope - this guards what users run.

Detection is deliberately conservative about the attribute form `x.open(...)`.
`open` as a method name is not exclusive to files: `tarfile.open(f, "r:gz")`,
`pdfplumber.open(path)`, `PIL.Image.open(path)` and `urllib` opener objects
all use it, and none of them take an `encoding` argument - passing one raises
TypeError. So a method call counts as file IO only when its first positional
argument is a literal file mode. A missed site is a bug that stays; a false
positive is a bug this test would introduce.
"""

import ast
import re
import sys

import pytest
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent

# Directories whose Python is executed by users (hooks, CLI, MCP servers,
# skill scripts). tests/ is deliberately absent: fixture files are not shipped.
SHIPPED_DIRS = ("arka", "bin", "core", "departments", "mcps", "plugins", "scripts")

SKIP_PARTS = {"__pycache__", "node_modules", "vendor", ".venv", "venv"}

SHIPPED_FILES = sorted(
    path
    for directory in SHIPPED_DIRS
    for path in (BASE_DIR / directory).rglob("*.py")
    if not SKIP_PARTS.intersection(path.parts)
)

# Calls that take an `encoding` keyword and default to the locale encoding.
TEXT_IO_CALLS = {"open", "read_text", "write_text"}

# A builtin file mode: "r", "w+", "rb", "xt". Not "r:gz" (tarfile), not a path.
FILE_MODE_RE = re.compile(r"^[rwxa][btx+]*$")


def _callee_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _literal_mode(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _builtin_open_mode(call: ast.Call) -> str | None:
    """Mode of `open(file, mode)`, or None when absent or not a literal."""
    for keyword in call.keywords:
        if keyword.arg == "mode":
            return _literal_mode(keyword.value)
    return _literal_mode(call.args[1]) if len(call.args) > 1 else None


def locale_dependent_calls(source: str) -> list[tuple[int, str]]:
    """Return (line, callee) for every text-mode call missing `encoding=`."""
    offenders = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = _callee_name(node)
        if name not in TEXT_IO_CALLS:
            continue
        if any(keyword.arg in (None, "encoding") for keyword in node.keywords):
            continue  # explicit encoding, or **kwargs that may carry one

        if name != "open":
            offenders.append((node.lineno, name))
            continue

        if isinstance(node.func, ast.Name):
            mode = _builtin_open_mode(node)
        else:
            mode = _literal_mode(node.args[0] if node.args else None)
            if mode is None or not FILE_MODE_RE.match(mode):
                continue  # not a file open - a same-named method elsewhere
        if mode and "b" in mode:
            continue  # binary mode: encoding is invalid there
        offenders.append((node.lineno, "open"))
    return offenders


class TestNoLocaleDependentFileIO:
    """Every shipped text-mode file operation pins its encoding."""

    @pytest.mark.parametrize(
        "module", SHIPPED_FILES, ids=lambda p: str(p.relative_to(BASE_DIR)).replace("\\", "/")
    )
    def test_module_pins_encoding(self, module):
        rel = str(module.relative_to(BASE_DIR)).replace("\\", "/")
        try:
            offenders = locale_dependent_calls(module.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            # Not this guard's business: a module can use syntax the running
            # interpreter predates (scripts/tools/dcf_calculator.py has a
            # backslash inside an f-string, legal from 3.12 / PEP 701 but a
            # SyntaxError on 3.11). Surface it as a skip rather than silently
            # passing or failing an unrelated build.
            pytest.skip(f"{rel} does not parse on Python {sys.version.split()[0]}: {exc.msg}")
        detail = ", ".join(f"line {line}: {name}()" for line, name in offenders)
        assert not offenders, (
            f'{rel} calls text IO without encoding="utf-8" ({detail}). '
            "Without it the call uses cp1252 on Windows and crashes on "
            "non-Latin-1 content."
        )


class TestGuardDetectsRegressions:
    """The guard must catch the pattern it exists to prevent."""

    def test_flags_bare_open(self):
        assert locale_dependent_calls("open('x.txt')") == [(1, "open")]

    def test_flags_bare_read_text(self):
        assert locale_dependent_calls("Path('x').read_text()") == [(1, "read_text")]

    def test_flags_bare_write_text(self):
        assert locale_dependent_calls("Path('x').write_text(body)") == [(1, "write_text")]

    def test_flags_path_open_in_text_mode(self):
        assert locale_dependent_calls("p.open('a')") == [(1, "open")]

    def test_accepts_explicit_encoding(self):
        assert locale_dependent_calls("open('x.txt', encoding='utf-8')") == []
        assert locale_dependent_calls("p.read_text(encoding='utf-8')") == []


class TestGuardDoesNotOverreach:
    """`open` is not exclusive to files, and binary mode takes no encoding."""

    def test_ignores_binary_mode(self):
        assert locale_dependent_calls("open('x.bin', 'rb')") == []
        assert locale_dependent_calls("open('x.bin', mode='wb')") == []
        assert locale_dependent_calls("p.open('r+b')") == []

    def test_ignores_non_file_open_apis(self):
        assert locale_dependent_calls("tarfile.open(archive, 'r:gz')") == []
        assert locale_dependent_calls("tarfile.open(fileobj=buffer)") == []
        assert locale_dependent_calls("pdfplumber.open(filepath)") == []
        assert locale_dependent_calls("PILImage.open(png_path)") == []
        assert locale_dependent_calls("opener.open(request, timeout=5)") == []

    def test_scans_a_real_shipped_tree(self):
        assert len(SHIPPED_FILES) > 100, "shipped-file discovery found almost nothing"

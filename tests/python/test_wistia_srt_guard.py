"""The wistia.js --srt-file guard must keep its own promise.

`wistia.js captions create --srt-file <path>` reads a caption file and
POSTs its contents to the Wistia API. Because the CLI is invoked BY an
agent, a prompt-injected path is an exfiltration vector (OWASP LLM06):
the guard must not let a secret be read and shipped as caption text.

These tests reproduce, end-to-end with the real CLI, the three bypasses
the Quality Gate found against the first (blocklist) implementation:
a symlink inside cwd pointing out of it, a `.env.local` dotenv-family
file, and a `../` traversal — plus the legitimate case, which must
still work. The guard is an extension allowlist (.srt/.vtt) + realpath
confinement to the real cwd.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

CLI = (
    Path(__file__).resolve().parents[2]
    / "departments"
    / "marketing"
    / "tools"
    / "clis"
    / "wistia.js"
)


def _run(cwd: Path, srt_arg: str) -> dict:
    proc = subprocess.run(
        [
            "node",
            str(CLI),
            "captions",
            "create",
            "--id",
            "abc123",
            "--language",
            "eng",
            "--srt-file",
            srt_arg,
            "--dry-run",
        ],
        cwd=str(cwd),
        env={**os.environ, "WISTIA_API_KEY": "test-key"},
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_cli_file_exists() -> None:
    assert CLI.is_file()


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_legit_srt_is_read(tmp_path: Path) -> None:
    (tmp_path / "caption.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8"
    )
    out = _run(tmp_path, "./caption.srt")
    assert "caption_file" in out.get("body", {})
    assert "hello" in out["body"]["caption_file"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_symlink_inside_cwd_pointing_out_is_blocked(tmp_path: Path) -> None:
    # A .srt symlink whose target lives outside cwd: passes the extension
    # allowlist, must be caught by realpath confinement.
    secret = tmp_path / "outside_secret.txt"
    secret.write_text("SSH-PRIVATE-KEY-MATERIAL\n", encoding="utf-8")
    workdir = tmp_path / "project"
    workdir.mkdir()
    link = workdir / "caption.srt"
    link.symlink_to(secret)
    out = _run(workdir, "./caption.srt")
    assert "error" in out
    assert "caption_file" not in out.get("body", {})


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_dotenv_family_is_blocked(tmp_path: Path) -> None:
    (tmp_path / ".env.local").write_text("SECRET=leaked\n", encoding="utf-8")
    out = _run(tmp_path, "./.env.local")
    assert "error" in out
    assert "caption_file" not in out.get("body", {})


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_in_cwd_srt_symlink_to_secret_is_blocked(tmp_path: Path) -> None:
    # The seam: a .srt symlink INSIDE cwd whose target is also inside cwd
    # passes both the argument extension check and the cwd confinement.
    # Only re-checking the extension of the RESOLVED path catches it.
    (tmp_path / ".env.local").write_text("SECRET=leaked\n", encoding="utf-8")
    link = tmp_path / "caption.srt"
    link.symlink_to(tmp_path / ".env.local")
    out = _run(tmp_path, "./caption.srt")
    assert "error" in out
    assert "caption_file" not in out.get("body", {})


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_in_cwd_srt_symlink_to_srt_is_allowed(tmp_path: Path) -> None:
    # A legitimate .srt symlink pointing at a real in-cwd .srt must work.
    (tmp_path / "real.srt").write_text("caption body\n", encoding="utf-8")
    link = tmp_path / "link.srt"
    link.symlink_to(tmp_path / "real.srt")
    out = _run(tmp_path, "./link.srt")
    assert "caption_file" in out.get("body", {})
    assert "caption body" in out["body"]["caption_file"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_hard_link_to_secret_is_blocked(tmp_path: Path) -> None:
    # A hard link shares the target's inode but realpath does NOT resolve
    # it, so a .srt hard link to an in-cwd secret slips past the symlink
    # and extension checks. It must be rejected on nlink > 1.
    secret = tmp_path / ".env.local"
    secret.write_text("SECRET=leaked\n", encoding="utf-8")
    link = tmp_path / "caption.srt"
    os.link(secret, link)
    out = _run(tmp_path, "./caption.srt")
    assert "error" in out
    assert "caption_file" not in out.get("body", {})


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_parent_traversal_is_blocked(tmp_path: Path) -> None:
    (tmp_path / "caption.srt").write_text("x\n", encoding="utf-8")
    workdir = tmp_path / "project"
    workdir.mkdir()
    out = _run(workdir, "../caption.srt")
    assert "error" in out
    assert "caption_file" not in out.get("body", {})

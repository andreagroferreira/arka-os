"""End-to-end deliver pipeline through the vendored CLI (subprocess node)."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

# Fonts load async with a system-monospace fallback; the footer href carries
# only the diagram type (upstream privacy contract). Anything else is a leak.
ALLOWED_EXTERNAL_HOSTS = {
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "tt-a1i.github.io",
}


def _deliver(
    node: str, cli: Path, ir: Path, out: Path, diagram_type: str
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [node, str(cli), "deliver", diagram_type, str(ir), str(out), "--json"],
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture()
def delivered(node: str, cli: Path, architecture_example: Path, tmp_path: Path):
    out = tmp_path / "out.html"
    result = _deliver(node, cli, architecture_example, out, "architecture")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout), out


def test_deliver_succeeds_with_receipt(delivered) -> None:
    receipt, out = delivered
    assert receipt["ok"] is True
    assert out.is_file()
    validation = receipt["validation"]
    assert validation["checksPassed"] == validation["checkCount"]


def test_receipt_sha256_matches_artifact(delivered) -> None:
    receipt, out = delivered
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    assert receipt["artifact"]["sha256"] == digest


def test_artifact_is_self_contained(delivered) -> None:
    _, out = delivered
    html = out.read_text(encoding="utf-8")
    assert "<script src=" not in html
    assert "fetch(" not in html
    hosts = {
        match.split("/")[2] for match in re.findall(r"https://[^\"' )]+", html)
    }
    assert hosts <= ALLOWED_EXTERNAL_HOSTS, hosts - ALLOWED_EXTERNAL_HOSTS


def test_broken_ir_fails_closed(
    node: str, cli: Path, architecture_example: Path, tmp_path: Path
) -> None:
    ir = json.loads(architecture_example.read_text(encoding="utf-8"))
    broken = copy.deepcopy(ir)
    del broken["components"]
    broken_path = tmp_path / "broken.architecture.json"
    broken_path.write_text(json.dumps(broken), encoding="utf-8")
    out = tmp_path / "broken.html"
    result = _deliver(node, cli, broken_path, out, "architecture")
    assert result.returncode != 0
    receipt = json.loads(result.stdout)
    assert receipt["ok"] is False
    assert receipt["stage"]
    assert not out.exists()


def test_second_renderer_dispatch(
    node: str, cli: Path, workflow_example: Path, tmp_path: Path
) -> None:
    out = tmp_path / "workflow.html"
    result = _deliver(node, cli, workflow_example, out, "workflow")
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["ok"] is True
    assert out.is_file()

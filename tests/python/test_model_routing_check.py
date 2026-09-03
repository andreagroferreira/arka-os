"""Model-routing telemetry: resolved routes, log parse, status summary."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from core.runtime.model_routing_check import (
    resolved_routes,
    served_counts,
    status_summary,
)

_MODELS_YAML = textwrap.dedent(
    """
    version: 1
    providers:
      ollama: {type: ollama, base_url: "http://localhost:11434"}
    aliases:
      runtime: {best: fable, default: sonnet, fast: sonnet}
    roles:
      quality_gate: {provider: runtime, model: best, effort: max}
      mechanical:   {provider: runtime, model: sonnet, effort: low}
      execution:    {provider: ollama, model: "kimi-k2.7-code:cloud", effort: high}
      strategy:     {provider: runtime, model: claude-fable-5-1, effort: max}
    """
)


@pytest.fixture()
def models_path(tmp_path: Path) -> Path:
    p = tmp_path / "models.yaml"
    p.write_text(_MODELS_YAML, encoding="utf-8")
    return p


def test_resolved_routes(models_path: Path):
    routes = resolved_routes(models_path)
    assert routes["opus"] == "anthropic:claude-fable-5-1"
    assert routes["sonnet"] == "anthropic:claude-sonnet-5"
    assert routes["haiku"] == "ollama:kimi-k2.7-code:cloud"


def test_served_counts_parses_routes(tmp_path: Path):
    log = tmp_path / "litellm.log"
    log.write_text(
        "POST /v1/messages model=arka-haiku\n"
        "POST /v1/messages model=arka-opus\n"
        "POST /v1/messages model=arka-haiku\n"
        "unrelated line\n",
        encoding="utf-8",
    )
    counts = served_counts(log)
    assert counts == {"haiku": 2, "opus": 1}


def test_served_counts_missing_log_is_empty(tmp_path: Path):
    assert served_counts(tmp_path / "nope.log") == {}


def test_status_summary_off_when_no_gateway(models_path: Path, tmp_path: Path):
    # No proxy running on this port in tests -> reports off, still lists routes.
    summary = status_summary(port=59999, user_path=models_path, log_path=tmp_path / "x.log")
    assert "Gateway: off" in summary
    assert "haiku → ollama:kimi-k2.7-code:cloud" in summary


# ── Runtime Sync PR3: the fallback chain the runtime will use ───────────

import json  # noqa: E402 — appended section
import shutil  # noqa: E402
import subprocess  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

from core.runtime.model_routing_check import (  # noqa: E402
    fallback_chain,
    fallback_line,
    read_fallback_setting,
)


def _settings(tmp_path: Path, payload) -> Path:
    p = tmp_path / "settings.json"
    p.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    return p


def test_fallback_chain_reads_the_array(tmp_path: Path):
    p = _settings(tmp_path, {"fallbackModel": ["claude-opus-5", "claude-sonnet-5"]})
    assert fallback_chain(p) == ["claude-opus-5", "claude-sonnet-5"]


def test_fallback_chain_normalises_the_legacy_string_without_rewriting(tmp_path: Path):
    p = _settings(tmp_path, {"fallbackModel": " claude-sonnet-5 "})
    before = p.read_text(encoding="utf-8")
    assert fallback_chain(p) == ["claude-sonnet-5"]
    assert p.read_text(encoding="utf-8") == before


@pytest.mark.parametrize(
    "payload",
    [{}, {"fallbackModel": None}, "{ not json", "[1]"],
    ids=["absent", "null", "not-json", "not-object"],
)
def test_unset_is_absent_null_or_unreadable(tmp_path: Path, payload):
    p = _settings(tmp_path, payload)
    assert read_fallback_setting(p).state == "unset"
    assert fallback_chain(p) is None
    assert "unset (npx arkaos update seeds" in fallback_line(p)


@pytest.mark.parametrize(
    "payload",
    [{"fallbackModel": []}, {"fallbackModel": ""}, {"fallbackModel": " "}],
    ids=["empty-array", "empty-string", "blank"],
)
def test_disabled_is_present_but_empty(tmp_path: Path, payload):
    """QG round 1 (Francisca B1): `[]` is the operator's choice — the seeder
    leaves it alone, so the status must not prescribe the seeder."""
    p = _settings(tmp_path, payload)
    assert read_fallback_setting(p).state == "disabled"
    assert fallback_chain(p) == []
    line = fallback_line(p)
    assert line.startswith("  fallback: disabled (fallbackModel is ")
    assert "npx arkaos update" not in line


@pytest.mark.parametrize(
    "payload",
    [{"fallbackModel": 7}, {"fallbackModel": [1, 2]}, {"fallbackModel": {"a": 1}}],
    ids=["int", "int-items", "mapping"],
)
def test_invalid_is_any_other_shape(tmp_path: Path, payload):
    p = _settings(tmp_path, payload)
    setting = read_fallback_setting(p)
    assert setting.state == "invalid"
    assert setting.raw == payload["fallbackModel"]
    assert fallback_chain(p) is None
    line = fallback_line(p)
    assert line.startswith("  fallback: invalid (")
    assert "expected an array of model ids" in line
    assert "npx arkaos update" not in line


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_disabled_wording_matches_the_seeder_noop(tmp_path: Path):
    """The seeder (installer/fallback-model.js) no-ops on `[]`; the status
    line for the same file says `disabled`, never `unset` — one operator
    state, one story across surfaces."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    settings = home / ".claude" / "settings.json"
    settings.write_text(json.dumps({"fallbackModel": []}), encoding="utf-8")
    script = (
        "import('./installer/fallback-model.js').then(m => "
        "console.log(JSON.stringify(m.seedFallbackModel({home: process.argv[1]}))))"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(home)],
        capture_output=True, text=True, cwd=REPO_ROOT, check=True, timeout=60,
    )
    seeded = json.loads(result.stdout.strip())
    assert seeded["action"] == "noop" and seeded["value"] == []
    assert json.loads(settings.read_text(encoding="utf-8")) == {"fallbackModel": []}
    assert fallback_line(settings).startswith("  fallback: disabled")


def test_fallback_chain_is_none_when_the_file_is_missing(tmp_path: Path):
    assert fallback_chain(tmp_path / "absent.json") is None


def test_status_summary_shows_the_chain(models_path: Path, tmp_path: Path):
    p = _settings(tmp_path, {"fallbackModel": ["claude-opus-5", "claude-sonnet-5"]})
    summary = status_summary(
        port=59999, user_path=models_path, log_path=tmp_path / "x.log", settings_path=p
    )
    assert "  fallback: claude-opus-5 → claude-sonnet-5" in summary


def test_status_summary_says_unset_and_how_to_seed(models_path: Path, tmp_path: Path):
    p = _settings(tmp_path, {})
    summary = status_summary(
        port=59999, user_path=models_path, log_path=tmp_path / "x.log", settings_path=p
    )
    assert "  fallback: unset (npx arkaos update seeds claude-opus-5 → claude-sonnet-5)" in summary
    assert fallback_line(p) in summary

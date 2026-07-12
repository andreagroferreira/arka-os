"""Tests for core/workflow/specialist_enforcer.py — Force Specialist Dispatch.

PR1 of the Squad Intelligence Upgrade. Blocks Tier-1 squad leads from
writing to specialist-owned files without dispatching the specialist via
the Agent tool first. Bypass via `[arka:specialist-bypass owner=<slug>
reason=<24+ chars>]` is
logged for accountability.
"""

import json
from pathlib import Path

import pytest


# Import deferred — the module does not exist yet (TDD red phase).
specialist_enforcer = pytest.importorskip(
    "core.workflow.specialist_enforcer",
    reason="specialist_enforcer.py not yet implemented (TDD red phase)",
)
Decision = specialist_enforcer.Decision
evaluate = specialist_enforcer.evaluate


# ─── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Isolate config + telemetry + ownership paths to tmp_path."""
    home = tmp_path / "home"
    home.mkdir()
    ownership_yaml = tmp_path / "agent-ownership.yaml"
    monkeypatch.setattr(specialist_enforcer, "CONFIG_PATH", home / "config.json")
    monkeypatch.setattr(
        specialist_enforcer,
        "TELEMETRY_PATH",
        home / "telemetry" / "specialist-dispatch.jsonl",
    )
    monkeypatch.setattr(specialist_enforcer, "OWNERSHIP_YAML_PATH", ownership_yaml)
    # Clear LRU cache so each test sees a fresh ownership config.
    if hasattr(specialist_enforcer, "_load_ownership"):
        specialist_enforcer._load_ownership.cache_clear()
    return {"home": home, "ownership_yaml": ownership_yaml}


def _write_config(home: Path, hard_enforcement: bool) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.json").write_text(
        json.dumps({"hooks": {"specialistEnforcement": hard_enforcement}}),
        encoding="utf-8",
    )


def _write_ownership(path: Path, rules: list[dict] | None = None) -> None:
    """Write a minimal but representative ownership YAML."""
    default_rules = [
        {"pattern": "**/*.vue", "owners": ["frontend-dev"]},
        {"pattern": "**/*.tsx", "owners": ["frontend-dev"]},
        {"pattern": "**/app/Services/**", "owners": ["senior-dev", "backend-dev"]},
        {"pattern": "**/.env*", "owners": ["security-eng"]},
        {"pattern": "config/hooks/**", "owners": ["security-eng", "devops-eng"]},
        {"pattern": "**/tests/**", "owners": ["*"]},
        {"pattern": "**/*.md", "owners": ["*"]},
    ]
    content = {
        "version": 1,
        "leads": ["paulo", "ines", "luna", "daniel", "ricardo", "tiago"],
        "c_suite": ["marco", "marta", "eduardo", "francisca", "sofia", "helena"],
        "ownership": rules if rules is not None else default_rules,
        "lead_allowed": ["CHANGELOG.md", "VERSION", "package.json", "**/*.yaml"],
    }
    import yaml as _yaml
    path.write_text(_yaml.safe_dump(content), encoding="utf-8")


def _write_transcript(path: Path, assistant_messages: list[str]) -> Path:
    lines = [{"role": "user", "content": "implement a feature"}]
    for msg in assistant_messages:
        lines.append({"role": "assistant", "content": msg})
    path.write_text(
        "\n".join(json.dumps(line) for line in lines),
        encoding="utf-8",
    )
    return path


# ─── Non-write tools never gated ───────────────────────────────────────


def test_read_tool_always_allows(tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    d = evaluate(
        tool_name="Read",
        transcript_path="/nonexistent",
        session_id="s1",
        tool_input={"file_path": "/tmp/some.vue"},
    )
    assert d.allow is True
    assert d.reason == "tool-not-gated"


def test_bash_tool_always_allows(tmp_config):
    """Bash classification is the flow_enforcer's job, not this one."""
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    d = evaluate(
        tool_name="Bash",
        transcript_path="/nonexistent",
        session_id="s1",
        tool_input={"command": "rm -rf /"},
    )
    assert d.allow is True
    assert d.reason == "tool-not-gated"


def test_task_tool_always_allows(tmp_config):
    """Task IS dispatch — should never be blocked by ownership."""
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    d = evaluate(
        tool_name="Task",
        transcript_path="/nonexistent",
        session_id="s1",
        tool_input={"subagent_type": "frontend-dev"},
    )
    assert d.allow is True
    assert d.reason == "tool-not-gated"


# ─── Feature flag ──────────────────────────────────────────────────────


def test_feature_flag_off_allows_all(tmp_config):
    _write_ownership(tmp_config["ownership_yaml"])
    # No config.json → flag defaults to off
    d = evaluate(
        tool_name="Write",
        transcript_path="/nonexistent",
        session_id="s1",
        tool_input={"file_path": "/tmp/app.vue"},
    )
    assert d.allow is True
    assert d.reason == "feature-flag-off"


def test_feature_flag_explicit_false(tmp_config):
    _write_config(tmp_config["home"], False)
    _write_ownership(tmp_config["ownership_yaml"])
    d = evaluate(
        tool_name="Write",
        transcript_path="/nonexistent",
        session_id="s1",
        tool_input={"file_path": "/tmp/app.vue"},
    )
    assert d.allow is True
    assert d.reason == "feature-flag-off"


# ─── No routing tag → defer to flow_enforcer ──────────────────────────


def test_no_routing_tag_defers(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(tmp_path / "tx.jsonl", ["just talking, no marker"])
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/tmp/app.vue"},
    )
    assert d.allow is True
    assert d.reason == "no-routing-tag"


# ─── Lead persona blocked from specialist territory ───────────────────


def test_lead_paulo_blocked_writing_vue(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] dev -> Paulo\n[arka:phase:10] working"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/Users/me/proj/src/App.vue"},
    )
    assert d.allow is False
    assert d.current_persona == "paulo"
    assert "frontend-dev" in d.required_owners
    assert "paulo" not in d.required_owners


def test_lead_ines_blocked_writing_services(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] landing -> Ines"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/Users/me/proj/app/Services/UserService.php"},
    )
    assert d.allow is False
    assert d.current_persona == "ines"
    assert set(d.required_owners) == {"senior-dev", "backend-dev"}


# ─── Specialist persona allowed in their own territory ────────────────


def test_specialist_frontend_dev_writes_vue(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    # Dispatch marker overrides routing — current persona becomes frontend-dev
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        [
            "[arka:routing] dev -> Paulo",
            "[arka:dispatch] paulo -> frontend-dev",
        ],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/Users/me/proj/src/App.vue"},
    )
    assert d.allow is True
    assert d.current_persona == "frontend-dev"
    assert d.reason.startswith("owner-match")


def test_specialist_senior_dev_writes_service(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] dev -> Paulo\n[arka:dispatch] paulo -> senior-dev"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/proj/app/Services/AuthService.php"},
    )
    assert d.allow is True
    assert d.current_persona == "senior-dev"


# ─── C-Suite always allowed ───────────────────────────────────────────


def test_c_suite_marco_allowed_anywhere(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] dev -> Marco"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/proj/src/App.vue"},
    )
    assert d.allow is True
    assert d.reason == "c-suite-override"


# ─── Bypass marker ────────────────────────────────────────────────────


def test_bypass_marker_with_reason_allows(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        [
            "[arka:routing] dev -> Paulo",
            "[arka:specialist-bypass owner=backend-dev reason=the specialist "
            "cannot run here, the toolchain is missing on this box]",
        ],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/proj/src/App.vue"},
    )
    assert d.allow is True
    assert d.bypass_used is True
    assert "toolchain is missing" in (d.bypass_reason or "")


def test_bypass_marker_without_reason_rejected(tmp_path, tmp_config):
    """Empty bypass reason must NOT trigger bypass — accountability."""
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        [
            "[arka:routing] dev -> Paulo",
            "[arka:specialist-bypass]",  # no reason
        ],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/proj/src/App.vue"},
    )
    assert d.allow is False
    assert d.bypass_used is False


# ─── Lead-allowed cross-cutting files ─────────────────────────────────


def test_lead_writes_changelog(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] dev -> Paulo"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/proj/CHANGELOG.md"},
    )
    assert d.allow is True
    assert d.reason == "lead-allowed-file"


def test_lead_writes_package_json(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] dev -> Paulo"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/proj/package.json"},
    )
    assert d.allow is True
    assert d.reason == "lead-allowed-file"


# ─── Open-access patterns ─────────────────────────────────────────────


def test_lead_writes_markdown(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] dev -> Paulo"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/proj/docs/notes.md"},
    )
    assert d.allow is True
    assert d.reason.startswith("open-access")


def test_lead_writes_test_file(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] dev -> Paulo"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/proj/tests/test_something.py"},
    )
    assert d.allow is True
    assert d.reason.startswith("open-access")


# ─── Unowned file (no pattern matches) ────────────────────────────────


def test_unowned_file_defaults_allow(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] dev -> Paulo"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/proj/random/unmatched_file.txt"},
    )
    assert d.allow is True
    assert d.reason == "no-ownership-rule"


# ─── Deny message format ──────────────────────────────────────────────


def test_deny_message_contains_dispatch_instructions(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] dev -> Paulo"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/proj/src/App.vue"},
    )
    msg = d.to_stderr_message()
    assert "ARKA:SPECIALIST" in msg
    assert "frontend-dev" in msg
    assert "specialist-bypass" in msg
    assert "Agent tool" in msg or "dispatch" in msg.lower()


# ─── Multiple routing tags — most recent wins ─────────────────────────


def test_most_recent_routing_tag_wins(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        [
            "[arka:routing] dev -> Paulo",
            "[arka:routing] landing -> Ines",  # newest
        ],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s1",
        tool_input={"file_path": "/proj/src/App.vue"},
    )
    assert d.current_persona == "ines"


# ─── Telemetry recording ──────────────────────────────────────────────


def test_telemetry_records_deny(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] dev -> Paulo"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s-tel",
        tool_input={"file_path": "/proj/src/App.vue"},
    )
    specialist_enforcer.record_telemetry(
        session_id="s-tel",
        tool="Write",
        decision=d,
        cwd="/proj",
        target_file="/proj/src/App.vue",
    )
    telemetry_path = specialist_enforcer.TELEMETRY_PATH
    assert telemetry_path.exists()
    line = telemetry_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    entry = json.loads(line)
    assert entry["allow"] is False
    assert entry["current_persona"] == "paulo"
    assert entry["target_file"] == "/proj/src/App.vue"


def test_telemetry_records_bypass(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        [
            "[arka:routing] dev -> Paulo",
            "[arka:specialist-bypass owner=frontend-dev reason=production "
            "is down and the frontend specialist cannot be dispatched]",
        ],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s-bp",
        tool_input={"file_path": "/proj/src/App.vue"},
    )
    specialist_enforcer.record_telemetry(
        session_id="s-bp",
        tool="Write",
        decision=d,
        cwd="/proj",
        target_file="/proj/src/App.vue",
    )
    telemetry_path = specialist_enforcer.TELEMETRY_PATH
    line = telemetry_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    entry = json.loads(line)
    assert entry["allow"] is True
    assert entry["bypass_used"] is True
    assert "production" in entry["bypass_reason"]


def test_telemetry_records_model_requested(tmp_path, tmp_config):
    """PR-4: dispatch records carry model_requested for /arka costs checks."""
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] dev -> Paulo"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s-model",
        tool_input={"file_path": "/proj/src/App.vue"},
    )
    specialist_enforcer.record_telemetry(
        session_id="s-model",
        tool="Write",
        decision=d,
        cwd="/proj",
        target_file="/proj/src/App.vue",
        model_requested="sonnet",
    )
    line = specialist_enforcer.TELEMETRY_PATH.read_text(
        encoding="utf-8"
    ).strip().splitlines()[-1]
    entry = json.loads(line)
    assert entry["model_requested"] == "sonnet"


def test_telemetry_model_requested_defaults_empty(tmp_path, tmp_config):
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] dev -> Paulo"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="s-nomodel",
        tool_input={"file_path": "/proj/src/App.vue"},
    )
    specialist_enforcer.record_telemetry(
        session_id="s-nomodel",
        tool="Write",
        decision=d,
        cwd="/proj",
        target_file="/proj/src/App.vue",
    )
    line = specialist_enforcer.TELEMETRY_PATH.read_text(
        encoding="utf-8"
    ).strip().splitlines()[-1]
    assert json.loads(line)["model_requested"] == ""


# ─── Path-traversal safety ────────────────────────────────────────────


def test_session_id_with_traversal_rejected(tmp_path, tmp_config):
    """Don't let a malicious session_id write outside telemetry dir."""
    _write_config(tmp_config["home"], True)
    _write_ownership(tmp_config["ownership_yaml"])
    transcript = _write_transcript(
        tmp_path / "tx.jsonl",
        ["[arka:routing] dev -> Paulo"],
    )
    d = evaluate(
        tool_name="Write",
        transcript_path=str(transcript),
        session_id="../../evil",
        tool_input={"file_path": "/proj/src/App.vue"},
    )
    # Decision still returned, but telemetry should reject the unsafe id
    specialist_enforcer.record_telemetry(
        session_id="../../evil",
        tool="Write",
        decision=d,
        cwd="/proj",
        target_file="/proj/src/App.vue",
    )
    # The malicious path must not exist
    assert not (tmp_path / "evil").exists()

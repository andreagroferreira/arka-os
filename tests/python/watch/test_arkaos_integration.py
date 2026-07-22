"""ArkaOS-native adaptations: key resolution, telemetry, call-time paths."""
from __future__ import annotations

import json
from pathlib import Path

import whisper

import config


def _arkaos_dir(home: Path) -> Path:
    d = home / ".arkaos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_keys_json(home: Path, payload) -> Path:
    path = _arkaos_dir(home) / "keys.json"
    path.write_text(
        payload if isinstance(payload, str) else json.dumps(payload),
        encoding="utf-8",
    )
    return path


def test_env_wins_over_keys_json(monkeypatch, _isolated_home: Path):
    _write_keys_json(_isolated_home, {"OPENAI_API_KEY": "sk-from-file"})
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    assert config.resolve_api_key("OPENAI_API_KEY") == "sk-from-env"


def test_keys_json_wins_over_watch_env(_isolated_home: Path):
    _write_keys_json(_isolated_home, {"OPENAI_API_KEY": "sk-from-keys"})
    (_arkaos_dir(_isolated_home) / "watch.env").write_text(
        "OPENAI_API_KEY=sk-from-watch-env\n", encoding="utf-8"
    )
    assert config.resolve_api_key("OPENAI_API_KEY") == "sk-from-keys"


def test_watch_env_is_the_fallback(_isolated_home: Path):
    (_arkaos_dir(_isolated_home) / "watch.env").write_text(
        "OPENAI_API_KEY=sk-from-watch-env\n", encoding="utf-8"
    )
    assert config.resolve_api_key("OPENAI_API_KEY") == "sk-from-watch-env"


def test_malformed_keys_json_is_ignored(_isolated_home: Path):
    _write_keys_json(_isolated_home, "{not json")
    assert config.resolve_api_key("OPENAI_API_KEY") is None


def test_non_dict_keys_json_is_ignored(_isolated_home: Path):
    _write_keys_json(_isolated_home, ["sk-in-a-list"])
    assert config.resolve_api_key("OPENAI_API_KEY") is None


def test_load_api_key_openai_only_via_keys_json(_isolated_home: Path):
    """The operator's setup: an OpenAI key in /arka keys, no Groq."""
    _write_keys_json(_isolated_home, {"OPENAI_API_KEY": "sk-operator"})
    backend, key = whisper.load_api_key()
    assert (backend, key) == ("openai", "sk-operator")


def test_load_api_key_prefers_groq_when_both(_isolated_home: Path):
    _write_keys_json(
        _isolated_home,
        {"OPENAI_API_KEY": "sk-openai", "GROQ_API_KEY": "gsk-groq"},
    )
    backend, key = whisper.load_api_key()
    assert (backend, key) == ("groq", "gsk-groq")


def test_load_api_key_preferred_filters(_isolated_home: Path):
    _write_keys_json(_isolated_home, {"GROQ_API_KEY": "gsk-groq"})
    assert whisper.load_api_key("openai") == (None, None)


def test_record_telemetry_appends_jsonl(_isolated_home: Path):
    config.record_telemetry({"detail": "balanced", "frames": 12})
    config.record_telemetry({"detail": "efficient", "frames": 3})
    lines = config.telemetry_file().read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["detail"] == "balanced"
    assert first["frames"] == 12
    assert first["ts"] > 0


def test_record_telemetry_is_fail_open(_isolated_home: Path, capsys):
    """A blocked telemetry path must never break a watch run."""
    # Occupy the telemetry DIRECTORY path with a file so mkdir raises.
    _arkaos_dir(_isolated_home)
    (_isolated_home / ".arkaos" / "telemetry").write_text("", encoding="utf-8")
    config.record_telemetry({"detail": "balanced"})  # must not raise
    assert "telemetry write skipped" in capsys.readouterr().err


def test_estimate_image_tokens_matches_512_reference():
    """512px 16:9 ≈ 197 tokens/frame (Anthropic w*h/750)."""
    import watch

    assert watch.estimate_image_tokens(1, 512) == 197
    assert watch.estimate_image_tokens(80, 512) == 80 * 197
    assert watch.estimate_image_tokens(0, 512) == 0


def _fake_binary(directory: Path, name: str, exit_code: int) -> None:
    path = directory / name
    path.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
    path.chmod(0o755)


def test_broken_ffmpeg_on_path_reports_missing(monkeypatch, tmp_path):
    """A binary that dies at load (dangling dylib) must read as missing,
    not as ready — `which` alone cannot see the difference."""
    import setup

    bindir = tmp_path / "bin"
    bindir.mkdir()
    _fake_binary(bindir, "ffmpeg", 134)  # dyld abort
    _fake_binary(bindir, "ffprobe", 0)
    _fake_binary(bindir, "yt-dlp", 0)
    monkeypatch.setenv("PATH", str(bindir))
    assert setup._check_binaries() == ["ffmpeg"]


def test_healthy_fake_binaries_pass_check(monkeypatch, tmp_path):
    import setup

    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name in ("ffmpeg", "ffprobe", "yt-dlp"):
        _fake_binary(bindir, name, 0)
    monkeypatch.setenv("PATH", str(bindir))
    assert setup._check_binaries() == []

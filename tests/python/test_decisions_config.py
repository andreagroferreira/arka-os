"""core.decisions.config — loading never raises, modes, thresholds."""

from __future__ import annotations

import json

import pytest

from core.decisions import config as cfgmod
from core.decisions.config import (
    DecisionsConfig,
    bypassed,
    load_decisions_config,
    site_mode,
    site_timeout_ms,
    threshold_for,
)
from core.decisions.sites.prompt import ROUTE, TOPIC_DRIFT


@pytest.fixture(autouse=True)
def _opt_out(monkeypatch):
    monkeypatch.delenv("ARKA_BYPASS_DECISIONS", raising=False)


def _write(path, data):
    path.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")
    return path


class TestLoad:
    def test_missing_file_is_defaults(self, tmp_path):
        assert load_decisions_config(tmp_path / "nope.json") == DecisionsConfig()

    def test_default_path_is_module_level(self, tmp_path, monkeypatch):
        target = _write(tmp_path / "c.json", {"decisions": {"enabled": False}})
        monkeypatch.setattr(cfgmod, "CONFIG_PATH", target)
        assert load_decisions_config().enabled is False

    @pytest.mark.parametrize("content", [
        "{not json", "[1, 2]", {"decisions": "yes"}, {"decisions": {"hookTimeoutMs": -5}},
        {"decisions": {"enabled": "maybe"}},
    ])
    def test_corrupt_or_invalid_is_defaults(self, tmp_path, content):
        assert load_decisions_config(_write(tmp_path / "c.json", content)) == DecisionsConfig()

    def test_oversized_file_is_defaults(self, tmp_path, monkeypatch):
        path = _write(tmp_path / "c.json", {"decisions": {"enabled": False}})
        monkeypatch.setattr(cfgmod, "MAX_CONFIG_BYTES", 10)
        assert load_decisions_config(path).enabled is True

    def test_camel_case_keys_and_site_forms(self, tmp_path):
        path = _write(tmp_path / "c.json", {"decisions": {
            "redactClients": False, "hookTimeoutMs": 900, "cacheTtlSeconds": 60,
            "thresholds": {"write": 0.8},
            "sites": {
                "topic-drift": "shadow",
                "route": {"mode": "act", "minConfidence": 0.7, "timeoutMs": 600},
                "refine": "turbo",
                "creation-intent": 42,
            },
        }})
        cfg = load_decisions_config(path)
        assert (cfg.redact_clients, cfg.hook_timeout_ms, cfg.cache_ttl_seconds) == (False, 900, 60)
        assert cfg.sites["topic-drift"].mode == "shadow"
        assert cfg.sites["route"].min_confidence == 0.7
        assert cfg.sites["route"].timeout_ms == 600
        assert cfg.sites["refine"].mode == "off"
        assert cfg.sites["creation-intent"].mode == "off"

    def test_sites_not_a_dict_is_empty(self):
        assert DecisionsConfig.model_validate({"sites": ["act"]}).sites == {}


class TestModes:
    def test_bypass_env(self, monkeypatch):
        assert bypassed() is False
        monkeypatch.setenv("ARKA_BYPASS_DECISIONS", "1")
        assert bypassed() is True
        assert site_mode(DecisionsConfig(), TOPIC_DRIFT) == "off"

    def test_disabled_is_off(self):
        assert site_mode(DecisionsConfig(enabled=False), TOPIC_DRIFT) == "off"

    def test_site_default_then_override(self):
        assert site_mode(DecisionsConfig(), TOPIC_DRIFT) == "act"
        cfg = DecisionsConfig.model_validate({"sites": {"topic-drift": "shadow"}})
        assert site_mode(cfg, TOPIC_DRIFT) == "shadow"


class TestThresholds:
    def test_risk_default(self):
        assert threshold_for(DecisionsConfig(), TOPIC_DRIFT) == 0.60
        assert threshold_for(DecisionsConfig(), ROUTE) == 0.75

    def test_config_threshold_then_site_min_confidence(self):
        cfg = DecisionsConfig.model_validate({"thresholds": {"write": 0.8}})
        assert threshold_for(cfg, ROUTE) == 0.8
        cfg = DecisionsConfig.model_validate(
            {"thresholds": {"write": 0.8}, "sites": {"route": {"minConfidence": 0.7}}}
        )
        assert threshold_for(cfg, ROUTE) == 0.7

    def test_timeout_override(self):
        assert site_timeout_ms(DecisionsConfig(), ROUTE) == 1000
        cfg = DecisionsConfig.model_validate({"sites": {"route": {"timeoutMs": 400}}})
        assert site_timeout_ms(cfg, ROUTE) == 400

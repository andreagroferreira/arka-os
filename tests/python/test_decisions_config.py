"""core.decisions.config — loading never raises, modes, thresholds."""

from __future__ import annotations

import dataclasses
import json

import pytest

from core.decisions import config as cfgmod
from core.decisions.config import (
    THRESHOLDS,
    DecisionsConfig,
    bypassed,
    configured_mode,
    load_decisions_config,
    site_mode,
    site_timeout_ms,
    threshold_for,
)
from core.decisions.registry import SITES
from core.decisions.sites.prompt import REFINE, ROUTE, TOPIC_DRIFT


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

    @pytest.mark.parametrize("override", [{"timeoutMs": 4000}, {"minConfidence": 0.7},
                                          {"mode": None}])
    def test_an_override_without_mode_keeps_the_site_default(self, override):
        # Kills: SiteConfig.mode defaulting to "act" again (PR5 D3): a
        # timeout-only override flipped shadow sites to act.
        assert REFINE.default_mode == "shadow"
        cfg = DecisionsConfig.model_validate({"sites": {"refine": override}})
        assert cfg.sites["refine"].mode is None
        assert site_mode(cfg, REFINE) == "shadow"
        assert configured_mode(cfg, REFINE) == "shadow"

    def test_an_explicit_mode_still_wins(self):
        cfg = DecisionsConfig.model_validate({"sites": {"refine": {"mode": "act",
                                                                   "timeoutMs": 4000}}})
        assert site_mode(cfg, REFINE) == "act"
        assert DecisionsConfig.model_validate(
            {"sites": {"refine": {"mode": "bogus"}}}).sites["refine"].mode == "off"

    def test_configured_mode_ignores_the_kill_switch(self, monkeypatch):
        monkeypatch.setenv("ARKA_BYPASS_DECISIONS", "1")
        cfg = DecisionsConfig.model_validate({"enabled": False})
        assert (site_mode(cfg, REFINE), configured_mode(cfg, REFINE)) == ("off", "shadow")


class TestThresholds:
    def test_risk_default(self):
        assert threshold_for(DecisionsConfig(), TOPIC_DRIFT) == 0.60
        assert threshold_for(DecisionsConfig(), REFINE) == 0.60
        table_route = dataclasses.replace(ROUTE, min_confidence=None)
        assert threshold_for(DecisionsConfig(), table_route) == 0.75

    def test_route_has_its_own_floor_without_any_config(self):
        """Spec PR5 D3: route acts from 0.70 on a machine with no ``decisions`` block."""
        assert ROUTE.min_confidence == 0.70
        assert threshold_for(DecisionsConfig(), ROUTE) == 0.70
        # Every other registered site still resolves through the risk table.
        for site in SITES.values():
            if site.name != "route":
                assert site.min_confidence is None, site.name
                assert threshold_for(DecisionsConfig(), site) == THRESHOLDS[site.risk]

    def test_site_floor_outranks_the_config_table(self):
        cfg = DecisionsConfig.model_validate({"thresholds": {"write": 0.9}})
        assert threshold_for(cfg, ROUTE) == 0.70
        assert threshold_for(cfg, dataclasses.replace(ROUTE, min_confidence=None)) == 0.9

    def test_operator_site_override_outranks_the_site_floor(self):
        cfg = DecisionsConfig.model_validate(
            {"thresholds": {"write": 0.8}, "sites": {"route": {"minConfidence": 0.85}}}
        )
        assert threshold_for(cfg, ROUTE) == 0.85

    @pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0])
    def test_site_floor_outside_the_unit_interval_is_rejected(self, bad):
        with pytest.raises(ValueError, match="min_confidence"):
            dataclasses.replace(ROUTE, min_confidence=bad)

    def test_timeout_override(self):
        assert site_timeout_ms(DecisionsConfig(), ROUTE) == 1000
        cfg = DecisionsConfig.model_validate({"sites": {"route": {"timeoutMs": 400}}})
        assert site_timeout_ms(cfg, ROUTE) == 400

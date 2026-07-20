"""Plan-canvas API — forge plan list/detail/decision endpoints.

Dashboard module loaded by path (the health-api pattern); persistence is
redirected to tmp_path by monkeypatching ``_plans_dir`` so the real
``~/.arkaos/plans`` is never touched.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

from core.forge import persistence  # noqa: E402
from core.forge.schema import ForgeContext, ForgePlan, ForgeStatus  # noqa: E402


@pytest.fixture(scope="module")
def dashboard_module():
    spec = importlib.util.spec_from_file_location(
        "dashboard_api_plans", REPO_ROOT / "scripts" / "dashboard-api.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def plans_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "plans"
    monkeypatch.setattr(persistence, "_plans_dir", lambda: target)
    return target


def _plan(plan_id: str, status: ForgeStatus = ForgeStatus.REVIEWING) -> ForgePlan:
    return ForgePlan(
        id=plan_id,
        name=f"Plan {plan_id}",
        context=ForgeContext(
            repo="test-repo", branch="master", commit_at_forge="abc123",
            arkaos_version="4.22.0", prompt="test task",
        ),
        status=status,
    )


def test_plans_list_empty(dashboard_module, plans_dir):
    result = dashboard_module.plans_list()
    assert result["plans"] == []
    assert result["active_id"] is None


def test_plans_list_returns_summaries_and_active(dashboard_module, plans_dir):
    persistence.save_plan(_plan("forge-1"))
    persistence.save_plan(_plan("forge-2", ForgeStatus.DRAFT))
    persistence.set_active_plan("forge-1")
    result = dashboard_module.plans_list()
    assert {p["id"] for p in result["plans"]} == {"forge-1", "forge-2"}
    assert result["active_id"] == "forge-1"


def test_plan_detail_round_trip(dashboard_module, plans_dir):
    persistence.save_plan(_plan("forge-detail"))
    result = dashboard_module.plan_detail("forge-detail")
    assert result["plan"]["id"] == "forge-detail"
    assert result["plan"]["status"] == "reviewing"


def test_plan_detail_unknown_is_not_found(dashboard_module, plans_dir):
    assert dashboard_module.plan_detail("forge-ghost") == {
        "error": "plan not found"
    }


@pytest.mark.parametrize(
    "bad_id", ["../../etc/passwd", "a/../b", "active", ".hidden", "", "a" * 200]
)
def test_plan_detail_rejects_unsafe_ids(dashboard_module, plans_dir, bad_id):
    result = dashboard_module.plan_detail(bad_id)
    assert result == {"error": "plan not found"}


def test_decision_approve_sets_status_and_stamp(dashboard_module, plans_dir):
    persistence.save_plan(_plan("forge-appr"))
    result = dashboard_module.plan_decision(
        "forge-appr", {"action": "approve", "note": "ship it"}
    )
    assert result["status"] == "approved"
    assert result["approved_at"]
    assert result["review_note"] == "ship it"
    reloaded = persistence.load_plan("forge-appr")
    assert reloaded.status is ForgeStatus.APPROVED
    assert reloaded.approved_by == "operator:plan-canvas"
    assert reloaded.review_note == "ship it"


def test_decision_reject_persists_note(dashboard_module, plans_dir):
    persistence.save_plan(_plan("forge-rej", ForgeStatus.DRAFT))
    result = dashboard_module.plan_decision(
        "forge-rej", {"action": "reject", "note": "wrong approach"}
    )
    assert result["status"] == "rejected"
    reloaded = persistence.load_plan("forge-rej")
    assert reloaded.status is ForgeStatus.REJECTED
    assert reloaded.review_note == "wrong approach"


@pytest.mark.parametrize(
    "status",
    [ForgeStatus.APPROVED, ForgeStatus.EXECUTING, ForgeStatus.COMPLETED,
     ForgeStatus.REJECTED, ForgeStatus.CANCELLED, ForgeStatus.ARCHIVED],
)
def test_decision_refuses_non_decidable_statuses(
    dashboard_module, plans_dir, status
):
    persistence.save_plan(_plan(f"forge-{status.value}", status))
    result = dashboard_module.plan_decision(
        f"forge-{status.value}", {"action": "approve"}
    )
    assert "not decidable" in result["error"]
    reloaded = persistence.load_plan(f"forge-{status.value}")
    assert reloaded.status is status  # untouched


def test_decision_rejects_bad_action(dashboard_module, plans_dir):
    persistence.save_plan(_plan("forge-bad"))
    result = dashboard_module.plan_decision("forge-bad", {"action": "delete"})
    assert "action must be" in result["error"]


def test_decision_note_is_capped(dashboard_module, plans_dir):
    persistence.save_plan(_plan("forge-cap"))
    dashboard_module.plan_decision(
        "forge-cap", {"action": "approve", "note": "x" * 5000}
    )
    assert len(persistence.load_plan("forge-cap").review_note) == 2000


def test_gates_state_shape(dashboard_module):
    result = dashboard_module.gates_state()
    assert "state" in result


def test_review_note_backwards_compatible(plans_dir):
    # Old YAMLs (no review_note key) must load with the new schema.
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan = _plan("forge-old")
    data = plan.model_dump(mode="json")
    data.pop("review_note")
    import yaml

    (plans_dir / "forge-old.yaml").write_text(
        yaml.dump(data), encoding="utf-8"
    )
    loaded = persistence.load_plan("forge-old")
    assert loaded is not None
    assert loaded.review_note is None


def test_decision_reject_stamps_trail(dashboard_module, plans_dir):
    # M2: reject must leave a trail — a feature that sells "leave a trail"
    # cannot record a decision without who + when.
    persistence.save_plan(_plan("forge-trail", ForgeStatus.REVIEWING))
    result = dashboard_module.plan_decision(
        "forge-trail", {"action": "reject", "note": "scope drift"}
    )
    assert result["rejected_at"]
    reloaded = persistence.load_plan("forge-trail")
    assert reloaded.rejected_at
    assert reloaded.rejected_by == "operator:plan-canvas"
    assert reloaded.approved_at is None


def test_list_plans_tolerates_scalar_shapes(plans_dir):
    # B4: pre-schema plans stored complexity/critic as scalars. list_plans
    # must summarize them, not crash on `int.get`.
    plans_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (plans_dir / "forge-scalar.yaml").write_text(
        yaml.dump({
            "id": "forge-scalar", "title": "Legacy", "status": "approved",
            "complexity": 3, "critic": "n/a", "phases": ["do the thing"],
        }),
        encoding="utf-8",
    )
    summaries = persistence.list_plans()
    row = next(s for s in summaries if s["id"] == "forge-scalar")
    assert row["tier"] == "shallow"
    assert row["confidence"] == 0.0


def test_legacy_plan_normalized_and_read_only(dashboard_module, plans_dir):
    # B3: a pre-schema YAML surfaces read-only in the detail pane and
    # refuses decisions.
    plans_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (plans_dir / "forge-legacy-1.yaml").write_text(
        yaml.dump({
            "id": "forge-legacy-1", "title": "Legacy hand-written plan",
            "date": "2026-06-02", "tier": "deep", "status": "approved",
            "note": "pre-schema artifact",
            "phases": ["Phase one", {"name": "Phase two", "department": "dev"}],
        }),
        encoding="utf-8",
    )
    result = dashboard_module.plan_detail("forge-legacy-1")
    assert result["legacy"] is True
    payload = result["plan"]
    assert payload["name"] == "Legacy hand-written plan"
    assert payload["goal"] == "pre-schema artifact"
    assert payload["complexity"]["tier"] == "deep"
    assert [ph["name"] for ph in payload["plan_phases"]] == [
        "Phase one", "Phase two"
    ]
    decision = dashboard_module.plan_decision(
        "forge-legacy-1", {"action": "approve"}
    )
    assert "read-only" in decision["error"]


def test_modern_plan_detail_flags_not_legacy(dashboard_module, plans_dir):
    persistence.save_plan(_plan("forge-modern"))
    result = dashboard_module.plan_detail("forge-modern")
    assert result["legacy"] is False

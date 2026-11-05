"""Escalation ladder: tiered flags become owned levels with first-seen history.

The contract under test: levels derive from the shared noncompliance tiers
(one source, never disagreeing), checks are explicit and attributed, and only
course publishers may run them.
"""

import json

from fastapi.testclient import TestClient

from api.main import app
from src import agent, learning


def _published(tmp_path, monkeypatch, run_id="ibrance-esc", due_on="2020-01-01"):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    content = tmp_path / "content" / run_id
    content.mkdir(parents=True)
    (content / "manifest.json").write_text(json.dumps({"drug": {"brand": "Ibrance"}}))
    record = learning.course(run_id)
    record.update(status="published", publication={
        "version": 1, "published_at": "2026-01-02T00:00:00+00:00", "published_by": "Priya Raman",
        "overrides": [], "starts_on": "2020-01-01", "due_on": due_on,
        "frequency": "once", "next_due_on": None, "message": "",
        "assignees": ["ken-osei"], "notifications": []})
    learning._save_course(record)
    state = learning.progress(run_id, "ken-osei")
    state["started_at"] = "2020-01-03T00:00:00+00:00"
    state["attempts"] = [
        {"id": "a0", "kind": "baseline", "score": 60, "correct": 3, "total": 5,
         "passing_score": 67, "passed": False, "answers": {}, "created_at": "2020-01-03T00:00:00+00:00"},
        {"id": "a1", "kind": "final", "score": 40, "correct": 2, "total": 5,
         "passing_score": 67, "passed": False, "answers": {}, "created_at": "2020-01-04T00:00:00+00:00"}]
    learning._save_progress(state)
    return run_id


def test_levels_derive_from_shared_tiers(tmp_path, monkeypatch):
    run_id = _published(tmp_path, monkeypatch)
    flags = {alert["message"]: alert["tier"] for alert in learning.noncompliance(run_id)}
    state = learning.escalation_state(run_id)
    assert state["checked_at"] is None
    assert len(state["items"]) == len(flags) == 2
    for item in state["items"]:
        assert item["level"] == flags[item["message"]]
        assert item["level_name"] == learning.ESCALATION_LEVELS[item["tier"]]["name"]
        assert item["owner"] == learning.ESCALATION_LEVELS[item["tier"]]["owner"]
        assert item["history"] == []


def test_alerts_carry_run_id_for_learner_deep_links(tmp_path, monkeypatch):
    """Every noncompliance flag names its course so the trainee UI can link it."""
    run_id = _published(tmp_path, monkeypatch)
    alerts = learning.noncompliance(run_id)
    assert len(alerts) == 2
    assert all(alert["run_id"] == run_id for alert in alerts)


def test_check_stamps_since_and_records_level_changes(tmp_path, monkeypatch):
    run_id = _published(tmp_path, monkeypatch)
    first = learning.check_escalations(run_id, "priya-raman")
    assert first["resolved"] == 0
    assert all(len(item["history"]) == 1 and item["history"][0]["note"] == "Flag raised"
               for item in first["items"])
    sinces = {item["key"]: item["since"] for item in first["items"]}

    # A fresh check without change adds no history and keeps first-seen dates.
    second = learning.check_escalations(run_id, "priya-raman")
    assert {item["key"]: item["since"] for item in second["items"]} == sinces
    assert all(len(item["history"]) == 1 for item in second["items"])

    # A worsening flag (recently due -> long overdue) records the move up.
    from datetime import date, timedelta
    recent = (date.today() - timedelta(days=3)).isoformat()
    record = learning.course(run_id)
    record["publication"]["due_on"] = recent
    learning._save_course(record)
    learning.check_escalations(run_id, "priya-raman")
    before = {item["key"]: item
              for item in learning.escalation_state(run_id)["items"]}
    assert before["ken-osei:Overdue with 0/4 modules done"]["level"] == 1
    record = learning.course(run_id)
    record["publication"]["due_on"] = "2020-01-01"
    learning._save_course(record)
    after = {item["key"]: item for item in learning.check_escalations(run_id, "priya-raman")["items"]}
    overdue = after["ken-osei:Overdue with 0/4 modules done"]
    assert overdue["level"] == 3 and len(overdue["history"]) == 3
    assert overdue["history"][-1]["note"] == "Moved to Escalated"
    assert overdue["since"] == before["ken-osei:Overdue with 0/4 modules done"]["since"]


def test_only_publishers_run_the_check(tmp_path, monkeypatch):
    run_id = _published(tmp_path, monkeypatch)
    try:
        learning.check_escalations(run_id, "ken-osei")
    except ValueError as error:
        assert "Publish courses" in str(error)
    else:
        raise AssertionError("expected a ValueError")


def test_resolved_flags_leave_the_ladder(tmp_path, monkeypatch):
    run_id = _published(tmp_path, monkeypatch)
    learning.check_escalations(run_id, "priya-raman")
    record = learning.course(run_id)
    record["publication"]["due_on"] = "2999-01-01"
    record["publication"]["starts_on"] = "2999-01-01"
    learning._save_course(record)
    state = learning.progress(run_id, "ken-osei")
    state["attempts"] = [
        {"id": "a0", "kind": "baseline", "score": 60, "correct": 3, "total": 5,
         "passing_score": 67, "passed": False, "answers": {}, "created_at": "2020-01-03T00:00:00+00:00"},
        {"id": "a2", "kind": "final", "score": 80, "correct": 4, "total": 5,
         "passing_score": 67, "passed": True, "answers": {}, "created_at": "2020-01-05T00:00:00+00:00"}]
    learning._save_progress(state)
    assert learning.escalation_state(run_id)["items"] == []
    assert learning.check_escalations(run_id, "priya-raman")["resolved"] == 2


def test_escalation_endpoints(tmp_path, monkeypatch):
    run_id = _published(tmp_path, monkeypatch)
    client = TestClient(app)
    live = client.get(f"/api/runs/{run_id}/escalations").json()
    assert len(live["items"]) == 2 and live["checked_at"] is None
    checked = client.post(f"/api/runs/{run_id}/escalations/check", json={"user_id": "priya-raman"}).json()
    assert checked["checked_by"] == "Priya Raman"
    assert client.post(f"/api/runs/{run_id}/escalations/check", json={"user_id": "ken-osei"}).status_code == 400

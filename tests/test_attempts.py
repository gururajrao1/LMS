import json

import pytest
from fastapi.testclient import TestClient
from api.main import app
from src import agent, learning


def _ready(tmp_path, run_id, max_final_attempts=3):
    base = tmp_path / "content" / run_id
    (base / "hcp" / "ppt").mkdir(parents=True)
    (base / "hcp" / "storyboard").mkdir(parents=True)
    (base / "msl" / "ppt").mkdir(parents=True)
    (base / "msl" / "storyboard").mkdir(parents=True)
    (base / "manifest.json").write_text(json.dumps({
        "run_id": run_id,
        "generated_at": "2026-01-01",
        "drug": {"brand": "Ibrance", "generic": "Palbociclib", "area": "Oncology"},
    }))
    (base / "source_manifest.json").write_text(json.dumps({"scope": "test", "sources": []}))
    (base / "learning_blueprint.json").write_text(json.dumps({"title": run_id}))
    quiz = {"title": "Quiz", "passing_score": 70, "questions": [
        {"id": "q0", "prompt": "Q0?", "options": ["a", "b", "c", "d"], "correct_index": 1,
         "rationale": "Because.", "option_rationales": ["no", "yes", "no", "no"],
         "citations": [{"title": "T", "locator": "L"}]},
        {"id": "q1", "prompt": "Q1?", "options": ["a", "b", "c", "d"], "correct_index": 2,
         "rationale": "Because.", "option_rationales": ["no", "no", "yes", "no"],
         "citations": [{"title": "T", "locator": "L"}]},
    ]}
    faq = {"title": "FAQ", "items": []}
    deck = {"title": "Deck", "slides": []}
    story = {"title": "Story", "estimated_duration_seconds": 0, "scenes": []}
    for track in ("hcp", "msl"):
        (base / track / "quiz.json").write_text(json.dumps(quiz))
        (base / track / "faq.json").write_text(json.dumps(faq))
        (base / track / "ppt" / "deck_spec.json").write_text(json.dumps(deck))
        (base / track / "storyboard" / "storyboard.json").write_text(json.dumps(story))
    learning.add_comment(run_id, "anil-shekhar", "deck", "minor", "Tighten slide 3.")
    comment_id = learning.course(run_id)["comments"][0]["id"]
    learning.resolve_comment(run_id, comment_id, "addressed", "Tightened.", "priya-raman")
    learning.publish_version(run_id, "priya-raman", "Slide 3 tightened")
    learning.add_signoff(run_id, "anil-shekhar", "approved")
    learning.publish_course(run_id, "priya-raman", "2026-03-01", "2026-03-31",
                            ["ken-osei", "lucy-whitfield"],
                            max_final_attempts=max_final_attempts)


def _fail(run_id, user_id, questions=4, passing=70):
    answers = {f"q{i}": (i % 4) for i in range(questions)}
    return learning.record_attempt(
        run_id, user_id, "final", answers,
        [{"id": f"q{i}", "correct_index": (i % 4) + 1 % 4} for i in range(questions)],
        passing)


def test_third_failed_final_locks_and_fourth_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _ready(tmp_path, "cap-course")
    for _ in range(3):
        attempt = _fail("cap-course", "ken-osei")
        assert attempt["attempt"]["passed"] is False
    state = learning.attempt_state("cap-course", "ken-osei")
    assert state == {"max": 3, "failed": 3, "remaining": 0, "locked": True}
    with pytest.raises(ValueError, match="No final attempts left"):
        _fail("cap-course", "ken-osei")


def test_warning_before_lock_and_reset_reopens(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _ready(tmp_path, "warn-course")
    assert learning.attempt_notices("warn-course", "ken-osei") == []
    _fail("warn-course", "ken-osei")
    _fail("warn-course", "ken-osei")
    assert learning.attempt_state("warn-course", "ken-osei")["remaining"] == 1
    assert [note["kind"] for note in learning.attempt_notices("warn-course", "ken-osei")] == ["last_chance"]
    _fail("warn-course", "ken-osei")
    assert [note["kind"] for note in learning.attempt_notices("warn-course", "ken-osei")] == ["locked"]
    learning.reset_attempts("warn-course", "ken-osei", user_role="admin")
    state = learning.attempt_state("warn-course", "ken-osei")
    assert state == {"max": 3, "failed": 0, "remaining": 3, "locked": False}
    assert learning.attempt_notices("warn-course", "ken-osei") == []


def test_passing_never_locks_and_baseline_is_uncapped(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _ready(tmp_path, "pass-course")
    for _ in range(5):
        learning.record_attempt("pass-course", "ken-osei", "baseline", {}, [], 70)
    assert learning.attempt_state("pass-course", "ken-osei")["locked"] is False


def test_custom_cap_per_course(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _ready(tmp_path, "cap-one", max_final_attempts=1)
    _fail("cap-one", "ken-osei")
    assert learning.attempt_state("cap-one", "ken-osei")["locked"] is True
    record = learning.course("cap-one")
    assert record["publication"]["max_final_attempts"] == 1


def test_lockout_alert_and_manager_routing(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _ready(tmp_path, "lock-course")
    learning.set_manager("priya-raman", "ken-osei", "sara-nakamura")
    for _ in range(3):
        _fail("lock-course", "ken-osei")
    kinds = {alert["kind"] for alert in learning.noncompliance("lock-course")
             if alert["user_id"] == "ken-osei"}
    assert "locked_out" in kinds
    locked = [item for item in learning.escalation_state("lock-course")["items"]
              if item["kind"] == "locked_out" and item["user_id"] == "ken-osei"]
    assert len(locked) == 1
    assert locked[0]["owner"] == "Sara Nakamura"
    assert locked[0]["level"] == 3


def test_escalation_falls_back_to_admin_without_manager(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _ready(tmp_path, "lock-admin")
    for _ in range(3):
        _fail("lock-admin", "lucy-whitfield")
    locked = [item for item in learning.escalation_state("lock-admin")["items"]
              if item["kind"] == "locked_out" and item["user_id"] == "lucy-whitfield"]
    assert locked[0]["owner"] == "admin"


def test_manager_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    with pytest.raises(ValueError, match="Unknown user"):
        learning.set_manager("priya-raman", "nobody", "sara-nakamura")
    with pytest.raises(ValueError, match="Unknown manager"):
        learning.set_manager("priya-raman", "ken-osei", "nobody")
    with pytest.raises(ValueError, match="cannot manage themselves"):
        learning.set_manager("priya-raman", "ken-osei", "ken-osei")
    with pytest.raises(ValueError, match="permission"):
        learning.set_manager("jordan-feld", "ken-osei", "sara-nakamura")
    entry = learning.set_manager("priya-raman", "ken-osei", "sara-nakamura")
    assert entry["manager"] == "sara-nakamura"
    entry = learning.set_manager("priya-raman", "ken-osei", "")
    assert "manager" not in entry


def test_assessment_endpoint_reports_cap_and_notifications(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _ready(tmp_path, "cap-api")
    for module in learning.MODULES:
        learning.set_module("cap-api", "ken-osei", module["id"], True)
    client = TestClient(app)
    before = client.get("/api/learn/ken-osei/cap-api/assessment/final").json()
    assert before["max_attempts"] == 3
    assert before["attempts_remaining"] == 3
    assert before["locked"] is False
    for _ in range(2):
        response = client.post("/api/learn/ken-osei/cap-api/assessment/final",
                               json={"answers": {"q0": 0}})
        assert response.status_code == 201
    mid = client.get("/api/learn/ken-osei/cap-api/assessment/final").json()
    assert mid["attempts_remaining"] == 1
    kinds = {note["kind"] for note in
             client.get("/api/learn/ken-osei/notifications").json()["notifications"]
             if note["run_id"] == "cap-api"}
    assert "last_chance" in kinds
    response = client.post("/api/learn/ken-osei/cap-api/assessment/final",
                           json={"answers": {"q0": 0}})
    assert response.status_code == 201
    after = client.get("/api/learn/ken-osei/cap-api/assessment/final").json()
    assert after["locked"] is True
    assert after["attempts_remaining"] == 0
    refused = client.post("/api/learn/ken-osei/cap-api/assessment/final",
                          json={"answers": {"q0": 0}})
    assert refused.status_code == 400


def test_cohort_reset_wipes_all_assignees(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _ready(tmp_path, "cohort-reset")
    for module in learning.MODULES:
        learning.set_module("cohort-reset", "ken-osei", module["id"], True)
        learning.set_module("cohort-reset", "lucy-whitfield", module["id"], True)
    learning.record_attempt("cohort-reset", "ken-osei", "baseline", {}, [], 70)
    _fail("cohort-reset", "lucy-whitfield")
    client = TestClient(app)
    missing = client.post("/api/runs/cohort-reset/cohort/reset",
                          json={"user_id": "priya-raman", "confirm_email": "not-an-email"})
    assert missing.status_code == 400
    response = client.post("/api/runs/cohort-reset/cohort/reset", json={
        "user_id": "priya-raman",
        "confirm_email": "priya@example.com",
    })
    assert response.status_code == 200
    assert response.json()["reset"] == 2
    for user_id in ("ken-osei", "lucy-whitfield"):
        summary = learning.summarize(learning.progress("cohort-reset", user_id))
        assert summary["modules_complete"] == 0
        assert summary["attempts"] == 0
        assert summary["certificate"] is None
    refused = client.post("/api/runs/cohort-reset/cohort/reset", json={
        "user_id": "ken-osei",
        "confirm_email": "ken@example.com",
    })
    assert refused.status_code == 400

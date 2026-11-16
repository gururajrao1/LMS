"""Shashi follow-ups: course types, induction board, confused signal.

Induction courses (vision/mission) hide the drug-course tabs and carry a
named finisher board; drug courses keep everything and expose no board.
A learner can flag a module confusing without writing an essay.
"""
import json

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src import agent, learning

ADMIN = "priya-raman"
LEARNER = "ken-osei"
OTHER = "lucy-whitfield"


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    assert learning.person(ADMIN) and learning.person(LEARNER)
    return tmp_path


def _publish(run_id, assignees, due_on="2026-11-30"):
    comment = learning.add_comment(run_id, "anil-shekhar", "deck", "minor", "Tighten slide 3.")
    learning.resolve_comment(run_id, comment["id"], "addressed", "Done.", ADMIN)
    learning.publish_version(run_id, ADMIN, "Seeded")
    learning.add_signoff(run_id, "anil-shekhar", "approved", "Good.")
    learning.publish_course(run_id, ADMIN, "2026-11-01", due_on, assignees)
    return run_id


@pytest.fixture
def api_client(data):
    return TestClient(app)


def _content(data, run_id, title, n_questions=4):
    base = data / "content" / run_id
    (base / "assets").mkdir(parents=True, exist_ok=True)
    (base / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "program_title": title,
        "drug": {"brand": "B", "generic": "g", "area": "a"}}))
    (base / "source_manifest.json").write_text(json.dumps({"scope": "US", "sources": []}))
    (base / "learning_blueprint.json").write_text(json.dumps({"title": title, "audiences": {}}))
    (base / "assets" / "quiz.json").write_text(json.dumps({
        "title": "t", "passing_score": 75,
        "questions": [{"id": f"q{i}", "prompt": f"Q{i}?", "options": ["a", "b"],
                       "correct_index": 0, "rationale": "r", "citations": []}
                      for i in range(n_questions)]}))
    (base / "assets" / "faq.json").write_text(json.dumps({"items": []}))
    (base / "assets" / "video_storyboard.json").write_text(
        json.dumps({"estimated_duration_seconds": 60, "scenes": []}))
    (base / "assets" / "deck_spec.json").write_text(json.dumps({"slides": []}))


def _certify(run_id, user_id):
    questions = [{"id": f"q{i}", "prompt": f"Q{i}?", "options": ["a", "b"],
                  "correct_index": 0, "rationale": "r", "citations": []}
                 for i in range(4)]
    for module in learning.MODULES:
        learning.set_module(run_id, user_id, module["id"], True)
    learning.record_attempt(run_id, user_id, "baseline",
                            {q["id"]: 0 for q in questions}, questions, 75)
    learning.record_attempt(run_id, user_id, "final",
                            {q["id"]: 0 for q in questions}, questions, 75)


def test_course_type_defaults_to_drug(data):
    assert learning.course_type("no-such-run") == "drug"


def test_set_course_type_needs_training_team(data):
    _publish("run-a", [LEARNER])
    with pytest.raises(ValueError, match="Unknown|permission|capability"):
        learning.set_course_type("run-a", LEARNER, "induction")
    with pytest.raises(ValueError, match="induction or drug|must be"):
        learning.set_course_type("run-a", ADMIN, "game-show")
    assert learning.set_course_type("run-a", ADMIN, "induction")["course_type"] == "induction"
    assert learning.course_type("run-a") == "induction"


def test_induction_board_ranks_finishers_by_time(data):
    _publish("run-b", [LEARNER, OTHER])
    learning.set_course_type("run-b", ADMIN, "induction")
    _certify("run-b", LEARNER)
    _certify("run-b", OTHER)
    board = learning.course_board("run-b", LEARNER)
    assert [row["user_id"] for row in board["ranks"]] == [LEARNER, OTHER]
    assert board["your_rank"] == 1
    assert all(row["score"] == 100 for row in board["ranks"])
    assert board["ranks"][0]["name"]


def test_drug_courses_expose_no_board(data):
    _publish("run-c", [LEARNER])
    _certify("run-c", LEARNER)
    assert learning.course_board("run-c", LEARNER)["ranks"] == []


def test_board_is_for_assignees_only(data):
    _publish("run-d", [LEARNER])
    learning.set_course_type("run-d", ADMIN, "induction")
    with pytest.raises(ValueError, match="not been assigned|assigned"):
        learning.course_board("run-d", OTHER)


def test_practice_scores_only_what_was_asked(data):
    """The daily check posts 3 answers against a 12-question quiz; the other
    9 are unasked, not wrong. Regression: submit used to score 3 of 12."""
    questions = [{"id": f"q{i}", "prompt": f"Q{i}?", "options": ["a", "b"],
                  "correct_index": 0, "rationale": "r", "citations": []}
                 for i in range(12)]
    result = learning.reinforce_feedback(questions, {"q0": 0, "q1": 1, "q2": 0})
    assert result["total"] == 3 and result["correct"] == 2


def test_confused_flag_survives_into_cohort_feedback(data):
    _publish("run-e", [LEARNER])
    learning.add_feedback("run-e", LEARNER, "deck", 2, "Lost me at slide 4.", confused=True)
    plain = learning.add_feedback("run-e", LEARNER, "faq", 5, "Clear.")
    assert plain["confused"] is False
    flagged = [entry for entry in learning.cohort("run-e")["feedback"] if entry["confused"]]
    assert len(flagged) == 1 and flagged[0]["module_id"] == "deck"


def test_daily_submit_logs_check_not_attempt(data, api_client):
    """The 2pm check records practice with a peer message, never an attempt."""
    _publish("run-k", [LEARNER, OTHER])
    _content(data, "run-k", "Vision")
    got = api_client.get(f"/api/learn/{LEARNER}/run-k/daily").json()
    assert len(got["questions"]) == 3 and got["today"]["count"] == 0
    answers = {question["id"]: 0 for question in got["questions"]}
    result = api_client.post(f"/api/learn/{LEARNER}/run-k/daily/submit",
                             json={"answers": answers}).json()
    assert result["total"] == 3 and result["today"]["count"] == 1
    assert "before" in result["message"] or "first" in result["message"]
    state = learning.progress("run-k", LEARNER)
    assert state["attempts"] == [] and len(state["daily_checks"]) == 1
    other = api_client.get(f"/api/learn/{OTHER}/run-k/daily").json()
    assert other["today"]["count"] == 1 and other["today"]["before_you"] == 1


def test_inbox_lists_assigned_daily_then_certified(data, api_client):
    _publish("run-j", [LEARNER])
    _content(data, "run-j", "Vision and Core Values")
    kinds = {note["kind"] for note in
             api_client.get(f"/api/learn/{LEARNER}/notifications").json()["notifications"]}
    assert {"assigned", "daily"} <= kinds
    _certify("run-j", LEARNER)
    inbox = api_client.get(f"/api/learn/{LEARNER}/notifications").json()["notifications"]
    assert any(note["kind"] == "certified" and "Code PL-" in note["message"] for note in inbox)
    assert not any(note["kind"] == "daily" for note in inbox)


def test_inbox_flags_overdue_first(data, api_client):
    _publish("run-l", [LEARNER], due_on="2026-11-08")
    _content(data, "run-l", "Vision")
    inbox = api_client.get(f"/api/learn/{LEARNER}/notifications").json()["notifications"]
    assert inbox[0]["kind"] == "overdue"


def test_audit_export_downloads_trail(data, api_client):
    _publish("run-h", [LEARNER])
    response = api_client.get("/api/runs/run-h/export/audit")
    assert response.status_code == 200
    body = response.json()
    assert body["verification"]["ok"] is True and len(body["audit"]) >= 1


def test_organization_stamps_certificate_line(data):
    _publish("run-i", [LEARNER])
    assert learning.set_course_type("run-i", ADMIN, "induction", "Clair Labs")["organization"] == "Clair Labs"
    assert learning.course("run-i")["organization"] == "Clair Labs"

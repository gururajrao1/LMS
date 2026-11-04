"""Shared training material: Q&A extraction, quiz building, and the admin loop.

The contract under test: extraction never invents (a document with no
questions yields no pairs), quizzes stay multiple-choice with a real answer
key, and every admin action (alerts, schedules, resets) reads off the record.
"""

import io
import json

from fastapi.testclient import TestClient

from api.main import app
from src import agent, learning, material


def _upload(tmp_path, monkeypatch, name, text):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    folder = tmp_path / "uploads" / "up1"
    folder.mkdir(parents=True)
    (folder / name).write_bytes(text.encode())
    (folder / "record.json").write_text(json.dumps({"id": "up1", "name": name}))
    return "up1"


def test_extract_qa_finds_markers_questions_and_headings(tmp_path, monkeypatch):
    doc = ("Q: What is the dose?\nA: 125 mg daily for 21 days, then 7 days off.\n\n"
           "How is it taken?\nWith food, at the same time each day, without fail.\n\n"
           "Monitoring\nNeutrophils are checked at baseline and each cycle without exception.\n\n"
           "Plain paragraph with no question in it at all, just background.")
    _upload(tmp_path, monkeypatch, "label.txt", doc)
    result = material.save_qa("up1")
    questions = [pair["question"] for pair in result["pairs"]]
    assert any("dose" in question for question in questions)
    assert "How is it taken?" in questions
    assert any("Monitoring" in question for question in questions)
    assert len(questions) <= material.MAX_PAIRS


def test_extract_qa_invents_nothing(tmp_path, monkeypatch):
    _upload(tmp_path, monkeypatch, "prose.txt", "Background.\n\nMore background, no questions anywhere.")
    assert material.save_qa("up1")["pairs"] == []


def test_build_quiz_scores_from_the_material(tmp_path, monkeypatch):
    doc = ("Q: Dose?\nA: The starting dose is 125 mg once daily for 21 days then 7 off.\n\n"
           "Q: Monitoring?\nA: Check neutrophils at baseline and before every single cycle.\n\n"
           "Storage\nStore the capsules at room temperature away from moisture every day.")
    _upload(tmp_path, monkeypatch, "label.txt", doc)
    material.save_qa("up1")
    quiz = material.build_quiz("up1")
    assert len(quiz["questions"]) >= 3 and quiz["passing_score"] == material.PASSING_SCORE
    for question in quiz["questions"]:
        assert len(question["options"]) == 4
        assert question["options"][question["correct_index"]] in {
            pair["answer"][:160] for pair in material.load_qa("up1")["pairs"]} | {"Not stated in the material"}
    assert material.load_quiz("up1")["title"] == quiz["title"]


def test_build_quiz_needs_pairs(tmp_path, monkeypatch):
    _upload(tmp_path, monkeypatch, "prose.txt", "Nothing to ask here.")
    material.save_qa("up1")
    try:
        material.build_quiz("up1")
    except ValueError as error:
        assert "at least two" in str(error)
    else:
        raise AssertionError("expected a ValueError")


def test_next_due_on_follows_the_frequency():
    assert learning.next_due_on("once", "2026-03-15") is None
    assert learning.next_due_on("quarterly", "2026-03-15") == "2026-06-15"
    assert learning.next_due_on("semiannual", "2026-03-15") == "2026-09-15"
    assert learning.next_due_on("annual", "2026-03-15") == "2027-03-15"
    assert learning.next_due_on("quarterly", "not-a-date") is None


def _published(tmp_path, monkeypatch, run_id="ibrance-x"):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    content = tmp_path / "content" / run_id
    content.mkdir(parents=True)
    (content / "manifest.json").write_text(json.dumps({"drug": {"brand": "Ibrance"}}))
    record = learning.course(run_id)
    record.update(status="published", publication={
        "version": 1, "published_at": "2026-01-02T00:00:00+00:00", "published_by": "Priya Raman",
        "overrides": [], "starts_on": "2026-01-01", "due_on": "2020-01-01",
        "frequency": "quarterly", "next_due_on": "2020-04-01", "message": "",
        "assignees": ["ken-osei"], "notifications": []})
    learning._save_course(record)
    state = learning.progress(run_id, "ken-osei")
    state["started_at"] = "2026-01-03T00:00:00+00:00"
    state["attempts"] = [{"id": "a1", "kind": "final", "score": 40, "correct": 2, "total": 5,
                          "passing_score": 67, "passed": False, "answers": {}, "created_at": "2026-01-04T00:00:00+00:00"}]
    learning._save_progress(state)
    return run_id


def test_alerts_flag_overdue_and_below_requirement(tmp_path, monkeypatch):
    run_id = _published(tmp_path, monkeypatch)
    alerts = TestClient(app).get(f"/api/runs/{run_id}/alerts").json()
    assert [alert["severity"] for alert in alerts] == ["danger", "danger", "warning"]
    assert any("Overdue" in alert["message"] for alert in alerts)
    assert any("below the required" in alert["message"] for alert in alerts)
    assert any("baseline" in alert["message"] for alert in alerts)


def test_reset_attempts_clears_answers_and_certificate(tmp_path, monkeypatch):
    run_id = _published(tmp_path, monkeypatch)
    client = TestClient(app)
    before = learning.progress(run_id, "ken-osei")
    assert len(before["attempts"]) == 1
    assert client.delete(f"/api/learn/ken-osei/{run_id}/attempts", params={"by": "priya-raman"}).status_code == 200
    after = learning.progress(run_id, "ken-osei")
    assert after["attempts"] == [] and after["certificate"] is None
    assert after["started_at"] == before["started_at"]
    assert client.delete(f"/api/learn/ken-osei/{run_id}/attempts", params={"by": "ken-osei"}).status_code == 400


def test_dashboard_results_rolls_up_published_courses(tmp_path, monkeypatch):
    run_id = _published(tmp_path, monkeypatch)
    body = TestClient(app).get("/api/dashboard/results").json()
    assert body["assigned"] == 1 and body["certified"] == 0
    assert [row["run_id"] for row in body["courses"]] == [run_id]


def test_xls_export_workbook_has_all_sheets(tmp_path, monkeypatch):
    from openpyxl import load_workbook
    run_id = _published(tmp_path, monkeypatch)
    response = TestClient(app).get(f"/api/runs/{run_id}/export/xls")
    assert response.status_code == 200
    assert "spreadsheetml.sheet" in response.headers["content-type"]
    workbook = load_workbook(io.BytesIO(response.content))
    assert set(workbook.sheetnames) == {"Cohort", "Questions", "Noncompliance", "Feedback"}
    assert [cell.value for cell in workbook["Cohort"][1]][:3] == ["user_id", "name", "role"]


def test_learner_dashboard_rolls_up_one_person(tmp_path, monkeypatch):
    run_id = _published(tmp_path, monkeypatch)
    client = TestClient(app)
    body = client.get("/api/learners/ken-osei/dashboard").json()
    assert body["user"]["name"] == "Dr. Ken Osei"
    assert [row["run_id"] for row in body["courses"]] == [run_id]
    assert body["points"] > 0 and len(body["alerts"]) == 3
    assert client.get("/api/learners/nobody-here/dashboard").status_code == 404

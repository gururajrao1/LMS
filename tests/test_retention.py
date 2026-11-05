"""Retention report and version timeline.

The contract under test: the report inventories what the course actually
holds (never the other way round), flags what is past its keep-until date,
and deletes nothing; the timeline orders versions, sign-offs and
publications oldest-first from the same record the review panels read.
"""

import json

from fastapi.testclient import TestClient

from api.main import app
from src import agent, learning


def _seeded(tmp_path, monkeypatch, run_id="ibrance-ret"):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    content = tmp_path / "content" / run_id
    content.mkdir(parents=True)
    (content / "manifest.json").write_text(json.dumps({"drug": {"brand": "Ibrance"}}))
    record = learning.course(run_id)
    record["versions"] = [
        {"version": 1, "summary": "First draft", "author_id": "agent",
         "author_name": "PharmaLearn agent", "addressed": [], "created_at": "2026-01-01T09:00:00+00:00"},
        {"version": 2, "summary": "Dose table added", "author_id": "priya-raman",
         "author_name": "Priya Raman", "addressed": [], "created_at": "2026-02-01T09:00:00+00:00"},
    ]
    record["version"] = 2
    record.update(status="published", publication={
        "version": 2, "published_at": "2026-02-02T00:00:00+00:00", "published_by": "Priya Raman",
        "overrides": [], "starts_on": "2026-02-01", "due_on": "2026-09-30",
        "frequency": "once", "next_due_on": None, "message": "",
        "assignees": ["ken-osei"],
        "notifications": [{"to": "ken.osei@pharmalearn.local", "name": "Dr. Ken Osei",
                           "subject": "Training assigned", "sent_at": "2020-03-01T00:00:00+00:00"}]})
    learning._save_course(record)
    learning.add_comment(run_id, "anil-shekhar", "deck", "major", "Name the companion diagnostic.")
    state = learning.progress(run_id, "ken-osei")
    state["started_at"] = "2026-02-03T00:00:00+00:00"
    state["attempts"] = [{"id": "a1", "kind": "baseline", "score": 60, "correct": 3, "total": 5,
                          "passing_score": 67, "passed": False, "answers": {},
                          "created_at": "2020-04-01T00:00:00+00:00"}]
    state["certificate"] = {"id": "c1", "code": "PL-IBRANCE-2026-ABC",
                            "issued_at": "2026-02-04T00:00:00+00:00"}
    learning._save_progress(state)
    staged = tmp_path / "uploads" / "up1"
    staged.mkdir(parents=True)
    (staged / "record.json").write_text(json.dumps({"id": "up1"}))
    (staged / "label.txt").write_text("dose")
    return run_id


def _classes(report):
    return {entry["id"]: entry for entry in report["classes"]}


def test_retention_counts_what_the_course_holds(tmp_path, monkeypatch):
    report = learning.retention(_seeded(tmp_path, monkeypatch))
    assert [entry["id"] for entry in report["classes"]] == [policy[0] for policy in learning.RETENTION_POLICIES]
    by_id = _classes(report)
    assert by_id["assessments"]["items"] == 1 and by_id["assessments"]["status"] == "due"
    assert by_id["assessments"]["first_due"] == "2022-04-01"
    assert by_id["assessments"]["due_for_review"] == 1
    assert by_id["certificates"]["items"] == 1 and by_id["certificates"]["status"] == "within policy"
    assert by_id["notices"]["items"] == 1 and by_id["notices"]["status"] == "due"
    assert by_id["uploads"]["items"] == 1 and by_id["uploads"]["status"] == "within policy"
    assert by_id["review"]["items"] >= 3 and by_id["feedback"]["status"] == "empty"


def test_timeline_orders_versions_signoffs_and_publication(tmp_path, monkeypatch):
    run_id = _seeded(tmp_path, monkeypatch)
    learning.add_signoff(run_id, "anil-shekhar", "approved", "Reads well")
    timeline = learning.version_timeline(run_id)
    kinds = [event["kind"] for event in timeline["events"]]
    assert kinds == ["version", "version", "publication", "signoff"]
    assert [event["at"] for event in timeline["events"]] == sorted(
        event["at"] for event in timeline["events"])
    assert timeline["events"][0]["title"] == "Version 1"
    assert timeline["events"][2]["actor"] == "Priya Raman"
    assert timeline["events"][-1]["actor"] == "Dr. Anil Shekhar"


def test_report_endpoints(tmp_path, monkeypatch):
    run_id = _seeded(tmp_path, monkeypatch)
    client = TestClient(app)
    report = client.get(f"/api/runs/{run_id}/retention").json()
    assert _classes(report)["assessments"]["due_for_review"] == 1
    timeline = client.get(f"/api/runs/{run_id}/timeline").json()
    assert timeline["version"] == 2 and timeline["status"] == "published"
    assert timeline["events"][0]["kind"] == "version"

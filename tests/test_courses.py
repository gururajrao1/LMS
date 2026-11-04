import io
import json
import zipfile

from fastapi.testclient import TestClient
from api.main import app, courses
from src import agent, learning


def _run(tmp_path, run_id, generated_at):
    path = tmp_path / "content" / run_id / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "run_id": run_id,
        "generated_at": generated_at,
        "drug": {"brand": "Ibrance", "generic": "Palbociclib", "area": "Oncology"},
    }))


def test_courses_use_latest_run_per_drug(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    for run_id, generated_at in [("ibrance-old", "2026-01-01"), ("ibrance-new", "2026-02-01")]:
        _run(tmp_path, run_id, generated_at)

    result = courses()
    ibrance = [course for course in result if course["name"] == "Ibrance"]
    assert len(ibrance) == 1
    assert ibrance[0]["run_id"] == "ibrance-new"


def test_a_new_run_never_hides_the_published_course(tmp_path, monkeypatch):
    """Generating during a demo must not remove the course a cohort is working through."""
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _run(tmp_path, "ibrance-published", "2026-01-01")
    _run(tmp_path, "ibrance-fresh", "2026-02-01")
    learning.add_comment("ibrance-published", "anil-shekhar", "deck", "minor", "Tighten slide 3.")
    learning.resolve_comment("ibrance-published", learning.course("ibrance-published")["comments"][0]["id"],
                             "addressed", None, "priya-raman")
    learning.publish_version("ibrance-published", "priya-raman", "Slide 3 tightened")
    learning.add_signoff("ibrance-published", "anil-shekhar", "approved")
    learning.publish_course("ibrance-published", "priya-raman", "2026-03-01", "2026-03-31", ["ken-osei"])

    result = [course for course in courses() if course["name"] == "Ibrance"]

    assert [course["run_id"] for course in result] == ["ibrance-published", "ibrance-fresh"]
    assert result[0]["review_status"] == "published"
    assert result[0]["assigned"] == 1
    assert result[1]["review_status"] == "draft"


def test_export_completions_csv_for_external_lms(tmp_path, monkeypatch):
    """Completions must leave the app as CSV for an external LMS or audit pack."""
    monkeypatch.setattr(agent, "DATA", tmp_path)
    run_id = "ibrance-export"
    _run(tmp_path, run_id, "2026-01-01")
    learning.add_comment(run_id, "anil-shekhar", "deck", "minor", "Tighten slide 3.")
    comment_id = learning.course(run_id)["comments"][0]["id"]
    learning.resolve_comment(run_id, comment_id, "addressed", "Tightened.", "priya-raman")
    learning.publish_version(run_id, "priya-raman", "Slide 3 tightened")
    learning.add_signoff(run_id, "anil-shekhar", "approved")
    learning.publish_course(run_id, "priya-raman", "2026-03-01", "2026-03-31", ["ken-osei"])
    response = TestClient(app).get(f"/api/runs/{run_id}/export/completions")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("user_id,name,role")
    assert any("ken-osei" in line for line in lines[1:])
    assert f"{run_id}-completions.csv" in response.headers["content-disposition"]


def _quiz_for(tmp_path, run_id, questions):
    path = tmp_path / "content" / run_id / "assets" / "quiz.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"questions": questions}))


def _question(qid, prompt, correct=0):
    return {"id": qid, "prompt": prompt, "options": ["a", "b", "c", "d"], "correct_index": correct, "rationale": "r", "citations": []}


def test_refresh_diff_flags_changed_questions_and_recertification(tmp_path, monkeypatch):
    """Label-change refresh: the new version names exactly what must be re-reviewed."""
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _run(tmp_path, "ibrance-old", "2026-01-01")
    _run(tmp_path, "ibrance-new", "2026-02-01")
    _quiz_for(tmp_path, "ibrance-old", [_question("q1", "Original wording"), _question("q2", "Retired")])
    _quiz_for(tmp_path, "ibrance-new", [_question("q1", "Reworded for the label"), _question("q3", "Brand new")])
    client = TestClient(app)
    assert client.get("/api/runs/ibrance-new/refresh/diff").status_code == 400
    diff = client.get("/api/runs/ibrance-new/refresh/diff", params={"against": "ibrance-old"}).json()
    assert diff["changed"] == ["q1"] and diff["removed"] == ["q2"] and diff["added"] == ["q3"]
    assert diff["recertification_required"] is True


def test_scorm_export_contains_manifest_and_quiz(tmp_path, monkeypatch):
    """SCORM package must carry a manifest so an external LMS can import the course."""
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _run(tmp_path, "ibrance-scorm", "2026-01-01")
    _quiz_for(tmp_path, "ibrance-scorm", [_question("q1", "What is the dose?")])
    response = TestClient(app).get("/api/runs/ibrance-scorm/export/scorm")
    assert response.status_code == 200
    assert "application/zip" in response.headers["content-type"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as package:
        assert "imsmanifest.xml" in package.namelist()
        assert any(name.endswith("quiz.json") for name in package.namelist())

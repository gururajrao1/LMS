import json

from api.main import courses
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

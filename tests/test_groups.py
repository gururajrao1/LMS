import json

import pytest
from fastapi.testclient import TestClient
from api.main import app
from src import agent, learning


def _ready(tmp_path, run_id):
    path = tmp_path / "content" / run_id / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "run_id": run_id,
        "generated_at": "2026-01-01",
        "drug": {"brand": "Ibrance", "generic": "Palbociclib", "area": "Oncology"},
    }))
    learning.add_comment(run_id, "anil-shekhar", "deck", "minor", "Tighten slide 3.")
    comment_id = learning.course(run_id)["comments"][0]["id"]
    learning.resolve_comment(run_id, comment_id, "addressed", "Tightened.", "priya-raman")
    learning.publish_version(run_id, "priya-raman", "Slide 3 tightened")
    learning.add_signoff(run_id, "anil-shekhar", "approved")


def test_group_crud_is_gated_and_validated(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    with pytest.raises(ValueError):
        learning.create_learner_group("jordan-feld", "Tech", ["ken-osei"])
    with pytest.raises(ValueError):
        learning.create_learner_group("priya-raman", "Tech", ["nobody-here"])
    group = learning.create_learner_group("priya-raman", "Tech", ["ken-osei"])
    assert group["id"] == "tech"
    with pytest.raises(ValueError):
        learning.create_learner_group("priya-raman", "Tech", ["ken-osei"])
    updated = learning.set_learner_group_members("priya-raman", "tech", ["ken-osei", "jordan-feld"])
    assert updated["members"] == ["ken-osei", "jordan-feld"]
    assert learning.delete_learner_group("priya-raman", "tech") == {"deleted": "tech"}
    assert learning.learner_groups() == []


def test_publish_via_group_expands_assignees(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _ready(tmp_path, "group-course")
    learning.create_learner_group("priya-raman", "Tech", ["jordan-feld", "ken-osei"])
    record = learning.publish_course(
        "group-course", "priya-raman", "2026-03-01", "2026-03-31", [],
        group_ids=["tech"],
    )
    assert record["publication"]["group_ids"] == ["tech"]
    assert set(record["publication"]["assignees"]) == {"jordan-feld", "ken-osei"}
    assert {learner["user_id"] for learner in learning.cohort("group-course")["learners"]} >= {"jordan-feld", "ken-osei"}
    assert any(entry["run_id"] == "group-course" for entry in learning.assignments("jordan-feld"))
    assert not any(entry["run_id"] == "group-course" for entry in learning.assignments("sara-nakamura"))


def test_group_membership_changes_apply_without_republish(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _ready(tmp_path, "group-live")
    learning.create_learner_group("priya-raman", "Tech", ["jordan-feld"])
    learning.publish_course("group-live", "priya-raman", "2026-03-01", "2026-03-31", [], group_ids=["tech"])
    learning.set_learner_group_members("priya-raman", "tech", ["jordan-feld", "sara-nakamura"])
    assert learning.is_assigned(learning.course("group-live"), "sara-nakamura")
    # Cohort/board follow live membership so Measure matches /learn.
    assert {row["user_id"] for row in learning.cohort("group-live")["learners"]} >= {
        "jordan-feld", "sara-nakamura",
    }
    learning.set_learner_group_members("priya-raman", "tech", ["sara-nakamura"])
    # Removed members stay assigned via the publish-time assignee snapshot.
    assert learning.is_assigned(learning.course("group-live"), "jordan-feld")


def test_group_endpoints_and_cohort(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    _ready(tmp_path, "group-api")
    client = TestClient(app)
    created = client.post("/api/groups", json={"by_user_id": "priya-raman", "label": "Tech", "member_ids": ["ken-osei"]})
    assert created.status_code == 201
    assert [group["id"] for group in client.get("/api/groups").json()] == ["tech"]
    published = client.post("/api/runs/group-api/publication", json={
        "user_id": "priya-raman", "starts_on": "2026-03-01", "due_on": "2026-03-31",
        "assignees": [], "group_ids": ["tech"],
    })
    assert published.status_code == 200
    cohort = client.get("/api/runs/group-api/cohort").json()
    assert {learner["user_id"] for learner in cohort["learners"]} >= {"ken-osei"}

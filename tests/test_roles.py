"""Custom roles and capability enforcement.

The contract under test: built-ins behave exactly as before (admins do
everything, reviewers sign off, settle and reset, learners only learn), and
custom roles grant precisely the capabilities they list — nothing more.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src import agent, learning


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    learning.roster()
    return TestClient(app)


def test_builtin_capabilities_preserve_the_old_gates(data):
    assert learning.capabilities_for("admin") == set(learning.CAPABILITY_IDS) - {"review.signoff"}
    assert learning.capabilities_for("reviewer") == {"review.signoff", "review.resolve", "learn.reset"}
    assert learning.capabilities_for("msl") == set()
    assert learning.capabilities_for("hcp") == set()
    assert learning.capabilities_for("checker") == set()
    assert learning.capabilities_for("no-such-role") == set()


def test_only_admins_manage_roles(data):
    with pytest.raises(ValueError, match="lacks the 'Manage people and roles' permission"):
        learning.create_role("anil-shekhar", "Instructor", capabilities=["review.signoff"])
    role = learning.create_role("priya-raman", "Instructor", "Field trainers who review",
                                ["review.signoff", "review.resolve"])
    assert role["id"] == "instructor" and role["builtin"] is False
    assert [entry["id"] for entry in learning.roles()][-1] == "instructor"


def test_create_role_validates_its_grant(data):
    with pytest.raises(ValueError, match="Unknown capabilities"):
        learning.create_role("priya-raman", "Scheduler", capabilities=["fly.starship"])
    learning.create_role("priya-raman", "Scheduler", capabilities=["course.publish"])
    with pytest.raises(ValueError, match="already a 'scheduler' role"):
        learning.create_role("priya-raman", "Scheduler", capabilities=[])
    with pytest.raises(ValueError, match="follows the msl or hcp track"):
        learning.create_role("priya-raman", "Trainee", capabilities=[], learner=True, track="admin")


def test_assign_role_moves_people_and_stays_off_the_machine(data):
    learning.create_role("priya-raman", "Instructor", capabilities=["review.signoff", "course.publish"])
    moved = learning.assign_role("priya-raman", "anil-shekhar", "instructor")
    assert moved["role"] == "instructor"
    assert set(moved["capabilities"]) == {"review.signoff", "course.publish"}
    assert moved["learner"] is False
    with pytest.raises(ValueError, match="not assignable"):
        learning.assign_role("priya-raman", "ken-osei", "checker")
    with pytest.raises(ValueError, match="Unknown role"):
        learning.assign_role("priya-raman", "ken-osei", "dean")
    with pytest.raises(ValueError, match="lacks the 'Manage people and roles' permission"):
        learning.assign_role("ken-osei", "lucy-whitfield", "instructor")


def test_delete_role_refuses_while_held(data):
    learning.create_role("priya-raman", "Instructor", capabilities=["review.signoff"])
    learning.assign_role("priya-raman", "anil-shekhar", "instructor")
    with pytest.raises(ValueError, match="still held by"):
        learning.delete_role("priya-raman", "instructor")
    with pytest.raises(ValueError, match="Built-in"):
        learning.delete_role("priya-raman", "reviewer")
    learning.assign_role("priya-raman", "anil-shekhar", "reviewer")
    assert learning.delete_role("priya-raman", "instructor") == {"deleted": "instructor"}


def test_custom_learner_role_gets_a_track(data):
    learning.create_role("priya-raman", "Trainee nurse", capabilities=[],
                         learner=True, track="hcp")
    assert learning.is_learner_role("trainee-nurse") is True
    assert learning.is_learner_role("reviewer") is False
    assert learning.is_learner_role("hcp") is True
    assert learning.track_for("trainee-nurse") == "hcp"
    assert learning.track_for("admin") == "hcp" and learning.track_for("msl") == "msl"
    guest = learning.sign_in(user_id=None, email="new.trainee@pharmalearn.local", role="trainee-nurse")
    assert guest["role"] == "trainee-nurse"
    assert learning.sign_in(user_id=None, email="impostor@pharmalearn.local", role="dean")["role"] == "hcp"


def test_capability_gate_opens_and_closes_review_work(data):
    learning.create_role("priya-raman", "Instructor",
                         capabilities=["review.signoff", "review.resolve", "review.assign"])
    learning.assign_role("priya-raman", "maria-alvarez", "instructor")
    comment = learning.add_comment("role-run", "priya-raman", "deck", "major", "Fix the dosing table.")
    settled = learning.resolve_comment("role-run", comment["id"], "addressed", "Table fixed.", user_id="priya-raman")
    assert settled["resolved_by_name"] == "Priya Raman"
    assigned = learning.assign_reviewers("role-run", "maria-alvarez", ["anil-shekhar"])
    assert assigned["review_assignment"]["reviewers"] == ["anil-shekhar"]
    instructor_settled = learning.resolve_comment("role-run", comment["id"], "addressed", "Table fixed.", user_id="maria-alvarez")
    assert instructor_settled["resolved_by_name"] == "Dr. Maria Alvarez"
    with pytest.raises(ValueError, match="lacks the 'Assign reviewers' permission"):
        learning.assign_reviewers("role-run", "ken-osei", ["anil-shekhar"])
    with pytest.raises(ValueError, match="lacks the 'Settle review comments' permission"):
        learning.resolve_comment("role-run", comment["id"], "addressed", "Nope.", user_id="ken-osei")


def test_reset_accepts_a_capability_holder(data):
    learning.create_role("priya-raman", "Support", capabilities=["learn.reset"])
    learning.assign_role("priya-raman", "jordan-feld", "support")
    record = learning.progress("role-run", "ken-osei")
    record["attempts"] = [{"id": "a1", "kind": "final"}]
    learning._save_progress(record)
    learning.reset_attempts("role-run", "ken-osei", actor_id="jordan-feld")
    assert learning.progress("role-run", "ken-osei")["attempts"] == []
    with pytest.raises(ValueError, match="lacks the 'Reset learner answers' permission"):
        learning.reset_attempts("role-run", "ken-osei", actor_id="ken-osei")


def test_role_endpoints_serve_the_builder(data):
    assert [entry["id"] for entry in data.get("/api/capabilities").json()] == list(learning.CAPABILITY_IDS)
    assert data.get("/api/roles").json()[0]["id"] == "admin"
    denied = data.post("/api/roles", json={"by_user_id": "ken-osei", "label": "Scheduler"})
    assert denied.status_code == 400
    created = data.post("/api/roles", json={
        "by_user_id": "priya-raman", "label": "Scheduler",
        "description": "Publishes approved courses",
        "capabilities": ["course.publish", "course.version"], "learner": False, "track": "hcp",
    })
    assert created.status_code == 201
    assert data.get("/api/roles").json()[-1]["id"] == "scheduler"
    moved = data.post("/api/people/ken-osei/role",
                      json={"by_user_id": "priya-raman", "role_id": "scheduler"})
    assert moved.status_code == 200 and moved.json()["role"] == "scheduler"
    session = data.post("/api/session", json={"user_id": "ken-osei"})
    assert session.json()["capabilities"] == ["course.publish", "course.version"]
    assert session.json()["learner"] is False
    assert data.delete("/api/roles/scheduler", params={"by_user_id": "priya-raman"}).status_code == 400
    data.post("/api/people/ken-osei/role",
              json={"by_user_id": "priya-raman", "role_id": "hcp"})
    assert data.delete("/api/roles/scheduler", params={"by_user_id": "priya-raman"}).json() == {"deleted": "scheduler"}

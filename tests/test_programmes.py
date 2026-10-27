import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src import agent, learning, programmes

RUN_ID = "ibrance-programme"
ADMIN, REVIEWER, LEARNER = "priya-raman", "anil-shekhar", "ken-osei"


@pytest.fixture(autouse=True)
def no_billed_calls(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    base = tmp_path / "content" / RUN_ID
    (base / "assets").mkdir(parents=True)
    (base / "manifest.json").write_text(json.dumps({
        "run_id": RUN_ID, "generated_at": "2026-08-01",
        "drug": {"brand": "Ibrance", "generic": "Palbociclib", "area": "Oncology"},
    }))
    for name, value in [("faq.json", {"items": []}), ("deck_spec.json", {"slides": []}),
                        ("video_storyboard.json", {"estimated_duration_seconds": 60, "scenes": []}),
                        ("quiz.json", {"title": "Q", "passing_score": 75, "questions": []})]:
        (base / "assets" / name).write_text(json.dumps(value))
    (base / "source_manifest.json").write_text(json.dumps({"scope": "US", "sources": []}))
    (base / "learning_blueprint.json").write_text(json.dumps({"title": "T", "audiences": {}}))
    return TestClient(app)


def _publish(starts: str, due: str, assignees=(LEARNER,)):
    comment = learning.add_comment(RUN_ID, REVIEWER, "deck", "major", "Tighten slide 3.")
    learning.resolve_comment(RUN_ID, comment["id"], "addressed", "Done.", ADMIN)
    learning.publish_version(RUN_ID, ADMIN, "v2")
    learning.add_signoff(RUN_ID, REVIEWER, "approved")
    return learning.publish_course(RUN_ID, ADMIN, starts, due, list(assignees))


def test_an_unpublished_course_is_not_yet_a_programme(client):
    """Content is not a programme until it is in the field with a cohort and a date."""
    assert programmes.programme(RUN_ID)["state"] == "draft"
    assert programmes.for_client()["programmes"] == []


@pytest.mark.parametrize("today,expected", [
    ("2026-08-25", "scheduled"),
    ("2026-09-15", "live"),
    ("2026-10-05", "completed"),
])
def test_the_calendar_decides_whether_a_programme_is_scheduled_live_or_done(client, today, expected):
    """Derived, never stored: a label computed from the dates cannot drift from them."""
    _publish("2026-09-01", "2026-09-30")

    assert programmes.programme(RUN_ID, date.fromisoformat(today))["state"] == expected


def test_a_fully_certified_cohort_is_complete_before_its_deadline(client):
    """The schedule is a deadline, not the definition of done."""
    _publish("2026-09-01", "2026-09-30")
    record = learning.progress(RUN_ID, LEARNER)
    record["certificate"] = {"id": "c1", "code": "X", "score": 100}
    learning._save_progress(record)

    assert programmes.programme(RUN_ID, date(2026, 9, 15))["state"] == "completed"


def test_archiving_is_attributed_reversible_and_changes_nothing_else(client):
    _publish("2026-09-01", "2026-09-30")

    archived = client.post(f"/api/runs/{RUN_ID}/archive",
                           json={"user_id": ADMIN, "note": "Cycle closed."}).json()

    assert archived["state"] == "archived"
    assert archived["archived"]["by_name"] == "Priya Raman"
    assert archived["archived"]["note"] == "Cycle closed."

    record = learning.course(RUN_ID)
    assert record["status"] == "published"
    assert record["publication"]["assignees"] == [LEARNER]
    assert [entry["action"] for entry in record["audit"]][-1] == "programme.archived"

    # Restoring hands the state back to the calendar, so which state it lands in is
    # the dates' business — covered above. What matters here is that it lets go.
    restored = client.post(f"/api/runs/{RUN_ID}/restore", json={"user_id": ADMIN}).json()
    assert restored["state"] != "archived"
    assert "archived" not in learning.course(RUN_ID)


def test_only_an_admin_can_archive(client):
    _publish("2026-09-01", "2026-09-30")

    refused = client.post(f"/api/runs/{RUN_ID}/archive", json={"user_id": REVIEWER})

    assert refused.status_code == 400
    assert programmes.programme(RUN_ID)["state"] != "archived"


def test_a_client_view_counts_its_programmes_by_state(client):
    _publish("2026-09-01", "2026-09-30")

    view = client.get("/api/clients/pfizer").json()

    assert view["client"]["name"] == "Pfizer"
    assert view["states"]["live"] + view["states"]["scheduled"] + view["states"]["completed"] == 1
    assert view["programmes"][0]["drug"]["brand"] == "Ibrance"
    assert view["programmes"][0]["cohort"]["assigned"] == 1


def _certify(user_id: str, baseline: int, final: int):
    """Give a learner a measured baseline, every module, and a passing final."""
    for module in learning.MODULES:
        learning.set_module(RUN_ID, user_id, module["id"], True)
    record = learning.progress(RUN_ID, user_id)
    record["attempts"] = [
        {"id": "a", "kind": "baseline", "score": baseline, "correct": 1, "total": 4,
         "passing_score": 75, "passed": False, "created_at": "2026-09-02T00:00:00+00:00"},
        {"id": "b", "kind": "final", "score": final, "correct": 4, "total": 4,
         "passing_score": 75, "passed": final >= 75, "created_at": "2026-09-05T00:00:00+00:00"},
    ]
    learning._save_progress(record)
    if final >= 75:
        learning.issue_certificate(RUN_ID, user_id)


def test_the_portfolio_pools_learners_rather_than_averaging_programmes(client):
    """A mean of means weights a five-person pilot like a five-hundred-person rollout.

    Here: two learners at +10 and one at +40. Pooled that is +20; averaging the two
    learners against the one would say +25, a number no learner produced.
    """
    _publish("2026-09-01", "2026-09-30", assignees=[LEARNER, "lucy-whitfield", "jordan-feld"])
    _certify(LEARNER, 50, 60)
    _certify("lucy-whitfield", 50, 60)
    _certify("jordan-feld", 50, 90)

    uplift = programmes.portfolio()["uplift"]

    assert uplift["learners"] == 3
    assert uplift["points"] == 20
    assert (uplift["baseline"], uplift["final"]) == (50, 70)


def test_the_portfolio_totals_reach_and_governance_across_programmes(client):
    _publish("2026-09-01", "2026-09-30", assignees=[LEARNER, "lucy-whitfield"])
    _certify(LEARNER, 40, 90)

    report = programmes.portfolio()

    assert report["reach"]["assigned"] == 2
    assert report["reach"]["certified"] == 1
    assert report["reach"]["certification_percent"] == 50
    # Agreement is about the checker, so a colleague's comment does not count
    # toward it — there is nothing for a human to have agreed or disagreed with.
    assert report["governance"]["settled"] == 0
    assert report["cost"]["manual_per_certified_usd"] > report["cost"]["per_certified_usd"]
    assert [row["run_id"] for row in report["programmes"]] == [RUN_ID]


def test_an_archived_programme_still_counts_in_the_portfolio(client):
    """Filing a finished programme away must not flatter the numbers."""
    _publish("2026-09-01", "2026-09-30", assignees=[LEARNER])
    before = programmes.portfolio()["reach"]

    client.post(f"/api/runs/{RUN_ID}/archive", json={"user_id": ADMIN, "note": "Done."})

    after = programmes.portfolio()
    assert after["reach"] == before
    assert after["states"]["archived"] == 1


def test_the_journey_cannot_run_ahead_of_the_work(client):
    """Each step is done because its evidence exists, so the spine is a reading of
    the record rather than a status someone remembered to advance."""
    from src import journey

    fresh = journey.steps(RUN_ID)
    assert [step["id"] for step in fresh["steps"]][:2] == ["project", "build"]
    assert fresh["steps"][0]["state"] == "done"          # the manifest exists
    assert fresh["steps"][4]["state"] == "waiting"       # nobody has been assigned
    assert fresh["done"] < fresh["total"]

    # Exactly one step is ever "in progress": the first thing not yet done.
    assert sum(1 for step in fresh["steps"] if step["state"] == "current") == 1

    _publish("2026-09-01", "2026-09-30")
    after = journey.steps(RUN_ID)

    assert after["done"] > fresh["done"]
    assert dict(zip([s["id"] for s in after["steps"]], [s["state"] for s in after["steps"]]))["cohort"] == "done"
    assert after["steps"][-1]["state"] != "done"         # nobody has certified yet


def test_the_journey_carries_the_evidence_for_each_step(client):
    from src import journey

    _publish("2026-09-01", "2026-09-30", assignees=[LEARNER, "lucy-whitfield"])
    steps = {step["id"]: step for step in journey.steps(RUN_ID)["steps"]}

    assert "2 trainees" in steps["cohort"]["evidence"]
    assert "2 notifications" in steps["access"]["evidence"]
    assert steps["schedule"]["evidence"][1] == "2026-09-01 to 2026-09-30"
    assert all(step["href"] for step in steps.values())


def test_an_unknown_client_is_refused(client):
    assert client.get("/api/clients/novartis").status_code == 400


def test_a_course_stored_before_clients_existed_belongs_to_the_default_one(client):
    """Forward-only: nothing already published is rewritten to gain an owner."""
    _publish("2026-09-01", "2026-09-30")
    record = learning.course(RUN_ID)
    assert "client_id" not in record

    assert programmes.programme(RUN_ID)["client_id"] == programmes.DEFAULT_CLIENT
    assert programmes.for_client()["programmes"][0]["run_id"] == RUN_ID

import json

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src import agent, learning

RUN_ID = "ibrance-test"
ADMIN, REVIEWER, LEARNER = "priya-raman", "anil-shekhar", "ken-osei"


def _question(index: int, correct: int):
    return {
        "id": f"q{index}",
        "prompt": f"Question {index}?",
        "options": ["a", "b", "c", "d"],
        "correct_index": correct,
        "rationale": f"Because of evidence {index}.",
        "citations": [{"title": "Label", "url": "https://example.test", "locator": "Section 2.1"}],
    }


@pytest.fixture(autouse=True)
def no_billed_calls(monkeypatch):
    """Tests must never reach the Anthropic API, and never spend money doing it."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    base = tmp_path / "content" / RUN_ID
    (base / "assets").mkdir(parents=True)
    (base / "manifest.json").write_text(json.dumps({
        "run_id": RUN_ID,
        "generated_at": "2026-08-01",
        "drug": {"brand": "Ibrance", "generic": "Palbociclib", "area": "Oncology"},
        "citation_count": 4,
    }))
    (base / "source_manifest.json").write_text(json.dumps({"scope": "US", "sources": []}))
    run_log = tmp_path / "logs" / RUN_ID / "run.json"
    run_log.parent.mkdir(parents=True)
    run_log.write_text(json.dumps({"id": RUN_ID, "created_at": "2026-08-01T09:00:00+00:00", "mode": "local"}))
    (base / "learning_blueprint.json").write_text(json.dumps({"title": "Ibrance course", "audiences": {}}))
    (base / "assets" / "quiz.json").write_text(json.dumps({
        "title": "Knowledge check",
        "passing_score": 75,
        "questions": [_question(index, index % 4) for index in range(4)],
    }))
    (base / "assets" / "faq.json").write_text(json.dumps({"items": []}))
    (base / "assets" / "video_storyboard.json").write_text(json.dumps({"estimated_duration_seconds": 60, "scenes": []}))
    (base / "assets" / "deck_spec.json").write_text(json.dumps({"slides": []}))
    return TestClient(app)


def _publish(client, assignees=(LEARNER,)):
    comment = client.post(f"/api/runs/{RUN_ID}/review/comments", json={
        "user_id": REVIEWER, "target": "deck", "severity": "blocking", "body": "Add the dose-reduction table.",
    }).json()
    client.patch(f"/api/runs/{RUN_ID}/review/comments/{comment['id']}", json={
        "user_id": ADMIN, "status": "addressed", "resolution": "Table added to slide 7.",
    })
    client.post(f"/api/runs/{RUN_ID}/review/versions", json={"user_id": ADMIN, "summary": "Dose table added"})
    client.post(f"/api/runs/{RUN_ID}/review/signoff", json={"user_id": REVIEWER, "decision": "approved"})
    return client.post(f"/api/runs/{RUN_ID}/publication", json={
        "user_id": ADMIN,
        "starts_on": "2026-09-01",
        "due_on": "2026-09-30",
        "assignees": list(assignees),
        "message": "Please complete before the cycle meeting.",
    })


def test_blocking_comment_holds_publication(client):
    client.post(f"/api/runs/{RUN_ID}/review/comments", json={
        "user_id": REVIEWER, "target": "quiz", "severity": "blocking", "body": "Question 3 is unsupported.",
    })
    client.post(f"/api/runs/{RUN_ID}/review/signoff", json={"user_id": REVIEWER, "decision": "approved"})

    review = client.get(f"/api/runs/{RUN_ID}/review").json()
    assert review["readiness"]["can_publish"] is False
    assert review["status"] == "in_review"

    response = client.post(f"/api/runs/{RUN_ID}/publication", json={
        "user_id": ADMIN, "starts_on": "2026-09-01", "due_on": "2026-09-30", "assignees": [LEARNER],
    })
    assert response.status_code == 400


def test_only_a_reviewer_can_sign_off(client):
    """Maker-checker: the admin who addresses comments must not clear the course."""
    self_approval = client.post(f"/api/runs/{RUN_ID}/review/signoff", json={"user_id": ADMIN, "decision": "approved"})
    assert self_approval.status_code == 400
    assert "reviewer" in self_approval.json()["detail"]
    assert client.get(f"/api/runs/{RUN_ID}/review").json()["readiness"]["approvals"] == 0

    response = client.post(f"/api/runs/{RUN_ID}/publication", json={
        "user_id": ADMIN, "starts_on": "2026-09-01", "due_on": "2026-09-30", "assignees": [LEARNER],
    })
    assert response.status_code == 400

    assert client.post(f"/api/runs/{RUN_ID}/review/signoff", json={"user_id": REVIEWER, "decision": "approved"}).status_code == 201
    assert client.get(f"/api/runs/{RUN_ID}/review").json()["readiness"]["can_publish"] is True


def test_a_reviewer_cannot_cut_versions_or_publish(client):
    """The checker judges the content; only the maker moves it forward."""
    comment = client.post(f"/api/runs/{RUN_ID}/review/comments", json={
        "user_id": REVIEWER, "target": "deck", "severity": "minor", "body": "Tighten slide 3.",
    }).json()
    client.patch(f"/api/runs/{RUN_ID}/review/comments/{comment['id']}", json={"user_id": ADMIN, "status": "addressed"})

    assert client.post(f"/api/runs/{RUN_ID}/review/versions", json={"user_id": REVIEWER}).status_code == 400
    assert client.post(f"/api/runs/{RUN_ID}/review/versions", json={"user_id": ADMIN}).status_code == 201

    client.post(f"/api/runs/{RUN_ID}/review/signoff", json={"user_id": REVIEWER, "decision": "approved"})
    schedule = {"starts_on": "2026-09-01", "due_on": "2026-09-30", "assignees": [LEARNER]}
    assert client.post(f"/api/runs/{RUN_ID}/publication", json={"user_id": REVIEWER, **schedule}).status_code == 400
    assert client.post(f"/api/runs/{RUN_ID}/publication", json={"user_id": ADMIN, **schedule}).status_code == 200


def test_a_comment_cannot_be_settled_by_nobody(client):
    """The hole this closes: an unattributed PATCH could clear a blocking finding.

    Dismissing removes a comment from `open_blocking`, which is what flips
    `can_publish`. So an anonymous dismissal was a silent route to publication.
    """
    comment = client.post(f"/api/runs/{RUN_ID}/review/comments", json={
        "user_id": REVIEWER, "target": "quiz", "severity": "blocking", "body": "Q3 is unsupported.",
    }).json()
    path = f"/api/runs/{RUN_ID}/review/comments/{comment['id']}"

    assert client.patch(path, json={"status": "dismissed"}).status_code == 422
    assert client.patch(path, json={"user_id": "nobody", "status": "dismissed"}).status_code == 400
    assert client.get(f"/api/runs/{RUN_ID}/review").json()["readiness"]["open_blocking"] == 1


def test_the_checker_cannot_settle_its_own_findings(client):
    """It raises and it never clears — the same asymmetry that stops it signing off."""
    comment = client.post(f"/api/runs/{RUN_ID}/review/comments", json={
        "user_id": REVIEWER, "target": "deck", "severity": "blocking", "body": "Slide 14 is off-label.",
    }).json()
    path = f"/api/runs/{RUN_ID}/review/comments/{comment['id']}"

    refused = client.patch(path, json={"user_id": learning.CHECKER["id"], "status": "dismissed"})
    assert refused.status_code == 400
    assert "admin or a reviewer" in refused.json()["detail"]
    assert client.patch(path, json={"user_id": LEARNER, "status": "dismissed"}).status_code == 400
    assert client.patch(path, json={
        "user_id": REVIEWER, "status": "dismissed", "resolution": "Slide 14 was already corrected.",
    }).status_code == 200


def test_every_resolution_names_who_made_it(client):
    comment = client.post(f"/api/runs/{RUN_ID}/review/comments", json={
        "user_id": REVIEWER, "target": "faq", "severity": "major", "body": "Name the companion diagnostic.",
    }).json()
    path = f"/api/runs/{RUN_ID}/review/comments/{comment['id']}"

    settled = client.patch(path, json={"user_id": ADMIN, "status": "addressed", "resolution": "Added."}).json()
    assert settled["resolved_by_id"] == ADMIN
    assert settled["resolved_by_name"] == "Priya Raman"
    assert settled["resolved_at"]

    # Reopening drops the attribution: there is no resolution left to own.
    reopened = client.patch(path, json={"user_id": REVIEWER, "status": "open"}).json()
    assert reopened["resolved_by_id"] is None
    assert reopened["resolved_at"] is None


def test_the_audit_trail_records_every_governance_step_and_only_appends(client):
    _publish(client)
    audit = client.get(f"/api/runs/{RUN_ID}/review").json()["audit"]

    assert [entry["action"] for entry in audit] == [
        "comment.raised", "comment.resolved", "version.cut", "signoff.recorded", "course.published",
    ]
    assert [entry["at"] for entry in audit] == sorted(entry["at"] for entry in audit)
    assert {entry["actor_id"] for entry in audit} == {ADMIN, REVIEWER}

    dismissal = audit[1]["detail"]
    assert (dismissal["was"], dismissal["now"]) == ("open", "addressed")
    assert audit[-1]["detail"]["approved_by"] == ["Dr. Anil Shekhar"]

    # Later activity appends; it never edits or removes what is already recorded.
    fresh = client.post(f"/api/runs/{RUN_ID}/review/comments", json={
        "user_id": REVIEWER, "target": "deck", "severity": "minor", "body": "Tighten slide 3.",
    }).json()
    client.patch(f"/api/runs/{RUN_ID}/review/comments/{fresh['id']}",
                 json={"user_id": ADMIN, "status": "dismissed", "resolution": "Editorial."})

    after = client.get(f"/api/runs/{RUN_ID}/review").json()["audit"]
    assert after[:len(audit)] == audit
    assert [entry["action"] for entry in after[len(audit):]] == ["comment.raised", "comment.resolved"]


def test_a_comment_closed_into_a_version_cannot_be_reopened(client):
    comment = client.post(f"/api/runs/{RUN_ID}/review/comments", json={
        "user_id": REVIEWER, "target": "deck", "severity": "major", "body": "Tighten slide 3.",
    }).json()
    path = f"/api/runs/{RUN_ID}/review/comments/{comment['id']}"
    client.patch(path, json={"user_id": ADMIN, "status": "addressed"})
    client.post(f"/api/runs/{RUN_ID}/review/versions", json={"user_id": ADMIN})

    refused = client.patch(path, json={"user_id": ADMIN, "status": "open"})
    assert refused.status_code == 400
    assert "closed into a version" in refused.json()["detail"]


def test_a_course_written_before_the_audit_trail_still_loads(client, tmp_path):
    """Forward-only: existing courses gain an empty trail, they are not rewritten."""
    legacy = tmp_path / "platform" / "courses" / f"{RUN_ID}.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps({
        "run_id": RUN_ID, "version": 3, "status": "in_review",
        "comments": [{
            "id": "old", "target": "deck", "severity": "minor", "body": "Historic.",
            "status": "dismissed", "resolution": "Handled offline.", "version": 1,
            "author_id": REVIEWER, "author_name": "Dr. Anil Shekhar", "author_title": "",
            "created_at": "2026-01-01T00:00:00+00:00", "resolved_at": "2026-01-02T00:00:00+00:00",
        }],
        "versions": [], "signoffs": [], "publication": None,
    }))

    review = client.get(f"/api/runs/{RUN_ID}/review").json()

    assert review["audit"] == []
    assert review["version"] == 3
    assert review["comments"][0]["resolution"] == "Handled offline."
    assert review["comments"][0].get("resolved_by_name") is None


def test_a_change_request_holds_publication_until_the_next_version(client):
    client.post(f"/api/runs/{RUN_ID}/review/signoff", json={"user_id": REVIEWER, "decision": "approved"})
    client.post(f"/api/runs/{RUN_ID}/review/signoff", json={"user_id": "maria-alvarez", "decision": "changes_requested", "note": "Check the AE table."})

    readiness = client.get(f"/api/runs/{RUN_ID}/review").json()["readiness"]
    assert readiness["approvals"] == 1
    assert readiness["changes_requested"] == 1
    assert readiness["can_publish"] is False


def test_version_bump_closes_addressed_comments(client):
    comment = client.post(f"/api/runs/{RUN_ID}/review/comments", json={
        "user_id": REVIEWER, "target": "faq", "severity": "major", "body": "Clarify the escalation path.",
    }).json()
    assert client.post(f"/api/runs/{RUN_ID}/review/versions", json={"user_id": ADMIN}).status_code == 400

    client.patch(f"/api/runs/{RUN_ID}/review/comments/{comment['id']}", json={"user_id": ADMIN, "status": "addressed"})
    record = client.post(f"/api/runs/{RUN_ID}/review/versions", json={
        "user_id": ADMIN, "summary": "Escalation path clarified",
    }).json()

    assert record["version"] == 2
    assert record["comments"][0]["status"] == "closed"
    assert record["versions"][-1]["addressed"] == [comment["id"]]


def test_publication_notifies_every_assignee(client):
    response = _publish(client, assignees=[LEARNER, "lucy-whitfield"])
    assert response.status_code == 200
    publication = response.json()["publication"]
    assert publication["version"] == 2
    assert [entry["to"] for entry in publication["notifications"]] == [
        "ken.osei@pharmalearn.local", "lucy.whitfield@pharmalearn.local",
    ]


def test_unassigned_learner_cannot_open_a_course(client):
    _publish(client)
    assert client.get(f"/api/learn/tom-becker/{RUN_ID}").status_code == 403
    assert client.get(f"/api/learn/{LEARNER}/{RUN_ID}").status_code == 200


def test_learner_completes_the_course_and_earns_a_certificate(client):
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    wrong = {question["id"]: (question["correct_index"] + 1) % 4 for question in quiz["questions"]}
    right = {question["id"]: question["correct_index"] for question in quiz["questions"]}

    baseline = client.get(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/baseline").json()
    assert len(baseline["questions"]) == 2
    assert "correct_index" not in baseline["questions"][0]
    assert client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/baseline", json={"answers": wrong}).json()["attempt"]["score"] == 0

    blocked = client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": right})
    assert blocked.status_code == 400

    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    assert client.get(f"/api/learn/{LEARNER}/{RUN_ID}/certificate").status_code == 404

    result = client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": right}).json()
    assert result["attempt"]["score"] == 100
    assert result["attempt"]["passed"] is True
    assert result["summary"]["uplift"] == 100
    assert result["review"][0]["rationale"]

    certificate = client.get(f"/api/learn/{LEARNER}/{RUN_ID}/certificate").json()
    assert certificate["learner_name"] == "Dr. Ken Osei"
    assert certificate["score"] == 100
    assert certificate["course_version"] == 2
    assert certificate["approved_by"] == [{"name": "Dr. Anil Shekhar", "title": "Therapeutic area expert, oncology"}]
    assert certificate["expires_at"][:4] == str(int(certificate["issued_at"][:4]) + 1)


def test_failing_the_final_withholds_the_certificate(client):
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})

    answers = {question["id"]: question["correct_index"] for question in quiz["questions"][:2]}
    result = client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": answers}).json()

    assert result["attempt"]["score"] == 50
    assert result["attempt"]["passed"] is False
    assert result["summary"]["certificate"] is None
    assert client.get(f"/api/learn/{LEARNER}/{RUN_ID}/certificate").status_code == 404


def test_cohort_reports_progress_and_uplift(client):
    _publish(client, assignees=[LEARNER, "lucy-whitfield"])
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    right = {question["id"]: question["correct_index"] for question in quiz["questions"]}
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/baseline", json={"answers": {}})
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": right})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/feedback", json={
        "module_id": "deck", "rating": 5, "comment": "The dose-reduction table is exactly what I needed.",
    })

    cohort = client.get(f"/api/runs/{RUN_ID}/cohort").json()
    assert cohort["assigned"] == 2
    assert cohort["started"] == 1
    assert cohort["certified"] == 1
    assert cohort["average_uplift"] == 100
    assert cohort["feedback"][0]["name"] == "Dr. Ken Osei"
    waiting = next(entry for entry in cohort["learners"] if entry["user_id"] == "lucy-whitfield")
    assert waiting["stage"] == "not_started"


def test_analytics_reports_the_funnel_difficulty_and_roi(client):
    _publish(client, assignees=[LEARNER, "lucy-whitfield"])
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    half = {
        question["id"]: question["correct_index"] if index < 2 else (question["correct_index"] + 1) % 4
        for index, question in enumerate(quiz["questions"])
    }
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/baseline", json={"answers": {}})
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": half})

    report = client.get(f"/api/runs/{RUN_ID}/analytics").json()

    assert [stage["count"] for stage in report["funnel"]] == [2, 1, 1, 1, 0, 0]
    assert report["funnel"][0]["stage"] == "Assigned"
    # q0 and q1 were answered correctly, q2 and q3 were not.
    assert [entry["percent"] for entry in report["difficulty"]] == [0, 0, 100, 100]
    assert report["difficulty"][0]["prompt"]
    assert sum(band["count"] for band in report["score_bands"]) == 1
    assert report["roi"]["baseline"]["first_version_days"] == 30
    assert report["roi"]["saving"]["percent_faster"] is not None
    assert {module["id"] for module in report["modules"]} == {module["id"] for module in learning.MODULES}


def test_analytics_is_quiet_before_publication(client):
    report = client.get(f"/api/runs/{RUN_ID}/analytics").json()
    assert report["funnel"][0]["count"] == 0
    assert report["difficulty"] == []
    assert report["roi"]["measured"]["days_to_publish"] is None


@pytest.mark.parametrize("today,expected", [
    ("2026-08-25", "upcoming"),
    ("2026-09-15", "due"),
    ("2026-10-05", "overdue"),
])
def test_a_learners_assignment_state_follows_the_schedule(client, today, expected):
    from datetime import date

    publication = {"starts_on": "2026-09-01", "due_on": "2026-09-30"}
    summary = {"certificate": None}

    assert learning.assignment_state(publication, summary, date.fromisoformat(today)) == expected


def test_nothing_is_overdue_for_someone_who_already_finished_it(client):
    """Their own progress first: a certificate is done whatever the calendar says."""
    from datetime import date

    publication = {"starts_on": "2026-09-01", "due_on": "2026-09-30"}

    assert learning.assignment_state(publication, {"certificate": {"id": "c1"}}, date(2026, 12, 1)) == "completed"


def test_learner_home_carries_the_schedule_for_each_assignment(client):
    _publish(client)

    home = client.get(f"/api/learn/{LEARNER}").json()

    course = home["courses"][0]
    assert course["state"] in learning.ASSIGNMENT_STATES
    assert course["days_remaining"] is not None
    assert course["days_until_start"] is not None
    # The window itself, so the client can place today inside it without a clock.
    assert (course["starts_on"], course["due_on"]) == ("2026-09-01", "2026-09-30")


def test_learner_home_lists_only_assigned_courses(client):
    _publish(client)
    assert client.get(f"/api/learn/{LEARNER}").json()["courses"][0]["run_id"] == RUN_ID
    assert client.get("/api/learn/tom-becker").json()["courses"] == []


def test_literal_escapes_are_decoded_before_content_is_stored():
    """A model can emit the six characters `\\u2013` inside a JSON string value."""
    emitted = {
        "drug": {"area": "Oncology \\u2013 HR-positive breast cancer"},
        "claims": [{"text": "Grade \\u22653 neutropenia", "count": 7}],
    }

    assert agent.decode_literal_escapes(emitted) == {
        "drug": {"area": "Oncology – HR-positive breast cancer"},
        "claims": [{"text": "Grade ≥3 neutropenia", "count": 7}],
    }
    assert agent.decode_literal_escapes("already – clean") == "already – clean"


@pytest.mark.parametrize(("passing_score", "expected"), [(75, 75), (8, 80), (10, 100), (100, 100)])
def test_passing_percent_normalizes_counts(passing_score, expected):
    quiz = {"passing_score": passing_score, "questions": [_question(index, 0) for index in range(10)]}
    assert agent.passing_percent(quiz) == expected


def test_evidence_recovers_the_supporting_text_behind_a_citation(client):
    """Assets carry only title/locator; the dossier keeps what the source actually said."""
    base = agent.DATA / "content" / RUN_ID / "master"
    base.mkdir(parents=True)
    label = {"title": "IBRANCE Label", "url": "https://dailymed.test/spl", "locator": "5.1"}
    (base / "dossier.json").write_text(json.dumps({
        "drug": {"brand": "Ibrance"},
        "title": "Ibrance dossier",
        "sections": [{
            "id": "05_safety", "title": "Safety", "summary": "",
            "claims": [
                {"text": "Neutropenia requires a blood count before each cycle.", "evidence_type": "FDA label",
                 "citations": [{**label, "supporting_text": "Monitor complete blood counts prior to the start of therapy."}]},
                {"text": "Dose reduction is advised for Grade 3 neutropenia.", "evidence_type": "FDA label",
                 "citations": [{**label, "supporting_text": "Manage with dose interruption or reduction."}]},
            ],
        }],
    }))

    response = client.get(f"/api/runs/{RUN_ID}/evidence", params={"title": "IBRANCE Label", "locator": "5.1"})
    found = response.json()

    assert response.status_code == 200
    assert found["citation"]["supporting_text"].startswith("Monitor complete blood counts")
    assert found["claim"]["section_title"] == "Safety"
    assert found["claim"]["evidence_type"] == "FDA label"
    assert found["supports_claims"] == 2
    assert found["related"][0]["text"].startswith("Dose reduction")

    missing = client.get(f"/api/runs/{RUN_ID}/evidence", params={"title": "Some other source", "locator": "1"})
    assert missing.status_code == 404


def test_chat_answers_from_the_dossier(client):
    base = agent.DATA / "content" / RUN_ID / "master"
    base.mkdir(parents=True)
    (base / "dossier.json").write_text(json.dumps({
        "drug": {"brand": "Ibrance"},
        "title": "Ibrance dossier",
        "sections": [{
            "id": "05_safety",
            "title": "Safety",
            "summary": "",
            "claims": [
                {
                    "text": "Neutropenia is the most common adverse reaction and requires a blood count before each cycle.",
                    "evidence_type": "label",
                    "citations": [{"title": "Label", "url": "https://example.test", "locator": "5.1", "supporting_text": "..."}],
                },
                {"text": "The capsule is taken with food.", "evidence_type": "label", "citations": []},
            ],
        }],
    }))

    response = client.post(f"/api/runs/{RUN_ID}/chat", json={"question": "How do I monitor for neutropenia?"}).json()

    assert response["mode"] == "retrieval"
    assert "Neutropenia" in response["answer"]
    assert response["citations"][0]["locator"] == "5.1"


def test_assigning_reviewers_records_who_and_notifies_them(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    record = learning.assign_reviewers("ibrance-1", "priya-raman", ["anil-shekhar"], "Focus on efficacy.")

    assignment = record["review_assignment"]
    assert assignment["reviewers"] == ["anil-shekhar"]
    assert assignment["assigned_by"] == "Priya Raman"
    assert assignment["version"] == record["version"]
    assert assignment["note"] == "Focus on efficacy."
    assert [entry["to"] for entry in assignment["notifications"]] == ["anil.shekhar@pharmalearn.local"]
    assert any(entry["action"] == "review.assigned" for entry in record["audit"])


def test_only_an_admin_assigns_and_only_a_reviewer_can_be_assigned(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    with pytest.raises(ValueError, match="Only an admin"):
        learning.assign_reviewers("ibrance-1", "anil-shekhar", ["maria-alvarez"])
    with pytest.raises(ValueError, match="Not a reviewer"):
        learning.assign_reviewers("ibrance-1", "priya-raman", ["ken-osei"])
    with pytest.raises(ValueError, match="Unknown reviewer"):
        learning.assign_reviewers("ibrance-1", "priya-raman", ["nobody"])
    with pytest.raises(ValueError, match="at least one reviewer"):
        learning.assign_reviewers("ibrance-1", "priya-raman", [])


def test_assignment_does_not_gate_who_may_sign_off(tmp_path, monkeypatch):
    """Naming a reviewer says whose queue it is, not who is permitted to act.

    A hard lock would strand a course whose named expert is on leave, which is a
    worse failure than an unexpected reviewer clearing it — that is attributed
    anyway.
    """
    monkeypatch.setattr(agent, "DATA", tmp_path)
    learning.assign_reviewers("ibrance-1", "priya-raman", ["anil-shekhar"])
    signoff = learning.add_signoff("ibrance-1", "maria-alvarez", "approved", "Picked this up.")
    assert signoff["decision"] == "approved"

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
    assert "Sign off reviews" in self_approval.json()["detail"]
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
    assert "Settle review comments" in refused.json()["detail"]
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
    assert result["summary"]["points"] == 4 * 25 + 100 + 100  # modules + final + uplift bonus
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
    with pytest.raises(ValueError, match="Assign reviewers"):
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


def test_reinforce_collects_only_missed_questions(client):
    """Spaced reinforcement: practice what this learner actually missed, never the answer key."""
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    answers = {question["id"]: question["correct_index"] for question in quiz["questions"][:2]}
    answers[quiz["questions"][2]["id"]] = (quiz["questions"][2]["correct_index"] + 1) % 4
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": answers})
    practice = client.get(f"/api/learn/{LEARNER}/{RUN_ID}/reinforce").json()
    assert practice["missed_count"] >= 1
    assert all("correct_index" not in question for question in practice["questions"])
    assert all("rationale" not in question for question in practice["questions"])


def test_reinforce_submit_returns_correctness_plus_rationale(client):
    """Practice stays honest on GET; the POST after the attempt teaches."""
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    half = {question["id"]: question["correct_index"] if index < 2
            else (question["correct_index"] + 1) % 4
            for index, question in enumerate(quiz["questions"])}
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": half})
    practice = client.get(f"/api/learn/{LEARNER}/{RUN_ID}/reinforce").json()
    assert practice["missed_count"] >= 1
    assert all("rationale" not in question and "correct_index" not in question
               for question in practice["questions"])
    right = {question["id"]: question["correct_index"] for question in quiz["questions"]}
    feedback = client.post(f"/api/learn/{LEARNER}/{RUN_ID}/reinforce/submit",
                           json={"answers": right}).json()
    assert feedback["correct"] == feedback["total"] == len(quiz["questions"])
    assert all(item["correct"] and item["rationale"] for item in feedback["items"])


def test_audit_exceptions_empty_on_clean_publish_and_verify_passes(client):
    """Review-by-exception: a clean course shows three empty lists; the chain verifies."""
    _publish(client)
    exceptions = client.get(f"/api/runs/{RUN_ID}/audit/exceptions").json()
    assert exceptions["overrides"] == [] and exceptions["challenged_dismissals"] == []
    assert exceptions["late_signoffs"] == []
    report = client.get(f"/api/runs/{RUN_ID}/audit/verify").json()
    assert report["ok"] is True and report["checked"] >= 5 and report["failed_at"] is None


def test_audit_verify_catches_tampering(client):
    """Editing a recorded entry breaks the chain at that entry."""
    _publish(client)
    record = learning.course(RUN_ID)
    record["audit"][0]["summary"] += " (edited)"
    learning._save_course(record)
    report = client.get(f"/api/runs/{RUN_ID}/audit/verify").json()
    assert report["ok"] is False and report["failed_at"] == record["audit"][0]["id"]


def test_attested_signoff_binds_identity_meaning_and_method(client):
    """Part 11 step: typed-name attestation records who, when, and what it means."""
    comment = client.post(f"/api/runs/{RUN_ID}/review/comments", json={
        "user_id": REVIEWER, "target": "deck", "severity": "blocking", "body": "Add the table.",
    }).json()
    client.patch(f"/api/runs/{RUN_ID}/review/comments/{comment['id']}", json={
        "user_id": ADMIN, "status": "addressed", "resolution": "Added."})
    client.post(f"/api/runs/{RUN_ID}/review/versions", json={"user_id": ADMIN})
    refused = client.post(f"/api/runs/{RUN_ID}/review/signoff", json={
        "user_id": REVIEWER, "decision": "approved", "attest": "Someone Else"})
    assert refused.status_code == 400
    signoff = client.post(f"/api/runs/{RUN_ID}/review/signoff", json={
        "user_id": REVIEWER, "decision": "approved", "attest": "Dr. Anil Shekhar"}).json()
    assert signoff["attested"] is True and signoff["method"] == "typed-name"
    assert signoff["meaning"] == "approval"


def test_reset_revokes_certificate_and_verify_reports_it(client):
    """A reset code reads as revoked, not as never-issued."""
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    right = {question["id"]: question["correct_index"] for question in quiz["questions"]}
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": right})
    code = client.get(f"/api/learn/{LEARNER}/{RUN_ID}/certificate").json()["code"]
    assert client.get("/api/certificates/verify", params={"code": code}).json()["status"] == "valid"
    client.delete(f"/api/learn/{LEARNER}/{RUN_ID}/attempts", params={"by": ADMIN})
    assert client.get("/api/certificates/verify", params={"code": code}).json()["status"] == "revoked"
    assert client.get("/api/certificates/verify", params={"code": "PL-NOPE-1"}).json()["status"] == "unknown"


def test_disposition_needs_dual_control_and_anonymizes_answers(client):
    """Retention execution: two different approvers, raw answers go, scores stay."""
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    right = {question["id"]: question["correct_index"] for question in quiz["questions"]}
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/baseline", json={"answers": right})
    learning.create_role(ADMIN, "Instructor", "Field trainers", ["course.publish"])
    learning.assign_role(ADMIN, REVIEWER, "instructor")
    proposed = client.post(f"/api/runs/{RUN_ID}/retention/dispose", json={
        "by_user_id": ADMIN, "action": "anonymize-assessments"}).json()
    assert proposed["status"] == "proposed"
    refused = client.post(f"/api/runs/{RUN_ID}/retention/dispose/{proposed['id']}/approve",
                          json={"by_user_id": ADMIN})
    assert refused.status_code == 400
    done = client.post(f"/api/runs/{RUN_ID}/retention/dispose/{proposed['id']}/approve",
                       json={"by_user_id": REVIEWER}).json()
    assert done["status"] == "executed" and done["affected"] >= 1
    attempts = learning.progress(RUN_ID, LEARNER)["attempts"]
    assert attempts and all(attempt.get("answers") == {} for attempt in attempts)
    assert all("score" in attempt for attempt in attempts)


def test_reminders_spanish_locale(client):
    """Human-reviewed templates: Spanish nudges, never a raw key."""
    _publish(client, assignees=[LEARNER, "lucy-whitfield"])
    queue = client.get(f"/api/runs/{RUN_ID}/reminders", params={"locale": "es"}).json()
    assert queue["locale"] == "es"
    assert any("Recordatorio" in entry["message"] for entry in queue["reminders"])


def test_nearby_rank_is_opt_in_and_anonymized(client):
    """Peer ranks need consent; neighbors render as ranks, never names."""
    _publish(client, assignees=[LEARNER, "lucy-whitfield"])
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    right = {question["id"]: question["correct_index"] for question in quiz["questions"]}
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": right})
    assert client.get("/api/leaderboard/nearby", params={
        "by_user_id": LEARNER, "user_id": LEARNER}).status_code == 400
    client.post(f"/api/people/{LEARNER}/board-opt-in", json={"by_user_id": LEARNER, "opt_in": True})
    client.post("/api/people/lucy-whitfield/board-opt-in",
                json={"by_user_id": ADMIN, "opt_in": True})
    board = client.get("/api/leaderboard/nearby", params={
        "by_user_id": LEARNER, "user_id": LEARNER}).json()
    assert board["rank"] == 1 and board["of"] == 2
    others = [entry for entry in board["neighbors"] if not entry["you"]]
    assert others and all(entry["name"] is None for entry in others)


def test_recertification_nudges_stale_certificates(client):
    """A new published version re-queues certified learners as recertification."""
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    right = {question["id"]: question["correct_index"] for question in quiz["questions"]}
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/baseline", json={"answers": right})
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": right})
    comment = client.post(f"/api/runs/{RUN_ID}/review/comments", json={
        "user_id": REVIEWER, "target": "faq", "severity": "major", "body": "Update the FAQ."}).json()
    client.patch(f"/api/runs/{RUN_ID}/review/comments/{comment['id']}", json={
        "user_id": ADMIN, "status": "addressed", "resolution": "Updated."})
    client.post(f"/api/runs/{RUN_ID}/review/versions", json={"user_id": ADMIN, "summary": "FAQ refresh"})
    client.post(f"/api/runs/{RUN_ID}/review/signoff", json={"user_id": REVIEWER, "decision": "approved"})
    republished = client.post(f"/api/runs/{RUN_ID}/publication", json={
        "user_id": ADMIN, "starts_on": "2026-09-01", "due_on": "2026-12-31",
        "assignees": [LEARNER], "message": "Recertify on v3."})
    assert republished.status_code == 200
    queue = client.get(f"/api/runs/{RUN_ID}/reminders").json()
    recert = [entry for entry in queue["reminders"] if entry["kind"] == "recertification"]
    assert len(recert) == 1 and recert[0]["user_id"] == LEARNER


def test_skills_mastery_tracks_general_skill_and_schedules_review(client):
    """BKT-lite: observations move mastery; every skill gets a next review."""
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    half = {question["id"]: question["correct_index"] if index < 2
            else (question["correct_index"] + 1) % 4
            for index, question in enumerate(quiz["questions"])}
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/baseline", json={"answers": half})
    body = client.get(f"/api/learn/{LEARNER}/{RUN_ID}/skills").json()
    general = body["skills"]["general"]
    assert 0 < general["mastery"] < 1
    assert general["observations"] == len(quiz["questions"])
    assert general["next_review"]["due_in_days"] >= 0


def test_at_risk_flags_stalled_learners_with_reasons(client):
    """Transparent triage: score plus the reasons, no black box."""
    _publish(client, assignees=[LEARNER, "lucy-whitfield"])
    report = client.get(f"/api/runs/{RUN_ID}/at-risk").json()
    flagged = {entry["user_id"]: entry for entry in report["at_risk"]}
    assert "lucy-whitfield" in flagged
    assert flagged["lucy-whitfield"]["reasons"]
    assert flagged["lucy-whitfield"]["tier"] in ("watch", "high")


def test_skills_gap_groups_misses_by_skill(client):
    """Untagged questions count as general; the shape is what tagging fills."""
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    half = {question["id"]: question["correct_index"] if index < 2
            else (question["correct_index"] + 1) % 4
            for index, question in enumerate(quiz["questions"])}
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": half})
    body = client.get(f"/api/runs/{RUN_ID}/skills-gap").json()
    assert body["skills"] and body["skills"][0]["skill"] == "general"
    assert body["skills"][0]["percent"] == 50


def test_reinforce_serves_most_due_first(client):
    """FSRS ordering: the least retrievable missed question comes first."""
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    half = {question["id"]: question["correct_index"] if index < 2
            else (question["correct_index"] + 1) % 4
            for index, question in enumerate(quiz["questions"])}
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": half})
    practice = client.get(f"/api/learn/{LEARNER}/{RUN_ID}/reinforce").json()
    assert practice["missed_count"] >= 1
    assert all("due_in_days" in question and "retrievability" in question
               for question in practice["questions"])


def test_certificate_templates_are_listed(client):
    templates = client.get("/api/certificate-templates").json()
    assert [template["id"] for template in templates] == ["classic", "modern", "formal"]
    assert all(template["label"] and template["description"] for template in templates)


def _publish_with_template(client, template):
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
        "assignees": [LEARNER],
        "message": "Please complete before the cycle meeting.",
        "certificate_template": template,
    })


def test_publish_rejects_an_unknown_certificate_design(client):
    response = _publish_with_template(client, "fancy")
    assert response.status_code == 400
    assert "Certificate design" in response.json()["detail"]


def test_certificate_carries_the_template_chosen_at_publish(client):
    publication = _publish_with_template(client, "formal")
    assert publication.status_code == 200
    assert publication.json()["publication"]["certificate_template"] == "formal"

    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    right = {question["id"]: question["correct_index"] for question in quiz["questions"]}
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": right})
    certificate = client.get(f"/api/learn/{LEARNER}/{RUN_ID}/certificate").json()
    assert certificate["template"] == "formal"


def test_badges_and_streak_are_derived_from_progress():
    """Recognition is computed, never stored: a badge cannot outlive the work."""
    from datetime import date, timedelta
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    record = {
        "run_id": RUN_ID, "user_id": LEARNER, "started_at": f"{yesterday}T09:00:00+00:00",
        "modules": {module["id"]: {"completed": True, "completed_at": f"{today}T09:00:00+00:00"}
                    for module in learning.MODULES[:2]},
        "attempts": [{"kind": "baseline", "score": 60, "passed": False,
                      "created_at": f"{yesterday}T11:00:00+00:00"}],
        "certificate": None, "feedback": [],
    }
    summary = learning.summarize(record)
    earned = {badge["id"] for badge in summary["badges"] if badge["earned"]}
    assert earned == {"first-steps", "baseline-complete", "halfway"}
    assert summary["streak_days"] == 2
    assert {badge["id"] for badge in summary["badges"]} == {badge_id for badge_id, _ in learning.BADGES}

    idle = dict(record, started_at=None, modules={}, attempts=[])
    assert learning.summarize(idle)["streak_days"] == 0
    assert all(not badge["earned"] for badge in learning.summarize(idle)["badges"])


def test_content_expiry_is_derived_from_the_publish_audit():
    from datetime import date
    assert learning._content_status(None)["content_state"] == "unpublished"
    fresh = learning._content_status({"published_at": f"{date.today().isoformat()}T09:00:00+00:00"})
    assert fresh["content_state"] == "current" and fresh["content_valid_until"]
    stale = learning._content_status({"published_at": "2020-01-01T09:00:00+00:00"})
    assert stale["content_state"] == "overdue"


def test_objections_are_admin_authored_and_learner_visible(client):
    _publish(client)
    refused = client.post(f"/api/runs/{RUN_ID}/objections", json={
        "user_id": LEARNER, "question": "Why not ribociclib?", "answer": "Formulary.",
    })
    assert refused.status_code == 400

    created = client.post(f"/api/runs/{RUN_ID}/objections", json={
        "user_id": ADMIN, "question": "Why not ribociclib?", "answer": "Formulary position per P&T.",
        "citations": [{"title": "P&T minutes", "url": "https://example.test", "locator": "Q3"}],
    })
    assert created.status_code == 201
    assert [entry["question"] for entry in client.get(f"/api/runs/{RUN_ID}/objections").json()] == [
        "Why not ribociclib?"]

    retired = client.patch(f"/api/runs/{RUN_ID}/objections/{created.json()['id']}",
                           json={"user_id": ADMIN, "retired": True})
    assert retired.status_code == 200
    assert client.get(f"/api/runs/{RUN_ID}/objections").json() == []


def test_safety_reports_are_open_to_learners_and_triaged_by_staff(client):
    _publish(client)
    unassigned = client.post(f"/api/runs/{RUN_ID}/safety",
                           json={"user_id": "tom-becker", "concern": "Rash in clinic"})
    assert unassigned.status_code == 201
    stranger = client.post(f"/api/runs/{RUN_ID}/safety",
                           json={"user_id": "nobody", "concern": "Rash in clinic"})
    assert stranger.status_code == 400

    reported = client.post(f"/api/runs/{RUN_ID}/safety",
                           json={"user_id": LEARNER, "concern": "Grade 3 neutropenia in clinic"})
    assert reported.status_code == 201
    assert reported.json()["status"] == "new"

    assert client.get(f"/api/runs/{RUN_ID}/safety", params={"user_id": LEARNER}).status_code == 400
    listed = client.get(f"/api/runs/{RUN_ID}/safety", params={"user_id": ADMIN}).json()
    assert [entry["reporter_id"] for entry in listed] == ["tom-becker", LEARNER]
    assert {entry["status"] for entry in listed} == {"new"}

    triaged = client.patch(f"/api/runs/{RUN_ID}/safety/{reported.json()['id']}",
                           json={"user_id": ADMIN}).json()
    assert triaged["status"] == "reviewed"
    assert triaged["reviewed_by"] == "Priya Raman"


def test_certificate_defaults_to_classic_without_a_template_choice(client):
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    right = {question["id"]: question["correct_index"] for question in quiz["questions"]}
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": right})
    assert client.get(f"/api/learn/{LEARNER}/{RUN_ID}/certificate").json()["template"] == "classic"


def test_learner_audit_records_start_and_completion(client):
    """A13: when did the learner start, and when did they complete."""
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    right = {question["id"]: question["correct_index"] for question in quiz["questions"]}
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/baseline", json={"answers": right})
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": right})
    audit = client.get(f"/api/runs/{RUN_ID}/audit/{LEARNER}").json()
    assert audit["run_id"] == RUN_ID
    assert audit["started_at"]
    assert audit["completed_at"]
    kinds = [entry["event"] for entry in audit["events"]]
    assert "training.started" in kinds
    assert "assessment.baseline" in kinds
    assert "training.completed" in kinds
    assert [entry["at"] for entry in audit["events"]] == sorted(entry["at"] for entry in audit["events"])


def test_reminders_queue_flags_incomplete_learners(client):
    """A5/A18: who still owes training, with a sendable message per learner."""
    _publish(client, assignees=[LEARNER, "lucy-whitfield"])
    queue = client.get(f"/api/runs/{RUN_ID}/reminders").json()
    assert queue["due_on"] == "2026-09-30"
    pending = [entry for entry in queue["reminders"] if entry["user_id"] == "lucy-whitfield"]
    assert pending
    assert pending[0]["message"]
    assert pending[0]["state"] in ("due", "overdue")


def test_points_follow_uplift_and_mastery_badges_are_earned(client):
    """Points reward learning, not just completion; mastery badges mark growth."""
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    wrong = {question["id"]: (question["correct_index"] + 1) % 4 for question in quiz["questions"]}
    right = {question["id"]: question["correct_index"] for question in quiz["questions"]}
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/baseline", json={"answers": wrong})
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    result = client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": right}).json()
    assert result["summary"]["uplift"] == 100
    assert result["summary"]["points"] == 4 * 25 + 100 + 100
    earned = {badge["id"] for badge in result["summary"]["badges"] if badge["earned"]}
    assert {"growth", "first-try", "certified"} <= earned


def test_streak_forgives_a_single_missed_day():
    """One gap day keeps the streak; two gaps break it."""
    from datetime import date, timedelta
    today = date.today()
    iso = lambda delta: (today - timedelta(days=delta)).isoformat() + "T09:00:00+00:00"
    record = {"run_id": RUN_ID, "user_id": LEARNER, "started_at": iso(3),
              "modules": {"deck": {"completed_at": iso(0)}, "videos": {"completed_at": iso(2)}},
              "attempts": [], "certificate": None, "feedback": []}
    assert learning._streak_days(record) == 2
    record["modules"] = {"deck": {"completed_at": iso(0)}, "videos": {"completed_at": iso(3)}}
    assert learning._streak_days(record) == 1


def test_reminders_carry_an_implementation_intention_prompt(client):
    """Nudges ask for a when-and-where plan, not just attention."""
    _publish(client, assignees=[LEARNER, "lucy-whitfield"])
    queue = client.get(f"/api/runs/{RUN_ID}/reminders").json()
    pending = [entry for entry in queue["reminders"] if entry["user_id"] == "lucy-whitfield"]
    assert pending
    assert "Plan now" in pending[0]["message"]


def test_faithfulness_endpoint_reports_per_track_numbers(client):
    """Wiring: one regression number per track plus the per-asset split."""
    body = client.get(f"/api/runs/{RUN_ID}/faithfulness").json()
    assert set(body["tracks"]) == {"hcp", "msl"}
    for report in body["tracks"].values():
        assert {"faithfulness", "cited_sentences", "supported_sentences", "assets"} <= set(report)
    single = client.get(f"/api/runs/{RUN_ID}/faithfulness", params={"track": "hcp"}).json()
    assert set(single["tracks"]) == {"hcp"}


def test_roster_import_upserts_by_email(client):
    """A1: bulk import toward AD — new people added, known emails updated."""
    csv_text = "name,email,role,title\nAsha Verma,asha.verma@pharmalearn.local,hcp,Oncologist\nDr. Ken Osei,ken.osei@pharmalearn.local,msl,MSL updated"
    result = client.post("/api/people/import", json={"by_user_id": ADMIN, "csv": csv_text}).json()
    assert result["added"] == 1
    assert result["updated"] == 1
    assert result["errors"] == []
    people = {entry["id"]: entry for entry in client.get("/api/people").json()}
    assert any(entry["email"] == "asha.verma@pharmalearn.local" for entry in people.values())

    refused = client.post("/api/people/import", json={"by_user_id": LEARNER, "csv": csv_text})
    assert refused.status_code == 400


def test_leaderboard_is_admin_only_and_ranks_by_points(client):
    """A8: points leaderboard, admin eyes only — no peer exposure."""
    _publish(client)
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    right = {question["id"]: question["correct_index"] for question in quiz["questions"]}
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": right})

    board = client.get("/api/leaderboard", params={"by_user_id": ADMIN}).json()
    assert board["entries"]
    assert board["entries"] == sorted(board["entries"], key=lambda entry: entry["points"], reverse=True)
    assert LEARNER in {entry["user_id"] for entry in board["entries"]}

    refused = client.get("/api/leaderboard", params={"by_user_id": LEARNER})
    assert refused.status_code == 400


def test_private_profile_hides_learner_from_peer_boards(client):
    """Hiding completions removes the learner from every peer-visible board,
    while the admin totals keep them for compliance."""
    _publish(client, assignees=[LEARNER, "lucy-whitfield"])
    for user in (LEARNER, "lucy-whitfield"):
        client.post(f"/api/people/{user}/board-opt-in",
                    json={"by_user_id": user, "opt_in": True})
    private = client.post(f"/api/people/{LEARNER}/privacy",
                          json={"by_user_id": LEARNER, "private": True})
    assert private.status_code == 201
    board = client.get("/api/leaderboard/nearby", params={
        "by_user_id": "lucy-whitfield", "user_id": "lucy-whitfield"}).json()
    assert board["of"] == 1
    assert len(board["neighbors"]) == 1 and board["neighbors"][0]["you"]
    assert LEARNER in {entry["user_id"] for entry in
                       client.get("/api/leaderboard", params={"by_user_id": ADMIN}).json()["entries"]}
    mine = client.get("/api/leaderboard/nearby", params={
        "by_user_id": LEARNER, "user_id": LEARNER})
    assert mine.status_code == 400


def test_private_profile_blocks_opt_in(client):
    """Opting into a peer board while private is a contradiction; the server
    refuses instead of silently showing the learner."""
    client.post(f"/api/people/{LEARNER}/privacy",
                json={"by_user_id": LEARNER, "private": True})
    refused = client.post(f"/api/people/{LEARNER}/board-opt-in",
                          json={"by_user_id": LEARNER, "opt_in": True})
    assert refused.status_code == 400
    visible = client.post(f"/api/people/{LEARNER}/privacy",
                          json={"by_user_id": LEARNER, "private": False})
    assert visible.status_code == 201
    assert client.post(f"/api/people/{LEARNER}/board-opt-in",
                       json={"by_user_id": LEARNER, "opt_in": True}).status_code == 200


def test_team_board_stays_inside_the_team_and_anonymized(client):
    """A team board ranks opted-in, non-private teammates only; outsiders and
    private teammates never appear, and neighbors carry no names."""
    _publish(client, assignees=[LEARNER, "lucy-whitfield", "tom-becker"])
    quiz = json.loads((agent.DATA / "content" / RUN_ID / "assets" / "quiz.json").read_text())
    right = {question["id"]: question["correct_index"] for question in quiz["questions"]}
    for module in learning.MODULES:
        client.post(f"/api/learn/{LEARNER}/{RUN_ID}/modules", json={"module_id": module["id"], "completed": True})
    client.post(f"/api/learn/{LEARNER}/{RUN_ID}/assessment/final", json={"answers": right})
    for user in (LEARNER, "lucy-whitfield", "tom-becker"):
        assert client.post(f"/api/people/{user}/team",
                           json={"by_user_id": ADMIN, "team": "Oncology West"}).status_code == 201
        client.post(f"/api/people/{user}/board-opt-in",
                    json={"by_user_id": user, "opt_in": True})
    client.post("/api/people/tom-becker/privacy",
                json={"by_user_id": "tom-becker", "private": True})
    board = client.get("/api/leaderboard/team", params={
        "by_user_id": LEARNER, "user_id": LEARNER, "team": "Oncology West"}).json()
    assert board["team"] == "Oncology West"
    assert board["of"] == 2
    others = [entry for entry in board["neighbors"] if not entry["you"]]
    assert others and all(entry["name"] is None for entry in others)
    assert board["rank"] == 1
    outsider = client.get("/api/leaderboard/team", params={
        "by_user_id": LEARNER, "user_id": LEARNER, "team": "Cardiology"})
    assert outsider.status_code == 400

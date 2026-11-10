"""Research round 3 (items 6-15): analytics, grading, and verifier builders.

Each test seeds only the state its function reads, following the
test_retention.py convention of writing course/progress records directly.
"""
import json
from datetime import UTC, datetime, timedelta

from src import agent, analytics, assistant, learning
from src import judge

RUN_ID = "ibrance-round3"

QUIZ = {
    "passing_score": 75,
    "questions": [
        {"id": "q1", "prompt": "First-line therapy?", "options": ["A", "B"],
         "correct_index": 0, "rationale": "Guideline states A first.",
         "citations": [{"title": "Label", "url": "https://x", "locator": "Sec 1"}]},
        {"id": "q2", "prompt": "Dose?", "options": ["A", "B"],
         "correct_index": 1, "rationale": "",
         "citations": []},
        {"id": "q3", "prompt": "Monitoring?", "options": ["A", "B"],
         "correct_index": 0, "rationale": "Monitor counts.",
         "citations": [{"title": "Label", "url": "https://x", "locator": "Sec 2"}]},
        {"id": "q4", "prompt": "Interaction?", "options": ["A", "B"],
         "correct_index": 1, "rationale": "CYP3A interaction.",
         "citations": [{"title": "Label", "url": "https://x", "locator": "Sec 3"}]},
    ],
}


def _seed(tmp_path, monkeypatch, run_id=RUN_ID):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    base = tmp_path / "content" / run_id / "hcp"
    base.mkdir(parents=True)
    (base / "quiz.json").write_text(json.dumps(QUIZ))
    record = learning.course(run_id)
    record["version"] = 1
    record.update(status="published", publication={
        "version": 1, "published_at": "2026-01-02T00:00:00+00:00",
        "published_by": "Priya Raman", "overrides": [],
        "starts_on": "2026-01-01", "due_on": "2026-12-31",
        "frequency": "once", "next_due_on": None, "message": "",
        "assignees": ["ken-osei"],
        "notifications": []})
    learning._save_course(record)
    return run_id


def _attempt(kind, score, correct, total, answers, created_at):
    return {"id": kind, "kind": kind, "score": score, "correct": correct,
            "total": total, "passing_score": 75,
            "passed": True if kind == "baseline" else score >= 75,
            "answers": answers, "created_at": created_at}


def test_adjudication_degrades_to_human_without_a_key(monkeypatch):
    """No key, no guessing: margin cases route to a human, never to a pass."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = learning.adjudicate_free_text("monitor blood counts", "check counts")
    assert result == {"model": "off", "verdict": None, "routed": "human"}


def test_grade_free_text_exact_match_passes_no_review():
    result = learning.grade_free_text("neutropenia monitor counts", "neutropenia monitor counts")
    assert result["score"] == 1.0
    assert result["passed"] is True
    assert result["needs_review"] is False


def test_grade_free_text_empty_answer_routes_to_review_never_fails():
    result = learning.grade_free_text("neutropenia monitor counts", "")
    assert result["score"] == 0.0
    assert result["passed"] is False
    assert result["needs_review"] is True
    assert result["never_auto_fail"] is True


def test_grade_free_text_partial_credit_below_review_line():
    result = learning.grade_free_text(
        "palbociclib with letrozole first line", "palbociclib letrozole")
    assert 0.0 < result["score"] < 1.0
    assert result["needs_review"] is True


def test_next_review_due_mastery_stretches_half_life():
    strong = analytics.next_review_due(90, 0)
    weak = analytics.next_review_due(60, 0)
    assert strong["half_life_days"] > weak["half_life_days"]
    assert strong["due_in_days"] > weak["due_in_days"]
    overdue = analytics.next_review_due(60, 365)
    assert overdue["overdue"] is True
    assert overdue["due_in_days"] == 0


def test_peer_turns_follow_prompt_evaluate_expand_repeat():
    turns = assistant.peer_turns("CDK4/6 inhibition delays progression.", topic="Ibrance")
    assert [turn["phase"] for turn in turns] == ["prompt", "evaluate", "expand", "repeat"]
    assert all(turn["question"] for turn in turns)


def test_verify_with_rationales_abstains_without_dossier(tmp_path, monkeypatch):
    run_id = _seed(tmp_path, monkeypatch)
    result = assistant.verify_with_rationales(run_id, "overall survival benefit")
    assert result["verdict"] == "NotEnoughInfo"
    assert result["rationales"] == []
    assert result["refutes_from_overlap"] is False


def test_verify_with_rationales_supports_cited_claim(tmp_path, monkeypatch):
    run_id = _seed(tmp_path, monkeypatch)
    dossier = tmp_path / "content" / run_id / "master" / "dossier.json"
    dossier.parent.mkdir(parents=True, exist_ok=True)
    dossier.write_text(json.dumps({"sections": [{
        "id": "s1", "title": "Efficacy",
        "claims": [{"text": "palbociclib delays disease progression in trials",
                    "evidence_type": "trial",
                    "citations": [{"title": "Label", "url": "https://x",
                                   "locator": "Sec 1"}]}]}]}))
    result = assistant.verify_with_rationales(run_id, "does palbociclib delay disease progression")
    assert result["verdict"] == "Supported"
    assert result["rationales"] and result["rationales"][0]["citations"]


def test_evidence_accuracy_withheld_without_report(tmp_path, monkeypatch):
    run_id = _seed(tmp_path, monkeypatch)
    report = analytics.evidence_conditioned_accuracy(run_id)
    assert report["measured"] is False
    assert report["withheld"] is True
    assert report["accuracy_percent"] is None


def test_evidence_accuracy_reports_conditioned_rate(tmp_path, monkeypatch):
    run_id = _seed(tmp_path, monkeypatch)
    monkeypatch.setattr(judge, "stored_report", lambda rid: {
        "stats": {"units": 10, "citations": 8, "checkable": 6,
                  "verified": 5, "coverage_percent": 75},
        "findings": [{"check": "quote_not_found"}, {"check": "uncited"}]})
    report = analytics.evidence_conditioned_accuracy(run_id)
    assert report["measured"] is True
    assert report["accuracy_percent"] == 83
    assert report["findings_by_check"] == {"quote_not_found": 1, "uncited": 1}


def test_mastery_curve_is_leakage_free(tmp_path, monkeypatch):
    run_id = _seed(tmp_path, monkeypatch)
    state = learning.progress(run_id, "ken-osei")
    state["started_at"] = "2026-01-03T00:00:00+00:00"
    state["attempts"] = [
        _attempt("final", 60, 3, 4, {"q1": 0, "q2": 0, "q3": 0, "q4": 0},
                 "2026-02-01T00:00:00+00:00"),
        _attempt("final", 100, 4, 4, {"q1": 0, "q2": 1, "q3": 0, "q4": 1},
                 "2026-03-01T00:00:00+00:00"),
    ]
    learning._save_progress(state)
    curve = analytics.mastery_over_time(run_id)
    assert [row["date"] for row in curve] == ["2026-02-01", "2026-03-01"]
    assert curve[0]["avg_final"] == 60
    assert curve[1]["avg_final"] == 80


def test_delayed_retention_withholds_early_finals(tmp_path, monkeypatch):
    run_id = _seed(tmp_path, monkeypatch)
    state = learning.progress(run_id, "ken-osei")
    state["started_at"] = "2026-01-03T00:00:00+00:00"
    state["attempts"] = [
        _attempt("baseline", 50, 2, 4, {}, "2026-01-03T00:00:00+00:00"),
        _attempt("final", 100, 4, 4, {"q1": 0, "q2": 1, "q3": 0, "q4": 1},
                 "2026-01-10T00:00:00+00:00"),
    ]
    learning._save_progress(state)
    report = analytics.delayed_retention(run_id, delay_days=30)
    assert report["measured"] == 0
    assert report["not_yet_measurable"] == 1
    assert report["retained_uplift"] is None


def test_delayed_retention_measures_after_delay(tmp_path, monkeypatch):
    run_id = _seed(tmp_path, monkeypatch)
    state = learning.progress(run_id, "ken-osei")
    state["started_at"] = "2026-01-03T00:00:00+00:00"
    state["attempts"] = [
        _attempt("baseline", 50, 2, 4, {}, "2026-01-03T00:00:00+00:00"),
        _attempt("final", 75, 3, 4, {"q1": 0, "q2": 1, "q3": 1, "q4": 1},
                 "2026-03-15T00:00:00+00:00"),
    ]
    learning._save_progress(state)
    report = analytics.delayed_retention(run_id, delay_days=30)
    assert report["measured"] == 1
    assert report["retained_uplift"] == 25


def test_course_rag_red_when_overdue(tmp_path, monkeypatch):
    run_id = _seed(tmp_path, monkeypatch)
    record = learning.course(run_id)
    record["publication"]["due_on"] = (
        datetime.now(UTC).date() - timedelta(days=20)).isoformat()
    learning._save_course(record)
    state = learning.progress(run_id, "ken-osei")
    state["started_at"] = "2026-01-03T00:00:00+00:00"
    learning._save_progress(state)
    rag = analytics.course_rag(run_id)
    assert rag["rag"] == "red"
    assert rag["red_learners"] == ["ken-osei"]


def test_course_rag_green_when_all_complete(tmp_path, monkeypatch):
    run_id = _seed(tmp_path, monkeypatch)
    state = learning.progress(run_id, "ken-osei")
    state["started_at"] = "2026-01-03T00:00:00+00:00"
    state["modules"] = {module["id"]: {"completed_at": "2026-02-01T00:00:00+00:00"}
                        for module in learning.MODULES}
    state["attempts"] = [
        _attempt("baseline", 50, 2, 4, {}, "2026-01-03T00:00:00+00:00"),
        _attempt("final", 100, 4, 4, {"q1": 0, "q2": 1, "q3": 0, "q4": 1},
                 "2026-02-01T00:00:00+00:00"),
    ]
    state["certificate"] = {"id": "c1", "issued_at": "2026-02-01T00:00:00+00:00",
                            "expires_at": "2030-02-01T00:00:00+00:00"}
    learning._save_progress(state)
    rag = analytics.course_rag(run_id)
    assert rag["rag"] == "green"


def test_interaction_gaps_labels_heuristic(tmp_path, monkeypatch):
    run_id = _seed(tmp_path, monkeypatch)
    state = learning.progress(run_id, "ken-osei")
    state["started_at"] = "2026-01-03T00:00:00+00:00"
    state["attempts"] = [
        _attempt("final", 50, 2, 4, {"q1": 0, "q2": 0, "q3": 1, "q4": 0},
                 "2026-02-01T00:00:00+00:00"),
    ]
    state["feedback"] = [{"id": "f1", "module_id": "deck", "rating": 2,
                          "comment": "Too dense.", "created_at": "2026-02-02T00:00:00+00:00"}]
    learning._save_progress(state)
    gaps = analytics.interaction_gaps(run_id)
    assert gaps["causal"] is False
    assert gaps["hardest_questions"]
    assert gaps["lowest_modules"]
    assert gaps["feedback_notes"][0]["comment"] == "Too dense."


def test_ask_depth_reports_rationale_and_hardest(tmp_path, monkeypatch):
    run_id = _seed(tmp_path, monkeypatch)
    state = learning.progress(run_id, "ken-osei")
    state["started_at"] = "2026-01-03T00:00:00+00:00"
    state["attempts"] = [
        _attempt("final", 50, 2, 4, {"q1": 0, "q2": 0, "q3": 1, "q4": 0},
                 "2026-02-01T00:00:00+00:00"),
    ]
    learning._save_progress(state)
    depth = analytics.ask_depth(run_id)
    assert depth["questions"] == 4
    assert depth["rationale_percent"] == 75
    assert depth["cited_percent"] == 75
    assert depth["hardest_attempts"] == 1

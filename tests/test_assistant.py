"""Page-contextual Ask starters, and the record/dossier routing behind them.

Two things are worth protecting here. A suggested question must be one the
assistant can actually answer — a starter that leads nowhere is the demo failing
in the exact place we claim to be well grounded. And the line between "ask the
record" and "ask the dossier" has to hold in both directions: a schedule question
must not be answered from prose, and a trial question must not be answered with
training dates.
"""

import json

import pytest

from src import agent, assistant, learning

DOSSIER = {
    "drug": {"brand": "Ibrance", "generic": "Palbociclib", "area": "Oncology"},
    "title": "Ibrance",
    "sections": [
        {"id": "13_unmet_needs", "title": "Documented unmet needs", "claims": [
            {"text": "Resistance to CDK4/6 inhibition remains a documented unmet need after progression.",
             "evidence_type": "review",
             "citations": [{"title": "Review", "url": "https://pubmed.ncbi.nlm.nih.gov/1", "locator": "Discussion"}]},
        ]},
        {"id": "03_clinical_evidence", "title": "Clinical evidence", "claims": [
            {"text": "In the phase 3 PALOMA-2 trial median progression-free survival was 24.8 months.",
             "evidence_type": "trial",
             "citations": [{"title": "PALOMA-2", "url": "https://pubmed.ncbi.nlm.nih.gov/2", "locator": "Results"}]},
        ]},
    ],
}


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    base = tmp_path / "content" / "run"
    base.mkdir(parents=True)
    (base / "context.json").write_text(json.dumps(DOSSIER))
    return "run"


def _publish(run_id):
    comment = learning.add_comment(run_id, "anil-shekhar", "deck", "minor", "Tighten slide 3.")
    learning.resolve_comment(run_id, comment["id"], "addressed", "Done.", "priya-raman")
    learning.publish_version(run_id, "priya-raman", "Slide 3 tightened")
    learning.add_signoff(run_id, "anil-shekhar", "approved")
    learning.publish_course(run_id, "priya-raman", "2026-09-01", "2026-09-30", ["ken-osei", "tom-becker"])


# Questions a reader would expect the *record* to settle, paired with the words
# that must appear in the answer for it to be worth anything.
RECORD_QUESTIONS = [
    ("When does this training programme open and close?", "2026-09-01"),
    ("How many trainees are assigned, and how many are certified?", "2 trainee(s) assigned"),
    ("Who approved this version, and were there any overrides?", "Dr. Anil Shekhar"),
    ("What is still blocking publication?", "blocking"),
]

# Questions about the drug. Several deliberately contain words a naive schedule
# or approval matcher would grab — "start", "approved", "who".
DOSSIER_QUESTIONS = [
    "What is the approved indication?",
    "What did the phase 3 trials show?",
    "When did PALOMA-2 start?",
    "Which sources support the approved indication?",
    "What are the unmet needs in this disease?",
]


@pytest.mark.parametrize("question,expected", RECORD_QUESTIONS)
def test_the_record_answers_questions_about_the_programme(run, question, expected):
    _publish(run)
    reply = assistant.platform_answer(run, question)

    assert reply is not None, f"no record answer for {question!r}"
    assert reply["mode"] == "record"
    assert expected in reply["answer"]
    # No model, no retrieval: these are facts, so they are read, not inferred.
    assert reply["citations"] == []


@pytest.mark.parametrize("question", DOSSIER_QUESTIONS)
def test_questions_about_the_drug_are_not_hijacked_by_the_record(run, question):
    """"When did PALOMA-2 start" must not be answered with the training dates."""
    _publish(run)
    assert assistant.platform_answer(run, question) is None


@pytest.mark.parametrize("days,expected", [
    (0, " (today)"), (1, " (1 day from now)"), (12, " (12 days from now)"),
    (-1, " (1 day ago)"), (-9, " (9 days ago)"), (None, ""),
])
def test_a_past_deadline_does_not_read_as_minus_one_day_ago(days, expected):
    """The word carries the direction, so the sign must not be printed as well."""
    assert assistant._day_phrase(days) == expected


def test_a_trainee_is_told_their_own_standing_not_the_cohorts(run, monkeypatch):
    """A closed window is "completed" for the programme and overdue for the person
    who never finished it. Telling a trainee the wrong one contradicts the card
    they just clicked through from."""
    _publish(run)
    record = learning.course(run)
    record["publication"].update({"starts_on": "2026-06-01", "due_on": "2026-07-01"})
    learning._save_course(record)

    theirs = assistant.platform_answer(run, "When is this training due?", "ken-osei")
    cohort = assistant.platform_answer(run, "When is this training due?")

    assert "For you it is overdue" in theirs["answer"]
    assert "ago" in theirs["answer"]
    assert "For you" not in cohort["answer"]


def test_a_stranger_asking_gets_the_cohort_answer(run):
    """user_id only personalises the reply for someone actually assigned."""
    _publish(run)
    reply = assistant.platform_answer(run, "When is this training due?", "priya-raman")
    assert "For you" not in reply["answer"]


def test_an_unpublished_course_says_so_rather_than_inventing_a_date(run):
    reply = assistant.platform_answer(run, "When does this training programme open?")
    assert reply is not None
    assert "not been published" in reply["answer"]


def test_every_starter_offered_is_one_the_assistant_can_answer(run):
    """The guarantee the whole feature rests on."""
    _publish(run)
    for context in assistant.CONTEXTS:
        for starter in assistant.starters(run, context):
            if starter["kind"] == "record":
                assert assistant.platform_answer(run, starter["question"]), starter["question"]
            else:
                assert assistant.search(run, starter["question"], limit=1), starter["question"]


def test_starters_differ_by_context(run):
    _publish(run)
    material = {entry["question"] for entry in assistant.starters(run, "material")}
    programme = {entry["question"] for entry in assistant.starters(run, "programme")}

    assert material and programme
    assert material != programme


def test_a_thin_dossier_drops_the_starters_it_cannot_support(run):
    """On another drug half these questions have no evidence. Better to show fewer."""
    offered = {entry["question"] for entry in assistant.starters(run, "material")}
    candidates = {question for _kind, question in assistant.CONTEXTS["material"]}

    assert offered < candidates
    assert "What are the unmet needs in this disease?" in offered
    assert "How is neutropenia monitored and managed?" not in offered


def test_an_unknown_context_falls_back_rather_than_returning_nothing(run):
    assert assistant.starters(run, "nonsense") == assistant.starters(run, assistant.DEFAULT_CONTEXT)


def _untraceable_evidence():
    return {
        "comment_id": "c1", "finding_id": "hcp:q1:untraceable", "check": "untraceable",
        "severity": "blocking", "reference": "Question q1",
        "message": "does not match any claim collected during research",
        "claim": "PFS was 24.8 months.", "quote": "", "spans": [], "match_percent": None,
        "passage": "", "source": None,
        "citations": [{"title": "Trial paper", "url": "https://example.com/paper",
                       "locator": "Results", "traceable": False, "held": False, "claim": ""}],
        "unheld": ["https://example.com/paper"], "coverage": {"held": 0, "total": 1},
    }


def test_about_finding_answers_from_the_finding_not_the_dossier(monkeypatch):
    """"Does it support the wording?" must be answered from the check state.

    The old box forwarded free text into dossier keyword search, which cannot
    speak about a finding — especially an untraceable one with no recorded
    evidence at all. The finding id routes to the evidence the panel shows.
    """
    import asyncio
    from src import judge
    monkeypatch.setattr(judge, "evidence_for",
                        lambda run_id, comment: _untraceable_evidence())
    reply = asyncio.run(assistant.about_finding(
        "run", "hcp:q1:untraceable", "does it support the wording?"))
    assert reply["mode"] == "finding"
    assert "No recorded evidence" in reply["answer"]
    assert "Trial paper" in reply["answer"]


def test_about_finding_unknown_id_falls_back_to_the_dossier(run, monkeypatch):
    import asyncio
    from src import judge
    monkeypatch.setattr(judge, "evidence_for", lambda run_id, comment: None)
    reply = asyncio.run(assistant.about_finding(
        "run", "nope", "What did the phase 3 trials show?"))
    assert reply["mode"] in ("retrieval", "model")
    assert "24.8" in reply["answer"]


def test_about_finding_says_how_to_approve_despite_a_block(monkeypatch):
    import asyncio
    from src import judge
    monkeypatch.setattr(judge, "evidence_for",
                        lambda run_id, comment: _untraceable_evidence())
    reply = asyncio.run(assistant.about_finding(
        "run", "hcp:q1:untraceable", "how do I approve this if it is blocked?"))
    assert "override" in reply["answer"]
    assert "sign-off" in reply["answer"]


def test_typos_read_as_the_word_they_plainly_meant(run):
    """"progresion" is not a word, but it is one letter from one — retrieval
    corrects it instead of reporting no evidence."""
    assert assistant._correct_terms(run, "What did the phase 3 trial show about progresion?") == {"progresion": "progression"}
    assert assistant.search(run, "What did the phase 3 trial show about progresion?")
    assert assistant._correct_terms(run, "What did the phase 3 trials show?") == {"trials": "trial"}


def test_what_happens_if_i_fail_is_answered_from_the_recorded_quiz(run, tmp_path, monkeypatch):
    """Procedural grading questions are record facts, not dossier claims."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    quiz_dir = tmp_path / "content" / "run" / "hcp"
    quiz_dir.mkdir(parents=True)
    (quiz_dir / "quiz.json").write_text(json.dumps({"passing_score": 75, "questions": []}))
    import asyncio
    reply = asyncio.run(assistant.answer("run", "what happens if i fail?", "hcp"))
    assert reply["mode"] == "record"
    assert "75%" in reply["answer"]
    assert "unlimited" in reply["answer"]
    assert reply["citations"] == []


def test_raw_count_pass_mark_is_shown_as_a_percentage(run, tmp_path):
    """Generators sometimes write "8 correct" instead of a percent; show 67%, not 8%."""
    quiz_dir = tmp_path / "content" / "run" / "hcp"
    quiz_dir.mkdir(parents=True)
    quiz_dir.joinpath("quiz.json").write_text(json.dumps(
        {"passing_score": 8, "questions": [{"id": f"q{i}"} for i in range(12)]}))
    rules = assistant._assessment_rules(run, "what happens if i fail?", "hcp")
    assert rules is not None
    assert "67%" in rules["answer"]
    assert "8%" not in rules["answer"]


def test_dossier_failure_questions_stay_with_the_dossier(run, tmp_path):
    """The grading intent must not hijack questions about treatment failure."""
    quiz_dir = tmp_path / "content" / "run" / "hcp"
    quiz_dir.mkdir(parents=True)
    (quiz_dir / "quiz.json").write_text(json.dumps({"passing_score": 75, "questions": []}))
    assert assistant._assessment_rules(run, "What are the treatment failure rates?", "hcp") is None
    assert assistant._assessment_rules(run, "What happens if I fail?", "hcp") is not None


def test_partial_match_names_what_is_missing():
    verdict, close = assistant._finding_state({
        "check": "quote_not_verbatim", "match_percent": 60,
        "spans": [{"text": "withhold IBRANCE", "present": True},
                  {"text": "until recovery", "present": False}],
        "citations": [], "unheld": [],
    })
    assert "60%" in verdict
    assert "until recovery" in verdict
    assert "override" in close

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

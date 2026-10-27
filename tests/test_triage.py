"""The gamified sort board.

The point of these tests is the claim the format rests on: a board is a way of
asking, not a different kind of assessment. So they check that a folded board is
indistinguishable from ordinary questions to everything downstream — the scorer,
the checker, the review queue — and that the only thing that knows about boards
is the layer that draws them.
"""

import json

import pytest

from api.main import _groups, _questions
from src import agent, judge, learning

BOARD = {
    "id": "dose-hold",
    "kind": "sort",
    "title": "Hold or continue?",
    "instruction": "Sort each finding by what the label requires at the start of a cycle.",
    "buckets": {"a": "Hold the dose", "b": "Continue at the current dose"},
    "items": [
        {"id": "t1", "prompt": "ANC 800/mm3 on day 15 of cycle 1", "correct_index": 0,
         "rationale": "Grade 3 neutropenia at day 15 requires interruption.",
         "citations": [{"title": "Label", "url": "https://dailymed.nlm.nih.gov/x", "locator": "2.2"}]},
        {"id": "t2", "prompt": "ANC 1400/mm3 before cycle 3", "correct_index": 1,
         "rationale": "At or above 1000/mm3 the dose continues unchanged.",
         "citations": [{"title": "Label", "url": "https://dailymed.nlm.nih.gov/x", "locator": "2.2"}]},
    ],
}

QUIZ = {
    "title": "Knowledge check",
    "passing_score": 75,
    "questions": [
        {"id": f"q{index}", "prompt": f"Question {index}?", "options": ["a", "b", "c", "d"],
         "correct_index": 0, "rationale": "Because.", "citations": []}
        for index in range(1, 13)
    ],
}


def _folded():
    return agent.fold_groups(json.loads(json.dumps(QUIZ)), [json.loads(json.dumps(BOARD))])


def test_board_items_become_ordinary_questions():
    """The whole design: downstream never learns that a game was played."""
    folded = _folded()
    item = folded["questions"][-2]

    assert item["id"] == "t1"
    assert item["options"] == ["Hold the dose", "Continue at the current dose"]
    assert item["correct_index"] == 0
    assert item["group"] == "dose-hold"
    # Every key an ordinary question has, so nothing downstream needs a branch.
    assert set(QUIZ["questions"][0]) <= set(item)


def test_folding_leaves_the_original_questions_alone():
    folded = _folded()
    assert folded["questions"][:12] == QUIZ["questions"]
    assert folded["title"] == QUIZ["title"]
    assert [group["buckets"] for group in folded["groups"]] == [["Hold the dose", "Continue at the current dose"]]


def test_a_board_item_is_scored_by_the_same_engine(tmp_path, monkeypatch):
    """A certificate cannot depend on which format a question was drawn in."""
    monkeypatch.setattr(agent, "DATA", tmp_path)
    questions = _folded()["questions"]
    answers = {question["id"]: question["correct_index"] for question in questions}
    answers["t1"] = 1  # the one board item they got wrong

    result = learning.record_attempt("run", "ken-osei", "baseline", answers, questions, 75)

    assert result["attempt"]["total"] == 14
    assert result["attempt"]["correct"] == 13


def test_a_colliding_item_id_is_refused():
    """Answers travel keyed by id, so a collision would score one item as another."""
    board = json.loads(json.dumps(BOARD))
    board["items"][0]["id"] = "q4"
    with pytest.raises(RuntimeError, match="collides"):
        agent.fold_groups(json.loads(json.dumps(QUIZ)), [board])


def test_the_checker_reads_board_items_like_any_other_question(tmp_path, monkeypatch):
    """An uncited board item has to be caught, or the game is a hole in the governance."""
    monkeypatch.setattr(agent, "DATA", tmp_path)
    board = json.loads(json.dumps(BOARD))
    board["items"][0]["citations"] = []
    track = tmp_path / "content" / "run" / "hcp"
    track.mkdir(parents=True)
    (track / "quiz.json").write_text(json.dumps(agent.fold_groups(json.loads(json.dumps(QUIZ)), [board])))

    units = {unit["id"]: unit for unit in judge.units("run", "hcp")}
    findings, _stats = judge.deterministic_findings("run", "hcp", "Ibrance")

    assert "quiz-t1" in units
    assert "Hold the dose" in units["quiz-t1"]["text"]
    assert any(finding.unit_id == "quiz-t1" and finding.check == "uncited" for finding in findings)
    # The cited item is not flagged, so the check is discriminating rather than
    # a rule that fires on everything the board contains.
    assert not any(finding.unit_id == "quiz-t2" and finding.check == "uncited" for finding in findings)


def _content(quiz):
    return {"learners": {"hcp": {"quiz": quiz}}}


def test_the_baseline_keeps_a_board_whole():
    """Half a board is not a shorter board; the buckets stop balancing."""
    folded = _folded()
    asked = _questions(_content(folded), "hcp", "baseline")

    board_items = [question["id"] for question in asked if question.get("group")]
    assert board_items == ["t1", "t2"]
    assert len([question for question in asked if not question.get("group")]) == 5


def test_the_baseline_measures_the_same_skills_as_the_final():
    """Uplift is a comparison. A skill tested only at the end is counted as learning."""
    folded = _folded()
    baseline = {question.get("group") for question in _questions(_content(folded), "hcp", "baseline")}
    final = {question.get("group") for question in _questions(_content(folded), "hcp", "final")}

    assert baseline == final == {None, "dose-hold"}


def test_boards_are_reported_only_when_their_items_are_asked():
    folded = _folded()
    assert [board["id"] for board in _groups(folded, folded["questions"])] == ["dose-hold"]
    assert _groups(folded, QUIZ["questions"]) == []


ASSEMBLE = {
    "id": "build-instruction",
    "kind": "assemble",
    "title": "Build the labelled instruction",
    "instruction": "Choose the phrase the label uses in each slot.",
    "items": [{
        "id": "a1",
        "prompt": "Grade 3 neutropenia on Day 1 of a cycle",
        "blanks": [
            {"id": "a1-b1", "before": "Withhold IBRANCE until recovery to ",
             "options": {"a": "Grade ≤2", "b": "Grade ≤1", "c": "baseline", "d": "Grade ≤3"},
             "correct_index": 0},
            {"id": "a1-b2", "before": ", then resume at ",
             "options": {"a": "half the dose", "b": "the next lower dose", "c": "the same dose", "d": "125 mg"},
             "correct_index": 1},
        ],
        "tail": ".",
        "rationale": "The label sets both the recovery threshold and the resumed dose.",
        "citations": [{"title": "Label", "url": "https://dailymed.nlm.nih.gov/x", "locator": "2.2"}],
    }],
}

FIGURE = {
    "id": "f1",
    "caption": "Median PFS, PALOMA-2.",
    "chart_kind": "bar",
    "x_title": "Arm", "y_title": "Median PFS", "y_suffix": " mo",
    "series": [{"name": "Median PFS", "points": [
        {"label": "Palbo + letrozole", "value": 24.8}, {"label": "Letrozole", "value": 14.5}]}],
    "prompt": "What is the absolute difference in median PFS between the arms?",
    "options": {"a": "10.3 months", "b": "24.8 months", "c": "14.5 months", "d": "5.2 months"},
    "correct_index": 0,
    "rationale": "24.8 minus 14.5 is 10.3 months.",
    "citations": [{"title": "PALOMA-2", "url": "https://pubmed.ncbi.nlm.nih.gov/1", "locator": "Results"}],
}


def test_every_format_reduces_to_the_same_scored_primitive(tmp_path, monkeypatch):
    """Three ways of asking, one way of scoring — that is the whole design."""
    monkeypatch.setattr(agent, "DATA", tmp_path)
    folded = agent.fold_groups(
        json.loads(json.dumps(QUIZ)),
        [json.loads(json.dumps(BOARD)), json.loads(json.dumps(ASSEMBLE))],
        [json.loads(json.dumps(FIGURE))],
    )
    questions = folded["questions"]
    by_id = {question["id"]: question for question in questions}

    # 12 standard + 2 sort items + 2 assemble blanks + 1 figure question.
    assert len(questions) == 17
    for question_id in ("t1", "a1-b1", "a1-b2", "f1"):
        assert set(QUIZ["questions"][0]) <= set(by_id[question_id])

    answers = {question["id"]: question["correct_index"] for question in questions}
    result = learning.record_attempt("run", "ken-osei", "final", answers, questions, 75)
    assert result["attempt"]["correct"] == 17


def test_each_assemble_blank_is_independently_scored():
    """Getting the threshold wrong must not also mark the resumed dose wrong."""
    folded = agent.fold_groups(json.loads(json.dumps(QUIZ)), [json.loads(json.dumps(ASSEMBLE))])
    blanks = [question for question in folded["questions"] if question.get("group") == "build-instruction"]

    assert [blank["id"] for blank in blanks] == ["a1-b1", "a1-b2"]
    assert [blank["correct_index"] for blank in blanks] == [0, 1]
    # The sentence shape travels with the group, not with the scored questions.
    sentence = folded["groups"][0]["items"][0]
    assert [blank["id"] for blank in sentence["blanks"]] == ["a1-b1", "a1-b2"]
    assert sentence["tail"] == "."


def test_a_figure_question_carries_its_chart_and_is_still_checkable(tmp_path, monkeypatch):
    """The chart is data, so its question is checked like any other claim."""
    monkeypatch.setattr(agent, "DATA", tmp_path)
    bare = json.loads(json.dumps(FIGURE))
    bare["citations"] = []
    folded = agent.fold_groups(json.loads(json.dumps(QUIZ)), [], [bare])
    track = tmp_path / "content" / "run" / "hcp"
    track.mkdir(parents=True)
    (track / "quiz.json").write_text(json.dumps(folded))

    question = folded["questions"][-1]
    assert question["figure"]["series"][0]["points"][0]["value"] == 24.8
    assert "groups" not in folded  # a figure is attached to a question, not grouped

    findings, _stats = judge.deterministic_findings("run", "hcp", "Ibrance")
    assert any(finding.unit_id == "quiz-f1" and finding.check == "uncited" for finding in findings)


def test_an_unknown_group_kind_is_refused():
    """Silently dropping a format would lose questions a learner was meant to answer."""
    group = json.loads(json.dumps(BOARD))
    group["kind"] = "wordsearch"
    with pytest.raises(RuntimeError, match="Unknown group kind"):
        agent.fold_groups(json.loads(json.dumps(QUIZ)), [group])


def test_removing_a_cycle_cannot_delete_the_videos_it_borrowed(tmp_path):
    """A cycle that owns its quiz still symlinks the 100MB it did not change.

    `--remove` deletes that cycle's folder, and if the delete followed the link it
    would take the source course's video library with it. Asserted rather than
    assumed, because the failure is silent and unrecoverable.
    """
    import shutil

    from scripts.seed_schedule import _own_track

    origin, root = tmp_path / "source", tmp_path / "cycle"
    (origin / "hcp" / "videos").mkdir(parents=True)
    (origin / "hcp" / "videos" / "lesson.mp4").write_text("frames")
    (origin / "hcp" / "quiz.json").write_text("{}")

    _own_track(origin, root, "hcp")
    assert (root / "hcp" / "videos").is_symlink()
    assert not (root / "hcp" / "quiz.json").is_symlink()

    shutil.rmtree(root)
    assert (origin / "hcp" / "videos" / "lesson.mp4").read_text() == "frames"


def test_feedback_to_the_agent_is_a_new_question_not_a_cache_hit(tmp_path, monkeypatch):
    """The regenerate-with-the-measurement loop is a no-op if the cache answers it."""
    monkeypatch.setattr(agent, "DATA", tmp_path)
    plain = agent._cache_path("assets", "hcp", "triage", "system", "user")
    corrected = agent._cache_path("assets", "hcp", "triage", "system", "user\n\nMEASUREMENT: scored 88%")

    assert plain != corrected


def test_a_quiz_without_a_board_is_unchanged():
    """Content built before the format existed must keep working exactly as it did."""
    assert _questions(_content(QUIZ), "hcp", "final") == QUIZ["questions"]
    assert len(_questions(_content(QUIZ), "hcp", "baseline")) == 5
    assert _groups(QUIZ, QUIZ["questions"]) == []

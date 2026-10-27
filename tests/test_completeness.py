import json

import pytest

from src import agent, completeness, learning

RUN_ID = "ibrance-coverage"


@pytest.fixture(autouse=True)
def no_billed_calls(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _deck(*slides):
    return {"slides": [
        {"number": index, "title": title, "purpose": "Teach", "content": list(content), "citations": []}
        for index, (title, content) in enumerate(slides, 1)
    ]}


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    for track in ("hcp", "msl"):
        (tmp_path / "content" / RUN_ID / track / "ppt").mkdir(parents=True)
    (tmp_path / "content" / RUN_ID / "manifest.json").write_text(json.dumps({
        "run_id": RUN_ID, "drug": {"brand": "Ibrance", "generic": "Palbociclib", "area": "Oncology"},
    }))
    return RUN_ID


def _write(track: str, deck: dict):
    (agent.DATA / "content" / RUN_ID / track / "ppt" / "deck_spec.json").write_text(json.dumps(deck))


def test_a_topic_nothing_addresses_is_missing(run):
    _write("hcp", _deck(("Welcome", ["An introduction to the course."])))
    _write("msl", _deck(("Welcome", ["An introduction to the course."])))

    row = next(r for r in completeness.matrix(run)["rows"] if r["id"] == "contraindications")

    assert row["tracks"]["hcp"]["state"] == "missing"
    assert row["tracks"]["hcp"]["total"] == 0


def test_a_topic_mentioned_once_is_thin_not_covered(run):
    """The state that matters most: on a large course, one mention reads as coverage."""
    _write("hcp", _deck(
        ("Safety overview", ["IBRANCE is contraindicated in nobody in particular."]),
        ("Something else", ["Unrelated content about scheduling."]),
    ))
    _write("msl", _deck(("Welcome", ["An introduction."])))

    row = next(r for r in completeness.matrix(run)["rows"] if r["id"] == "contraindications")

    assert row["tracks"]["hcp"]["state"] == "thin"
    assert row["tracks"]["hcp"]["total"] == 1


def test_a_topic_two_units_address_is_covered(run):
    _write("hcp", _deck(
        ("Contraindications", ["IBRANCE is contraindicated in this population."]),
        ("Hypersensitivity", ["Known hypersensitivity to palbociclib."]),
    ))
    _write("msl", _deck(("Welcome", ["An introduction."])))

    row = next(r for r in completeness.matrix(run)["rows"] if r["id"] == "contraindications")

    assert row["tracks"]["hcp"]["state"] == "covered"
    assert [unit["reference"] for unit in row["tracks"]["hcp"]["units"]] == [
        "Slide 1: Contraindications", "Slide 2: Hypersensitivity",
    ]


def test_a_topic_another_audience_needs_is_not_held_against_this_one(run):
    """An HCP course is not incomplete for lacking an MSL's off-label procedure."""
    _write("hcp", _deck(("Welcome", ["An introduction."])))
    _write("msl", _deck(("Welcome", ["An introduction."])))

    row = next(r for r in completeness.matrix(run)["rows"] if r["id"] == "off_label_handling")

    assert row["tracks"]["hcp"] is None
    assert row["tracks"]["msl"]["state"] == "missing"


def test_a_thin_topic_is_raised_one_severity_below_an_absent_one(run):
    _write("hcp", _deck(
        ("Safety", ["IBRANCE is contraindicated in nobody."]),
        ("Filler", ["Unrelated."]),
    ))
    _write("msl", _deck(("Welcome", ["An introduction."])))

    gaps = {(gap["track"], gap["topic"]): gap for gap in completeness.gaps(run)}

    assert gaps[("hcp", "contraindications")]["state"] == "thin"
    assert gaps[("hcp", "contraindications")]["severity"] == "major"
    assert gaps[("msl", "contraindications")]["state"] == "missing"
    assert gaps[("msl", "contraindications")]["severity"] == "blocking"


def test_a_gap_becomes_an_ordinary_review_comment_and_is_never_raised_twice(run):
    _write("hcp", _deck(("Welcome", ["An introduction."])))
    _write("msl", _deck(("Welcome", ["An introduction."])))

    raised = completeness.promote(run, finding_ids=[completeness.gap_id("msl", "contraindications")])

    assert len(raised) == 1
    assert raised[0]["origin"] == "automated_check"
    assert raised[0]["check"] == "not_covered"
    assert raised[0]["author_id"] == learning.CHECKER["id"]
    assert raised[0]["severity"] == "blocking"
    assert learning.readiness(learning.course(run))["can_publish"] is False

    again = completeness.promote(run, finding_ids=[completeness.gap_id("msl", "contraindications")])
    assert again == []


def test_the_curriculum_is_declared_outside_the_code():
    """A medical education lead changes what complete means without a deploy."""
    spec = completeness.curriculum()

    assert spec["schema_version"] == 1
    assert {topic["severity"] for topic in spec["topic"]} <= {"blocking", "major", "minor"}
    for topic in spec["topic"]:
        assert topic["patterns"] and topic["why"] and topic["audiences"]
        assert set(topic["audiences"]) <= {"hcp", "msl"}

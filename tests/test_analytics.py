"""The ROI model, and specifically what it does when a course is fast.

Every figure here is derived from timestamps, and the interesting failure mode is
not a wrong number — it is a number that rounds to zero and then propagates as a
division, a falsy check, or a saving of exactly 100%.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest

from src import agent, analytics, learning

RUN_ID = "ibrance-roi"
ADMIN, REVIEWER, LEARNER = "priya-raman", "anil-shekhar", "ken-osei"


@pytest.fixture(autouse=True)
def no_billed_calls(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def published(tmp_path, monkeypatch):
    """A course generated, reviewed and published inside twenty minutes.

    Deliberately the compressed case: it is what the product claims to make
    possible, and it is the shape that broke every downstream figure.
    """
    monkeypatch.setattr(agent, "DATA", tmp_path)
    started = datetime.now(UTC) - timedelta(minutes=20)
    base = tmp_path / "content" / RUN_ID
    base.mkdir(parents=True)
    (base / "manifest.json").write_text(json.dumps({
        "run_id": RUN_ID,
        "generated_at": (started + timedelta(minutes=3)).isoformat(),
        "drug": {"brand": "Ibrance", "generic": "Palbociclib", "area": "Oncology"},
        "citation_count": 341,
        "cost_usd": 0,
    }))
    run_log = tmp_path / "logs" / RUN_ID / "run.json"
    run_log.parent.mkdir(parents=True)
    run_log.write_text(json.dumps({"id": RUN_ID, "created_at": started.isoformat(), "mode": "replay"}))

    comment = learning.add_comment(RUN_ID, REVIEWER, "deck", "blocking", "Add the line-of-therapy context.")
    learning.resolve_comment(RUN_ID, comment["id"], "addressed", "Slide added.", ADMIN)
    learning.publish_version(RUN_ID, ADMIN, "Line-of-therapy slide added")
    learning.add_signoff(RUN_ID, REVIEWER, "approved", "Approved for release.")
    today = datetime.now(UTC).date()
    learning.publish_course(RUN_ID, ADMIN, today.isoformat(),
                            (today + timedelta(days=30)).isoformat(), [LEARNER])
    return RUN_ID


def test_a_course_published_the_same_day_still_reports_its_impact(published):
    """The product's own pitch is generation to field inside a day.

    Elapsed time was rounded to one decimal place, so anything under about an
    hour became 0.0 days — which read as falsy in the panel and hid the whole
    impact page, and made every figure derived from it claim a saving of exactly
    100% against a zero-length run.
    """
    report = analytics.roi(published)

    assert report["measured"]["days_to_publish"] is not None
    assert report["measured"]["days_to_publish"] > 0
    # A stated baseline cannot be beaten by literally all of itself.
    assert report["saving"]["percent_faster"] <= 99

    economics = analytics.unit_economics(published)
    assert economics["build_cost_usd"] > 0, "a course that reached the field did not cost nothing"
    assert economics["floored"] is True
    assert economics["expert_days_costed"] == analytics.MANUAL_BASELINE["min_expert_days"]

    phases = analytics.time_to_field(published)["phases"]
    spans = [phase["measured_days"] for phase in phases if phase["measured_minutes"]]
    assert spans and all(span > 0 for span in spans), "sub-day phases must survive rounding"


def test_an_agreement_rate_is_withheld_until_it_means_something(published):
    """One settled finding reporting 100% is a sample of one presented as a rate."""
    from src import judge

    leverage = analytics.checker_leverage(published)
    assert leverage["settled"] < judge.MIN_FOR_RATE
    assert leverage["agreement_percent"] is None
    assert leverage["min_for_rate"] == judge.MIN_FOR_RATE

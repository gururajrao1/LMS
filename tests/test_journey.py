"""The ten-step journey reads state, never stores it.

The rule under test: the "machine checks" step is done when the check has
*run* — a clean report with zero findings still counts. Waiting on findings
would strand every clean course at step three forever.
"""

import json

from src import agent, judge
from src.journey import steps


def _seed(tmp_path, monkeypatch, run_id="ibrance-journey"):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    (tmp_path / "content" / run_id).mkdir(parents=True)
    (tmp_path / "content" / run_id / "manifest.json").write_text(json.dumps({
        "drug": {"brand": "Ibrance", "generic": "palbociclib", "area": "Oncology"},
        "citation_count": 5,
    }))
    (tmp_path / "logs" / run_id).mkdir(parents=True)
    (tmp_path / "logs" / run_id / "run.json").write_text(json.dumps({"id": run_id}))


def _states(run_id):
    return {item["id"]: item["state"] for item in steps(run_id)["steps"]}


def test_check_step_waits_for_the_checker_to_run(tmp_path, monkeypatch):
    """No stored report, no done step — even on a fully generated course."""
    _seed(tmp_path, monkeypatch)
    assert _states("ibrance-journey")["check"] == "current"


def test_check_step_is_done_when_the_check_ran_clean(tmp_path, monkeypatch):
    """Zero findings is a finished check, not an unfinished one."""
    _seed(tmp_path, monkeypatch)
    path = judge.report_path("ibrance-journey")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"findings": [], "stats": {"coverage_percent": 100}}))
    assert _states("ibrance-journey")["check"] == "done"

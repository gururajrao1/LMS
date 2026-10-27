"""A replay run reproduces a finished course without calling a model."""

import asyncio
import json

import pytest

from src import agent


def _source(root, run_id="ibrance-source"):
    """A minimal but complete finished run, laid out as the agent writes one."""
    base = root / "content" / run_id
    (base / "master" / "sections").mkdir(parents=True)
    for path in sorted((agent.PROMPTS / "research").glob("*.md")):
        (base / "master" / "sections" / f"{path.stem}.json").write_text(json.dumps({
            "id": path.stem, "title": path.stem, "summary": "", "claims": [], "gaps": [], "warnings": [],
        }))
    (base / "master" / "dossier.json").write_text(json.dumps({
        "drug": {"brand": "Ibrance", "generic": "palbociclib", "area": "Oncology"},
        "title": "Ibrance master learning dossier",
        "sections": [{"id": "01", "claims": [{"citations": [{"url": "u", "title": "t"}]}]}],
        "gaps": [], "warnings": [],
    }))
    for track in ("hcp", "msl"):
        (base / track / "ppt").mkdir(parents=True)
        (base / track / "storyboard").mkdir(parents=True)
        (base / track / "videos").mkdir(parents=True)
        (base / track / "videos" / "one.mp4").write_bytes(b"video")
        (base / track / "ppt" / "deck_spec.json").write_text(json.dumps({"slides": [{"number": 1}]}))
        (base / track / "ppt" / f"ibrance-{track}-training.pptx").write_bytes(b"pptx")
        (base / track / "storyboard" / "storyboard.json").write_text(json.dumps({"scenes": []}))
        (base / track / "faq.json").write_text(json.dumps({"items": []}))
        (base / track / "quiz.json").write_text(json.dumps({"passing_score": 75, "questions": []}))
    (base / "source_manifest.json").write_text(json.dumps({"sources": [{"url": "u"}]}))
    (base / "learning_blueprint.json").write_text(json.dumps({"title": "Ibrance"}))
    (base / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "generated_at": "2026-01-01T00:00:00+00:00",
        "drug": {"brand": "Ibrance", "generic": "palbociclib", "area": "Oncology"},
    }))
    return run_id


@pytest.fixture
def replayed(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    monkeypatch.setattr(agent, "REPLAY_SOURCE", _source(tmp_path))
    monkeypatch.setattr(agent, "STAGE_DELAY", 0)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-used-by-a-replay")
    run = agent.create_run("Ibrance")
    asyncio.run(agent.run_agent(run["id"], "Ibrance"))
    return tmp_path, run["id"]


def test_replay_completes_without_a_model_call(replayed, monkeypatch):
    root, run_id = replayed
    assert agent.get_run(run_id)["status"] == "completed"
    assert agent.get_run(run_id)["mode"] == "replay"
    # No ledger at all: a replay that opened one would report itself as a free run
    # rather than as a run that never happened.
    assert not (root / "logs" / run_id / "usage.json").exists()


def test_replay_walks_the_same_stages_a_generation_would(replayed):
    root, run_id = replayed
    events = [json.loads(line) for line in (root / "logs" / run_id / "events.jsonl").read_text().splitlines()]
    stages = [event["stage"] for event in events]

    assert stages[0] == "resolve_drug"
    assert stages[-1] == "complete"
    assert sum(stage.startswith("research_") for stage in stages) == 14
    for stage in ["build_master_dossier", "generate_hcp_quiz", "generate_msl_ppt",
                  "render_hcp_pptx", "attach_citations"]:
        assert stage in stages, stage
    assert events[-1]["progress"] == 100


def test_replay_produces_a_course_the_api_can_serve(replayed):
    root, run_id = replayed
    base = root / "content" / run_id
    for track in ("hcp", "msl"):
        for name in ["quiz.json", "faq.json", "ppt/deck_spec.json", "storyboard/storyboard.json"]:
            assert (base / track / name).exists(), f"{track}/{name}"
        assert (base / track / "ppt" / f"ibrance-{track}-training.pptx").exists()
    assert len(list((base / "master" / "sections").glob("*.json"))) == 14
    manifest = json.loads((base / "manifest.json").read_text())
    assert manifest["run_id"] == run_id
    assert manifest["cost_usd"] == 0
    # Its own id and its own timestamp: a replay is a new run, not a second name
    # for the one it copied.
    assert manifest["generated_at"] != "2026-01-01T00:00:00+00:00"


def test_replay_symlinks_videos_rather_than_copying_them(replayed):
    root, run_id = replayed
    videos = root / "content" / run_id / "hcp" / "videos"
    assert videos.is_symlink(), "100MB of video must not be duplicated per demo run"
    assert (videos / "one.mp4").read_bytes() == b"video"


def test_without_a_replay_source_nothing_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    monkeypatch.setattr(agent, "REPLAY_SOURCE", "")
    assert agent.replay_source() is None


def test_a_missing_replay_source_is_ignored_rather_than_fatal(tmp_path, monkeypatch):
    """A stale id in the environment must not take the Create content button down."""
    monkeypatch.setattr(agent, "DATA", tmp_path)
    monkeypatch.setattr(agent, "REPLAY_SOURCE", "ibrance-deleted-last-week")
    assert agent.replay_source() is None

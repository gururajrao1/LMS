import asyncio
import shutil
from types import SimpleNamespace

import pytest

from api.main import content
from src import agent


def test_local_data_uses_the_standard_run_path(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    dataset = agent.content_path("library", "ibrance")
    monkeypatch.setattr(agent, "DATA", tmp_path)
    shutil.copytree(dataset, tmp_path / "library" / "ibrance")

    run = agent.create_run("Ibrance")
    asyncio.run(agent.run_agent(run["id"], "Ibrance"))

    completed = agent.get_run(run["id"])
    assert completed["status"] == "completed"
    assert completed["progress"] == 100
    assert len(list((tmp_path / "content" / run["id"] / "master" / "sections").glob("*.json"))) == 14
    for learner in ["msl", "hcp"]:
        base = tmp_path / "content" / run["id"] / learner
        assert (base / "ppt" / f"ibrance-{learner}-training.pptx").read_bytes()[:2] == b"PK"
        assert (base / "storyboard" / "storyboard.json").exists()
        assert (base / "faq.json").exists()
        assert (base / "quiz.json").exists()
    course = content(run["id"])
    assert set(course["learners"]) == {"msl", "hcp"}
    assert course["learners"]["msl"]["faq"]["title"] != course["learners"]["hcp"]["faq"]["title"]
    assert (tmp_path / "content" / run["id"] / "assets" / "ibrance-training.pptx").read_bytes()[:2] == b"PK"
    assert "DM-IBRANCE-2026" in (tmp_path / "content" / run["id"] / "assets" / "faq.json").read_text()


def test_run_budget_records_usage_and_stops_before_overspend(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    run = agent.create_run("Ibrance")
    budget = agent.RunBudget(run["id"], limit_usd=1)
    response = SimpleNamespace(usage=SimpleNamespace(
        input_tokens=1000,
        output_tokens=500,
        server_tool_use=SimpleNamespace(web_search_requests=2),
    ))

    budget.record(response, "research")

    assert budget.spent_usd == pytest.approx(0.027)
    assert agent._json(tmp_path / "logs" / run["id"] / "usage.json")["calls"][0]["web_searches"] == 2
    with pytest.raises(RuntimeError, match="Stopped before"):
        budget.check("large call", max_tokens=100_000)
    with pytest.raises(RuntimeError, match="token safety limit"):
        budget.check("large input", max_tokens=10, input_tokens=agent.MAX_INPUT_TOKENS + 1)


def test_failed_attempt_is_never_recorded_as_free(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    run = agent.create_run("Ibrance")
    budget = agent.RunBudget(run["id"])
    attempt = budget.start_attempt("pptx", 10_000, 16_000, "pptx")

    budget.fail_attempt(attempt, TimeoutError("timed out"))

    usage = agent._json(tmp_path / "logs" / run["id"] / "usage.json")
    assert usage["billing_status"] == "reconciliation_required"
    assert usage["unknown_cost_attempts"] == 1
    assert usage["calls"][0]["cost_usd"] is None
    with pytest.raises(RuntimeError, match="requires billing reconciliation"):
        budget.check("next call", max_tokens=100)


def test_a_rejected_request_is_not_treated_as_unknown_cost(tmp_path, monkeypatch):
    """A 400 never reaches generation, so it is not billed and must not block the run."""
    monkeypatch.setattr(agent, "DATA", tmp_path)
    run = agent.create_run("Ibrance")
    budget = agent.RunBudget(run["id"])
    attempt = budget.start_attempt("judge", 2_000, 1_200, "judge")

    budget.fail_attempt(attempt, RuntimeError("Error code: 400 - {'type': 'invalid_request_error'}"))

    usage = agent._json(tmp_path / "logs" / run["id"] / "usage.json")
    assert usage["unknown_cost_attempts"] == 0
    assert usage["calls"][0]["status"] == "failed"
    assert usage["calls"][0]["cost_usd"] == 0
    budget.check("next call", max_tokens=100)


def test_one_hour_cache_write_uses_double_input_price(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    run = agent.create_run("Ibrance")
    budget = agent.RunBudget(run["id"])
    response = SimpleNamespace(usage=SimpleNamespace(
        input_tokens=0,
        cache_creation_input_tokens=1_000_000,
        cache_read_input_tokens=0,
        output_tokens=0,
        server_tool_use=None,
    ))

    budget.record(response, "cached asset")

    assert budget.spent_usd == pytest.approx(agent.INPUT_USD_PER_MTOK * 2)


def test_local_ppt_provider_never_calls_anthropic(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    monkeypatch.setattr(agent, "PPT_PROVIDER", "local")
    agent._write(tmp_path / "config" / "anthropic_deck_skill.json", {"id": "skill-test", "version": "1"})
    prepared = tmp_path / "library" / "ibrance" / "hcp" / "ppt" / "ibrance-hcp-training.pptx"
    prepared.parent.mkdir(parents=True)
    prepared.write_bytes(b"PK prepared deck")
    run = agent.create_run("Ibrance")
    target = tmp_path / "output.pptx"

    asyncio.run(agent._pptx({"title": "Deck"}, "hcp", target, None, agent.RunBudget(run["id"]), "ibrance"))

    assert target.read_bytes() == prepared.read_bytes()
    assert agent._json(tmp_path / "logs" / run["id"] / "usage.json")["spent_usd"] == 0


def test_structured_output_cache_is_validated_and_free(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    run = agent.create_run("Ibrance")
    budget = agent.RunBudget(run["id"])
    cached = agent._cache_path("research", "Ibrance", "section one")
    agent._write(cached, {
        "id": "01_disease_foundation",
        "title": "Disease foundation",
        "summary": "Summary",
        "claims": [{
            "text": "Claim",
            "evidence_type": "approved label",
            "citations": [{
                "title": "Source",
                "url": "https://example.com",
                "locator": "p. 1",
                "supporting_text": "Support",
            }],
        }],
        "gaps": [],
        "warnings": [],
    })

    value = asyncio.run(agent._message_json(
        "system",
        "user",
        "research cache test",
        budget,
        agent.ResearchSection,
        cache_path=cached,
    ))

    assert value["id"] == "01_disease_foundation"
    assert budget.spent_usd == 0
    assert budget.calls[0]["local_cache_hit"] is True


def test_anthropic_schemas_avoid_unsupported_constraints():
    prohibited = {"minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems", "pattern"}

    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(child) for child in value.values()), set())
        if isinstance(value, list):
            return set().union(*(keys(child) for child in value), set())
        return set()

    models = [agent.ResearchSection, agent.MasterDossier, *agent.ASSET_MODELS.values()]
    for model in models:
        assert not (keys(model.model_json_schema()) & prohibited)

    asset_schema = agent.PptAsset.model_json_schema()
    assert set(asset_schema["$defs"]["AssetCitation"]["properties"]) == {"title", "url", "locator"}


def test_research_recovers_safe_metadata_from_partial_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    run = agent.create_run("Ibrance")
    budget = agent.RunBudget(run["id"])
    prompt_file = agent.PROMPTS / "research" / "03_clinical_evidence.md"
    system = agent._prompt("common", "research_rules.md") + "\n\n" + prompt_file.read_text()
    user = (
        "Research Ibrance for this section. Search first, then call save_research_section exactly once "
        "with the completed evidence. Do not submit before reviewing the search results."
    )
    partial = agent._cache_path("research_partial", "ibrance", system, user)
    agent._write(partial, {
        "id": "clinical-evidence",
        "title": "Clinical evidence",
        "summary": "Summary",
        "claims": [],
    })

    section = asyncio.run(agent._research("Ibrance", prompt_file, budget))

    assert section["id"] == "03_clinical_evidence"
    assert section["gaps"] == []
    assert section["warnings"] == []
    assert budget.spent_usd == 0


def test_stream_failure_records_usage_and_raw_output(tmp_path, monkeypatch):
    import anthropic

    monkeypatch.setattr(agent, "DATA", tmp_path)
    run = agent.create_run("Ibrance")
    budget = agent.RunBudget(run["id"])
    response = SimpleNamespace(
        stop_reason="max_tokens",
        content=[SimpleNamespace(type="text", text='{"title":"unfinished"')],
        usage=SimpleNamespace(input_tokens=100, output_tokens=200, server_tool_use=None),
    )

    class Stream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def get_final_message(self):
            return response

    async def count_tokens(**_):
        return SimpleNamespace(input_tokens=100)

    client = SimpleNamespace(messages=SimpleNamespace(stream=lambda **_: Stream(), count_tokens=count_tokens))
    monkeypatch.setattr(anthropic, "AsyncAnthropic", lambda **_: client)
    cached = tmp_path / "cache" / "storyboard.json"

    with pytest.raises(agent.IncompleteStructuredOutput):
        asyncio.run(agent._message_json(
            "system",
            "user",
            "storyboard",
            budget,
            agent.StoryboardAsset,
            max_tokens=24_000,
            cache_path=cached,
        ))

    assert budget.calls[0]["output_tokens"] == 200
    assert cached.with_suffix(".partial.json").exists()


def test_folding_groups_keeps_the_pass_mark_the_author_set():
    """Folding must not dilute the mark by changing the count under it.

    `passing_score` is often written as "8 correct" for a 12-question quiz. Adding
    twenty group items behind that number turned an intended 67% into 8-of-32, a
    25% pass mark nobody chose.
    """
    quiz = {
        "passing_score": 8,
        "questions": [{"id": f"q{n}", "prompt": "", "options": [], "correct_index": 0,
                       "rationale": "", "citations": []} for n in range(1, 13)],
    }
    group = {
        "id": "board", "kind": "sort", "title": "Board", "instruction": "Sort these.",
        "buckets": ["A", "B"],
        "items": [{"id": f"b{n}", "prompt": f"Finding {n}", "correct_index": 0,
                   "rationale": "", "citations": []} for n in range(1, 9)],
    }

    folded = agent.fold_groups(quiz, [group])

    assert len(folded["questions"]) == 20
    assert folded["passing_score"] == 67
    # And it survives the read path, which normalizes again.
    assert agent.passing_percent(folded) == 67


def test_a_pass_mark_already_in_percent_is_left_alone():
    quiz = {"passing_score": 80,
            "questions": [{"id": f"q{n}", "prompt": "", "options": [], "correct_index": 0,
                           "rationale": "", "citations": []} for n in range(1, 13)]}
    assert agent.fold_groups(quiz, [])["passing_score"] == 80

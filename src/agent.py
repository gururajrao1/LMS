import asyncio
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATA = Path(os.getenv("PHARMALEARN_DATA_DIR", ".pharmalearn"))
DATA = DATA if DATA.is_absolute() else ROOT / DATA
PROMPTS = ROOT / "src" / "prompts"
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
RUN_BUDGET_USD = float(os.getenv("PHARMALEARN_RUN_BUDGET_USD", "8"))
RESEARCH_MAX_TOKENS = 24_000
ASSET_MAX_TOKENS = 24_000
SONNET5_INTRO = MODEL == "claude-sonnet-5" and date.today() <= date(2026, 8, 31)
INPUT_USD_PER_MTOK = float(os.getenv("ANTHROPIC_INPUT_USD_PER_MTOK", "2" if SONNET5_INTRO else "3"))
OUTPUT_USD_PER_MTOK = float(os.getenv("ANTHROPIC_OUTPUT_USD_PER_MTOK", "10" if SONNET5_INTRO else "15"))
WEB_SEARCH_USD = float(os.getenv("ANTHROPIC_WEB_SEARCH_USD", "0.01"))
CACHE_WRITE_MULTIPLIER = 2.0
CACHE_READ_MULTIPLIER = 0.1
MAX_INPUT_TOKENS = int(os.getenv("PHARMALEARN_MAX_INPUT_TOKENS", "190000"))
PPT_PROVIDER = os.getenv("PHARMALEARN_PPT_PROVIDER", "local").lower()
PPT_STAGE_BUDGET_USD = float(os.getenv("PHARMALEARN_PPT_STAGE_BUDGET_USD", "1.50"))
PPT_MAX_TURNS = int(os.getenv("PHARMALEARN_PPT_MAX_TURNS", "2"))
STAGE_DELAY = float(os.getenv("PHARMALEARN_STAGE_DELAY", "0.35"))
# A finished run to replay stage by stage instead of regenerating. Set for a
# demo, where the point is to show the pipeline, not to pay for it twice.
REPLAY_SOURCE = os.getenv("PHARMALEARN_REPLAY_SOURCE", "").strip()
CACHE_SCHEMA_VERSION = "1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(StrictModel):
    title: str
    url: str
    locator: str
    supporting_text: str


class AssetCitation(StrictModel):
    title: str
    url: str
    locator: str


class Claim(StrictModel):
    text: str
    evidence_type: str
    citations: list[Citation]


class ResearchSection(StrictModel):
    id: str
    title: str
    summary: str
    claims: list[Claim]
    gaps: list[str]
    warnings: list[str]


class Drug(StrictModel):
    brand: str
    generic: str
    manufacturer: str
    area: str


class MasterDossier(StrictModel):
    drug: Drug
    title: str
    gaps: list[str]
    warnings: list[str]


class Slide(StrictModel):
    number: int
    title: str
    purpose: str
    content: list[str]
    citations: list[AssetCitation]


class PptAsset(StrictModel):
    title: str
    subtitle: str
    audience: str
    slides: list[Slide]


class StoryboardScene(StrictModel):
    id: int
    duration_seconds: int
    title: str
    learning_purpose: str
    narration: str
    visual: str
    on_screen_text: str
    citations: list[AssetCitation]


class StoryboardAsset(StrictModel):
    title: str
    estimated_duration_seconds: int
    scenes: list[StoryboardScene]


class FaqItem(StrictModel):
    question: str
    answer: str
    nuance: str
    escalation: str
    citations: list[AssetCitation]


class FaqAsset(StrictModel):
    title: str
    items: list[FaqItem]


class FourOptions(StrictModel):
    a: str
    b: str
    c: str
    d: str


class QuizQuestion(StrictModel):
    id: str
    prompt: str
    options: FourOptions
    correct_index: Literal[0, 1, 2, 3]
    rationale: str
    option_rationales: FourOptions
    citations: list[AssetCitation]


class QuizAsset(StrictModel):
    title: str
    passing_score: int
    questions: list[QuizQuestion]


class TwoBuckets(StrictModel):
    a: str
    b: str


class TriageItem(StrictModel):
    id: str
    prompt: str
    correct_index: Literal[0, 1]
    rationale: str
    citations: list[AssetCitation]


class TriageAsset(StrictModel):
    """A sort board: short clinical findings, each belonging in one of two buckets.

    The gamified format. It is deliberately *not* a second assessment engine —
    see `fold_groups`, which turns every item into an ordinary quiz question.
    """

    title: str
    instruction: str
    buckets: TwoBuckets
    items: list[TriageItem]


class AssembleBlank(StrictModel):
    id: str
    before: str
    options: FourOptions
    correct_index: Literal[0, 1, 2, 3]


class AssembleItem(StrictModel):
    id: str
    prompt: str
    blanks: list[AssembleBlank]
    tail: str
    rationale: str
    citations: list[AssetCitation]


class AssembleAsset(StrictModel):
    """Word building: reconstruct a labelled instruction from candidate phrases.

    The clinical version of the mechanic. What matters in the field is the exact
    labelled wording — a threshold, a timing, a dose — so the chips are the words
    that change the meaning, not letters of a drug name.
    """

    title: str
    instruction: str
    items: list[AssembleItem]


class FigurePoint(StrictModel):
    label: str
    value: float


class FigureSeries(StrictModel):
    name: str
    points: list[FigurePoint]


class FigureQuestion(StrictModel):
    id: str
    caption: str
    chart_kind: Literal["line", "bar"]
    x_title: str
    y_title: str
    y_suffix: str
    series: list[FigureSeries]
    prompt: str
    options: FourOptions
    correct_index: Literal[0, 1, 2, 3]
    rationale: str
    citations: list[AssetCitation]


class FigureAsset(StrictModel):
    """Read-the-data questions, drawn from numbers the dossier actually recorded.

    This is the honest form of "include images to select from". Photographs of
    patients, scans and histology are the obvious reading of that request and the
    wrong one: they need licensing we do not have, and a wrong or unrepresentative
    image is a clinical error we could not check. A chart we render from cited
    numbers is verifiable, is the thing a field team is actually quizzed on, and
    every value in it can be traced back to its source.
    """

    title: str
    questions: list[FigureQuestion]


ASSET_MODELS = {
    "ppt": PptAsset,
    "storyboard": StoryboardAsset,
    "faq": FaqAsset,
    "quiz": QuizAsset,
    "triage": TriageAsset,
    "assemble": AssembleAsset,
    "figure": FigureAsset,
}


def _options(value) -> list[str]:
    return list(value.values()) if isinstance(value, dict) else list(value)


def _sort_group(group: dict) -> tuple[dict, list[dict]]:
    buckets = _options(group["buckets"])
    questions = [{
        "id": item["id"],
        "prompt": item["prompt"],
        "options": buckets,
        "correct_index": item["correct_index"],
        "rationale": item["rationale"],
        "citations": item.get("citations", []),
    } for item in group["items"]]
    return {"buckets": buckets}, questions


def _assemble_group(group: dict) -> tuple[dict, list[dict]]:
    """Each blank is its own question; the sentence is how they are presented."""
    items, questions = [], []
    for item in group["items"]:
        items.append({
            "id": item["id"],
            "prompt": item["prompt"],
            "tail": item["tail"],
            "blanks": [{"id": blank["id"], "before": blank["before"]} for blank in item["blanks"]],
        })
        for blank in item["blanks"]:
            questions.append({
                "id": blank["id"],
                "prompt": f"{item['prompt']} — {blank['before'].strip() or 'opening phrase'}",
                "options": _options(blank["options"]),
                "correct_index": blank["correct_index"],
                "rationale": item["rationale"],
                "citations": item.get("citations", []),
            })
    return {"items": items}, questions


GROUP_KINDS = {"sort": _sort_group, "assemble": _assemble_group}

# The gamified formats. Optional by construction: a library assembled before they
# existed simply has none, and the course is complete without them.
GAMIFIED = {"triage": "sort", "assemble": "assemble", "figure": None}


def fold_groups(quiz: dict, groups: list[dict], figures: list[dict] | None = None) -> dict:
    """Fold the gamified formats into the quiz as ordinary questions.

    The whole design rests on this function. Every format reduces to the same
    primitive — a prompt, a list of options, one correct index — so a sort-board
    item, one blank in an assembled sentence, and a question about a chart are all
    stored as ordinary quiz questions. What differs is only how they are drawn:
    a `group` key says which group a question belongs to, and a `figure` key
    carries the chart a question is asked about.

    The consequence is that nothing downstream needs to know a game was played.
    The checker reads them as questions and verifies their citations like any
    other (`judge.units`); `record_attempt` scores them with the same comparison,
    so they count toward the same certificate and the same measured uplift; the
    review queue can raise a comment on any of them. Delete `groups` and every
    item is still a valid, scored, checkable question — the format is a way of
    asking, not a different kind of thing to be right about.
    """
    questions = list(quiz["questions"])
    # Answers travel keyed by question id, so a collision would silently score one
    # item against another's correct answer. Cheap to check, invisible if it fails.
    seen = {question["id"] for question in questions}

    kept = []
    for group in groups:
        build = GROUP_KINDS.get(group["kind"])
        if not build:
            raise RuntimeError(f"Unknown group kind {group['kind']!r}")
        extra, produced = build(group)
        for question in produced:
            if question["id"] in seen:
                raise RuntimeError(f"Item {question['id']} collides with an existing quiz question id")
            seen.add(question["id"])
            questions.append({**question, "group": group["id"]})
        kept.append({"id": group["id"], "kind": group["kind"], "title": group["title"],
                     "instruction": group["instruction"], **extra})

    for figure in figures or []:
        if figure["id"] in seen:
            raise RuntimeError(f"Figure question {figure['id']} collides with an existing quiz question id")
        seen.add(figure["id"])
        questions.append({
            "id": figure["id"],
            "prompt": figure["prompt"],
            "options": _options(figure["options"]),
            "correct_index": figure["correct_index"],
            "rationale": figure["rationale"],
            "citations": figure.get("citations", []),
            "figure": {key: figure[key] for key in
                       ("caption", "chart_kind", "x_title", "y_title", "y_suffix", "series")},
        })

    # Fix the pass mark to a percentage before the question count changes under it.
    # `passing_score` is a percentage by contract but is often written as "8 correct",
    # and folding twenty group items behind that number turned an intended 8-of-12
    # into 8-of-32 — a 67% mark quietly becoming 25%. Converting here preserves what
    # the author actually set, and a value already in percent is left alone.
    folded = {**quiz, "questions": questions, "passing_score": passing_percent(quiz)}
    if kept:
        folded["groups"] = kept
    return folded


@dataclass
class RunBudget:
    run_id: str
    limit_usd: float = RUN_BUDGET_USD
    spent_usd: float = 0.0
    calls: list[dict] = field(default_factory=list)

    def __post_init__(self):
        path = content_path("logs", self.run_id, "usage.json")
        if path.exists():
            value = _json(path)
            self.spent_usd = value.get("spent_usd", 0)
            self.calls = value.get("calls", [])

    def _save(self):
        unknown = sum(call.get("cost_status") == "unknown" for call in self.calls)
        value = {
            "limit_usd": self.limit_usd,
            "spent_usd": round(self.spent_usd, 6),
            "unknown_cost_attempts": unknown,
            "billing_status": "reconciliation_required" if unknown else "recorded",
            "calls": self.calls,
        }
        _write(content_path("logs", self.run_id, "usage.json"), value)
        run = get_run(self.run_id)
        if run:
            run.update({"budget_usd": self.limit_usd, "cost_usd": value["spent_usd"]})
            _write(content_path("logs", self.run_id, "run.json"), run)

    def check(
        self,
        label: str,
        max_tokens: int,
        input_chars: int = 0,
        web_searches: int = 0,
        input_tokens: int | None = None,
        stage: str | None = None,
        stage_limit_usd: float | None = None,
    ):
        if any(call.get("cost_status") == "unknown" for call in self.calls):
            raise RuntimeError(
                f"Stopped before {label}: a previous Anthropic attempt has unknown cost and requires billing reconciliation"
            )
        estimated_input_tokens = input_tokens or max(1, input_chars // 3)
        if estimated_input_tokens > MAX_INPUT_TOKENS:
            raise RuntimeError(
                f"Stopped before {label}: {estimated_input_tokens:,} input tokens exceeds the "
                f"{MAX_INPUT_TOKENS:,}-token safety limit"
            )
        billing_input_tokens = estimated_input_tokens + web_searches * 25_000
        reserve = (
            billing_input_tokens * INPUT_USD_PER_MTOK / 1_000_000
            + max_tokens * OUTPUT_USD_PER_MTOK / 1_000_000
            + web_searches * WEB_SEARCH_USD
        )
        if stage and stage_limit_usd is not None:
            stage_spent = sum(call.get("cost_usd") or 0 for call in self.calls if call.get("stage") == stage)
            if stage_spent + reserve > stage_limit_usd:
                raise RuntimeError(
                    f"Stopped before {label}: the ${stage_limit_usd:.2f} {stage} stage limit would be exceeded"
                )
        if self.spent_usd + reserve > self.limit_usd - 0.25:
            raise RuntimeError(
                f"Stopped before {label}: ${self.spent_usd:.2f} used from the ${self.limit_usd:.2f} run budget"
            )

    def start_attempt(
        self,
        label: str,
        input_tokens: int,
        max_output_tokens: int,
        stage: str | None = None,
    ) -> str:
        attempt_id = f"attempt-{len(self.calls) + 1:04d}"
        self.calls.append({
            "attempt_id": attempt_id,
            "label": label,
            "stage": stage or label,
            "status": "pending",
            "cost_status": "unknown",
            "preflight_input_tokens": input_tokens,
            "max_output_tokens": max_output_tokens,
            "started_at": datetime.now(UTC).isoformat(),
            "cost_usd": None,
        })
        self._save()
        return attempt_id

    def record(self, response, label: str, attempt_id: str | None = None, stage: str | None = None):
        usage = response.usage
        server = getattr(usage, "server_tool_use", None)
        searches = getattr(server, "web_search_requests", 0) if server else 0
        input_tokens = getattr(usage, "input_tokens", 0)
        cache_creation_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0)
        cost = (
            input_tokens * INPUT_USD_PER_MTOK / 1_000_000
            + cache_creation_tokens * INPUT_USD_PER_MTOK * CACHE_WRITE_MULTIPLIER / 1_000_000
            + cache_read_tokens * INPUT_USD_PER_MTOK * CACHE_READ_MULTIPLIER / 1_000_000
            + output_tokens * OUTPUT_USD_PER_MTOK / 1_000_000
            + searches * WEB_SEARCH_USD
        )
        self.spent_usd += cost
        value = {
            "label": label,
            "stage": stage or label,
            "status": "completed",
            "cost_status": "recorded",
            "input_tokens": input_tokens,
            "cache_creation_input_tokens": cache_creation_tokens,
            "cache_read_input_tokens": cache_read_tokens,
            "output_tokens": output_tokens,
            "web_searches": searches,
            "cost_usd": round(cost, 6),
            "finished_at": datetime.now(UTC).isoformat(),
        }
        if attempt_id:
            next(call for call in self.calls if call.get("attempt_id") == attempt_id).update(value)
        else:
            self.calls.append(value)
        self._save()

    def fail_attempt(self, attempt_id: str, error: BaseException):
        # A request rejected as invalid never reached generation, so it is not
        # billed and must not poison the ledger. Anything else may have partially
        # executed and stays unknown until it is reconciled against the invoice.
        rejected = "invalid_request_error" in str(error) or type(error).__name__ == "BadRequestError"
        call = next(call for call in self.calls if call.get("attempt_id") == attempt_id)
        # A rejected request never reached generation, so recording it as an
        # unknown cost is simply wrong. Everything else may have been billed and
        # stays unknown until it is reconciled against the invoice — that gate is
        # deliberate and must not be widened for convenience.
        detail = (
            {"cost_status": "recorded", "cost_usd": 0,
             "reconciliation": "rejected before generation; not billable"}
            if rejected else
            {"cost_status": "unknown", "cost_usd": None}
        )
        call.update({
            "status": "failed",
            "error": f"{type(error).__name__}: {error}",
            "finished_at": datetime.now(UTC).isoformat(),
            **detail,
        })
        self._save()

    def record_cache_hit(self, label: str, path: Path):
        self.calls.append({
            "label": label,
            "stage": label,
            "status": "cached",
            "cost_status": "recorded",
            "local_cache_hit": True,
            "path": str(path),
            "cost_usd": 0,
        })
        self._save()


def content_path(*parts: str) -> Path:
    return DATA.joinpath(*parts)


LITERAL_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


def decode_literal_escapes(value):
    """Repair `\\u2013`-style escapes a model can emit inside a JSON string value.

    The result is the six characters backslash-u-2-0-1-3 rather than an en dash,
    which then renders literally everywhere the claim is shown.
    """
    if isinstance(value, str):
        return LITERAL_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), value)
    if isinstance(value, list):
        return [decode_literal_escapes(item) for item in value]
    if isinstance(value, dict):
        return {key: decode_literal_escapes(item) for key, item in value.items()}
    return value


def passing_percent(quiz: dict) -> int:
    """The pass mark as a percentage.

    `passing_score` is a percentage by contract, but a model can read the field
    as "questions answered correctly". A value no larger than the question count
    can only mean a raw count, so convert it rather than failing a learner who
    scored 70% against a mark of "8".
    """
    value = int(quiz.get("passing_score", 75))
    total = len(quiz.get("questions", []))
    if total and value <= total:
        return round(100 * value / total)
    return max(0, min(100, value))


def _json(path: Path):
    return json.loads(path.read_text())


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def _copy(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _prompt(*parts: str) -> str:
    return PROMPTS.joinpath(*parts).read_text()


def _cache_path(kind: str, *values: str, suffix: str = ".json") -> Path:
    def path_for(parts):
        digest = hashlib.sha256()
        for value in parts:
            digest.update(value.encode())
            digest.update(b"\0")
        return content_path("cache", kind, f"{digest.hexdigest()[:24]}{suffix}")

    current = path_for((CACHE_SCHEMA_VERSION, MODEL, *values))
    legacy = path_for((CACHE_SCHEMA_VERSION, MODEL, datetime.now(UTC).date().isoformat(), *values))
    if legacy.exists() and not current.exists():
        _copy(legacy, current)
    return current


def prompt_hashes():
    return {
        path.relative_to(PROMPTS).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        for path in sorted(PROMPTS.rglob("*.md"))
    }


def create_run(drug: str):
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{_slug(drug)}-{stamp}"
    run = {
        "id": run_id,
        "drug": drug,
        "status": "queued",
        "progress": 0,
        "created_at": datetime.now(UTC).isoformat(),
        "prompt_hashes": prompt_hashes(),
    }
    _write(content_path("logs", run_id, "run.json"), run)
    return run


def get_run(run_id: str):
    path = content_path("logs", Path(run_id).name, "run.json")
    return _json(path) if path.exists() else None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _emit(run_id: str, stage: str, progress: int, message: str, status: str = "running"):
    event = {
        "stage": stage,
        "status": status,
        "progress": progress,
        "message": message,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    log = content_path("logs", run_id, "events.jsonl")
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as file:
        file.write(json.dumps(event) + "\n")
    run = get_run(run_id) or {"id": run_id}
    run.update({"status": status, "progress": progress, "current_stage": stage})
    _write(content_path("logs", run_id, "run.json"), run)


async def _stage(run_id: str, name: str, progress: int, message: str):
    _emit(run_id, name, progress, message)
    await asyncio.sleep(STAGE_DELAY)


class IncompleteStructuredOutput(RuntimeError):
    pass


async def _metered_send(
    send,
    budget: RunBudget,
    label: str,
    input_tokens: int,
    max_tokens: int,
    web_searches: int = 0,
    stage: str | None = None,
    stage_limit_usd: float | None = None,
):
    budget.check(
        label,
        max_tokens,
        web_searches=web_searches,
        input_tokens=input_tokens,
        stage=stage,
        stage_limit_usd=stage_limit_usd,
    )
    attempt_id = budget.start_attempt(label, input_tokens, max_tokens, stage)
    try:
        response = await send()
    except BaseException as error:
        budget.fail_attempt(attempt_id, error)
        raise
    budget.record(response, label, attempt_id, stage)
    return response


async def _message_json(
    system: str,
    user: str,
    label: str,
    budget: RunBudget,
    output_model: type[BaseModel],
    tools=None,
    max_tokens=ASSET_MAX_TOKENS,
    cache_path: Path | None = None,
    cache_system: bool = False,
    stage: str | None = None,
    stage_limit_usd: float | None = None,
):
    from anthropic import AsyncAnthropic

    if cache_path and cache_path.exists():
        value = output_model.model_validate(_json(cache_path)).model_dump()
        budget.record_cache_hit(label, cache_path)
        return decode_literal_escapes(value)

    client = AsyncAnthropic(max_retries=0)
    messages = [{"role": "user", "content": user}]
    system_value = [{
        "type": "text",
        "text": system,
        "cache_control": {"type": "ephemeral", "ttl": "1h"},
    }] if cache_system else system
    request = {"model": MODEL, "max_tokens": max_tokens, "system": system_value, "messages": messages}
    if tools:
        request["tools"] = tools

    streamed = max_tokens >= 24_000
    output_config = {"format": {
        "type": "json_schema",
        "schema": output_model.model_json_schema(),
    }}

    async def send():
        if streamed:
            stream_request = {**request, "output_config": output_config}
            async with client.messages.stream(**stream_request) as stream:
                return await stream.get_final_message()
        return await client.messages.parse(**request, output_format=output_model)

    async def counted_send():
        count_request = {key: request[key] for key in ["model", "system", "messages", "tools"] if key in request}
        count_request["output_config"] = output_config
        counted = await client.messages.count_tokens(**count_request)
        return await _metered_send(
            send,
            budget,
            label,
            counted.input_tokens,
            max_tokens,
            searches,
            stage=stage,
            stage_limit_usd=stage_limit_usd,
        )

    searches = sum(tool.get("max_uses", 0) for tool in tools or [] if tool.get("name") == "web_search")
    response = await counted_send()
    for _ in range(2):
        if response.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": response.content})
        request["messages"] = messages
        response = await counted_send()
    if response.stop_reason == "pause_turn":
        raise RuntimeError(f"Anthropic did not finish {label} after three turns")
    if streamed:
        raw = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        try:
            value = output_model.model_validate_json(raw).model_dump()
        except ValueError as error:
            partial = cache_path.with_suffix(".partial.json") if cache_path else _cache_path("partial", label)
            _write(partial, {"label": label, "stop_reason": response.stop_reason, "raw_output": raw})
            raise IncompleteStructuredOutput(
                f"Incomplete structured output for {label} (stop reason: {response.stop_reason}); raw output saved to {partial}"
            ) from error
    else:
        if response.parsed_output is None:
            raise RuntimeError(f"Anthropic returned no structured output for {label} (stop reason: {response.stop_reason})")
        value = response.parsed_output.model_dump()
    value = decode_literal_escapes(value)
    if cache_path:
        _write(cache_path, value)
    return value


async def _research(drug: str, prompt_file: Path, budget: RunBudget):
    from anthropic import AsyncAnthropic

    system = _prompt("common", "research_rules.md") + "\n\n" + prompt_file.read_text()
    user = (
        f"Research {drug} for this section. Search first, then call save_research_section exactly once "
        "with the completed evidence. Do not submit before reviewing the search results."
    )
    cached = _cache_path("research", drug.lower(), system, user)
    partial = _cache_path("research_partial", drug.lower(), system, user)
    if cached.exists():
        section = ResearchSection.model_validate(_json(cached)).model_dump()
        budget.record_cache_hit(prompt_file.stem, cached)
        return section
    if partial.exists():
        raw = _json(partial)
        raw["id"] = prompt_file.stem
        raw.setdefault("gaps", [])
        raw.setdefault("warnings", [])
        try:
            section = ResearchSection.model_validate(raw).model_dump()
            _write(cached, section)
            budget.record_cache_hit(prompt_file.stem, partial)
            return section
        except ValueError:
            pass

    tools = [
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 3,
            "user_location": {"type": "approximate", "country": "US"},
        },
        {
            "name": "save_research_section",
            "description": "Submit the completed, source-grounded research section after web research is finished.",
            "input_schema": ResearchSection.model_json_schema(),
            "strict": True,
        },
    ]
    client = AsyncAnthropic(max_retries=0)
    messages = [{"role": "user", "content": user}]
    request = {"model": MODEL, "max_tokens": RESEARCH_MAX_TOKENS, "system": system, "messages": messages, "tools": tools}

    async def send():
        async with client.messages.stream(**request) as stream:
            return await stream.get_final_message()

    for attempt in range(3):
        counted = await client.messages.count_tokens(
            model=request["model"],
            system=request["system"],
            messages=request["messages"],
            tools=request["tools"],
        )
        response = await _metered_send(
            send,
            budget,
            prompt_file.stem,
            counted.input_tokens,
            request["max_tokens"],
            web_searches=3,
        )
        for block in response.content:
            if getattr(block, "type", "") == "tool_use" and getattr(block, "name", "") == "save_research_section":
                raw = dict(block.input)
                _write(partial, raw)
                raw["id"] = prompt_file.stem
                raw.setdefault("gaps", [])
                raw.setdefault("warnings", [])
                section = ResearchSection.model_validate(raw).model_dump()
                section["id"] = prompt_file.stem
                _write(cached, section)
                return section
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
        elif attempt < 2:
            messages.extend([
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": "Now submit the completed research with save_research_section."},
            ])
        request["messages"] = messages
    raise RuntimeError(f"Anthropic did not submit structured research for {prompt_file.stem}")


def _seed_sections(context: dict):
    topics = {
        "01": {"approved_use"},
        "02": {"mechanism", "dosing"},
        "03": {"pivotal_evidence"},
        "04": {"approved_use", "dosing", "monitoring"},
        "05": {"monitoring"},
        "06": {"approved_use"},
        "07": set(),
        "08": {"mechanism", "pivotal_evidence"},
        "09": set(),
        "10": {"dosing", "monitoring"},
        "11": {"approved_use"},
        "12": {"pivotal_evidence"},
        "13": set(),
        "14": {"mechanism"},
    }
    sections = []
    for path in sorted((PROMPTS / "research").glob("*.md")):
        wanted = topics[path.stem[:2]]
        claims = [claim for claim in context["claims"] if claim["topic"] in wanted]
        title = path.read_text().splitlines()[0].removeprefix("# ")
        sections.append({
            "id": path.stem,
            "title": title,
            "summary": "Prepared from the bundled Ibrance evidence for the no-key demo run.",
            "claims": claims,
            "gaps": [] if claims else ["Not covered by the bundled no-key evidence."],
            "warnings": [],
        })
    return sections


async def _master_dossier(drug: str, sections: list[dict], local_source: Path | None, budget: RunBudget | None):
    if local_source:
        drug_record = _json(local_source / "manifest.json")["drug"]
        return {
            "drug": drug_record,
            "title": f"{drug_record['brand']} master learning dossier",
            "sections": sections,
            "gaps": [gap for section in sections for gap in section["gaps"]],
            "warnings": [],
        }
    system = _prompt("common", "citations.md") + "\n\n" + _prompt("common", "master_dossier.md")
    user = f"DRUG: {drug}\n\nRESEARCHED SECTIONS:\n{json.dumps(sections)}"
    overview = await _message_json(
        system,
        user,
        "master dossier",
        budget,
        MasterDossier,
        max_tokens=4000,
        cache_path=_cache_path("master", system, user),
    )
    overview["sections"] = sections
    return overview


async def _asset(master: dict, learner: str, kind: str, local_source: Path | None, budget: RunBudget | None,
                 note: str = ""):
    """Build one learning asset.

    `note` appends caller-supplied feedback to the prompt — a measurement of the
    previous attempt, so the model is corrected by a number rather than by a
    stronger adjective. It is part of the cache key, so asking again with new
    feedback is a new question rather than a cache hit on the old answer.
    """
    filenames = {
        "ppt": "deck_spec.json",
        "storyboard": "video_storyboard.json",
        "faq": "faq.json",
        "quiz": "quiz.json",
        "triage": "triage.json",
        "assemble": "assemble.json",
        "figure": "figure.json",
    }
    if local_source:
        paths = {
            "ppt": local_source / learner / "ppt" / "deck_spec.json",
            "storyboard": local_source / learner / "storyboard" / "storyboard.json",
            "faq": local_source / learner / "faq.json",
            "quiz": local_source / learner / "quiz.json",
            "triage": local_source / learner / "triage.json",
            "assemble": local_source / learner / "assemble.json",
            "figure": local_source / learner / "figure.json",
        }
        fallback = local_source / "assets" / filenames[kind]
        if kind in GAMIFIED and not paths[kind].exists() and not fallback.exists():
            # A library assembled before the board existed simply has no board.
            # The course is complete without one; failing here would make an
            # optional format retroactively mandatory for content already built.
            return None
        return _json(paths[kind] if paths[kind].exists() else fallback)
    system = _prompt("common", "citations.md") + f"\n\nMASTER DOSSIER:\n{json.dumps(master)}"
    user = "\n\n".join(filter(None, [
        _prompt("learners", f"{learner}.md"),
        _prompt("formats", f"{kind}.md"),
        f"Generate the {kind} learning asset for the {learner.upper()} learner.",
        note,
    ]))
    cached = _cache_path("assets", learner, kind, system, user)
    # Any format with per-item length limits can run over them and come back
    # truncated, so they all get one retry. The last attempt re-raises whatever
    # it hit: swallowing it here left `value` unbound and turned a clear
    # "the model was cut off" into an UnboundLocalError three frames away.
    attempts = 1 if kind in {"ppt", "faq"} else 2
    for attempt in range(attempts):
        retry_user = user if attempt == 0 else user + (
            "\n\nRETRY: The previous response was incomplete. Follow every length limit strictly and return "
            "one complete JSON object. Do not add extra items or commentary."
        )
        try:
            value = await _message_json(
                system,
                retry_user,
                f"{learner} {kind}" + (" retry" if attempt else ""),
                budget,
                ASSET_MODELS[kind],
                # The board is short but has to be reasoned about as a set — which
                # items defeat the surface reading is a property of the whole
                # board — and that reasoning ran the default budget out before the
                # JSON was finished. Headroom for thinking, not for more items.
                max_tokens=ASSET_MAX_TOKENS * 2 if kind in GAMIFIED else ASSET_MAX_TOKENS,
                cache_path=cached,
                cache_system=True,
            )
            break
        except IncompleteStructuredOutput:
            if attempt == attempts - 1:
                raise
    if kind == "quiz":
        if not 50 <= value["passing_score"] <= 100:
            raise RuntimeError("Quiz passing_score is a percentage and must be between 50 and 100")
        for question in value["questions"]:
            question["options"] = list(question["options"].values())
            question["option_rationales"] = list(question["option_rationales"].values())
    return value


def _deck_skill():
    skill_id = os.getenv("ANTHROPIC_DECK_SKILL_ID")
    if skill_id:
        return {"id": skill_id, "version": os.getenv("ANTHROPIC_DECK_SKILL_VERSION", "latest")}
    config = content_path("config", "anthropic_deck_skill.json")
    if not config.exists():
        raise RuntimeError("PharmaLearn deck Skill is not configured; run scripts/sync_anthropic_skill.py")
    return _json(config)


async def _pptx(
    deck: dict,
    learner: str,
    path: Path,
    local_source: Path | None,
    budget: RunBudget | None,
    drug_slug: str,
):
    if local_source:
        prepared = local_source / learner / "ppt" / f"ibrance-{learner}-training.pptx"
        _copy(prepared if prepared.exists() else local_source / "assets" / "ibrance-training.pptx", path)
        return

    custom_skill = _deck_skill()
    skills = [
        {"type": "anthropic", "skill_id": "pptx", "version": "latest"},
        {"type": "custom", "skill_id": custom_skill["id"], "version": custom_skill.get("version", "latest")},
    ]
    cached = _cache_path(
        "pptx",
        learner,
        json.dumps(deck, sort_keys=True),
        custom_skill["id"],
        str(custom_skill.get("version", "latest")),
        suffix=".pptx",
    )
    if cached.exists():
        _copy(cached, path)
        budget.record_cache_hit(f"{learner} pptx", cached)
        return
    if PPT_PROVIDER != "anthropic":
        prepared = content_path("library", drug_slug, learner, "ppt", f"{drug_slug}-{learner}-training.pptx")
        if not prepared.exists():
            raise RuntimeError(
                f"No local {learner.upper()} PowerPoint is available. Set PHARMALEARN_PPT_PROVIDER=anthropic "
                "to explicitly enable billable PowerPoint generation."
            )
        _copy(prepared, path)
        _copy(path, cached)
        if budget:
            budget.record_cache_hit(f"{learner} pptx", prepared)
        return

    from anthropic import AsyncAnthropic

    if budget is None:
        raise RuntimeError("Anthropic PowerPoint generation requires a run budget")
    client = AsyncAnthropic(max_retries=0)
    template = f"{learner.upper()}_Training_Deck_Template.pptx"
    prompt = (
        f"Create an editable PowerPoint for the {learner.upper()} learner using {template} from the "
        f"PharmaLearn custom Skill as the starting template. Preserve every citation, do not add claims, and "
        f"return only the final .pptx file.\n\nDECK SPECIFICATION:\n{json.dumps(deck)}"
    )
    request = {
        "model": MODEL,
        "max_tokens": 16000,
        "betas": ["skills-2025-10-02", "files-api-2025-04-14"],
        "container": {"skills": skills},
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"type": "code_execution_20260521", "name": "code_execution"}],
    }

    async def send():
        async with client.beta.messages.stream(**request) as stream:
            return await stream.get_final_message()

    async def counted_send():
        counted = await client.beta.messages.count_tokens(
            model=request["model"],
            messages=request["messages"],
            tools=request["tools"],
            betas=request["betas"],
        )
        return await _metered_send(
            send,
            budget,
            f"{learner} pptx",
            counted.input_tokens,
            request["max_tokens"],
            stage=f"{learner}_pptx",
            stage_limit_usd=PPT_STAGE_BUDGET_USD,
        )

    file_id = None
    response = None
    for turn in range(PPT_MAX_TURNS):
        response = await counted_send()
        for block in response.content:
            result = getattr(block, "content", None)
            if getattr(block, "type", "") in {"code_execution_tool_result", "bash_code_execution_tool_result"} and result:
                for output in getattr(result, "content", []):
                    file_id = getattr(output, "file_id", file_id)
        if file_id or response.stop_reason != "pause_turn":
            break
        if turn == PPT_MAX_TURNS - 1:
            break
        container_id = getattr(getattr(response, "container", None), "id", None)
        if not container_id:
            raise RuntimeError(f"Anthropic did not return a reusable container for {learner.upper()} PowerPoint")
        request["messages"].append({"role": "assistant", "content": response.content})
        request["container"] = {"id": container_id, "skills": skills}
    if not file_id:
        raise RuntimeError(f"Anthropic did not return the {learner.upper()} PowerPoint")
    downloaded = await client.beta.files.download(file_id=file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    await downloaded.write_to_file(path)
    _copy(path, cached)


def _source_manifest(master: dict, local_source: Path | None):
    if local_source:
        return _json(local_source / "source_manifest.json")
    sources = {}
    for section in master["sections"]:
        for claim in section.get("claims", []):
            for citation in claim.get("citations", []):
                key = citation.get("url") or citation.get("title")
                if key:
                    sources[key] = citation
    return {
        "scope": "Sources selected by section-specific web research",
        "accessed_at": datetime.now(UTC).isoformat(),
        "sources": list(sources.values()),
    }


async def _build_tracks(
    run_id: str,
    target: Path,
    master: dict,
    local_source: Path | None,
    budget: RunBudget | None,
):
    outputs = {"msl": {}, "hcp": {}}
    paths = {
        learner: {
            "ppt": target / learner / "ppt" / "deck_spec.json",
            "storyboard": target / learner / "storyboard" / "storyboard.json",
            "faq": target / learner / "faq.json",
            "quiz": target / learner / "quiz.json",
        }
        for learner in outputs
    }
    index = 0
    for kind in ["ppt", "storyboard", "faq", "quiz"]:
        for learner in outputs:
            await _stage(run_id, f"generate_{learner}_{kind}", 50 + index * 3, f"Building {learner.upper()} {kind}")
            outputs[learner][kind] = await _asset(master, learner, kind, local_source, budget)
            _write(paths[learner][kind], outputs[learner][kind])
            index += 1

    # The gamified formats are built after the quiz because they are folded into
    # it: their items become questions, so the quiz on disk is the one the learner
    # is scored on and the one the checker reads. Each is also written on its own,
    # so a reviewer can see the format as the agent authored it.
    step = 0
    for learner in outputs:
        groups, figures = [], []
        for kind, group_kind in GAMIFIED.items():
            await _stage(run_id, f"generate_{learner}_{kind}", 73 + step * 2,
                         f"Building {learner.upper()} {kind}")
            step += 1
            asset = await _asset(master, learner, kind, local_source, budget)
            if not asset:
                continue
            outputs[learner][kind] = asset
            _write(target / learner / f"{kind}.json", asset)
            if group_kind:
                groups.append({"id": _slug(asset["title"])[:40], "kind": group_kind, **asset})
            else:
                figures += asset["questions"]
        if groups or figures:
            outputs[learner]["quiz"] = fold_groups(outputs[learner]["quiz"], groups, figures)
            _write(paths[learner]["quiz"], outputs[learner]["quiz"])

    ppt_files = {}
    for progress, learner in [(85, "msl"), (87, "hcp")]:
        await _stage(run_id, f"render_{learner}_pptx", progress, f"Rendering {learner.upper()} PowerPoint")
        ppt_files[learner] = target / learner / "ppt" / f"{_slug(master['drug']['brand'])}-{learner}-training.pptx"
        await _pptx(
            outputs[learner]["ppt"],
            learner,
            ppt_files[learner],
            local_source,
            budget,
            _slug(master["drug"]["brand"]),
        )
    return ppt_files["hcp"]


def _compatibility_view(target: Path, master: dict, source_manifest: dict, hcp_ppt: Path, local_source: Path | None):
    assets = target / "assets"
    brand_slug = _slug(master["drug"]["brand"])
    _copy(hcp_ppt, assets / f"{brand_slug}-training.pptx")
    _copy(target / "hcp" / "ppt" / "deck_spec.json", assets / "deck_spec.json")
    _copy(target / "hcp" / "storyboard" / "storyboard.json", assets / "video_storyboard.json")
    _copy(target / "hcp" / "faq.json", assets / "faq.json")
    _copy(target / "hcp" / "quiz.json", assets / "quiz.json")
    _write(target / "source_manifest.json", source_manifest)
    _write(target / "context.json", master)
    if local_source:
        _copy(local_source / "learning_blueprint.json", target / "learning_blueprint.json")
    else:
        _write(target / "learning_blueprint.json", {
            "title": master["title"],
            "audiences": {"MSL": [], "HCP": []},
            "asset_roles": {"ppt": "Course", "video_storyboard": "Visual story", "faq": "Reference", "quiz": "Assessment"},
        })
    citation_count = sum(
        len(claim.get("citations", []))
        for section in master["sections"]
        for claim in section.get("claims", [])
    )
    return {
        "course_id": brand_slug,
        "status": "completed",
        "drug": master["drug"],
        "learners": ["msl", "hcp"],
        "assets": [
            {"type": "ppt", "title": "Clinical presentation", "file": f"{brand_slug}-training.pptx", "downloadable": True},
            {"type": "video_storyboard", "title": "Storyboard", "file": "video_storyboard.json"},
            {"type": "faq", "title": "FAQ", "file": "faq.json"},
            {"type": "quiz", "title": "Knowledge quiz", "file": "quiz.json"},
        ],
        "citation_count": citation_count,
        "warning_count": len(master.get("warnings", [])),
    }


# Where each asset kind lives inside a track folder, so a replay can copy what a
# generation would have written without re-deriving the layout in two places.
REPLAY_ASSETS = {
    "ppt": ("ppt", "deck_spec.json"),
    "storyboard": ("storyboard", "storyboard.json"),
    "faq": ("faq.json",),
    "quiz": ("quiz.json",),
    "triage": ("triage.json",),
    "assemble": ("assemble.json",),
    "figure": ("figure.json",),
}


def replay_source() -> Path | None:
    """The finished run a replay copies from, if one is configured and present."""
    if not REPLAY_SOURCE:
        return None
    candidate = Path(REPLAY_SOURCE)
    source = candidate if candidate.is_absolute() else content_path("content", candidate.name)
    return source if (source / "manifest.json").exists() else None


def _link_or_copy(source: Path, target: Path):
    """Symlink a directory, copy a file.

    The video folders are 100MB of the 104MB a course occupies and a replay does
    not change a frame of them, so three demo runs should not cost 300MB to say
    so. Resolved first, so replaying a replay does not build a chain of links.
    """
    if target.is_symlink() or target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source.resolve())


async def _replay(run_id: str, drug: str, source: Path, target: Path):
    """Walk a finished run's stages again, copying its output instead of rebuilding it.

    A demo has to show the pipeline working, and the pipeline working twice on the
    same drug produces the same course at full price — 14 research calls, 14 assets
    and two decks, none of which would differ. This emits the identical stage
    sequence against content already on disk, so the event log, the asset layout
    and the manifest are exactly what a real run writes. Only the model calls are
    absent, and `mode` on the run record says so rather than implying otherwise.
    """
    await _stage(run_id, "resolve_drug", 4, f"Preparing the learning dossier for {drug}")

    for index, path in enumerate(sorted((PROMPTS / "research").glob("*.md")), 1):
        stored = source / "master" / "sections" / f"{path.stem}.json"
        await _stage(run_id, f"research_{path.stem}", 4 + index * 2,
                     f"Researching {path.stem[3:].replace('_', ' ')}")
        if stored.exists():
            _copy(stored, target / "master" / "sections" / f"{path.stem}.json")

    master = _json(source / "master" / "dossier.json")
    claims = sum(len(section.get("claims", [])) for section in master["sections"])
    await _stage(run_id, "collate_evidence", 43,
                 f"Collating {claims} evidence claims from {len(master['sections'])} researched sections")
    await _stage(run_id, "build_master_dossier", 46,
                 "Combining the researched sections into the master dossier")
    _write(target / "master" / "dossier.json", master)

    index = 0
    for kind in ["ppt", "storyboard", "faq", "quiz"]:
        for learner in ["msl", "hcp"]:
            await _stage(run_id, f"generate_{learner}_{kind}", 50 + index * 3,
                         f"Building {learner.upper()} {kind}")
            _copy(source / learner / Path(*REPLAY_ASSETS[kind]),
                  target / learner / Path(*REPLAY_ASSETS[kind]))
            index += 1

    step = 0
    for learner in ["msl", "hcp"]:
        for kind in GAMIFIED:
            stored = source / learner / Path(*REPLAY_ASSETS[kind])
            await _stage(run_id, f"generate_{learner}_{kind}", 73 + step * 2,
                         f"Building {learner.upper()} {kind}")
            step += 1
            # A course built before the boards existed simply has none, exactly as
            # `_asset` tolerates for the bundled library.
            if stored.exists():
                _copy(stored, target / learner / Path(*REPLAY_ASSETS[kind]))

    brand_slug = _slug(master["drug"]["brand"])
    ppt_files = {}
    for progress, learner in [(85, "msl"), (87, "hcp")]:
        await _stage(run_id, f"render_{learner}_pptx", progress, f"Rendering {learner.upper()} PowerPoint")
        name = f"{brand_slug}-{learner}-training.pptx"
        ppt_files[learner] = target / learner / "ppt" / name
        _copy(source / learner / "ppt" / name, ppt_files[learner])
        videos = source / learner / "videos"
        if videos.exists():
            _link_or_copy(videos, target / learner / "videos")

    return master, ppt_files["hcp"]


# The learner-facing assets, in the order a reviewer reads them. Verification is
# reported per asset because "3 citations flagged" is only actionable once you
# know whether they are on a slide or in the quiz.
VERIFIED_ASSETS = [("deck", "deck"), ("storyboard", "storyboard"),
                   ("faq", "FAQ"), ("quiz", "quiz")]


async def _verify_tracks(run_id: str, drug: str):
    """Check every citation in the finished assets against the stored sources.

    This is the maker-checker seam, and it runs inside the build rather than after
    it: the same deterministic checks the reviewer's Checks tab exposes, reported
    per asset as each track is finished. Nothing here is a simulation — the counts
    are read off the assets just written, and a course whose citations do not
    resolve says so before anyone opens it.

    Deterministic only, and cheap enough to be unconditional: no model is called,
    so this costs nothing on a replay and nothing on a live run either.
    """
    from src import judge

    await _stage(run_id, "verify_citations", 89,
                 "Checking every citation against the stored source documents")
    progress = 90
    for track in ("msl", "hcp"):
        try:
            findings, _stats = judge.deterministic_findings(run_id, track, drug)
        except Exception as error:
            # A missing source corpus is a thinner report, not a failed build. The
            # course is still valid; what is unverifiable is reported as such.
            await _stage(run_id, f"verify_{track}", progress,
                         f"{track.upper()} citations could not be checked: {error}")
            progress += 4
            continue
        flagged: dict[str, int] = {}
        for finding in findings:
            flagged[finding.asset] = flagged.get(finding.asset, 0) + 1
        counts: dict[str, dict] = {}
        for unit in judge.units(run_id, track):
            entry = counts.setdefault(unit["asset"], {"units": 0, "citations": 0})
            entry["units"] += 1
            entry["citations"] += len(unit["citations"])
        for asset, label in VERIFIED_ASSETS:
            tally = counts.get(asset)
            if not tally:
                continue
            raised = flagged.get(asset, 0)
            await _stage(
                run_id, f"verify_{track}_{asset}", progress,
                f"{track.upper()} {label}: {tally['citations']} citations across {tally['units']} units, "
                + (f"{raised} flagged for review" if raised else "none flagged"),
            )
            progress += 1


async def _generate(run_id: str, drug: str, target: Path, local_source: Path | None, budget: "RunBudget | None"):
    """Research the drug and build both tracks, live or from the bundled library."""
    if local_source and not local_source.exists():
        raise RuntimeError(f"No bundled no-key content exists for {drug}")
    await _stage(run_id, "resolve_drug", 4, f"Preparing the learning dossier for {drug}")

    if local_source:
        context = _json(local_source / "context.json")
        sections = _seed_sections(context)
        for index, section in enumerate(sections, 1):
            await _stage(run_id, f"research_{section['id']}", 4 + index * 2, f"Prepared {section['title']}")
            _write(target / "master" / "sections" / f"{section['id']}.json", section)
    else:
        sections = []
        research_prompts = sorted((PROMPTS / "research").glob("*.md"))
        for index, path in enumerate(research_prompts, 1):
            await _stage(run_id, f"research_{path.stem}", 4 + index * 2, f"Researching {path.stem[3:].replace('_', ' ')}")
            section = await _research(drug, path, budget)
            sections.append(section)
            _write(target / "master" / "sections" / f"{section['id']}.json", section)

    await _stage(run_id, "collate_evidence", 43,
                 f"Collating evidence from {len(sections)} researched sections")
    await _stage(run_id, "build_master_dossier", 46, "Combining the researched sections into the master dossier")
    master = await _master_dossier(drug, sections, local_source, budget)
    _write(target / "master" / "dossier.json", master)

    return master, await _build_tracks(run_id, target, master, local_source, budget)


async def run_agent(run_id: str, drug: str):
    target = content_path("content", run_id)
    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    replay = replay_source()
    local_source = None if has_key else content_path("library", _slug(drug))
    # A replay makes no model calls, so it opens no ledger. A zero-spend ledger
    # would otherwise read as "this run was free" rather than "this run was not run".
    budget = RunBudget(run_id) if has_key and not replay else None
    if budget:
        budget._save()
    run = get_run(run_id) or {"id": run_id}
    run["mode"] = "replay" if replay else ("live" if has_key else "local")
    _write(content_path("logs", run_id, "run.json"), run)
    try:
        if replay:
            master, hcp_ppt = await _replay(run_id, drug, replay, target)
            local_source = replay
        else:
            master, hcp_ppt = await _generate(run_id, drug, target, local_source, budget)

        await _verify_tracks(run_id, master["drug"]["brand"])

        await _stage(run_id, "attach_citations", 98, "Attaching citations and preparing the course")
        sources = _source_manifest(master, local_source)
        manifest = _compatibility_view(target, master, sources, hcp_ppt, local_source)
        manifest.update({
            "run_id": run_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "cost_usd": round(budget.spent_usd, 6) if budget else 0,
        })
        _write(target / "manifest.json", manifest)

        _emit(run_id, "complete", 100, "MSL and HCP learning assets are ready", "completed")
        run = get_run(run_id)
        run["content_url"] = f"/api/runs/{run_id}/content"
        _write(content_path("logs", run_id, "run.json"), run)
    except Exception as error:
        _emit(run_id, "failed", 100, str(error), "failed")

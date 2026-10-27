"""Course assistant: answers learner questions from the run's own dossier.

Retrieval is always local, so the chatbot works without an API key and can only
speak from claims the agent already collected and cited. When a key is present
the same retrieved claims are handed to the model, which must answer using only
that evidence; spend lands in the run's existing usage ledger.
"""

import math
import os
import re
from datetime import date
from pathlib import Path

from src.agent import (
    AssetCitation,
    RunBudget,
    StrictModel,
    _cache_path,
    _json,
    _message_json,
    _prompt,
    content_path,
)

CHAT_MAX_TOKENS = 1_500
CHAT_STAGE_BUDGET_USD = float(os.getenv("PHARMALEARN_CHAT_BUDGET_USD", "0.50"))
STOPWORDS = {
    "the", "and", "for", "with", "what", "when", "which", "does", "did", "how", "why", "are", "was",
    "this", "that", "from", "have", "has", "can", "could", "should", "would", "about", "into", "than",
    "there", "their", "they", "you", "your", "its", "it's", "any", "all", "who", "whom", "get", "got",
    "tell", "explain", "describe", "give", "please", "patient", "patients",
}


class ChatAnswer(StrictModel):
    answer: str
    citations: list[AssetCitation]


def _terms(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9\-']*", text.lower())
    return [word for word in words if len(word) > 2 and word not in STOPWORDS]


def _dossier(run_id: str) -> dict | None:
    for relative in [("master", "dossier.json"), ("context.json",)]:
        path = content_path("content", Path(run_id).name, *relative)
        if path.exists():
            return _json(path)
    return None


def claims(run_id: str) -> list[dict]:
    dossier = _dossier(run_id)
    if not dossier:
        return []
    return [
        {
            "section_id": section["id"],
            "section_title": section["title"],
            "text": claim["text"],
            "evidence_type": claim.get("evidence_type", ""),
            "citations": claim.get("citations", []),
        }
        for section in dossier.get("sections", [])
        for claim in section.get("claims", [])
    ]


def _norm(value: str) -> str:
    return " ".join((value or "").split()).strip().lower()


def evidence(run_id: str, title: str = "", locator: str = "", url: str = "") -> dict | None:
    """Recover the verbatim supporting text behind a citation shown on an asset.

    Assets carry only title/url/locator, but the dossier keeps the `supporting_text`
    the claim was actually built from. Joining them back is what turns a citation
    chip into evidence a reviewer can check.
    """
    want_title, want_locator, want_url = _norm(title), _norm(locator), _norm(url)
    if not (want_title or want_url):
        return None

    pool = claims(run_id)
    best: tuple[int, dict, dict] | None = None
    from_source = []
    for claim in pool:
        for citation in claim["citations"]:
            has_title, has_locator, has_url = (
                _norm(citation.get("title", "")),
                _norm(citation.get("locator", "")),
                _norm(citation.get("url", "")),
            )
            same_source = (want_title and want_title == has_title) or (want_url and want_url == has_url)
            if not same_source:
                continue
            from_source.append(claim)
            score = 2 + (1 if want_locator and want_locator == has_locator else 0)
            score += 1 if citation.get("supporting_text") else 0
            if not best or score > best[0]:
                best = (score, claim, citation)

    if not best:
        return None
    _, claim, citation = best
    return {
        "citation": {
            "title": citation.get("title", ""),
            "url": citation.get("url", ""),
            "locator": citation.get("locator", ""),
            "supporting_text": citation.get("supporting_text", ""),
        },
        "claim": {
            "text": claim["text"],
            "evidence_type": claim["evidence_type"],
            "section_id": claim["section_id"],
            "section_title": claim["section_title"],
        },
        "related": [
            {"text": other["text"], "section_title": other["section_title"]}
            for other in from_source if other["text"] != claim["text"]
        ][:4],
        "supports_claims": len({other["text"] for other in from_source}),
    }


def search(run_id: str, question: str, limit: int = 5) -> list[dict]:
    """Rank the run's claims against a question by inverse-document-frequency overlap."""
    pool = claims(run_id)
    query = set(_terms(question))
    if not pool or not query:
        return []
    documents = [set(_terms(f"{claim['section_title']} {claim['text']}")) for claim in pool]
    frequency = {term: sum(term in document for document in documents) for term in query}
    scored = []
    for claim, document in zip(pool, documents, strict=True):
        score = sum(
            math.log(len(pool) / frequency[term])
            for term in query
            if term in document and frequency[term]
        )
        if score > 0:
            # Normalize by length so a long claim that mentions the term in passing
            # does not outrank a short one that is actually about it.
            scored.append((score / math.sqrt(len(document)), claim))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [claim for _, claim in scored[:limit]]


def _citations(matches: list[dict], limit: int = 6) -> list[dict]:
    seen, citations = set(), []
    for match in matches:
        for citation in match["citations"]:
            key = (citation.get("title"), citation.get("locator"))
            if key in seen:
                continue
            seen.add(key)
            citations.append({
                "title": citation.get("title", ""),
                "url": citation.get("url", ""),
                "locator": citation.get("locator", ""),
            })
    return citations[:limit]


def _local_answer(question: str, matches: list[dict]) -> dict:
    if not matches:
        return {
            "answer": (
                "The course dossier does not cover that. Ask about the disease context, mechanism, "
                "clinical evidence, dosing, safety monitoring, or patient support for this drug, or "
                "escalate the question to Medical Information."
            ),
            "citations": [],
            "evidence": [],
            "mode": "retrieval",
        }
    lead = "The strongest evidence in this course's dossier:"
    body = "\n\n".join(f"• {match['text']}" for match in matches[:3])
    return {
        "answer": f"{lead}\n\n{body}",
        "citations": _citations(matches[:3]),
        "evidence": matches,
        "mode": "retrieval",
    }


# Starter questions offered per surface. `record` ones are answered from the
# programme's own data; the rest must find evidence in the dossier before they
# are shown — see `starters`.
CONTEXTS: dict[str, list[tuple[str, str]]] = {
    "material": [
        ("dossier", "What are the unmet needs in this disease?"),
        ("dossier", "What did the phase 3 trials show?"),
        ("dossier", "What is the mechanism of action?"),
        ("dossier", "How is neutropenia monitored and managed?"),
        # "How does this compare with the alternatives?" reads well and retrieves
        # nothing — neither word appears in the claims. The grounding gate caught
        # it, which is the gate earning its place rather than a phrasing quibble.
        ("dossier", "What are the current standards of care?"),
    ],
    "evidence": [
        ("dossier", "Which sources support the approved indication?"),
        ("dossier", "What evidence is there for overall survival?"),
        ("record", "What did the checker find, and what is still open?"),
        ("dossier", "What does the label say about dose modification?"),
    ],
    "review": [
        ("record", "What is still blocking publication?"),
        ("record", "Who has approved this version?"),
        ("dossier", "What evidence sits behind the efficacy claims?"),
        ("dossier", "Where does the label describe the approved population?"),
    ],
    "programme": [
        ("record", "When does this training programme open and close?"),
        ("record", "How many trainees are assigned, and how many are certified?"),
        ("record", "Who approved this version, and were there any overrides?"),
        ("dossier", "What is this course teaching the field team?"),
    ],
    "learner": [
        ("record", "When is this training due?"),
        ("dossier", "What are the unmet needs in this disease?"),
        ("dossier", "What are the most common adverse reactions?"),
        ("dossier", "What should I tell a patient about taking this drug?"),
    ],
}
DEFAULT_CONTEXT = "material"


def starters(run_id: str, context: str = DEFAULT_CONTEXT) -> list[dict]:
    """Suggested questions for the surface the reader is on.

    Every suggestion is checked before it is offered. A dossier question is shown
    only if retrieval actually finds something for it, and a record question only
    if the record holds the answer. Suggesting a question the assistant then
    cannot answer is worse than suggesting nothing — it is the demo failing in
    the one place we are claiming to be well grounded, and on a different drug
    whose dossier has no market section, half of these would do exactly that.
    """
    offered = []
    for kind, question in CONTEXTS.get(context) or CONTEXTS[DEFAULT_CONTEXT]:
        answerable = bool(platform_answer(run_id, question)) if kind == "record" \
            else bool(search(run_id, question, limit=1))
        if answerable:
            offered.append({"question": question, "kind": kind})
    return offered


SCHEDULE = re.compile(r"\b(launch|start|open|begin|due|deadline|schedul|when|live|window)\w*", re.I)
COHORT = re.compile(r"\b(who|assign|trainee|learner|cohort|certif|complet|progress|uplift|score)\w*", re.I)
GOVERNANCE = re.compile(r"\b(sign.?off|review|comment|version|publish|checker|finding|block|override)\w*", re.I)

# A question is about the programme only if it names something the platform owns.
# Without this, "when did the phase 3 trial start" reads as a schedule question and
# gets answered with training dates. Deliberately excludes bare "approved", which
# in this domain far more often means the drug than a sign-off.
PLATFORM = re.compile(
    r"\b(programme|program|training|course|cycle|publication|publish\w*|version|cohort|trainee\w*"
    r"|learner\w*|assign\w*|certif\w*|sign.?off|checker|reviewer|comment\w*|override\w*|blocking"
    r"|deadline|module)\b", re.I)


def _day_phrase(days: int | None) -> str:
    if days is None:
        return ""
    if days == 0:
        return " (today)"
    # The direction is carried by the word, so the sign must not also be printed:
    # a deadline one day past read "-1 day ago".
    size = abs(days)
    return f" ({size} day{'' if size == 1 else 's'} {'from now' if days > 0 else 'ago'})"


def platform_answer(run_id: str, question: str, user_id: str = "") -> dict | None:
    """Answer from the programme's own records, or return None to fall through.

    Schedules, cohorts and sign-offs are facts the platform stores, not claims in
    a dossier — retrieval over the dossier cannot answer "when does this open"
    and the model would be guessing. So these are read straight off the record
    and returned verbatim, with no model in the path at all.
    """
    from src import learning, programmes

    if not PLATFORM.search(question):
        return None
    record = learning.course(run_id)
    publication = record.get("publication")
    lines: list[str] = []

    mine = user_id and publication and user_id in publication["assignees"]

    if SCHEDULE.search(question):
        if not publication:
            lines.append("This course has not been published yet, so it has no schedule. "
                         f"It is at version {record['version']} and its review status is {record['status']}.")
        elif mine:
            # Their own standing, which is what "is this due" means to a trainee.
            # The cohort's state is a different question and often a different word:
            # a cycle whose window has closed is "completed" while the person who
            # never finished it is overdue.
            summary = learning.summarize(learning.progress(run_id, user_id))
            state = learning.assignment_state(publication, summary)
            days = (date.fromisoformat(publication["due_on"]) - date.today()).days
            lines.append(
                f"It runs {publication['starts_on']} to {publication['due_on']}"
                f"{_day_phrase(days)}. For you it is {state}"
                + (f", and you are {summary['percent']}% through the material." if state != "completed"
                   else ", and your certificate is on record."))
        else:
            state = programmes.programme(run_id) or {}
            lines.append(
                f"It runs {publication['starts_on']} to {publication['due_on']}"
                f"{_day_phrase(state.get('days_remaining'))}, and is currently {state.get('state', 'scheduled')}.")
    if COHORT.search(question) and publication and not mine:
        group = learning.cohort(run_id)
        uplift = group.get("average_uplift")
        lines.append(
            f"{group['assigned']} trainee(s) assigned, {group['started']} started, "
            f"{group['certified']} certified"
            + (f", average uplift +{uplift} points." if uplift is not None else "."))
    if GOVERNANCE.search(question):
        ready = learning.readiness(record)
        approvals = ", ".join(ready["approved_by"]) or "nobody yet"
        lines.append(
            f"Version {record['version']}, approved by {approvals}. "
            f"{ready['open_comments']} open review comment(s), {ready['open_blocking']} blocking"
            + (f", {ready['overrides']} override(s) on the record." if ready["overrides"] else "."))

    if not lines:
        return None
    return {"answer": "\n\n".join(lines), "citations": [], "evidence": [], "mode": "record"}


async def answer(run_id: str, question: str, learner: str = "hcp", user_id: str = "") -> dict:
    """Answer a course question, preferring the model when a key and budget allow."""
    # Questions about the programme itself are settled by the record, not by
    # searching prose for something that was never written down.
    from_record = platform_answer(run_id, question, user_id)
    if from_record:
        return from_record

    matches = search(run_id, question)
    local = _local_answer(question, matches)
    if not os.getenv("ANTHROPIC_API_KEY") or not matches:
        return local

    evidence = "\n\n".join(
        f"[{index}] SECTION: {match['section_title']}\nCLAIM: {match['text']}\n"
        + "\n".join(f"SOURCE: {cite.get('title', '')} | {cite.get('locator', '')} | {cite.get('url', '')}"
                    for cite in match["citations"])
        for index, match in enumerate(matches, 1)
    )
    system = "\n\n".join([
        _prompt("common", "citations.md"),
        _prompt("learners", f"{learner if learner in {'msl', 'hcp'} else 'hcp'}.md"),
        "You answer questions from a field learner about a course they are studying. Use only the "
        "numbered evidence below. If the evidence does not answer the question, say so and suggest "
        "escalating to Medical Information. Keep the answer under 120 words and cite the sources you "
        "used, copying their title, url and locator exactly.",
        f"EVIDENCE:\n{evidence}",
    ])
    try:
        budget = RunBudget(Path(run_id).name)
        value = await _message_json(
            system,
            question,
            f"chat {learner}",
            budget,
            ChatAnswer,
            max_tokens=CHAT_MAX_TOKENS,
            # Keyed on the evidence rather than the run: this answer is a function of
            # the question and the claims retrieved for it, and nothing else. Keying
            # on run_id meant a course regenerated from identical content paid again
            # to be told the same thing, and gave a differently worded answer each
            # time — which is wrong twice over for a question about fixed evidence.
            cache_path=_cache_path("chat", learner, question.strip().lower(), evidence),
            stage="chat",
            stage_limit_usd=CHAT_STAGE_BUDGET_USD,
        )
    except Exception:
        return local
    return {**value, "evidence": matches, "mode": "model"}

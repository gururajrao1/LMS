"""Course assistant: answers learner questions from the run's own dossier.

Retrieval is always local, so the chatbot works without an API key and can only
speak from claims the agent already collected and cited. When a key is present
the same retrieved claims are handed to the model, which must answer using only
that evidence; spend lands in the run's existing usage ledger.
"""

import difflib
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
    for fixed in _correct_terms(run_id, question).values():
        query.add(fixed)
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


def rerank_by_support(run_id: str, question: str, matches: list[dict]) -> list[dict]:
    """Order matches by verifiability, then by question coverage.

    A SelfCite-style necessity/sufficiency proxy built from what is on hand:
    necessity favours matches carrying rare question terms (terms the answer
    cannot be built without), sufficiency favours matches covering more of
    the question, and anything with a citation outranks anything without —
    an uncited match can still be relevant, but it must never be quoted as
    evidence ahead of a cited one. Stable, so pass-one order breaks ties.
    """
    pool = claims(run_id)
    size = len(pool) or 1
    frequency: dict[str, int] = {}
    for claim in pool:
        for term in set(_terms(f"{claim['section_title']} {claim['text']}")):
            frequency[term] = frequency.get(term, 0) + 1
    query = set(_terms(question))
    for fixed in _correct_terms(run_id, question).values():
        query.add(fixed)

    def _score(match: dict) -> tuple:
        document = set(_terms(f"{match['section_title']} {match['text']}"))
        necessity = sum(
            math.log(size / frequency[term])
            for term in query
            if term in document and frequency.get(term)
        )
        sufficiency = (
            sum(1 for term in query if term in document) / len(query) if query else 0.0
        )
        return (bool(match.get("citations")), necessity, sufficiency)

    return sorted(matches, key=_score, reverse=True)


def expanded_search(run_id: str, question: str, limit: int = 5) -> list[dict]:
    """Two-pass retrieval with dedup: the first pass asks the question, the
    second pass re-asks it in the vocabulary of the best first-pass claims.

    A claim sharing no words with the question is invisible to a single
    overlap pass even when it is the answer's neighbour (MedCite's
    re-retrieval finding). Expanding with each top claim's own rare terms
    pulls those neighbours in; dedup keeps the merge honest, and the
    support rerank puts verifiable coverage first.
    """
    first = search(run_id, question, limit=limit)
    seen = {claim["text"] for claim in first}
    merged = list(first)
    question_terms = set(_terms(question))
    for claim in first[:3]:
        extra = sorted(set(_terms(claim["text"])) - question_terms)[:6]
        if not extra:
            continue
        for hit in search(run_id, f"{question} {' '.join(extra)}", limit=limit):
            if hit["text"] not in seen:
                seen.add(hit["text"])
                merged.append(hit)
    return rerank_by_support(run_id, question, merged)[:limit]


def _well_supported(matches: list[dict], need: int = 3) -> bool:
    """Adaptive gate: when every top match carries a citation, the local
    answer is served directly and no model is billed.

    Retrieval already found checkable evidence, so a model rewrite can only
    reword it — at a cost, and with a chance to drift from the quotes. Weak
    evidence still goes to the model, which sees the same matches.
    """
    top = matches[:need]
    return bool(top) and all(match.get("citations") for match in top)


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
    if not any(match.get("citations") for match in matches[:3]):
        return {
            "answer": (
                "I can't verify an answer to that from this course's dossier — the closest "
                "material has no cited evidence behind it, and I won't quote uncited text "
                "as if it were sourced. Please escalate the question to Medical Information."
            ),
            "citations": [],
            "evidence": [],
            "mode": "refused",
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
    "assessment": [
        ("record", "When is this training due?"),
        ("dossier", "What did the phase 3 trials show?"),
        ("dossier", "What are the unmet needs in this disease?"),
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


def _correct_terms(run_id: str, question: str) -> dict[str, str]:
    """Map misspelled query terms to their closest dossier term.

    A typo reads as the word it plainly meant, not as zero evidence — so the
    retrieval below searches the corrected vocabulary too. Only terms the
    dossier never uses are candidates; exact terms pass through untouched.
    """
    query = set(_terms(question))
    if not query:
        return {}
    vocabulary = set()
    for claim in claims(run_id):
        vocabulary.update(_terms(f"{claim['section_title']} {claim['text']}"))
    corrections = {}
    for term in query:
        if term not in vocabulary:
            close = difflib.get_close_matches(term, vocabulary, n=1, cutoff=0.8)
            if close and close[0] != term:
                corrections[term] = close[0]
    return corrections


ASSESSMENT_RULES = re.compile(
    r"\b(what happens if i|if i fail|can i (retake|resubmit|try)|do i (need|have to)|"
    r"how many (attempts|tries|times can i)|is there a (pass mark|limit)|what is the pass|"
    r"what('s| is) the pass|will i (have to|need to)|do i get another|second (chance|attempt))\b"
    r"|\bpass(ing)? (mark|score|grade|criteria)\b|\bretak\w+|\bresubmit\w*|\bresit\w+",
    re.I)


def _assessment_rules(run_id: str, question: str, learner: str = "hcp") -> dict | None:
    """How grading works here, read off the recorded quiz — never the dossier.

    The baseline maps what you know and is never graded; the final needs its
    passing score, attempts are unlimited, and the latest attempt counts.
    """
    if not ASSESSMENT_RULES.search(question):
        return None
    track = learner if learner in {"msl", "hcp"} else "hcp"
    path = content_path("content", Path(run_id).name, track, "quiz.json")
    if not path.exists():
        return None
    quiz = _json(path)
    # `passing_score` is a percentage by contract, but generators sometimes
    # write a raw count ("8 correct" of 12). Same conversion the grader uses:
    # a value no larger than the question count is a count, not a percent.
    passing = int(quiz.get("passing_score", 75))
    total = len(quiz.get("questions", []))
    if total and passing <= total:
        passing = round(100 * passing / total)
    return {
        "answer": (
            "The baseline isn't graded — it maps what you know before you start, so answer honestly. "
            f"The final needs {passing}% to pass and issue your certificate. "
            "Attempts are unlimited and your latest attempt counts, so if you fall short, "
            "revise the material and resubmit."
        ),
        "citations": [],
        "evidence": [],
        "mode": "record",
    }


def _noted(result: dict, corrections: dict[str, str]) -> dict:
    if not corrections:
        return result
    reading = "I read " + ", ".join(f"'{wrong}' as '{right}'" for wrong, right in sorted(corrections.items())) + ". "
    return {**result, "answer": reading + result["answer"]}


async def answer(run_id: str, question: str, learner: str = "hcp", user_id: str = "") -> dict:
    """Answer a course question, preferring the model when a key and budget allow."""
    # Questions about the programme itself are settled by the record, not by
    # searching prose for something that was never written down.
    from_record = platform_answer(run_id, question, user_id)
    if from_record:
        return from_record

    rules = _assessment_rules(run_id, question, learner)
    if rules:
        return rules
    matches = expanded_search(run_id, question)
    corrections = _correct_terms(run_id, question)
    local = _noted(_local_answer(question, matches), corrections)
    if not os.getenv("ANTHROPIC_API_KEY") or not matches:
        return local
    if local.get("mode") == "refused" or _well_supported(matches):
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
    return _noted({**value, "evidence": matches, "mode": "model"}, corrections)


def _finding_state(evidence: dict) -> tuple[str, str]:
    """One verdict line plus the close-out line for a machine finding."""
    check = evidence.get("check", "")
    cites = evidence.get("citations") or []
    untraced = [c for c in cites if not c.get("traceable")]
    unheld = evidence.get("unheld") or []
    if check == "untraceable":
        names = "; ".join(_cite_name(c) for c in untraced) or "the citation"
        return (
            f"No recorded evidence sits behind {names}, so it can neither support "
            "nor contradict the wording — the citation matches nothing collected "
            "during research.",
            "To close it: record a verbatim excerpt from the cited document, repoint "
            "the cite at a held source, or dismiss with a reason (and an override "
            "reason if the check still fails, which stands as your sign-off).",
        )
    if check == "quote_not_found":
        doc = (evidence.get("source") or {}).get("title", "the held document")
        return (
            f"No — the recorded quote is absent from {doc}, so it does not support "
            "the wording as it stands.",
            "To close it: fix the recorded quote to the document's actual passage, "
            "or dismiss with a reason (and an override reason if the check still fails).",
        )
    if check == "quote_not_verbatim":
        percent = evidence.get("match_percent")
        missing = [s["text"] for s in evidence.get("spans", []) if not s.get("present")]
        detail = (" The struck-through spans are the words missing from the document: "
                  + "; ".join(missing[:3])) if missing else ""
        return (
            f"Partly — {percent}% of the recorded quote is verbatim in the held document."
            f"{detail}",
            "To close it: correct the quote to the document's exact wording, or dismiss "
            "with a reason (and an override reason if the check still fails).",
        )
    return (
        "Yes — the recorded passage verifies against the held document.",
        "Nothing to close here unless the wording itself needs a human edit.",
    )


def _cite_name(citation: dict) -> str:
    title = (citation.get("title") or "").strip() or "an untitled citation"
    locator = (citation.get("locator") or "").strip()
    return f"{title} ({locator})" if locator else title


async def about_finding(run_id: str, finding_id: str, question: str, learner: str = "hcp") -> dict:
    """Answer a question about one machine finding from the finding itself.

    The review surface already computed everything the question could be about —
    which check fired, what was recorded, what matches and what is missing — so
    this never searches the dossier for keywords. Without a model key it answers
    from that state directly; with one, the same state is the model's only context.
    """
    from src import judge

    evidence = judge.evidence_for(run_id, {"finding_id": finding_id, "id": ""})
    if not evidence:
        return await answer(run_id, question, learner)

    verdict, close = _finding_state(evidence)
    asked = (question or "").strip().lower()
    if any(word in asked for word in ("approve", "override", "dismiss", "publish", "sign")):
        head = ("To approve despite the block: dismiss the comment with your reason; "
                "if the checker challenges it, record an override reason — that stands "
                "as your sign-off, the comment leaves the open queue, and sign-off plus "
                "zero open blocking unblocks publication.")
    elif any(word in asked for word in ("support", "wording", "evidence behind", "justify")):
        head = verdict
    else:
        head = f"{verdict} {close}"
        return {"answer": head, "citations": [], "evidence": evidence, "mode": "finding"}

    if any(word in asked for word in ("approve", "override", "dismiss", "publish", "sign")):
        body = f"{head} Current state: {verdict}"
    else:
        body = f"{head} {close}"
    local = {"answer": body, "citations": [], "evidence": evidence, "mode": "finding"}
    if not os.getenv("ANTHROPIC_API_KEY"):
        return local

    state = "\n".join([
        f"CHECK: {evidence.get('check')} ({evidence.get('severity')})",
        f"REFERENCE: {evidence.get('reference')}",
        f"CLAIM (as written): {evidence.get('claim')}",
        f"RECORDED QUOTE: {evidence.get('quote') or '(none)'}",
        f"MATCH: {evidence.get('match_percent')}",
        "CITATIONS:",
        *[f"- {c.get('title')} | {c.get('locator')} | {c.get('url')} "
          f"(traceable={c.get('traceable')}, held={c.get('held')})"
          for c in evidence.get("citations", [])],
        f"UNHELD: {', '.join(evidence.get('unheld', [])) or '(none)'}",
    ])
    system = "\n\n".join([
        "Answer a reviewer's question about one automated check finding. Use only the "
        "finding state below — never dossier search results. Say plainly whether the "
        "recorded evidence supports the wording, name the gap, and say what closes it "
        "(record a verbatim excerpt, repoint the cite, or dismiss with an override "
        "reason). Keep the answer under 120 words.",
        f"FINDING STATE:\n{state}",
        f"REVIEWER QUESTION: {question}",
    ])
    try:
        value = await _message_json(
            system, question, f"chat finding {learner}", RunBudget(Path(run_id).name),
            ChatAnswer, max_tokens=CHAT_MAX_TOKENS,
            cache_path=_cache_path("chat-finding", learner, finding_id, question.strip().lower()),
            stage="chat", stage_limit_usd=CHAT_STAGE_BUDGET_USD,
        )
    except Exception:
        return local
    return {**value, "evidence": evidence, "mode": "model-finding"}

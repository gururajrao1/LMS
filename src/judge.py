"""Automated quality checks on generated assets, before a human reviewer sees them.

The point is not to score content out of five. It is to answer questions that have
a checkable answer, so a finding can be shown rather than asserted:

  * Does the quoted supporting text actually appear in the source document?
  * Does every factual unit trace back to a collected claim?
  * Does the asset say more than the evidence behind it supports?
  * Does a unit rest only on manufacturer-hosted or promotional pages?
  * Does it make a comparative claim without head-to-head evidence?

Everything except the overreach check is deterministic and runs without an API
key. Coverage is reported honestly: a citation whose source we do not hold full
text for is recorded as *unverifiable*, never as verified.
"""

import os
import re
from datetime import UTC, datetime
from hashlib import sha1
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from src.agent import (
    RunBudget,
    _write,
    StrictModel,
    _cache_path,
    _json,
    _slug,
    content_path,
)

JUDGE_MAX_TOKENS = 1200
JUDGE_STAGE_BUDGET_USD = float(os.getenv("PHARMALEARN_JUDGE_BUDGET_USD", "2.00"))
MIN_QUOTE_FRAGMENT = 40

# Manufacturer-hosted and promotional properties. Not disallowed — the label and
# medical-information pages live here — but a claim resting *only* on them is a
# finding a medical reviewer would want to make deliberately.
PROMOTIONAL = {"pfizer.com", "pfizerpro.com", "ibrance.com", "pfizermedical.com", "labeling.pfizer.com"}
AGGREGATORS = {"drugs.com", "fda.report", "rxlist.com", "medscape.com"}

# Only explicit superiority language. "versus letrozole" and "compared with placebo"
# are how trials are correctly described, and flagging them buries the real signal.
COMPARATIVE = re.compile(
    r"\b(superior to|better than|more effective than|outperform\w*|best[- ]in[- ]class|"
    r"preferred over|first[- ]line choice over|the most effective)\b", re.I)

# Title, objective and agenda slides carry no factual assertion, so absence of a
# citation is correct rather than a finding.
FRONT_MATTER = re.compile(r"\b(welcome|learning objectives|agenda|introduction|contents|"
                          r"thank you|questions|closing|summary of this training)\b", re.I)

# Asset language that asserts causation or certainty. Compared against the hedging
# in the source text to spot strength drift.
STRONG = re.compile(r"\b(prevents?|eliminat\w+|cures?|guarantees?|ensures?|reverses?|proven to|"
                    r"significantly reduces?|always|never|all patients)\b", re.I)
HEDGED = re.compile(r"\b(associated with|suggests?|may|might|could|observed|reported|trend\w*|"
                    r"numerically|not statistically significant|no significant)\b", re.I)

# The depth floor. This audience works in the therapeutic area, so an efficacy
# effect quoted without its precision is not a simplification — it is the number
# without the part that says how much to believe it. One checkable facet of depth,
# not the whole of it: whether the writing is *good* stays a reviewer's judgement.
EFFECT = re.compile(r"\bmedian (?:pfs|os|progression-free survival|overall survival)\b|"
                    r"\bprogression-free survival of\b|\bhazard ratio\b|\bhr\s*[=:]|"
                    r"\b\d+(?:\.\d+)?\s*months?\s+(?:vs\.?|versus|compared)", re.I)
PRECISION = re.compile(r"\b95%\s*ci\b|\bconfidence interval\b|\bci[:,]?\s*0?\.\d+|"
                       r"\bp\s*[=<]\s*0?\.\d+|\brange\b", re.I)


class JudgeVerdict(StrictModel):
    verdict: Literal["supported", "needs_context", "overreach", "unsupported"]
    severity: Literal["blocking", "major", "minor"]
    explanation: str
    suggested_rewrite: str


@dataclass
class Finding:
    unit_id: str
    asset: str
    reference: str
    check: str
    severity: str
    message: str
    asset_text: str = ""
    source_text: str = ""
    suggested_rewrite: str = ""
    citations: list[dict] = field(default_factory=list)


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9%.\s-]", " ", (text or "").lower()).split())


def _domain(url: str) -> str:
    match = re.match(r"https?://([^/]+)", url or "")
    return match.group(1).lower().removeprefix("www.") if match else ""


def units(run_id: str, track: str) -> list[dict]:
    """Every citable factual unit in a track's assets, with its own citations."""
    base = content_path("content", Path(run_id).name, track)
    found: list[dict] = []

    deck = base / "ppt" / "deck_spec.json"
    if deck.exists():
        for slide in _json(deck)["slides"]:
            found.append({
                "id": f"deck-{slide['number']}",
                "asset": "deck",
                "reference": f"Slide {slide['number']}: {slide['title']}",
                "text": " ".join([slide["title"], *slide.get("content", [])]),
                "citations": slide.get("citations", []),
            })

    quiz = base / "quiz.json"
    if quiz.exists():
        for question in _json(quiz)["questions"]:
            options = question["options"]
            correct = options[question["correct_index"]] if isinstance(options, list) else ""
            found.append({
                "id": f"quiz-{question['id']}",
                "asset": "quiz",
                "reference": f"Question {question['id']}",
                "text": " ".join([question["prompt"], correct, question.get("rationale", "")]),
                "citations": question.get("citations", []),
            })

    faq = base / "faq.json"
    if faq.exists():
        for index, item in enumerate(_json(faq)["items"], 1):
            found.append({
                "id": f"faq-{index}",
                "asset": "faq",
                "reference": item["question"][:90],
                "text": " ".join([item["answer"], item.get("nuance", "")]),
                "citations": item.get("citations", []),
            })

    storyboard = base / "storyboard" / "storyboard.json"
    if storyboard.exists():
        for scene in _json(storyboard)["scenes"]:
            found.append({
                "id": f"scene-{scene['id']}",
                "asset": "storyboard",
                "reference": f"Scene {scene['id']}: {scene['title']}",
                "text": " ".join([scene.get("narration", ""), scene.get("on_screen_text", "")]),
                "citations": scene.get("citations", []),
            })
    return found


# A document has one identity; a URL has many spellings. DailyMed alone appears as
# drugInfo.cfm and lookup.cfm, with and without a version, all naming the same SPL.
# Keying by registry identifier rather than URL text is a correctness fix, not a
# convenience: those documents were already held and simply not recognised.
_SOURCE_KEYS = (
    ("dailymed", re.compile(r"dailymed\.nlm\.nih\.gov/.*?setid=([0-9a-f-]{36})", re.I)),
    ("pubmed", re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")),
    ("pmc", re.compile(r"(?:pmc\.ncbi\.nlm\.nih\.gov|ncbi\.nlm\.nih\.gov/pmc)/articles/(PMC\d+)", re.I)),
    # The study record only. A protocol PDF under cdn.clinicaltrials.gov is a
    # different document, and folding it in here would check a quote against text
    # it was never drawn from — a false result, which is worse than no result.
    ("nct", re.compile(r"^https?://(?:www\.)?clinicaltrials\.gov/study/(NCT\d+)", re.I)),
)


def source_key(url: str) -> str:
    """The identity of the document a URL names, or the URL when unrecognised."""
    for name, pattern in _SOURCE_KEYS:
        found = pattern.search(url or "")
        if found:
            return f"{name}:{found.group(1).lower()}"
    return url or ""


def source_corpus(drug: str) -> dict[str, str]:
    """Normalized full text of every stored source snapshot we can read.

    Keyed by `source_key`, so a citation can be checked against the document it
    names however that URL happens to be written. PDFs are skipped; where a source
    offers both PDF and XML the XML carries the same text, so label coverage is
    unaffected.

    Every snapshot is read, oldest first, so a later fetch supersedes an earlier one
    for the same document and a supplementary snapshot adds to what is already held
    rather than replacing it.
    """
    root = content_path("sources", _slug(drug))
    if not root.exists():
        return {}
    snapshots = [path for path in sorted(root.iterdir())
                 if path.is_dir() and not path.name.startswith(".")]
    corpus: dict[str, str] = {}
    for source in [entry for snapshot in snapshots for entry in sorted(snapshot.iterdir())]:
        manifest = source / "manifest.json"
        if not manifest.exists():
            continue
        registry = _json(manifest).get("registry", {})
        url = registry.get("url", "")
        if not url:
            continue
        text = []
        for path in sorted((source / "raw").glob("**/*")) if (source / "raw").exists() else []:
            if path.suffix.lower() not in {".xml", ".txt", ".json", ".html", ".htm"}:
                continue
            if path.stat().st_size > 20_000_000:
                continue
            try:
                raw = path.read_text(errors="ignore")
            except OSError:
                continue
            text.append(re.sub(r"<[^>]+>", " ", raw))
        if text:
            corpus[source_key(url)] = _norm(" ".join(text))
    return corpus


def readable_source(drug: str, url: str) -> str:
    """The stored document as prose: tags stripped, spacing collapsed, case kept.

    `source_corpus` normalizes for matching, which makes it unreadable. A reviewer
    deciding a finding needs to see the sentence as it is written, so this reads
    the same files again without flattening them. Off the check path — the
    evidence panel and the reading pane call it, one document at a time.
    """
    wanted = source_key(url)
    root = content_path("sources", _slug(drug))
    snapshots = [path for path in sorted(root.iterdir(), reverse=True)
                 if path.is_dir() and not path.name.startswith(".")] if root.exists() else []
    for source in [entry for snapshot in snapshots for entry in sorted(snapshot.iterdir())]:
        manifest = source / "manifest.json"
        if not manifest.exists() or source_key(_json(manifest).get("registry", {}).get("url", "")) != wanted:
            continue
        text = []
        for path in _readable_files(source / "raw"):
            try:
                text.append(re.sub(r"<[^>]+>", " ", path.read_text(errors="ignore")))
            except OSError:
                continue
        return re.sub(r"\s+", " ", " ".join(text)).strip()
    return ""


# The document first, its metadata after. Alphabetical order put DailyMed's
# 1.8KB `history.json` ahead of its 510KB `spl.xml`, so a reader opening the US
# label was met with an API envelope. Nothing is dropped — a quote can legitimately
# sit in either file — they are only read in the order a person would want them.
_READABLE = {".xml": 0, ".html": 1, ".htm": 1, ".txt": 2, ".json": 3}


def _readable_files(raw: Path) -> list[Path]:
    if not raw.exists():
        return []
    files = [path for path in raw.glob("**/*")
             if path.suffix.lower() in _READABLE and path.stat().st_size <= 20_000_000]
    return sorted(files, key=lambda path: (_READABLE[path.suffix.lower()], -path.stat().st_size, path.name))


def held_documents(drug: str) -> dict[str, dict]:
    """What we actually hold on disk, keyed by document identity.

    The inventory behind the reading pane. "Source" on a course card means a link
    we recorded; this is the narrower and more useful claim — the document is
    here, we fetched it on a date, and it can be read without leaving the app or
    trusting that the far end still serves it.

    Later snapshots win, so a re-fetch supersedes an earlier copy of the same
    document rather than appearing twice.
    """
    root = content_path("sources", _slug(drug))
    if not root.exists():
        return {}
    held: dict[str, dict] = {}
    snapshots = [path for path in sorted(root.iterdir())
                 if path.is_dir() and not path.name.startswith(".")]
    for source in [entry for snapshot in snapshots for entry in sorted(snapshot.iterdir())]:
        manifest = source / "manifest.json"
        if not manifest.exists():
            continue
        value = _json(manifest)
        registry = value.get("registry", {})
        key = source_key(registry.get("url", ""))
        if not key:
            continue
        readable = [path for path in sorted((source / "raw").glob("**/*"))
                    if path.suffix.lower() in {".xml", ".txt", ".json", ".html", ".htm"}]
        held[key] = {
            "key": key,
            "source_id": value.get("source_id", source.name),
            "title": registry.get("title", "") or source.name,
            "url": registry.get("url", ""),
            "kind": registry.get("kind", ""),
            "fetched_at": value.get("fetched_at", ""),
            "access_level": value.get("access_level", ""),
            # PDF-only sources are held but not readable as text, and saying so is
            # the point — "we have it" and "you can read it here" differ.
            "readable": bool(readable),
        }
    return held


def quote_spans(supporting: str, corpus_text: str) -> list[dict]:
    """The recorded quote split into runs that are, and are not, in the source.

    Same five-word shingles the score uses, so the highlighting and the percentage
    can never disagree. This is what turns "12% verbatim" from a number a reviewer
    has to trust into a sentence they can read for themselves.
    """
    tokens = (supporting or "").split()
    normalized = [_norm(token) for token in tokens]
    real = [index for index, word in enumerate(normalized) if word]
    covered = [False] * len(tokens)
    for start in range(max(0, len(real) - 4)):
        window = real[start:start + 5]
        if len(window) < 5:
            break
        if " ".join(normalized[index] for index in window) in corpus_text:
            for index in window:
                covered[index] = True

    spans: list[dict] = []
    for index, token in enumerate(tokens):
        if spans and spans[-1]["present"] == covered[index]:
            spans[-1]["text"] += f" {token}"
        else:
            spans.append({"text": token, "present": covered[index]})
    return spans


def _passage(raw: str, spans: list[dict], window: int = 420) -> str:
    """Stored text around the longest part of the quote that is really there."""
    if not raw:
        return ""
    lowered = raw.lower()
    for span in sorted((item for item in spans if item["present"]), key=lambda item: -len(item["text"])):
        words = span["text"].split()
        # A long anchor fails on any difference in whitespace or punctuation, and
        # the point is to locate the passage, not to re-verify it. A short run from
        # the start of a span that already matched is enough to find the place.
        for size in (8, 5, 3):
            if len(words) < size:
                continue
            anchor = " ".join(words[:size])
            at = lowered.find(anchor.lower())
            if at < 0:
                continue
            start, end = max(0, at - window // 3), min(len(raw), at + window)
            return ("… " if start else "") + raw[start:end].strip() + (" …" if end < len(raw) else "")
    return ""


def _dossier_citations(run_id: str) -> dict[tuple[str, str], dict]:
    """Every dossier citation, keyed by title and by locator, for traceability."""
    path = content_path("content", Path(run_id).name, "master", "dossier.json")
    if not path.exists():
        return {}
    index: dict[tuple[str, str], dict] = {}
    for section in _json(path).get("sections", []):
        for claim in section.get("claims", []):
            for citation in claim.get("citations", []):
                key = (_norm(citation.get("title", "")), _norm(citation.get("locator", "")))
                index.setdefault(key, {**citation, "claim": claim["text"], "section": section["title"]})
                loose = (_norm(citation.get("title", "")), "")
                index.setdefault(loose, {**citation, "claim": claim["text"], "section": section["title"]})
    return index


def quote_match(supporting: str, corpus_text: str) -> float:
    """How much of a recorded quote is actually present in the source, 0–1.

    Measured over five-word shingles so the result degrades smoothly: a quote
    stitched from two places scores in the middle rather than failing outright,
    which is the difference between "paraphrased" and "not in the document".
    """
    fragments = [_norm(part) for part in re.split(r"\.{2,}|…", supporting or "")]
    fragments = [part for part in fragments if len(part) >= MIN_QUOTE_FRAGMENT]
    if not fragments:
        return 0.0
    present = total = 0
    for fragment in fragments:
        words = fragment.split()
        shingles = [" ".join(words[index:index + 5]) for index in range(max(1, len(words) - 4))]
        total += len(shingles)
        present += sum(shingle in corpus_text for shingle in shingles)
    return present / total if total else 0.0


VERBATIM, PARTIAL = 0.9, 0.35


def deterministic_findings(run_id: str, track: str, drug: str) -> tuple[list[Finding], dict]:
    corpus = source_corpus(drug)
    dossier = _dossier_citations(run_id)
    findings: list[Finding] = []
    stats = {"units": 0, "citations": 0, "traceable": 0, "checkable": 0, "verified": 0, "partial": 0}

    for unit in units(run_id, track):
        stats["units"] += 1
        citations = unit["citations"]

        if not citations:
            if not FRONT_MATTER.search(unit["reference"]):
                findings.append(Finding(unit["id"], unit["asset"], unit["reference"], "uncited", "major",
                                        "This unit makes a factual statement with no citation attached.",
                                        asset_text=unit["text"][:400]))
            continue

        domains = {_domain(citation.get("url", "")) for citation in citations}
        if domains and domains <= (PROMOTIONAL | AGGREGATORS):
            findings.append(Finding(
                unit["id"], unit["asset"], unit["reference"], "promotional_only", "major",
                f"Every citation here is manufacturer-hosted or an aggregator ({', '.join(sorted(domains))}). "
                "A primary regulatory or peer-reviewed source should carry this claim.",
                asset_text=unit["text"][:400], citations=citations))

        if EFFECT.search(unit["text"]) and not PRECISION.search(unit["text"]):
            findings.append(Finding(
                unit["id"], unit["asset"], unit["reference"], "imprecise_effect", "major",
                f"An efficacy effect (“{EFFECT.search(unit['text']).group(0)}”) is stated without a confidence "
                "interval, p-value or range. This audience reads the estimate and the uncertainty together; "
                "the figure alone reads as more certain than the evidence is.",
                asset_text=unit["text"][:400], citations=citations))

        if COMPARATIVE.search(unit["text"]):
            findings.append(Finding(
                unit["id"], unit["asset"], unit["reference"], "comparative_claim", "major",
                f"Comparative language (“{COMPARATIVE.search(unit['text']).group(0)}”) needs head-to-head "
                "evidence or explicit framing as cross-trial.",
                asset_text=unit["text"][:400], citations=citations))

        for citation in citations:
            stats["citations"] += 1
            key = (_norm(citation.get("title", "")), _norm(citation.get("locator", "")))
            match = dossier.get(key) or dossier.get((key[0], ""))
            if not match:
                findings.append(Finding(
                    unit["id"], unit["asset"], unit["reference"], "untraceable", "blocking",
                    f"Citation “{citation.get('title', '')[:70]}” does not match any claim collected during "
                    "research, so there is no recorded evidence behind it.",
                    asset_text=unit["text"][:400], citations=[citation]))
                continue
            stats["traceable"] += 1

            supporting = match.get("supporting_text", "")
            corpus_text = corpus.get(source_key(match.get("url", "")))
            if not supporting or not corpus_text:
                continue
            stats["checkable"] += 1
            ratio = quote_match(supporting, corpus_text)
            if ratio >= VERBATIM:
                stats["verified"] += 1
            elif ratio >= PARTIAL:
                stats["partial"] += 1
                findings.append(Finding(
                    unit["id"], unit["asset"], unit["reference"], "quote_not_verbatim", "major",
                    f"The recorded supporting quote is only {round(100 * ratio)}% verbatim — part of it does "
                    "not appear in the source document, so it reads as a stitched or paraphrased quotation.",
                    asset_text=unit["text"][:400], source_text=supporting[:400], citations=[citation]))
            else:
                findings.append(Finding(
                    unit["id"], unit["asset"], unit["reference"], "quote_not_found", "blocking",
                    f"Only {round(100 * ratio)}% of the recorded supporting quote appears in the stored source "
                    "document. Treat this citation as unverified until a reviewer confirms it.",
                    asset_text=unit["text"][:400], source_text=supporting[:400], citations=[citation]))
    return findings, stats


def _unit_evidence(unit: dict, dossier: dict) -> list[dict]:
    evidence = []
    for citation in unit["citations"]:
        key = (_norm(citation.get("title", "")), _norm(citation.get("locator", "")))
        match = dossier.get(key) or dossier.get((key[0], ""))
        if match and match.get("supporting_text"):
            evidence.append(match)
    return evidence


async def model_findings(run_id: str, track: str, budget: RunBudget | None = None,
                         limit: int | None = None) -> tuple[list[Finding], str]:
    """Ask a model whether each unit overstates the evidence recorded behind it.

    Returns the findings and a status string. A check that could not run must say
    so — reporting "no problems found" when nothing was actually checked would be
    the worst possible failure mode for a quality gate.
    """
    from src.agent import _message_json

    if not os.getenv("ANTHROPIC_API_KEY"):
        return [], "skipped: no ANTHROPIC_API_KEY set"
    dossier = _dossier_citations(run_id)
    budget = budget or RunBudget(Path(run_id).name)
    findings: list[Finding] = []
    checked = 0
    skipped: list[str] = []

    system = "\n".join([
        "You are a medical-affairs reviewer performing a pre-check on pharmaceutical training content "
        "before a human expert sees it. You are given a unit of learner-facing text and the verbatim "
        "evidence recorded behind it.",
        "",
        "Judge ONLY whether the learner-facing text is supported by the evidence provided.",
        "  supported     - the text stays within what the evidence states",
        "  needs_context - accurate but omits a qualifier that changes how it should be read",
        "  overreach     - states more certainty, breadth or benefit than the evidence supports",
        "  unsupported   - asserts something the evidence does not establish at all",
        "",
        "Be strict about: causal language where the evidence is associative; absolute claims where the "
        "evidence gives a range or confidence interval; population breadth beyond the labelled indication; "
        "efficacy stated without its qualifying conditions.",
        "Do not comment on style, teaching quality, or completeness. Do not invent evidence.",
        "If the verdict is 'supported', use severity 'minor' and leave suggested_rewrite empty.",
        "",
        "Answer in at most 40 words for explanation and at most 40 words for suggested_rewrite. "
        "Do not restate the text. Be specific about which word or number is unsupported.",
    ])

    pool = units(run_id, track)[:limit] if limit else units(run_id, track)
    for unit in pool:
        evidence = _unit_evidence(unit, dossier)
        if not evidence:
            continue
        user = "\n\n".join([
            f"LEARNER-FACING TEXT ({unit['reference']}):\n{unit['text']}",
            "EVIDENCE RECORDED BEHIND IT:\n" + "\n\n".join(
                f"CLAIM: {item['claim']}\nSOURCE: {item.get('title', '')} | {item.get('locator', '')}\n"
                f"VERBATIM: {item.get('supporting_text', '')}"
                for item in evidence),
        ])
        try:
            value = await _message_json(
                system, user, f"judge {track} {unit['id']}", budget, JudgeVerdict,
                max_tokens=JUDGE_MAX_TOKENS,
                cache_path=_cache_path("judge", run_id, track, unit["id"], unit["text"]),
                cache_system=True, stage="judge", stage_limit_usd=JUDGE_STAGE_BUDGET_USD,
            )
        except Exception as error:
            # A unit the model cannot answer cleanly is skipped, not fatal. Four
            # failures in a row means something systemic, so stop paying for it.
            match = re.search(r"'message': '([^']+)'", str(error))
            skipped.append((match.group(1) if match else str(error))[:120])
            if len(skipped) >= 4:
                return findings, f"stopped after {checked} of {len(pool)} units — {skipped[-1]}"
            continue
        checked += 1
        if value["verdict"] == "supported":
            continue
        findings.append(Finding(
            unit["id"], unit["asset"], unit["reference"], value["verdict"], value["severity"],
            value["explanation"], asset_text=unit["text"][:400],
            source_text=evidence[0].get("supporting_text", "")[:400],
            suggested_rewrite=value.get("suggested_rewrite", ""), citations=unit["citations"]))
    note = f" ({len(skipped)} skipped)" if skipped else ""
    return findings, f"complete: {checked} of {len(pool)} units judged{note}"


async def confirm(run_id: str, track: str, findings: list[Finding],
                  budget: RunBudget | None = None) -> tuple[list[Finding], str]:
    """Re-judge the serious findings against everything the course collected.

    The first pass sees only the evidence attached to a unit, so it cannot tell
    "this is not supported anywhere" from "this is supported, but the citation
    beside it is not the one that supports it". The second pass adds the closest
    claims from the whole dossier and re-asks. Findings that clear become an
    under-citation finding, which is a real defect but a different one, and only
    what survives stays blocking.
    """
    from src.agent import _message_json
    from src.assistant import search

    serious = [item for item in findings if item.check in {"unsupported", "overreach"}]
    if not serious:
        return findings, "no findings needed confirmation"

    dossier = _dossier_citations(run_id)
    by_id = {unit["id"]: unit for unit in units(run_id, track)}
    budget = budget or RunBudget(Path(run_id).name)
    confirmed: list[Finding] = []
    checked = 0
    failures: list[str] = []

    system = (
        "You are re-checking a flagged piece of pharmaceutical training content. You are given the "
        "learner-facing text, the evidence cited beside it, and the most relevant additional evidence "
        "from the same research dossier.\n\n"
        "Decide whether the text is supported by ANY of the evidence shown.\n"
        "  supported     - some evidence here supports it, even if it was not the citation attached\n"
        "  needs_context - supported but missing a qualifier that changes how it reads\n"
        "  overreach     - states more than any evidence here supports\n"
        "  unsupported   - no evidence here establishes it\n\n"
        "Answer in at most 40 words per field. Name the specific claim that is unsupported."
    )

    for finding in serious:
        unit = by_id.get(finding.unit_id)
        if not unit:
            confirmed.append(finding)
            continue
        cited = _unit_evidence(unit, dossier)
        nearby = search(run_id, unit["text"], limit=5)
        user = "\n\n".join([
            f"LEARNER-FACING TEXT ({unit['reference']}):\n{unit['text']}",
            "EVIDENCE CITED BESIDE IT:\n" + "\n".join(
                f"- {item.get('supporting_text', '')}" for item in cited),
            "OTHER EVIDENCE COLLECTED FOR THIS COURSE:\n" + "\n".join(
                f"- {match['text']}" for match in nearby),
        ])
        try:
            value = await _message_json(
                system, user, f"confirm {track} {unit['id']}", budget, JudgeVerdict,
                max_tokens=JUDGE_MAX_TOKENS,
                cache_path=_cache_path("judge-confirm", run_id, track, unit["id"], unit["text"]),
                stage="judge", stage_limit_usd=JUDGE_STAGE_BUDGET_USD)
        except Exception as error:
            # One flaky call must not discard the whole pass, but a systemic
            # failure (credit, auth) should stop rather than retry thirty times.
            match = re.search(r"'message': '([^']+)'", str(error))
            failures.append((match.group(1) if match else str(error))[:120])
            confirmed.append(finding)
            if len(failures) >= 4:
                kept = [item for item in findings if item.check not in {"unsupported", "overreach"}]
                remaining = [item for item in serious if item not in confirmed]
                return kept + confirmed + remaining, (
                    f"stopped after {checked} of {len(serious)} — {failures[-1]}")
            continue
        checked += 1

        if value["verdict"] in {"supported", "needs_context"}:
            confirmed.append(Finding(
                # The course does hold the evidence, so this is a traceability
                # defect rather than a safety one — real, but not reviewer-urgent.
                finding.unit_id, finding.asset, finding.reference, "under_cited", "minor",
                "The course does hold evidence for this, but not in the citation attached here — "
                f"a reader following the citation will not find it. {value['explanation']}",
                asset_text=finding.asset_text, source_text=finding.source_text,
                suggested_rewrite=finding.suggested_rewrite, citations=finding.citations))
        else:
            confirmed.append(Finding(
                finding.unit_id, finding.asset, finding.reference, value["verdict"], value["severity"],
                f"Confirmed against the whole dossier: {value['explanation']}",
                asset_text=finding.asset_text, source_text=finding.source_text,
                suggested_rewrite=value.get("suggested_rewrite", ""), citations=finding.citations))

    kept = [item for item in findings if item.check not in {"unsupported", "overreach"}]
    note = f" ({len(failures)} could not be re-checked)" if failures else ""
    return kept + confirmed, f"confirmed {checked} of {len(serious)} findings against the full dossier{note}"


TARGET_FOR = {"deck": "deck", "quiz": "quiz", "faq": "faq", "storyboard": "storyboard",
              "under_cited": "sources"}


def report_path(run_id: str) -> Path:
    return content_path("platform", "checks", f"{Path(run_id).name}.json")


def stored_report(run_id: str) -> dict | None:
    path = report_path(run_id)
    return _json(path) if path.exists() else None


def _legacy_finding_id(finding: dict) -> str:
    """The identifier used before citations were part of it.

    Kept only so comments already raised against the old form stay matched to
    their finding; nothing new is ever given one of these.
    """
    return f"{finding['unit_id']}:{finding['check']}:{finding['reference'][:40]}"


def finding_id(finding: dict) -> str:
    """A handle that is stable across re-runs and unique within a report.

    Unit, check and reference alone are not unique: one quiz question can fail
    the same check against two different citations. Collapsing those loses a
    finding — in the review queue, where the second is never raised, and in the
    Checks tab, where React drops the duplicate key. The citation is what tells
    them apart, so it belongs in the identifier.
    """
    citations = ";".join(
        f"{citation.get('title') or ''}#{citation.get('locator') or ''}"
        for citation in finding.get("citations") or ()
    )
    if not citations:
        return _legacy_finding_id(finding)
    digest = sha1(citations.encode()).hexdigest()[:8]
    return f"{_legacy_finding_id(finding)}#{digest}"


# Checks with a checkable answer: whether a quote appears in a stored document,
# whether a citation traces to a collected claim, whether a domain is on a list.
# None of them is an opinion, so none of them stops being true when a reviewer
# disagrees. The rest — unsupported, overreach, under_cited — are model judgements,
# where a human expert outranks the machine and a dismissal is simply accepted.
DETERMINISTIC_CHECKS = frozenset({
    "uncited", "promotional_only", "comparative_claim", "imprecise_effect",
    "untraceable", "quote_not_verbatim", "quote_not_found",
})


def drug_for(run_id: str) -> str:
    path = content_path("content", Path(run_id).name, "manifest.json")
    return _json(path).get("drug", {}).get("brand", "") if path.exists() else ""


def failing_now(run_id: str, tracks=("hcp", "msl")) -> dict[str, dict]:
    """Every deterministic finding that currently reproduces, indexed by identifier.

    Cheap by construction: no model, no API key, no network. It reads the same
    stored corpus the original check read, which is the point — the answer cannot
    be argued with, only changed by adding the source document or fixing the text.

    Built once and reused when several comments are being re-checked together; a
    version cut asks about every addressed comment at once.
    """
    drug = drug_for(run_id)
    index: dict[str, dict] = {}
    for track in tracks:
        found, _ = deterministic_findings(run_id, track, drug)
        for item in found:
            bare = asdict(item)
            # `run` namespaces unit ids by track before the identifier is built, so
            # the prefixed form is what a stored report holds. Both are indexed
            # because a report written straight from `deterministic_findings` is not.
            for candidate in ({**bare, "unit_id": f"{track}:{item.unit_id}"}, bare):
                index.setdefault(finding_id(candidate), candidate)
                index.setdefault(_legacy_finding_id(candidate), candidate)
    return index


def still_failing(comment: dict, index: dict[str, dict]) -> dict | None:
    """Grounds for not taking this comment at its word, or None if it stands.

    None means the question is settled in the comment's favour for one of three
    reasons: it is a human's comment with no check behind it, it is a model
    judgement where a human expert outranks the machine, or the check genuinely
    no longer reproduces.
    """
    check = comment.get("check") or ""
    identifier = comment.get("finding_id")
    if comment.get("origin") != "automated_check" or check not in DETERMINISTIC_CHECKS or not identifier:
        return None
    found = index.get(identifier)
    if not found:
        return None
    return {
        "check": check,
        "reference": found["reference"],
        "message": found["message"],
        "asset_text": found.get("asset_text", ""),
        "source_text": found.get("source_text", ""),
    }


def dismissal_challenge(run_id: str, comment: dict) -> dict | None:
    """Whether dismissing this one comment should be challenged rather than accepted."""
    return still_failing(comment, failing_now(run_id))


def coverage_now(run_id: str, tracks=("hcp", "msl")) -> dict:
    """What could be checked against the corpus as it stands today.

    A stored report is a snapshot of one moment: the findings it holds are what the
    machine saw on the draft, and overwriting them would erase the record of what
    review was for. But the corpus grows — every document resolved from a citation
    makes more of the course checkable — so the live figure is reported alongside
    the snapshot rather than replacing it.
    """
    drug = drug_for(run_id)
    stats = {"units": 0, "citations": 0, "traceable": 0, "checkable": 0, "verified": 0, "partial": 0}
    for track in tracks:
        _, counts = deterministic_findings(run_id, track, drug)
        for key in stats:
            stats[key] += counts[key]
    return {
        **stats,
        "documents": len(source_corpus(drug)),
        "coverage_percent": round(100 * stats["checkable"] / stats["citations"]) if stats["citations"] else 0,
        "verified_percent": round(100 * stats["verified"] / stats["checkable"]) if stats["checkable"] else 0,
    }


def evidence_for(run_id: str, comment: dict) -> dict | None:
    """Everything needed to decide one machine finding, in one payload.

    A reviewer should not have to leave the comment to settle it: the claim as it
    is written, the quote that was recorded against it, which parts of that quote
    are really in the stored document, the passage itself, and — said plainly —
    what we do not hold and therefore could not check.
    """
    identifier = comment.get("finding_id")
    report = stored_report(run_id)
    if not identifier or not report:
        return None
    finding = next((item for item in report["findings"] if finding_id(item) == identifier), None)
    if not finding:
        return None

    drug = drug_for(run_id)
    corpus = source_corpus(drug)
    dossier = _dossier_citations(run_id)

    citations, unheld = [], []
    quote, spans, percent, passage, source = "", [], None, "", None
    for citation in finding.get("citations") or ():
        key = (_norm(citation.get("title", "")), _norm(citation.get("locator", "")))
        claim = dossier.get(key) or dossier.get((key[0], ""))
        url = (claim or citation).get("url", "")
        held = source_key(url) in corpus
        citations.append({
            "title": citation.get("title", ""),
            "url": url,
            "locator": citation.get("locator", ""),
            "traceable": bool(claim),
            "held": held,
            "claim": (claim or {}).get("claim", ""),
        })
        if not held:
            unheld.append(url or citation.get("title", ""))
        if quote or not claim or not held:
            continue
        quote = claim.get("supporting_text", "")
        if quote:
            spans = quote_spans(quote, corpus[source_key(url)])
            percent = round(100 * quote_match(quote, corpus[source_key(url)]))
            passage = _passage(readable_source(drug, url), spans)
            source = {"title": citation.get("title", ""), "url": url, "locator": citation.get("locator", "")}

    return {
        "comment_id": comment["id"],
        "check": finding["check"],
        "severity": finding["severity"],
        "reference": finding["reference"],
        "message": finding["message"],
        "claim": finding.get("asset_text", ""),
        "suggested_rewrite": finding.get("suggested_rewrite", ""),
        "quote": quote,
        "spans": spans,
        "match_percent": percent,
        "passage": passage,
        "source": source,
        "citations": citations,
        # Stated rather than implied: a citation we hold no document for was never
        # checked, and saying so is the difference between honest and merely quiet.
        "unheld": unheld,
        "coverage": {"held": sum(1 for entry in citations if entry["held"]), "total": len(citations)},
    }


def promote(run_id: str, severities=("blocking",), finding_ids: list[str] | None = None) -> list[dict]:
    """Turn stored findings into review comments in the normal queue.

    The checker uses the same comment shape, severities and address/dismiss flow
    as a human reviewer, so a machine finding is something an expert can disagree
    with rather than a separate channel that bypasses them. Re-running is safe:
    a finding already promoted is not raised twice.
    """
    from src import learning

    report = stored_report(run_id)
    if not report:
        raise ValueError("Run the checks before promoting findings")

    record = learning.course(run_id)
    already = {comment.get("finding_id") for comment in record["comments"] if comment.get("finding_id")}
    wanted = set(finding_ids or [])
    raised = []
    for finding in report["findings"]:
        identifier = finding_id(finding)
        chosen = identifier in wanted if wanted else finding["severity"] in severities
        # A comment raised before the identifier gained its citation is still that
        # finding's comment, so an existing queue is never duplicated on re-run.
        if not chosen or identifier in already or _legacy_finding_id(finding) in already:
            continue
        body = f"{finding['reference']}\n{finding['message']}"
        if finding.get("suggested_rewrite"):
            body += f"\n\nSuggested: {finding['suggested_rewrite']}"
        comment = learning.add_comment(
            run_id, learning.CHECKER["id"], TARGET_FOR.get(finding["asset"], "sources"),
            finding["severity"], body)
        record = learning.course(run_id)
        stored = next(entry for entry in record["comments"] if entry["id"] == comment["id"])
        stored["finding_id"] = identifier
        stored["origin"] = "automated_check"
        stored["check"] = finding["check"]
        learning._save_course(record)
        already.add(identifier)
        raised.append(stored)
    return raised


# Below this, a percentage says more about the sample than the reviewer. Counts are
# always shown; a rate only appears once there is enough behind it to mean anything.
MIN_FOR_RATE = 3


def agreement(run_id: str) -> dict:
    """How often a human reviewer accepted what the checker raised.

    The calibration number: a machine gate is only worth its noise if the experts
    who can overrule it usually do not.

    The per-reviewer split is for a conversation about calibration, not a scorecard
    — which is why overrides are counted separately rather than folded into
    "dismissed", and why a rate is withheld until there is a sample behind it.
    """
    from src import learning

    record = learning.course(run_id)
    machine = [comment for comment in record["comments"] if comment.get("origin") == "automated_check"]
    settled = [comment for comment in machine if comment["status"] in {"addressed", "closed", "dismissed"}]
    accepted = [comment for comment in settled if comment["status"] != "dismissed"]

    people: dict[str, dict] = {}
    for comment in settled:
        who = comment.get("resolved_by_id") or ""
        entry = people.setdefault(who, {
            "id": who,
            "name": comment.get("resolved_by_name") or "Not recorded",
            "title": comment.get("resolved_by_title") or "",
            "settled": 0, "accepted": 0, "dismissed": 0, "overrides": 0,
        })
        entry["settled"] += 1
        entry["dismissed" if comment["status"] == "dismissed" else "accepted"] += 1
        entry["overrides"] += bool(comment.get("override"))

    for entry in people.values():
        entry["agreement_percent"] = (round(100 * entry["accepted"] / entry["settled"])
                                      if entry["settled"] >= MIN_FOR_RATE else None)

    return {
        "raised": len(machine),
        "settled": len(settled),
        "accepted": len(accepted),
        "dismissed": len(settled) - len(accepted),
        # The same floor the per-reviewer split already used. Without it one
        # dismissal rendered as "0% reviewer agreement", which is precisely the
        # sample-of-one number MIN_FOR_RATE exists to withhold — and it read as a
        # verdict on the checker rather than as a count of one.
        "agreement_percent": (round(100 * len(accepted) / len(settled))
                              if len(settled) >= MIN_FOR_RATE else None),
        "by_reviewer": sorted(people.values(), key=lambda entry: -entry["settled"]),
    }


async def run(run_id: str, drug: str, tracks=("hcp", "msl"), model_tracks=("hcp",)) -> dict:
    """Deterministic checks on every track; the model passes only where asked.

    The model half is the expensive half, so it is scoped explicitly rather than
    run everywhere by default. Results are cached per unit, so a repeat run of an
    unchanged course costs nothing."""
    from src.agent import replay_source

    # A replayed course is a copy of content that has already been through this,
    # so the model half would pay a second time for verdicts on identical text.
    # The deterministic half still runs in full against the copy actually on disk,
    # which is what keeps the report about this run rather than about its source.
    if replay_source():
        model_tracks = ()

    findings: list[Finding] = []
    model_status: dict[str, str] = {}
    stats = {"units": 0, "citations": 0, "traceable": 0, "checkable": 0, "verified": 0, "partial": 0}
    for track in tracks:
        deterministic, counts = deterministic_findings(run_id, track, drug)
        findings += [Finding(**{**asdict(item), "unit_id": f"{track}:{item.unit_id}"}) for item in deterministic]
        for key in stats:
            stats[key] += counts[key]
        if track in model_tracks:
            model, status = await model_findings(run_id, track)
            if model:
                model, confirm_status = await confirm(run_id, track, model)
                status = f"{status}; {confirm_status}"
            model_status[track] = status
            findings += [Finding(**{**asdict(item), "unit_id": f"{track}:{item.unit_id}"}) for item in model]

    order = {"blocking": 0, "major": 1, "minor": 2}
    findings.sort(key=lambda item: (order.get(item.severity, 3), item.unit_id))
    report = {
        "run_id": run_id,
        "model_status": model_status or {"": "skipped: deterministic checks only"},
        "stats": {
            **stats,
            "flagged_units": len({item.unit_id for item in findings}),
            "coverage_percent": round(100 * stats["checkable"] / stats["citations"]) if stats["citations"] else 0,
            "verified_percent": round(100 * stats["verified"] / stats["checkable"]) if stats["checkable"] else 0,
        },
        "findings": [asdict(item) for item in findings],
        "checked_at": datetime.now(UTC).isoformat(),
    }
    _write(report_path(run_id), report)
    return report


# ---------------------------------------------------------------------------
# Repointing a bad citation.
#
# A finding that says "this quote is not in that document" has exactly one honest
# fix: cite a document that does contain it. That was a repair the seed script
# could perform and the running app could not, which made it a demo trick rather
# than a product feature — and left a real blocking finding with no route out of
# the review queue except waving it through.
# ---------------------------------------------------------------------------

# Where each citable unit lives on disk, and how `units()` names it. The two must
# agree exactly: a repoint that cannot find the unit a finding names is a fix that
# silently does nothing. FAQ entries carry no id of their own and are addressed by
# position, which is why the id is built from the entry *and* its index.
ASSET_FILE = {
    "deck": ("ppt", "deck_spec.json", "slides", lambda entry, index: f"deck-{entry['number']}"),
    "quiz": (None, "quiz.json", "questions", lambda entry, index: f"quiz-{entry['id']}"),
    "storyboard": ("storyboard", "storyboard.json", "scenes", lambda entry, index: f"scene-{entry['id']}"),
    "faq": (None, "faq.json", "items", lambda entry, index: f"faq-{index}"),
}


REPOINT_STOPWORDS = frozenset("the a an of for and or in on to with at is are be as by from that this it not".split())


def _repoint_terms(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]{4,}", (text or "").lower())} - REPOINT_STOPWORDS


def verified_citation(run_id: str, drug: str, about: str = "") -> dict | None:
    """A citation the dossier holds whose recorded quote is really in the source.

    Repointing a bad citation at this one is the fix a reviewer would make by hand,
    and it is the only kind that actually clears a `untraceable` or `quote_not_found`
    check — which is the point, now that a version cut reads the content back.

    `about` is the text being cited, and the best-overlapping candidate wins.
    Taking the first verifiable claim instead put a bladder-metastasis case report
    behind a neutropenia dose-modification question: traceable, verbatim, and
    about something else entirely. Our checks measure provenance, not relevance,
    so nothing downstream would have objected — which is exactly why the choice
    has to be made carefully here rather than left to dictionary order.
    """
    corpus = source_corpus(drug)
    wanted = _repoint_terms(about)
    best, best_score = None, -1.0
    for claim in _dossier_citations(run_id).values():
        text = corpus.get(source_key(claim.get("url", "")))
        quote = claim.get("supporting_text", "")
        if not (text and quote and quote_match(quote, text) >= VERBATIM):
            continue
        candidate = {"title": claim.get("title", ""), "url": claim.get("url", ""),
                     "locator": claim.get("locator", "")}
        if not wanted:
            return candidate
        overlap = _repoint_terms(" ".join([quote, claim.get("title", ""), claim.get("locator", "")]))
        score = len(wanted & overlap) / len(wanted)
        if score > best_score:
            best, best_score = candidate, score
    return best


def repoint(run_id: str, track: str, unit_id: str, citation: dict) -> bool:
    """Put a good citation on the unit a finding names. Returns whether it landed."""
    for folder, name, collection, make_id in ASSET_FILE.values():
        base = content_path("content", run_id, track)
        path = (base / folder / name) if folder else (base / name)
        if not path.exists():
            continue
        data = _json(path)
        for index, entry in enumerate(data.get(collection, []), 1):
            if make_id(entry, index) != unit_id:
                continue
            entry["citations"] = [citation]
            _write(path, data)
            return True
    return False


# Only a finding that names a document problem can be fixed by naming a better
# document. An overreach or an imprecise effect is a wording problem and has to be
# rewritten by a person; offering a one-click fix there would be a lie.
REPOINTABLE = frozenset({"quote_not_found", "quote_not_verbatim", "untraceable", "promotional_only"})


def repoint_comment(run_id: str, comment_id: str, user_id: str) -> dict:
    """Repoint the citation behind one machine finding, and say what happened.

    The maker's fix, not the checker's: an admin chooses to apply it, and the
    version cut afterwards re-runs the same check against the changed content, so
    the fix has to be real to survive. Returns the citation that was applied.
    """
    from src import learning

    record = learning.course(run_id)
    author = learning._author(user_id, role="admin")
    comment = next((entry for entry in record["comments"] if entry["id"] == comment_id), None)
    if not comment:
        raise ValueError("Comment not found")
    if comment.get("origin") != "automated_check":
        raise ValueError("Only an automated finding names a citation that can be repointed")
    if comment.get("check") not in REPOINTABLE:
        raise ValueError(f"A {comment.get('check')} finding is a wording problem — it has to be rewritten, not recited")

    report = stored_report(run_id) or {"findings": []}
    finding = next((item for item in report["findings"]
                    if finding_id(item) == comment.get("finding_id")), None)
    if not finding:
        raise ValueError("The finding behind this comment is no longer in the stored report")

    drug = drug_for(run_id)
    track, _, unit_id = finding["unit_id"].partition(":")
    # Chosen against the unit's own text, so the replacement is about the same
    # thing the claim is about. Provenance without relevance is how a bladder-case
    # citation ends up behind a neutropenia question.
    citation = verified_citation(run_id, drug, finding.get("asset_text", "") or finding["reference"])
    if not citation:
        raise ValueError("No citation in this dossier both resolves to a held document and quotes it verbatim")
    if not repoint(run_id, track, unit_id, citation):
        raise ValueError(f"Could not find {unit_id} in the {track.upper()} assets to repoint")

    learning._audit(
        record, author, "citation.repointed",
        f"{author['name']} repointed the citation on {finding['reference'][:60]} to {citation['title'][:60]}",
        comment_id=comment_id, unit_id=finding["unit_id"], check=comment.get("check"),
        url=citation.get("url"))
    learning._save_course(record)
    return citation

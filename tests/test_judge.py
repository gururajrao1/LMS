import json

import pytest

from src import agent, judge, learning

RUN_ID = "ibrance-check"
LABEL = {"title": "IBRANCE Label", "url": "https://dailymed.test/spl", "locator": "5.1"}
QUOTE = "Monitor complete blood counts prior to the start of therapy and at the beginning of each cycle."


@pytest.fixture(autouse=True)
def no_billed_calls(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    base = tmp_path / "content" / RUN_ID
    (base / "hcp" / "ppt").mkdir(parents=True)
    (base / "master").mkdir(parents=True)

    # The drug is read back off the manifest whenever a check re-runs on its own,
    # so a fixture without one silently has no corpus to check against.
    (base / "manifest.json").write_text(json.dumps({
        "run_id": RUN_ID, "generated_at": "2026-08-01",
        "drug": {"brand": "Ibrance", "generic": "Palbociclib", "area": "Oncology"},
    }))

    (base / "master" / "dossier.json").write_text(json.dumps({
        "drug": {"brand": "Ibrance"}, "title": "Ibrance dossier",
        "sections": [{
            "id": "05_safety", "title": "Safety", "summary": "",
            "claims": [{
                "text": "Blood counts are monitored before each cycle.",
                "evidence_type": "FDA label",
                "citations": [{**LABEL, "supporting_text": QUOTE}],
            }],
        }],
    }))
    (base / "hcp" / "ppt" / "deck_spec.json").write_text(json.dumps({"slides": [
        {"number": 1, "title": "Welcome and Learning Objectives", "purpose": "Open", "content": [], "citations": []},
        {"number": 2, "title": "Monitoring", "purpose": "Safety", "content": ["Check counts each cycle."],
         "citations": [LABEL]},
        {"number": 3, "title": "Uncited safety claim", "purpose": "Safety",
         "content": ["Neutropenia resolves without intervention."], "citations": []},
        {"number": 4, "title": "Promotional only", "purpose": "Context",
         "content": ["Dosing guidance."],
         "citations": [{"title": "Ibrance dosing", "url": "https://www.pfizerpro.com/dosing", "locator": "Dosing"}]},
    ]}))

    # A stored source whose text the quote can be checked against.
    source = tmp_path / "sources" / "ibrance" / "20260101T000000Z" / "label"
    (source / "raw").mkdir(parents=True)
    (source / "manifest.json").write_text(json.dumps({"registry": {"url": LABEL["url"], "title": "Label"}}))
    (source / "raw" / "spl.xml").write_text(f"<doc><p>{QUOTE}</p></doc>")
    return RUN_ID


def _report(run_id):
    """A stored report shaped exactly as `judge.run` writes one.

    The track prefix on `unit_id` matters: repointing splits it back off to know
    which asset to rewrite, so a report written without it sends the repoint
    looking for an empty unit in a track called "deck-4".
    """
    findings, stats = judge.deterministic_findings(run_id, "hcp", "ibrance")
    findings = [judge.Finding(**{**judge.asdict(item), "unit_id": f"hcp:{item.unit_id}"})
                for item in findings]
    judge._write(judge.report_path(run_id), {
        "run_id": run_id, "stats": {**stats, "flagged_units": len({f.unit_id for f in findings})},
        "findings": [judge.asdict(f) for f in findings],
    })
    return findings


def test_quote_match_scores_how_much_of_a_quote_is_real():
    source = judge._norm(f"preamble {QUOTE} trailing text")
    assert judge.quote_match(QUOTE, source) == 1.0
    assert judge.quote_match("Monitor complete blood counts prior to inventing a fact never written", source) < 0.9
    assert judge.quote_match("Entirely different sentence about something else altogether here", source) == 0.0


def test_front_matter_slides_are_not_flagged_as_uncited(run):
    findings = _report(run)
    uncited = [item.reference for item in findings if item.check == "uncited"]
    assert any("Uncited safety claim" in reference for reference in uncited)
    assert not any("Learning Objectives" in reference for reference in uncited)


def test_a_claim_resting_only_on_promotional_sources_is_flagged(run):
    findings = _report(run)
    assert any(item.check == "promotional_only" and "Promotional only" in item.reference for item in findings)


def test_a_verbatim_quote_is_verified_against_the_stored_source(run):
    _findings, stats = judge.deterministic_findings(run, "hcp", "ibrance")
    assert stats["checkable"] == 1
    assert stats["verified"] == 1


def test_promotion_raises_blocking_only_and_is_idempotent(run):
    _report(run)
    blocking = judge.promote(run)
    assert judge.promote(run) == []

    record = learning.course(run)
    machine = [entry for entry in record["comments"] if entry["origin"] == "automated_check"]
    assert len(machine) == len(blocking)
    assert {entry["severity"] for entry in machine} <= {"blocking"}
    assert all(entry["author_name"] == "PharmaLearn checker" for entry in machine)


def test_the_lead_can_send_selected_findings_to_review(run):
    findings = _report(run)
    major = next(item for item in findings if item.severity == "major")
    identifier = judge.finding_id(judge.asdict(major))

    raised = judge.promote(run, finding_ids=[identifier])

    assert len(raised) == 1
    assert raised[0]["finding_id"] == identifier
    assert judge.promote(run, finding_ids=[identifier]) == []


def test_two_findings_on_one_unit_stay_separable(run):
    """One unit can fail the same check against two citations.

    Before the citation was part of the identifier these collapsed: the second
    was never raised into the queue, and the Checks tab rendered both under one
    React key. The reference is identical, so only the citation tells them apart.
    """
    shared = {"unit_id": "hcp:quiz-q3", "check": "quote_not_found", "reference": "Question q3"}
    first = {**shared, "citations": [{"title": "Label: capsule", "locator": "Dosage (1)"}]}
    second = {**shared, "citations": [{"title": "Label: tablet", "locator": "Dosage (1),(2)"}]}

    assert judge.finding_id(first) != judge.finding_id(second)
    # Stable across runs: the same finding always hashes to the same handle.
    assert judge.finding_id(first) == judge.finding_id({**first})


def test_a_comment_raised_under_the_old_identifier_is_not_raised_again(run):
    """Existing review queues predate the citation being part of the identifier."""
    findings = _report(run)
    blocking = judge.asdict(next(item for item in findings if item.severity == "blocking"))
    judge.promote(run)

    record = learning.course(run)
    machine = next(entry for entry in record["comments"] if entry.get("origin") == "automated_check")
    machine["finding_id"] = judge._legacy_finding_id(blocking)
    learning._save_course(record)

    assert judge.promote(run) == []


def test_the_checker_can_raise_comments_but_never_sign_off(run):
    _report(run)
    judge.promote(run)
    with pytest.raises(ValueError, match="reviewer"):
        learning.add_signoff(run, learning.CHECKER["id"], "approved")


def test_agreement_counts_what_reviewers_accepted(run):
    _report(run)
    judge.promote(run, severities=("blocking", "major"))
    machine = [entry for entry in learning.course(run)["comments"] if entry["origin"] == "automated_check"]
    learning.resolve_comment(run, machine[0]["id"], "addressed", "Fixed.", "priya-raman")
    # Overruling a check that still fails takes a named override, so the reviewer
    # who disagreed with the machine is the one recorded as disagreeing with it.
    learning.resolve_comment(run, machine[1]["id"], "dismissed", "Not applicable.", "anil-shekhar",
                             override_reason="Label page is the primary source here.")

    agreement = judge.agreement(run)

    assert agreement["raised"] == len(machine)
    assert agreement["settled"] == 2
    assert agreement["accepted"] == 1
    # Counts always; the rate waits for MIN_FOR_RATE. This assertion used to read
    # 50 — the headline was the one place the floor was not applied, so a single
    # override published itself as "0% reviewer agreement".
    assert agreement["agreement_percent"] is None


def test_blocking_findings_hold_publication(run):
    _report(run)
    judge.promote(run)
    learning.add_signoff(run, "anil-shekhar", "approved")

    readiness = learning.readiness(learning.course(run))

    assert readiness["open_blocking"] > 0
    assert readiness["can_publish"] is False


ADMIN, REVIEWER = "priya-raman", "anil-shekhar"


def _machine_comment(run_id: str, check: str | None = None) -> dict:
    comments = [entry for entry in learning.course(run_id)["comments"] if entry.get("origin") == "automated_check"]
    return next(entry for entry in comments if check is None or entry.get("check") == check)


def test_dismissing_a_still_failing_check_is_challenged_not_accepted(run):
    """Whether a citation traces to a collected claim is a fact, not an opinion.

    Before this, one PATCH removed the comment from `open_blocking` and cleared
    the course to publish. Now the check re-runs and the dismissal is held.
    """
    _report(run)
    judge.promote(run)
    learning.add_signoff(run, REVIEWER, "approved")
    comment = _machine_comment(run, "untraceable")

    held = learning.resolve_comment(run, comment["id"], "dismissed", "Not applicable.", REVIEWER)

    assert held["status"] == "open"
    assert held["challenge"]["check"] == "untraceable"
    assert held["challenge"]["by_name"] == "Dr. Anil Shekhar"
    assert held["challenge"]["attempted_reason"] == "Not applicable."

    readiness = learning.readiness(learning.course(run))
    assert readiness["challenged"] == 1
    assert readiness["open_blocking"] > 0
    assert readiness["can_publish"] is False


def test_an_override_carries_the_dismissal_through_and_names_who_made_it(run):
    """Experts are never blocked outright — the decision is simply never silent."""
    _report(run)
    judge.promote(run)
    comment = _machine_comment(run, "untraceable")
    learning.resolve_comment(run, comment["id"], "dismissed", "Not applicable.", REVIEWER)

    settled = learning.resolve_comment(
        run, comment["id"], "dismissed", "Not applicable.", REVIEWER,
        override_reason="Citation is correct; the paper postdates the dossier snapshot.")

    assert settled["status"] == "dismissed"
    assert settled["override"]["actor_name"] == "Dr. Anil Shekhar"
    assert settled["override"]["check"] == "untraceable"
    assert "postdates" in settled["override"]["reason"]
    # The override answers the challenge, so the banner goes; the trail keeps it.
    assert "challenge" not in settled

    record = learning.course(run)
    assert learning.readiness(record)["overrides"] == 1
    assert [entry["action"] for entry in record["audit"]][-3:] == [
        "dismissal.challenged", "dismissal.overridden", "comment.resolved",
    ]


def test_a_model_judgement_is_dismissed_without_challenge(run):
    """A human expert outranks the model, so only checkable findings are challenged."""
    _report(run)
    judge.promote(run)
    record = learning.course(run)
    comment = _machine_comment(run, "untraceable")
    next(entry for entry in record["comments"] if entry["id"] == comment["id"])["check"] = "unsupported"
    learning._save_course(record)

    settled = learning.resolve_comment(run, comment["id"], "dismissed", "Reads correctly in context.", REVIEWER)

    assert settled["status"] == "dismissed"
    assert "challenge" not in settled


def test_a_finding_that_no_longer_reproduces_is_dismissed_silently(run):
    """The world can change. If the defect is genuinely gone, the check says so."""
    _report(run)
    judge.promote(run)
    comment = _machine_comment(run, "untraceable")

    # Give the offending slide a citation the dossier does hold.
    deck = agent.DATA / "content" / RUN_ID / "hcp" / "ppt" / "deck_spec.json"
    spec = json.loads(deck.read_text())
    spec["slides"][3]["citations"] = [LABEL]
    deck.write_text(json.dumps(spec))

    settled = learning.resolve_comment(run, comment["id"], "dismissed", "Citation corrected.", REVIEWER)

    assert settled["status"] == "dismissed"
    assert "challenge" not in settled
    assert "override" not in settled


def test_a_dismissal_needs_a_reason(run):
    _report(run)
    judge.promote(run)
    comment = _machine_comment(run)

    with pytest.raises(ValueError, match="needs a reason"):
        learning.resolve_comment(run, comment["id"], "dismissed", "", REVIEWER)


def test_addressing_a_challenged_comment_clears_the_challenge(run):
    _report(run)
    judge.promote(run)
    comment = _machine_comment(run, "untraceable")
    learning.resolve_comment(run, comment["id"], "dismissed", "Not applicable.", REVIEWER)

    fixed = learning.resolve_comment(run, comment["id"], "addressed", "Citation repointed.", ADMIN)

    assert fixed["status"] == "addressed"
    assert "challenge" not in fixed
    # The attempt itself stays on the record even though the banner is gone.
    assert any(entry["action"] == "dismissal.challenged" for entry in learning.course(run)["audit"])


FAKE = {"title": "IBRANCE Label", "url": "https://dailymed.test/spl", "locator": "9.9"}
FABRICATED = "Palbociclib eliminates the need for routine haematology monitoring in every patient treated."


def _add_a_fabricated_quote(run_id: str):
    """A dossier claim whose recorded quote is not in the source it names."""
    base = agent.DATA / "content" / run_id
    dossier = json.loads((base / "master" / "dossier.json").read_text())
    dossier["sections"].append({
        "id": "09_monitoring", "title": "Monitoring", "summary": "",
        "claims": [{"text": "Monitoring can be relaxed.", "evidence_type": "FDA label",
                    "citations": [{**FAKE, "supporting_text": FABRICATED}]}],
    })
    (base / "master" / "dossier.json").write_text(json.dumps(dossier))

    deck = base / "hcp" / "ppt" / "deck_spec.json"
    spec = json.loads(deck.read_text())
    spec["slides"].append({"number": 5, "title": "Monitoring cadence", "purpose": "Safety",
                           "content": ["Routine monitoring is not needed."], "citations": [FAKE]})
    deck.write_text(json.dumps(spec))


def test_an_efficacy_effect_without_its_precision_is_flagged(run):
    """The depth floor: for this audience the estimate and the uncertainty go together."""
    deck = agent.DATA / "content" / RUN_ID / "hcp" / "ppt" / "deck_spec.json"
    spec = json.loads(deck.read_text())
    spec["slides"] += [
        {"number": 7, "title": "Efficacy", "purpose": "Evidence",
         "content": ["Median progression-free survival was 24.8 months versus 14.5 months."],
         "citations": [LABEL]},
        {"number": 8, "title": "Efficacy in full", "purpose": "Evidence",
         "content": ["Median progression-free survival was 24.8 months versus 14.5 (95% CI 0.46-0.72)."],
         "citations": [LABEL]},
    ]
    deck.write_text(json.dumps(spec))

    findings = _report(run)
    flagged = [item.reference for item in findings if item.check == "imprecise_effect"]

    assert any("Slide 7" in reference for reference in flagged)
    assert not any("Slide 8" in reference for reference in flagged)


def test_a_reviewer_is_not_rated_on_too_small_a_sample(run):
    """Counts always; a percentage only once it describes the reviewer, not the sample."""
    _report(run)
    judge.promote(run, severities=("blocking", "major"))
    comments = learning.course(run)["comments"]
    learning.resolve_comment(run, comments[0]["id"], "addressed", "Fixed.", ADMIN)

    solo = next(entry for entry in judge.agreement(run)["by_reviewer"] if entry["id"] == ADMIN)
    assert solo["settled"] == 1
    assert solo["agreement_percent"] is None

    for comment in comments[1:4]:
        learning.resolve_comment(run, comment["id"], "addressed", "Fixed.", ADMIN)

    rated = next(entry for entry in judge.agreement(run)["by_reviewer"] if entry["id"] == ADMIN)
    assert rated["settled"] >= judge.MIN_FOR_RATE
    assert rated["agreement_percent"] == 100


def test_an_override_is_counted_apart_from_a_plain_dismissal(run):
    """Overruling the checker with a written reason is not waving it away."""
    _report(run)
    judge.promote(run, severities=("blocking", "major"))
    comments = learning.course(run)["comments"]
    target = next(entry for entry in comments if entry.get("check") == "untraceable")
    learning.resolve_comment(run, target["id"], "dismissed", "Reviewed.", REVIEWER,
                             override_reason="Correct as cited; accepted deliberately.")

    entry = next(item for item in judge.agreement(run)["by_reviewer"] if item["id"] == REVIEWER)

    assert (entry["dismissed"], entry["overrides"]) == (1, 1)


def test_one_document_is_recognised_however_its_url_is_written():
    """DailyMed alone spells the same SPL four ways; each named a document we held."""
    setid = "e0e6412f-50b4-4fd4-9364-62818d121a07"
    spellings = [
        f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}",
        f"https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid={setid}&version=23",
        f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid.upper()}&audience=consumer",
    ]
    assert len({judge.source_key(url) for url in spellings}) == 1
    assert judge.source_key(spellings[0]) == f"dailymed:{setid}"

    assert judge.source_key("https://pubmed.ncbi.nlm.nih.gov/27959613/") == "pubmed:27959613"
    assert judge.source_key("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4924326/") == "pmc:pmc4924326"
    assert judge.source_key("https://pmc.ncbi.nlm.nih.gov/articles/PMC4924326") == "pmc:pmc4924326"
    assert judge.source_key("https://clinicaltrials.gov/study/NCT01942135") == "nct:nct01942135"


def test_a_protocol_pdf_is_not_treated_as_the_study_record():
    """Different documents. Folding them together would check a quote against text
    it was never drawn from, which is a false answer rather than an honest gap."""
    record = judge.source_key("https://clinicaltrials.gov/study/NCT02600923")
    protocol = judge.source_key("https://cdn.clinicaltrials.gov/large-docs/23/NCT02600923/Prot_000.pdf")

    assert record != protocol
    assert protocol.startswith("https://")  # unrecognised, so it stays its own URL


def test_an_unrecognised_url_is_its_own_identity():
    assert judge.source_key("https://ascopubs.org/doi/10.1200/JCO.21.01392") == "https://ascopubs.org/doi/10.1200/JCO.21.01392"
    assert judge.source_key("") == ""


def test_a_later_snapshot_adds_to_the_corpus_rather_than_replacing_it(run):
    """Resolved citations arrive as a supplementary snapshot; the label must survive."""
    before = judge.source_corpus("ibrance")
    assert LABEL["url"] in before

    extra = agent.DATA / "sources" / "ibrance" / "20260202T000000Z" / "paper"
    (extra / "raw").mkdir(parents=True)
    (extra / "manifest.json").write_text(json.dumps({
        "registry": {"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC4924326/", "title": "A paper"},
    }))
    (extra / "raw" / "fulltext.xml").write_text("<article><body><p>Palbociclib was studied.</p></body></article>")

    after = judge.source_corpus("ibrance")

    assert LABEL["url"] in after
    assert "pmc:pmc4924326" in after
    assert len(after) == len(before) + 1


def test_quote_spans_agree_with_the_score_they_illustrate(run):
    corpus = judge._norm(f"preamble {QUOTE} trailing text")
    spans = judge.quote_spans(QUOTE, corpus)
    assert all(span["present"] for span in spans)

    stitched = f"{QUOTE} Palbociclib is never associated with any haematological toxicity whatsoever here."
    spans = judge.quote_spans(stitched, corpus)
    assert [span["present"] for span in spans] == [True, False]
    assert "haematological toxicity" in spans[1]["text"]
    # The highlighting and the percentage are built from the same shingles, so a
    # reviewer reading the marks can never be shown something the score denies.
    assert 0 < judge.quote_match(stitched, corpus) < 1


def test_evidence_shows_a_fabricated_quote_as_entirely_absent(run):
    _add_a_fabricated_quote(run)
    _report(run)
    judge.promote(run)
    comment = _machine_comment(run, "quote_not_found")

    evidence = judge.evidence_for(run, comment)

    assert evidence["match_percent"] == 0
    assert evidence["spans"] and not any(span["present"] for span in evidence["spans"])
    assert evidence["passage"] == ""   # nothing matched, so there is nothing to show
    assert evidence["claim"]
    assert evidence["coverage"] == {"held": 1, "total": 1}


def _add_a_stitched_quote(run_id: str):
    """A quote that is real up to a point, then continues into text that is not."""
    stitched = f"{QUOTE} No dose interruption is required at any grade of neutropenia in practice."
    base = agent.DATA / "content" / run_id
    dossier = json.loads((base / "master" / "dossier.json").read_text())
    dossier["sections"].append({
        "id": "10_dosing", "title": "Dosing", "summary": "",
        "claims": [{"text": "Interruption is optional.", "evidence_type": "FDA label",
                    "citations": [{**LABEL, "locator": "2.2", "supporting_text": stitched}]}],
    })
    (base / "master" / "dossier.json").write_text(json.dumps(dossier))

    deck = base / "hcp" / "ppt" / "deck_spec.json"
    spec = json.loads(deck.read_text())
    spec["slides"].append({"number": 6, "title": "Dose interruption", "purpose": "Safety",
                           "content": ["Interruption is optional."],
                           "citations": [{**LABEL, "locator": "2.2"}]})
    deck.write_text(json.dumps(spec))


def test_evidence_shows_the_passage_when_the_quote_is_really_there(run):
    _add_a_stitched_quote(run)
    _report(run)
    stored = judge.stored_report(run)
    partial = next(item for item in stored["findings"] if item["check"] == "quote_not_verbatim")
    judge.promote(run, finding_ids=[judge.finding_id(partial)])

    evidence = judge.evidence_for(run, _machine_comment(run, "quote_not_verbatim"))

    assert 0 < evidence["match_percent"] < 100
    assert [span["present"] for span in evidence["spans"]] == [True, False]
    assert "No dose interruption" in evidence["spans"][1]["text"]
    assert QUOTE.split(".")[0][:40].lower() in evidence["passage"].lower()
    assert evidence["source"]["url"] == LABEL["url"]


def test_evidence_names_what_we_could_not_check(run):
    """A citation we hold no document for was never verified, and says so."""
    _report(run)
    judge.promote(run, severities=("major",))
    comment = _machine_comment(run, "promotional_only")

    evidence = judge.evidence_for(run, comment)

    assert evidence["unheld"] == ["https://www.pfizerpro.com/dosing"]
    assert evidence["coverage"] == {"held": 0, "total": 1}
    assert evidence["match_percent"] is None


def _clear_the_untraceable_slide():
    """Give the offending slide a citation the dossier actually holds."""
    deck = agent.DATA / "content" / RUN_ID / "hcp" / "ppt" / "deck_spec.json"
    spec = json.loads(deck.read_text())
    spec["slides"][3]["citations"] = [LABEL]
    deck.write_text(json.dumps(spec))


def test_a_claimed_fix_that_did_not_land_is_not_closed_into_a_version(run):
    """"Addressed" is a claim about the content, and the content can be read.

    Without this, saying a thing was fixed was enough to close it forever, and the
    defect went to the field inside a version that said it had been dealt with.
    """
    _report(run)
    judge.promote(run, severities=("blocking", "major"))
    comments = learning.course(run)["comments"]
    untraceable = next(entry for entry in comments if entry.get("check") == "untraceable")
    uncited = next(entry for entry in comments if entry.get("check") == "uncited")
    for entry in (untraceable, uncited):
        learning.resolve_comment(run, entry["id"], "addressed", "Fixed in the deck.", ADMIN)

    # Only one of the two was really fixed.
    _clear_the_untraceable_slide()
    record = learning.publish_version(run, ADMIN, "Citation repointed")

    by_id = {entry["id"]: entry for entry in record["comments"]}
    assert by_id[untraceable["id"]]["status"] == "closed"
    assert by_id[uncited["id"]]["status"] == "open"
    assert by_id[uncited["id"]]["unverified"]["check"] == "uncited"
    assert record["versions"][-1]["addressed"] == [untraceable["id"]]
    assert record["versions"][-1]["unverified"] == [uncited["id"]]
    assert [entry["action"] for entry in record["audit"]][-1] == "fix.unverified"


def test_a_version_cannot_be_cut_when_no_claimed_fix_holds_up(run):
    _report(run)
    judge.promote(run, severities=("blocking", "major"))
    for comment in learning.course(run)["comments"]:
        learning.resolve_comment(run, comment["id"], "addressed", "Fixed, honestly.", ADMIN)

    with pytest.raises(ValueError, match="None of the 3 addressed comment"):
        learning.publish_version(run, ADMIN, "Everything fixed")

    assert learning.course(run)["version"] == 1


def test_a_human_comment_is_taken_at_its_word(run):
    """There is no check behind a colleague's opinion, so there is nothing to re-run."""
    _report(run)
    comment = learning.add_comment(run, REVIEWER, "deck", "major", "Slide 3 reads awkwardly.")
    learning.resolve_comment(run, comment["id"], "addressed", "Reworded.", ADMIN)

    record = learning.publish_version(run, ADMIN, "Wording pass")

    assert record["comments"][0]["status"] == "closed"
    assert record["versions"][-1]["unverified"] == []


def test_verification_costs_one_pass_not_one_per_comment(run):
    """The index is built once; a version cut with many comments must not re-read
    the whole corpus for each of them."""
    _report(run)
    judge.promote(run, severities=("blocking", "major"))
    calls = {"n": 0}
    original = judge.deterministic_findings

    def counted(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    judge.deterministic_findings = counted
    try:
        addressed = learning.course(run)["comments"]
        for comment in addressed:
            learning.resolve_comment(run, comment["id"], "addressed", "Fixed.", ADMIN)
        calls["n"] = 0
        _clear_the_untraceable_slide()
        learning.publish_version(run, ADMIN, "Batch")
    finally:
        judge.deterministic_findings = original

    assert len(addressed) > 2
    assert calls["n"] == len(judge.failing_now.__defaults__[0])  # one pass per track


def test_an_override_is_stamped_on_the_published_course(run):
    _report(run)
    judge.promote(run)
    for comment in [entry for entry in learning.course(run)["comments"] if entry["status"] == "open"]:
        learning.resolve_comment(run, comment["id"], "dismissed", "Reviewed.", REVIEWER,
                                 override_reason="Accepted risk, signed by the TA lead.")
    learning.add_signoff(run, REVIEWER, "approved")

    record = learning.publish_course(run, ADMIN, "2026-09-01", "2026-09-30", ["ken-osei"])

    overrides = record["publication"]["overrides"]
    assert overrides and all(entry["actor_name"] == "Dr. Anil Shekhar" for entry in overrides)
    assert all(entry["check"] in judge.DETERMINISTIC_CHECKS for entry in overrides)


# --- Repointing a bad citation -------------------------------------------------

def test_repoint_reaches_every_asset_the_checker_inspects():
    """`units()` and `ASSET_FILE` have to name units identically.

    A repoint that cannot find the unit a finding names does nothing and reports
    nothing, so the two id schemes drifting apart is silent. FAQ entries were the
    ones missing: they carry no id of their own and are addressed by position.
    """
    assert set(judge.ASSET_FILE) == {"deck", "quiz", "storyboard", "faq"}

    samples = {
        "deck": ({"number": 6}, 1, "deck-6"),
        "quiz": ({"id": "q2"}, 1, "quiz-q2"),
        "storyboard": ({"id": 3}, 1, "scene-3"),
        "faq": ({"question": "anything"}, 3, "faq-3"),
    }
    for asset, (entry, index, expected) in samples.items():
        _folder, _name, _collection, make_id = judge.ASSET_FILE[asset]
        assert make_id(entry, index) == expected, asset


def test_only_document_findings_offer_a_repoint():
    """An overreach is a wording problem; citing something else does not fix it."""
    assert "quote_not_found" in judge.REPOINTABLE
    assert "untraceable" in judge.REPOINTABLE
    assert "overreach" not in judge.REPOINTABLE
    assert "imprecise_effect" not in judge.REPOINTABLE
    assert "under_cited" not in judge.REPOINTABLE


def test_a_human_comment_names_no_citation_to_repoint(run):
    comment = learning.add_comment(run, "anil-shekhar", "deck", "major", "Too strong.")
    with pytest.raises(ValueError, match="automated finding"):
        judge.repoint_comment(run, comment["id"], "priya-raman")


def test_repointing_a_wording_finding_is_refused(run):
    """Citing a different document cannot fix a sentence that overstates its evidence."""
    _report(run)
    judge.promote(run)
    record = learning.course(run)
    comment = next(entry for entry in record["comments"] if entry["origin"] == "automated_check")
    comment["check"] = "overreach"
    learning._save_course(record)

    with pytest.raises(ValueError, match="rewritten"):
        judge.repoint_comment(run, comment["id"], "priya-raman")


def test_only_an_admin_repoints(run):
    _report(run)
    judge.promote(run)
    comment = next(entry for entry in learning.course(run)["comments"]
                   if entry["origin"] == "automated_check")
    with pytest.raises(ValueError, match="Only an admin"):
        judge.repoint_comment(run, comment["id"], "anil-shekhar")


def test_agreement_withholds_a_rate_until_there_is_a_sample(run):
    """One dismissal is a count of one, not a 0% verdict on the checker.

    The per-reviewer split already applied this floor; the headline did not, so a
    single override rendered the checker as having no agreement at all.
    """
    _report(run)
    judge.promote(run)
    comment = next(entry for entry in learning.course(run)["comments"]
                   if entry["origin"] == "automated_check")
    learning.resolve_comment(run, comment["id"], "dismissed", "Not material.", "anil-shekhar",
                             override_reason="Checked by hand.")

    result = judge.agreement(run)
    assert result["settled"] == 1
    assert result["dismissed"] == 1
    assert result["agreement_percent"] is None, "a rate from one finding is not a rate"


def test_a_repoint_clears_the_check_that_reopened_the_comment(run):
    """The whole arc: a claimed fix reopens, a repoint makes it true, the next version closes it.

    Each half of this is covered on its own — a dismissal is challenged, an
    unverified fix is reopened, a repoint rewrites the asset — but nothing proved
    they compose. If the repoint wrote a citation the checker does not then accept,
    a comment could reopen at every version cut with no way to ever settle it
    honestly, and the only route left would be an override.
    """
    _report(run)
    judge.promote(run, severities=("blocking", "major"))
    comment = next(entry for entry in learning.course(run)["comments"]
                   if entry.get("check") == "promotional_only")

    # A version needs at least one fix that holds up, so a human comment rides
    # along — it has no check behind it and is taken at its word.
    human = learning.add_comment(run, REVIEWER, "deck", "major", "Add the line-of-therapy context.")
    learning.resolve_comment(run, human["id"], "addressed", "Slide added.", ADMIN)

    # Claimed, not done: the check still fails, so the version cut hands it back.
    learning.resolve_comment(run, comment["id"], "addressed", "Reworded the slide.", ADMIN)
    record = learning.publish_version(run, ADMIN, "First pass")
    assert next(e for e in record["comments"] if e["id"] == human["id"])["status"] == "closed"
    reopened = next(entry for entry in record["comments"] if entry["id"] == comment["id"])
    assert reopened["status"] == "open"
    assert reopened["unverified"]["check"] == "promotional_only"

    # Repointed to a document the corpus actually holds, and now it is true.
    moved = judge.repoint_comment(run, comment["id"], "priya-raman")
    assert moved["url"] == LABEL["url"]
    assert comment["id"] not in judge.failing_now(run)

    learning.resolve_comment(run, comment["id"], "addressed", "Repointed to the label.", ADMIN)
    record = learning.publish_version(run, ADMIN, "Citation repointed to the label")
    closed = next(entry for entry in record["comments"] if entry["id"] == comment["id"])
    assert closed["status"] == "closed"
    assert closed["closed_in_version"] == record["version"]
    assert "unverified" not in closed
    assert record["versions"][-1]["unverified"] == []

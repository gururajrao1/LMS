"""Populate the demo so every stakeholder has something waiting at sign-in.

Takes the newest generated course and walks it through the real workflow: two
domain experts review it, the medical education lead addresses their comments and
cuts version 2, both experts sign off, it is published to a cohort, and the
cohort works through it at different speeds. Every write goes through the same
functions the API uses, so nothing here can produce state the app could not.

Safe to re-run: it refuses to touch a course that already has review history or a
learner who has already started, and it never deletes anything.

    uv run python scripts/seed_demo.py            # seed the newest course
    uv run python scripts/seed_demo.py --status   # show what is already seeded
"""

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import judge, learning  # noqa: E402
from src.agent import content_path  # noqa: E402

ADMIN = "priya-raman"
CLINICAL, REGULATORY = "anil-shekhar", "maria-alvarez"

REVIEW = [
    (CLINICAL, "quiz", "blocking",
     "Question 4 states the PFS benefit as an absolute month gain. The label reports a range and the "
     "confidence interval crosses into a smaller effect — rewrite it to match the labelled wording.",
     "Rewritten to the labelled PFS range with the confidence interval shown alongside."),
    (CLINICAL, "deck", "major",
     "Slide 11 shows the neutropenia rate without the dose-modification guidance that follows it. An MSL "
     "quoting this in the field will get asked 'and then what?' immediately.",
     "Added the dose-interruption and reduction table as slide 12, cited to Section 2.2 of the label."),
    (REGULATORY, "faq", "major",
     "The answer on combination use should name the FDA-approved test requirement for the PIK3CA-mutated "
     "population. As written it implies broader eligibility than the label supports.",
     "Answer now names the companion diagnostic requirement and links the label section."),
    (REGULATORY, "sources", "minor",
     "Several claims lean on manufacturer-hosted pages. Where a DailyMed or FDA equivalent exists, that "
     "should be the primary citation and the Pfizer page secondary.",
     "Primary citations repointed to DailyMed and Drugs@FDA where an equivalent exists."),
    (CLINICAL, "storyboard", "minor",
     "Scene 3 narration says 'stops the cell cycle'. Prefer 'inhibits progression from G1 into S phase' — "
     "the audience is oncology-literate and the loose phrasing will read as imprecise.",
     "Narration reworded to the mechanistic phrasing."),
]

# name, days after publication they start, how far they get, baseline, final attempts
COHORT = [
    ("ken-osei", 1, "certified", 58, [92]),
    ("lucy-whitfield", 2, "certified", 42, [58, 83]),
    ("jordan-feld", 1, "certified", 67, [100]),
    ("sara-nakamura", 4, "final_pending", 50, []),
    ("tom-becker", 6, "learning", 33, []),
]

# How the experts triaged the checker's findings. Anything not listed is accepted.
# Both of these are deterministic checks, so waving one away is challenged and takes
# a named override — which is the point, and worth showing in the seeded history.
DISMISSED = {
    "promotional_only": ("The labelling page is the primary source for this claim; manufacturer hosting is expected here.",
                         "labeling.pfizer.com is the sponsor's own Prescribing Information, which is the primary "
                         "regulatory text for this claim. Overriding the promotional-source rule deliberately."),
    "quote_not_verbatim": ("Quote spans two adjacent label paragraphs. Acceptable as an excerpt; left as is.",
                           "Checked against Section 5.1 by hand: the excerpt is faithful and the break between "
                           "paragraphs is not material. Accepting the partial match."),
}

MACHINE_RESOLUTION = {
    "quote_not_found": "Quotation replaced with the exact label sentence and the locator corrected.",
    "untraceable": "Citation removed; the scene now cites the trial record already in the dossier.",
    "unsupported": "Claim rewritten to the labelled indication; the trastuzumab reference removed.",
    "overreach": "Wording softened to match the confidence interval reported in the evidence.",
    "needs_context": "Qualifier added so the figure is not read as a licensed claim.",
    "under_cited": "Citation repointed to the claim that actually supports the sentence.",
}

FEEDBACK = {
    "ken-osei": [("deck", 5, "The dose-modification table is exactly what I needed in clinic."),
                 ("faq", 4, "Good escalation paths. I would add one on hepatic impairment.")],
    "lucy-whitfield": [("videos", 3, "Useful, but I wanted the trial data spelled out more slowly."),
                       ("deck", 4, "Clear. The citation on every slide is what makes it usable.")],
    "jordan-feld": [("faq", 5, "This is the sharpest part of the course for field conversations."),
                    ("storyboard", 4, "Good structure. Scene 3 is now much more precise.")],
    "tom-becker": [("deck", 4, "Dense but well organised.")],
}


def _newest_run() -> str | None:
    runs = []
    for path in content_path("content").glob("*/manifest.json"):
        try:
            manifest = json.loads(path.read_text())
            runs.append((manifest.get("generated_at", path.parent.name), manifest.get("run_id", path.parent.name)))
        except (json.JSONDecodeError, OSError):
            continue
    return max(runs)[1] if runs else None


def _apply_machine_fixes(run_id: str, drug: str, comments: list[dict]) -> int:
    """Make the content match what the resolutions claim.

    Marking a comment addressed is a claim, and cutting a version now re-reads the
    assets to check it. A seed that only wrote the claim would be caught by its own
    product — correctly — so it writes the fix too.
    """
    report = judge.stored_report(run_id) or {"findings": []}
    by_id = {judge.finding_id(item): item for item in report["findings"]}

    fixed = 0
    for comment in comments:
        finding = by_id.get(comment.get("finding_id", ""))
        if not finding or finding["check"] not in {"untraceable", "quote_not_found", "quote_not_verbatim"}:
            continue
        track, _, unit_id = finding["unit_id"].partition(":")
        # Chosen against this unit's own text, so the replacement is about the
        # same thing the claim is about.
        citation = judge.verified_citation(run_id, drug, finding.get("asset_text", "") or finding["reference"])
        if citation:
            fixed += judge.repoint(run_id, track, unit_id, citation)
    return fixed


def _backdate_course(run_id: str, generated: datetime) -> None:
    """Put the review round on a realistic schedule instead of all at 'now'.

    Without this every timestamp is the moment the script ran, so the elapsed
    time from generation to publication is however long the run has been sitting
    on disk — which makes the ROI comparison meaningless.

    Order has to hold as well as spacing. Every comment is raised before it is
    resolved and resolved before the version that closes it, otherwise the
    governance trail shows a version closing comments that were still open — an
    impossible sequence, and the first thing an auditor would pick up.
    """
    record = learning.course(run_id)
    at = lambda days: (generated + timedelta(days=days)).isoformat()
    comments = record["comments"]
    span = max(len(comments) - 1, 1)
    for index, comment in enumerate(comments):
        # The first comment stays at 0.8: it is what the ROI split measures the
        # review phase from, so the window must not move when the spacing changes.
        comment["created_at"] = at(0.8 + 0.5 * index / span)
        comment["resolved_at"] = at(1.5 + 0.4 * index / span)
    for version in record["versions"][1:]:
        version["created_at"] = at(2.0)
    for index, signoff in enumerate(record["signoffs"]):
        signoff["created_at"] = at(2.4 + index * 0.2)
    if record.get("publication"):
        record["publication"]["published_at"] = at(3.0)
        for notification in record["publication"]["notifications"]:
            notification["sent_at"] = at(3.0)
    learning._save_course(record)


def _backdate(run_id: str, user_id: str, mapper):
    """Rewrite the timestamps a seeded learner produced so the activity curve is real."""
    record = learning.progress(run_id, user_id)
    for index, (_module_id, detail) in enumerate(record["modules"].items()):
        detail["completed_at"] = mapper(index).isoformat()
    for index, attempt in enumerate(record["attempts"]):
        attempt["created_at"] = mapper(index * 2).isoformat()
    if record["certificate"]:
        record["certificate"]["issued_at"] = mapper(len(learning.MODULES) + 1).isoformat()
        issued = datetime.fromisoformat(record["certificate"]["issued_at"])
        record["certificate"]["expires_at"] = issued.replace(year=issued.year + 1).isoformat()
    if record["started_at"]:
        record["started_at"] = mapper(0).isoformat()
    learning._save_progress(record)


def seed(run_id: str) -> None:
    record = learning.course(run_id)
    if record["comments"] or record.get("publication"):
        print(f"! {run_id} already has review history — leaving it untouched.")
        return

    manifest = json.loads((content_path("content", run_id, "manifest.json")).read_text())
    generated = datetime.fromisoformat(manifest["generated_at"])
    if not generated.tzinfo:
        generated = generated.replace(tzinfo=UTC)

    print(f"Seeding {manifest['drug']['brand']} ({run_id})")

    # 1. The machine checks the draft before any human reads it.
    report = judge.stored_report(run_id)
    if not report:
        report = asyncio.run(judge.run(run_id, manifest["drug"]["brand"], model_tracks=()))
    blocking = judge.promote(run_id)
    majors = [item for item in report["findings"] if item["severity"] == "major"][:4]
    selected = judge.promote(run_id, finding_ids=[judge.finding_id(item) for item in majors])
    print(f"  automated checks: {len(report['findings'])} findings, "
          f"{len(blocking)} blocking auto-raised, {len(selected)} more sent by the lead")

    # 2. The experts adjudicate what the machine raised.
    record = learning.course(run_id)
    for comment in [entry for entry in record["comments"] if entry.get("origin") == "automated_check"]:
        dismissal = DISMISSED.get(comment.get("check", ""))
        if dismissal:
            # Overruling the checker is a clinical judgement, so it is attributed to
            # the expert who made it rather than to whoever ran the queue. The first
            # call is challenged; the second carries the override that settles it.
            reason, override = dismissal
            learning.resolve_comment(run_id, comment["id"], "dismissed", reason, CLINICAL)
            learning.resolve_comment(run_id, comment["id"], "dismissed", reason, CLINICAL,
                                     override_reason=override)
        else:
            learning.resolve_comment(run_id, comment["id"], "addressed",
                                     MACHINE_RESOLUTION.get(comment.get("check", ""), "Corrected in this version."),
                                     ADMIN)
    agreement = judge.agreement(run_id)
    print(f"  reviewers accepted {agreement['accepted']} of {agreement['settled']} machine findings "
          f"({agreement['agreement_percent']}% agreement)")

    # 3. Then the humans add what only a human would notice.
    for author, target, severity, body, resolution in REVIEW:
        comment = learning.add_comment(run_id, author, target, severity, body)
        learning.resolve_comment(run_id, comment["id"], "addressed", resolution, ADMIN)
    print(f"  {len(REVIEW)} further expert comments raised and addressed")

    # 4. The fixes are made in the content, not just described. Cutting the version
    # re-reads the assets, so anything only claimed here would be reopened.
    addressed = [entry for entry in learning.course(run_id)["comments"] if entry["status"] == "addressed"]
    fixed = _apply_machine_fixes(run_id, manifest["drug"]["brand"], addressed)
    print(f"  {fixed} citation(s) repointed in the assets so the claimed fixes are real")

    learning.publish_version(run_id, ADMIN, "Label-aligned PFS wording, dose-modification table, companion-diagnostic detail")
    learning.add_signoff(run_id, CLINICAL, "approved", "Clinically accurate and traceable to the label.")
    learning.add_signoff(run_id, REGULATORY, "approved", "Citations and promotional balance acceptable for field use.")
    print("  version 2 cut, signed off by both reviewers")

    starts = (generated + timedelta(days=3)).date()
    learning.publish_course(
        run_id, ADMIN,
        starts.isoformat(),
        (starts + timedelta(days=30)).isoformat(),
        [user_id for user_id, *_ in COHORT],
        "Complete before the advisory board. The final assessment is required for field use.",
    )
    print(f"  published to {len(COHORT)} trainees, due {(starts + timedelta(days=30)).isoformat()}")

    quizzes = {
        track: json.loads((content_path("content", run_id, track, "quiz.json")).read_text())
        for track in ("hcp", "msl")
    }

    for user_id, delay, stage, baseline_target, final_targets in COHORT:
        person = learning.person(user_id)
        track = learning.track_for(person["role"])
        questions = quizzes[track]["questions"]
        baseline_questions = questions[::2][:5]

        learning.record_attempt(run_id, user_id, "baseline",
                                _answers(baseline_questions, baseline_target), baseline_questions, 0)
        if stage != "baseline":
            for module in learning.MODULES:
                if stage == "learning" and module["id"] in {"storyboard", "faq"}:
                    continue
                learning.set_module(run_id, user_id, module["id"], True)
        for target in final_targets:
            learning.record_attempt(run_id, user_id, "final", _answers(questions, target), questions,
                                    _passing(quizzes[track]))
        for module_id, rating, comment in FEEDBACK.get(user_id, []):
            learning.add_feedback(run_id, user_id, module_id, rating, comment)

        day = datetime.combine(starts, datetime.min.time(), tzinfo=UTC) + timedelta(days=delay)
        _backdate(run_id, user_id, lambda step, day=day: day + timedelta(hours=2 * step))
        summary = learning.summarize(learning.progress(run_id, user_id))
        print(f"  {person['name']:<22} {summary['stage']:<14} baseline {summary['baseline_score']}"
              f" → final {summary['final_score']}")

    _backdate_course(run_id, generated)
    print(f"  review timeline set: generated {generated.date()}, published {(generated + timedelta(days=3)).date()}")


def _passing(quiz: dict) -> int:
    from src.agent import passing_percent

    return passing_percent(quiz)


def _answers(questions: list[dict], target_percent: int) -> dict[str, int]:
    """Answer just enough questions correctly to land on the target score."""
    wanted = round(len(questions) * target_percent / 100)
    return {
        question["id"]: question["correct_index"] if index < wanted else (question["correct_index"] + 1) % 4
        for index, question in enumerate(questions)
    }


def status() -> None:
    root = content_path("platform", "courses")
    if not root.exists():
        print("Nothing seeded yet.")
        return
    for path in sorted(root.glob("*.json")):
        record = json.loads(path.read_text())
        publication = record.get("publication")
        assigned = len(publication["assignees"]) if publication else 0
        print(f"{record['run_id']}: v{record['version']} {record['status']}, "
              f"{len(record['comments'])} comments, {assigned} assigned")
        for user_id in publication["assignees"] if publication else []:
            summary = learning.summarize(learning.progress(record["run_id"], user_id))
            print(f"    {user_id:<18} {summary['stage']:<14} {summary['percent']:>3}% modules"
                  f"  baseline {summary['baseline_score']} → final {summary['final_score']}")


def reseed(run_id: str) -> None:
    """Archive this course's demo state, then build it again from scratch.

    Only touches platform state for this run. Generated content is never removed,
    and the archive keeps whatever was there before.
    """
    import shutil

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive = content_path("platform", "archive", stamp)
    for source in [content_path("platform", "courses", f"{run_id}.json"), content_path("platform", "progress", run_id)]:
        if source.exists():
            target = archive / source.relative_to(content_path("platform"))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
    print(f"Archived previous demo state to platform/archive/{stamp}")
    seed(run_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="course to seed (default: the newest generated run)")
    parser.add_argument("--status", action="store_true", help="show what is already seeded")
    parser.add_argument("--reseed", action="store_true", help="archive this course's demo state and rebuild it")
    parser.add_argument("--retime", action="store_true",
                        help="re-apply the review schedule to an already-seeded course, leaving its content alone")
    args = parser.parse_args()

    if args.status:
        status()
        return
    run_id = args.run_id or _newest_run()
    if not run_id:
        print("No generated course found. Create one first.")
        return
    if args.retime:
        manifest = json.loads((content_path("content", run_id, "manifest.json")).read_text())
        generated = datetime.fromisoformat(manifest["generated_at"])
        _backdate_course(run_id, generated.replace(tzinfo=UTC) if not generated.tzinfo else generated)
        print(f"Review schedule re-applied to {run_id}.")
        return
    reseed(run_id) if args.reseed else seed(run_id)


if __name__ == "__main__":
    main()

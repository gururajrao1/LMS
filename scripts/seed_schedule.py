"""Add training cycles around the live course, so a trainee's schedule has shape.

A learner assigned one course only ever sees one state, which makes the schedule
view impossible to read: there is no "upcoming", nothing overdue, nothing behind
them. This stands up the cycles a medical affairs team actually runs for a single
drug — annual recertification, a safety refresher, a label-update briefing — each
with its own dates and its own cohort progress.

Same drug, same content, different cycles. Nothing here invents a product: a card
labelled Eliquis over palbociclib material would be exactly the kind of quiet
untruth the rest of this system exists to catch. What differs is the schedule and
who finished, which is what the schedule view is for.

Heavy asset folders are symlinked rather than copied — the content is genuinely the
same 103MB, and three copies of it would be storage spent on saying so.

Safe to re-run: a cycle that already exists is left alone, and nothing is deleted.

    uv run python scripts/seed_schedule.py --status
    uv run python scripts/seed_schedule.py
    uv run python scripts/seed_schedule.py --remove   # take the cycles back out
"""

import argparse
import asyncio
import json
import shutil
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.seed_demo as seed_demo  # noqa: E402
from src import agent, judge, learning  # noqa: E402
from src.agent import content_path  # noqa: E402

ADMIN = "priya-raman"
CLINICAL, REGULATORY = "anil-shekhar", "maria-alvarez"

# Offsets are relative to today, so the demo reads the same whenever it is run.
CYCLES = [
    {
        "id": "recert-2026",
        "title": "Annual recertification",
        "starts": -168, "runs": 45,
        "summary": "Yearly sign-off that the field team is current on the label.",
        "outcome": "certified",
    },
    {
        "id": "safety-refresher",
        "title": "Safety refresher: neutropenia management",
        "starts": -77, "runs": 44,
        "summary": "Called after a safety signal review. Dose modification and monitoring.",
        "outcome": "started",
        # The sort board lives here rather than on the live course. A refresher on
        # dose modification is what the board actually tests, and this cycle has a
        # checks report of its own — running the checker over the new questions on
        # the live course would overwrite the record of what was caught on its draft.
        "board": True,
    },
    {
        "id": "label-update",
        "title": "Label update briefing",
        "starts": 29, "runs": 30,
        "summary": "Scheduled ahead of the next Prescribing Information revision.",
        "outcome": "none",
    },
]

# Symlinked: identical between cycles and large. Copied: small and cycle-specific.
LINKED = ("hcp", "msl", "assets", "master", "context.json")
COPIED = ("learning_blueprint.json", "source_manifest.json")


def _source_run() -> str:
    published = [record for record in learning.published_courses()]
    if not published:
        raise SystemExit("No published course to build cycles around. Run seed_demo.py first.")
    return published[0]["run_id"]


def _run_id(cycle: dict) -> str:
    return f"ibrance-cycle-{cycle['id']}"


def _own_track(origin: Path, root: Path, track: str) -> None:
    """Give this cycle its own copy of a track, minus the video files.

    A cycle that changes its assessment cannot share the folder it changes. The
    videos are the 100MB and they are untouched, so they stay symlinked.
    """
    (root / track).mkdir(parents=True)
    for entry in (origin / track).iterdir():
        if entry.name == "videos":
            (root / track / entry.name).symlink_to(entry)
        elif entry.is_dir():
            shutil.copytree(entry, root / track / entry.name)
        else:
            shutil.copy2(entry, root / track / entry.name)


def _add_formats(root: Path, drug: str, track: str) -> int:
    """Fold every gamified format the library holds into this cycle's quiz.

    Returns the number of questions added. A format the library does not have is
    simply skipped: they are optional by construction, and a cycle built before
    one existed stays valid.
    """
    quiz_path = root / track / "quiz.json"
    quiz = json.loads(quiz_path.read_text())
    before = len(quiz["questions"])
    groups, figures = [], []
    for kind, group_kind in agent.GAMIFIED.items():
        source = content_path("library", drug, track, f"{kind}.json")
        if not source.exists():
            continue
        asset = json.loads(source.read_text())
        (root / track / f"{kind}.json").write_text(json.dumps(asset, indent=2) + "\n")
        if group_kind:
            groups.append({"id": agent._slug(asset["title"])[:40], "kind": group_kind, **asset})
        else:
            figures += asset["questions"]
    if not groups and not figures:
        return 0
    folded = agent.fold_groups(quiz, groups, figures)
    quiz_path.write_text(json.dumps(folded, indent=2) + "\n")
    return len(folded["questions"]) - before


def _build_content(source: str, run_id: str, cycle: dict, generated: date) -> None:
    root = content_path("content", run_id)
    if root.exists():
        return
    origin = content_path("content", source)
    root.mkdir(parents=True)
    tracks = ("hcp", "msl") if cycle.get("board") else ()
    for name in LINKED:
        if name not in tracks:
            (root / name).symlink_to(origin / name)
    for name in COPIED:
        shutil.copy2(origin / name, root / name)
    drug = agent._slug(json.loads((origin / "manifest.json").read_text())["drug"]["brand"])
    for track in tracks:
        _own_track(origin, root, track)
        added = _add_formats(root, drug, track)
        print(f"    {track}: +{added} gamified question(s)")

    manifest = json.loads((origin / "manifest.json").read_text())
    manifest.update({
        "run_id": run_id,
        "generated_at": datetime.combine(generated, datetime.min.time(), tzinfo=UTC).isoformat(),
        # The drug is untouched. The cycle is what this programme is, and it is
        # carried separately so nothing ever has to misname the medicine.
        "program_title": cycle["title"],
        "program_summary": cycle["summary"],
        # This cycle runs content that was already built, researched and approved.
        # Saying so keeps the portfolio from counting one build four times.
        "reuses": source,
    })
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    log = content_path("logs", run_id, "run.json")
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(json.dumps({
        "id": run_id, "mode": "local",
        "created_at": datetime.combine(generated - timedelta(days=3), datetime.min.time(), tzinfo=UTC).isoformat(),
    }, indent=2) + "\n")


def _check(run_id: str, drug: str) -> list[dict]:
    """Run the checker over this cycle's own assets and raise what blocks.

    Deterministic checks only, and the report says so. Those are the checks that
    matter for new questions — is it cited, is the citation traceable, is the
    quoted text really in the document — and they cost nothing, so a cycle that
    changes its content is never published against a report of someone else's.
    """
    report = asyncio.run(judge.run(run_id, drug, model_tracks=()))
    raised = judge.promote(run_id)
    board = [finding for finding in report["findings"] if finding["asset"] == "quiz"]
    print(f"    checked: {len(report['findings'])} finding(s), {len(raised)} raised into review "
          f"({len(board)} on quiz questions)")
    return raised


def _settle_checks(run_id: str, drug: str) -> None:
    """Clear what the checker raised, the way a reviewer would have to.

    A blocking finding is either genuinely fixed in the content or waved through
    by a named person with a reason. There is no third option, and cutting the
    version re-reads the assets to confirm the first kind really landed — so the
    citations here are actually repointed, not just described as repointed.
    """
    from scripts.seed_demo import _repoint, _verified_citation

    findings = {judge.finding_id(item): item for item in (judge.stored_report(run_id) or {"findings": []})["findings"]}
    fixed = 0
    open_checks = [comment for comment in learning.course(run_id)["comments"]
                   if comment["status"] == "open" and comment["author_id"] == learning.CHECKER["id"]]

    for comment in open_checks:
        finding = findings.get(comment.get("finding_id", ""))
        track, _, unit_id = (finding or {}).get("unit_id", "").partition(":")
        # Whether the repoint landed, per comment — not a count matched back to
        # positions. Only some assets can be repointed at all, so "three were
        # fixed" says nothing about *which* three, and marking the wrong ones
        # addressed is a claim the version cut then correctly refuses.
        citation = _verified_citation(
            run_id, drug, (finding or {}).get("asset_text", "") or (finding or {}).get("reference", ""))
        landed = bool(citation and finding and _repoint(run_id, track, unit_id, citation))
        if landed:
            fixed += 1
            learning.resolve_comment(run_id, comment["id"], "addressed",
                                     "Citation repointed to a source claim whose quote verifies.", ADMIN)
        else:
            # Already adjudicated on the course this cycle reuses, and the content
            # is unchanged here — an override with a reason, not a re-argument.
            learning.resolve_comment(run_id, comment["id"], "dismissed",
                                     "Carried over from the approved parent course; content unchanged.", ADMIN,
                                     override_reason="Adjudicated on the parent course; this cycle reuses it verbatim.")
    print(f"    settled: {fixed} fixed in the content, {len(open_checks) - fixed} overridden on the record")


def _review_and_publish(run_id: str, cycle: dict, starts: date, cohort: list[str]) -> None:
    comment = learning.add_comment(
        run_id, CLINICAL, "deck", "major",
        f"Confirm the {cycle['title'].lower()} still matches the current Prescribing Information "
        "before this cycle opens.")
    learning.resolve_comment(run_id, comment["id"], "addressed",
                             "Checked against the current label; no wording changes needed.", ADMIN)
    learning.publish_version(run_id, ADMIN, f"{cycle['title']} cycle")
    learning.add_signoff(run_id, CLINICAL, "approved", "Clinically current for this cycle.")
    learning.add_signoff(run_id, REGULATORY, "approved", "Citations and balance unchanged.")
    learning.publish_course(run_id, ADMIN, starts.isoformat(),
                            (starts + timedelta(days=cycle["runs"])).isoformat(), cohort, cycle["summary"])


def _quiz(run_id: str, track: str) -> dict:
    return json.loads((content_path("content", run_id, track, "quiz.json")).read_text())


def _progress(run_id: str, user_id: str, outcome: str, finished: date) -> None:
    """Put a learner where this cycle says they should be."""
    if outcome == "none":
        return
    track = learning.track_for((learning.person(user_id) or {}).get("role", "hcp"))
    quiz = _quiz(run_id, track)
    questions = quiz["questions"]
    passing = quiz.get("passing_score", 75)

    # A believable baseline: they already knew some of it. Deterministic per learner,
    # so re-running does not reshuffle the cohort's numbers — and never zero, which
    # would make the uplift look manufactured rather than measured.
    offset = sum(ord(character) for character in user_id)
    known = {question["id"] for index, question in enumerate(questions) if (index + offset) % 5 < 2}
    right = {question["id"]: question["correct_index"] for question in questions}
    baseline = {
        question["id"]: (question["correct_index"] if question["id"] in known
                         else (question["correct_index"] + 1) % len(question["options"]))
        for question in questions
    }
    learning.record_attempt(run_id, user_id, "baseline", baseline, questions, passing)

    if outcome == "started":
        for module in learning.MODULES[:2]:
            learning.set_module(run_id, user_id, module["id"], True)
        return

    for module in learning.MODULES:
        learning.set_module(run_id, user_id, module["id"], True)
    learning.record_attempt(run_id, user_id, "final", right, questions, passing)
    learning.issue_certificate(run_id, user_id)

    # Put the cycle's activity inside the cycle, not on the day the script ran.
    record = learning.progress(run_id, user_id)
    for index, attempt in enumerate(record["attempts"]):
        attempt["created_at"] = datetime.combine(
            finished - timedelta(days=6 - index * 3), datetime.min.time(), tzinfo=UTC).isoformat()
    if record.get("certificate"):
        record["certificate"]["issued_at"] = datetime.combine(
            finished, datetime.min.time(), tzinfo=UTC).isoformat()
    learning._save_progress(record)


def _selected(only: str) -> list[dict]:
    """Rebuilding one cycle should not disturb the other two."""
    if not only:
        return CYCLES
    chosen = [cycle for cycle in CYCLES if cycle["id"] == only]
    if not chosen:
        raise SystemExit(f"Unknown cycle {only!r}. Known: {', '.join(cycle['id'] for cycle in CYCLES)}")
    return chosen


def status() -> None:
    for cycle in CYCLES:
        run_id = _run_id(cycle)
        record = learning.course(run_id)
        state = record.get("status", "absent") if content_path("content", run_id).exists() else "absent"
        print(f"  {cycle['title']:<44} {state}")


def remove(only: str = "") -> None:
    """Take the cycles back out, leaving the real course untouched."""
    for cycle in _selected(only):
        run_id = _run_id(cycle)
        for path in (content_path("content", run_id), content_path("logs", run_id),
                     content_path("platform", "progress", run_id)):
            if path.is_symlink() or path.exists():
                shutil.rmtree(path, ignore_errors=True) if path.is_dir() else path.unlink()
        for path in (content_path("platform", "courses", f"{run_id}.json"), judge.report_path(run_id)):
            path.unlink(missing_ok=True)
        print(f"  removed {cycle['title']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="show which cycles exist")
    parser.add_argument("--remove", action="store_true", help="delete the cycles this script created")
    parser.add_argument("--only", default="", help="act on one cycle by id, leaving the others alone")
    args = parser.parse_args()

    if args.status:
        status()
        return 0
    if args.remove:
        remove(args.only)
        return 0

    source = _source_run()
    cohort = learning.course(source)["publication"]["assignees"]
    today = date.today()
    print(f"Building cycles around {source} for {len(cohort)} trainee(s)")

    for cycle in _selected(args.only):
        run_id = _run_id(cycle)
        starts = today + timedelta(days=cycle["starts"])
        if learning.course(run_id).get("publication"):
            print(f"= {cycle['title']} already published — left alone.")
            continue

        # Content is built before a cycle runs, never after — and never in the
        # future. A briefing scheduled for next month was still written this week,
        # so an upcoming cycle generates from today rather than from its own start
        # date. Left unclamped it dated itself forward, which made it permanently
        # the newest course on the dashboard and gave the ROI panel a negative
        # elapsed time to divide by.
        generated = min(starts, date.today()) - timedelta(days=4)
        _build_content(source, run_id, cycle, generated)
        if cycle.get("board"):
            drug = json.loads(content_path("content", source, "manifest.json").read_text())["drug"]["brand"]
            _check(run_id, drug)
            _settle_checks(run_id, drug)
        _review_and_publish(run_id, cycle, starts, cohort)
        # Every review timestamp is otherwise the moment this script ran, so the
        # measured build-to-publish time is however long the repo has been sitting
        # on disk. seed_demo wrote this helper for exactly that; the cycles need it
        # just as much.
        seed_demo._backdate_course(
            run_id, datetime.combine(generated, datetime.min.time(), tzinfo=UTC))
        due = starts + timedelta(days=cycle["runs"])
        for user_id in cohort:
            _progress(run_id, user_id, cycle["outcome"], min(due, today) - timedelta(days=2))
        print(f"+ {cycle['title']:<44} {starts} to {due}  ({cycle['outcome']})")

    print("\nDone. Sign in as a trainee to see the schedule.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

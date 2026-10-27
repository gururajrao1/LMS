"""Get a freshly published course ready for the learner act of the demo.

Act 4 needs two things the publish step does not produce. A cohort: four
colleagues at different points, so the live learner is not the only row in the
analytics and the uplift number has something to average against. And an answer
key, because the final assessment is thirty-odd questions and nobody is reading
a JSON file on stage.

The live learner is left with a baseline attempt and nothing else — the whole
point of the act is watching one person go from baseline to certificate in front
of the room, and any module ticked here is a beat taken away from that.

Every write goes through the same functions the API uses, so this cannot produce
state the app could not.

    uv run python scripts/demo_prep.py cohort <run-id>
    uv run python scripts/demo_prep.py answers <run-id>
    uv run python scripts/demo_prep.py answers <run-id> --score 88
"""

import argparse
import json
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import learning  # noqa: E402
from src.agent import content_path  # noqa: E402

LIVE_LEARNER = "ken-osei"

# Who else is on the course, how far in they started, where they got to, and what
# they scored. Spread deliberately: one certified early, one who needed two goes,
# one sitting on a finished course they have not submitted, one still reading.
# Analytics with five identical rows demonstrates nothing.
COHORT = [
    ("lucy-whitfield", 2, "certified", 42, [58, 83]),
    ("jordan-feld", 1, "certified", 67, [100]),
    ("sara-nakamura", 4, "final_pending", 50, []),
    ("tom-becker", 6, "learning", 33, []),
]

FEEDBACK = {
    "lucy-whitfield": [("videos", 3, "Useful, but I wanted the trial data spelled out more slowly."),
                       ("deck", 4, "Clear. The citation on every slide is what makes it usable.")],
    "jordan-feld": [("faq", 5, "This is the sharpest part of the course for field conversations."),
                    ("storyboard", 4, "Good structure, and scene 3 is precise about the mechanism.")],
    "tom-becker": [("deck", 4, "Dense but well organised.")],
}

# What the live learner knew before the course. Low enough that the uplift in Act
# 5 is worth looking at, high enough to read as a working oncologist rather than
# someone who has never met the drug.
LIVE_BASELINE = 55


def _quiz(run_id: str, track: str) -> dict:
    return json.loads(content_path("content", run_id, track, "quiz.json").read_text())


def _asked(run_id: str, track: str, kind: str) -> list[dict]:
    """The questions the API would ask, so a seeded score means what the app means."""
    from api.main import _questions

    quiz = _quiz(run_id, track)
    return _questions({"learners": {track: {"quiz": quiz}}}, track, kind)


def _answers(questions: list[dict], target_percent: int, who: str) -> dict[str, int]:
    """Answer just enough correctly to land on the target score.

    Which questions are missed is drawn per learner rather than taken off the end.
    Answering the first N correctly gives every seeded learner the same tail of
    wrong answers, and the hardest-questions chart in the analytics then reports
    the last four questions in the quiz — an artefact of the seeding that reads,
    on a screen, as a finding about the content.
    """
    wanted = round(len(questions) * target_percent / 100)
    wrong = set(random.Random(who).sample(range(len(questions)), len(questions) - wanted))
    return {
        question["id"]: (question["correct_index"] + 1) % 4 if index in wrong else question["correct_index"]
        for index, question in enumerate(questions)
    }


def _backdate(run_id: str, user_id: str, start: datetime) -> None:
    """Spread one learner's history over real hours instead of stacking it on now."""
    record = learning.progress(run_id, user_id)
    for index, (_module_id, detail) in enumerate(record["modules"].items()):
        detail["at"] = (start + timedelta(hours=2 * index)).isoformat()
    for index, attempt in enumerate(record["attempts"]):
        attempt["created_at"] = (start + timedelta(hours=2 * index + 1)).isoformat()
    if record.get("certificate"):
        record["certificate"]["issued_at"] = (start + timedelta(days=1)).isoformat()
    learning._save_progress(record)


def cohort(run_id: str, live_learner: str) -> None:
    record = learning.course(run_id)
    publication = record.get("publication")
    if not publication:
        raise SystemExit(f"{run_id} is not published yet — run Act 3 first.")

    starts = datetime.combine(
        learning._on(publication["starts_on"]) or datetime.now(UTC).date(),
        datetime.min.time(), tzinfo=UTC)

    for user_id, delay, stage, baseline_target, final_targets in COHORT:
        if user_id not in publication["assignees"]:
            print(f"  skipping {user_id} — not assigned to this course")
            continue
        if learning.progress(run_id, user_id)["attempts"]:
            print(f"  skipping {user_id} — already started")
            continue
        person = learning.person(user_id)
        track = learning.track_for(person["role"])
        final_questions = _asked(run_id, track, "final")
        baseline_questions = _asked(run_id, track, "baseline")
        passing = _quiz(run_id, track)["passing_score"]

        learning.record_attempt(run_id, user_id, "baseline",
                                _answers(baseline_questions, baseline_target, user_id), baseline_questions, 0)
        for module in learning.MODULES:
            if stage == "learning" and module["id"] in {"storyboard", "faq"}:
                continue
            learning.set_module(run_id, user_id, module["id"], True)
        for target in final_targets:
            learning.record_attempt(run_id, user_id, "final",
                                    _answers(final_questions, target, f"{user_id}-{target}"),
                                    final_questions, passing)
        for module_id, rating, comment in FEEDBACK.get(user_id, []):
            learning.add_feedback(run_id, user_id, module_id, rating, comment)

        _backdate(run_id, user_id, starts + timedelta(days=delay))
        summary = learning.summarize(learning.progress(run_id, user_id))
        print(f"  {person['name']:<22} {summary['stage']:<14} baseline {summary['baseline_score']}"
              f" → final {summary['final_score']}")

    live = learning.person(live_learner)
    if not live:
        raise SystemExit(f"Unknown learner {live_learner}")
    if learning.progress(run_id, live_learner)["attempts"]:
        print(f"  {live['name']:<22} already has a baseline — left alone")
        return
    track = learning.track_for(live["role"])
    baseline_questions = _asked(run_id, track, "baseline")
    learning.record_attempt(run_id, live_learner, "baseline",
                            _answers(baseline_questions, LIVE_BASELINE, live_learner), baseline_questions, 0)
    _backdate(run_id, live_learner, starts)
    summary = learning.summarize(learning.progress(run_id, live_learner))
    print(f"  {live['name']:<22} {summary['stage']:<14} baseline {summary['baseline_score']}"
          f" → nothing else, ready to demo")


def _blocks(questions: list[dict], quiz: dict) -> list[tuple[dict | None, list[dict]]]:
    """The order the assessment page lays out: whole groups first, then the rest.

    Mirrors `blocks()` in the assessment page. A key in quiz order would send the
    presenter hunting for question 14 while the screen is showing a sort board.
    """
    by_id = {group["id"]: group for group in quiz.get("groups", [])}
    gathered: dict[str, list[dict]] = {}
    loose: list[dict] = []
    for question in questions:
        group = by_id.get(question.get("group") or "")
        if group:
            gathered.setdefault(group["id"], []).append(question)
        else:
            loose.append(question)
    return ([(by_id[group_id], items) for group_id, items in gathered.items()]
            + [(None, loose)])


def _bucket_label(group: dict, index: int) -> str:
    """Buckets are plain strings on the board, not objects."""
    buckets = group.get("buckets") or []
    return buckets[index] if index < len(buckets) else f"option {index + 1}"


def answers(run_id: str, track: str, score: int | None) -> None:
    quiz = _quiz(run_id, track)
    questions = _asked(run_id, track, "final")
    passing = quiz["passing_score"]
    needed = -(-len(questions) * passing // 100)

    print(f"{quiz['title']}\n")
    print(f"{len(questions)} questions · pass mark {passing}% · {needed} correct to pass\n")

    # Deliberate misses come from the plain questions, spread out. Taking them off
    # the end put every miss on a figure question, which is both the wrong story —
    # a clinician who cannot read a chart — and a waste of the four questions worth
    # showing on screen. The sort board, the assemble panel and the figures all
    # stay correct.
    miss: set[str] = set()
    if score is not None:
        wrong = len(questions) - round(len(questions) * score / 100)
        plain = [question for question in questions
                 if not question.get("group") and not question.get("figure")]
        if wrong > len(plain):
            raise SystemExit(f"{score}% needs {wrong} wrong answers but only {len(plain)} plain "
                             f"questions to spend them on — pick a higher score.")
        # Offset half a stride so the first miss is not the first question asked:
        # opening the assessment by deliberately choosing a wrong answer is the one
        # moment the presenter is most likely to fumble.
        stride = len(plain) // wrong if wrong else 0
        miss = {plain[index * stride + stride // 2]["id"] for index in range(wrong)} if wrong else set()

    for group, items in _blocks(questions, quiz):
        if group is None:
            if not items:
                continue
            print("── Remaining questions ──\n")
            for question in items:
                mark = "  ✗ ANSWER WRONG" if question["id"] in miss else ""
                choice = question["options"][question["correct_index"]]
                print(f"  {question['prompt']}")
                print(f"    → {chr(65 + question['correct_index'])}. {choice}{mark}\n")
            continue

        kind = "Sort board" if group.get("kind") == "sort" else "Build the instruction"
        print(f"── {kind}: {group['title']} ──\n")
        for question in items:
            mark = "  ✗ ANSWER WRONG" if question["id"] in miss else ""
            if group.get("kind") == "sort":
                print(f"  {question['prompt']}")
                print(f"    → {_bucket_label(group, question['correct_index'])}{mark}\n")
            else:
                print(f"  {question['prompt']}")
                print(f"    → {question['options'][question['correct_index']]}{mark}\n")

    if score is not None:
        print(f"Answering the {len(miss)} marked question(s) wrong lands on {score}%.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("cohort", help="seed the other trainees and the live learner's baseline")
    seed.add_argument("run_id")
    seed.add_argument("--live-learner", default=LIVE_LEARNER)

    key = sub.add_parser("answers", help="print the final assessment key in screen order")
    key.add_argument("run_id")
    key.add_argument("--track", default="hcp", choices=("hcp", "msl"))
    key.add_argument("--score", type=int, help="mark enough questions to land on this score")

    args = parser.parse_args()
    if args.command == "cohort":
        cohort(args.run_id, args.live_learner)
    else:
        answers(args.run_id, args.track, args.score)


if __name__ == "__main__":
    main()

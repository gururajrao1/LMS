"""Course analytics and the ROI model.

Everything here is derived from state the platform already records — publication
dates, stored attempt answers, module completions, ratings, and the agent's own
run and usage logs. The only inputs that are *not* measured are the manual
baselines a customer supplies for comparison, and those are returned alongside
every result so a reader can see exactly what the saving is being measured
against.
"""

import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from src import learning
from src.agent import content_path

# What the same work costs a medical-affairs team today. Stated, not measured —
# override per customer rather than quietly assuming these are universal.
MANUAL_BASELINE = {
    "first_version_days": float(os.getenv("PHARMALEARN_MANUAL_FIRST_VERSION_DAYS", "30")),
    "update_days": float(os.getenv("PHARMALEARN_MANUAL_UPDATE_DAYS", "15")),
    "review_cycle_days": float(os.getenv("PHARMALEARN_MANUAL_REVIEW_DAYS", "10")),
    "blended_day_rate_usd": float(os.getenv("PHARMALEARN_DAY_RATE_USD", "900")),
    # What it costs an expert to find one citation defect by reading: open the
    # source, locate the passage, compare it to the claim, write it up.
    "minutes_per_defect_found": float(os.getenv("PHARMALEARN_MINUTES_PER_DEFECT", "25")),
    # Elapsed time is a fair proxy for cost over weeks and a nonsense one over
    # minutes: a course generated and published inside an hour did not cost zero,
    # it cost the expert attention it still had to pass through. Costing is floored
    # here rather than reported as $0, which reads as a broken number and invites
    # the reader to discount every figure beside it.
    "min_expert_days": float(os.getenv("PHARMALEARN_MIN_EXPERT_DAYS", "0.5")),
}

# Cohort sizes the per-learner cost is projected across. Authoring cost is fixed,
# so this is the shape of the curve rather than a forecast of enrolment.
PROJECTION_COHORTS = (25, 100, 400)

SCORE_BANDS = [(0, 59, "0–59"), (60, 69, "60–69"), (70, 79, "70–79"), (80, 89, "80–89"), (90, 100, "90–100")]


def _json(path: Path):
    import json

    return json.loads(path.read_text())


def _at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _day(value: str | None) -> str | None:
    moment = _at(value)
    return moment.date().isoformat() if moment else None


def _quiz(run_id: str, track: str):
    base = content_path("content", Path(run_id).name)
    for candidate in [base / track / "quiz.json", base / "assets" / "quiz.json"]:
        if candidate.exists():
            return _json(candidate)
    return None


def _progress_records(run_id: str):
    record = learning.course(run_id)
    assigned = record["publication"]["assignees"] if record.get("publication") else []
    people = {entry["id"]: entry for entry in learning.roster()}
    return record, [(user_id, people.get(user_id, {}), learning.progress(run_id, user_id)) for user_id in assigned]


def funnel(run_id: str) -> list[dict]:
    """The standard completion funnel: how far the cohort got, stage by stage."""
    _record, entries = _progress_records(run_id)
    total = len(entries)
    started = baseline = modules = passed = certified = 0
    for _user_id, _person, state in entries:
        summary = learning.summarize(state)
        started += summary["stage"] != "not_started"
        baseline += summary["baseline_score"] is not None
        modules += summary["modules_complete"] == summary["modules_total"]
        passed += summary["passed"]
        certified += bool(summary["certificate"])
    stages = [
        ("Assigned", total),
        ("Started", started),
        ("Baseline taken", baseline),
        ("Modules complete", modules),
        ("Passed the final", passed),
        ("Certified", certified),
    ]
    return [
        {"stage": label, "count": count, "percent": round(100 * count / total) if total else 0}
        for label, count in stages
    ]


def score_bands(run_id: str) -> list[dict]:
    _record, entries = _progress_records(run_id)
    finals = [
        learning.summarize(state)["final_score"]
        for _user_id, _person, state in entries
        if learning.summarize(state)["final_score"] is not None
    ]
    counts = Counter()
    for score in finals:
        for low, high, label in SCORE_BANDS:
            if low <= score <= high:
                counts[label] += 1
                break
    return [{"band": label, "count": counts[label]} for _low, _high, label in SCORE_BANDS]


def question_difficulty(run_id: str) -> list[dict]:
    """Which questions the cohort actually got wrong — the content-improvement signal."""
    _record, entries = _progress_records(run_id)
    seen: dict[tuple[str, str], dict] = {}
    for _user_id, person, state in entries:
        track = learning.track_for(person.get("role", "hcp"))
        quiz = _quiz(run_id, track)
        if not quiz:
            continue
        correct_by_id = {question["id"]: question for question in quiz["questions"]}
        for attempt in state["attempts"]:
            if attempt["kind"] != "final":
                continue
            for question_id, chosen in attempt["answers"].items():
                question = correct_by_id.get(question_id)
                if not question:
                    continue
                key = (track, question_id)
                entry = seen.setdefault(key, {
                    "track": track,
                    "id": question_id,
                    "prompt": question["prompt"],
                    "attempts": 0,
                    "correct": 0,
                })
                entry["attempts"] += 1
                entry["correct"] += chosen == question["correct_index"]
    results = [
        {**entry, "percent": round(100 * entry["correct"] / entry["attempts"])}
        for entry in seen.values() if entry["attempts"]
    ]
    return sorted(results, key=lambda entry: (entry["percent"], entry["id"]))


def module_engagement(run_id: str) -> list[dict]:
    _record, entries = _progress_records(run_id)
    completions = Counter()
    ratings = defaultdict(list)
    for _user_id, _person, state in entries:
        for module_id in state["modules"]:
            completions[module_id] += 1
        for item in state["feedback"]:
            ratings[item["module_id"]].append(item["rating"])
    return [{
        "id": module["id"],
        "title": module["title"],
        "minutes": module["minutes"],
        "completed": completions[module["id"]],
        "rating": round(sum(ratings[module["id"]]) / len(ratings[module["id"]]), 1) if ratings[module["id"]] else None,
        "ratings": len(ratings[module["id"]]),
    } for module in learning.MODULES]


def activity(run_id: str) -> list[dict]:
    """Daily completions since publication, plus the cumulative certified curve."""
    _record, entries = _progress_records(run_id)
    days: dict[str, dict] = defaultdict(lambda: {"modules": 0, "assessments": 0, "certificates": 0})
    for _user_id, _person, state in entries:
        for detail in state["modules"].values():
            day = _day(detail.get("completed_at"))
            if day:
                days[day]["modules"] += 1
        for attempt in state["attempts"]:
            day = _day(attempt.get("created_at"))
            if day:
                days[day]["assessments"] += 1
        certificate = state.get("certificate")
        day = _day(certificate.get("issued_at")) if certificate else None
        if day:
            days[day]["certificates"] += 1
    running = 0
    series = []
    for day in sorted(days):
        running += days[day]["certificates"]
        series.append({"date": day, **days[day], "cumulative_certified": running})
    return series


def roi(run_id: str) -> dict:
    """Measured elapsed time against the stated manual baseline."""
    record = learning.course(run_id)
    publication = record.get("publication")
    run_path = content_path("logs", Path(run_id).name, "run.json")
    manifest_path = content_path("content", Path(run_id).name, "manifest.json")
    run = _json(run_path) if run_path.exists() else {}
    manifest = _json(manifest_path) if manifest_path.exists() else {}

    started = _at(run.get("created_at"))
    generated = _at(manifest.get("generated_at"))
    published = _at(publication["published_at"]) if publication else None
    comments = [_at(comment["created_at"]) for comment in record["comments"]]
    comments = [moment for moment in comments if moment]

    generation_minutes = round((generated - started).total_seconds() / 60, 1) if started and generated else None
    # Three decimals, not one: a course that reached the field in twenty minutes
    # is 0.0 days at one decimal place, and every figure derived from it then
    # divides by zero-ish and reports a saving of exactly 100%.
    review_days = round((published - min(comments)).total_seconds() / 86400, 3) if published and comments else None
    days_to_publish = round((published - started).total_seconds() / 86400, 3) if started and published else None

    baseline_days = MANUAL_BASELINE["first_version_days"]
    rate = MANUAL_BASELINE["blended_day_rate_usd"]
    agent_cost = float(manifest.get("cost_usd") or 0)
    days_saved = round(baseline_days - days_to_publish, 1) if days_to_publish is not None else None
    cost_saved = round(days_saved * rate - agent_cost) if days_saved is not None else None
    # Floored at 99: the comparison is against a stated baseline, and claiming to
    # have removed literally all of a 30-day cycle is a rounding artefact rather
    # than a result anyone can defend in the room.
    percent_faster = (min(round(100 * days_saved / baseline_days), 99)
                      if days_saved is not None else None)

    return {
        "measured": {
            "generation_minutes": generation_minutes,
            "review_days": review_days,
            "days_to_publish": days_to_publish,
            "agent_cost_usd": round(agent_cost, 2),
            "versions": len(record["versions"]),
            "expert_comments": len(record["comments"]),
            "reviewers": len({entry["author_id"] for entry in record["signoffs"]}),
            "citations": manifest.get("citation_count"),
        },
        "baseline": MANUAL_BASELINE,
        "saving": {
            "days_saved": days_saved,
            "percent_faster": percent_faster,
            "cost_saved_usd": cost_saved,
            "update_days_saved": MANUAL_BASELINE["update_days"],
        },
    }


def time_to_field(run_id: str) -> dict:
    """Where the elapsed time actually went, phase by phase.

    "90% faster" is a good headline and a bad argument: it invites the reply
    that the saving is all in a generation step nobody was spending 30 days on.
    Splitting the clock answers that. Each phase is bounded by timestamps the
    platform already recorded, and the manual column is the stated baseline
    apportioned the way a medical-affairs team actually spends it.
    """
    record = learning.course(run_id)
    run_path = content_path("logs", Path(run_id).name, "run.json")
    manifest_path = content_path("content", Path(run_id).name, "manifest.json")
    run = _json(run_path) if run_path.exists() else {}
    manifest = _json(manifest_path) if manifest_path.exists() else {}

    started = _at(run.get("created_at"))
    generated = _at(manifest.get("generated_at"))
    published = _at(record["publication"]["published_at"]) if record.get("publication") else None
    comments = sorted(moment for moment in (_at(entry["created_at"]) for entry in record["comments"]) if moment)
    signoffs = sorted(moment for moment in (_at(entry["created_at"]) for entry in record["signoffs"]) if moment)

    review_opened = comments[0] if comments else generated
    approved = signoffs[-1] if signoffs else None

    def span(start: datetime | None, end: datetime | None) -> float | None:
        return round((end - start).total_seconds() / 60, 2) if start and end else None

    # The manual split: drafting dominates, review is the stated cycle, and the
    # rest is the queue before an expert picks it up plus the lag to the field.
    baseline_total = MANUAL_BASELINE["first_version_days"]
    baseline_review = MANUAL_BASELINE["review_cycle_days"]
    baseline_publish, baseline_wait = 2.0, 2.0
    baseline_draft = max(baseline_total - baseline_review - baseline_publish - baseline_wait, 0.0)

    # The phases tile the whole span from the run starting to the course reaching
    # the field, so they add up to the headline figure rather than to less than it.
    # The queue is a phase like any other: work sitting still is still elapsed time.
    phases = [
        ("Research and draft", "Sources gathered, dossier built, four assets generated",
         span(started, generated), baseline_draft),
        ("Waiting for a reviewer", "Drafted and sitting in the queue",
         span(generated, review_opened), baseline_wait),
        ("Expert review", "First comment raised through to the last sign-off",
         span(review_opened, approved), baseline_review),
        ("Approval to field", "Signed off, scheduled and assigned to the cohort",
         span(approved, published), baseline_publish),
    ]
    return {
        "phases": [
            {
                "phase": name,
                "detail": detail,
                "measured_minutes": minutes,
                # Five places, not two: these spans are recorded in minutes, and
                # rounding to hundredths of a day collapses a 24-second step and a
                # 12-minute one to the same 0.0 before anything can format them.
                "measured_days": round(minutes / 1440, 5) if minutes is not None else None,
                "manual_days": manual,
            }
            for name, detail, minutes, manual in phases
        ],
        "measured_total_days": round(sum(minutes or 0 for _n, _d, minutes, _m in phases) / 1440, 5),
        "manual_total_days": baseline_total,
    }


def unit_economics(run_id: str) -> dict:
    """Cost per certified learner, and how it falls as the cohort grows.

    The cost of building a course is fixed; every extra learner divides it. That
    is the whole argument for automating authoring, and it is invisible in a
    single "days saved" figure. Projected cohorts are labelled as projections —
    only the current row is measured.
    """
    record = learning.course(run_id)
    _record, entries = _progress_records(run_id)
    certified = sum(1 for _user_id, _person, state in entries if learning.summarize(state)["certificate"])
    assigned = len(entries)

    measured = roi(run_id)["measured"]
    rate = MANUAL_BASELINE["blended_day_rate_usd"]
    days_to_publish = measured["days_to_publish"]
    expert_days = max(days_to_publish or 0, MANUAL_BASELINE["min_expert_days"])
    build_cost = round(expert_days * rate + measured["agent_cost_usd"])
    manual_build_cost = round(MANUAL_BASELINE["first_version_days"] * rate)

    def per_learner(cost: float, learners: int) -> int | None:
        return round(cost / learners) if learners else None

    projection = [
        {"learners": size, "cost_usd": per_learner(build_cost, size),
         "manual_cost_usd": per_learner(manual_build_cost, size), "measured": False}
        for size in PROJECTION_COHORTS
    ]
    return {
        "build_cost_usd": build_cost,
        "expert_days_costed": round(expert_days, 3),
        "floored": expert_days > (days_to_publish or 0),
        "manual_build_cost_usd": manual_build_cost,
        "certified": certified,
        "assigned": assigned,
        "cost_per_certified_usd": per_learner(build_cost, certified),
        "manual_cost_per_certified_usd": per_learner(manual_build_cost, certified),
        "curve": [
            {"learners": certified, "cost_usd": per_learner(build_cost, certified),
             "manual_cost_usd": per_learner(manual_build_cost, certified), "measured": True},
            *projection,
        ],
        "version_count": len(record["versions"]),
    }


def speed_to_competence(run_id: str) -> dict:
    """Days from the course reaching the field to a learner being certified.

    The LMS question is not whether the cohort finished, it is how quickly the
    field became able to use the material. Measured per learner from publication
    to the certificate; anyone not yet certified is counted as outstanding rather
    than quietly dropped from the median.
    """
    record, entries = _progress_records(run_id)
    published = _at(record["publication"]["published_at"]) if record.get("publication") else None
    learners = []
    for _user_id, person, state in entries:
        summary = learning.summarize(state)
        certificate = summary["certificate"]
        issued = _at(certificate["issued_at"]) if certificate else None
        learners.append({
            "name": person.get("name", "Unknown"),
            "track": learning.track_for(person.get("role", "hcp")).upper(),
            "days": round((issued - published).total_seconds() / 86400, 1) if issued and published else None,
            "attempts": len([attempt for attempt in state["attempts"] if attempt["kind"] == "final"]),
        })
    certified = sorted(entry["days"] for entry in learners if entry["days"] is not None)
    median = None
    if certified:
        middle = len(certified) // 2
        median = certified[middle] if len(certified) % 2 else round((certified[middle - 1] + certified[middle]) / 2, 1)
    return {
        "median_days": median,
        "fastest_days": certified[0] if certified else None,
        "slowest_days": certified[-1] if certified else None,
        "certified": len(certified),
        "outstanding": len(learners) - len(certified),
        "learners": sorted(learners, key=lambda entry: (entry["days"] is None, entry["days"] or 0)),
    }


def uplift_by_track(run_id: str) -> list[dict]:
    """Baseline against final, split by learning track.

    A single cohort average hides the case the two tracks exist to handle: an
    MSL and a prescriber start from different places and should not be judged
    against one number. Paired only — a learner counts in both columns or
    neither, so the two averages always describe the same people.
    """
    _record, entries = _progress_records(run_id)
    grouped: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for _user_id, person, state in entries:
        summary = learning.summarize(state)
        if summary["baseline_score"] is None or summary["final_score"] is None:
            continue
        grouped[learning.track_for(person.get("role", "hcp"))].append(
            (summary["baseline_score"], summary["final_score"]))
    results = []
    for track, pairs in sorted(grouped.items()):
        baselines = [pair[0] for pair in pairs]
        finals = [pair[1] for pair in pairs]
        baseline = round(sum(baselines) / len(baselines))
        final = round(sum(finals) / len(finals))
        results.append({
            "track": track.upper(),
            "learners": len(pairs),
            "baseline": baseline,
            "final": final,
            "uplift": final - baseline,
        })
    return results


def checker_leverage(run_id: str) -> dict:
    """What the automated pre-review took off the reviewers' desks.

    Only findings a human *accepted* are counted. A finding the experts threw out
    saved nobody anything, and counting it would make the checker look better the
    noisier it got.
    """
    from src import judge

    record = learning.course(run_id)
    machine = [entry for entry in record["comments"] if entry.get("origin") == "automated_check"]
    settled = [entry for entry in machine if entry["status"] in {"closed", "dismissed"}]
    accepted = [entry for entry in settled if entry["status"] == "closed"]

    report = judge.stored_report(run_id) or {}
    stats = report.get("stats", {})
    minutes = MANUAL_BASELINE["minutes_per_defect_found"]
    hours_saved = round(len(accepted) * minutes / 60, 1)

    return {
        "units_checked": stats.get("units"),
        "citations_checked": stats.get("checkable"),
        "raised": len(machine),
        "accepted": len(accepted),
        "dismissed": len(settled) - len(accepted),
        # Withheld below the same threshold the judge uses. Two settled findings
        # reporting "50% agreement" is a coin toss presented as a measurement.
        "agreement_percent": (round(100 * len(accepted) / len(settled))
                              if len(settled) >= judge.MIN_FOR_RATE else None),
        "settled": len(settled),
        "min_for_rate": judge.MIN_FOR_RATE,
        "minutes_per_defect": minutes,
        "reviewer_hours_saved": hours_saved,
        "reviewer_cost_saved_usd": round(hours_saved / 8 * MANUAL_BASELINE["blended_day_rate_usd"]),
        "human_comments": len(record["comments"]) - len(machine),
    }


def analytics(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "funnel": funnel(run_id),
        "score_bands": score_bands(run_id),
        "difficulty": question_difficulty(run_id),
        "modules": module_engagement(run_id),
        "activity": activity(run_id),
        "roi": roi(run_id),
        "time_to_field": time_to_field(run_id),
        "unit_economics": unit_economics(run_id),
        "speed_to_competence": speed_to_competence(run_id),
        "uplift_by_track": uplift_by_track(run_id),
        "checker_leverage": checker_leverage(run_id),
    }

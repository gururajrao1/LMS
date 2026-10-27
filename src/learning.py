"""Demo learning-platform state.

The agent produces course content; this module stores everything that happens
around it: who the people are, the maker-checker review of a course, its
publication and schedule, and each learner's progress, assessments and
certificate. State is JSON under `.pharmalearn/platform/` so every step of a
demo stays inspectable, matching the no-database constraint of the run data.
"""

import json
import os
import re
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from src.agent import content_path

ROLES = ("admin", "reviewer", "checker", "msl", "hcp")
LEARNER_ROLES = ("msl", "hcp")
COURSE_STATUSES = ("draft", "in_review", "approved", "published")
SEVERITIES = ("blocking", "major", "minor")

# Who may settle a review comment. The checker raises findings and never settles
# them — the same asymmetry that stops it signing off — and a learner is not part
# of the review at all. Without this, any caller could clear a blocking finding.
RESOLVER_ROLES = ("admin", "reviewer")

# Lets a submitted attempt have its unanswered questions filled with the correct
# answer. Purely a stage affordance: a thirty-question assessment answered live is
# ten minutes of silence in a demo. Off unless explicitly set, and an attempt that
# used it says so on the record rather than passing as someone's own work.
DEMO_FILL = os.getenv("PHARMALEARN_DEMO_FILL", "").strip() not in {"", "0", "false"}

MODULES = [
    {"id": "deck", "title": "Clinical deck", "kind": "ppt", "minutes": 25},
    {"id": "videos", "title": "Video lessons", "kind": "video", "minutes": 18},
    {"id": "storyboard", "title": "Visual story", "kind": "storyboard", "minutes": 10},
    {"id": "faq", "title": "Field FAQ", "kind": "faq", "minutes": 12},
]

REVIEW_TARGETS = [
    {"id": "deck", "title": "Clinical deck"},
    {"id": "storyboard", "title": "Visual story"},
    {"id": "faq", "title": "Field FAQ"},
    {"id": "quiz", "title": "Knowledge quiz"},
    {"id": "sources", "title": "Sources and citations"},
]

# The automated checker authors review comments but can never sign off — only a
# human reviewer clears content, so the machine triages and never approves.
CHECKER = {
    "id": "pharmalearn-checker", "name": "PharmaLearn checker",
    "email": "checks@pharmalearn.local", "role": "checker",
    "title": "Automated pre-review",
}

SEED_PEOPLE = [
    CHECKER,
    {"id": "priya-raman", "name": "Priya Raman", "email": "priya.raman@pharmalearn.local", "role": "admin", "title": "Medical education lead"},
    {"id": "anil-shekhar", "name": "Dr. Anil Shekhar", "email": "anil.shekhar@pharmalearn.local", "role": "reviewer", "title": "Therapeutic area expert, oncology"},
    {"id": "maria-alvarez", "name": "Dr. Maria Alvarez", "email": "maria.alvarez@pharmalearn.local", "role": "reviewer", "title": "Regulatory and medical affairs"},
    {"id": "jordan-feld", "name": "Jordan Feld", "email": "jordan.feld@pharmalearn.local", "role": "msl", "title": "MSL, oncology West"},
    {"id": "sara-nakamura", "name": "Sara Nakamura", "email": "sara.nakamura@pharmalearn.local", "role": "msl", "title": "MSL, oncology East"},
    {"id": "ken-osei", "name": "Dr. Ken Osei", "email": "ken.osei@pharmalearn.local", "role": "hcp", "title": "Medical oncologist"},
    {"id": "lucy-whitfield", "name": "Dr. Lucy Whitfield", "email": "lucy.whitfield@pharmalearn.local", "role": "hcp", "title": "Breast oncology, community practice"},
    {"id": "tom-becker", "name": "Dr. Tom Becker", "email": "tom.becker@pharmalearn.local", "role": "hcp", "title": "Oncology nurse practitioner"},
]


def _json(path: Path):
    return json.loads(path.read_text())


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _platform(*parts: str) -> Path:
    return content_path("platform", *parts)


def roster() -> list[dict]:
    path = _platform("roster.json")
    if not path.exists():
        _write(path, SEED_PEOPLE)
        return [dict(person) for person in SEED_PEOPLE]
    people = _json(path)
    # A roster written before a system identity existed gains it on next read.
    # Additive only: real people already in the file are never rewritten.
    missing = [entry for entry in (CHECKER,) if not any(p["id"] == entry["id"] for p in people)]
    if missing:
        people = missing + people
        _write(path, people)
    return people


def person(user_id: str) -> dict | None:
    return next((entry for entry in roster() if entry["id"] == user_id), None)


def sign_in(user_id: str | None = None, email: str | None = None, role: str | None = None) -> dict:
    people = roster()
    if user_id:
        found = next((entry for entry in people if entry["id"] == user_id), None)
        if found:
            return found
    if email:
        found = next((entry for entry in people if entry["email"].lower() == email.lower()), None)
        if found:
            return found
    if not email:
        raise ValueError("Provide a known user_id or an email address")
    local = email.split("@")[0]
    guest = {
        "id": _slug(local) or _id(),
        "name": local.replace(".", " ").replace("_", " ").title(),
        "email": email,
        "role": role if role in ROLES else "hcp",
        "title": "Demo participant",
    }
    _write(_platform("roster.json"), people + [guest])
    return guest


def track_for(role: str) -> str:
    return role if role in LEARNER_ROLES else "hcp"


def course(run_id: str) -> dict:
    path = _platform("courses", f"{Path(run_id).name}.json")
    if path.exists():
        record = _json(path)
        # Forward-only: a course written before the audit trail existed gains an
        # empty one on read. Its trail starts from now; nothing already recorded
        # is rewritten or invented after the fact.
        record.setdefault("audit", [])
        return record
    return {
        "run_id": run_id,
        "version": 1,
        "status": "draft",
        "comments": [],
        "versions": [{
            "version": 1,
            "summary": "Agent-generated first draft",
            "author_id": "agent",
            "author_name": "PharmaLearn agent",
            "addressed": [],
            "created_at": None,
        }],
        "signoffs": [],
        "publication": None,
        "audit": [],
    }


def _save_course(record: dict) -> dict:
    _write(_platform("courses", f"{Path(record['run_id']).name}.json"), record)
    return record


def _author(user_id: str, *, role: str | None = None) -> dict:
    found = person(user_id)
    if not found:
        raise ValueError(f"Unknown user {user_id}")
    if role and found["role"] != role:
        raise ValueError(f"Only {'an' if role[0] in 'aeiou' else 'a'} {role} can do that")
    return found


def _audit(record: dict, actor: dict, action: str, summary: str, **detail) -> dict:
    """Append one governance event to the course.

    Append-only by construction: this is the only function that writes to the
    trail, and it only ever appends. Nothing in this module edits or removes an
    entry, because the trail has to be trustworthy exactly when someone would
    prefer it said something else.
    """
    entry = {
        "id": _id(),
        "at": _now(),
        "action": action,
        "actor_id": actor["id"],
        "actor_name": actor["name"],
        "actor_title": actor.get("title", ""),
        "actor_role": actor.get("role", ""),
        "summary": summary,
        "detail": {key: value for key, value in detail.items() if value is not None},
    }
    record.setdefault("audit", []).append(entry)
    return entry


def readiness(record: dict) -> dict:
    version = record["version"]
    open_blocking = [
        comment for comment in record["comments"]
        if comment["status"] == "open" and comment["severity"] == "blocking"
    ]
    current = [entry for entry in record["signoffs"] if entry["version"] == version]
    approvals = [entry for entry in current if entry["decision"] == "approved"]
    changes = [entry for entry in current if entry["decision"] == "changes_requested"]
    return {
        "open_comments": sum(1 for comment in record["comments"] if comment["status"] == "open"),
        "open_blocking": len(open_blocking),
        # A challenged dismissal is still open, so it already holds publication.
        # Counted separately because "someone tried to wave this away" is worth
        # seeing on its own rather than buried in the open total.
        "challenged": sum(1 for comment in record["comments"]
                          if comment["status"] == "open" and comment.get("challenge")),
        "overrides": sum(1 for comment in record["comments"] if comment.get("override")),
        "addressed_comments": sum(1 for comment in record["comments"] if comment["status"] == "addressed"),
        "approvals": len(approvals),
        "changes_requested": len(changes),
        "approved_by": [entry["author_name"] for entry in approvals],
        "can_publish": bool(approvals) and not open_blocking and not changes,
    }


def submit_for_review(run_id: str, user_id: str) -> dict:
    record = course(run_id)
    _author(user_id)
    if record["status"] == "published":
        raise ValueError("A published course is already past review")
    record["status"] = "in_review"
    return _save_course(record)


def add_comment(run_id: str, user_id: str, target: str, severity: str, body: str) -> dict:
    record = course(run_id)
    author = _author(user_id)
    if severity not in SEVERITIES:
        raise ValueError(f"Severity must be one of {', '.join(SEVERITIES)}")
    if not body.strip():
        raise ValueError("A review comment needs a body")
    comment = {
        "id": _id(),
        "target": target,
        "severity": severity,
        "body": body.strip(),
        "status": "open",
        "resolution": None,
        "version": record["version"],
        "author_id": author["id"],
        "author_name": author["name"],
        "author_title": author.get("title", ""),
        "created_at": _now(),
        "resolved_at": None,
    }
    record["comments"].append(comment)
    if record["status"] == "draft":
        record["status"] = "in_review"
    _audit(record, author, "comment.raised",
           f"{author['name']} raised a {severity} comment on {target}",
           comment_id=comment["id"], severity=severity, target=target)
    _save_course(record)
    return comment


RESOLUTIONS = ("open", "addressed", "dismissed")


def _dismissal_challenge(run_id: str, comment: dict) -> dict | None:
    """Grounds for challenging a dismissal, if the check still fails.

    Imported here rather than at module scope: `judge` reaches back into this
    module to raise comments, and a top-level import in both directions is a cycle.
    """
    from src import judge

    try:
        return judge.dismissal_challenge(run_id, comment)
    except Exception:
        # A re-check that cannot run is not evidence the finding is gone. Let the
        # dismissal proceed rather than blocking a reviewer on a missing corpus,
        # and leave the reason they gave standing as the record.
        return None


def _challenge(record: dict, comment: dict, actor: dict, grounds: dict, reason: str) -> dict:
    """Hold a dismissal open because the check it dismisses still fails."""
    comment["challenge"] = {
        "raised_at": _now(),
        "by_id": actor["id"],
        "by_name": actor["name"],
        "by_title": actor.get("title", ""),
        "attempted_reason": reason,
        **grounds,
    }
    _audit(record, actor, "dismissal.challenged",
           f"{actor['name']} tried to dismiss a {comment['severity']} comment on "
           f"{comment['target']}; the {grounds['check']} check still fails",
           comment_id=comment["id"], severity=comment["severity"], target=comment["target"],
           check=grounds["check"], reason=reason)
    _save_course(record)
    return comment


def resolve_comment(run_id: str, comment_id: str, status: str, resolution: str | None = None,
                    user_id: str | None = None, override_reason: str | None = None) -> dict:
    """Settle a review comment, on the record.

    `user_id` is required. A resolution that nobody owns is the hole this closes:
    a blocking finding could previously be dismissed by an unauthenticated call,
    which removed it from `readiness()` and silently cleared the course to publish.

    Dismissing a machine finding is re-checked rather than taken on trust. If the
    check still fails against the stored sources the dismissal is *challenged*:
    the comment stays open, so publication stays held, until either the source is
    added or `override_reason` is given. Overriding is always allowed — it is
    never silent.
    """
    record = course(run_id)
    if status not in RESOLUTIONS:
        raise ValueError(f"Status must be {', '.join(RESOLUTIONS[:-1])} or {RESOLUTIONS[-1]}")
    if not user_id:
        raise ValueError("A review comment can only be settled by a named user")
    actor = _author(user_id)
    if actor["role"] not in RESOLVER_ROLES:
        raise ValueError("Only an admin or a reviewer can settle a review comment")
    comment = next((entry for entry in record["comments"] if entry["id"] == comment_id), None)
    if not comment:
        raise ValueError("Comment not found")
    if comment["status"] == "closed":
        raise ValueError("A comment already closed into a version cannot be reopened")

    reason = (resolution or "").strip()
    if status == "dismissed":
        if not reason:
            raise ValueError("Dismissing a finding needs a reason")
        grounds = _dismissal_challenge(run_id, comment)
        if grounds and not (override_reason or "").strip():
            return _challenge(record, comment, actor, grounds, reason)
        if grounds:
            comment["override"] = {
                "reason": override_reason.strip(),
                "check": grounds["check"],
                "actor_id": actor["id"],
                "actor_name": actor["name"],
                "actor_title": actor.get("title", ""),
                "at": _now(),
            }
            _audit(record, actor, "dismissal.overridden",
                   f"{actor['name']} overrode a still-failing {grounds['check']} check on {comment['target']}",
                   comment_id=comment_id, severity=comment["severity"], target=comment["target"],
                   check=grounds["check"], reason=override_reason.strip())
            # The override answers the challenge, so it replaces it. What was
            # challenged, and by whom, stays in the audit trail either way.
            comment.pop("challenge", None)

    was = comment["status"]
    settled = status != "open"
    # A challenge belongs to the dismissal that provoked it. Fixing the content or
    # reopening the comment makes it moot; the audit trail keeps it either way.
    if status != "dismissed":
        comment.pop("challenge", None)
    comment["status"] = status
    comment["resolution"] = (resolution or "").strip() or None
    comment["resolved_at"] = _now() if settled else None
    # Attribution follows the resolution: reopening drops it, because there is no
    # longer a resolution for anyone to own.
    comment["resolved_by_id"] = actor["id"] if settled else None
    comment["resolved_by_name"] = actor["name"] if settled else None
    comment["resolved_by_title"] = actor.get("title", "") if settled else None

    verb = {"open": "reopened", "addressed": "marked addressed", "dismissed": "dismissed"}[status]
    _audit(record, actor, "comment.resolved",
           f"{actor['name']} {verb} a {comment['severity']} comment on {comment['target']}",
           comment_id=comment_id, severity=comment["severity"], target=comment["target"],
           was=was, now=status, resolution=comment["resolution"],
           origin=comment.get("origin"), check=comment.get("check"))
    _save_course(record)
    return comment


def _verify_fixes(run_id: str, addressed: list[dict]) -> tuple[list[dict], list[tuple[dict, dict]]]:
    """Split claimed fixes into the ones that landed and the ones that did not.

    A comment marked addressed is a claim about the content, and the content can
    be read. Anything with a deterministic check behind it is re-run; a human's
    comment has nothing to re-run and is taken at its word.
    """
    from src import judge

    try:
        index = judge.failing_now(run_id)
    except Exception:
        # A check that cannot run is not evidence a fix failed. Do not strand a
        # version cut on a missing corpus.
        return list(addressed), []

    cleared, unverified = [], []
    for comment in addressed:
        grounds = judge.still_failing(comment, index)
        (unverified.append((comment, grounds)) if grounds else cleared.append(comment))
    return cleared, unverified


def publish_version(run_id: str, user_id: str, summary: str) -> dict:
    record = course(run_id)
    author = _author(user_id, role="admin")
    addressed = [comment for comment in record["comments"] if comment["status"] == "addressed"]
    if not addressed:
        raise ValueError("Address at least one review comment before cutting a version")

    # "Addressed" is a claim, and a version is where it becomes permanent, so this
    # is the last honest moment to read the content and check the claim is true.
    cleared, unverified = _verify_fixes(run_id, addressed)
    if not cleared:
        raise ValueError(
            f"None of the {len(addressed)} addressed comment(s) could be verified — the checks they came "
            "from still fail against the stored sources. Fix the content, or dismiss with an override.")

    record["version"] += 1
    for comment in cleared:
        comment["status"] = "closed"
        comment["closed_in_version"] = record["version"]
        comment.pop("unverified", None)
    for comment, grounds in unverified:
        # Not closed, and not silently left as addressed either: the fix did not
        # land, so the comment goes back to the queue it came from.
        comment["status"] = "open"
        comment["resolved_at"] = None
        comment["unverified"] = {"at": _now(), "version": record["version"], **grounds}

    record["versions"].append({
        "version": record["version"],
        "summary": summary.strip() or f"Addressed {len(cleared)} review comment(s)",
        "author_id": author["id"],
        "author_name": author["name"],
        "addressed": [comment["id"] for comment in cleared],
        "unverified": [comment["id"] for comment, _ in unverified],
        "created_at": _now(),
    })
    record["status"] = "in_review"
    _audit(record, author, "version.cut",
           f"{author['name']} cut version {record['version']}, closing {len(cleared)} comment(s)"
           + (f"; {len(unverified)} claimed fix(es) did not clear their checks" if unverified else ""),
           version=record["version"], closed=[comment["id"] for comment in cleared],
           unverified=[comment["id"] for comment, _ in unverified] or None)
    for comment, grounds in unverified:
        _audit(record, author, "fix.unverified",
               f"A {comment['severity']} comment on {comment['target']} was marked addressed, but the "
               f"{grounds['check']} check still fails — reopened",
               comment_id=comment["id"], severity=comment["severity"], target=comment["target"],
               check=grounds["check"], version=record["version"])
    _save_course(record)
    return record


def add_signoff(run_id: str, user_id: str, decision: str, note: str = "") -> dict:
    record = course(run_id)
    # Maker-checker: whoever authors and addresses the content cannot clear it.
    author = _author(user_id, role="reviewer")
    if decision not in {"approved", "changes_requested"}:
        raise ValueError("Decision must be approved or changes_requested")
    record["signoffs"] = [
        entry for entry in record["signoffs"]
        if not (entry["author_id"] == author["id"] and entry["version"] == record["version"])
    ]
    signoff = {
        "id": _id(),
        "version": record["version"],
        "decision": decision,
        "note": note.strip(),
        "author_id": author["id"],
        "author_name": author["name"],
        "author_title": author.get("title", ""),
        "created_at": _now(),
    }
    record["signoffs"].append(signoff)
    if record["status"] != "published":
        record["status"] = "approved" if readiness(record)["can_publish"] else "in_review"
    _audit(record, author, "signoff.recorded",
           f"{author['name']} recorded "
           f"{'approval' if decision == 'approved' else 'changes requested'} for v{record['version']}",
           version=record["version"], decision=decision, note=signoff["note"] or None)
    _save_course(record)
    return signoff


def assign_reviewers(run_id: str, user_id: str, reviewer_ids: list[str], note: str = "") -> dict:
    """Put named reviewers on a course, so the queue says who owns what.

    A shared queue tells five reviewers that something needs reviewing and none of
    them that it is theirs. This does not gate anything — any reviewer may still
    open any course and sign it off, because a hard lock would strand a course
    whose named expert is on leave. What it changes is whose dashboard says so.
    """
    record = course(run_id)
    author = _author(user_id, role="admin")
    people = {entry["id"]: entry for entry in roster()}
    unknown = [user for user in reviewer_ids if user not in people]
    if unknown:
        raise ValueError(f"Unknown reviewer(s): {', '.join(unknown)}")
    not_reviewers = [people[user]["name"] for user in reviewer_ids if people[user]["role"] != "reviewer"]
    if not_reviewers:
        raise ValueError(f"Not a reviewer: {', '.join(not_reviewers)}")
    if not reviewer_ids:
        raise ValueError("Select at least one reviewer")

    record["review_assignment"] = {
        "version": record["version"],
        "assigned_at": _now(),
        "assigned_by": author["name"],
        "reviewers": reviewer_ids,
        "note": note.strip(),
        "notifications": [{
            "to": people[user]["email"],
            "name": people[user]["name"],
            "subject": f"Review requested: {record['run_id']} v{record['version']}",
            "sent_at": _now(),
        } for user in reviewer_ids],
    }
    _audit(record, author, "review.assigned",
           f"{author['name']} assigned v{record['version']} to "
           f"{', '.join(people[user]['name'] for user in reviewer_ids)}",
           version=record["version"], reviewers=reviewer_ids)
    _save_course(record)
    return record


def publish_course(
    run_id: str,
    user_id: str,
    starts_on: str,
    due_on: str,
    assignees: list[str],
    message: str = "",
) -> dict:
    record = course(run_id)
    author = _author(user_id, role="admin")
    if not readiness(record)["can_publish"]:
        raise ValueError("A course needs an approving sign-off and no open blocking comments")
    if not assignees:
        raise ValueError("Select at least one trainee")
    people = {entry["id"]: entry for entry in roster()}
    unknown = [user for user in assignees if user not in people]
    if unknown:
        raise ValueError(f"Unknown trainee(s): {', '.join(unknown)}")
    # Overriding a still-failing check is allowed, but it travels with the course:
    # anyone reading the publication sees what was waved through and who did it.
    overrides = [{
        "comment_id": comment["id"],
        "severity": comment["severity"],
        "target": comment["target"],
        **comment["override"],
    } for comment in record["comments"] if comment.get("override")]

    record["status"] = "published"
    record["publication"] = {
        "version": record["version"],
        "published_at": _now(),
        "published_by": author["name"],
        "overrides": overrides,
        "starts_on": starts_on,
        "due_on": due_on,
        "message": message.strip(),
        "assignees": assignees,
        "notifications": [{
            "to": people[user]["email"],
            "name": people[user]["name"],
            "subject": f"Training assigned: complete by {due_on}",
            "sent_at": _now(),
        } for user in assignees],
    }
    _audit(record, author, "course.published",
           f"{author['name']} published v{record['version']} to {len(assignees)} trainee(s), due {due_on}",
           version=record["version"], starts_on=starts_on, due_on=due_on,
           assignees=assignees, approved_by=readiness(record)["approved_by"],
           overrides=len(overrides) or None)
    _save_course(record)
    return record


def published_courses() -> list[dict]:
    root = _platform("courses")
    records = [_json(path) for path in sorted(root.glob("*.json"))] if root.exists() else []
    return [record for record in records if record["status"] == "published" and record.get("publication")]


# Where one learner stands with one assignment. Derived like the programme
# lifecycle, and for the same reason: a stored status would need someone to keep
# it true, and would be wrong in between.
ASSIGNMENT_STATES = ("overdue", "due", "upcoming", "completed")


def _on(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def assignment_state(publication: dict, summary: dict, today: date | None = None) -> str:
    """Their own progress first: nothing is overdue for someone who already finished."""
    if summary.get("certificate"):
        return "completed"
    today = today or date.today()
    starts, due = _on(publication.get("starts_on")), _on(publication.get("due_on"))
    if starts and today < starts:
        return "upcoming"
    if due and today > due:
        return "overdue"
    return "due"


def days_until(value: str | None, today: date | None = None) -> int | None:
    moment = _on(value)
    return (moment - (today or date.today())).days if moment else None


def assignments(user_id: str) -> list[dict]:
    return [
        record for record in published_courses()
        if user_id in record["publication"]["assignees"]
    ]


def progress(run_id: str, user_id: str) -> dict:
    path = _platform("progress", Path(run_id).name, f"{Path(user_id).name}.json")
    if path.exists():
        return _json(path)
    return {
        "run_id": run_id,
        "user_id": user_id,
        "started_at": None,
        "modules": {},
        "attempts": [],
        "certificate": None,
        "feedback": [],
    }


def _save_progress(record: dict) -> dict:
    _write(_platform("progress", Path(record["run_id"]).name, f"{record['user_id']}.json"), record)
    return record


def _attempt(record: dict, kind: str) -> dict | None:
    attempts = [entry for entry in record["attempts"] if entry["kind"] == kind]
    return attempts[-1] if attempts else None


def summarize(record: dict) -> dict:
    """Derived learner state: module completion, scores and knowledge uplift."""
    done = [module for module in MODULES if module["id"] in record["modules"]]
    baseline, final = _attempt(record, "baseline"), _attempt(record, "final")
    modules_complete = len(done) == len(MODULES)
    passed = bool(final and final["passed"])
    if not record["started_at"]:
        stage = "not_started"
    elif not baseline:
        stage = "baseline"
    elif not modules_complete:
        stage = "learning"
    elif not passed:
        stage = "final"
    else:
        stage = "complete"
    return {
        "stage": stage,
        "modules_complete": len(done),
        "modules_total": len(MODULES),
        "percent": round(100 * len(done) / len(MODULES)),
        "baseline_score": baseline["score"] if baseline else None,
        "final_score": final["score"] if final else None,
        "uplift": final["score"] - baseline["score"] if baseline and final else None,
        "passed": passed,
        "attempts": len(record["attempts"]),
        "certificate": record["certificate"],
    }


def start(run_id: str, user_id: str) -> dict:
    record = progress(run_id, user_id)
    if not record["started_at"]:
        record["started_at"] = _now()
        _save_progress(record)
    return record


def set_module(run_id: str, user_id: str, module_id: str, completed: bool) -> dict:
    if module_id not in {module["id"] for module in MODULES}:
        raise ValueError(f"Unknown module {module_id}")
    record = start(run_id, user_id)
    if completed:
        record["modules"].setdefault(module_id, {"completed_at": _now()})
    else:
        record["modules"].pop(module_id, None)
    return _save_progress(record)


def record_attempt(
    run_id: str,
    user_id: str,
    kind: str,
    answers: dict[str, int],
    questions: list[dict],
    passing_score: int,
    fill_unanswered: bool = False,
) -> dict:
    if kind not in {"baseline", "final"}:
        raise ValueError("Assessment kind must be baseline or final")
    if fill_unanswered and not DEMO_FILL:
        raise ValueError("Filling unanswered questions is off — set PHARMALEARN_DEMO_FILL to enable it")
    record = start(run_id, user_id)
    filled = [question["id"] for question in questions if question["id"] not in answers] if fill_unanswered else []
    if filled:
        answers = {**answers,
                   **{question["id"]: question["correct_index"]
                      for question in questions if question["id"] in set(filled)}}
    correct = sum(1 for question in questions if answers.get(question["id"]) == question["correct_index"])
    total = len(questions)
    score = round(100 * correct / total) if total else 0
    attempt = {
        "id": _id(),
        "kind": kind,
        "score": score,
        "correct": correct,
        "total": total,
        "passing_score": passing_score,
        "passed": kind == "baseline" or score >= passing_score,
        "answers": answers,
        "created_at": _now(),
    }
    if filled:
        # Kept on the attempt, not just in the moment: analytics reads these rows,
        # and a 100% that was typed by a person and a 100% that was filled in are
        # different facts about the cohort.
        attempt["demo_filled"] = filled
    record["attempts"].append(attempt)
    _save_progress(record)
    if kind == "final" and attempt["passed"]:
        issue_certificate(run_id, user_id)
        record = progress(run_id, user_id)
    return {"attempt": attempt, "summary": summarize(record)}


def issue_certificate(run_id: str, user_id: str) -> dict | None:
    record = progress(run_id, user_id)
    state = summarize(record)
    if record["certificate"] or not state["passed"] or not state["modules_complete"] == state["modules_total"]:
        return record["certificate"]
    learner = person(user_id)
    course_record = course(run_id)
    published_version = (course_record.get("publication") or {}).get("version", course_record["version"])
    approvals = [
        entry for entry in course_record["signoffs"]
        if entry["decision"] == "approved" and entry["version"] == published_version
    ]
    issued = datetime.now(UTC)
    record["certificate"] = {
        "id": _id(),
        "code": f"PL-{_slug(run_id.split('-')[0]).upper()}-{issued.year}-{_id()[:6].upper()}",
        "user_id": user_id,
        "learner_name": learner["name"] if learner else user_id,
        "learner_title": learner.get("title", "") if learner else "",
        "run_id": run_id,
        "course_version": published_version,
        "score": state["final_score"],
        "issued_at": issued.isoformat(),
        # Field training is requalified annually; the certificate has to say so.
        "expires_at": issued.replace(year=issued.year + 1).isoformat(),
        "approved_by": [
            {"name": entry["author_name"], "title": entry["author_title"]}
            for entry in approvals
        ],
    }
    _save_progress(record)
    return record["certificate"]


def add_feedback(run_id: str, user_id: str, module_id: str, rating: int, comment: str = "") -> dict:
    record = start(run_id, user_id)
    if not 1 <= rating <= 5:
        raise ValueError("Rating must be between 1 and 5")
    entry = {
        "id": _id(),
        "module_id": module_id,
        "rating": rating,
        "comment": comment.strip(),
        "created_at": _now(),
    }
    record["feedback"] = [item for item in record["feedback"] if item["module_id"] != module_id] + [entry]
    _save_progress(record)
    return entry


def cohort(run_id: str) -> dict:
    record = course(run_id)
    assigned = record["publication"]["assignees"] if record.get("publication") else []
    people = {entry["id"]: entry for entry in roster()}
    learners = []
    for user_id in assigned:
        state = summarize(progress(run_id, user_id))
        learners.append({
            "user_id": user_id,
            "name": people.get(user_id, {}).get("name", user_id),
            "role": people.get(user_id, {}).get("role", "hcp"),
            "title": people.get(user_id, {}).get("title", ""),
            **state,
        })
    # Averages are computed only over learners who have BOTH scores, so
    # "62 → 91" is one cohort measured twice rather than two different groups.
    paired = [entry for entry in learners if entry["uplift"] is not None]
    certified = [entry for entry in learners if entry["certificate"]]
    started = [entry for entry in learners if entry["stage"] != "not_started"]
    feedback = []
    for user_id in assigned:
        for entry in progress(run_id, user_id)["feedback"]:
            feedback.append({**entry, "name": people.get(user_id, {}).get("name", user_id)})
    mean = lambda values: round(sum(values) / len(values)) if values else None
    return {
        "run_id": run_id,
        "assigned": len(learners),
        "started": len(started),
        "certified": len(certified),
        "measured": len(paired),
        "average_baseline": mean([entry["baseline_score"] for entry in paired]),
        "average_final": mean([entry["final_score"] for entry in paired]),
        "average_uplift": mean([entry["uplift"] for entry in paired]),
        "learners": learners,
        "feedback": sorted(feedback, key=lambda entry: entry["created_at"], reverse=True),
    }

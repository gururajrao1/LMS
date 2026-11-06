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
CAPABILITIES = (
    ("course.publish", "Publish courses",
     "Release reviewed courses to trainees and republish their schedules."),
    ("course.version", "Cut new versions",
     "Open a new draft version from review feedback."),
    ("review.signoff", "Sign off reviews",
     "Approve a course version so it can be published."),
    ("review.resolve", "Settle review comments",
     "Clear blocking and non-blocking review findings."),
    ("review.assign", "Assign reviewers",
     "Put named reviewers on a course version."),
    ("learn.reset", "Reset learner answers",
     "Clear attempts and certificates so a learner starts over."),
    ("roster.manage", "Manage people and roles",
     "Create custom roles and assign anyone a role."),
)
CAPABILITY_IDS = tuple(entry[0] for entry in CAPABILITIES)
CAPABILITY_LABELS = {entry[0]: entry[1] for entry in CAPABILITIES}

# What each built-in role could already do, restated as capabilities so custom
# roles speak the same language. Reviewers keep sign-off, resolution and
# resets; learners and the machine identity act through assignments, never
# through these gates, exactly as before. The one deliberate exception to
# "admin can do everything" is sign-off: maker-checker means the training
# lead who addresses comments must not clear the course, so sign-off stays
# reviewer-exclusive unless an admin deliberately grants it elsewhere.
DEFAULT_ROLE_CAPABILITIES = {
    "admin": set(CAPABILITY_IDS) - {"review.signoff"},
    "reviewer": {"review.signoff", "review.resolve", "learn.reset"},
    "checker": set(),
    "msl": set(),
    "hcp": set(),
}

BUILTIN_ROLE_LABELS = {
    "admin": "Admin",
    "reviewer": "Reviewer",
    "checker": "Automated check",
    "msl": "MSL",
    "hcp": "HCP",
}
BUILTIN_ROLE_DESCRIPTIONS = {
    "admin": "Full control: courses, reviews, people and roles.",
    "reviewer": "Reviews and signs off content, settles findings, resets answers.",
    "checker": "Machine identity that raises findings and never approves.",
    "msl": "Field medical training track.",
    "hcp": "Clinical training track.",
}

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


def custom_roles() -> list[dict]:
    """Roles the training team built on top of the five built-ins."""
    path = _platform("roles.json")
    return _json(path) if path.exists() else []


def _save_custom_roles(entries: list[dict]) -> list[dict]:
    _write(_platform("roles.json"), entries)
    return entries


def roles() -> list[dict]:
    """Every assignable role: built-ins first, then custom builds."""
    builtin = [
        {
            "id": role_id,
            "label": BUILTIN_ROLE_LABELS[role_id],
            "description": BUILTIN_ROLE_DESCRIPTIONS[role_id],
            "builtin": True,
            "learner": role_id in LEARNER_ROLES,
            "track": role_id if role_id in LEARNER_ROLES else "hcp",
            "capabilities": sorted(DEFAULT_ROLE_CAPABILITIES.get(role_id, ())),
        }
        for role_id in ("admin", "reviewer", "msl", "hcp", "checker")
    ]
    return builtin + [{**entry, "builtin": False} for entry in custom_roles()]


def known_roles() -> list[str]:
    return [entry["id"] for entry in roles()]


def capabilities_for(role_id: str) -> set[str]:
    """What a role may do: defaults for built-ins, the grant for custom roles."""
    if role_id in DEFAULT_ROLE_CAPABILITIES:
        return set(DEFAULT_ROLE_CAPABILITIES[role_id])
    custom = next((entry for entry in custom_roles() if entry["id"] == role_id), None)
    return set(custom.get("capabilities", ())) if custom else set()


def is_learner_role(role_id: str) -> bool:
    if role_id in LEARNER_ROLES:
        return True
    return any(entry["id"] == role_id and entry.get("learner") for entry in custom_roles())


def public_person(entry: dict) -> dict:
    """A roster entry plus what the UI needs to admit it: capabilities and learnerhood."""
    return {
        **entry,
        "capabilities": sorted(capabilities_for(entry.get("role", ""))),
        "learner": is_learner_role(entry.get("role", "")),
    }


def require_capability(user_id: str, capability: str) -> dict:
    """The single gate behind every training-team action.

    Unknown users and roles without the grant are refused the same way the
    old role checks refused them: a ValueError the API turns into a 400.
    """
    found = person(user_id)
    if not found:
        raise ValueError(f"Unknown user {user_id}")
    if capability not in capabilities_for(found["role"]):
        label = CAPABILITY_LABELS.get(capability, capability)
        raise ValueError(f"{found['name']} lacks the '{label}' permission")
    return found


def create_role(by_user_id: str, label: str, description: str = "",
                capabilities: list[str] | tuple[str, ...] = (),
                learner: bool = False, track: str = "hcp") -> dict:
    """Build a custom role from the capability catalog."""
    require_capability(by_user_id, "roster.manage")
    label = label.strip()
    if not label:
        raise ValueError("Name the role")
    unknown = [cap for cap in capabilities if cap not in CAPABILITY_IDS]
    if unknown:
        raise ValueError(f"Unknown capabilities: {', '.join(unknown)}")
    if learner and track not in LEARNER_ROLES:
        raise ValueError("A learner role follows the msl or hcp track")
    role_id = _slug(label)
    if not role_id:
        raise ValueError("Name the role with letters or numbers")
    if role_id in known_roles():
        raise ValueError(f"There is already a '{role_id}' role")
    entries = custom_roles()
    entry = {
        "id": role_id,
        "label": label,
        "description": description.strip(),
        "capabilities": sorted(set(capabilities)),
        "learner": bool(learner),
        "track": track if learner else "hcp",
        "created_by": by_user_id,
        "created_at": _now(),
    }
    entries.append(entry)
    _save_custom_roles(entries)
    return {**entry, "builtin": False}


def assign_role(by_user_id: str, user_id: str, role_id: str) -> dict:
    """Move anyone onto any assignable role; the machine identity stays unassignable."""
    require_capability(by_user_id, "roster.manage")
    if role_id == "checker":
        raise ValueError("The automated check identity is not assignable")
    if role_id not in known_roles():
        raise ValueError(f"Unknown role {role_id}")
    people = roster()
    found = next((entry for entry in people if entry["id"] == user_id), None)
    if not found:
        raise ValueError(f"Unknown user {user_id}")
    found["role"] = role_id
    _write(_platform("roster.json"), people)
    return public_person(found)


def delete_role(by_user_id: str, role_id: str) -> dict:
    """Remove a custom role that nobody holds; built-ins are permanent."""
    require_capability(by_user_id, "roster.manage")
    entries = custom_roles()
    if not any(entry["id"] == role_id for entry in entries):
        raise ValueError("Built-in roles cannot be deleted")
    holders = [entry["name"] for entry in roster() if entry["role"] == role_id]
    if holders:
        raise ValueError(f"Role is still held by: {', '.join(holders)}")
    _save_custom_roles([entry for entry in entries if entry["id"] != role_id])
    return {"deleted": role_id}


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
        "role": role if role in known_roles() else "hcp",
        "title": "Demo participant",
    }
    _write(_platform("roster.json"), people + [guest])
    return guest


def track_for(role: str) -> str:
    if role in LEARNER_ROLES:
        return role
    custom = next((entry for entry in custom_roles() if entry["id"] == role and entry.get("learner")), None)
    if custom and custom.get("track") in LEARNER_ROLES:
        return custom["track"]
    return "hcp"


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


def _content_status(publication: dict | None) -> dict:
    """How fresh the published content is: approved training material carries
    an expiry, so stale content can never pass as current. Derived, like
    everything else here — the expiry is months after the publish audit."""
    months = int(os.getenv("PHARMALEARN_CONTENT_VALID_MONTHS", "12"))
    published_at = (publication or {}).get("published_at")
    if not published_at:
        return {"content_valid_until": None, "content_state": "unpublished"}
    valid_until = date.fromisoformat(published_at[:10]).toordinal() + 30 * months
    remaining = valid_until - date.today().toordinal()
    state = "overdue" if remaining < 0 else "due" if remaining <= 30 else "current"
    return {
        "content_valid_until": date.fromordinal(valid_until).isoformat(),
        "content_state": state,
    }


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
        **_content_status(record.get("publication")),
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
    actor = require_capability(user_id, "review.resolve")
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
    author = require_capability(user_id, "course.version")
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
    author = require_capability(user_id, "review.signoff")
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


def objections(run_id: str) -> list[dict]:
    """Admin-authored answers to the hard questions HCPs actually ask.
    Retired entries stay on the record so the audit never loses one."""
    return [entry for entry in course(run_id).get("objections", []) if not entry.get("retired")]


def add_objection(run_id: str, user_id: str, question: str, answer: str,
                  citations: list[dict] | None = None) -> dict:
    record = course(run_id)
    author = require_capability(user_id, "course.publish")
    if not question.strip() or not answer.strip():
        raise ValueError("An objection needs both the question and the approved answer")
    entry = {
        "id": _id(),
        "question": question.strip(),
        "answer": answer.strip(),
        "citations": citations or [],
        "author_id": author["id"],
        "author_name": author["name"],
        "created_at": _now(),
        "retired": False,
    }
    record.setdefault("objections", []).append(entry)
    _audit(record, author, "objection.added", f"{author['name']} added an approved answer",
           version=record["version"])
    _save_course(record)
    return entry


def update_objection(run_id: str, user_id: str, objection_id: str, question: str | None = None,
                     answer: str | None = None, retired: bool | None = None) -> dict:
    record = course(run_id)
    author = require_capability(user_id, "course.publish")
    entry = next((item for item in record.get("objections", []) if item["id"] == objection_id), None)
    if not entry:
        raise ValueError("Objection not found")
    if question is not None:
        if not question.strip():
            raise ValueError("An objection needs both the question and the approved answer")
        entry["question"] = question.strip()
    if answer is not None:
        if not answer.strip():
            raise ValueError("An objection needs both the question and the approved answer")
        entry["answer"] = answer.strip()
    if retired is not None:
        entry["retired"] = bool(retired)
    _audit(record, author, "objection.updated", f"{author['name']} updated an approved answer",
           version=record["version"])
    _save_course(record)
    return entry


def _safety_file(run_id: str) -> Path:
    return _platform("safety", f"{Path(run_id).name}.json")


def safety_reports(run_id: str) -> list[dict]:
    path = _safety_file(run_id)
    return _json(path).get("reports", []) if path.exists() else []


def report_safety(run_id: str, user_id: str, concern: str) -> dict:
    """Anyone signed in can raise a safety concern; triage is staff work.
    Reporting stays open on purpose — silence is the failure mode here, so
    there is no assignment gate, only an identity check."""
    record = course(run_id)
    reporter = person(user_id)
    if not reporter:
        raise ValueError("Unknown person")
    if not concern.strip():
        raise ValueError("Describe the concern")
    entry = {
        "id": _id(),
        "concern": concern.strip(),
        "reporter_id": reporter["id"],
        "reporter_name": reporter["name"],
        "created_at": _now(),
        "status": "new",
        "reviewed_by": None,
        "reviewed_at": None,
    }
    path = _safety_file(run_id)
    payload = _json(path) if path.exists() else {"run_id": record["run_id"], "reports": []}
    payload["reports"].append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    _audit(record, reporter, "safety.reported", f"{reporter['name']} reported a safety concern",
           version=record["version"])
    _save_course(record)
    return entry


def review_safety(run_id: str, user_id: str, report_id: str) -> dict:
    record = course(run_id)
    reviewer = require_capability(user_id, "review.resolve")
    path = _safety_file(run_id)
    payload = _json(path) if path.exists() else {"reports": []}
    entry = next((item for item in payload["reports"] if item["id"] == report_id), None)
    if not entry:
        raise ValueError("Safety report not found")
    entry["status"] = "reviewed"
    entry["reviewed_by"] = reviewer["name"]
    entry["reviewed_at"] = _now()
    path.write_text(json.dumps(payload, indent=2))
    _audit(record, reviewer, "safety.reviewed", f"{reviewer['name']} triaged a safety concern",
           version=record["version"])
    _save_course(record)
    return entry


def assign_reviewers(run_id: str, user_id: str, reviewer_ids: list[str], note: str = "") -> dict:
    """Put named reviewers on a course, so the queue says who owns what.

    A shared queue tells five reviewers that something needs reviewing and none of
    them that it is theirs. This does not gate anything — any reviewer may still
    open any course and sign it off, because a hard lock would strand a course
    whose named expert is on leave. What it changes is whose dashboard says so.
    """
    record = course(run_id)
    author = require_capability(user_id, "review.assign")
    people = {entry["id"]: entry for entry in roster()}
    unknown = [user for user in reviewer_ids if user not in people]
    if unknown:
        raise ValueError(f"Unknown reviewer(s): {', '.join(unknown)}")
    not_reviewers = [people[user]["name"] for user in reviewer_ids
                     if "review.signoff" not in capabilities_for(people[user]["role"])]
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


FREQUENCIES = ("once", "quarterly", "semiannual", "annual")
FREQUENCY_MONTHS = {"once": 0, "quarterly": 3, "semiannual": 6, "annual": 12}

CERTIFICATE_TEMPLATES = {
    "classic": {
        "label": "Classic",
        "description": "Centered certificate with the brand band — the default wall piece.",
    },
    "modern": {
        "label": "Modern",
        "description": "Dark header band with left-aligned details — reads well on screen.",
    },
    "formal": {
        "label": "Formal",
        "description": "Framed serif layout with signatory emphasis — for compliance files.",
    },
}


def next_due_on(frequency: str, due_on: str) -> str | None:
    """When the next run of a repeating schedule falls due, if it repeats."""
    months = FREQUENCY_MONTHS.get(frequency, 0)
    if not months:
        return None
    try:
        year, month, day = (int(part) for part in due_on.split("-"))
    except (ValueError, AttributeError):
        return None
    month += months
    year += (month - 1) // 12
    month = (month - 1) % 12 + 1
    return date(year, month, min(day, 28)).isoformat()


def reset_attempts(run_id: str, user_id: str, user_role: str = "", actor_id: str = "") -> dict:
    """The training team clears a learner's assessment answers so they start over.

    Attempts and any certificate earned from them go; module progress stays,
    so the learner retakes the checks rather than redoing the whole course.
    """
    if actor_id:
        require_capability(actor_id, "learn.reset")
    elif user_role and user_role not in {"admin", "reviewer"}:
        raise ValueError("Only the training team can reset answers")
    record = progress(run_id, user_id)
    record["attempts"] = []
    record["certificate"] = None
    _save_progress(record)
    return summarize(record)


def publish_course(
    run_id: str,
    user_id: str,
    starts_on: str,
    due_on: str,
    assignees: list[str],
    message: str = "",
    frequency: str = "once",
    certificate_template: str = "classic",
) -> dict:
    record = course(run_id)
    author = require_capability(user_id, "course.publish")
    if not readiness(record)["can_publish"]:
        raise ValueError("A course needs an approving sign-off and no open blocking comments")
    if not assignees:
        raise ValueError("Select at least one trainee")
    if frequency not in FREQUENCIES:
        raise ValueError(f"Schedule must be one of: {', '.join(FREQUENCIES)}")
    if certificate_template not in CERTIFICATE_TEMPLATES:
        raise ValueError(f"Certificate design must be one of: {', '.join(CERTIFICATE_TEMPLATES)}")
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
        "frequency": frequency,
        "next_due_on": next_due_on(frequency, due_on),
        "certificate_template": certificate_template,
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
    """Live programmes only: archiving files a programme out of the running list."""
    root = _platform("courses")
    records = [_json(path) for path in sorted(root.glob("*.json"))] if root.exists() else []
    return [record for record in records
            if record["status"] == "published" and record.get("publication")
            and not record.get("archived")]


# Where one learner stands with one assignment. Derived like the programme
# lifecycle, and for the same reason: a stored status would need someone to keep
# it true, and would be wrong in between.
ASSIGNMENT_STATES = ("overdue", "due", "upcoming", "completed")


def _on(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def noncompliance(run_id: str) -> list[dict]:
    """Tiered noncompliance flags: overdue, below-requirement, or unbaselined.

    One shared source for the cohort alerts panel, the escalation ladder and
    every export, so the UI and the spreadsheet can never disagree.
    """
    record = course(run_id)
    publication = record.get("publication") or {}
    data = cohort(run_id)
    alerts = []
    for learner in data["learners"]:
        who = {"user_id": learner["user_id"], "name": learner["name"]}
        days = days_until(publication.get("due_on"))
        if assignment_state(publication, learner) == "overdue":
            tier = 3 if (days is not None and days <= -14) else 2 if (days is not None and days <= -7) else 1
            alerts.append({**who, "run_id": run_id, "kind": "overdue", "severity": "danger", "tier": tier,
                           "message": f"Overdue with {learner['modules_complete']}/{learner['modules_total']} modules done"})
        if learner.get("final_score") is not None and not learner["passed"]:
            alerts.append({**who, "run_id": run_id, "kind": "below_requirement", "severity": "danger", "tier": 2,
                           "message": f"Final {learner['final_score']}% is below the required score"})
        if learner["stage"] != "not_started" and learner["baseline_score"] is None:
            alerts.append({**who, "run_id": run_id, "kind": "unbaselined", "severity": "warning", "tier": 1,
                           "message": "Started without a recorded baseline"})
    order = {"danger": 0, "warning": 1}
    return sorted(alerts, key=lambda alert: (order[alert["severity"]], alert["tier"]))


ESCALATION_LEVELS = {
    1: {"level": 1, "name": "Nudge", "owner": "learner",
        "action": "In-app nudge to the learner to get back on plan."},
    2: {"level": 2, "name": "Follow-up", "owner": "reviewer",
        "action": "Flagged for training-team follow-up with the learner."},
    3: {"level": 3, "name": "Escalated", "owner": "admin",
        "action": "Escalated to the training lead for a decision."},
}


def _escalation_store_path(run_id: str) -> Path:
    return _platform("escalations", f"{Path(run_id).name}.json")


def _load_escalations(run_id: str) -> dict:
    path = _escalation_store_path(run_id)
    if path.exists():
        return _json(path)
    return {"run_id": run_id, "checked_at": None, "checked_by": None, "items": {}}


def escalation_state(run_id: str) -> dict:
    """The live ladder: every current flag with its level, owner and first-seen date."""
    stored = _load_escalations(run_id)
    known = stored.get("items", {})
    items = []
    for alert in noncompliance(run_id):
        key = f"{alert['user_id']}:{alert['message']}"
        previous = known.get(key, {})
        level = ESCALATION_LEVELS.get(alert.get("tier", 1), ESCALATION_LEVELS[1])
        items.append({
            **alert,
            "key": key,
            "level": level["level"],
            "level_name": level["name"],
            "owner": level["owner"],
            "action": level["action"],
            "since": previous.get("since", date.today().isoformat()),
            "history": previous.get("history", []),
        })
    return {"run_id": run_id, "checked_at": stored.get("checked_at"),
            "checked_by": stored.get("checked_by"), "items": items}


def check_escalations(run_id: str, user_id: str) -> dict:
    """Run the ladder: stamp first-seen dates, record level changes, prune resolved."""
    require_capability(user_id, "course.publish")
    state = escalation_state(run_id)
    today = date.today().isoformat()
    known = _load_escalations(run_id).get("items", {})
    kept = {}
    for item in state["items"]:
        previous = known.get(item["key"], {})
        history = list(previous.get("history", []))
        if not previous:
            history.append({"at": _now(), "level": item["level"], "note": "Flag raised"})
        elif previous.get("level") != item["level"]:
            history.append({"at": _now(), "from": previous.get("level"),
                            "level": item["level"], "note": f"Moved to {item['level_name']}"})
        item["since"] = previous.get("since", today)
        item["history"] = history
        kept[item["key"]] = {"level": item["level"], "since": item["since"], "history": history}
    resolved = [key for key in known if key not in kept]
    actor = person(user_id)
    _write(_escalation_store_path(run_id), {
        "run_id": run_id, "checked_at": _now(),
        "checked_by": actor["name"] if actor else user_id, "items": kept,
    })
    state = escalation_state(run_id)
    state["resolved"] = len(resolved)
    return state


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


RETENTION_POLICIES = (
    ("assessments", "Assessment attempts",
     "Raw answers and per-attempt scores.", 2,
     "Anonymize raw answers after two years; attempt scores stay for uplift analysis."),
    ("certificates", "Certificates",
     "Issued certificates with verification codes.", 7,
     "Keep for audit; verification codes stay valid for the whole period."),
    ("feedback", "Learner feedback",
     "Module ratings and comments.", 3,
     "Aggregate into content reviews, then retire the raw comments."),
    ("review", "Review trail",
     "Comments, sign-offs, overrides and the audit trail.", 7,
     "Keep for inspection readiness alongside the published versions."),
    ("notices", "Notifications",
     "Assignment and escalation notices.", 1,
     "Operational mail; the course record keeps what was sent and when."),
    ("uploads", "Staged material",
     "Source documents staged for a run.", 5,
     "Keep while the course they informed is live, then archive."),
)


def _iso_years_after(value: str | None, years: int) -> str | None:
    try:
        moment = datetime.fromisoformat(value) if value else None
    except ValueError:
        return None
    if not moment:
        return None
    try:
        return moment.replace(year=moment.year + years).date().isoformat()
    except ValueError:
        return moment.replace(year=moment.year + years, day=28).date().isoformat()


def retention(run_id: str) -> dict:
    """What personal and operational data this course holds, and how long each class stays.

    Report-only: nothing is deleted here. Each class carries its policy in
    years, the oldest and newest item seen, and how many items are past their
    keep-until date, so the training team can see what is due for review.
    """
    name = Path(run_id).name
    today = date.today().isoformat()
    collected: dict[str, list[str]] = {policy[0]: [] for policy in RETENTION_POLICIES}

    for record in _platform("progress", name).glob("*.json"):
        try:
            state = _json(record)
        except (OSError, ValueError):
            continue
        for attempt in state.get("attempts", []):
            if attempt.get("created_at"):
                collected["assessments"].append(attempt["created_at"])
        certificate = state.get("certificate") or {}
        if certificate.get("issued_at"):
            collected["certificates"].append(certificate["issued_at"])
    try:
        for entry in cohort(run_id)["feedback"]:
            if entry.get("created_at"):
                collected["feedback"].append(entry["created_at"])
    except (OSError, ValueError, KeyError):
        pass

    record = course(run_id)
    for comment in record.get("comments", []):
        if comment.get("created_at"):
            collected["review"].append(comment["created_at"])
    for signoff in record.get("signoffs", []):
        if signoff.get("created_at"):
            collected["review"].append(signoff["created_at"])
    for version in record.get("versions", []):
        if version.get("created_at"):
            collected["review"].append(version["created_at"])
    for entry in record.get("audit", []):
        if entry.get("at"):
            collected["review"].append(entry["at"])
    publication = record.get("publication") or {}
    for notice in publication.get("notifications", []):
        if notice.get("sent_at"):
            collected["notices"].append(notice["sent_at"])

    store = _load_escalations(run_id)
    if store.get("checked_at"):
        collected["notices"].append(store["checked_at"])
    for item in store.get("items", {}).values():
        for event in item.get("history", []):
            if event.get("at"):
                collected["notices"].append(event["at"])

    uploads = content_path("uploads")
    if uploads.exists():
        for entry in uploads.iterdir():
            if entry.is_file() and entry.name != "record.json":
                collected["uploads"].append(
                    datetime.fromtimestamp(entry.stat().st_mtime, UTC).isoformat())
            elif entry.is_dir():
                for document in entry.iterdir():
                    if document.is_file() and document.name != "record.json":
                        collected["uploads"].append(
                            datetime.fromtimestamp(document.stat().st_mtime, UTC).isoformat())

    classes = []
    for key, label, blurb, years, action in RETENTION_POLICIES:
        moments = sorted(collected[key])
        due = sum(1 for moment in moments
                  if (until := _iso_years_after(moment, years)) and until < today)
        classes.append({
            "id": key, "label": label, "description": blurb, "keep_years": years,
            "action": action, "items": len(moments),
            "oldest": moments[0] if moments else None,
            "newest": moments[-1] if moments else None,
            "first_due": _iso_years_after(moments[0], years) if moments else None,
            "due_for_review": due,
            "status": "due" if due else ("empty" if not moments else "within policy"),
        })
    return {"run_id": run_id, "today": today, "classes": classes}


def version_timeline(run_id: str) -> dict:
    """Every version of the course and what happened to it, oldest first.

    Versions, sign-offs and publications in one ladder, so a reviewer can see
    how v1 became the published v3 without opening three panels.
    """
    record = course(run_id)
    events = []
    for version in record.get("versions", []):
        events.append({
            "at": version.get("created_at"), "kind": "version",
            "title": f"Version {version.get('version')}",
            "detail": version.get("summary", ""),
            "actor": version.get("author_name", ""),
        })
    for signoff in record.get("signoffs", []):
        events.append({
            "at": signoff.get("created_at"), "kind": "signoff",
            "title": f"v{signoff.get('version')} {signoff.get('decision')}",
            "detail": signoff.get("note", ""),
            "actor": signoff.get("author_name", ""),
        })
    publication = record.get("publication") or {}
    if publication.get("published_at"):
        events.append({
            "at": publication.get("published_at"), "kind": "publication",
            "title": f"Published v{publication.get('version')}",
            "detail": f"{len(publication.get('assignees', []))} trainee(s), due {publication.get('due_on')}",
            "actor": publication.get("published_by", ""),
        })
    assignment = record.get("review_assignment")
    if assignment and assignment.get("assigned_at"):
        events.append({
            "at": assignment.get("assigned_at"), "kind": "assignment",
            "title": f"v{assignment.get('version')} assigned for review",
            "detail": (assignment.get("note", "") or "").strip(),
            "actor": assignment.get("assigned_by", ""),
        })
    events.sort(key=lambda event: (event["at"] is None, event["at"] or ""))
    return {"run_id": run_id, "version": record["version"], "status": record["status"], "events": events}


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


BADGES = [
    ("first-steps", "First steps"),
    ("baseline-complete", "Baseline complete"),
    ("halfway", "Halfway there"),
    ("course-complete", "Course complete"),
    ("final-pass", "Final passed"),
    ("certified", "Certified"),
    ("high-scorer", "High scorer"),
]


def _badges(record: dict, baseline: dict | None, final: dict | None, percent: int,
            modules_complete: bool, passed: bool) -> list[dict]:
    """Earned recognition, derived every call: nothing is stored, so a badge
    can never disagree with the progress it celebrates."""
    earned = set()
    if record["started_at"]:
        earned.add("first-steps")
    if baseline:
        earned.add("baseline-complete")
    if percent >= 50:
        earned.add("halfway")
    if modules_complete:
        earned.add("course-complete")
    if passed:
        earned.add("final-pass")
    if record["certificate"]:
        earned.add("certified")
    if final and final["score"] >= 90:
        earned.add("high-scorer")
    return [{"id": badge_id, "label": label, "earned": badge_id in earned}
            for badge_id, label in BADGES]


def _streak_days(record: dict) -> int:
    """Consecutive calendar days with any activity, ending today or yesterday.
    Anything older breaks the run, so a returning learner starts a new one."""
    days = set()
    for module in record["modules"].values():
        if module.get("completed_at"):
            days.add(module["completed_at"][:10])
    for attempt in record["attempts"]:
        if attempt.get("created_at"):
            days.add(attempt["created_at"][:10])
    if not days:
        return 0
    today = date.today().isoformat()
    cursor = today if today in days else (
        date.fromordinal(date.today().toordinal() - 1).isoformat())
    streak = 0
    while cursor in days:
        streak += 1
        cursor = date.fromordinal(date.fromisoformat(cursor).toordinal() - 1).isoformat()
    return streak


def summarize(record: dict) -> dict:
    """Derived learner state: module completion, scores and knowledge uplift."""
    done = [module for module in MODULES if module["id"] in record["modules"]]
    baseline, final = _attempt(record, "baseline"), _attempt(record, "final")
    modules_complete = len(done) == len(MODULES)
    percent = round(100 * len(done) / len(MODULES))
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
        "percent": percent,
        "baseline_score": baseline["score"] if baseline else None,
        "final_score": final["score"] if final else None,
        "uplift": final["score"] - baseline["score"] if baseline and final else None,
        "passed": passed,
        "attempts": len(record["attempts"]),
        "certificate": record["certificate"],
        "points": len(done) * 25 + (final["score"] if final else 0),
        "badges": _badges(record, baseline, final, percent, modules_complete, passed),
        "streak_days": _streak_days(record),
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
        "template": (course_record.get("publication") or {}).get("certificate_template", "classic")
        if (course_record.get("publication") or {}).get("certificate_template") in CERTIFICATE_TEMPLATES
        else "classic",
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

"""Reconstruct the governance trail for courses reviewed before it existed.

Everything here is derived from what the course record already stores — comment
authors and timestamps, version authors, sign-offs, the publication. Nothing is
invented, and one thing genuinely cannot be recovered: who settled a comment,
because resolutions were not attributed until now. Those entries say so rather
than guessing, which is also the clearest way to show what the change fixed.

Every reconstructed entry is marked `reconstructed: true`.

Safe to re-run: a course that already has a trail is left alone, and no existing
field is modified or removed.

    uv run python scripts/backfill_audit.py --dry-run
    uv run python scripts/backfill_audit.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import learning  # noqa: E402

# Resolutions predate attribution. Naming a plausible actor would be a fabrication
# in exactly the record that exists to prevent fabrication.
UNKNOWN = {"id": "", "name": "Not recorded", "role": "", "title": "Settled before resolutions were attributed"}


def _actor(user_id: str = "", name: str = "") -> dict:
    found = learning.person(user_id) if user_id else None
    if not found and name:
        found = next((entry for entry in learning.roster() if entry["name"] == name), None)
    return found or {"id": user_id, "name": name or user_id or "Unknown", "role": "", "title": ""}


def _entry(actor: dict, action: str, at: str, summary: str, **detail) -> dict:
    return {
        "id": learning._id(),
        "at": at,
        "action": action,
        "actor_id": actor["id"],
        "actor_name": actor["name"],
        "actor_title": actor.get("title", ""),
        "actor_role": actor.get("role", ""),
        "summary": summary,
        "detail": {key: value for key, value in detail.items() if value is not None},
        "reconstructed": True,
    }


def rebuild(record: dict) -> list[dict]:
    entries: list[dict] = []

    for comment in record["comments"]:
        author = _actor(comment.get("author_id", ""), comment.get("author_name", ""))
        entries.append(_entry(
            author, "comment.raised", comment["created_at"],
            f"{author['name']} raised a {comment['severity']} comment on {comment['target']}",
            comment_id=comment["id"], severity=comment["severity"], target=comment["target"]))

        if not comment.get("resolved_at"):
            continue
        # "closed" is the version cut, recorded below; what happened here is the
        # resolution that preceded it.
        settled = "dismissed" if comment["status"] == "dismissed" else "addressed"
        verb = "dismissed" if settled == "dismissed" else "marked addressed"
        entries.append(_entry(
            UNKNOWN, "comment.resolved", comment["resolved_at"],
            f"A {comment['severity']} comment on {comment['target']} was {verb}",
            comment_id=comment["id"], severity=comment["severity"], target=comment["target"],
            now=settled, resolution=comment.get("resolution"),
            origin=comment.get("origin"), check=comment.get("check")))

    for version in record["versions"]:
        if not version.get("created_at"):
            continue  # the agent's first draft, which predates any review
        author = _actor(version.get("author_id", ""), version.get("author_name", ""))
        entries.append(_entry(
            author, "version.cut", version["created_at"],
            f"{author['name']} cut version {version['version']}, "
            f"closing {len(version.get('addressed', []))} comment(s)",
            version=version["version"], closed=version.get("addressed") or None))

    for signoff in record["signoffs"]:
        author = _actor(signoff.get("author_id", ""), signoff.get("author_name", ""))
        entries.append(_entry(
            author, "signoff.recorded", signoff["created_at"],
            f"{author['name']} recorded "
            f"{'approval' if signoff['decision'] == 'approved' else 'changes requested'} "
            f"for v{signoff['version']}",
            version=signoff["version"], decision=signoff["decision"], note=signoff.get("note") or None))

    publication = record.get("publication")
    if publication:
        author = _actor(name=publication.get("published_by", ""))
        entries.append(_entry(
            author, "course.published", publication["published_at"],
            f"{author['name']} published v{publication['version']} to "
            f"{len(publication['assignees'])} trainee(s), due {publication['due_on']}",
            version=publication["version"], starts_on=publication["starts_on"],
            due_on=publication["due_on"], assignees=publication["assignees"]))

    return sorted(entries, key=lambda entry: entry["at"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show what would be written and stop")
    args = parser.parse_args()

    root = learning._platform("courses")
    paths = sorted(root.glob("*.json")) if root.exists() else []
    if not paths:
        print("No courses found.")
        return 0

    for path in paths:
        record = learning._json(path)
        if record.get("audit"):
            print(f"= {path.stem}: already has {len(record['audit'])} entries — left untouched.")
            continue

        entries = rebuild(record)
        unknown = sum(1 for entry in entries if entry["actor_name"] == UNKNOWN["name"])
        print(f"{'?' if args.dry_run else '+'} {path.stem}: {len(entries)} entries reconstructed"
              f"{f', {unknown} with no recorded actor' if unknown else ''}")
        if args.dry_run:
            for entry in entries:
                print(f"    {entry['at'][:19]}  {entry['action']:<18} {entry['summary']}")
            continue

        record["audit"] = entries
        learning._write(path, record)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

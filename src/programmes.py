"""Clients, and the training programmes that run inside them.

A course is content. A *programme* is that content in the field: published to a
named cohort, on a schedule, for one client. The distinction matters because
almost everything management asks — what is running, what finished, how the last
cycle went — is a question about programmes, not about courses.

Lifecycle is derived, not stored, with one exception. Whether a programme is
scheduled, live or complete is a fact about the calendar and the cohort, and
computing it from those means the label can never drift from what is true. A
stored state would need a job to keep it honest and would be wrong between runs.
Archiving is the exception, because it is a decision a person makes rather than
something the dates imply, so it is recorded with who made it and when.
"""

from datetime import date
from pathlib import Path

from src import learning
from src.agent import content_path

STATES = ("draft", "scheduled", "live", "completed", "archived")

# One client, described honestly. The model takes N; inventing tenants to look
# multi-tenant would put fabricated organisations in a demo about not fabricating.
SEED_CLIENTS = [{
    "id": "pfizer",
    "name": "Pfizer",
    "region": "United States",
    "jurisdiction": "US",
    "curriculum": "us_oncology",
}]

DEFAULT_CLIENT = SEED_CLIENTS[0]["id"]


def _path() -> Path:
    return content_path("platform", "clients.json")


def clients() -> list[dict]:
    path = _path()
    if not path.exists():
        learning._write(path, SEED_CLIENTS)
        return [dict(entry) for entry in SEED_CLIENTS]
    return learning._json(path)


def client(client_id: str) -> dict:
    found = next((entry for entry in clients() if entry["id"] == client_id), None)
    if not found:
        raise ValueError(f"Unknown client {client_id}")
    return found


def _on(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def state_of(record: dict, cohort: dict | None = None, today: date | None = None) -> str:
    """Where this programme is in its life, from the calendar and the cohort."""
    if record.get("archived"):
        return "archived"
    publication = record.get("publication")
    if record.get("status") != "published" or not publication:
        return "draft"

    today = today or date.today()
    starts, due = _on(publication.get("starts_on")), _on(publication.get("due_on"))
    if starts and today < starts:
        return "scheduled"
    # Everyone certified is finished, whatever the calendar says — the schedule is
    # a deadline, not the definition of done.
    if cohort and cohort["assigned"] and cohort["certified"] >= cohort["assigned"]:
        return "completed"
    if due and today > due:
        return "completed"
    return "live"


def _manifest(run_id: str) -> dict:
    path = content_path("content", Path(run_id).name, "manifest.json")
    return learning._json(path) if path.exists() else {}


def programme(run_id: str, today: date | None = None) -> dict:
    """One course seen as a programme: its schedule, its cohort and where it stands."""
    record = learning.course(run_id)
    manifest = _manifest(run_id)
    publication = record.get("publication") or {}
    numbers = learning.cohort(run_id) if publication else None
    today = today or date.today()
    due = _on(publication.get("due_on"))
    return {
        "run_id": run_id,
        "client_id": record.get("client_id", DEFAULT_CLIENT),
        "drug": manifest.get("drug", {}),
        "title": manifest.get("program_title"),
        # Set when this programme runs content built for an earlier one.
        "reuses": manifest.get("reuses"),
        "version": record.get("version", 1),
        "state": state_of(record, numbers, today),
        "starts_on": publication.get("starts_on"),
        "due_on": publication.get("due_on"),
        "days_remaining": (due - today).days if due else None,
        "published_at": publication.get("published_at"),
        "published_by": publication.get("published_by"),
        "overrides": len(publication.get("overrides") or []),
        "archived": record.get("archived"),
        "cohort": {
            "assigned": numbers["assigned"] if numbers else 0,
            "started": numbers["started"] if numbers else 0,
            "certified": numbers["certified"] if numbers else 0,
            "average_uplift": numbers["average_uplift"] if numbers else None,
        },
    }


def _run_ids() -> list[str]:
    root = content_path("platform", "courses")
    return sorted(path.stem for path in root.glob("*.json")) if root.exists() else []


def for_client(client_id: str = DEFAULT_CLIENT, include_drafts: bool = False,
               today: date | None = None) -> dict:
    """Every programme a client has, newest first, with a count per state."""
    entry = client(client_id)
    found = [programme(run_id, today) for run_id in _run_ids()]
    found = [item for item in found if item["client_id"] == client_id]
    if not include_drafts:
        found = [item for item in found if item["state"] != "draft"]
    found.sort(key=lambda item: item["published_at"] or "", reverse=True)
    return {
        "client": entry,
        "programmes": found,
        "states": {state: sum(1 for item in found if item["state"] == state) for state in STATES},
    }


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    return (ordered[middle] if len(ordered) % 2
            else round((ordered[middle - 1] + ordered[middle]) / 2, 1))


def portfolio(client_id: str = DEFAULT_CLIENT, today: date | None = None) -> dict:
    """Everything a client's training did, consolidated across its programmes.

    Archived programmes are included: they were delivered, and leaving them out
    would make the portfolio flatter every time someone tidied up.

    Averages are pooled over learners, never averaged over programmes. A mean of
    means weights a five-person pilot the same as a five-hundred-person rollout and
    reliably reports a number no individual programme produced.
    """
    from src import analytics, judge

    view = for_client(client_id, today=today)
    running = view["programmes"]
    reach = {"assigned": 0, "started": 0, "certified": 0}
    learners: list[dict] = []
    days: list[float] = []
    built = manual = saved = 0
    raised = accepted = settled = blocking = overrides = found = 0
    checkable = citations = 0
    rows = []

    for entry in running:
        run_id = entry["run_id"]
        cohort = learning.cohort(run_id)
        for key in reach:
            reach[key] += cohort[key]
        learners += [item for item in cohort["learners"] if item["uplift"] is not None]

        # A cycle that reuses approved content was not built again. Counting its
        # build cost, its elapsed time or its findings a second time would report a
        # portfolio that did more work than anyone did.
        if entry.get("reuses"):
            rows.append({
                "run_id": run_id, "drug": entry["title"] or entry["drug"].get("brand", run_id),
                "state": entry["state"], "assigned": cohort["assigned"], "certified": cohort["certified"],
                "average_uplift": cohort["average_uplift"], "days_to_publish": None,
                "cost_saved_usd": None, "findings": None, "overrides": entry["overrides"],
                "reuses": entry["reuses"],
            })
            continue

        measured = analytics.roi(run_id)
        if measured["measured"]["days_to_publish"] is not None:
            days.append(measured["measured"]["days_to_publish"])
        saved += measured["saving"]["cost_saved_usd"] or 0
        # One definition of build cost, kept where it already lives: elapsed days at
        # the blended rate plus what the agent actually spent.
        economics = analytics.unit_economics(run_id)
        built += economics["build_cost_usd"]
        manual += economics["manual_build_cost_usd"]

        agreement = judge.agreement(run_id)
        raised += agreement["raised"]
        settled += agreement["settled"]
        accepted += agreement["accepted"]
        overrides += entry["overrides"]
        report = judge.stored_report(run_id) or {}
        findings = report.get("findings", [])
        found += len(findings)
        blocking += sum(1 for item in findings if item["severity"] == "blocking")
        stats = report.get("stats", {})
        checkable += stats.get("checkable", 0)
        citations += stats.get("citations", 0)

        rows.append({
            "run_id": run_id,
            "drug": entry["title"] or entry["drug"].get("brand", run_id),
            "state": entry["state"],
            "assigned": cohort["assigned"],
            "certified": cohort["certified"],
            "average_uplift": cohort["average_uplift"],
            "days_to_publish": measured["measured"]["days_to_publish"],
            "cost_saved_usd": measured["saving"]["cost_saved_usd"],
            "findings": len(findings),
            "overrides": entry["overrides"],
        })

    baseline = analytics.MANUAL_BASELINE
    pooled = lambda key: (round(sum(item[key] for item in learners) / len(learners))
                          if learners else None)
    return {
        "client": view["client"],
        "states": view["states"],
        "programmes": rows,
        "reach": {
            **reach,
            "measured": len(learners),
            "certification_percent": round(100 * reach["certified"] / reach["assigned"]) if reach["assigned"] else None,
        },
        "uplift": {
            "learners": len(learners),
            "baseline": pooled("baseline_score"),
            "final": pooled("final_score"),
            "points": pooled("uplift"),
        },
        "speed": {
            "median_days_to_publish": _median(days),
            "manual_days": baseline["first_version_days"],
            "programmes": len(days),
        },
        "cost": {
            "build_usd": built,
            "manual_usd": manual,
            "saved_usd": saved,
            "per_certified_usd": round(built / reach["certified"]) if reach["certified"] else None,
            "manual_per_certified_usd": round(manual / reach["certified"]) if reach["certified"] else None,
        },
        "governance": {
            "findings": found,
            "blocking_found": blocking,
            "raised_to_reviewers": raised,
            "settled": settled,
            "agreement_percent": round(100 * accepted / settled) if settled else None,
            "overrides": overrides,
            "coverage_percent": round(100 * checkable / citations) if citations else None,
        },
    }


def archive(run_id: str, user_id: str, note: str = "") -> dict:
    """Take a programme out of the running list, on the record.

    Reversible and attributed: archiving is a filing decision, not a deletion, and
    nothing about the course, its cohort or its trail is touched.
    """
    record = learning.course(run_id)
    author = learning._author(user_id, role="admin")
    if record.get("status") != "published":
        raise ValueError("Only a published programme can be archived")
    if record.get("archived"):
        raise ValueError("This programme is already archived")
    record["archived"] = {
        "at": learning._now(),
        "by_id": author["id"],
        "by_name": author["name"],
        "note": note.strip(),
    }
    learning._audit(record, author, "programme.archived",
                    f"{author['name']} archived the programme", note=note.strip() or None)
    learning._save_course(record)
    return programme(run_id)


def restore(run_id: str, user_id: str) -> dict:
    record = learning.course(run_id)
    author = learning._author(user_id, role="admin")
    if not record.get("archived"):
        raise ValueError("This programme is not archived")
    record.pop("archived")
    learning._audit(record, author, "programme.restored", f"{author['name']} restored the programme")
    learning._save_course(record)
    return programme(run_id)

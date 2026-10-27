"""The ten steps a training programme goes through, and where one has got to.

Every step here already existed; none of it was visible as a sequence. Scattered
across tabs, the work reads as a pile of features, and the question a client
actually asks — *what happens, in what order, and who is accountable at each point*
— has to be answered by narration instead of by the product.

State is computed from the same records the rest of the app writes, never stored.
A step is done because the evidence for it exists, so this can neither run ahead of
the work nor fall behind it, and there is no status field for anyone to fix up.
"""

from pathlib import Path

from src import analytics, judge, learning, programmes
from src.agent import content_path

WAITING, CURRENT, DONE = "waiting", "current", "done"


def _json(path: Path) -> dict:
    return learning._json(path) if path.exists() else {}


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def steps(run_id: str) -> dict:
    """Each step, whether it is done, and the evidence that says so."""
    name = Path(run_id).name
    manifest = _json(content_path("content", name, "manifest.json"))
    run = _json(content_path("logs", name, "run.json"))
    record = learning.course(run_id)
    readiness = learning.readiness(record)
    publication = record.get("publication") or {}
    report = judge.stored_report(run_id) or {}
    findings = report.get("findings", [])
    agreement = judge.agreement(run_id)
    cohort = learning.cohort(run_id) if publication else {
        "assigned": 0, "started": 0, "certified": 0, "learners": [], "average_uplift": None}
    baselined = sum(1 for entry in cohort["learners"] if entry.get("baseline_score") is not None)
    roi = analytics.roi(run_id)["measured"] if publication else {}
    saving = analytics.roi(run_id)["saving"] if publication else {}
    programme = programmes.programme(run_id)

    course_href = f"/courses/{run_id}"
    found = [
        {
            "id": "project",
            "title": "The project",
            "detail": f"{programme['drug'].get('brand', 'A drug')} for "
                      f"{programmes.client(programme['client_id'])['name']}, "
                      f"{programmes.client(programme['client_id'])['jurisdiction']} regulatory scope.",
            "done": bool(manifest),
            "evidence": [programme["drug"].get("generic", ""), programme["drug"].get("area", "").split("–")[0].strip()],
            "href": "/portfolio",
        },
        {
            "id": "build",
            "title": "Agents build the content",
            "detail": "Sources gathered, a dossier assembled, then a deck, storyboard, FAQ and quiz "
                      "generated per audience with a citation on every factual unit.",
            "done": bool(report or findings) or bool(manifest.get("citation_count")),
            "evidence": [
                _plural(manifest.get("citation_count", 0), "citation"),
                f"{roi.get('generation_minutes')} min to draft" if roi.get("generation_minutes") is not None else "",
            ],
            "href": f"{course_href}?tab=ppt",
        },
        {
            "id": "check",
            "title": "The machine checks it before a human does",
            "detail": "Every citable unit is read back against the stored source documents. "
                      "Blocking findings are raised into the review queue automatically.",
            "done": bool(findings),
            "evidence": [
                _plural(len(findings), "finding"),
                f"{sum(1 for item in findings if item['severity'] == 'blocking')} blocking",
                f"{report.get('stats', {}).get('coverage_percent', 0)}% checkable",
            ],
            "href": f"{course_href}?tab=checks",
        },
        {
            "id": "review",
            "title": "Experts review, and the checker is checked back",
            "detail": "A reviewer addresses or dismisses each finding. A dismissal that the source "
                      "still contradicts is challenged, and an override is recorded with a reason.",
            "done": bool(readiness["approvals"]) and not readiness["open_blocking"],
            "evidence": [
                _plural(len(record["comments"]), "comment"),
                f"{agreement['agreement_percent']}% agreement" if agreement["agreement_percent"] is not None else "",
                _plural(readiness["approvals"], "sign-off"),
            ],
            "href": f"{course_href}?tab=review",
        },
        {
            "id": "cohort",
            "title": "Target trainees are chosen",
            "detail": "The people who need this course, by role and territory.",
            "done": bool(publication.get("assignees")),
            "evidence": [_plural(len(publication.get("assignees", [])), "trainee")],
            "href": f"{course_href}?tab=publish",
        },
        {
            "id": "schedule",
            "title": "The programme is scheduled and published",
            "detail": "Publication is held until a reviewer has approved and no blocking finding is open.",
            "done": bool(publication),
            "evidence": [
                f"v{publication.get('version')}" if publication else "",
                f"{publication.get('starts_on')} to {publication.get('due_on')}" if publication else "",
                programme["state"],
            ],
            "href": f"{course_href}?tab=publish",
        },
        {
            "id": "access",
            "title": "Trainees are notified and given access",
            "detail": "Only assigned learners can open the course; anyone else is refused at the API.",
            "done": bool(publication.get("notifications")),
            "evidence": [_plural(len(publication.get("notifications", [])), "notification")],
            "href": f"{course_href}?tab=cohort",
        },
        {
            "id": "baseline",
            "title": "A baseline is captured before they learn",
            "detail": "Each learner sits the assessment cold, so the uplift afterwards is the same "
                      "cohort measured twice rather than two different groups.",
            "done": baselined > 0,
            "evidence": [f"{baselined} of {cohort['assigned']} baselined"],
            "href": f"{course_href}?tab=cohort",
        },
        {
            "id": "certify",
            "title": "They complete the course and certify",
            "detail": "A certificate names the course version and the reviewers who approved it.",
            "done": cohort["certified"] > 0,
            "evidence": [
                f"{cohort['certified']} of {cohort['assigned']} certified",
                f"+{cohort['average_uplift']} points" if cohort["average_uplift"] is not None else "",
            ],
            "href": f"{course_href}?tab=cohort",
        },
        {
            "id": "impact",
            "title": "The client sees impact across every programme",
            "detail": "Reach, uplift, time to field and cost per certified learner, consolidated — "
                      "and what never reached the field.",
            "done": bool(publication) and cohort["certified"] > 0,
            "evidence": [
                f"{roi.get('days_to_publish')} days to field" if roi.get("days_to_publish") is not None else "",
                f"${saving['cost_saved_usd']:,} saved" if saving.get("cost_saved_usd") is not None else "",
            ],
            "href": "/portfolio",
        },
    ]

    # The first step that is not done is where the work actually is; everything
    # after it is waiting on this one rather than independently unstarted.
    current = next((item for item in found if not item["done"]), None)
    for item in found:
        item["state"] = DONE if item["done"] else (CURRENT if item is current else WAITING)
        item["evidence"] = [value for value in item["evidence"] if value]
        del item["done"]

    done = sum(1 for item in found if item["state"] == DONE)
    return {
        "run_id": run_id,
        "steps": found,
        "done": done,
        "total": len(found),
        "percent": round(100 * done / len(found)),
        "state": programme["state"],
    }

import asyncio
import io
import json
import openpyxl
import zipfile
import re
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from src import analytics, assistant, completeness, journey, judge, learning, material, present, programmes
from src.agent import content_path, create_run, get_run, passing_percent, run_agent

app = FastAPI(title="PharmaLearn API")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)
tasks: set[asyncio.Task] = set()


class RunRequest(BaseModel):
    drug: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/courses")
def courses():
    planned = [
        {"id": "eliquis", "name": "Eliquis", "generic": "Apixaban", "area": "Cardiology", "status": "Preview", "progress": 72},
        {"id": "vyndaqel", "name": "Vyndaqel", "generic": "Tafamidis", "area": "Cardiology", "status": "Preview", "progress": 48},
        {"id": "xeljanz", "name": "Xeljanz", "generic": "Tofacitinib", "area": "Immunology", "status": "Preview", "progress": 31},
    ]
    runs: dict[str, list[dict]] = {}
    for path in content_path("content").glob("*/manifest.json"):
        try:
            manifest = json.loads(path.read_text())
            drug = manifest["drug"]
            run_id = manifest.get("run_id", path.parent.name)
            key = drug["brand"].lower()
            candidate = {
                "id": key,
                "run_id": run_id,
                "name": drug["brand"],
                "generic": drug["generic"],
                "area": drug["area"],
                "status": "Ready",
                "progress": 100,
                "generated_at": manifest.get("generated_at", run_id),
            }
            record = learning.course(run_id)
            if record.get("archived"):
                continue
            candidate.update({
                "review_status": record["status"],
                "version": record["version"],
                "assigned": len(record["publication"]["assignees"]) if record.get("publication") else 0,
                "assigned_reviewers": (record.get("review_assignment") or {}).get("reviewers", []),
            })
            runs.setdefault(key, []).append(candidate)
        except (KeyError, json.JSONDecodeError):
            continue

    # A newly generated run must never hide the published course a cohort is already
    # working through. Show the live one and, if a newer draft exists, show that too.
    ready = []
    for entries in runs.values():
        published = [entry for entry in entries if entry["review_status"] == "published"]
        newest = max(entries, key=lambda entry: entry["generated_at"])
        chosen = [max(published, key=lambda entry: entry["generated_at"])] if published else []
        if newest["run_id"] not in {entry["run_id"] for entry in chosen}:
            chosen.append(newest)
        ready.extend(chosen)
    ready.sort(key=lambda course: (course["review_status"] == "published", course["generated_at"]), reverse=True)
    return ready + [course for course in planned if course["name"].lower() not in runs]


@app.post("/api/runs", status_code=202)
async def start_run(request: RunRequest):
    if request.drug.strip().lower() not in {"ibrance", "palbociclib"}:
        raise HTTPException(400, "Content generation currently supports Ibrance only.")
    run = create_run("Ibrance")
    task = asyncio.create_task(run_agent(run["id"], "Ibrance"))
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return run


@app.get("/api/runs/{run_id}")
def run_status(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@app.get("/api/runs/{run_id}/events")
async def events(run_id: str):
    if not get_run(run_id):
        raise HTTPException(404, "Run not found")

    async def stream():
        path = content_path("logs", run_id, "events.jsonl")
        position = 0
        while True:
            if path.exists():
                with path.open() as file:
                    file.seek(position)
                    chunk = file.read()
                    position = file.tell()
                    for line in chunk.splitlines():
                        yield f"data: {line.strip()}\n\n"
            run = get_run(run_id)
            if run and run["status"] in {"completed", "failed"} and path.exists() and position == path.stat().st_size:
                break
            await asyncio.sleep(0.2)

    return StreamingResponse(stream(), media_type="text/event-stream")


def course_content(run_id: str):
    base = content_path("content", run_id)
    if not base.exists():
        raise HTTPException(404, "Content not found")
    def read(path: str):
        try:
            return json.loads((base / path).read_text())
        except FileNotFoundError:
            raise HTTPException(404, "Content not found for this run")
    def learner(name: str):
        root = base / name
        if not root.exists():
            track = {
                "faq": read("assets/faq.json"),
                "quiz": read("assets/quiz.json"),
                "storyboard": read("assets/video_storyboard.json"),
                "deck": read("assets/deck_spec.json"),
                "videos": [],
                "pptx_url": f"/api/runs/{run_id}/assets/ibrance-training.pptx",
            }
        else:
            videos = sorted(
                file for file in (root / "videos").glob("*")
                if file.suffix.lower() in {".mp4", ".mov", ".webm"}
            )
            track = {
                "faq": read(f"{name}/faq.json"),
                "quiz": read(f"{name}/quiz.json"),
                "storyboard": read(f"{name}/storyboard/storyboard.json"),
                "deck": read(f"{name}/ppt/deck_spec.json"),
                "videos": [{
                    "id": file.stem,
                    "title": " ".join(file.stem.replace("_", " ").split()).replace("CDK4 6", "CDK4/6").replace("Can t", "Can't"),
                    "url": f"/api/runs/{run_id}/videos/{name}/{quote(file.name)}",
                } for file in videos],
                "pptx_url": f"/api/runs/{run_id}/downloads/{name}/pptx",
            }
        track["quiz"]["passing_score"] = passing_percent(track["quiz"])
        return track

    response = {
        "manifest": read("manifest.json"),
        "sources": read("source_manifest.json"),
        "blueprint": read("learning_blueprint.json"),
        "default_learner": "hcp",
        "learners": {name: learner(name) for name in ["hcp", "msl"]},
    }
    response.update(response["learners"]["hcp"])
    return response


@app.get("/api/runs/{run_id}/content")
def content(run_id: str):
    return course_content(run_id)


@app.get("/api/runs/{run_id}/downloads/{learner}/pptx")
def learner_pptx(run_id: str, learner: str):
    if learner not in {"msl", "hcp"}:
        raise HTTPException(404, "Learner not found")
    files = list(content_path("content", run_id, learner, "ppt").glob("*.pptx"))
    if len(files) != 1:
        raise HTTPException(404, "PowerPoint not found")
    return FileResponse(files[0], filename=files[0].name, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")


@app.get("/api/runs/{run_id}/videos/{learner}/{name}")
def learner_video(run_id: str, learner: str, name: str):
    if learner not in {"msl", "hcp"}:
        raise HTTPException(404, "Learner not found")
    root = content_path("content", run_id, learner, "videos").resolve()
    target = (root / Path(name).name).resolve()
    media_types = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}
    if root not in target.parents or not target.exists() or target.suffix.lower() not in media_types:
        raise HTTPException(404, "Video not found")
    return FileResponse(target, media_type=media_types[target.suffix.lower()])


@app.get("/api/runs/{run_id}/assets/{name}")
def asset(run_id: str, name: str):
    assets = content_path("content", run_id, "assets").resolve()
    target = (assets / Path(name).name).resolve()
    if assets not in target.parents or not target.exists():
        raise HTTPException(404, "Asset not found")
    return FileResponse(target, filename=target.name, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")


BASELINE_QUESTIONS = 5
# Enough that the format is measured at both ends without doubling the baseline.
BASELINE_FIGURES = 2


class SessionRequest(BaseModel):
    user_id: str | None = None
    email: str | None = None
    role: str | None = None


class CommentRequest(BaseModel):
    user_id: str
    target: str
    severity: str
    body: str


class ResolveRequest(BaseModel):
    user_id: str
    status: str
    resolution: str | None = None
    # Supplied only on the second attempt, once a dismissal has been challenged.
    override_reason: str | None = None


class VersionRequest(BaseModel):
    user_id: str
    summary: str = ""


class SignoffRequest(BaseModel):
    user_id: str
    decision: str
    note: str = ""


class AssignReviewersRequest(BaseModel):
    user_id: str
    reviewer_ids: list[str]
    note: str = ""


class PublishRequest(BaseModel):
    user_id: str
    starts_on: str
    due_on: str
    assignees: list[str]
    message: str = ""
    frequency: str = "once"
    certificate_template: str = "classic"


class ModuleRequest(BaseModel):
    module_id: str
    completed: bool = True


class AnswerRequest(BaseModel):
    answers: dict[str, int]
    # Demo affordance, refused unless PHARMALEARN_DEMO_FILL is set.
    fill_unanswered: bool = False


class QuizBuildRequest(BaseModel):
    title: str = ""


class FeedbackRequest(BaseModel):
    module_id: str
    rating: int
    comment: str = ""


class ObjectionRequest(BaseModel):
    user_id: str
    question: str
    answer: str
    citations: list[dict] = []


class ObjectionUpdate(BaseModel):
    user_id: str
    question: str | None = None
    answer: str | None = None
    retired: bool | None = None


class SafetyRequest(BaseModel):
    user_id: str
    concern: str


class SafetyReviewRequest(BaseModel):
    user_id: str


class ChatRequest(BaseModel):
    question: str
    learner: str = "hcp"
    # Set when the question is about one review finding: answered from the
    # finding's own state (check, quote, match) instead of dossier search.
    finding_id: str | None = None
    # Set when a trainee is asking, so "when is this due" answers about their own
    # progress rather than the cohort's — otherwise the bot tells someone their
    # overdue course is "completed", because for the cohort it is.
    user_id: str = ""


class WebSourceRequest(BaseModel):
    url: str
    note: str = ""


def _guard(action):
    """Run a state change, turning the state layer's rejections into 400s."""
    try:
        return action()
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@app.get("/api/people")
def people():
    return [learning.public_person(entry) for entry in learning.roster()]


class RoleRequest(BaseModel):
    by_user_id: str
    label: str
    description: str = ""
    capabilities: list[str] = []
    learner: bool = False
    track: str = "hcp"


class AssignRoleRequest(BaseModel):
    by_user_id: str
    role_id: str


@app.get("/api/capabilities")
def capabilities():
    """The permission catalog custom roles are built from."""
    return [
        {"id": capability_id, "label": label, "description": description}
        for capability_id, label, description in learning.CAPABILITIES
    ]


@app.get("/api/roles")
def roles():
    """Every assignable role: built-ins plus what the training team built."""
    return learning.roles()


@app.post("/api/roles", status_code=201)
def create_role(request: RoleRequest):
    return _guard(lambda: learning.create_role(
        request.by_user_id, request.label, request.description,
        request.capabilities, request.learner, request.track,
    ))


@app.post("/api/people/{user_id}/role")
def assign_person_role(user_id: str, request: AssignRoleRequest):
    return _guard(lambda: learning.assign_role(
        request.by_user_id, Path(user_id).name, request.role_id))


@app.delete("/api/roles/{role_id}")
def delete_role(role_id: str, by_user_id: str = ""):
    return _guard(lambda: learning.delete_role(by_user_id, Path(role_id).name))


@app.post("/api/session")
def session(request: SessionRequest):
    return _guard(lambda: learning.public_person(
        learning.sign_in(request.user_id, request.email, request.role)))


@app.get("/api/runs/{run_id}/review")
def review(run_id: str):
    record = learning.course(run_id)
    return {**record, "readiness": learning.readiness(record), "targets": learning.REVIEW_TARGETS}


@app.post("/api/runs/{run_id}/review/submit")
def review_submit(run_id: str, request: SessionRequest):
    return _guard(lambda: learning.submit_for_review(run_id, request.user_id))


@app.post("/api/runs/{run_id}/review/comments", status_code=201)
def review_comment(run_id: str, request: CommentRequest):
    return _guard(lambda: learning.add_comment(
        run_id, request.user_id, request.target, request.severity, request.body
    ))


@app.patch("/api/runs/{run_id}/review/comments/{comment_id}")
def review_resolve(run_id: str, comment_id: str, request: ResolveRequest):
    return _guard(lambda: learning.resolve_comment(
        run_id, comment_id, request.status, request.resolution, request.user_id, request.override_reason
    ))


@app.post("/api/runs/{run_id}/review/comments/{comment_id}/repoint")
def review_repoint(run_id: str, comment_id: str, request: SessionRequest):
    """Apply the one fix a citation finding actually has: cite a better document."""
    citation = _guard(lambda: judge.repoint_comment(run_id, comment_id, request.user_id))
    record = learning.course(run_id)
    return {"citation": citation, **record, "readiness": learning.readiness(record),
            "targets": learning.REVIEW_TARGETS}


@app.get("/api/runs/{run_id}/review/comments/{comment_id}/evidence")
def review_evidence(run_id: str, comment_id: str):
    """What a reviewer needs to settle this comment without leaving it."""
    record = learning.course(run_id)
    comment = next((entry for entry in record["comments"] if entry["id"] == comment_id), None)
    if not comment:
        raise HTTPException(404, "Comment not found")
    evidence = judge.evidence_for(run_id, comment)
    if not evidence:
        # A human's comment has no finding behind it, so there is nothing to show.
        raise HTTPException(404, "No machine evidence behind this comment")
    return evidence


@app.post("/api/runs/{run_id}/review/assign")
def review_assign(run_id: str, request: AssignReviewersRequest):
    return _guard(lambda: learning.assign_reviewers(
        run_id, request.user_id, request.reviewer_ids, request.note
    ))


@app.post("/api/runs/{run_id}/review/versions", status_code=201)
def review_version(run_id: str, request: VersionRequest):
    return _guard(lambda: learning.publish_version(run_id, request.user_id, request.summary))


@app.get("/api/runs/{run_id}/objections")
def list_objections(run_id: str):
    """Approved answers to the objections HCPs raise in the field."""
    return learning.objections(run_id)


@app.post("/api/runs/{run_id}/objections", status_code=201)
def create_objection(run_id: str, request: ObjectionRequest):
    return _guard(lambda: learning.add_objection(
        run_id, request.user_id, request.question, request.answer, request.citations))


@app.patch("/api/runs/{run_id}/objections/{objection_id}")
def edit_objection(run_id: str, objection_id: str, request: ObjectionUpdate):
    return _guard(lambda: learning.update_objection(
        run_id, request.user_id, objection_id, request.question, request.answer, request.retired))


@app.post("/api/runs/{run_id}/safety", status_code=201)
def report_safety(run_id: str, request: SafetyRequest):
    """Raise a safety concern from the field; triage is staff work."""
    return _guard(lambda: learning.report_safety(run_id, request.user_id, request.concern))


@app.get("/api/runs/{run_id}/safety")
def list_safety(run_id: str, user_id: str):
    def _list():
        learning.require_capability(user_id, "review.resolve")
        return learning.safety_reports(run_id)
    return _guard(_list)


@app.patch("/api/runs/{run_id}/safety/{report_id}")
def triage_safety(run_id: str, report_id: str, request: SafetyReviewRequest):
    return _guard(lambda: learning.review_safety(run_id, request.user_id, report_id))


@app.post("/api/runs/{run_id}/review/signoff", status_code=201)
def review_signoff(run_id: str, request: SignoffRequest):
    return _guard(lambda: learning.add_signoff(run_id, request.user_id, request.decision, request.note))


@app.post("/api/runs/{run_id}/publication")
def publish(run_id: str, request: PublishRequest):
    return _guard(lambda: learning.publish_course(
        run_id, request.user_id, request.starts_on, request.due_on, request.assignees, request.message,
        frequency=request.frequency,
        certificate_template=request.certificate_template,
    ))


@app.get("/api/certificate-templates")
def certificate_templates():
    """The three certificate designs the training team can pick at publish."""
    return [
        {"id": template_id, **spec}
        for template_id, spec in learning.CERTIFICATE_TEMPLATES.items()
    ]


@app.get("/api/runs/{run_id}/cohort")
def cohort(run_id: str):
    return learning.cohort(run_id)


@app.get("/api/runs/{run_id}/alerts")
def noncompliance_alerts(run_id: str):
    """Flag every learner falling short: overdue, below-requirement, unbaselined."""
    return learning.noncompliance(run_id)


class EscalationCheckRequest(BaseModel):
    user_id: str


@app.get("/api/runs/{run_id}/escalations")
def escalations(run_id: str):
    """The live escalation ladder: every flag with its level, owner and first-seen date."""
    return learning.escalation_state(Path(run_id).name)


@app.post("/api/runs/{run_id}/escalations/check")
def run_escalation_check(run_id: str, request: EscalationCheckRequest):
    """Run the ladder: stamp first-seen dates, record level changes, prune resolved."""
    return _guard(lambda: learning.check_escalations(Path(run_id).name, request.user_id))


@app.get("/api/runs/{run_id}/retention")
def retention_report(run_id: str):
    """What data this course holds and how long each class stays. Report-only."""
    return learning.retention(Path(run_id).name)


@app.get("/api/runs/{run_id}/timeline")
def version_timeline(run_id: str):
    """Every version and what happened to it, oldest first."""
    return learning.version_timeline(Path(run_id).name)


@app.get("/api/dashboard/results")
def dashboard_results():
    """Results across every published course for the admin dashboard."""
    rows = []
    for record in learning.published_courses():
        try:
            data = learning.cohort(record["run_id"])
            manifest = json.loads(content_path("content", Path(record["run_id"]).name, "manifest.json").read_text())
            name = manifest["drug"]["brand"]
        except (OSError, KeyError, json.JSONDecodeError):
            continue
        rows.append({"run_id": record["run_id"], "name": name, "version": record["version"],
                     "assigned": data["assigned"], "started": data["started"],
                     "certified": data["certified"], "average_uplift": data["average_uplift"],
                     "average_final": data["average_final"]})
    return {"courses": rows, "assigned": sum(row["assigned"] for row in rows),
            "certified": sum(row["certified"] for row in rows)}


@app.get("/api/learners/{user_id}/dashboard")
def learner_dashboard(user_id: str):
    """One learner's whole picture: every assignment, totals, and open flags."""
    person = learning.person(Path(user_id).name)
    if not person:
        raise HTTPException(404, "Unknown learner")
    courses = []
    for record in learning.assignments(person["id"]):
        state = learning.summarize(learning.progress(record["run_id"], person["id"]))
        courses.append({"run_id": record["run_id"], "version": record["version"],
                        "state": learning.assignment_state(record["publication"], state),
                        "stage": state["stage"], "percent": state["percent"], "points": state["points"],
                        "passed": state["passed"], "certificate": state["certificate"]})
    alerts = []
    for record in learning.published_courses():
        alerts.extend(alert for alert in learning.noncompliance(record["run_id"])
                      if alert["user_id"] == person["id"])
    return {"user": person, "courses": courses,
            "points": sum(row["points"] for row in courses),
            "certified": sum(1 for row in courses if row["certificate"]),
            "overdue": sum(1 for row in courses if row["state"] == "overdue"),
            "alerts": alerts}


@app.get("/api/runs/{run_id}/analytics")
def course_analytics(run_id: str):
    return analytics.analytics(run_id)


@app.get("/api/runs/{run_id}/export/completions")
def export_completions(run_id: str):
    """CSV export of cohort completions for an external LMS or compliance pack."""
    data = learning.cohort(run_id)
    header = ["user_id", "name", "role", "title", "stage", "modules_complete", "modules_total", "percent", "points", "baseline_score", "final_score", "uplift", "passed", "attempts", "certificate_code", "certificate_issued_at"]
    def cell(value) -> str:
        text = "" if value is None else str(value)
        return '"' + text.replace('"', '""') + '"' if any(mark in text for mark in [",", '"', "\n"]) else text
    lines = [",".join(header)]
    for learner in data["learners"]:
        cert = learner.get("certificate") or {}
        lines.append(",".join(cell(learner.get(key)) if key not in {"certificate_code", "certificate_issued_at"} else cell(cert.get("code" if key == "certificate_code" else "issued_at")) for key in header))
    body = "\r\n".join(lines) + "\r\n"
    return StreamingResponse(iter([body]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{Path(run_id).name}-completions.csv"'})


def _quiz_questions(run_id: str, track: str) -> list[dict]:
    base = content_path("content", Path(run_id).name)
    for candidate in [base / track / "quiz.json", base / "assets" / "quiz.json"]:
        if candidate.exists():
            return json.loads(candidate.read_text()).get("questions", [])
    return []


@app.get("/api/runs/{run_id}/refresh/diff")
def refresh_diff(run_id: str, against: str = ""):
    """Label-change refresh: what changed between two course versions, and re-certification signal."""
    if not against:
        raise HTTPException(400, "Pass ?against=<previous-run-id> to compare two label versions")
    current = {question["id"]: question for question in _quiz_questions(run_id, "hcp") + _quiz_questions(run_id, "msl")}
    previous = {question["id"]: question for question in _quiz_questions(against, "hcp") + _quiz_questions(against, "msl")}
    changed, added, removed = [], [], []
    for qid, question in current.items():
        old = previous.get(qid)
        if old is None:
            added.append(qid)
        elif old.get("prompt") != question.get("prompt") or old.get("correct_index") != question.get("correct_index") or old.get("rationale") != question.get("rationale"):
            changed.append(qid)
    for qid in previous:
        if qid not in current:
            removed.append(qid)
    return {"run_id": run_id, "against": against, "added": added, "removed": removed, "changed": changed, "changed_count": len(changed) + len(added) + len(removed), "recertification_required": bool(changed or added or removed), "note": "Certificates stamp the course version, so a changed course always re-certifies on pass"}


def _sheet(workbook, title, header, rows):
    sheet = workbook.create_sheet(title)
    sheet.append(header)
    for cell in sheet[1]:
        cell.font = openpyxl.styles.Font(bold=True)
    for row in rows:
        sheet.append([row.get(key) if not isinstance(row.get(key), dict) else "" for key in header])
    widths = [max(len(str(row[index] if index < len(row) else "")) for row in [header, *sheet.values]) for index in range(len(header))]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[openpyxl.utils.get_column_letter(index)].width = min(width + 2, 60)


@app.get("/api/runs/{run_id}/export/xls")
def export_xls(run_id: str):
    """Excel workbook: cohort, question difficulty, noncompliance, feedback."""
    data = learning.cohort(run_id)
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    _sheet(workbook, "Cohort", ["user_id", "name", "role", "stage", "modules_complete", "modules_total",
                                "percent", "points", "baseline_score", "final_score", "uplift", "passed",
                                "attempts", "certificate"], [{**learner, "certificate": bool(learner.get("certificate"))} for learner in data["learners"]])
    _sheet(workbook, "Questions", ["track", "id", "prompt", "attempts", "correct", "percent"],
           analytics.question_difficulty(run_id))
    _sheet(workbook, "Noncompliance", ["severity", "tier", "name", "message"], learning.noncompliance(run_id))
    _sheet(workbook, "Feedback", ["name", "module", "rating", "comment"],
           [{**entry, "module": entry.get("module_id")} for entry in data["feedback"]])
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return StreamingResponse(iter([buffer.getvalue()]),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{Path(run_id).name}-report.xlsx"'})

class PresentationRequest(BaseModel):
    title: str = "Training"
    text: str = ""


@app.post("/api/presentations", status_code=201)
def create_presentation(body: PresentationRequest):
    """Training slides (.pptx) from pasted present text, no new dependency.

    Blank-line-separated blocks become slides: the first line is the heading,
    the rest become bullets. Stateless — nothing is stored.
    """
    sections = present.parse_sections(body.text)
    if not sections:
        raise HTTPException(400, "No slide content found")
    payload = present.build_pptx(body.title, sections)
    name = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in body.title.strip() or "training")
    return StreamingResponse(iter([payload]), status_code=201,
                             media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                             headers={"Content-Disposition": f'attachment; filename="{name[:60]}.pptx"'})


@app.get("/api/runs/{run_id}/export/scorm")
def export_scorm(run_id: str):
    """Minimal SCORM 1.2 package: manifest plus the course quiz payloads and completions CSV."""
    manifest = content_path("content", Path(run_id).name, "manifest.json")
    if not manifest.exists():
        raise HTTPException(404, "Content not found")
    drug = json.loads(manifest.read_text())["drug"]["brand"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("imsmanifest.xml", f"""<?xml version="1.0" encoding="UTF-8"?><manifest identifier="PHARMALEARN-{run_id}" version="1.2"><organizations><organization identifier="ORG-1"><title>{drug} training</title><item identifier="ITEM-1" identifierref="RES-1"/></organization></organizations><resources><resource identifier="RES-1" type="webcontent" adlcp:scormtype="sco" href="quiz.json"><file href="quiz.json"/></resource></resources></manifest>""")
        for track in ("hcp", "msl"):
            for question in _quiz_questions(run_id, track):
                package.writestr(f"{track}/quiz.json", json.dumps({"track": track, "questions": _quiz_questions(run_id, track)}, indent=2))
                break
        package.writestr("completions.csv", "user_id,stage\n")
    buffer.seek(0)
    return StreamingResponse(iter([buffer.getvalue()]), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{Path(run_id).name}-scorm12.zip"'})


def _checks_payload(run_id: str, report: dict | None):
    record = learning.course(run_id)
    promoted = {
        comment.get("finding_id"): comment["status"]
        for comment in record["comments"] if comment.get("origin") == "automated_check"
    }
    # A comment raised before the identifier gained its citation matches only on
    # the old form. Where two findings share that old form, one comment exists and
    # the first claims it; the rest report honestly as not yet raised, so the lead
    # can send them rather than believing a reviewer already has them.
    claimed: set[str] = set()

    def status(finding: dict) -> str | None:
        current = promoted.get(judge.finding_id(finding))
        if current:
            return current
        legacy = judge._legacy_finding_id(finding)
        if legacy in claimed or legacy not in promoted:
            return None
        claimed.add(legacy)
        return promoted[legacy]

    findings = [
        {**finding, "id": judge.finding_id(finding), "promoted": status(finding)}
        for finding in (report or {}).get("findings", [])
    ]
    # The report is a snapshot; the corpus is not. Reporting both keeps the record
    # of what was caught on the draft while showing honestly how much more of the
    # course could be checked today.
    try:
        now = judge.coverage_now(run_id)
    except Exception:
        now = {}
    return {**(report or {"run_id": run_id, "stats": {}, "findings": []}),
            "findings": findings, "agreement": judge.agreement(run_id), "now": now}


@app.get("/api/runs/{run_id}/checks")
def checks(run_id: str):
    return _checks_payload(run_id, judge.stored_report(run_id))


@app.post("/api/runs/{run_id}/checks")
async def run_checks(run_id: str, request: SessionRequest):
    """Run the checks, then raise the blocking findings into the review queue."""
    _guard(lambda: learning.require_capability(request.user_id or "", "course.publish"))
    manifest = content_path("content", Path(run_id).name, "manifest.json")
    if not manifest.exists():
        raise HTTPException(404, "Content not found")
    drug = json.loads(manifest.read_text())["drug"]["brand"]
    report = await judge.run(run_id, drug)
    judge.promote(run_id)
    judge.reconcile(run_id)
    return _checks_payload(run_id, report)


class PromoteRequest(BaseModel):
    user_id: str
    finding_ids: list[str]


@app.post("/api/runs/{run_id}/checks/promote", status_code=201)
def promote_findings(run_id: str, request: PromoteRequest):
    _guard(lambda: learning.require_capability(request.user_id, "course.publish"))
    raised = _guard(lambda: judge.promote(run_id, finding_ids=request.finding_ids))
    return {"raised": len(raised), **_checks_payload(run_id, judge.stored_report(run_id))}


class ArchiveRequest(BaseModel):
    user_id: str
    note: str = ""


@app.get("/api/clients")
def all_clients():
    return programmes.clients()


@app.get("/api/clients/{client_id}")
def client_programmes(client_id: str, include_drafts: bool = False):
    """A client and every training programme running inside it."""
    return _guard(lambda: programmes.for_client(client_id, include_drafts))


@app.get("/api/runs/{run_id}/journey")
def course_journey(run_id: str):
    """The ten steps this programme goes through, and where it has got to."""
    return _guard(lambda: journey.steps(run_id))


@app.get("/api/clients/{client_id}/portfolio")
def client_portfolio(client_id: str):
    """Every programme this client ran, consolidated into one report."""
    return _guard(lambda: programmes.portfolio(client_id))


@app.post("/api/runs/{run_id}/archive")
def archive_programme(run_id: str, request: ArchiveRequest):
    return _guard(lambda: programmes.archive(run_id, request.user_id, request.note))


@app.post("/api/runs/{run_id}/restore")
def restore_programme(run_id: str, request: SessionRequest):
    return _guard(lambda: programmes.restore(run_id, request.user_id))


def _completeness_payload(run_id: str) -> dict:
    record = learning.course(run_id)
    raised = {comment.get("finding_id"): comment["status"] for comment in record["comments"]
              if comment.get("finding_id", "").startswith("completeness:")}
    gaps = [{**gap, "promoted": raised.get(gap["finding_id"])} for gap in completeness.gaps(run_id)]
    return {**completeness.matrix(run_id), "gaps": gaps}


@app.get("/api/runs/{run_id}/completeness")
def course_completeness(run_id: str):
    """Required topics against what the course actually covers."""
    return _guard(lambda: _completeness_payload(run_id))


@app.post("/api/runs/{run_id}/completeness/promote", status_code=201)
def promote_gaps(run_id: str, request: PromoteRequest):
    _guard(lambda: learning.require_capability(request.user_id, "course.publish"))
    raised = _guard(lambda: completeness.promote(run_id, finding_ids=request.finding_ids))
    return {"raised": len(raised), **_completeness_payload(run_id)}


@app.post("/api/runs/{run_id}/chat")
async def chat(run_id: str, request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(400, "Ask a question")
    if not content_path("content", Path(run_id).name).exists():
        raise HTTPException(404, "Content not found")
    if request.finding_id:
        return await assistant.about_finding(run_id, request.finding_id, request.question, request.learner)
    return await assistant.answer(run_id, request.question, request.learner, request.user_id)


@app.get("/api/runs/{run_id}/chat/starters")
def chat_starters(run_id: str, context: str = assistant.DEFAULT_CONTEXT):
    if not content_path("content", Path(run_id).name).exists():
        raise HTTPException(404, "Content not found")
    return {"context": context, "starters": assistant.starters(run_id, context)}


def _drug_of(run_id: str) -> str:
    manifest = content_path("content", Path(run_id).name, "manifest.json")
    if not manifest.exists():
        raise HTTPException(404, "Content not found")
    return json.loads(manifest.read_text())["drug"]["brand"]


@app.get("/api/runs/{run_id}/library")
def library(run_id: str):
    """The run's sources, each marked with whether the document is here to read."""
    drug = _drug_of(run_id)
    held = judge.held_documents(drug)
    listed = json.loads(content_path("content", Path(run_id).name, "source_manifest.json").read_text())

    # Collapsed by document identity, not by URL. The same SPL is listed under
    # both drugInfo.cfm and lookup.cfm, and showing it twice would misrepresent
    # how much we hold — the whole reason `source_key` exists.
    documents: list[dict] = []
    by_key: dict[str, dict] = {}
    for source in listed.get("sources", []):
        key = judge.source_key(source.get("url", ""))
        if key in by_key:
            by_key[key]["listed_as"] += 1
            continue
        stored = held.get(key)
        entry = {
            "key": key,
            "title": source.get("title", "") or (stored or {}).get("title", ""),
            "url": source.get("url", ""),
            "publisher": source.get("publisher", ""),
            "source_id": source.get("source_id", "") or (stored or {}).get("source_id", ""),
            "kind": (stored or {}).get("kind", ""),
            "fetched_at": (stored or {}).get("fetched_at", ""),
            "held": bool(stored and stored["readable"]),
            "cited": True,
            "listed_as": 1,
        }
        by_key[key] = entry
        documents.append(entry)
    seen = set(by_key)
    # Documents fetched to resolve citations are held but were never in the
    # original manifest. Hiding them would understate what the reviewer can read.
    for key, stored in held.items():
        if key in seen or not stored["readable"]:
            continue
        documents.append({**stored, "publisher": "", "cited": False, "held": True, "listed_as": 0})

    documents.sort(key=lambda entry: (not entry["held"], not entry["cited"], entry["title"].lower()))
    return {
        "drug": drug,
        "held": sum(1 for entry in documents if entry["held"]),
        "total": len(documents),
        "documents": documents,
    }


@app.get("/api/runs/{run_id}/library/document")
def library_document(run_id: str, url: str = "", key: str = ""):
    drug = _drug_of(run_id)
    held = judge.held_documents(drug)
    wanted = judge.source_key(url) if url else key
    stored = held.get(wanted)
    if not stored or not stored["readable"]:
        raise HTTPException(404, "That document is not held locally")
    text = judge.readable_source(drug, stored["url"])
    if not text:
        raise HTTPException(404, "That document is held but could not be read as text")
    return {**stored, "text": text, "characters": len(text)}


@app.get("/api/runs/{run_id}/evidence")
def evidence(run_id: str, title: str = "", locator: str = "", url: str = ""):
    found = assistant.evidence(run_id, title, locator, url)
    if not found:
        raise HTTPException(404, "No stored evidence matches that citation")
    return found


@app.get("/api/runs/{run_id}/knowledge")
def knowledge(run_id: str):
    base = content_path("content", Path(run_id).name)
    dossier_path = base / "master" / "dossier.json"
    if not dossier_path.exists():
        raise HTTPException(404, "Dossier not found")
    dossier = json.loads(dossier_path.read_text())
    sources = json.loads((base / "source_manifest.json").read_text())
    return {
        "drug": dossier["drug"],
        "title": dossier["title"],
        "gaps": dossier.get("gaps", []),
        "warnings": dossier.get("warnings", []),
        "sources": sources.get("sources", []),
        "sections": [{
            "id": section["id"],
            "title": section["title"],
            "summary": section["summary"],
            "gaps": section.get("gaps", []),
            "warnings": section.get("warnings", []),
            "claims": section.get("claims", []),
        } for section in dossier.get("sections", [])],
    }


def _uploads_root():
    return content_path("uploads")


@app.get("/api/uploads")
def uploads():
    root = _uploads_root()
    records = [json.loads(path.read_text()) for path in sorted(root.glob("*/record.json"))] if root.exists() else []
    return sorted(records, key=lambda record: record["added_at"], reverse=True)


@app.post("/api/uploads", status_code=201)
async def upload(file: UploadFile = File(...), note: str = Form("")):
    payload = await file.read()
    if not payload:
        raise HTTPException(400, "The uploaded file is empty")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    folder = _uploads_root() / stamp
    folder.mkdir(parents=True, exist_ok=True)
    name = Path(file.filename or "document").name
    (folder / name).write_bytes(payload)
    record = {
        "id": stamp,
        "kind": "upload",
        "name": name,
        "note": note.strip(),
        "bytes": len(payload),
        "content_type": file.content_type or "application/octet-stream",
        "added_at": datetime.now(UTC).isoformat(),
        "status": "staged",
    }
    (folder / "record.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


@app.post("/api/uploads/web", status_code=201)
async def pull_web_source(request: WebSourceRequest):
    url = request.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Provide an http(s) URL")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    folder = _uploads_root() / stamp
    folder.mkdir(parents=True, exist_ok=True)
    record = {
        "id": stamp,
        "kind": "web",
        "name": url,
        "note": request.note.strip(),
        "added_at": datetime.now(UTC).isoformat(),
        "status": "staged",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            response = await client.get(url)
        (folder / "fetched.html").write_bytes(response.content)
        title = ""
        if "text/html" in response.headers.get("content-type", ""):
            match = re.search(r"<title[^>]*>(.*?)</title>", response.text, re.S | re.I)
            title = " ".join(match.group(1).split())[:200] if match else ""
        record.update({
            "http_status": response.status_code,
            "title": title,
            "bytes": len(response.content),
            "content_type": response.headers.get("content-type", ""),
        })
    except Exception as error:
        record.update({"status": "unreachable", "error": f"{type(error).__name__}: {error}"})
    (folder / "record.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def _material_error(action):
    try:
        return action()
    except FileNotFoundError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(400, str(error))


@app.post("/api/uploads/{upload_id}/qa", status_code=201)
def extract_qa(upload_id: str):
    """Pull question/answer pairs out of shared material, nothing invented."""
    return _material_error(lambda: material.save_qa(Path(upload_id).name))


@app.get("/api/uploads/{upload_id}/qa")
def read_qa(upload_id: str):
    return _material_error(lambda: material.load_qa(Path(upload_id).name))


@app.post("/api/uploads/{upload_id}/quiz", status_code=201)
def build_upload_quiz(upload_id: str, request: QuizBuildRequest):
    """Turn extracted Q&A pairs into a scored multiple-choice quiz."""
    return _material_error(lambda: material.build_quiz(Path(upload_id).name, request.title))


@app.get("/api/uploads/{upload_id}/quiz")
def read_upload_quiz(upload_id: str):
    return _material_error(lambda: material.load_quiz(Path(upload_id).name))


def _learner_context(user_id: str, run_id: str):
    learner = learning.person(user_id)
    if not learner:
        raise HTTPException(404, "Person not found")
    record = learning.course(run_id)
    if not record.get("publication") or user_id not in record["publication"]["assignees"]:
        raise HTTPException(403, "This course has not been assigned to you")
    track = learning.track_for(learner["role"])
    return learner, record, course_content(run_id), track


@app.get("/api/learn/{user_id}")
def learner_home(user_id: str):
    learner = learning.person(user_id)
    if not learner:
        raise HTTPException(404, "Person not found")
    courses = []
    for record in learning.assignments(user_id):
        manifest_path = content_path("content", Path(record["run_id"]).name, "manifest.json")
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        publication = record["publication"]
        summary = learning.summarize(learning.progress(record["run_id"], user_id))
        courses.append({
            "run_id": record["run_id"],
            "drug": manifest["drug"],
            # A cycle names the programme; the drug names the medicine. Keeping them
            # apart means a card can say "Annual recertification" without any card
            # ever having to misname what is inside it.
            "title": manifest.get("program_title"),
            "version": publication["version"],
            "starts_on": publication["starts_on"],
            "due_on": publication["due_on"],
            "message": publication["message"],
            "summary": summary,
            "state": learning.assignment_state(publication, summary),
            "days_remaining": learning.days_until(publication["due_on"]),
            "days_until_start": learning.days_until(publication["starts_on"]),
        })
    return {"user": learner, "track": learning.track_for(learner["role"]), "courses": courses}


@app.get("/api/learn/{user_id}/{run_id}")
def learner_course(user_id: str, run_id: str):
    learner, record, content_value, track = _learner_context(user_id, run_id)
    state = learning.progress(run_id, user_id)
    feedback = {entry["module_id"]: entry for entry in state["feedback"]}
    return {
        "user": learner,
        "track": track,
        "manifest": content_value["manifest"],
        "sources": content_value["sources"],
        "content": content_value["learners"][track],
        "publication": record["publication"],
        "version": record["version"],
        "modules": [{
            **module,
            "completed": module["id"] in state["modules"],
            "feedback": feedback.get(module["id"]),
        } for module in learning.MODULES],
        "summary": learning.summarize(state),
    }


@app.post("/api/learn/{user_id}/{run_id}/modules")
def learner_module(user_id: str, run_id: str, request: ModuleRequest):
    _learner_context(user_id, run_id)
    state = _guard(lambda: learning.set_module(run_id, user_id, request.module_id, request.completed))
    return {"modules": state["modules"], "summary": learning.summarize(state)}


def _questions(content_value, track: str, kind: str):
    questions = content_value["learners"][track]["quiz"]["questions"]
    if kind != "baseline":
        return questions
    # Sample the plain questions as before, keep every group whole, and make sure
    # at least one figure is asked.
    #
    # Groups are kept intact rather than sampled because a half-board is not a
    # shorter board, it is a broken one — the buckets stop balancing and the
    # learner can infer answers from what is missing. Figure questions *are*
    # independent, so they can be sampled, but they have to be sampled as figures:
    # left to the plain stride they fell off the end entirely and the format was
    # only ever asked at the finish.
    #
    # The rule behind both: uplift is a comparison, so a skill measured only at the
    # end gets counted as learning without ever having been tested for at the start.
    plain = [question for question in questions if not question.get("group") and not question.get("figure")]
    figures = [question for question in questions if question.get("figure")]
    chosen = {question["id"] for question in
              (plain[::2][:BASELINE_QUESTIONS] or plain[:BASELINE_QUESTIONS]) + figures[:BASELINE_FIGURES]}
    return [
        question for question in questions
        if question["id"] in chosen or question.get("group")
    ]


def _groups(quiz: dict, questions: list[dict]) -> list[dict]:
    """The groups the asked questions actually draw on, in question order."""
    present = {question["group"] for question in questions if question.get("group")}
    return [group for group in quiz.get("groups", []) if group["id"] in present]


@app.get("/api/learn/{user_id}/{run_id}/assessment/{kind}")
def assessment(user_id: str, run_id: str, kind: str):
    if kind not in {"baseline", "final"}:
        raise HTTPException(404, "Assessment not found")
    _learner, _record, content_value, track = _learner_context(user_id, run_id)
    quiz = content_value["learners"][track]["quiz"]
    state = learning.progress(run_id, user_id)
    attempts = [attempt for attempt in state["attempts"] if attempt["kind"] == kind]
    asked = _questions(content_value, track, kind)
    return {
        "kind": kind,
        "title": quiz["title"],
        # Already a percentage: `course_content` normalizes every quiz it reads.
        # Normalizing again read that percentage as a raw count, so one quiz
        # reported 25% in the workspace and 78% to the learner sitting it.
        "passing_score": quiz["passing_score"],
        "gated": kind == "final",
        # Tells the page whether to offer the fill-the-rest control at all.
        "demo_fill": learning.DEMO_FILL,
        "groups": _groups(quiz, asked),
        "questions": [{
            "id": question["id"],
            "prompt": question["prompt"],
            "options": question["options"],
            "group": question.get("group"),
            "figure": question.get("figure"),
        } for question in asked],
        "attempts": attempts,
    }


@app.post("/api/learn/{user_id}/{run_id}/assessment/{kind}", status_code=201)
def submit_assessment(user_id: str, run_id: str, kind: str, request: AnswerRequest):
    if kind not in {"baseline", "final"}:
        raise HTTPException(404, "Assessment not found")
    _learner, _record, content_value, track = _learner_context(user_id, run_id)
    quiz = content_value["learners"][track]["quiz"]
    questions = _questions(content_value, track, kind)
    if kind == "final" and learning.summarize(learning.progress(run_id, user_id))["modules_complete"] < len(learning.MODULES):
        raise HTTPException(400, "Complete every learning module before the final assessment")
    result = _guard(lambda: learning.record_attempt(
        run_id, user_id, kind, request.answers, questions, quiz["passing_score"],
        fill_unanswered=request.fill_unanswered,
    ))
    return {
        **result,
        "groups": _groups(quiz, questions),
        "review": [{
            "id": question["id"],
            "prompt": question["prompt"],
            "options": question["options"],
            "group": question.get("group"),
            "figure": question.get("figure"),
            "chosen": request.answers.get(question["id"]),
            "correct_index": question["correct_index"],
            "correct": request.answers.get(question["id"]) == question["correct_index"],
            "rationale": question["rationale"],
            "citations": question["citations"],
        } for question in questions],
    }


@app.post("/api/learn/{user_id}/{run_id}/feedback", status_code=201)
def learner_feedback(user_id: str, run_id: str, request: FeedbackRequest):
    _learner_context(user_id, run_id)
    return _guard(lambda: learning.add_feedback(
        run_id, user_id, request.module_id, request.rating, request.comment
    ))


@app.get("/api/learn/{user_id}/{run_id}/certificate")
def certificate(user_id: str, run_id: str):
    _learner, _record, content_value, _track = _learner_context(user_id, run_id)
    issued = learning.issue_certificate(run_id, user_id)
    if not issued:
        raise HTTPException(404, "Finish every module and pass the final assessment to earn a certificate")
    return {**issued, "drug": content_value["manifest"]["drug"], "course_title": content_value["blueprint"]["title"]}


@app.delete("/api/learn/{user_id}/{run_id}/attempts")
def reset_learner_attempts(user_id: str, run_id: str, by: str = ""):
    """An admin clears a learner's assessment answers so they start over."""
    person = learning.person(by) if by else None
    return _guard(lambda: learning.reset_attempts(
        Path(run_id).name, Path(user_id).name, (person or {}).get("role", ""),
        actor_id=Path(by).name if by else ""))


@app.get("/api/learn/{user_id}/{run_id}/reinforce")
def reinforce(user_id: str, run_id: str):
    """Spaced reinforcement: practice set built from this learner's missed questions."""
    try:
        _learner, _record, content_value, track = _learner_context(user_id, run_id)
    except FileNotFoundError:
        return {"run_id": run_id, "user_id": user_id, "missed_count": 0, "questions": []}
    quiz = (content_value.get("learners", {}).get(track) or {}).get("quiz") or {}
    questions = quiz.get("questions", [])
    if not questions:
        return {"run_id": run_id, "user_id": user_id, "missed_count": 0, "questions": []}
    by_id = {question["id"]: question for question in questions}
    ever_correct: set[str] = set()
    ever_seen: set[str] = set()
    for attempt in learning.progress(run_id, user_id)["attempts"]:
        for qid, chosen in (attempt.get("answers") or {}).items():
            ever_seen.add(qid)
            if qid in by_id and chosen == by_id[qid]["correct_index"]:
                ever_correct.add(qid)
    missed = [by_id[qid] for qid in ever_seen if qid in by_id and qid not in ever_correct]
    return {"run_id": run_id, "user_id": user_id, "missed_count": len(missed), "questions": [{k: question[k] for k in ("id", "prompt", "options", "citations") if k in question} for question in missed]}

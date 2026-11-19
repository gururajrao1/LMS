"""Seed Shashi demo: 4 users + 2 courses matching the 11-Nov call.

Courses:
- vision-mission-2026: combined Vision/Mission/Strategy/Values, taken, due end-Nov
- vision-only-2026: Vision only, not taken, due 8 Nov
Content is cloned from ibrance-cycle-label-update so player/quiz work unchanged.
"""
import json
import shutil
from pathlib import Path

from src import learning
from src.agent import content_path

DEMO_USERS = [
    {"id": "guru-raja", "name": "Guru Raja", "email": "guru.raja@pharmalearn.local", "role": "admin", "title": "PharmaLearn builder"},
    {"id": "pattabhi", "name": "Pattabhi", "email": "pattabhi@pharmalearn.local", "role": "msl", "title": "MSL, oncology East"},
    {"id": "shashidhar-gururao", "name": "Shashidhar Gururao", "email": "shashidhar@pharmalearn.local", "role": "msl", "title": "Training stakeholder"},
    {"id": "parimala", "name": "Parimala", "email": "parimala@pharmalearn.local", "role": "hcp", "title": "Medical oncologist"},
]

COMBINED = "vision-mission-2026"
COMBINED2 = "vision-innovation-2026"
VISION_ONLY = "vision-only-2026"
SOURCE_RUN = "ibrance-cycle-label-update"

PROGRAMS = {
    COMBINED: {
        "program_title": "Vision, Mission, Strategy & Core Values",
        "message": "Complete this course before the end-of-November review. About 15 min: 13 slides with voice, then a 12-question check. You need 80% to pass.",
        "starts_on": "2026-11-01",
        "due_on": "2026-11-30",
        "description": "Covers organisation vision and mission, strategic goals and core values. Certifies the learner completed the induction track (v2, pass mark 80%).",
        "topics": ["Organisation vision", "Mission statement", "Strategic goals", "Core values"],
        "organization": "Clair Labs",
    },
    COMBINED2: {
        "program_title": "Vision and Core Values",
        "message": "Vision and the values behind it. About 10 min plus a 12-question check. You need 80% to pass.",
        "starts_on": "2026-11-01",
        "due_on": "2026-11-30",
        "description": "Covers vision and core values: what we stand for and why. Certifies the learner completed the induction (v2, pass mark 80%).",
        "topics": ["Organisation vision", "Core values"],
        "organization": "Clair Labs",
    },
    VISION_ONLY: {
        "program_title": "Vision",
        "message": "The organisation vision, nothing else. About 5 min plus a 12-question check. Due 8 November.",
        "starts_on": "2026-11-01",
        "due_on": "2026-11-08",
        "description": "Covers the organisation vision statement only. Certifies the learner completed the vision induction (v1, pass mark 80%).",
        "topics": ["Organisation vision"],
        "organization": "Clair Labs",
    },
}

# run_id -> {user_id: [finals n_correct]}. Baselines always pass.
SIMULATIONS = {
    COMBINED: {
        "shashidhar-gururao": [6, 7, 11],
        "pattabhi": [7, 10],
        "guru-raja": [11],
    },
    COMBINED2: {
        "shashidhar-gururao": [10],
        "guru-raja": [11],
    },
}


def ensure_users():
    people = {p["id"]: p for p in learning.roster()}
    changed = False
    for user in DEMO_USERS:
        if user["id"] not in people:
            people[user["id"]] = user
            changed = True
    if changed:
        path = Path(".pharmalearn/platform/roster.json")
        path.write_text(json.dumps(list(people.values()), indent=2) + "\n")
    return people


def clone_content(run_id: str, program_title: str):
    src = content_path("content", SOURCE_RUN)
    dst = content_path("content", run_id)
    if not dst.exists():
        shutil.copytree(src, dst)
    manifest_path = dst / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["run_id"] = run_id
    manifest["program_title"] = program_title
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    # Baseline standard: 10-15 questions, 70% pass. Source has 12 questions; set pass to 70%.
    for track in ("hcp", "msl"):
        quiz_path = dst / track / "quiz.json"
        if quiz_path.exists():
            quiz = json.loads(quiz_path.read_text())
            quiz["passing_score"] = 70
            quiz_path.write_text(json.dumps(quiz, indent=2) + "\n")
    return dst


def ensure_course(run_id: str, program: dict, assignees: list[str]):
    record = learning.course(run_id)
    record["version"] = 2
    record["status"] = "published"
    record["description"] = program["description"]
    record["topics_covered"] = program.get("topics", [])
    record["organization"] = program.get("organization", "")
    if not any(s.get("decision") == "approved" and s.get("version") == 2 for s in record.get("signoffs", [])):
        record.setdefault("signoffs", []).append({
            "id": "seed-signoff", "version": 2, "decision": "approved",
            "note": "Approved for Shashi demo.", "author_id": "anil-shekhar",
            "author_name": "Dr. Anil Shekhar", "author_title": "Therapeutic area expert, oncology",
            "created_at": "2026-11-10T10:00:00+00:00", "attested": True,
            "method": "typed-name", "meaning": "Seeded approval for demo",
        })
    record["publication"] = {
        "version": 2,
        "published_at": "2026-11-10T10:00:00+00:00",
        "published_by": "Priya Raman",
        "overrides": [],
        "starts_on": program["starts_on"],
        "due_on": program["due_on"],
        "frequency": "once",
        "next_due_on": None,
        "certificate_template": "classic",
        "message": program["message"],
        "assignees": assignees,
        "notifications": [{
            "to": "demo@pharmalearn.local", "name": "Demo cohort",
            "subject": f"Training assigned: complete by {program['due_on']}",
            "sent_at": "2026-11-10T10:00:00+00:00",
        }],
    }
    learning._save_course(record)
    return record


def quiz_questions(run_id: str):
    quiz = json.loads(content_path("content", run_id, "hcp", "quiz.json").read_text())
    return quiz["questions"], quiz["passing_score"]


def answer_set(questions, n_correct: int):
    answers = {}
    for i, q in enumerate(questions):
        if i < n_correct:
            answers[q["id"]] = q["correct_index"]
        else:
            answers[q["id"]] = (q["correct_index"] + 1) % len(q["options"])
    return answers


def simulate(run_id: str, user_id: str, finals: list[int]):
    """finals: list of n_correct per final attempt. Baseline always passes."""
    questions, passing = quiz_questions(run_id)
    for module in learning.MODULES:
        learning.set_module(run_id, user_id, module["id"], True)
    # Baseline (ungraded, always passes)
    learning.record_attempt(run_id, user_id, "baseline",
                            answer_set(questions[:5], 4), questions[:5], passing)
    for n_correct in finals:
        learning.record_attempt(run_id, user_id, "final",
                                answer_set(questions, n_correct), questions, passing)


def main():
    ensure_users()
    assignees = [u["id"] for u in DEMO_USERS]
    for run_id, program in PROGRAMS.items():
        clone_content(run_id, program["program_title"])
        ensure_course(run_id, program, assignees)
        learning.set_course_type(run_id, "guru-raja", "induction")
    # Attempts come from SIMULATIONS above.
    for run_id, finals in SIMULATIONS.items():
        for user_id in finals:
            stale = Path(f".pharmalearn/platform/progress/{run_id}/{user_id}.json")
            if stale.exists():
                stale.unlink()
    for run_id, finals in SIMULATIONS.items():
        for user_id, attempts in finals.items():
            simulate(run_id, user_id, attempts)
    # Everyone else: assigned, not started.
    print("Seeded Shashi demo:")
    for run_id in PROGRAMS:
        cohort = learning.cohort(run_id)
        for learner in cohort["learners"]:
            print(f"  {run_id} {learner['name']}: stage={learner['stage']} "
                  f"attempts={learner['attempts']} final={learner['final_score']} "
                  f"cert={bool(learner['certificate'])}")


if __name__ == "__main__":
    main()

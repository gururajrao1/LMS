"""Prep Pattabhi for a fast story demo: modules done + pass final → certificate."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
RUN = "patient-recruitment-2026"
USER = "pattabhi"
ROOT = Path(__file__).resolve().parents[1]
QUIZ = ROOT / ".pharmalearn" / "content" / RUN / "msl" / "quiz.json"


def call(method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode() or "null"
            return resp.status, json.loads(raw) if raw[:1] in "{[" else raw
    except urllib.error.HTTPError as err:
        raw = err.read().decode()
        try:
            payload = json.loads(raw) if raw else {"detail": err.reason}
        except json.JSONDecodeError:
            payload = {"detail": raw}
        raise RuntimeError(f"{method} {path} → {err.code}: {payload}") from err


def main() -> None:
    keys = {q["id"]: q["correct_index"] for q in json.loads(QUIZ.read_text())["questions"]}

    call("POST", f"/api/runs/{RUN}/publication", {
        "user_id": "guru-raja",
        "starts_on": "2026-11-17",
        "due_on": "2026-11-30",
        "assignees": ["guru-raja", "pattabhi", "shashidhar-gururao", "parimala"],
        "group_ids": ["clinical-trial"],
        "message": "Story demo: 15 min induction — 70% to pass.",
        "frequency": "once",
        "certificate_template": "modern",
        "max_final_attempts": 3,
    })

    try:
        call("DELETE", f"/api/learn/{USER}/{RUN}/attempts?by=guru-raja")
        print("reset attempts")
    except RuntimeError as err:
        print("reset skipped:", err)

    course = call("GET", f"/api/learn/{USER}/{RUN}")[1]
    for module in course.get("modules", []):
        if not module.get("completed"):
            call("POST", f"/api/learn/{USER}/{RUN}/modules", {"module_id": module["id"], "completed": True})
    print("modules complete")

    for kind in ("baseline", "final"):
        summary = call("GET", f"/api/learn/{USER}/{RUN}")[1].get("summary") or {}
        if kind == "baseline" and summary.get("baseline_score") is not None:
            print("baseline already", summary["baseline_score"])
            continue
        if kind == "final" and summary.get("certificate"):
            print("already certified", summary["certificate"].get("code"))
            return
        meta = call("GET", f"/api/learn/{USER}/{RUN}/assessment/{kind}")[1]
        answers = {q["id"]: keys[q["id"]] for q in meta["questions"] if q["id"] in keys}
        result = call("POST", f"/api/learn/{USER}/{RUN}/assessment/{kind}", {"answers": answers})[1]
        attempt = result.get("attempt") or result
        print(kind, "score", attempt.get("score"), "passed", attempt.get("passed"))

    course = call("GET", f"/api/learn/{USER}/{RUN}")[1]
    cert = (course.get("summary") or {}).get("certificate") or {}
    print("certificate", cert.get("code"), "template from pub = modern")


if __name__ == "__main__":
    main()

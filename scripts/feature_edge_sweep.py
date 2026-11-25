"""Live API permutation sweep for patient-recruitment + platform gates.

Run against a booted API:  uv run python scripts/feature_edge_sweep.py
Exits non-zero if any check fails. Safe: uses disposable progress for ken-osei
on a throwaway path where possible; prefers read-only + reversible ops on PR.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any

BASE = "http://127.0.0.1:8000"
RUN = "patient-recruitment-2026"
FAILS: list[str] = []
OKS: list[str] = []


def call(method: str, path: str, body: dict | None = None) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode() or ""
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "json" in ctype or raw[:1] in "{[":
                return resp.status, json.loads(raw or "null")
            return resp.status, raw
    except urllib.error.HTTPError as err:
        raw = err.read().decode() or ""
        try:
            payload = json.loads(raw) if raw else {"detail": err.reason}
        except json.JSONDecodeError:
            payload = {"detail": raw or str(err.reason)}
        return err.code, payload


def expect(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        OKS.append(name)
        print(f"  OK  {name}")
    else:
        FAILS.append(f"{name}: {detail}")
        print(f" FAIL {name} — {detail}")


def main() -> int:
    print("=== PharmaLearn feature edge sweep ===\n")

    code, health = call("GET", "/health")
    expect("health", code == 200, str(health))

    code, templates = call("GET", "/api/certificate-templates")
    ids = {row["id"] for row in templates} if isinstance(templates, list) else set()
    expect("cert templates classic/modern/formal", ids >= {"classic", "modern", "formal"}, str(ids))

    code, groups = call("GET", "/api/groups")
    group_ids = {row["id"] for row in groups} if isinstance(groups, list) else set()
    expect("clairlabs groups present", "clinical-trial" in group_ids, str(group_ids))

    code, review = call("GET", f"/api/runs/{RUN}/review")
    ready = (review or {}).get("readiness") or {}
    expect("PR can_publish", code == 200 and ready.get("can_publish") is True, str(ready))

    # Empty reach refused
    code, err = call("POST", f"/api/runs/{RUN}/publication", {
        "user_id": "guru-raja",
        "starts_on": "2026-11-17",
        "due_on": "2026-11-30",
        "assignees": [],
        "group_ids": [],
        "message": "edge",
        "frequency": "once",
        "certificate_template": "classic",
        "max_final_attempts": 3,
    })
    expect("publish empty reach → 4xx", code >= 400, f"{code} {err}")

    # Empty leadership-only group → still no people
    code, err = call("POST", f"/api/runs/{RUN}/publication", {
        "user_id": "guru-raja",
        "starts_on": "2026-11-17",
        "due_on": "2026-11-30",
        "assignees": [],
        "group_ids": ["senior-leadership"],
        "message": "edge",
        "frequency": "once",
        "certificate_template": "formal",
        "max_final_attempts": 3,
    })
    expect("publish empty leadership group → 4xx", code >= 400, f"{code} {err}")

    # Bad template
    code, err = call("POST", f"/api/runs/{RUN}/publication", {
        "user_id": "guru-raja",
        "starts_on": "2026-11-17",
        "due_on": "2026-11-30",
        "assignees": ["pattabhi"],
        "group_ids": [],
        "message": "edge",
        "frequency": "once",
        "certificate_template": "neon",
        "max_final_attempts": 3,
    })
    expect("bad cert template → 4xx", code >= 400, f"{code} {err}")

    # Learner cannot publish
    code, err = call("POST", f"/api/runs/{RUN}/publication", {
        "user_id": "pattabhi",
        "starts_on": "2026-11-17",
        "due_on": "2026-11-30",
        "assignees": ["pattabhi"],
        "group_ids": [],
        "message": "edge",
        "frequency": "once",
        "certificate_template": "classic",
        "max_final_attempts": 3,
    })
    expect("learner publish blocked", code >= 400, f"{code} {err}")

    # Republish valid (restore clinical-trial + modern)
    code, pub = call("POST", f"/api/runs/{RUN}/publication", {
        "user_id": "guru-raja",
        "starts_on": "2026-11-17",
        "due_on": "2026-11-30",
        "assignees": ["guru-raja", "pattabhi", "shashidhar-gururao", "parimala"],
        "group_ids": ["clinical-trial"],
        "message": "Complete before the end-of-November review. About 15 min: 17 slides, then a 12-question check. 70% to pass.",
        "frequency": "once",
        "certificate_template": "modern",
        "max_final_attempts": 3,
    })
    expect("republish PR modern", code == 200 and (pub.get("publication") or {}).get("certificate_template") == "modern", str(pub)[:200])

    code, cohort = call("GET", f"/api/runs/{RUN}/cohort")
    learner_ids = {row["user_id"] for row in (cohort or {}).get("learners", [])}
    expect("cohort has 4 assignees", learner_ids >= {"pattabhi", "parimala", "guru-raja", "shashidhar-gururao"}, str(learner_ids))

    code, course = call("GET", f"/api/learn/pattabhi/{RUN}")
    expect("pattabhi can load course", code == 200, str(course)[:120] if code != 200 else "")
    if code == 200:
        videos = (course.get("content") or {}).get("videos") or []
        mods = {m["id"]: m.get("completed") for m in course.get("modules", [])}
        expect("empty videos auto-completed", not videos and mods.get("videos") is True, str(mods))
        expect("induction type", course.get("course_type") == "induction", str(course.get("course_type")))

    code, unassigned = call("GET", f"/api/learn/jordan-feld/{RUN}")
    expect("unassigned jordan blocked or empty assign", code >= 400 or not ((unassigned or {}).get("publication")), f"{code}")

    # Baseline then fail finals to lock (use ken only if assigned — skip lock on live PR assignees)
    # Read reminders / alerts / templates instead for read-only edges
    code, reminders = call("GET", f"/api/runs/{RUN}/reminders")
    expect(
        "reminders endpoint",
        code == 200 and isinstance(reminders, (list, dict)),
        str(type(reminders)),
    )

    code, alerts = call("GET", f"/api/runs/{RUN}/alerts")
    expect("alerts endpoint", code == 200, str(code))

    code, checks = call("GET", f"/api/runs/{RUN}/checks")
    expect("checks endpoint", code == 200, str(code))

    code, export = call("GET", f"/api/runs/{RUN}/export/completions")
    expect("completions export", code == 200 and isinstance(export, str) and len(export) > 0, str(code))

    code, audit = call("GET", f"/api/runs/{RUN}/export/audit")
    expect(
        "audit export",
        code == 200 and (
            (isinstance(audit, dict) and "audit" in audit)
            or (isinstance(audit, str) and "audit" in audit)
        ),
        str(type(audit)),
    )

    code, verify = call("GET", f"/api/runs/{RUN}/audit/verify")
    expect("audit verify", code == 200, str(verify)[:120])

    # Cap = 0 refused
    code, err = call("POST", f"/api/runs/{RUN}/publication", {
        "user_id": "guru-raja",
        "starts_on": "2026-11-17",
        "due_on": "2026-11-30",
        "assignees": ["pattabhi"],
        "group_ids": ["clinical-trial"],
        "message": "edge",
        "frequency": "once",
        "certificate_template": "modern",
        "max_final_attempts": 0,
    })
    expect("attempt cap 0 → 4xx", code >= 400, f"{code} {err}")

    # Restore good publication after bad cap attempt
    call("POST", f"/api/runs/{RUN}/publication", {
        "user_id": "guru-raja",
        "starts_on": "2026-11-17",
        "due_on": "2026-11-30",
        "assignees": ["guru-raja", "pattabhi", "shashidhar-gururao", "parimala"],
        "group_ids": ["clinical-trial"],
        "message": "Complete before the end-of-November review. About 15 min: 17 slides, then a 12-question check. 70% to pass.",
        "frequency": "once",
        "certificate_template": "modern",
        "max_final_attempts": 3,
    })

    print(f"\n=== {len(OKS)} passed · {len(FAILS)} failed ===")
    for row in FAILS:
        print(f"  - {row}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

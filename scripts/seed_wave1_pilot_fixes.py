"""Wave 1 pilot fixes: managers, ClairLabs groups, DEMO_FILL off, group publish.

Closes several Shashi Partial items in-app without SES/IT:

  - every patient-recruitment assignee has a manager
  - named org groups exist (tech / management / leadership / genomic / clinical)
  - patient-recruitment publication also targets the clinical-trial group
  - .env gets PHARMALEARN_DEMO_FILL=0 if present / created from example

    uv run python scripts/seed_wave1_pilot_fixes.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import learning  # noqa: E402
from src.agent import content_path  # noqa: E402

ADMIN = "guru-raja"
RUN_ID = "patient-recruitment-2026"

# Shashi Nov 17 named groups. Only people already on the roster are attached;
# missing names are noted so HR can fill later.
GROUPS = [
    {
        "id": "tech",
        "label": "Tech",
        "want": ["guru-raja", "paavan", "alak"],
    },
    {
        "id": "management",
        "label": "Management",
        "want": ["shashidhar-gururao", "pattabhi", "shubhangi"],
    },
    {
        "id": "senior-leadership",
        "label": "Senior leadership",
        "want": ["pankaj", "chandra", "shekhar"],
    },
    {
        "id": "genomic",
        "label": "Genomic team",
        "want": ["parimala"],
    },
    {
        "id": "clinical-trial",
        "label": "Clinical trial team",
        "want": ["guru-raja", "pattabhi", "shashidhar-gururao", "parimala"],
    },
]

# Manager for lockout routing: Shashi owns the induction cohort; Priya covers Shashi.
MANAGERS = {
    "guru-raja": "shashidhar-gururao",
    "pattabhi": "shashidhar-gururao",
    "parimala": "shashidhar-gururao",
    "shashidhar-gururao": "priya-raman",
}


def _ensure_demo_fill_off() -> None:
    example = ROOT / ".env.example"
    if example.exists():
        text = example.read_text(encoding="utf-8")
        text2 = re.sub(
            r"^PHARMALEARN_DEMO_FILL=.*$",
            "PHARMALEARN_DEMO_FILL=0",
            text,
            flags=re.M,
        )
        if "PHARMALEARN_DEMO_FILL=" not in text2:
            text2 += "\nPHARMALEARN_DEMO_FILL=0\n"
        example.write_text(text2, encoding="utf-8")

    env_path = ROOT / ".env"
    if not env_path.exists():
        env_path.write_text(example.read_text(encoding="utf-8") if example.exists() else "PHARMALEARN_DEMO_FILL=0\n", encoding="utf-8")
    text = env_path.read_text(encoding="utf-8")
    if re.search(r"^PHARMALEARN_DEMO_FILL=", text, re.M):
        text = re.sub(r"^PHARMALEARN_DEMO_FILL=.*$", "PHARMALEARN_DEMO_FILL=0", text, flags=re.M)
    else:
        text = text.rstrip() + "\nPHARMALEARN_DEMO_FILL=0\n"
    env_path.write_text(text, encoding="utf-8")
    print("DEMO_FILL=0 in .env and .env.example")


def _set_managers() -> None:
    for user_id, manager_id in MANAGERS.items():
        learning.set_manager(ADMIN, user_id, manager_id)
        print(f"manager {user_id} -> {manager_id}")


def _seed_groups() -> list[str]:
    people = {entry["id"] for entry in learning.roster()}
    existing = {entry["id"]: entry for entry in learning.learner_groups()}
    missing_notes = []
    for spec in GROUPS:
        present = [uid for uid in spec["want"] if uid in people]
        absent = [uid for uid in spec["want"] if uid not in people]
        if absent:
            missing_notes.append(f"{spec['label']}: awaiting roster for {', '.join(absent)}")
        if spec["id"] in existing:
            learning.set_learner_group_members(ADMIN, spec["id"], present)
            print(f"group updated {spec['id']} members={present}")
        else:
            # create_learner_group slugs the label; force id by writing after create
            # when slug matches. Labels are chosen so _slug(label) == id.
            entry = learning.create_learner_group(ADMIN, spec["label"], present)
            if entry["id"] != spec["id"]:
                # Rename id to stable key if slug drifted.
                groups = learning.learner_groups()
                for item in groups:
                    if item["id"] == entry["id"]:
                        item["id"] = spec["id"]
                        item["label"] = spec["label"]
                learning._save_learner_groups(groups)
                print(f"group created {spec['id']} (renamed from {entry['id']}) members={present}")
            else:
                print(f"group created {spec['id']} members={present}")
    for note in missing_notes:
        print(f"NOTE {note}")
    return [spec["id"] for spec in GROUPS]


def _attach_clinical_group(group_ids: list[str]) -> None:
    path = content_path("platform", "courses", f"{RUN_ID}.json")
    if not path.exists():
        print(f"skip publish attach: {RUN_ID} missing")
        return
    record = json.loads(path.read_text(encoding="utf-8"))
    publication = record.get("publication") or {}
    current = list(publication.get("group_ids") or [])
    if "clinical-trial" not in current and "clinical-trial" in group_ids:
        current.append("clinical-trial")
    publication["group_ids"] = current
    # Keep direct assignees; group expands live.
    record["publication"] = publication
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"{RUN_ID} group_ids={current}")


def main() -> int:
    _ensure_demo_fill_off()
    _set_managers()
    group_ids = _seed_groups()
    _attach_clinical_group(group_ids)
    print("wave1 pilot fixes applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

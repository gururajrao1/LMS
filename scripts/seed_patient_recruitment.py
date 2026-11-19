"""Register the Patient Recruitment course for demo and training.

Content under .pharmalearn/content/patient-recruitment-2026 is authored from
docs/Patient Recruitment Deck.pptx (17 slides, 14 FAQs, 12-question quiz,
6-scene storyboard, both tracks). This script only creates the course record,
publication and induction typing - no signoffs are seeded (real review adds
them) and no attempts are simulated (this course trains real learners).
"""
import json

from src import learning

RUN_ID = "patient-recruitment-2026"
ASSIGNEES = ["guru-raja", "pattabhi", "shashidhar-gururao", "parimala"]


def main():
    record = learning.course(RUN_ID)
    record["version"] = 1
    record["status"] = "published"
    record["description"] = (
        "Covers the ClairLabs patient recruitment programme end to end: the five-step "
        "journey from screener to recruited participant, the AI-driven funnel, HCP and "
        "advocacy outreach, data intelligence, site activation, patient experience and "
        "the go-live roadmap. Certifies the learner completed the patient recruitment "
        "induction (v1, pass mark 80%)."
    )
    record["topics_covered"] = [
        "Recruitment journey",
        "AI-driven funnel",
        "HCP and advocacy outreach",
        "Site activation",
        "Patient experience",
        "Go-live roadmap",
    ]
    record["organization"] = "Clair Labs"
    record["publication"] = {
        "version": 1,
        "published_at": "2026-11-17T00:00:00+00:00",
        "published_by": "Guru Raja",
        "overrides": [],
        "starts_on": "2026-11-17",
        "due_on": "2026-11-30",
        "frequency": "once",
        "next_due_on": None,
        "certificate_template": "classic",
        "message": "Complete before the end-of-November review. About 20 min: 17 slides with the visual story, then a 12-question check. You need 80% to pass.",
        "assignees": ASSIGNEES,
        "notifications": [{
            "to": "demo@pharmalearn.local", "name": "Demo cohort",
            "subject": "Training assigned: complete by 2026-11-30",
            "sent_at": "2026-11-17T00:00:00+00:00",
        }],
    }
    learning._save_course(record)
    learning.set_course_type(RUN_ID, "guru-raja", "induction")
    cohort = learning.cohort(RUN_ID)
    print(f"Course {RUN_ID}: status={record['status']} version={record['version']}")
    for learner in cohort["learners"]:
        print(f"  {learner['name']}: stage={learner['stage']} attempts={learner['attempts']}")


if __name__ == "__main__":
    main()

# PharmaLearn — Features, Use Cases & Research Notes

Plain-language readme. No removals: everything below adds to the current app.

## The app in one paragraph

PharmaLearn drafts drug training (slides, video storyboard, FAQ, quiz) with citations,
asks an automated checker plus human experts to review it, publishes it to field staff
(MSLs and HCPs), then tracks who learned what. See
[README](https://github.com/gururajrao1/LMS/blob/main/README.md) and the local
[KT notes](/C:/Users/gurur/OneDrive/Documents/LMS-clairlabs/KT.md).

## Feature list + why each exists

1. **Readiness banner** — Admin opens a course and sees the 3 publish gates
   (approval at this version, no open blocking comments, no change requests).
   Why: today that answer hides in the Publish tab; a banner stops failed publish clicks.
2. **Guided 4-stage nav (Content → Review → Publish → Measure)** — Same 13 panels,
   grouped in demo order. Why: new admins follow project → build → validate →
   schedule → certify without getting lost.
3. **Comment-side evidence** — Each finding shows claim + recorded quote + matched
   spans + source passage + what is unheld. Why: reviewers decide in one place;
   a 0% or 12% quote match is visible, not just a number.
4. **Comment-scoped Ask** — Chat limited to that finding's dossier slice.
   Why: answers unmet-need or trial questions from held evidence, says plainly
   when not covered instead of guessing.
5. **Learner Next action** — One primary button across baseline → modules →
   final → certificate. Why: learners never wonder what to do today; locks
   explain themselves.
6. **Label-change refresh** — Diff a new label, flag affected slides, route them
   for re-review and re-certification. Why: safety updates ship in hours, and the
   certificate still says which version was passed.
7. **Client portfolio view** — Live / due / completed plus uplift across drugs.
   Why: a Pfizer-level lead sees all programs at once; existing code already has
   `programme` and `portfolio` helpers to build on.
8. **Export pack (PDF)** — Cohort + Impact + audit trail as a file. Why: compliance
   and client reviews happen outside the app.
9. **Spaced reinforcement** — Short re-quiz built from each learner's missed
   questions before expiry. Why: hardest-questions data already exists; this closes
   the loop into retention.
10. **Offline + transcripts** — Downloadable modules and video transcripts.
    Why: field MSLs with bad connectivity still finish; text also helps search.

## What existing apps do (so we copy the right parts)

- **Veeva Vault / Veeva LMS**: pharma-native compliance training tied to controlled
  documents (SOPs, policies). Lesson: bind training records to document versions —
  PharmaLearn already stamps certificates with course version and approvers.
  See [pharma LMS buyer guide](https://360learning.com/blog/lms-pharma/).
- **ComplianceWire / MasterControl**: GxP audit trail first, learning second.
  Lesson: every resolution must be attributed and re-checkable — matches the
  dismissal-challenge design here.
- **360Learning, Docebo, LearnUpon, Absorb**: SME authoring + completion focus for
  non-GxP enablement. Lesson: most pharma firms run two systems (GxP + enablement);
  PharmaLearn sits on the enablement side and should export (SCORM/xAPI/PDF)
  rather than replace the GxP LMS. See
  [pharma LMS buyer guide](https://360learning.com/blog/lms-pharma/).
- **Veeva CRM for MSLs**: tracks scientific exchanges and KOL insights in the field.
  Lesson: the portfolio and insight-capture ideas fit naturally after certification.

## What literature says (short version)

- AI video in medical education is early: a systematic review of 103 studies kept
  only 5, and control materials still beat AI video on accuracy in one trial. Use
  storyboards + human review first, full video later. See
  [AI-generated videos review](https://pmc.ncbi.nlm.nih.gov/articles/PMC12742227/).
- Chatbot studies keep finding the same trade-off: readable answers score lower on
  reliability, confident models still hallucinate citations. Hence: retrieval-first
  answers, refusal when uncovered, and deterministic quote checks before any model
  opinion.
- Image/clinical-fidelity reviews warn about demographic bias in AI images. Hence:
  avoid image-based severity quizzes until imagery is licensed and representative.

## Papers With Code patterns worth copying

- **MedCite**: end-to-end citation generation + evaluation for medical QA, with
  citation recall/precision/F1 alongside answer correctness. Pattern: measure the
  citation, not just the answer. See
  [MedCite paper](https://arxiv.org/html/2506.06605v1).
- **LongCite / LongBench-Cite**: sentence-level citations for long-context QA and an
  automatic benchmark for them. Pattern: fine-grained citations make verification
  possible. See
  [LongCite](https://paperswithcode.com/paper/longcite-enabling-llms-to-generate-fine).
- **Self-RAG**: retrieve, generate, then critique with self-reflection; big gains in
  factuality and citation accuracy. Pattern: checker-after-author, like the
  pre-review checker + second-opinion confirm here. See
  [Self-RAG](https://paperswithcode.com/paper/self-rag-learning-to-retrieve-generate-and).
- **PaniniQA**: patient education QA that checks answers and corrects the learner.
  Pattern: per-question rationale + correction, like the baseline/final review
  panels. See
  [PaniniQA](https://paperswithcode.com/paper/paniniqa-enhancing-patient-education-through).
- **VerifAI-style claim verification**: split answers into atomic claims, check each
  with NLI against retrieved evidence. Pattern: matches `quote_spans` /
  `quote_match` deterministic checks already in this repo.

## How to read this repo next

1. Run the demo path in [README](https://github.com/gururajrao1/LMS/blob/main/README.md).
2. Skim [KT notes](/C:/Users/gurur/OneDrive/Documents/LMS-clairlabs/KT.md) sections 4–6.
3. Open [accuracy design](https://github.com/gururajrao1/LMS/blob/main/docs/ACCURACY.md)
   for the dismissal-challenge demo script.
4. Pick one feature above; its home is named in that bullet.

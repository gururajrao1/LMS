# KPI dashboard — draft for Shashidhar's review

Seeded demo already shows your story: Shashi 4 attempts, Pattabhi 3, Guru
first-try pass at 92%, Parimala not started. One overdue (vision-only, due 8 Nov).

## Proposed KPIs (all computed from data the app already records)

| # | KPI | Definition | Target |
|---|-----|------------|--------|
| 1 | Attempts per learner | Assessment attempts (baseline + finals) on each course | Visible, no target |
| 2 | First-try pass rate | % certified with exactly 1 final attempt | Track only for now |
| 3 | Compliance | % assigned learners certified at 80%+ in every course, within cutoff | 100% = green |
| 4 | Time to certify | Median days from publish to certificate | Track only for now |
| 5 | Overdue count | Assigned, past due, not certified | 0 = green |
| 6 | Knowledge uplift | Mean final minus baseline, paired learners only | > 0 |
| 7 | Stuck signals | "Confusing" flags per module + hardest questions by miss rate | Review weekly |

## Open questions for you

1. Are these the activities to track, or should anything be added/removed?
2. Daily 2pm check: on-page only for now — do you also want email/SMS?
3. Voice: browser read-aloud for the demo — is server-generated audio needed for field users?
4. Badges: keep the "first-try pass" style badges for induction? Yes/no.
5. Leaderboard: named finisher list is induction-only in this draft (drug
   courses stay anonymized for compliance). Confirm you are happy with that line.

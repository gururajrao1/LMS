# Learner flow — MSL and HCP

**Personas:** Jordan Feld, Sara Nakamura (MSL) · Dr. Ken Osei, Dr. Lucy Whitfield, Dr. Tom Becker (HCP).
**Owns:** working through assigned training and proving knowledge.

MSL and HCP follow an identical flow. The only difference is which generated track they receive: an MSL sees the MSL deck, videos, storyboard, FAQ, and quiz; an HCP sees the HCP set. The track is derived from the role, not chosen by the learner.

A learner sees a course only if an admin published it **and** put them on the assignee list. Requesting a course you are not assigned to returns 403.

---

## 1. See what is assigned

**Screen:** `/learn` · `GET /api/learn/{user_id}`

Header tiles: assigned courses, in progress, certificates earned.

Each course card carries the drug, the version published to you, the training window, and days remaining — highlighted amber inside a week or once overdue. The card's call to action reflects where you are:

| Stage | Card says |
| --- | --- |
| `not_started` | Start the baseline check |
| `baseline` / `learning` | Continue learning |
| `final` | Take the final assessment |
| `complete` | View your certificate |

Once both assessments exist the card also shows `baseline → final` with the uplift.

With nothing assigned, the page explains that courses appear once a medical education lead publishes one to your role — not an error.

---

## 2. Open the course

**Screen:** `/learn/{runId}` · `GET /api/learn/{user_id}/{runId}`

The header shows the drug, your track, the published version, the due date, and the message the admin sent with the assignment.

Below it, a four-step **journey** strip, each step linking where it can:

1. **Baseline check** — score once taken
2. **Learning material** — *n* of 4 modules
3. **Final assessment** — locked until every module is done
4. **Certificate** — locked until you pass

A locked step shows a padlock rather than a dead link.

---

## 3. Take the baseline

**Screen:** `/learn/{runId}/assessment/baseline`

`GET .../assessment/baseline` returns a five-question sample drawn deterministically from the quiz — **without** `correct_index`, so answers are not in the browser.

Submitting posts your answers; the server scores them and returns a per-question review with the correct answer, the rationale, and citations. The baseline is never a gate: it is the "before" measurement that makes uplift meaningful, and the page says so.

---

## 4. Work the modules

**Screen:** `/learn/{runId}`, module tabs

| Module | Content | Est. |
| --- | --- | --- |
| Deck | 16:9 slide thumbnails; click one for its full body copy, why it is there, and its citations. Plus the `.pptx` download | 25 min |
| Videos | Track playlist, auto-advancing; falls back to a note pointing at the storyboard when a track has no videos | 18 min |
| Visual story | Storyboard scenes: narration, visual direction, on-screen text | 10 min |
| FAQ | The questions you will be asked, with nuance and escalation paths | 12 min |

Each tab ends with a footer that does two things:

- **Mark complete** — `POST .../modules {module_id, completed}`. Reversible; a completed tab shows a check in its trigger and the journey strip and progress bar update immediately.
- **Rate this module** — 1–5 stars, plus an optional comment saved on blur (`POST .../feedback`). Ratings land in the admin's cohort view as direct feedback for the next version.

---

## 5. Ask the course a question

**Screen:** **Ask** tab · `POST /api/runs/{runId}/chat`

A chat panel answering only from the cited dossier the course was built from, with source links under each answer. Suggested questions seed the first turn.

Without an API key the answer is drawn straight from the strongest matching claims. With one, the model answers from those same claims and nothing else. An off-topic question gets an honest "not covered here — escalate to Medical Information" rather than a guess.

---

## 6. Sit the final

**Screen:** `/learn/{runId}/assessment/final`

Gated: submitting before all four modules are complete returns 400, and the journey strip does not link there until they are.

- The full quiz (12 questions for the Ibrance HCP track), again with no answers sent to the browser.
- The pass mark comes from the quiz's `passing_score`, normalized to a percentage — 67% for the Ibrance HCP quiz.
- A sticky footer tracks how many you have answered; submit unlocks when all are.

The result panel gives the score, pass or fail, and the knowledge uplift against your baseline, then the full per-question review with rationale and citations.

**Failing** offers **Try again** and **Review the material**; attempts are unlimited and every one is recorded. **Passing** issues the certificate immediately and links to it.

---

## 7. Certificate

**Screen:** `/learn/{runId}/certificate` · `GET .../certificate`

Issued only when every module is complete and the final is passed; requesting it earlier returns 404 with that explanation.

It records the learner's name and title, the course and track, the final score, **the course version passed**, the issue date, a **valid-through date** one year on, the **named reviewers who approved that version**, and a verification code (`PL-IBRANCE-2026-XXXXXX`). **Print or save as PDF** uses the browser's print dialog, and the page chrome is hidden in print.

Because the version is stamped on the certificate, a later version of the course leaves the historical record intact — the certificate says what was actually learned.

---

## What the learner never sees

- `correct_index`, rationales, or citations for a question they have not yet answered.
- Any course they have not been assigned.
- The review, publish, or cohort surfaces — those tabs are not rendered for learner roles, and `/dashboard` redirects them back to `/learn`.

# Admin flow

**Persona:** Priya Raman, medical education lead.
**Owns:** generating content, addressing review comments, cutting versions, publishing to a cohort, monitoring outcomes, and curating the data store.

The admin is the *maker* in the maker-checker split. An admin can raise comments too, but cannot supply the approving sign-off that unlocks publication — that has to come from a reviewer.

---

## 1. Generate a course

**Screen:** `/dashboard` → **Create content** dialog → `/runs/{runId}`

| Step | System |
| --- | --- |
| Dashboard loads | `GET /api/courses` returns generated courses (with review status, version, assigned count) followed by planned placeholders |
| Type a drug name, submit | `POST /api/runs {drug}` starts a background run and returns its id. Anything other than Ibrance/palbociclib is rejected with 400 |
| Run page opens | `GET /api/runs/{id}` for status, then an `EventSource` on `/api/runs/{id}/events` |
| Stages stream in | Each agent stage appends to `events.jsonl`; the page shows one row per stage with a live percentage |
| Run completes | **Send for review** links to `/courses/{runId}` |

Without an `ANTHROPIC_API_KEY` the agent reads the prepared Ibrance datastore and the run is reproducible. With a key it does live section research. Either way the run writes 14 research sections, a master dossier, and four assets for each of the MSL and HCP tracks.

The dashboard header counts are real: generated courses, awaiting publication, published, and total trainees assigned.

---

## 2. Inspect what was generated

**Screen:** `/courses/{runId}`

`GET /api/runs/{id}/content` and `GET /api/runs/{id}/review` load together. The header shows the drug, current version, review status, citation count, and open-comment count.

The **HCP / MSL** toggle re-renders every asset tab against that track — the two tracks are separately generated, not one deck relabelled.

| Tab | Shows |
| --- | --- |
| PPTX | Slide-by-slide purpose and citations, plus a `.pptx` download |
| Videos | Track playlist, auto-advancing |
| Storyboard | Scenes with narration, visual direction, on-screen text |
| FAQ | Question, answer, nuance, escalation path |
| Quiz | Every question **with the correct answer and rationale marked** — this is the review view; learners never receive it |
| Sources | The authoritative source inventory |
| Fact check | Ask a claim against the dossier before signing off (see §6) |

---

## 3. Address review comments

**Screen:** `/courses/{runId}` → **Review** tab

Comments arrive from reviewers grouped into **Open**, **Addressed**, and **Resolved**. Each carries an asset target, a severity (`blocking` / `major` / `minor`), the author, and the version it was raised against.

| Action | Call | Effect |
| --- | --- | --- |
| Mark addressed | `PATCH .../review/comments/{id}` `{status:"addressed", resolution}` | Prompts for a resolution note, which is stored and shown with the comment |
| Dismiss | same, `{status:"dismissed"}` | Closes it without a version bump |
| Reopen | same, `{status:"open"}` | Returns it to the open list |

Raising the first comment on a draft flips the course status from `draft` to `in_review` automatically. (`POST .../review/submit` can set that explicitly; the UI does not need it.)

---

## 4. Cut a version

**Screen:** same tab, **Cut a new version** card

`POST /api/runs/{id}/review/versions {user_id, summary}`

- Requires **at least one addressed comment**, otherwise 400 — a version always records what changed.
- Increments the version, moves every addressed comment to `closed` and stamps it with `closed_in_version`.
- Appends a version-history entry: summary, author, timestamp, and the ids of the comments it closed.
- Resets status to `in_review`, so sign-offs have to be re-recorded against the new version.

The version history sidebar reads bottom-up from `v1 — Agent-generated first draft`.

---

## 5. Publish and schedule

**Screen:** `/courses/{runId}` → **Publish** tab

The readiness gate is shown before the form, and the submit button stays disabled until it clears:

| Condition | Requirement |
| --- | --- |
| Approvals | At least one reviewer approved **at the current version** |
| Blocking comments | None open |
| Change requests | None outstanding at the current version |

`POST /api/runs/{id}/publication {user_id, starts_on, due_on, assignees, message}` then:

- Sets status to `published` and records the version being published.
- Rejects an empty trainee list or an unknown trainee id with 400.
- Writes one notification record per assignee — recipient, name, subject, timestamp — listed in the **Notifications sent** panel. Nothing is emailed; the panel says so.

Re-publishing updates the window, roster, and message in place.

---

## 6. Fact check a claim

**Screen:** `/courses/{runId}` → **Fact check** tab

`POST /api/runs/{id}/chat {question, learner}` ranks the run's own claims by inverse-document-frequency overlap, length-normalized, and answers from the top matches with their citations.

- Without an API key the answer is extractive — the strongest matching claims, verbatim, with sources. The badge reads **Dossier retrieval**.
- With a key those same claims are handed to the model, which must answer from them alone; the badge reads **Model answer**. Spend is metered into the run's usage ledger under a `chat` stage with its own cap.
- A question the dossier does not cover returns a refusal that suggests escalating to Medical Information, rather than a guess.

---

## 7. Monitor the cohort

**Screen:** `/courses/{runId}` → **Cohort** tab · `GET /api/runs/{id}/cohort`

Four tiles: assigned, started, certified, average knowledge uplift.

The learner table gives one row per assignee: stage, modules completed, a baseline→final score track, and the certificate code. The score track is a single bar for the final score with a marker at the baseline, so the gap between them *is* the uplift.

Stages: `not_started` → `baseline` → `learning` → `final` → `complete`.

Below it, every module rating and comment learners left, newest first — the feedback loop back into the next version.

---

## 8. Show the impact

**Screen:** `/courses/{runId}` → **Impact** tab · `GET /api/runs/{id}/analytics`

The headline compares measured elapsed time against a stated manual baseline. Everything on the left of that comparison is measured from this course's own logs; everything on the right is an assumption, and the panel says which is which rather than presenting the saving as a fact.

| Measured from the logs | Assumed (override per customer) |
| --- | --- |
| Draft generation time, expert review cycle, days to publish | A manual first version takes 30 days |
| Comment count, versions, reviewers, citations | Blended day rate of $900 |
| Agent spend on the run | A label-change update costs 15 days manually |

Override the assumptions with `PHARMALEARN_MANUAL_FIRST_VERSION_DAYS`, `PHARMALEARN_MANUAL_UPDATE_DAYS`, `PHARMALEARN_MANUAL_REVIEW_DAYS` and `PHARMALEARN_DAY_RATE_USD`.

Below it, the reporting a training platform is expected to carry:

- **Completion funnel** — assigned → started → baseline taken → modules complete → passed → certified.
- **Knowledge uplift** — the cohort average before and after, computed only over learners who took *both* assessments, with the sample size stated.
- **Final score distribution** across five bands.
- **Activity since publication** — modules, assessments and certificates per day.
- **Hardest questions** — percent correct per question from stored answers, worst first, with anything under 60% flagged. A question most learners miss is usually a gap in the material, and this is what feeds the next version.
- **Module engagement** — completions and the rating learners gave each module.

The admin dashboard carries a compact version of the headline so the comparison is visible on the first screen.

## 9. Curate the data store

**Screen:** `/knowledge`

| Tab | Purpose |
| --- | --- |
| Dossier | All 14 sections and their claims, each with evidence type and citations. The search box filters across every claim. Recorded gaps and warnings are surfaced separately |
| Sources | The authoritative source inventory with links |
| Add sources | Upload a document (`POST /api/uploads`, multipart) or fetch a URL (`POST /api/uploads/web`) |

A fetched URL is retrieved immediately, stored with its HTTP status, title, and byte count, and marked `unreachable` if the fetch fails. Staged items are held in the data store for the medical team; the bundled Ibrance run uses its own fixed source set, and the panel states that rather than implying otherwise.

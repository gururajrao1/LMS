# Reviewer flow

**Personas:** Dr. Anil Shekhar (therapeutic area expert, oncology) and Dr. Maria Alvarez (regulatory and medical affairs).
**Owns:** judging whether generated content is accurate, and recording the sign-off that lets it reach the field.

The reviewer is the *checker*. This is the role the demo exists to make cheap: the domain expert reviews rather than authors, and their comments become a versioned record instead of tracked changes in an emailed deck.

A reviewer cannot address their own comments, cut versions, publish, or see the cohort. Those tabs are not rendered for this role, and `publish_version` and `publish_course` reject a non-admin at the API, so the separation does not depend on the UI.

---

## 1. Open the queue

**Screen:** `/dashboard`

The same dashboard the admin sees, titled **Review queue** with the copy changed to match the role, and no **Create content** button. Course cards show the current version and review status; opening one goes to `/courses/{runId}`.

---

## 2. Read the content as a learner would

**Screen:** `/courses/{runId}`

Every asset tab is available, and the **HCP / MSL** toggle switches which track is under review — the two are generated separately and need judging separately.

The **Quiz** tab is the reviewer's view: correct answers, rationales, and citations are all marked, with a note that learners sit it without them and must clear the pass mark.

Every factual unit carries a citation chip. The **Sources** tab lists the authoritative inventory behind them.

---

## 3. Check a claim before judging it

**Screen:** **Fact check** tab

`POST /api/runs/{id}/chat` answers only from the dossier this course was built from, with citations. Use it to test whether a slide's claim is actually supported before raising a comment about it.

If the dossier does not cover the question, it says so and suggests escalation rather than inventing an answer.

---

## 4. Raise comments

**Screen:** **Review** tab → **Raise a review comment**

`POST /api/runs/{id}/review/comments {user_id, target, severity, body}`

| Field | Values |
| --- | --- |
| Asset | Clinical deck · Visual story · Field FAQ · Knowledge quiz · Sources and citations |
| Severity | **Blocking** — must fix before publication · **Major** · **Minor** |
| Comment | Free text; an empty body is rejected |

Severity is the lever that matters: a **blocking** comment left open makes publication impossible, and the admin's publish form shows exactly that as the reason. Major and minor comments are recorded and tracked but do not hold the release.

The first comment on a draft course moves it to `in_review`. Each comment records the version it was raised against, so history stays readable after several rounds.

Comments appear in **Open**, then **Addressed** once the admin has responded with a resolution note, then **Resolved** after a version closes them. The reviewer sees each state and the resolution text, but the address/dismiss controls belong to the admin.

---

## 5. Sign off

**Screen:** **Review** tab → **Your sign-off** card

`POST /api/runs/{id}/review/signoff {user_id, decision, note}`

| Decision | Effect |
| --- | --- |
| **Approve** | Counts toward the readiness gate at the current version |
| **Request changes** | Blocks publication at the current version even if an approval also exists |

A sign-off is recorded against the version that is current when you record it. Recording a second decision at the same version replaces your first — you cannot accumulate contradictory votes. When the admin cuts a new version, sign-offs at the old one no longer satisfy the gate, so re-approval is required after every change.

Multiple reviewers can sign off independently; the **Sign-offs** panel lists each decision with its author, title, version, and note. One approval is enough to clear the gate, so a two-expert review is a matter of practice rather than a hard-coded quorum.

---

## What the reviewer's decision controls

The admin's publish button is disabled until all three are true:

1. at least one **approval** at the current version,
2. **no** open blocking comments,
3. **no** outstanding change requests at the current version.

Attempting to publish anyway returns 400 with the reason, so the gate holds at the API, not just in the UI.

---

## The queue arrives pre-triaged

Before a human opens the course, an automated checker runs over every citable unit and writes what it finds into this same queue, authored by **PharmaLearn checker** and marked *automated*. It has role `checker`: it can raise comments and it can never sign off.

| Check | What it answers | Needs a model |
| --- | --- | --- |
| Quote fidelity | Does the recorded supporting quote actually appear in the stored source document? | No |
| Traceability | Does every citation trace back to a claim collected during research? | No |
| Source quality | Does this unit rest only on manufacturer-hosted or aggregator pages? | No |
| Overreach | Does the text state more certainty, breadth or benefit than its evidence supports? | Yes |
| Under-citation | Is this supported by the course's evidence, but not by the citation printed beside it? | Yes |

Findings are severity-ranked the same way yours are. **Blocking findings are raised automatically** and hold publication through the normal readiness gate. Everything else sits on the **Checks** tab until the medical education lead sends it over, so the queue is not flooded.

Coverage is reported honestly: only citations whose source document is held in full can be quote-checked, and anything else is reported as *unverifiable* rather than verified.

You accept or dismiss a machine finding exactly as you would a colleague's. That ratio is the **reviewer agreement** rate shown on the Checks tab — the calibration number that says whether the checker is earning its place.

# PharmaLearn — demo feedback: assessment and progress

Source: `todo.txt` (client-demo feedback). This document holds the reading of that
feedback, the plan derived from it, and the running status of the work.

Status legend: ⬜ not started · 🟡 in progress · ✅ done · ⏸️ deferred

---

## The frame

The two principles at the bottom of `todo.txt` are the spine — everything above is
in service of them:

1. **End-to-end, plus integration into their existing LMS** (we are not asking the
   client to rip anything out).
2. **Faster, cheaper, better** — in that order, and *better* is the one that is hard
   to fake.

Items 1–8 split into **three that change what the product is** and **five that change
how well it demos**.

---

## The three structural items

### 1 · "How do you ensure accuracy and completeness?"

The hardest question in the list. Three distinct sub-asks, worth keeping separate:

**(a) Can the system catch a *reviewer* who is wrong?** — Today: **no.** We verify
generated content against stored sources. We do not verify a reviewer's *resolution*
against those sources. Readiness gating counts comments; it does not judge them. If a
reviewer dismisses a valid blocking finding, or approves a wrong rewrite, nothing
stops it. This is the most defensible thing we could add — "AI checks the human,
human checks the AI" is a claim no competitor makes, and it is the natural extension
of the checker that already exists.

**(b) The reviewer needs the evidence in front of them, internal *and* external.**
The unmet-needs example is the right test. Today the Ask bot is course-scoped,
retrieval-first over the dossier — it cannot be opened *on a specific comment*, and
it cannot reach past the corpus we collected. To resolve fast, a reviewer needs: the
claim, the cited passage, the source document, and *what we could not find* — in one
place.

**(c) The audience is expert.** MSLs and HCPs in the same therapeutic area. Content
cannot be shallow. Our honest number is **21% citation coverage** — the thing to fix,
not hide.

Deliverable explicitly requested: **a written approach note plus a demo flow that
backs it up.**

### 2 · Project / tenancy model

Client (e.g. Pfizer) → N drugs → N training programs, each with a lifecycle:
**live / completed / archived**, scheduled and managed. Then a **client-level
consolidated report** across all programs, exportable as PDF or shown as a dashboard
tab.

Today: flat list of runs. One `publication` record per course carrying `starts_on` /
`due_on` / `assignees`. `review_status` reaches `published` and stops — no archived
state, no client entity, no cross-course rollup. Cohort and Impact are per-course only.

This is **extending** cohort + impact upward, not rebuilding them.

### 3 · The process flow is not obvious when demoing

The ten steps from `todo.txt` are the demo script:

> project → agents build → agents + humans validate → define trainees → schedule &
> publish → grant access → capture baseline → trainees certify within schedule →
> client watches progress across programs → client sees ROI

Every one of those exists in the codebase. **None is visible as a sequence.** They are
scattered across tabs with no spine. Cheapest high-impact item in the file — it is
presentation of things already built.

---

## The five that sharpen the demo

| # | Ask | Today | Note |
|---|---|---|---|
| **4** | Trainee schedule: in-progress / upcoming / completed with timelines | Learner home lists courses with dates, no schedule framing | Small; data already there |
| **5** | Gamify the quiz — word building, image-select (severe vs non-severe) | Plain MCQ | ⚠️ see below |
| **6** | Page-contextual Ask suggestions | Dock is course-scoped, no starters | Cheap, demos well |
| **7** | Sidecar viewer for locally-held reference docs | Sources are links only | Same investment as fixing coverage |
| **8** | Document every place an agent is used | Undocumented | Inventory below |

**On item 5 — one flag.** Gamification is the item most likely to work against us with
senior management. Word-building and image-select read as *consumer edtech* to an
audience whose actual anxiety is regulatory exposure. Image-based clinical severity
questions also need licensed, accurate imagery — a sourcing problem, not a UI one.
Suggestion: build *one* gamified format as proof the engine supports it; do not lead
with it.

**On item 7** — same underlying work as raising coverage past 21%. Hold the source
documents in full rather than as links, and both the sidecar and the verification rate
come from it. One investment, two visible wins.

---

## Item 8 — agent inventory (as it stands today)

| Where | What the agent does |
|---|---|
| `research_*` | One call per dossier section, run in parallel — collects claims + citations |
| `build_master_dossier` | Synthesises the researched sections into one master dossier |
| `generate_{track}_{asset}` | Deck, quiz, FAQ, storyboard — per track (HCP, MSL) |
| `generate_{track}_triage` | Sort board — findings into one of two labelled actions |
| `generate_{track}_assemble` | Word building — a labelled instruction rebuilt from phrase chips |
| `generate_{track}_figure` | Read-the-data questions about a chart drawn from cited numbers |
| `render_{track}_pptx` | PowerPoint via Anthropic Skills (`pptx` + custom `pharmalearn-decks`) |
| `attach_citations` | Binds citations back to units |
| `judge.model_findings` | Judgement-requiring checks (`unsupported`, tone, balance) |
| `judge.confirm` | Second pass — confirms or drops findings before they are raised |
| `assistant.answer` | Ask bot, model mode |

The part that matters for the accuracy story: **`judge.deterministic_findings` uses no
model at all** — quote matching against stored source text, plus citation
traceability. That is where 5 of the 7 blocking findings came from.

---

## Plan and status

Working top to bottom through `todo.txt`. Each step stops for review before the next
one starts.

### Item 1 — accuracy and completeness

| Step | Description | Status |
|---|---|---|
| 1.0 | Accuracy & completeness approach note (`docs/ACCURACY.md`) — the written answer plus the demo flow that backs it | ✅ |
| 1.1 | Attributed resolutions + append-only audit trail (closes the unauthenticated-PATCH hole) | ✅ |
| 1.2 | Dismissal re-check and challenge — a deterministic finding cannot be silently dismissed | ✅ |
| 1.3 | Rewrite re-check before a version is cut | ✅ |
| 1.4 | Comment-scoped evidence for the reviewer — claim, cited passage, source document, stated gap, in one place | ✅ |
| 1.5 | Completeness coverage matrix — required topics × what the course covers | ✅ |
| 1.6 | Coverage lift: wire `scripts/fetch_pfizer.py` into the pipeline so registry citations resolve on demand | ✅ |
| 1.7 | Per-reviewer calibration; depth floor for expert audience | ✅ |

### Item 2 — project / tenancy model

| Step | Description | Status |
|---|---|---|
| 2.0 | Client → drug → program data model; program lifecycle (live / completed / archived) | ✅ |
| 2.1 | Client-level dashboard consolidating cohort + impact across programs | ✅ |
| 2.2 | PDF export of the consolidated report | ✅ |

### Item 3 — visible process spine

| Step | Description | Status |
|---|---|---|
| 3.0 | Make the ten-step flow visible and navigable end to end | ✅ |

### Items 4–8

| Step | Description | Status |
|---|---|---|
| 4.0 | Trainee schedule view — in progress / upcoming / completed, with timelines | ✅ |
| 5.0 | Gamified quiz formats — sort board, word building, figure questions | ✅ |
| 6.0 | Page-contextual Ask starter questions | ✅ |
| 7.0 | Source sidecar — read locally-held reference documents in-app | ✅ |
| 8.0 | Publish the agent inventory as documentation | ✅ |

---

## Log

| Date | Entry |
|---|---|
| 2026-08-18 | **Item 8 done — `docs/WHERE_AI_IS_USED.md`**, written for a non-technical reader. Thirteen agent roles across research, authoring and checking (≈744 calls per course), each described as a job rather than a feature. **The second table is the one that matters for this audience: where AI is deliberately not used** — quote verification, citation traceability, coverage, marking, schedules, programme answers, and approval. Five of the seven blocking findings on the example course came from the non-AI half, which is the strongest single fact in the note. Every figure in it was checked against the system rather than recalled: 744 calls, 341 citations, 109 findings / 7 blocking, 5 of 7 blocking from deterministic checks, 14 research sections. One claim was softened on checking — the model pass runs on the primary track by default, so "reads every unit" would have been an overstatement. **All eight `todo.txt` items are now complete.** |
| 2026-08-18 | **Item 7 done — the sidecar, and the last link in the provenance chain.** The Sources tab is now a **reference library**: `38 of 125` cited documents are held here in full and open in a right-hand reading pane with find-in-document, match counts and next/previous. The rest are listed honestly as *"Linked, not stored — a quote against them cannot be machine-verified."* The chain now closes in one place: **citation chip → recorded quote → the stored document, scrolled to and highlighting that sentence** — verified on the real FDA label (96,761 characters, quote found and marked). It also means the evidence survives the publisher changing a URL, which for a label is not hypothetical. Text is rendered as paragraphs, never as the source's own HTML: this is untrusted third-party content and injecting it as markup would be a scripting hole opened for the sake of typography. |
| 2026-08-18 | **Two fixes found by reading the result rather than the code.** The US label opened on an **API envelope** — `history.json` (1.8KB) sorts before `spl.xml` (510KB), so alphabetical order put DailyMed's metadata ahead of the prescribing information. `readable_source` now orders by substance and nothing is dropped, since a quote can legitimately sit in either file. And the library first reported **42 held of 129**, double-counting the same SPL under `drugInfo.cfm` and `lookup.cfm`; collapsed by `source_key` it is **38 of 125**, with *"cited under 3 URLs"* shown on the row — overstating how much of the evidence we hold would be the exact kind of quiet inflation the rest of this system exists to catch. Also: the floating **Ask** button rendered on top of the open sidecar. Fixed in CSS, deliberately unlayered — inside `@layer components` the rule loses to the `flex` utility on the button itself. 7 new tests, 142 pass. |
| 2026-08-18 | **Item 6 done — the Ask starters are contextual, and grounded.** Five contexts (`material` / `evidence` / `review` / `programme` / `learner`) mapped from the thirteen workspace tabs, fetched from `GET /api/runs/{run}/chat/starters?context=`. **Every suggestion is checked before it is offered**: a dossier question only appears if retrieval actually finds something, a record question only if the record holds the answer. A starter that leads nowhere is the demo failing in the exact place we claim to be well grounded, and it caught a real one — *"How does this compare with the alternatives?"* reads well and retrieves nothing, because neither word appears in any claim. Replaced with *"What are the current standards of care?"*, which hits the Currently Available Treatments section. Each chip says where its answer will come from before it is clicked. |
| 2026-08-18 | **The bot can now answer about the programme, not just the drug.** The client's *"When will this training program launch?"* is not a dossier question — no retrieval over prose can answer it and the model would be guessing. `assistant.platform_answer` reads schedule, cohort and governance straight off the record, with **no model in the path**, and replies are badged *From the record*. The routing is the risky part, so it is tested in both directions: six programme questions must be answered from the record, and five drug questions — including *"When did PALOMA-2 start?"* and *"Which sources support the approved indication?"* — must fall through to the dossier. Bare "approved" is deliberately **not** a platform word: in this domain it means the drug far more often than a sign-off. |
| 2026-08-18 | **A trainee is told their own standing, not the cohort's.** Asked "when is this due", the first version answered *"currently completed"* to a learner whose own card two clicks earlier said *33 days overdue* — both true, of different subjects. The chat now carries `user_id`, and for an assignee the answer is theirs: *"For you it is overdue, and you are 50% through the material."* Also fixed *"(-1 day ago)"* — the word already carries the direction, so the sign must not be printed too. 22 new tests, 135 pass. |
| 2026-08-18 | **Two more formats, for variety.** *Word building* (`assemble`) is the clinical form of the mechanic: rebuild a labelled instruction from phrase chips, where the chips are the words that change what a clinician does — `125 mg` / `21 consecutive days` / `7 days off`, `Grade ≤2` / `resume at the next lower dose`. Assembling a drug name from letters would teach nothing. *Figure questions* are the honest form of "include images to select from": **charts rendered from cited numbers, never a photograph, scan or histology slide** — those need licensing we do not have, and a wrong or unrepresentative image is a clinical error no check of ours could catch. The charts carry real trial data (PALOMA-2 PFS 24.8 vs 14.5 mo; final OS 53.9 vs 51.2, HR 0.956, not significant; PALOMA-3 9.5 vs 4.6). `fold_boards` generalised to **`fold_groups`**: every format still reduces to one primitive — a prompt, options, one correct index — so a sort item, one blank in a sentence, and a chart question are all ordinary quiz questions. Identity in a chart is never colour-alone (name, line style, marker, direct labels) and every chart ships a table of its own numbers. The cycle now carries **20 gamified questions on the HCP track, 18 on MSL**; the checker ran over all of them (49 findings, 4 blocking, publication refused until settled). 113 pass. $5.81 of $8. |
| 2026-08-18 | **Generation degrades rather than failing, so the build gates it.** Twice the agent returned a well-formed figure question whose prompt was the literal word `"placeholder"` with an empty citation list. The JSON validated, so nothing upstream objected — a chart would have rendered under the question "placeholder". `build_formats.py` now drops what cannot ship (placeholder prompt, no citations, fewer than two plotted points), says exactly what went and why, and asks again once with the reason. That took the HCP figures from 1 unusable chart to **4 usable ones for $0.09**. Same correction that worked on the sort board: tell the model what was measured, not the rule again. |
| 2026-08-18 | **Figures were missing from the baseline** — they carry no `group`, so the plain-question stride never reached them and the format was only ever asked at the finish. Fixed by sampling figures *as figures* (`BASELINE_FIGURES`), which is the same rule that keeps groups whole: uplift is a comparison, so a skill measured only at the end is counted as learning without ever having been tested for at the start. Also fixed two of my own layout bugs, found by rendering rather than reading: a y-axis title anchored beside the tick labels ran off the frame (*"Median progression-free survival"* drew as *"vival mo"*), and single-series bar charts reserved a third of the frame for a legend they never drew. |
| 2026-08-17 | **Item 5 done — the sort board.** Not word-building and not image-select: a **triage board**, which is the client's "severe vs non-severe" instinct built as the decision an MSL actually makes — one clinical finding at a time, two labelled *actions*, tap to place. It needs no licensed clinical imagery, and the content is the label. **The board is a way of asking, not a second assessment engine:** `agent.fold_boards` turns each item into an ordinary quiz question carrying a `board` key, so the checker verifies its citations (`judge.units` needed no change), `record_attempt` scores it toward the same certificate and the same measured uplift, and the review queue can raise a comment on it. Strip the `boards` list and every item is still a valid scored question — test-enforced. The baseline keeps a board **whole** rather than sampling it: uplift is a comparison, and a skill only tested at the end gets counted as learning. **The governance ran for real and refused to publish**: 38 findings, 4 blocking, and one of them was a fabricated citation on board item `t1` (*"IBRANCE\, for for oral use" does not match any claim collected during research*). It lives on the safety-refresher cycle, not the live course, because re-running the checker there would overwrite the record of what was caught on the draft. 11 new tests, 109 pass. $3.76 of $8 spent. |
| 2026-08-17 | **Three bugs found while building item 5, two of them mine.** (a) A **latent** one in `_asset`: `if attempt == 1` re-raised only on the storyboard's second try, so every other asset swallowed a truncated response and then read an unbound variable — a clear "the model was cut off" surfaced as an `UnboundLocalError` three frames away. (b) I measured whether a board could be passed by sorting on severity adjectives alone; the first board scored **86%** against a 67% pass mark, so it was a vocabulary test. Feeding the measurement back into the prompt took HCP to **29%**. MSL's retry measured *worse* (100%), and the "keep only if it improves" guard correctly kept the original — so MSL stands at **88%** and is the weaker board, recorded rather than hidden. (c) The measurement itself was **wrong**: it assumed bucket 0 was the acting bucket, and the HCP board listed "continue" first, so it scored the inverse heuristic and reported a plausible-looking number either way. `acting_bucket()` now reads the labels. |
| 2026-08-17 | **A hole worth naming: we verify provenance, not relevance.** Repointing a failed citation picked the first dossier claim whose quote verified, which put a *bladder-metastasis case report* behind a neutropenia dose-modification question — traceable, verbatim, checker-clean, and about something else. `_verified_citation` now ranks candidates by term overlap with the text being cited. But the general point stands and no current check catches it: a citation can pass every check we have and still not support the claim. Worth saying out loud in the demo rather than being asked. |
| 2026-08-17 | Read `todo.txt`, wrote this assessment, agreed to work top to bottom with a review gate after each step. |
| 2026-08-17 | **Step 1.0 done** — `docs/ACCURACY.md`. Found three concrete holes while grounding it: resolution is unauthenticated (`api/main.py:311`), dismissing a blocking finding silently flips `can_publish` (`src/learning.py:169`), and rewrites are never re-checked (`src/learning.py:238`). Re-cut the item-1 sub-steps around them. |
| 2026-08-17 | **Reseeded** (`--reseed`; prior state archived to `platform/archive/20260817T123641Z`, nothing deleted). The course now has a fully attributed 38-entry trail, 15 comments closed with **0 unverified**, 91% agreement, and one named override on the publication. 5 citations were repointed in the assets so the resolutions are true. Checks tab unchanged — 109 findings, 7 blocking — because it reads the v1 snapshot. 11 comments raised instead of 10: the ID-collision fix means both q3 findings now reach the queue. ROI unchanged at 3.0 vs 30.0 days. |
| 2026-08-17 | **Item 4 — schedule data added.** With one programme a learner only ever saw one category, so the schedule view was unreadable. `scripts/seed_schedule.py` stands up the cycles a medical affairs team actually runs for one drug — annual recertification (completed), safety refresher (overdue), label-update briefing (upcoming) — alongside the live course. **Same drug, same content:** a card reading "Eliquis" over palbociclib material would be exactly the quiet untruth the rest of the system exists to catch, so the cycle names the programme and `drug` still names the medicine. Assets are symlinked, not copied (103MB × 3 saved). Two honesty fixes found while checking the result: baselines were scoring 0, making "+100 uplift" look manufactured — now deterministic per learner and believable (42 → 100); and counting the reused cycles as separate builds would have reported **436 findings and 4× the build cost** in the portfolio's credibility block, so manifests carry `reuses` and the portfolio excludes them from build economics while still counting reach and uplift. Cost per certified learner correctly falls $900 → $338, which is the real argument for reusing approved content. `--remove` takes it all back out. 98 pass. |
| 2026-08-17 | **Item 4 done** — the trainee home is a schedule now, grouped **Overdue → In progress → Upcoming → Completed** in the order that matters to the person reading it, each card carrying a timeline with today marked inside its window. `learning.assignment_state()` derives the state the same way the programme lifecycle does, with the learner's own progress taking precedence: nothing is overdue for someone who already finished it. The lede answers the only question a trainee opens this to ask — *"Your closest deadline is Ibrance, due today."* Verified across two learners: a certified one sees only "Completed" and no today-marker; one mid-course sees "In progress", the marker, and "Due today". The React Compiler caught `Date.now()` in render — fixed by positioning the marker from the server's own day counts, which also removes a real hydration mismatch across timezones. 5 new tests, 98 pass. |
| 2026-08-17 | **Item 3 done** — `src/journey.py` and a **Journey** tab, now the admin's landing view on a course: *From a drug name to a certified field team*, the ten steps in order with the evidence for each and a link into the tab where it lives. **State is computed, never stored** — a step is done because its evidence exists, so the spine cannot run ahead of the work or fall behind it, and there is no status field for anyone to fix up. Exactly one step is ever "in progress": the first not yet done. On the seeded course it reads 10/10 with real numbers at every step (341 citations, 109 findings / 7 blocking / 21% checkable, 16 comments / 91% agreement / 2 sign-offs, 5 trainees, 5 of 5 baselined, 3 of 5 certified / +38 points, 3.0 days to field / $24,300 saved). Nothing new was built to make this work — it is the same records read in order. 2 new tests, 93 pass. |
| 2026-08-17 | **Step 2.2 done — item 2 complete.** "Export PDF" on the portfolio, via a print stylesheet and the browser's own print-to-PDF. Chosen over a server-side renderer deliberately: weasyprint/reportlab means a system-library dependency and a second layout to keep in sync, and the PDF would drift from the page the first time either changed. Screen chrome is hidden, a print-only provenance line is added (date, "measured, not modelled", regulatory scope), `print-color-adjust: exact` keeps the bars painted, and `.print-keep` stops a card splitting across a break. Verified by generating the real PDF headlessly rather than trusting the CSS: 2 pages, all six blocks intact, bars painted, nav and button absent. |
| 2026-08-17 | **Step 2.1 done** — `/portfolio`, a client-level consolidation of cohort + impact across every programme, plus `programmes.portfolio()` and `GET /api/clients/{id}/portfolio`. Five blocks, no metric spam: reach, pooled uplift, time to field, cost per certified learner, and *Caught before the field* — the one block that is not about speed or money. **Averages are pooled over learners, never averaged over programmes**; a mean of means weights a five-person pilot like a five-hundred-person rollout and reports a number no learner produced (test-enforced with a worked case: +20 pooled vs +25 by mean-of-means). Archived programmes are counted, so tidying up cannot flatter the portfolio. Reads $900 vs $9,000 per certified learner, 3 vs 30 days, 109 findings / 7 blocking / 91% agreement / 1 override. Caveat: with one programme the consolidation equals the single programme — the arithmetic is what generalises. 4 new tests, 91 pass. |
| 2026-08-17 | **Step 2.0 done** — `src/programmes.py`: client → programme, where a programme is a course *in the field* (published, scheduled, with a cohort). **Lifecycle is derived, not stored**: scheduled / live / completed come from the calendar and the cohort on every read, so the label cannot drift the way a stored status does and needs no job to keep it honest. Archiving is the one stored state, because it is a decision a person makes — attributed, reversible, and it touches nothing else. A fully certified cohort counts as completed before its deadline: the schedule is a deadline, not the definition of done. `GET /api/clients`, `GET /api/clients/{id}`, archive/restore. Programmes panel on the admin dashboard. One client (Pfizer) seeded and the model takes N — inventing tenants would put fabricated organisations in a demo about not fabricating. Also stopped both list surfaces from reprinting the full (erroneous) indication string away from the checks that scrutinise it. 9 new tests, 88 pass. |
| 2026-08-17 | **Step 1.7 done — item 1 complete.** Per-reviewer calibration on the Checks tab: counts always, a rate only above 3 settled findings, and overrides counted apart from plain dismissals. On the seeded course that reads Priya Raman 10 accepted / 0 dismissed (100%) and Dr. Shekhar 1 dismissed / 1 overridden (**n=1**, deliberately unrated). Depth floor shipped as `imprecise_effect`: an efficacy effect stated without a CI, p-value or range — 5 findings on 101 units, and the same defect the seeded human reviewer had to catch by hand. Two earlier candidate rules measured at 0 findings and were dropped rather than shipped as decoration; one of them was a `re.I` bug making an all-caps trial-name token match any word. 3 new tests, 78 pass. |
| 2026-08-17 | **Step 1.6 done** — **coverage 21% → 38%**, verified quotes 21 → 48, corpus 11 → 38 documents. Two parts. (a) A correctness fix: `judge.source_key` gives a document one identity, so the same DailyMed SPL written as `drugInfo.cfm`, `lookup.cfm` and `&version=23` is recognised as the one document we already held — 21% → 24% with no network. Deliberately *not* applied to `cdn.clinicaltrials.gov` protocol PDFs, which are a different document from the study record. (b) `scripts/resolve_citations.py` reads a run's own citations, resolves the ones naming an open-registry document, and fetches them through the existing handlers into a **supplementary** snapshot; `source_corpus` now reads every snapshot, newest wins. 27 fetched, 0 failed, 24 with full text. New `pmc_article` handler in `fetch_pfizer.py`. **Did not overwrite the stored report** — it is the v1 record of what the machine caught on the draft, and 5 of its findings would vanish because step 1.3's fixes genuinely landed. The Checks tab now reports both: the snapshot's 21% and the live corpus's 38%. 4 new tests, 75 pass. |
| 2026-08-17 | **Step 1.5 done** — new **Coverage** tab: 15 required topics × HCP/MSL, from `config/curriculum/us_oncology.toml` so a medical education lead can change what "complete" means without a deploy. Three states, not two — a topic mentioned once is reported **thin**, because on a 101-unit course one mention reads as coverage and is not. Gaps promote into the ordinary review queue as checker comments (`check: not_covered`), addressed or dismissed like any other, blocking ones holding publication. First pass scored 100% on loose patterns; tightened them and added the thin state, which took it to a truthful 92% with 2 real gaps. `src/completeness.py`, `GET/POST /api/runs/{run}/completeness`. 7 new tests, 71 pass. |
| 2026-08-17 | **Step 1.4 done** — "Show me the evidence" on any machine comment: the claim as written, the recorded quote rendered span by span against the stored document (matched text highlighted, invented text struck through), the passage from the source itself, and every citation marked traceable / held / neither. `GET /api/runs/{run}/review/comments/{id}/evidence`. Highlighting and the percentage are built from the same five-word shingles, so they can never disagree — test-enforced. Found and fixed a fixture gap while building it: `tests/test_judge.py` never wrote a `manifest.json`, so any check re-reading the drug had no corpus. 4 new tests, 64 pass. |
| 2026-08-17 | **Step 1.3 done** — cutting a version now re-reads the assets and checks that every claimed fix is actually there. A comment whose check still reproduces is not closed: it returns to the queue marked `unverified`, and a version cut where nothing verifies is refused outright. Human comments have no check behind them and are taken at their word. One corpus pass per version cut, not one per comment (test-enforced). **This caught the seed lying:** 4 of its machine "fixes" were narrative only and were never applied to the content, so a fresh seed failed at publication. `seed_demo.py` now repoints the offending citations at a dossier source whose quote verifies — the fixes are real, and a fresh seed produces 15 comments closed, **0 unverified**, 91% agreement, one attributed override. Existing course untouched (verification is forward-only). 4 new tests, 60 pass. |
| 2026-08-17 | **Step 1.2 done** — dismissing a machine finding now re-runs the check. If it still fails the dismissal is *challenged*: the comment stays open, publication stays held, until either the source is added or a named override is recorded. Only the six deterministic checks are challengeable — a model judgement is dismissed without argument, because a human expert outranks the model there. Verified on real Ibrance data: the 0% quote and both fabricated citations are challenged; both `unsupported` findings are accepted. 65ms per re-check, no model, no network. Overrides are stamped on the publication record. 8 new tests, 56 pass. **Open question for the demo:** every machine comment on the seeded course is already settled, so there is no live finding to challenge on screen — see the note below. |
| 2026-08-17 | **Step 1.1 done** — resolutions are attributed and every governance step is on an append-only trail. `resolve_comment` now requires a named user, refuses anyone who is not an admin or reviewer (the checker raises but never settles), and refuses to reopen a comment already closed into a version. New `Activity` card on the Review tab. Backfilled the existing course's trail from data it already stored; the 15 historic resolutions read *"Settled before resolutions were attributed"* rather than naming a plausible actor. Also found and fixed an impossible sequence in the seeded timeline (a version cut closing comments the trail showed as resolved later) — `seed_demo.py --retime`; ROI figures verified unchanged at 3.0 vs 30.0 days. 6 new tests, 49 pass. |

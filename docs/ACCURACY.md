# Accuracy and completeness — how PharmaLearn ensures it

The question a client will ask in the first ten minutes is some version of:

> *You generated this with an AI. Why should I let it in front of my medical
> affairs team?*

This document is the answer. It states what the system does today, where it is
weak, what we are adding, and the demo sequence that proves each claim rather than
asserting it.

Two things are treated as separate problems throughout, because they fail
differently:

- **Accuracy** — what the material says is true, and traceable to a source we hold.
- **Completeness** — nothing a knowledgeable reader would expect is missing.

An accurate course can still be dangerous if it omits a contraindication. A
complete course can still be wrong. Both need their own check.

---

## 1 · The principle

**Nothing is trusted because a model produced it, and nothing is trusted because a
human approved it.** Every claim in the material has to be attached to a document we
hold, and every decision made about that claim has to survive being re-checked
against the same document.

That gives four lines of defence. Three exist today. The fourth is the gap this
document closes.

| | Line of defence | Trusts | Status |
|---|---|---|---|
| 0 | Held source corpus — documents, not links | nothing | partial (21% coverage) |
| 1 | Pre-review machine check | the corpus | **built** |
| 2 | Human expert review, role-separated | the expert | **built** |
| 3 | Resolution verification — re-checking the expert | the corpus, again | **gap** |

---

## 2 · What exists today

### Line 0 — the corpus

We store source documents in full, not as URLs, and match quoted text against them.
Coverage is reported honestly: a citation whose source document we do not hold is
recorded as **unverifiable**, never as verified.

Current numbers on the Ibrance course: 101 units, 188 citations, 186 traceable,
39 checkable, 21 verified, 15 partial — **21% coverage**.

That 21% is the weakest number in the system and we lead with it rather than bury
it. Section 5 is how it goes up.

### Line 1 — the pre-review check (`src/judge.py`)

Runs before any human opens the course. Six checks are **deterministic** — no model,
no API key, no judgement:

| Check | Severity | What it answers |
|---|---|---|
| `quote_not_found` | blocking | Does the recorded supporting quote appear in the stored source document at all? |
| `untraceable` | blocking | Does this citation match any claim actually collected during research? |
| `quote_not_verbatim` | major | Is the quote stitched or paraphrased rather than lifted? |
| `uncited` | major | Does a factual unit carry no citation? (front matter is exempt) |
| `promotional_only` | major | Does this claim rest *only* on manufacturer-hosted or aggregator pages? |
| `comparative_claim` | major | Is there superiority language without head-to-head evidence? |

One check requires a model — `unsupported` / `overreach` / `needs_context`, which
asks whether the asset says more than its evidence supports. Findings from it are
re-confirmed by a second pass (`judge.confirm`) before they are raised at all.

**Why this matters more than it sounds:** on the Ibrance course the checker raised
7 blocking findings, and **5 of the 7 came from the deterministic checks**. Those are
not an AI's opinion about quality. They are "this sentence is not in the FDA label",
which is either true or false and can be shown on screen.

What they caught:

- **Three fabricated quotes** — supporting text matching the stored DailyMed SPL at
  **0%** and **12%**.
- **Two fabricated citations** — scenes 5 and 6 cited papers that were never
  collected during research.
- **An off-label indication claim** — HCP slide 14 and MSL slide 17 described a
  HER2-positive maintenance indication. Palbociclib is approved for HR+/HER2-negative
  disease only. The error originated in the source metadata and propagated into two
  decks; both instances were caught downstream.

### Line 2 — human review

Maker–checker separation, enforced at the API rather than hidden in the UI, and
covered by tests:

- `test_the_checker_can_raise_comments_but_never_sign_off`
- `test_only_a_reviewer_can_sign_off`
- `test_a_reviewer_cannot_cut_versions_or_publish`
- `test_blocking_findings_hold_publication`
- `test_unassigned_learner_cannot_open_a_course`

Reviewer agreement with the machine checker on the Ibrance course: **90%** (9 of 10
settled findings accepted, 1 dismissed).

---

## 3 · The gap — and it is a real one

> *"If reviewers give wrong input, can our system identify it and prevent
> degradation?"*

**Today the honest answer is no.** Three specific holes, all verifiable in the code:

**(a) Resolution is unauthenticated.** `PATCH /api/runs/{run_id}/review/comments/{id}`
(`api/main.py:311`) carries no user identity. `learning.resolve_comment`
(`src/learning.py:224`) takes `run_id`, `comment_id`, `status`, `resolution` — and no
author. We do not record *who* resolved a finding, so we cannot attribute or audit it.

**(b) Dismissal silently unblocks publication.** `readiness()`
(`src/learning.py:169`) counts only comments whose status is `open`. Setting a
blocking finding to `dismissed` removes it from `open_blocking`, which flips
`can_publish` to true. A valid, correct, machine-proven blocking finding can be made
to disappear with one PATCH and no justification.

**(c) A rewrite is never re-checked.** `publish_version` (`src/learning.py:238`)
requires at least one addressed comment and cuts a version. The replacement text is
not run back through the checks. A rewrite that fixes the flagged sentence while
introducing a new uncited claim passes unnoticed.

So the current system is strong at catching what the *machine* got wrong and has no
defence at all against what a *human* gets wrong. For a client whose actual anxiety
is regulatory exposure, that is the wrong way round.

---

## 4 · The approach — Line 3, resolution verification

The insight that makes this tractable: **the deterministic findings are facts, not
opinions.** Whether a quote appears in a document does not become false because a
reviewer disagrees with it. So a dismissal can be checked by re-running the identical
check — no second model, no AI arguing with a doctor.

### 4.1 Dismissals are re-checked, not accepted

When a reviewer dismisses a finding, the originating check re-runs against the stored
corpus.

- **Check still fails, and it is deterministic** → the dismissal is *challenged*. The
  finding does not leave `open_blocking`. The reviewer is offered exactly two ways
  forward:
  1. **Attach the source.** Add the document that contains the quote. The check
     re-runs; if it now passes, the finding closes legitimately and coverage goes up
     as a side effect.
  2. **Record a named override.** A signed, attributed, reasoned exception. It is
     stored, it appears in the audit trail, and it is stamped on the published
     course. Overriding is allowed — doing it invisibly is not.
- **Check still fails, and it is a model finding** → dismissal is accepted (a human
  expert outranks the model on judgement calls) and recorded as a disagreement,
  feeding the agreement statistics.
- **Check now passes** → the dismissal is accepted silently. The world changed; the
  reviewer was right.

This is the whole "prevent degradation" answer, and it costs no API spend.

### 4.2 Rewrites are re-checked before the version is cut

When a reviewer supplies replacement text, that text goes back through the same unit
checks before `publish_version` accepts it. A rewrite that drops the citation,
introduces an uncited claim, or quotes text that is still not in the source is caught
at the point of edit — while the reviewer is still looking at it — instead of
surviving into a published version.

### 4.3 Every resolution is attributed

`resolve_comment` takes a `user_id`, the role is enforced server-side, and the
resolution joins an append-only trail: who, when, what changed, which check re-ran,
and what it returned. This is a prerequisite for the other two and closes hole (a).

### 4.4 Reviewer calibration, surfaced not policed

We already compute agreement between the checker and the reviewers in aggregate.
Extending it per reviewer gives a signal for a training-quality conversation: a
reviewer dismissing materially more deterministic findings than peers is worth a
look. Presented as calibration, never as a scorecard.

### 4.5 Completeness — the coverage matrix

Distinct from accuracy and needs its own mechanism.

Required topics per audience are declared (indications, dosing and administration,
contraindications, warnings and precautions, adverse reactions, drug interactions,
use in specific populations, mechanism of action, pivotal trial evidence, monitoring
— plus audience-specific items such as unmet need and competitive positioning for
MSLs). The matrix is *required topic × what the course actually covers*, and every
empty cell is a finding with the same severity machinery as the accuracy checks.

This is what answers the unmet-needs example directly: if the material covers it, the
matrix says where; if it does not, the gap is raised as a finding rather than left for
someone to notice.

The dossier already carries `gaps` and `warnings` per section, so the raw material for
this exists — it is not currently rolled up into a required-topic view.

### 4.6 Depth floor for an expert audience

The material goes to people who work in the same therapeutic area, so shallow is a
defect. Depth is partly checkable: a claim resting on trial evidence should carry the
trial identifier, the population, the endpoint and the effect size. Absence of those
where the evidence type is a clinical trial is a `shallow_claim` finding.

---

## 5 · Closing the coverage gap (Line 0)

21% is low because we hold roughly 10 source documents against 120 distinct cited
sources. The fix is mechanical, not conceptual.

Of the 341 citations in the dossier, **146 (43%) sit on machine-fetchable open
registries**:

| Registry | Citations |
|---|---|
| DailyMed | 42 |
| accessdata.fda.gov | 31 |
| ncbi.nlm.nih.gov | 25 |
| cdn.clinicaltrials.gov | 19 |
| pmc.ncbi.nlm.nih.gov | 14 |

`scripts/fetch_pfizer.py` already parses all four formats (`pubmed.xml`,
`study.json`, `spl.xml`) against an allowlist in `config/sources/pfizer_us.toml`. It
is simply not wired into the pipeline to resolve citations on demand. Doing so
roughly doubles-to-quadruples verified coverage.

The residual — `pfizer.com` (29) and `pfizerpro.com` (25) — is manufacturer-hosted,
which the checker already flags as `promotional_only`. That is correct behaviour, not
a gap to close.

**Second-order benefit:** once documents are held rather than linked, the reviewer can
read them in the app (the sidecar in `todo.txt` item 7). One investment, two visible
wins.

---

## 6 · Giving the reviewer what they need to resolve quickly

A reviewer should never have to leave the comment to decide it. On any finding:

- The **claim** as written in the asset.
- The **cited passage** from the dossier, with the matched and unmatched spans marked
  — so a 12% quote match is visible rather than a number.
- The **source document itself**, in the sidecar, scrolled to the passage.
- **What we do not hold**, stated plainly, with the option to fetch it from the
  allowlisted registries in place.
- **Ask, scoped to this finding** — retrieval over the dossier and held corpus first,
  model only when retrieval is thin, answering with citations and saying so when the
  answer is not in the corpus.

That last point is the unmet-needs example in the feedback: the reviewer asks "what
are the unmet needs here?", gets the internal dossier answer plus what the registries
say, and is told directly whether the material already covers it.

---

## 7 · The demo sequence

Roughly ninety seconds, and every step is shown rather than described.

**1 — A finding that is a fact.**
Open the Checks tab. Take `quiz-q3`: *"Only 0% of the recorded supporting quote
appears in the stored source document."* Put the asset text and the actual DailyMed
SPL side by side. There is nothing to argue about.

**2 — The reviewer tries to dismiss it.**
The dismissal is challenged: *"This is not a judgement call — the sentence is still
not in the stored label. Attach a source that contains it, or record a named
override."* The finding stays blocking. `can_publish` stays false.

> This is the moment. It is the only part of the demo where the software tells a
> senior clinician they are wrong, and it can do it because it is not offering an
> opinion.

**3 — The override path, shown honestly.**
Record the override. It is attributed, reasoned, in the audit trail, and stamped on
the published course. We do not block experts; we make the decision visible.

**4 — The rewrite path.**
Undo, and rewrite instead. The replacement text is re-checked live. It passes, the
comment closes, the version is cut — and the checks re-run across the whole course so
the delta is on screen.

**5 — Completeness.**
Open the coverage matrix. *"Use in specific populations — not covered."* Accept the
suggestion; that unit regenerates with citations.

**6 — The receipt.**
Back to Impact: expert review compressed from 10 days to 1.8, cost per certified
learner from $9,000 to $900, checker agreement 90%, coverage stated as-is.

---

## 8 · What we say, and what we do not

**We say:**
- Every claim is attached to a document, and we will show you the document.
- 5 of 7 publication-blocking findings needed no model at all.
- We caught an off-label indication claim before it reached a field team.
- Reviewers agreed with the machine checker 90% of the time.
- A reviewer cannot silently erase a provable defect.

**We do not say:**
- That the AI is accurate. That claim is unfalsifiable and every competitor makes it.
- That coverage is complete. It is 21%, we report it as 21%, and we show the path to
  raising it.
- That human review can be removed. The system exists to make expert review *fast*,
  not optional — that is where the 10 days to 1.8 days comes from, and it is the only
  part of the economics that actually matters.

---

## Build status

| | Capability | State |
|---|---|---|
| 4.1 | Dismissal re-check and challenge | to build |
| 4.2 | Rewrite re-check before version cut | to build |
| 4.3 | Attributed resolutions + audit trail | to build |
| 4.4 | Per-reviewer calibration | to build |
| 4.5 | Completeness coverage matrix | to build |
| 4.6 | Depth floor | to build |
| 5 | Registry fetch wired into the pipeline | fetcher exists, not wired |
| 6 | Comment-scoped evidence and sidecar | to build |
| 1 | Deterministic + model pre-review checks | **built** |
| 2 | Role-separated review, server-enforced | **built** |

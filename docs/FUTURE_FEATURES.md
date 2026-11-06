# Future features (parked, not built yet)

Batch 1 from the trainee-feature shortlist, deliberately deferred: it needs
pharmacist-grade rule tables, and those deserve a dedicated, carefully
reviewed pass — not to be rushed alongside the batch 2/3 UI work.

## Dosing calculator (Ibrance first, then per-drug)

**What:** the trainee enters a patient situation, the app returns the
label-correct answer with the citation that proves it.

**Rule tables (all values must come from the dossier, never hardcoded):**

- Standard regimen: 125 mg once daily, 21 days on / 7 off, 28-day cycle.
- Capsules with food; tablets with or without food.
- Reductions: 100 mg, then 75 mg step-downs for Grade 3/4 neutropenia and other
  severe toxicities, per the dose-modification table (label §2.2 / §5.1).
- Severe hepatic impairment (Child-Pugh C): 75 mg starting dose.
- Renal impairment of any severity with CrCl > 15 mL/min: no change.
- Missed/vomited dose: skip, do not double; next scheduled dose as normal.
- Strong CYP3A inhibitors: avoid; strong inducers: avoid (exposure changes
  both ways).

**Build notes:** derive every rule from dossier claims at runtime (same
pattern as the checker — quote-first, no invented numbers). Each answer shows
its citation chip. Wrong-input handling: unknown Child-Pugh class or CrCl
below range must refuse to answer, not guess.

**Validation:** pytest cases per rule against a fixture dossier; one live
click-through per rule; quote-verbatim check on every displayed value.

## Interaction checker (same batch)

**What:** pick a co-medication → severity-graded warning with plain-language
reason and the label section behind it.

**Minimum rule set (Ibrance):** strong CYP3A inhibitors (avoid), strong
inducers (avoid / loss of efficacy), sensitive CYP3A substrates (exposure
increase), grapefruit products (avoid). Severity grades: avoid / use-with-care
/ no action, each with its citation.

**Build notes:** same derivation rule as the calculator. Unknown drug →
"no recorded interaction," never a clean bill of health.

## Parked alongside

- **Eliquis as a second drug** (see plan: registry-driven gate, frozen
  `library/eliquis` base, keyed live generation). Blocked on: LLM key for the
  one live generation run, or a hand-built evidence base nobody should
  volunteer for without expertise.
- **Server-synced resume** (cross-device continue): needs progress sync
  endpoint + conflict rule; localStorage resume already ships.
- **MOA animation payloads**: the stepper UI (batch 2) plays storyboard
  scenes; true 3D animation needs commissioned media, not code.

## Perceived performance (observed: some clicks take seconds)

Measured symptom first, then fix in this order — biggest feel-per-effort first:

1. **Parallelise page loads.** Learn and course pages fire 3–4 `getJson`
   calls in sequence (course → objections → library). Move independent
   fetches into one `Promise.all` so the slowest call, not the sum, sets
   the wait. No backend change.
2. **Skeletons, not spinners.** Every tab and card that waits on data
   renders a shaped skeleton matching its final layout today (`Loading`
   exists but is a generic line). A skeleton that matches the layout
   removes the "did it break?" second entirely.
3. **Library documents are the heaviest payload.** Full label text ships
   on first open. Serve a character-capped first paint (e.g. 20k chars
   around the requested quote) with progressive fill, and cache the
   parsed text in memory per session so reopening is instant.
4. **Chat latency budget.** Retrieval + model is inherently slowest;
   stream the answer (SSE) instead of blocking on the full reply, and
   show cited partials as they arrive.
5. **Prefetch on intent.** Prefetch the next most-likely tab (Mechanism
   after storyboard, final after modules complete) on hover/focus, inside
   the existing `changeTab` flow — never prefetch everything.
6. **Measure before tuning further.** Add a lightweight client timing log
   (fetch durations per endpoint, painted into the existing synced-status
   line in dev only) so the next slow click names itself instead of
   needing a hunt.

# Session handoff — continue on any machine

HEAD: `1c880f6` on `main` (pushed to origin). Tree clean. Details of what
shipped live in [README.md](../README.md) ("What shipped") and
[ROADMAP.md](ROADMAP.md) (ingested vs rejected vs future).

## What this session decided

- All 18 meeting actions (A1–A18) were shortlisted into Phase 1 / Phase 2 /
  parked; Phase 1 is fully built, including the research ingest below.
- A deep-research workflow (6 angles, critic, gap follow-up, synthesis) fed
  the build. Ingested: 10 quick wins + medium bets. Rejected on evidence:
  faster-only narration, Bionic/RSVP readers, whole-label rebuilds, full AKT
  tracing, public peer boards. Large bets stay parked in ROADMAP.md.
- Two corrections landed after the first summary: typed-name attestation UI
  in review sign-off, and the opt-in peer board on the learner home.
  (The focus page needed no correction — it already showed the redesign.)

## Open threads (concrete next steps)

- Large bets in ROADMAP.md are unstarted: NLI model, xAPI, SSO/SCIM, neural
  narration, offline mobile, WCAG 2.2 AA, tagged PDF/UA, branching scenarios.
- Live wires, all opt-in/off by default: DailyMed/openFDA fetch, model
  adjudication (needs `ANTHROPIC_API_KEY`), email/SMS nudge delivery.
- Generation-side sentence-citation instruction is not in `src/prompts/`;
  scoring side (`sentence_f1`, faithfulness) is built.
- Frontend wiring noted complete: attested sign-off, nearby opt-in.

## Repo map (where features live)

- Learning/audit/gamification: `src/learning.py`; analytics: `src/analytics.py`,
  `src/fsrs.py`; checks: `src/judge.py`; coverage: `src/completeness.py`;
  evidence/registry/labels: `src/evidence_fetch.py`; builders:
  `src/present.py`; API: `api/main.py`.
- Learner home + peer board: `ui/web/src/app/learn/page.tsx`,
  `ui/web/src/components/peer-board.tsx`; review + attestation:
  `ui/web/src/components/course-review.tsx`; focus experiment:
  `ui/web/src/app/experiments/focus/page.tsx`.

## Verification gates (run before any handoff claim)

```bash
uv run pytest -q            # backend, expect 313 passed
cd ui/web && npm run lint   # clean
cd ui/web && npm run build  # success, /experiments/focus prerendered
```

## Conventions learned the hard way

- Many source files use CRLF: multi-line exact-match edits fail; use
  single-line anchors with `edit_file`, or line-index splicing scripts.
- Keep generated-code scripts ASCII- and backslash-free where possible:
  `chr(92)`/`chr(10)`, `[0-9]` instead of `\d`, `" ".join(s.split())`
  instead of `\s+`. When escapes matter, verify with numeric char dumps,
  never eyeballing.
- The project interpreter is 3.13 via `uv run python`; system Python is
  3.11 and rejects 3.12+ f-string syntax present in older code — always
  verify with the project interpreter.
- FastAPI matches routes in registration order: static paths
  (`/audit/exceptions`) must register before parameterized ones
  (`/audit/{user_id}`).
- New check kinds need `DETERMINISTIC_CHECKS`, a frontend label in
  `course-checks.tsx`, and tests; stats dicts assert per-key, so additive
  keys are safe.
- Throwaway probe scripts lived in machine-local `/tmp` (not in the repo);
  durable coverage lives in `tests/` per change.

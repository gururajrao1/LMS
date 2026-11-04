# PharmaLearn — Detailed Knowledge Transfer (KT)

Product: [PharmaLearn demo](https://github.com/gururajrao1/LMS) (“LMS” repo) is a local, file-backed
**pharma field-training LMS**. It generates citation-backed training for a drug (Ibrance),
runs it through automated + human review, publishes it to a cohort, and measures learning and ROI.

This KT covers: what it does, domain, personas, end-to-end flow, architecture, backend modules,
agent pipeline, storage, API, frontend, governance, accuracy model, prompts, sources, analytics,
testing, setup, limits, and where to read code.

## 1. What the app does (30 seconds)

- Input: a drug name (only `Ibrance`/`palbociclib` generates; Eliquis/Vyndaqel/Xeljanz are preview cards).
- Agent builds: 14 research sections → master dossier → 8 asset tracks (MSL/HCP × PPT, storyboard, FAQ, quiz)
  plus gamified formats (triage sort-board, assemble word-build, figure read-the-data), plus PPTX files.
- Checker pre-reviews every citable unit before humans see it; blocking findings auto-enter the review queue.
- Reviewers comment and sign off; admin addresses comments, cuts versions, publishes to a dated cohort.
- Learners (MSL/HCP) do baseline → 4 modules → final → certificate; admin sees cohort + impact analytics.
- Everything is inspectable JSON under `.pharmalearn/`; no database.

Start here: [README](https://github.com/gururajrao1/LMS/blob/main/README.md),
[implementation plan](https://github.com/gururajrao1/LMS/blob/main/docs/implementation_plan.md),
[user flows index](https://github.com/gururajrao1/LMS/blob/main/docs/user-flows/README.md).

## 2. Domain it contributes to

Life Sciences / Medical Affairs — field-medical enablement, not generic e-learning:

- Audience is expert: MSLs and HCPs in the same therapeutic area (oncology for Ibrance).
- Risk is regulatory: off-label wording, missing contraindications, promotional-only sourcing.
- Value claim: `1 month → days`, expert review time `-80%`, versioning/label updates in hours.
- Differentiator attempted: deterministic quote verification + dismissal-challenge (“AI checks the human”),
  coverage honestly reported (21%), approval never automated.

See: [accuracy design](https://github.com/gururajrao1/LMS/blob/main/docs/ACCURACY.md),
[where AI is used](https://github.com/gururajrao1/LMS/blob/main/docs/WHERE_AI_IS_USED.md),
[progress assessment](https://github.com/gururajrao1/LMS/blob/main/docs/PROGRESS.md).

## 3. Personas and separation of duties

| Persona | Role | Owns | Cannot do |
|---|---|---|---|
| Priya Raman | admin | generate, address, version, publish, monitor | approve own content |
| Anil Shekhar / Maria Alvarez | reviewer | comment, sign off | address own comments, cut version, publish, see cohort |
| Jordan Feld / Sara Nakamura | MSL | MSL track learning | see unassigned courses, review surfaces |
| Ken Osei / Lucy Whitfield / Tom Becker | HCP | HCP track learning | same as MSL |
| PharmaLearn checker | checker | raise machine findings | sign off (enforced) |

Auth is demo-only: pick a person on `/`, stored in `localStorage` (`pharmalearn.session`).
Maker-checker is API-enforced in [review logic](https://github.com/gururajrao1/LMS/blob/main/src/learning.py)
(`_author`, `add_signoff`, `publish_version`, `publish_course`), covered by
[learning tests](https://github.com/gururajrao1/LMS/blob/main/tests/test_learning.py).

## 4. The 5-minute demo loop

1. Admin → dashboard → Create content → `POST /api/runs {drug: Ibrance}` → run page streams SSE.
2. Checks tab: quote fidelity, traceability, promotional-only, comparative, overreach. Blocking auto-promoted.
3. Reviewer opens course, HCP/MSL toggle, Fact check tab (`POST .../chat`), raises blocking/major/minor comments.
4. Admin marks addressed with resolution, cuts v2 (addressed → closed, `closed_in_version` stamped).
5. Reviewer approves at v2. Readiness gate: approval at current version + no open blocking + no change requests.
6. Admin publishes: window + assignees + message → per-learner notifications (recorded, not emailed).
7. Learner: My training → baseline (5Q sample, server-scored) → 4 modules + ratings → final (gated, pass mark
   from `quiz.passing_score`, e.g. 67%) → certificate (version-stamped, valid 1 year, named approvers).
8. Admin: Cohort (assigned/started/certified, uplift, feedback) → Impact (time-to-field, funnel, score bands,
   hardest questions, module engagement, ROI vs manual assumptions).

Flows: [admin](https://github.com/gururajrao1/LMS/blob/main/docs/user-flows/admin.md),
[reviewer](https://github.com/gururajrao1/LMS/blob/main/docs/user-flows/reviewer.md),
[learner](https://github.com/gururajrao1/LMS/blob/main/docs/user-flows/learner.md).
Seeded demo: [seed script](https://github.com/gururajrao1/LMS/blob/main/scripts/seed_demo.py) walks a real course
through checker → 5 human comments → v2 → 2 sign-offs → 5-learner cohort.

## 5. Architecture

- Backend: [FastAPI entrypoint](https://github.com/gururajrao1/LMS/blob/main/api/main.py) (~889 lines).
  HTTP + SSE only. Endpoints grouped below. Background runs via `asyncio.create_task`.
- Frontend: [Next.js app](https://github.com/gururajrao1/LMS/tree/main/ui/web) (App Router, TS, Tailwind,
  shadcn-style components, Bun). Pages under `src/app`: `/`, `/dashboard`, `/courses/[runId]`,
  `/runs/[runId]`, `/learn`, `/learn/[runId]`, `/portfolio`, `/knowledge`.
- Python core in [src](https://github.com/gururajrao1/LMS/tree/main/src):
  `agent.py` (1458 lines, orchestration), `judge.py` (1126, checker),
  `learning.py` (839, review/learn state), `analytics.py` (486), `assistant.py` (384),
  `completeness.py` (177), `journey.py` (175), `programmes.py` (304).
- Storage: local JSON only. `.pharmalearn/content/<run-id>/`, `.pharmalearn/logs/<run-id>/`,
  `.pharmalearn/platform/` (roster, courses, progress), `.pharmalearn/library/ibrance/`,
  `.pharmalearn/uploads/`, `.pharmalearn/sources/`, `.pharmalearn/cache/`. Delete
  `.pharmalearn/platform/` to reset workflow state without deleting generated content.
- Prompts are config: [prompts](https://github.com/gururajrao1/LMS/tree/main/src/prompts)
  (`common/`, `research/01–14`, `formats/`, `learners/msl.md|hcp.md`). Hashes stored per run.
- Spend-capped Anthropic calls: `RunBudget`, per-run `usage.json`, cache reuse; PPT Skill opt-in only.

## 6. Agent pipeline (each run)

1. `resolve_drug` — dossier prep.
2. `research_01…14` — disease, product science, clinical evidence, label, safety, market,
   compliance, narrative, patient support, role considerations, current treatments, comparisons,
   unmet needs, MOA/onset/duration. Each returns claims + citations + gaps/warnings.
3. `build_master_dossier` — combines sections into `master/dossier.json`.
4. `generate_{msl,hcp}_{ppt,storyboard,faq,quiz,triage,assemble,figure}` — per-track assets.
5. `render_{msl,hcp}_pptx` — finished `.pptx` (local/cached deck by default).
6. `verify_citations` + `attach_citations` — deterministic checks per asset, manifest + compatibility view.
7. `complete` — manifest with `run_id`, `generated_at`, `cost_usd`, `content_url`.

Replay mode (`PHARMALEARN_REPLAY_SOURCE`) copies a finished run stage-by-stage with no model calls
(`mode: replay`, `cost_usd: 0`). Live mode needs `ANTHROPIC_API_KEY`; otherwise local Ibrance data.

Key functions: `create_run`, `run_agent`, `_research`, `_master_dossier`, `_asset`, `_pptx`,
`_verify_tracks`, `_replay`, `_link_or_copy` in
[agent orchestration](https://github.com/gururajrao1/LMS/blob/main/src/agent.py).

## 7. Storage layout (audit trail)

- Run events: `.pharmalearn/logs/<run-id>/events.jsonl`, `run.json` (status, mode, prompt hashes).
- Artifacts: `.pharmalearn/content/<run-id>/manifest.json`, `source_manifest.json`, `context.json`,
  `learning_blueprint.json`, `assets/`, `<track>/ppt|storyboard|faq.json|quiz.json|triage|assemble|figure`.
- Review: `.pharmalearn/platform/courses/<run-id>.json` (versions, comments, sign-offs, publication).
- Learning: `.pharmalearn/platform/progress/<run-id>/<user>.json` (modules, attempts, certificate, feedback).
- Roster: `.pharmalearn/platform/roster.json`. Uploads: `.pharmalearn/uploads/<ts>/`.

Inspect table is in [README](https://github.com/gururajrao1/LMS/blob/main/README.md) (“Inspect an agent run”).

## 8. API surface (grouped)

- Health/courses/runs: `GET /health`, `GET /api/courses`, `POST /api/runs`,
  `GET /api/runs/{id}`, `GET /api/runs/{id}/events` (SSE), `GET .../content`,
  `GET .../assets/{name}`, `GET .../downloads/{learner}/pptx`, `GET .../videos/...`.
- Review: `GET .../review`, `POST .../review/comments`, `PATCH .../review/comments/{cid}`,
  `POST .../review/comments/{cid}/repoint`, `GET .../review/comments/{cid}/evidence`,
  `POST .../review/versions`, `POST .../review/signoff`, `POST .../review/assign`,
  `POST .../publication`, `GET .../cohort`, `GET .../analytics`, `GET .../journey`.
- Checks/completeness: `GET|POST .../checks`, `POST .../checks/promote`,
  `GET .../completeness`, `POST .../completeness/promote`.
- Knowledge/chat/uploads: `GET .../knowledge`, `GET .../library`, `GET .../evidence`,
  `POST .../chat`, `GET .../chat/starters`, `GET|POST /api/uploads`, `POST /api/uploads/web`.
- Learning: `GET /api/learn/{user}`, `GET|POST /api/learn/{user}/{run}/...`,
  assessments `GET|POST .../assessment/{baseline|final}`, `GET .../certificate`, `POST .../feedback`.
- Programmes: `GET /api/clients`, `GET /api/clients/{id}`, `GET .../portfolio`,
  `POST .../archive`, `POST .../restore`.

Full list lives in [API entrypoint](https://github.com/gururajrao1/LMS/blob/main/api/main.py).

## 9. Frontend map

- `/` login (role-grouped roster, no passwords) → `/dashboard` (admin/reviewer) or `/learn` (MSL/HCP).
- `/dashboard`: course cards (review status, version, assignees), Create content modal, compact ROI headline.
- `/courses/[runId]`: HCP/MSL toggle; tabs PPTX, Videos, Storyboard, FAQ, Quiz (reviewer sees answers),
  Sources, Fact check, Review, Checks, Completeness, Cohort, Impact, Publish.
- `/runs/[runId]`: live stage stream (one row per agent stage + %).
- `/learn`: assigned courses, stage CTA, baseline→final uplift, days-remaining.
- `/learn/[runId]`: 4-step journey strip, module tabs, Ask tab, gated final, certificate page.
- `/portfolio`, `/knowledge` (Dossier/Sources/Add sources), course chat dock, evidence sidecar components.

See [web app](https://github.com/gururajrao1/LMS/tree/main/ui/web) and
[components](https://github.com/gururajrao1/LMS/tree/main/ui/web/src/components).

## 10. Governance that matters

- Readiness (`readiness()` in [review logic](https://github.com/gururajrao1/LMS/blob/main/src/learning.py)):
  approval at current version + zero open blocking + zero outstanding change requests.
- Dismissal challenge: deterministic findings re-run on dismiss; still-failing stays `open`
  (`challenged`), needs source attach or named `override_reason`. Model-only findings can be
  disagreed with and feed agreement stats.
- Rewrite re-check: `publish_version` runs `_verify_fixes` before closing addressed comments.
- Attribution: `resolve_comment` requires `user_id`; audit trail records who/when/what/check result.
- Certificates stamp version + named approvers + valid-through date; answers never leave
  `correct_index` in the browser; scoring is server-side.

## 11. Accuracy vs completeness

- Accuracy: quote fidelity (`quote_not_found`, `quote_not_verbatim`), traceability (`untraceable`),
  source quality (`promotional_only`, `comparative_claim`), model overreach
  (`unsupported`/`overreach`/`needs_context` + second-opinion confirm).
- Completeness: [oncology curriculum](https://github.com/gururajrao1/LMS/blob/main/config/curriculum/us_oncology.toml)
  × course units → coverage matrix; gaps promoted as major/blocking comments.
- Honest numbers: Ibrance course ~101 units, 188 citations, 186 traceable, 39 checkable, 21% coverage.
  5 of 7 blocking findings came from deterministic checks, not the model.

## 12. Testing, setup, operations

- Gates: `uv run pytest`, `bun run lint`, `bun run build` (see [README](https://github.com/gururajrao1/LMS/blob/main/README.md)).
- Suite: 162 pytest tests (`tests/test_agent|judge|learning|analytics|assistant|completeness|courses|library|programmes|replay|triage`).
- Local run: `cp .env.example .env`, `uv sync`, `uv run uvicorn api.main:app --reload` + `bun install; bun dev` in `ui/web`.
- Seed: `uv run python scripts/seed_demo.py` (`--status`, `--reseed`); cost reconcile and skill sync scripts in
  [scripts](https://github.com/gururajrao1/LMS/tree/main/scripts).
- Recent fix (pushed `e88831c`): Windows symlink fallback in `_link_or_copy`/`_own_track` +
  date-robust budget test; full suite green (was 6 failed in project env on Windows).

## 13. Known limits (do not demo as done)

Single-drug generation (Ibrance only); replay default; no real auth/SSO; no email sending;
no video renderer (storyboard contract only); JSON-file storage (no multi-tenant DB);
fetcher (`fetch_pfizer.py` + [source allowlist](https://github.com/gururajrao1/LMS/tree/main/config/sources))
exists but is not wired into citation resolution; coverage still thin on manufacturer-hosted sources.

Next highest-value builds: label-change diff + retraining, SCORM/xAPI export, client portfolio PDF,
comment-scoped evidence sidecar, spaced reinforcement, multilingual tracks, offline mobile.


# PharmaLearn implementation plan

## Goal

Build a local demo that accepts a Pfizer drug name, shows an auditable agent run, and serves four citation-backed training assets: PowerPoint, video storyboard, FAQ, and quiz.

The first complete path uses the local Ibrance datastore and does not require an Anthropic API key. When `ANTHROPIC_API_KEY` is present, the same workflow can invoke Claude without changing the frontend or artifact formats.

## Constraints

- Next.js App Router, TypeScript, Tailwind CSS, and selected shadcn-style components; Bun manages frontend packages.
- One minimal FastAPI application and one `src/agent.py`; uv manages Python.
- Local file storage under `.pharmalearn/`; no database, queue, or agent framework.
- Prompts under `src/prompts/` are the only content-tuning surface.
- Stable JSON artifact contracts keep prompt edits from breaking the UI.
- US regulatory scope for the demo.

## Repository shape

```text
api/
  main.py                 # HTTP and SSE only
ui/web/                   # Next.js App Router frontend
src/
  agent.py                # run orchestration and source adapters
  learning.py             # roster, review, publication, progress, certificates
  analytics.py            # completion funnel, question difficulty, ROI model
  judge.py                # automated pre-review: quote fidelity, traceability, overreach
  assistant.py            # citation-backed course chat over the dossier
  prompts/                # expert-editable prompt files
.pharmalearn/
  library/ibrance/        # inspected local drug data and asset inputs
  content/<run-id>/       # copied/generated run artifacts
  logs/<run-id>/          # event stream and run metadata
docs/
  implementation_plan.md
README.md
```

## User flow

1. Demo sign-in as a person with an Admin, Reviewer, MSL, or HCP role.
2. Admin opens the course library and chooses Ibrance.
3. `POST /api/runs` starts a background run.
4. The run page consumes `GET /api/runs/{id}/events` as server-sent events.
5. The agent records research, context, blueprint, generation, and citation steps.
6. A reviewer comments on the generated assets; the admin addresses comments and cuts a version.
7. An approving sign-off with no open blocking comments unlocks publication to a dated cohort.
8. Assigned learners take a baseline check, work the modules, pass a final assessment, and earn a certificate.
9. The admin monitors completion, baseline-to-final uplift, certificates, and content feedback.

## Minimal API

Content generation:

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Readiness check |
| `GET /api/courses` | Course cards with review status |
| `POST /api/runs` | Start a run for a drug |
| `GET /api/runs/{id}` | Run status and artifact manifest |
| `GET /api/runs/{id}/events` | SSE progress events |
| `GET /api/runs/{id}/content` | Learning-hub JSON |
| `GET /api/runs/{id}/assets/{name}` | Download an artifact such as PPTX |
| `GET /api/runs/{id}/knowledge` | Dossier sections, claims, gaps, sources |
| `POST /api/runs/{id}/chat` | Citation-backed answer from the run's dossier |

Review, publication, and learning:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/people`, `POST /api/session` | Demo roster and sign-in |
| `GET /api/runs/{id}/review` | Comments, versions, sign-offs, readiness |
| `POST /api/runs/{id}/review/comments` | Raise a review comment |
| `PATCH .../review/comments/{comment}` | Address, dismiss, or reopen |
| `POST /api/runs/{id}/review/versions` | Cut a version, closing addressed comments |
| `POST /api/runs/{id}/review/signoff` | Approve or request changes |
| `POST /api/runs/{id}/publication` | Publish to a dated cohort and notify |
| `GET /api/runs/{id}/cohort` | Progress, uplift, certificates, feedback |
| `GET /api/runs/{id}/analytics` | Funnel, score bands, question difficulty, activity, ROI |
| `GET /api/runs/{id}/evidence` | The supporting text behind a citation |
| `GET/POST /api/runs/{id}/checks` | Read or run the automated checks |
| `POST /api/runs/{id}/checks/promote` | Send selected findings to the reviewer |
| `GET /api/learn/{user}` | A learner's assigned courses |
| `GET /api/learn/{user}/{run}` | Course state, modules, progress |
| `POST /api/learn/{user}/{run}/modules` | Mark a module complete |
| `GET/POST .../assessment/{baseline\|final}` | Sit and submit an assessment |
| `GET .../certificate` | Issued certificate |
| `POST .../feedback` | Rate a module |
| `GET/POST /api/uploads`, `POST /api/uploads/web` | Stage documents and fetched pages |

## Review and learning state

A second storage root, `.pharmalearn/platform/`, holds everything that happens around the generated content. It follows the same rules as the run data: JSON files, no database, inspectable at every step.

```text
.pharmalearn/platform/
  roster.json                       # demo people and their roles
  courses/<run-id>.json             # version, status, comments, sign-offs, publication
  progress/<run-id>/<user>.json     # modules, attempts, certificate, feedback
```

Publication gates on `readiness`: at least one approving sign-off at the current version, no open blocking comments, and no outstanding change requests. Assessment answers are scored server-side and `correct_index` is never sent to a learner's browser.

## Agent stages

Each stage appends a JSON object to `.pharmalearn/logs/<run-id>/events.jsonl`. The stream is:

1. `resolve_drug` — prepare the dossier for the requested drug.
2. `research_01_disease_foundation` … `research_14_moa_onset_duration` — one stage per prompt in `src/prompts/research/`, each producing a section of summarized, cited claims.
3. `build_master_dossier` — combine the sections into `master/dossier.json`.
4. `generate_{msl,hcp}_{ppt,storyboard,faq,quiz}` — eight asset stages, two learner tracks by four formats.
5. `render_{msl,hcp}_pptx` — produce each track's `.pptx`.
6. `attach_citations` — build the source manifest and the compatibility view.
7. `complete` — write the manifest and open the course.

Missing citations are warnings in the demo, not publishing failures.

`learning_blueprint.json` currently carries the dossier title and the asset-role map; its `audiences` map is a stub on live runs. Track differentiation happens in the per-learner asset prompts (`src/prompts/learners/`), not in a generated objectives document.

## Source policy

**Implemented today:** live runs use Anthropic web search, bounded to `max_uses: 3` per research section and steered by the per-section instructions in `src/prompts/research/`, with a US country hint. Every claim still records its title, URL, locator, supporting text, and access date, and the source manifest is built from what was actually cited.

**Built but not yet wired into the agent:** the deterministic snapshot pipeline below exists as `scripts/fetch_pfizer.py` with the allowlist in `config/sources/pfizer_us.toml`, and has produced timestamped evidence snapshots under `.pharmalearn/sources/` for ibrance, eliquis, prevnar and vyndaqel. `src/agent.py` does not read them. Connecting the two is the main step from "cited" to "deterministically sourced", and is the reason the table is kept here.

| Source | Deterministic access | Use |
| --- | --- | --- |
| DailyMed | API v2 `/services/v2/spls.json?drug_name=...`; retrieve the selected SPL/XML/PDF by Set ID | Current US prescribing information |
| Drugs@FDA | Official product record/data files and linked approval documents | Approval history, FDA reviews, archived labels |
| FDA safety | Fixed FDA safety communication and labeling-change searches | Post-market warnings and changes |
| ClinicalTrials.gov | REST API v2 `/api/v2/studies?query.intr=...` and `/api/v2/studies/{nctId}` | Trial registry data and posted results |
| PubMed | NCBI E-utilities `esearch` followed by `efetch` | Pivotal publications and bounded recent evidence |
| Guidelines | Therapeutic-area domain allowlist | Current place in therapy |
| Government epidemiology | Therapeutic-area registry such as CDC, NIH, or SEER | Disease burden and risk populations |
| Pfizer | Official product and medical-information domains | Manufacturer context; never sole support for comparative claims |

The stop rule is coverage-based, not time-based: every required topic is either supported or recorded as not found. The source manifest stores URLs, access dates, queries, document versions, and selection reasons.

## Artifact contracts

```text
.pharmalearn/content/<run-id>/
  manifest.json
  source_manifest.json
  context.json
  learning_blueprint.json
  assets/
    deck_spec.json
    ibrance-training.pptx
    video_storyboard.json
    faq.json
    quiz.json
```

All assets use the same citation shape:

```json
{
  "source_id": "DM-IBRANCE-2026",
  "title": "IBRANCE Prescribing Information",
  "url": "https://dailymed.nlm.nih.gov/...",
  "locator": "Section 2.1",
  "supporting_text": "Recommended starting dose: 125 mg...",
  "accessed_at": "2026-07-14"
}
```

## Prompt-only customization

The agent reads prompt files on every run. In model-backed runs, experts may change medical depth, audience emphasis, educational strategy, tone, or asset instructions without rebuilding the application. Local-data runs remain reproducible while recording the same prompt hashes.

```text
src/prompts/
  common/          citations.md, master_dossier.md, research_rules.md
  research/        01_disease_foundation.md … 14_moa_onset_duration.md
  formats/         ppt.md, storyboard.md, faq.md, quiz.md
  learners/        msl.md, hcp.md
```

JSON schemas remain code-owned. Each run records prompt hashes for reproducibility.

## PowerPoint and video

- The default live path reuses a local/cached `.pptx`. Anthropic's PowerPoint Skill is an explicit opt-in with streaming, container reuse, no automatic retries, and separate spend/turn limits.
- The no-key presentation provider uses a real inspected `.pptx` so downloading works end to end.
- `video_storyboard.json` is the stable video contract. A future renderer consumes it and adds an optional MP4 path to `manifest.json`; the UI then switches from storyboard to video player without changing generation prompts.

## Verification

- Python: import checks and FastAPI endpoint tests against a temporary data directory.
- Frontend: TypeScript/lint and production build.
- Presentation: render every slide, inspect full-size previews, and run overflow checks.
- End to end: start both servers, create an Ibrance run, receive SSE completion, load content, submit quiz answers, and download a valid `.pptx`.

## Audit locations

| What to inspect | Location |
| --- | --- |
| Step-by-step events | `.pharmalearn/logs/<run-id>/events.jsonl` |
| Run status and prompt hashes | `.pharmalearn/logs/<run-id>/run.json` |
| Retrieved source inventory | `.pharmalearn/content/<run-id>/source_manifest.json` |
| Normalized medical claims | `.pharmalearn/content/<run-id>/context.json` |
| Learning design | `.pharmalearn/content/<run-id>/learning_blueprint.json` |
| Per-format inputs and outputs | `.pharmalearn/content/<run-id>/assets/` |
| Expert-editable behavior | `src/prompts/` |
| Orchestration code | `src/agent.py` |

## Delivery order

1. Populate and validate the local Ibrance datastore.
2. Implement the standard local-data agent path and FastAPI endpoints.
3. Build the four Stitch-aligned Next.js routes.
4. Verify the complete offline run and PPTX download.
5. Document setup, prompt editing, `.env`, source adapters, and audit workflow.

## References

- [Next.js App Router installation](https://nextjs.org/docs/app/getting-started/installation)
- [Next.js App Router](https://nextjs.org/docs/app)
- [DailyMed API v2](https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm)
- [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/about-api)
- [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25500/)
- [Anthropic PowerPoint skill](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/quickstart)

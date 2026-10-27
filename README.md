# PharmaLearn demo

Local demo for turning authoritative drug information into four citation-backed training assets — PPTX, video storyboard, FAQ, and quiz — then reviewing, publishing, and teaching them to a field cohort.

Potential Demo Drugs: 

1. Ibrance
2. Eliquis
3. Vyndaqel
4. Prevnar

## Run locally

Requirements: Python 3.13+, [uv](https://docs.astral.sh/uv/), [Bun](https://bun.sh/), and Node.js 20.9+.

```bash
cp .env.example .env
uv sync
uv run uvicorn api.main:app --reload
```

In a second terminal:

```bash
cd ui/web
bun install
bun dev
```

Open `http://localhost:3000`. Pick a role and a person from the demo roster to sign in. An API key is not needed for this local-data end-to-end path.

## Pre-populate the demo

```bash
uv run python scripts/seed_demo.py
```

Takes the newest generated course and walks it through the real workflow: the automated checker runs first and its blocking findings are raised into the review queue, the experts accept or dismiss them (producing a real agreement rate), two domain experts then raise five comments of their own, the medical education lead addresses them and cuts v2, both experts sign off, it is published to five trainees, and the cohort works through it at different speeds — three certified (one after a failed first attempt), one waiting on the final, one mid-module. Every write goes through the same functions the API uses, and timestamps are placed on a realistic schedule so the analytics and ROI figures mean something.

It refuses to touch a course that already has review history. `--status` shows what is seeded; `--reseed` archives the current demo state under `.pharmalearn/platform/archive/` and rebuilds it. Nothing is ever deleted.

## Walking the whole demo

The app has two halves: an authoring side for Admin and Reviewer, and a learning side for MSL and HCP. A full loop takes about five minutes.

1. **Admin — Priya Raman.** Create content for **Ibrance**, or open the course that already exists. The run page streams each agent stage.
2. **Admin — Checks.** The automated checker has already run: it verifies each recorded quote against the stored source document, traces every citation back to a collected claim, and asks a model whether the text says more than its evidence supports. Blocking findings are raised into the review queue automatically; the lead sends selected others.
3. **Reviewer — Dr. Anil Shekhar.** Open **Review**. The queue arrives pre-triaged, machine findings marked *automated*. Accept or dismiss them — that ratio becomes the **reviewer agreement** rate on the Checks tab. Then raise your own comments; a *blocking* one holds publication.
4. **Admin.** Mark the comment addressed with a resolution, cut **version 2** (addressed comments close into it), and check **Fact check** to test a claim against the dossier.
5. **Reviewer.** Approve the sign-off for v2. The course becomes publishable only with an approval, no open blocking comments, and no outstanding change requests.
6. **Admin — Publish.** Set the window, pick trainees, and publish. Each assignee gets a recorded notification.
7. **HCP — Dr. Ken Osei** (or an MSL). The course appears under **My training**: baseline check → four modules with progress and per-module ratings → final assessment (server-scored, answers never sent to the browser) → certificate.
8. **Admin — Cohort.** Per-learner progress, baseline → final scores, average knowledge uplift, certificates, and the feedback learners left.
9. **Admin — Impact.** Time to field against the manual baseline, the completion funnel, score distribution, activity since publication, and the questions the cohort actually got wrong — the signal for what to fix in the next version.

Click any citation chip on a slide, FAQ answer or quiz rationale to open the evidence behind it: the verbatim text from the source, the claim it supports, the research section it came from, and the other claims resting on the same source.

The **Knowledge hub** browses every collected claim with its citation, and stages uploaded documents or fetched URLs for the medical team.

Demo roles: Admin (create, address comments, version, publish, monitor), Reviewer (comment, sign off), MSL and HCP (learn). Platform state lives in `.pharmalearn/platform/` as JSON, so any step can be inspected or reset by deleting that folder.

## Optional Anthropic key

Add `ANTHROPIC_API_KEY` to `.env` to run section-specific web research and generate MSL/HCP assets. Live runs default to an $8 guard, count input tokens before each request, disable automatic SDK retries, and record every attempt in `.pharmalearn/logs/<run-id>/usage.json` before it is sent.

Successful live stages are reused across later runs from `.pharmalearn/cache/`; each research section and asset is also saved immediately in its run folder. PowerPoints use the local/cached Ibrance decks by default. Set `PHARMALEARN_PPT_PROVIDER=anthropic` only when you explicitly want a billable PowerPoint Skill run; that stage has its own spend and continuation limits.

Before the first live run, upload or refresh the learner-specific PowerPoint Skill:

```bash
uv run python scripts/sync_anthropic_skill.py
```

Only run that upload when Anthropic PowerPoint generation is enabled. To reconcile the authoritative Anthropic dashboard export with local logs:

```bash
uv run python scripts/reconcile_anthropic_costs.py /path/to/anthropic-costs.csv
```

If old run logs were intentionally removed, pass the last captured figure with `--local-total`.

Without a key, the same agent path reads the prepared inputs in `.pharmalearn/library/ibrance/`.

## The two intended editing surfaces

1. Edit `src/prompts/*.md` to tune medical depth, teaching strategy, tone, or individual asset instructions on model-backed runs. Prompt hashes are stored with every run; local-data outputs remain intentionally reproducible.
2. Later, connect a video renderer to `assets/video_storyboard.json`; its stable scene contract avoids changes to the rest of the app.

## Inspect an agent run

After creating content, copy the run ID from the browser URL.

| Inspect | Path |
| --- | --- |
| Every agent event | `.pharmalearn/logs/<run-id>/events.jsonl` |
| Status, mode, prompt hashes | `.pharmalearn/logs/<run-id>/run.json` |
| Source inventory and exact queries | `.pharmalearn/content/<run-id>/source_manifest.json` |
| Normalized medical claims | `.pharmalearn/content/<run-id>/context.json` |
| Learning objectives | `.pharmalearn/content/<run-id>/learning_blueprint.json` |
| PPTX, storyboard, FAQ, quiz | `.pharmalearn/content/<run-id>/assets/` |
| Review, versions, sign-offs, schedule | `.pharmalearn/platform/courses/<run-id>.json` |
| A learner's progress, attempts, certificate | `.pharmalearn/platform/progress/<run-id>/<user>.json` |
| Demo roster | `.pharmalearn/platform/roster.json` |
| Staged uploads and fetched pages | `.pharmalearn/uploads/` |
| Automated check report | `.pharmalearn/platform/checks/<run-id>.json` |

The local Ibrance datastore is `.pharmalearn/library/ibrance/`. The agent does not copy a finished run: each standard stage writes its own source, context, blueprint, or asset file into `.pharmalearn/content/<run-id>/`.

The prepared no-key dataset uses a fixed source inventory. Live runs use the section-specific source instructions in `src/prompts/research/` with Anthropic web search.

To create a timestamped Ibrance evidence snapshot under `.pharmalearn/sources/ibrance/`:

```bash
uv run python scripts/fetch_pfizer.py --drug ibrance
```

The allowlist and audit instructions are in `config/sources/`. Inspect `latest.json`, then the selected snapshot's `snapshot.json` and per-source `manifest.json` files.

## Useful checks

```bash
uv run pytest
cd ui/web && bun run lint && bun run build
```

The implementation rationale and source policy are in `docs/implementation_plan.md`.

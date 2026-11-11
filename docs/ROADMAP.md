# PharmaLearn improvement roadmap — literature review ingest

Source: deep-research workflow over journals, papers, paperswithcode SOTA, and
existing apps (Veeva Vault Training, Cornerstone, Docebo, TalentLMS, Absorb,
Moodle, Articulate). Status as of this file: what is **ingested** (shipped with
tests), what was **rejected** on evidence, and what stays **future**.

## Ingested — quick wins (small effort, shipped with tests)

- Reinforce feedback with rationale (`reinforce_feedback`, POST
  `/reinforce/submit`): correctness plus rationale per item after the attempt.
  Butler & Roediger.
- Narration rate control and clause chunking (`build_narration` wpm /
  chunk_chars, `NarrationRequest`): default 140wpm, adjustable 80-300, never
  faster-only. Speech-rate literature.
- Focus reader redesigned to sequential disclosure with reread view
  (`focus-reader.tsx`, `/experiments/focus`): supersedes the blur prototype.
  Snell 2024, Benedetto 2015.
- Per-asset faithfulness (`judge.faithfulness`, GET `/faithfulness`):
  supported cited sentences over cited ones, plus per-asset split.
- Abstract-only cap (`abstract_only` major finding, never verified) and
  heuristic paraphrase screen (`entails`) beside `quote_match`.
- Registry-held citations resolve as conditional support (`registry_only`),
  never verified, never untraceable-conflated.
- Uplift-weighted points, growth and first-try badges, single-day streak
  freeze, implementation-intention nudges (EN reviewed, ES reviewed).
- Review-by-exception (`/audit/exceptions`), hash-chained audit plus
  `/audit/verify`, typed-name attestation on sign-off (meaning recorded).
- Certificate verification lookup with revocation on answers reset.
- Dual-control retention disposition executing raw-answer anonymization.
- Nearby rank, opt-in only, neighbors anonymized.
- Recertification nudges for certificates predating the published version.
- BKT-lite per-skill mastery with next-review timing (`/skills`).
- FSRS-lite scheduling ordering reinforce practice (`fsrs.py`).
- At-risk triage with reasons (`/at-risk`); per-skill gaps (`/skills-gap`).
- Phillips L1-L4 levels mapped onto already-measured numbers in ROI.
- PPTX alt text plus run language; PDF document language plus bookmark
  outline; CSV roster import step toward AD.
- SPL section splitter plus label diff (`label_sections`,
  `diff_label_sections`); token-recall completeness matching; ACCURACY.md
  Sec 8 reconciled with the built code.
- Model adjudication for margin short answers with keyless human-routing
  fallback (`adjudicate_free_text`).

## Ingested — medium bets (shipped, honest scope notes)

- Sentence-level citation scoring via `sentence_f1` plus faithfulness, with
  the cite-every-sentence instruction in `src/prompts/common/citations.md`
  (pinned by `tests/test_prompts.py`).
- Registry fetch wired into citation resolution; live DailyMed/openFDA fetch
  stays opt-in (network off by default).
- Label-change recertification via section diffs plus reminders; Veeva-style
  fully automatic retraining triggers are not wired to publication.
- Part 11 step: identity, meaning, timestamp on sign-off; password
  re-authentication and closed-system controls are future work.
- Hash-chained audit with verify endpoint; external timestamping is future.
- Verifiable certificates with lookup and revocation; signed PDF rendering
  is future.
- Auto-escalation context surfaced in reminders; scheduled auto-nudge
  delivery (email/SMS) is future — nudges are drafts, nothing is mailed.
- BKT-lite now; SAKT/AKT graduate in only with real data volume.
- At-risk heuristic, not a fitted model; calibrated only by inspection.

## Explicitly rejected on evidence

- Faster-only narration and Bionic/RSVP-style occlusion readers:
  comprehension harm, so the opposite fixes shipped instead.
- Whole-label rebuilds on label change: section-level diffs plus targeted
  recertification instead.
- Full deep knowledge tracing by default: small cohorts rule out deep
  models; BKT-lite now, AKT later.
- Public peer leaderboard for regulated completions: admin-only totals plus
  opt-in nearby ranks instead.

## Future — large bets (not built)

- NLI entailment model beside `quote_match` (BEVERS/FEVER style).
- Embedding-based completeness over token recall.
- cmi5/xAPI alongside SCORM 1.2.
- SSO (SAML/OIDC) plus SCIM lifecycle beyond CSV roster import.
- Multilingual neural narration (YourTTS/VALL-E class) with human-reviewed
  translation pipeline beyond the two reviewed templates.
- Offline-first mobile packs (Moodle-app model).
- Full WCAG 2.2 AA pass and tagged PDF/UA output.
- Branching-scenario authoring, isolation-of-impact L4 and monetised L5 ROI.
- Sequential recommendations (popularity now; SASRec/BERT4Rec later).

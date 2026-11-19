# Future learning workflow — AI enrichment + company-wide rollout

**Read this first (manager, 2 minutes).** Two proposals. First, a repeatable
AI pipeline so every new topic becomes a full course the same way the patient
recruitment course did: material in, researched draft out, Shashi validates,
publish. Second, the ordered suggestion list for taking the app company-wide
after the pilot. Neither changes anything training today; both are build
queues with owners and gates.

## Part A — AI topic-enrichment workflow (future)

**Goal:** any approved topic (a deck, a label change, a new drug) becomes a
complete, checkable course without hand-authoring every question.

**Stages, each with a named owner and gate:**

1. **Ingest.** Admin uploads the deck or PDF. The system extracts slides/sections
   and registers the file as the programme source. Owner: training ops. Gate:
   source file stored and listed.
2. **Research.** A model pass gathers supporting evidence: registry labels,
   literature (as with the recruitment survey — meta-analyses over vendor
   claims), and internal dossiers. Every fact keeps its source. Owner: AI
   pipeline. Gate: every drafted claim traceable to a stored source.
3. **Draft.** The model writes FAQ items, quiz questions with rationales,
   deck slides, storyboard scenes, and escalation notes, in the exact JSON
   shapes the app already serves. Owner: AI pipeline. Gate: schema-valid
   content, pass mark defaulting to the 70% baseline.
4. **Verify.** The existing checker runs over the draft: citations resolve
   against stored sources, sentence-level faithfulness scored, unsupported
   numbers flagged as deck-vendor figures. Owner: automated checker. Gate:
   zero blocking findings or recorded overrides.
5. **Validate.** Shashi (or the topic expert) takes the quiz, corrects
   answers, and signs off — the same loop he offered for the recruitment
   course. Owner: topic expert. Gate: human approval on the record.
6. **Publish.** Assign to groups, set the window, notify. Owner: training
   lead. Gate: the existing review readiness check.

**Guardrails that never relax:** quote-first (no invented numbers, ever);
model output is a draft until human sign-off; every version keeps its audit
trail; certificates only ever reflect passed, human-approved content.

**Ways to make trainees learn better (queued behind the pipeline):**
peer-reviewed written assignments with reviewer rubrics; Ask-bot depth
metrics so fast answers can't masquerade as understanding; decay-aware
spaced re-quizzing with delayed retention measured at a fixed interval;
single-voice narration per course; interaction mining that turns the
hardest-missed questions into next version's fix list.

## Part B — company-wide suggestions (after the pilot)

Ordered by dependency, not enthusiasm. Each item names its unblocker.

1. **Load the real roster** (unblocker: HR export). Full employee list with
   roles, plus a manager against each name for lockout emails.
2. **Create the groups Shashi named** (unblocker: roster). Tech,
   management, senior leadership, genomic and clinical-trial teams; courses
   assigned to groups from here on.
3. **Bless the rules org-wide** (unblocker: Shashi). 70% everywhere, 3
   attempts with warnings and lockout, approver-only overdue extensions.
4. **SSO login** (unblocker: IT). Retire the demo picker; leavers lose
   access automatically.
5. **Email reminders** (unblocker: mail provider + compliance sign-off).
   Due, overdue, and manager notices; SMS later only if field teams need it.
6. **One-team pilot, then expand** (unblocker: Shashi names the team). Two
   weeks on the dashboard, fix what surfaces, then open wider.
7. **Support rota** (unblocker: staffing). Named humans for locked learners
   and trainee questions; officially supported browsers and phones.
8. **Audit rehearsal** (unblocker: two weeks of real data). Run one export
   pack end to end before inviting scrutiny.
9. **Content calendar** (unblocker: programme team). Which topic becomes a
   course each month, who validates it, and recertification triggers on
   label changes.
10. **Metrics review cadence** (unblocker: KPI draft, now decided). Monthly
    read of attempts, uplift, stuck signals, and retention with the fixes
    fed back into content via the Part A pipeline.

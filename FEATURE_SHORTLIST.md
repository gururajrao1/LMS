# Feature Shortlist for the LMS — every candidate, its actual use case

Scope: additive only. Nothing here removes an existing panel or flow.
Statuses: HAVE (shipped), PARTIAL (exists, needs extension), NEW (to build).
Everything built across the demo batches is listed under Shipped at the
bottom — built, verified, and removed from the to-add list.

## Pharma compliance (Veeva Vault Training, 21 CFR Part 11)

Sources: [Veeva Training brief](https://www.veeva.com/resources/veeva-training-solutions-brief/),
[pharma LMS guide](https://360learning.com/blog/lms-pharma/),
[Part 11 LMS guide](https://www.gyrus.com/blogs/21-cfr-part-11-compliant-lms/).

- **SOP-linked auto re-training** (PARTIAL — manual refresh diff endpoint exists).
  Adds: a new assignment the moment a controlled document or label changes.
  Actual use case: the Ibrance label gains a warning; Priya cuts v3 and every
  certified HCP is automatically re-enrolled instead of her chasing spreadsheets.
- **Role-based qualifications** (PARTIAL — custom roles with capabilities, per-trainee assignment, stage tracking and dashboards shipped; required-training mapping per role still open).
  Adds: required training mapped per role, readiness shown per person.
  Actual use case: Priya opens Cohort and sees Dr. Osei is qualified on v2 while
  Dr. Becker still owes the final, with no manual cross-checking.
- **Part 11 e-signatures** (NEW).
  Adds: unique verifiable signatures tied to login on completions and sign-offs.
  Actual use case: an FDA auditor asks who approved v2 — the sign-off carries
  Anil's identity, timestamp, and meaning, instead of a plain name field.
- **Full computer-generated audit trails** (PARTIAL — review audit exists).
  Adds: timestamped log of every enrollment, attempt, completion, signature.
  Actual use case: the export pack answers "who did what, when" without anyone
  assembling records by hand.
- **Pre-validated posture** (NEW, docs-heavy).
  Adds: documented validation that the LMS meets Part 11.
  Actual use case: Pfizer security review passes in days because the validation
  pack already exists.

## Enterprise (Cornerstone, Docebo)

- **Skills-gap mapping from hardest questions** (NEW).
  Adds: missed-question data rolled up into skill gaps per cohort.
  Actual use case: Impact shows "dose modification questions fail 60% of the
  time" so the next version fixes the material, not the learners.
- **Re-enrollment automation** (NEW).
  Adds: expiring certificates auto re-assign the current version.
  Actual use case: a certificate lapses after a year and the learner is
  re-enrolled automatically; Priya never runs the expiry spreadsheet.
- **Recommended-next rail** (SHIPPED).
  Adds: the single most urgent course surfaced on the learner home page.
  Actual use case: Jordan opens Learn and sees "Ibrance final due in 3 days"
  instead of scanning four section lists.
- **Branded multi-audience portals** (NEW).
  Adds: separate spaces per client or team under one system.
  Actual use case: a second pharma client onboards without ever seeing
  Pfizer's courses or cohorts.
- **HRIS, CRM, SSO integrations** (NEW).
  Adds: identity, org data, and field activity flowing in and out.
  Actual use case: SSO first (no more demo roster), then HRIS so leavers lose
  access automatically; CRM later to link training to field activity.
- **AI translations plus video transcripts** (NEW).
  Adds: every video and module readable in each market language, transcripts
  searchable.
  Actual use case: a Spanish-speaking HCP cohort trains on the same v2 content
  without a separate manual translation project.
- **Scheduled auto reports** (NEW).
  Adds: the cohort report emailed daily, weekly, or monthly.
  Actual use case: the medical-education lead gets Monday's completion numbers
  without opening the app.
- **Content marketplace** (SKIP).
  Adds: buying ready-made courses. No use here — our content is generated
  in-house from the dossier.

## SMB and open source (TalentLMS, Absorb, Moodle Workplace)

* **Branches and multi-tenancy** (NEW).
  Adds: isolated portals per client or division with own branding and roles.
  Actual use case: same as branded portals above; Moodle proves the model
  works for compliance training at scale.
* **Points and levels** (SHIPPED — points only; levels and unlock sequences stay out).
  Adds: 25 points per finished module plus the final score, shown on the
  learner page.
  Actual use case: Tom sees points grow as he works through modules, which
  keeps momentum up without a public leaderboard that would feel wrong for a
  regulated audience. Unlock sequences stay out for now.
* **Dynamic rules engine** (NEW).
  Adds: if-this-then-that automation for enrollments and paths.
  Actual use case: "when v3 publishes, re-enroll everyone certified on v2"
  runs as a rule instead of a manual publish-plus-chase cycle.
* **Org hierarchies with manager rollups** (NEW).
  Adds: team-level progress views above the per-learner table.
  Actual use case: a regional manager sees her ten HCPs' completion in one
  row instead of reading the whole cohort table.
* **AI admin helper** (NEW).
  Adds: draft publish messages and summarize open review comments.
  Actual use case: Priya clicks once to draft the assignment message that
  goes out with publication.
* **Offline mode plus transcripts** (PARTIAL — storyboard exists, no offline).
  Adds: downloadable modules and video transcripts.
  Actual use case: an MSL with no signal in a rural territory still finishes
  the deck on a tablet.

## Creator (Learnyst)

Sources: [product page](https://www.learnyst.com/products/sell-online-courses),
[platform FAQ](https://support.learnyst.com/learnyst-platform-faqs).

* **White-label per client** (NEW).
  Adds: client brand on web and (later) mobile.
  Actual use case: Pfizer opens training and sees Pfizer, which is what
  enterprise buyers expect before rollout.
* **Single login across web and mobile** (NEW).
  Adds: one identity everywhere.
  Actual use case: required groundwork before offline mobile ships.
* **Bundles** (PARTIAL — portfolio groups programmes).
  Adds: multi-drug programmes tracked as one package.
  Actual use case: "Q3 oncology readiness" bundles Ibrance plus the next drug
  with one completion number for the client.
* **Email and SMS automation** (NEW).
  Adds: assignment, reminder, and due-date messages.
  Actual use case: Sara gets "final due in 3 days" without Priya sending it.
* **Referral wallet** (PARK).
  Adds: learners earning credits for inviting others. No use while we
  contract with pharma clients rather than selling to learners.
* **Gateways, EMIs, coupons** (SKIP — same reason).

## Authoring (Articulate 360)

Sources: [Stratbeans guide](https://stratbeans.com/is-articulate-360-an-lms),
[Teachfloor](https://www.teachfloor.com/elearning-glossary/storyline-360).

* **SCORM, xAPI, cmi5, AICC import** (PARTIAL — SCORM export exists, import missing).
  Adds: Storyline and Rise packages upload and play inside our review loop.
  Actual use case: a client brings legacy compliance modules into our
  analytics and recertification flow instead of running two systems.
* **Branching scenarios** (PARTIAL — triage and storyboard cover the simple end).
  Adds: full decision-tree cases. Actual use case: "an unsolicited off-label
  question arrives — what do you do?" as a scored scenario for MSLs.
* **WCAG 2.1 plus translations baseline** (NEW).
  Adds: accessible, multilingual playback. Actual use case: same build as
  the Docebo translations item; one implementation serves both.
* **Do not clone Storyline** (DECISION).
  Integrate and import first; a Rise-like block editor comes only after
  import works.

## Shipped (built and demo-visible — no longer to be added)

1. Cohort export buttons — CSV plus SCORM download on the Cohort tab.
   Use: Priya hands compliance a file instead of screenshots.
2. Refresh diff panel — compare two label versions, list added, removed,
   and changed questions with a re-certification flag.
   Use: the label-change conversation happens on screen, not in email.
3. Missed-questions practice — learner section built from the reinforce
   endpoint, no answer key shown.
   Use: Tom practices exactly what he missed before retaking the final.
4. Points plus badge — server-computed points shown on the learner page.
   Use: visible momentum for the learner, honest numbers for the admin.
5. Recommended-next rail — most urgent course surfaced on the learner home.
   Use: nobody wonders what to do today.
6. Voice read-aloud — every assessment question plus a full read-through,
   via speech synthesis on the test page.
   Use: field trainers who absorb better by listening, and accessibility.
7. Q&A extraction plus quiz builder — deterministic pairs pulled from staged
   material, turned into scored multiple-choice practice.
   Use: a congress deck becomes a real knowledge check in one click, with
   nothing invented.
8. Scheduled training frequencies — once, quarterly, semiannual, annual —
   with next-due dates stamped at publish.
   Use: annual requalification runs itself instead of living in a spreadsheet.
9. Noncompliance alerts with RAG tiers — overdue, below-requirement and
   unbaselined flags, red/amber with labels, shared by the panel and exports.
   Use: Priya sees who needs action before the auditor asks.
10. Group and individual assignment — publish to trainees by MSL/HCP group
    or person, with start and due dates.
    Use: the right people get the course on the right date, no side lists.
11. Admin answer reset — clear attempts and certificates while keeping
    module progress.
    Use: a failed final restarts cleanly without redoing the whole course.
12. Excel export — Cohort, Questions, Noncompliance and Feedback sheets.
    Use: the compliance pack is a spreadsheet, not screenshots.
13. Individual learner dashboards — per-person page with courses, points,
    RAG state and alerts.
    Use: a manager checks one learner without reading the whole cohort.
14. Training slides export — pasted present text becomes a real .pptx deck.
    Use: the same material trains a room without rebuilding slides.
15. Certificate designs — Classic, Modern and Formal templates picked at
    publish time and stamped on every certificate.
    Use: the wall piece fits the audience, from field team to audit file.
16. Custom roles and permissions — capability catalog, role builder, per
    person assignment, enforced on every gated action.
    Use: an Instructor reviews and publishes without touching the roster;
    maker-checker (admin never signs off) still holds.
17. Escalation ladder — noncompliance tiers become owned L1/L2/L3 levels
    with first-seen dates, level-change history and an attributed check run.
    Use: a two-week overdue flag reaches the training lead on its own.
18. Retention report — per-course inventory of attempts, certificates,
    feedback, review trail, notices and uploads against keep-until policy.
    Use: the team sees what is due for review; nothing is deleted by the app.
19. Version timeline — versions, sign-offs, assignments and publications on
    one ladder, oldest first.
    Use: a reviewer sees how v1 became the published v3 in one glance.

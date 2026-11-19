# Office-wide rollout checklist — what works, what's next, what it costs, what's broken

**Read this first (manager, 2 minutes).** The LMS trains people end to end
today: courses, quizzes, certificates, dashboards. Verified this week:
**347 backend tests pass, 9 frontend tests pass, typecheck clean.** Two
things block company-wide rollout: anyone can sign in as anyone (no real
login), and there is no backup of the training data. Cheapest workable AWS
setup is **about $24–28/month**; the safer standard setup is $80–200+/month.
Everything below is checked off, priced, or assigned a fix.

## 1. Already integrated (verified in the repo)

| Area | What exists |
|---|---|
| People | Roles, capabilities, custom roles, learner groups, roster import |
| Courses | Draft → review → sign-off → publish, 9 content courses, 2 tracks |
| Assessments | Baseline + final, 3-attempt cap, admin reset, daily practice |
| Certificates | Version-stamped, verifiable, revokable, 3 templates |
| Oversight | Cohort, noncompliance tiers, escalation ladder, reminders (EN/ES) |
| Motivation | 9 badges, uplift points, streaks, opt-in boards, voices |
| Authoring | Upload → Q&A → quiz builder, knowledge hub, narration builder |
| Proof | 347 backend + 9 frontend tests green, audit chain, exports |

## 2. Future phases for the office-wide program

1. **Harden blockers.** Real login (Cognito/SSO) + Postgres with backups and
   a tested restore. Nothing rolls out before this.
2. **Comms + data rules.** SES email sending, manager column backfilled,
   attempt cap pinned per published version.
3. **Quality gates.** Component tests, accessibility fixes, mobile reflow.
4. **Infra cutover.** EC2 + RDS + S3/CloudFront + Route 53 + CloudWatch.
5. **Operate.** Publish courses, watch cohorts and escalations, review
   analytics monthly.

## 3. Tech needed per phase

- Phase 0: Cognito user pool + SSO, server-issued tokens on every route,
  Postgres on RDS Single-AZ with automated backups + point-in-time
  recovery, snapshot/restore endpoint and drill.
- Phase 1: SES identities and send path with bounce handling, roster
  manager column (import/HRIS), version-pinned attempt caps.
- Phase 2: Vitest component/route tests, axe checks, responsive reflow.
- Phase 3: Single t4g.micro EC2 + EBS, S3 + CloudFront, Route 53,
  7–14 day CloudWatch retention.

## 4. Cheapest workable costing (us-east-1, verify on the calculator)

| Piece | Cheapest pick | $/mo |
|---|---|---|
| Database | RDS db.t4g.micro + 20 GB gp3 | ~$14 |
| Compute | Single EC2 t4g.micro + EBS | ~$8 |
| Files + CDN | S3 + CloudFront free tier | ~$0 |
| Email | SES, ~5k mails | ~$0.5 |
| Login | Cognito, under 10k users | $0 |
| DNS + logs | Route 53 + CloudWatch short retention | ~$2 |
| **Total** | Single-AZ, no autoscaling | **~$24–28** |

Sacrifices vs the $80–200 standard: no failover, burstable-only speed,
short logs. Watch-outs: possible ~$3.65/mo public IPv4 charge, and SES
needs production access granted. Sources: RDS, EC2, S3, SES, and Cognito
figures corroborated via 2026 pricing guides; re-check before committing.

## 5. Major gaps found by testing everything

| Gap | Severity |
|---|---|
| Sign-in is pick-a-name with no password; any caller can impersonate anyone | BLOCKS rollout |
| No backup or restore for the training data store | BLOCKS rollout |
| No email sending; all reminders stay in-app | Should fix |
| Attempt-cap changes apply retroactively to in-flight learners | Should fix |
| Manager unset by default, so lockout routing degrades to generic text | Should fix |
| Only 9 frontend assertions, no component/route/accessibility tests | Should fix |
| Wide tables scroll sideways on mobile, no device tests | Nice to have |
| Login lacks radio semantics, no skip link or live regions | Nice to have |

## 6. How each gap gets solved

1. **Auth:** Cognito/SSO login, delete guest auto-create and client-chosen
   roles, server-issued tokens on every route.
2. **Backup:** Postgres with automated backups + point-in-time recovery,
   plus a snapshot/restore endpoint and a tested runbook.
3. **Email:** SES send path for publish, due, overdue, and manager
   reminders with bounce handling and receipts.
4. **Cap retroactivity:** pin the attempt cap to the published version and
   grandfather in-flight learners; add a cap-change-mid-course test.
5. **Managers:** mandatory manager column in roster import/HRIS sync, and
   backfill managers before lockout routing goes live.
6. **Frontend tests:** component and route coverage plus automated
   accessibility checks in the gates.
7. **Mobile:** reflow cohort and compliance tables for small screens, add
   viewport tests.
8. **Accessibility:** proper login radio semantics, skip link, live-region
   announcements, verified keyboard order.

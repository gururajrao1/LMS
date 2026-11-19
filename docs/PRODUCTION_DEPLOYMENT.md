# Production deployment — taking the LMS company-wide on AWS

**Read this first (manager, 2 minutes).** Today the LMS runs on one laptop
with a demo sign-in and files instead of a database. That is fine for the
pilot. For the whole company it needs four upgrades: real login, a real
database, proper hosting with backups, and emailed reminders. Ballpark AWS
cost is **$90–120/month for the pilot** and **$150–200/month for full
production**, verified against October 2026 us-east-1 list prices — re-check
in the [AWS Pricing Calculator](https://calculator.aws) for our region before
committing. The build order in [Phases](#phases) keeps training running the
whole time. Nothing in the trainee experience gets stricter; the strictness
auditors need lives underneath it.

## Where we are vs where we are going

| Area | Today (demo) | Production |
|---|---|---|
| Sign-in | Pick-a-name, no password | SSO login, leavers cut off |
| Data | JSON files on one disk | Postgres database + backups |
| Hosting | Laptop, stops after sessions | Always-on AWS services |
| Reminders | In-app only | Email (+SMS later) |
| Content | Files in the repo (176 MB) | Files in S3, served via CDN |

## Target architecture on AWS

Trainee browser → CloudFront CDN (decks, videos) + load balancer → two
services: the web app and the API, each running as a container on ECS
Fargate. The API reads and writes Postgres on RDS. Login goes through
Cognito (SSO). Reminders go out through SES email. Secrets live in Secrets
Manager; logs and alarms in CloudWatch.

| Piece | AWS service | Job |
|---|---|---|
| Web app + API | ECS Fargate, 2 services | Always-on hosting, no servers to patch |
| Database | RDS Postgres | People, attempts, certificates, audit |
| Course files | S3 + CloudFront | Decks/videos, fast worldwide |
| Login | Cognito + SSO | One company login, auto offboarding |
| Email | SES | Due/overdue/manager reminders |

## Data design (SE section)

Move runtime facts into Postgres; keep course content as files in S3 with the
database pointing at them. Tables: `people` (id, name, email, role, manager),
`learner_groups` (id, label, members), `courses` + `publications` (version,
assignees, group ids, due dates), `progress` (modules, attempts as an
append-only log, certificates), and `audit_log` (append-only: who did what,
when, hash-chained like today). Attempts and audit rows are never updated or
deleted — corrections are new rows — so an auditor can replay any
certificate. The existing hash chain and verification lookup carry over
unchanged, just backed by the database.

## Audit and compliance mapping (manager + SE)

| Auditor asks | Answer after migration |
|---|---|
| Who completed what, when? | Progress + audit replay per learner |
| Is this certificate real? | Verify-by-code lookup, revocations listed |
| Who approved the course? | Sign-offs with typed-name attestation |
| Can records be edited? | No, append-only tables plus backups |
| Who sees drug training? | Roles stay anonymized outside induction |

## Cost, AWS ballpark (verify before committing)

us-east-1 list prices, October 2026. Our region may differ slightly.

| Item | Size | $/mo |
|---|---|---|
| RDS Postgres, Single-AZ (pilot) | db.t4g.micro + 20 GB | ~$15 |
| RDS Postgres, Multi-AZ (production) | db.t4g.small + 40 GB | ~$40 |
| ECS Fargate, API + web | 2 x 1 vCPU/2 GB, always on | ~$70 |
| App load balancer | 1 ALB | ~$16 |
| S3 content + CloudFront | ~200 GB, mostly cached | ~$5 |
| SES email | 10k mails | ~$1 |
| Cognito login | Pilot-scale users | Free tier |
| Route 53 + logs | 1 zone + CloudWatch | ~$4 |

Pilot total is about **$90-120/month** (Single-AZ, Fargate). Production total
is about **$150-200/month** (Multi-AZ, ALB, backups). A cheaper path is one
EC2 box instead of Fargate, saving about $50/month but returning server
patching to us — worth it only if someone owns ops.

## Phases

1. **Database first.** Move people, progress, certificates, and audit into
   Postgres; content stays in files. Training keeps running.
2. **Login.** Cognito + SSO; demo picker retires. Leavers lose access
   automatically (also answers the HRIS ask).
3. **Hosting.** API + web to Fargate behind the load balancer; S3 +
   CloudFront for course files; backups and alarms on.
4. **Reminders.** SES email for due, overdue, and manager notices (already
   decided YES); SMS later if field teams need it.
5. **Hardening.** Multi-AZ database, audit export pack, load test with a
   realistic cohort, then open to all employees.

## Open decisions and risks

- Region choice moves prices ~10-20% — confirm in the Pricing Calculator.
- Manager emails need the manager column on the roster (or HRIS) first.
- The 3-attempt rule should be new-courses-only unless Shashi says
  otherwise; retroactive locks would rewrite the pilot story.
- Biggest risk is data migration, not features: the JSON-to-Postgres move
  needs a rehearsed import with a rollback snapshot.


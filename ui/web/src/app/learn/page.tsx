"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Award, Bell, BookOpenCheck, CalendarDays, CircleAlert, GraduationCap, Inbox, TriangleAlert } from "lucide-react";
import { AppShell, Loading, Stat } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Assignment, AssignmentState, getJson, LearnerHome, LearnerSummary } from "@/lib/api";

type DashboardAlert = { user_id: string; name: string; run_id: string; kind: "overdue" | "below_requirement" | "unbaselined"; severity: "danger" | "warning"; tier: number; message: string };

type Nudge = { key: string; title: string; message: string; href: string; urgent: boolean };

/** Server flags plus due-soon courses, each with a deep link to the fix. */
function buildNudges(courses: Assignment[], alerts: DashboardAlert[]): Nudge[] {
  const byRun: Record<string, Assignment> = Object.fromEntries(courses.map((course) => [course.run_id, course]));
  const titleOf = (run_id: string) => byRun[run_id]?.title ?? byRun[run_id]?.drug.brand ?? "Training";
  const nudges: Nudge[] = alerts.map((alert) => ({
    key: `${alert.run_id}-${alert.message}`,
    title: titleOf(alert.run_id),
    message: alert.message,
    href: alert.kind === "overdue"
      ? `/learn/${alert.run_id}`
      : alert.kind === "below_requirement"
        ? `/learn/${alert.run_id}/assessment/final`
        : `/learn/${alert.run_id}/assessment/baseline`,
    urgent: alert.severity === "danger",
  }));
  for (const course of courses) {
    const left = course.days_remaining;
    if (course.state === "due" && left !== null && left >= 0 && left <= 7 && !nudges.some((nudge) => nudge.href === `/learn/${course.run_id}`))
      nudges.push({
        key: `due-${course.run_id}`,
        title: course.title ?? course.drug.brand,
        message: left === 0 ? "Due today — finish it now." : `Due in ${left} ${left === 1 ? "day" : "days"} — still time to stay on plan.`,
        href: `/learn/${course.run_id}`,
        urgent: left <= 2,
      });
  }
  return nudges;
}
import { RAG_BADGE, RAG_DOT } from "@/lib/rag";
import { useSession } from "@/lib/session";

const NEXT_STEP: Record<LearnerSummary["stage"], string> = {
  not_started: "Start the baseline check",
  baseline: "Work through the material",
  learning: "Continue learning",
  final: "Take the final assessment",
  complete: "View your certificate",
};

const STAGE_BADGE: Record<LearnerSummary["stage"], string> = {
  not_started: "bg-stone-100 dark:bg-muted text-stone-600 dark:text-muted-foreground",
  baseline: "bg-stone-100 dark:bg-muted text-stone-700 dark:text-stone-200",
  learning: "bg-stone-100 dark:bg-muted text-stone-700 dark:text-stone-200",
  final: "bg-warn-50 dark:bg-warn-950 text-warn-700 dark:text-warn-400",
  complete: "bg-brand-50 dark:bg-brand-950 text-brand-700 dark:text-brand-300",
};

/**
 * The schedule, in the order it matters to the person reading it: what is late,
 * what is on now, what is coming, what is behind them. Ordering by urgency rather
 * than by title is the whole point — a trainee opening this wants to know what to
 * do today, not to browse a catalogue.
 */
const SECTIONS: { state: AssignmentState; title: string; blurb: string }[] = [
  { state: "overdue", title: "Overdue", blurb: "Past its due date and not yet complete." },
  { state: "due", title: "In progress", blurb: "Open now, within its schedule." },
  { state: "upcoming", title: "Upcoming", blurb: "Scheduled, not open yet." },
  { state: "completed", title: "Completed", blurb: "Certified, with your score on record." },
];

function shortDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function timing(course: Assignment) {
  const { state, days_remaining: left, days_until_start: until } = course;
  if (state === "completed") return { label: "Complete", urgent: false };
  if (state === "upcoming") return { label: until === 1 ? "Opens tomorrow" : `Opens in ${until} days`, urgent: false };
  if (left === null) return { label: "", urgent: false };
  if (left < 0) return { label: `${Math.abs(left)} ${Math.abs(left) === 1 ? "day" : "days"} overdue`, urgent: true };
  if (left === 0) return { label: "Due today", urgent: true };
  return { label: `${left} ${left === 1 ? "day" : "days"} left`, urgent: left <= 7 };
}

const DAY = 86_400_000;

/**
 * Where today sits between the start and the deadline, so "3 days left" has a shape.
 *
 * Positioned from the day counts the server sent, not from the browser's clock:
 * the two can disagree across a timezone, and a marker that moves between the
 * server render and the client one is a hydration mismatch as well as a lie.
 */
function Timeline({ course }: { course: Assignment }) {
  const start = new Date(`${course.starts_on}T00:00:00`).getTime();
  const end = new Date(`${course.due_on}T00:00:00`).getTime();
  const span = Math.max(Math.round((end - start) / DAY), 1);
  const gone = span - (course.days_remaining ?? 0);
  const elapsed = Math.min(Math.max(gone / span, 0), 1);
  const done = course.state === "completed";

  return (
    <div className="mt-3">
      <div className="relative h-1.5 w-full rounded-full bg-stone-100 dark:bg-muted">
        <div className={`h-1.5 rounded-full ${done ? "bg-brand-600" : "bg-stone-300"}`}
          style={{ width: `${(done ? 1 : elapsed) * 100}%` }} />
        {!done && course.state !== "upcoming" && (
          <span aria-hidden title="Today"
            className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-brand-600 ring-2 ring-white dark:ring-stone-900"
            style={{ left: `${elapsed * 100}%` }} />
        )}
      </div>
      <div className="mt-1.5 flex items-center justify-between text-xs text-stone-600 dark:text-muted-foreground">
        <span className="flex items-center gap-1.5"><CalendarDays size={12} /> {shortDate(course.starts_on)}</span>
        <span>{shortDate(course.due_on)}</span>
      </div>
    </div>
  );
}

function AssignmentCard({ course }: { course: Assignment }) {
  const due = timing(course);
  return (
    <Link href={`/learn/${course.run_id}`}>
      <Card className="h-full transition-shadow hover:shadow-md">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <CardTitle className="text-xl leading-tight">{course.title ?? course.drug.brand}</CardTitle>
              <p className="mt-1 text-sm text-stone-600 dark:text-muted-foreground">
                {course.title ? `${course.drug.brand} · ` : ""}{course.drug.generic} · v{course.version}
              </p>
            </div>
            <Badge className={STAGE_BADGE[course.summary.stage]}>
              {course.summary.stage === "complete" ? "Certified" : `${course.summary.percent}% complete`}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <Progress value={course.summary.percent} />
          <Timeline course={course} />
          {due.label && (
            <>
            <p className="mt-3"><span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${RAG_BADGE[course.state === "overdue" ? "red" : course.state === "upcoming" ? "neutral" : course.summary.certificate ? "green" : "amber"]}`}><span aria-hidden className={`size-1.5 rounded-full ${RAG_DOT[course.state === "overdue" ? "red" : course.state === "upcoming" ? "neutral" : course.summary.certificate ? "green" : "amber"]}`} />{course.state === "overdue" ? "Overdue" : course.state === "upcoming" ? "Not open yet" : course.summary.certificate ? "Complete" : "In progress"}</span></p>
            <p className={`mt-2 text-sm font-medium ${due.urgent ? "text-warn-700 dark:text-warn-400" : "text-stone-600 dark:text-muted-foreground"}`}>{due.label}</p>
            </>
          )}
          {course.summary.uplift !== null && (
            <p className="mt-3 text-sm text-stone-600 dark:text-muted-foreground">
              Baseline {course.summary.baseline_score} → final <b>{course.summary.final_score}</b>{" "}
              <span className="text-brand-700 dark:text-brand-300">({course.summary.uplift >= 0 ? "+" : ""}{course.summary.uplift})</span>
            </p>
          )}
          <p className="mt-4 flex items-center gap-1.5 text-sm font-medium text-brand-700 dark:text-brand-300">
            {course.state === "upcoming" ? "Opens soon" : NEXT_STEP[course.summary.stage]} <ArrowRight size={14} /> <span className="ml-auto font-semibold text-stone-600 dark:text-muted-foreground">{course.summary.points} pts{course.summary.certificate ? ` · valid until ${course.summary.certificate.expires_at?.slice(0, 10)}` : ""}</span>
          </p>
        </CardContent>
      </Card>
    </Link>
  );
}

export default function LearnerHomePage() {
  const user = useSession(["msl", "hcp"], { anyLearner: true });
  const [home, setHome] = useState<LearnerHome | null>(null);
  const [alerts, setAlerts] = useState<DashboardAlert[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    getJson<LearnerHome>(`/api/learn/${user.id}`).then(setHome).catch(() => setError("Could not load your training."));
    getJson<{ alerts: DashboardAlert[] }>(`/api/learners/${user.id}/dashboard`).then((dashboard) => setAlerts(dashboard.alerts)).catch(() => {});
  }, [user]);

  if (!user) return <AppShell><Loading /></AppShell>;
  if (!home) return <AppShell user={user}><Loading label={error || "Loading your training…"} /></AppShell>;

  const certified = home.courses.filter((course) => course.state === "completed").length;
  const active = home.courses.filter((course) => course.state === "due" || course.state === "overdue").length;
  const next = home.courses
    .filter((course) => course.state === "due" || course.state === "overdue")
    .sort((a, b) => (a.days_remaining ?? 0) - (b.days_remaining ?? 0))[0];
  const nudges = buildNudges(home.courses, alerts);

  return (
    <AppShell user={user}>
      <div>
        <p className="text-sm font-semibold text-brand-700 dark:text-brand-300">{home.track.toUpperCase()} TRAINING TRACK</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Welcome back, {user.name.replace(/^Dr\.?\s+/i, "").split(" ")[0]}</h1>
        <p className="mt-2 text-stone-600 dark:text-muted-foreground">
          {next
            ? <>Your closest deadline is <b>{next.title ?? next.drug.brand}</b>, {timing(next).label.toLowerCase()}.</>
            : "Nothing is outstanding. Everything assigned to you is complete or not yet open."}
        </p>
      </div>

      {nudges.length > 0 && (
        <Card className="mt-8 border-warn-200 dark:border-warn-800 bg-warn-50 dark:bg-warn-950">
          <CardContent className="p-5">
            <p className="flex items-center gap-2 font-semibold"><Bell size={16} className="text-warn-700 dark:text-warn-400" /> Needs your attention ({nudges.length})</p>
            <ul className="mt-3 space-y-2">
              {nudges.map((nudge) => (
                <li key={nudge.key}>
                  <Link href={nudge.href} className="flex items-center gap-2.5 rounded-lg bg-white dark:bg-surface p-3 shadow-sm transition-shadow hover:shadow-md">
                    {nudge.urgent
                      ? <TriangleAlert size={16} className="shrink-0 text-warn-700 dark:text-warn-400" />
                      : <CircleAlert size={16} className="shrink-0 text-brand-700 dark:text-brand-300" />}
                    <span className="min-w-0 text-sm"><b>{nudge.title}</b> <span className="text-stone-600 dark:text-muted-foreground">— {nudge.message}</span></span>
                    <ArrowRight size={15} className="ml-auto shrink-0 text-brand-700 dark:text-brand-300" />
                  </Link>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <section className="mt-8 grid gap-4 sm:grid-cols-3">
        <Stat icon={BookOpenCheck} value={home.courses.length} label="Assigned to you" tone="brand" />
        <Stat icon={GraduationCap} value={active} label="Open now" tone={active ? "warn" : "brand"} />
        <Stat icon={Award} value={certified} label="Certificates earned" />
      </section>

      {next && (
        <Link href={`/learn/${next.run_id}`}>
          <Card className="mt-8 border-brand-200 dark:border-brand-800 bg-brand-50 dark:bg-brand-950 transition-shadow hover:shadow-md">
            <CardContent className="flex items-center gap-4 p-5">
              <span className="grid size-11 shrink-0 place-items-center rounded-full bg-brand-600 text-white"><GraduationCap size={20} /></span>
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wide text-brand-700 dark:text-brand-300">Up next for you</p>
                <p className="mt-0.5 truncate text-lg font-semibold">{next.title ?? next.drug.brand} · {timing(next).label}</p>
                <p className="text-sm text-stone-600 dark:text-muted-foreground">{NEXT_STEP[next.summary.stage]}</p>
              </div>
              <ArrowRight size={18} className="ml-auto shrink-0 text-brand-700 dark:text-brand-300" />
            </CardContent>
          </Card>
        </Link>
      )}

      {!home.courses.length ? (
        <Card className="mt-9"><CardContent className="flex flex-col items-center gap-3 p-12 text-center text-stone-600 dark:text-muted-foreground">
          <Inbox size={28} className="text-stone-300" />
          <p>Nothing has been assigned to you yet.</p>
          <p className="text-sm">Courses appear here as soon as a medical education lead publishes one to your role.</p>
        </CardContent></Card>
      ) : (
        SECTIONS.map(({ state, title, blurb }) => {
          const courses = home.courses.filter((course) => course.state === state);
          if (!courses.length) return null;
          return (
            <section key={state} className="mt-9">
              <div className="flex flex-wrap items-baseline gap-x-3">
                <h2 className="text-lg font-semibold">{title}</h2>
                <span className="text-sm tabular-nums text-stone-500 dark:text-stone-400">{courses.length}</span>
                <p className="text-sm text-stone-600 dark:text-muted-foreground">{blurb}</p>
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                {courses.map((course) => <AssignmentCard key={course.run_id} course={course} />)}
              </div>
            </section>
          );
        })
      )}
    </AppShell>
  );
}

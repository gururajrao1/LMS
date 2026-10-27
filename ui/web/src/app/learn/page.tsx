"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Award, BookOpenCheck, CalendarDays, GraduationCap, Inbox } from "lucide-react";
import { AppShell, Loading, Stat } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Assignment, AssignmentState, getJson, LearnerHome, LearnerSummary } from "@/lib/api";
import { useSession } from "@/lib/session";

const NEXT_STEP: Record<LearnerSummary["stage"], string> = {
  not_started: "Start the baseline check",
  baseline: "Work through the material",
  learning: "Continue learning",
  final: "Take the final assessment",
  complete: "View your certificate",
};

const STAGE_BADGE: Record<LearnerSummary["stage"], string> = {
  not_started: "bg-stone-100 text-stone-600",
  baseline: "bg-stone-100 text-stone-700",
  learning: "bg-stone-100 text-stone-700",
  final: "bg-warn-50 text-warn-700",
  complete: "bg-brand-50 text-brand-700",
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
      <div className="relative h-1.5 w-full rounded-full bg-stone-100">
        <div className={`h-1.5 rounded-full ${done ? "bg-brand-600" : "bg-stone-300"}`}
          style={{ width: `${(done ? 1 : elapsed) * 100}%` }} />
        {!done && course.state !== "upcoming" && (
          <span aria-hidden title="Today"
            className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-brand-600 ring-2 ring-white"
            style={{ left: `${elapsed * 100}%` }} />
        )}
      </div>
      <div className="mt-1.5 flex items-center justify-between text-xs text-stone-600">
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
              <p className="mt-1 text-sm text-stone-600">
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
            <p className={`mt-2 text-sm font-medium ${due.urgent ? "text-warn-700" : "text-stone-600"}`}>{due.label}</p>
          )}
          {course.summary.uplift !== null && (
            <p className="mt-3 text-sm text-stone-600">
              Baseline {course.summary.baseline_score} → final <b>{course.summary.final_score}</b>{" "}
              <span className="text-brand-700">({course.summary.uplift >= 0 ? "+" : ""}{course.summary.uplift})</span>
            </p>
          )}
          <p className="mt-4 flex items-center gap-1.5 text-sm font-medium text-brand-700">
            {course.state === "upcoming" ? "Opens soon" : NEXT_STEP[course.summary.stage]} <ArrowRight size={14} />
          </p>
        </CardContent>
      </Card>
    </Link>
  );
}

export default function LearnerHomePage() {
  const user = useSession(["msl", "hcp"]);
  const [home, setHome] = useState<LearnerHome | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    getJson<LearnerHome>(`/api/learn/${user.id}`).then(setHome).catch(() => setError("Could not load your training."));
  }, [user]);

  if (!user) return <AppShell><Loading /></AppShell>;
  if (!home) return <AppShell user={user}><Loading label={error || "Loading your training…"} /></AppShell>;

  const certified = home.courses.filter((course) => course.state === "completed").length;
  const active = home.courses.filter((course) => course.state === "due" || course.state === "overdue").length;
  const next = home.courses
    .filter((course) => course.state === "due" || course.state === "overdue")
    .sort((a, b) => (a.days_remaining ?? 0) - (b.days_remaining ?? 0))[0];

  return (
    <AppShell user={user}>
      <div>
        <p className="text-sm font-semibold text-brand-700">{home.track.toUpperCase()} TRAINING TRACK</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Welcome back, {user.name.replace(/^Dr\.?\s+/i, "").split(" ")[0]}</h1>
        <p className="mt-2 text-stone-600">
          {next
            ? <>Your closest deadline is <b>{next.title ?? next.drug.brand}</b>, {timing(next).label.toLowerCase()}.</>
            : "Nothing is outstanding. Everything assigned to you is complete or not yet open."}
        </p>
      </div>

      <section className="mt-8 grid gap-4 sm:grid-cols-3">
        <Stat icon={BookOpenCheck} value={home.courses.length} label="Assigned to you" tone="brand" />
        <Stat icon={GraduationCap} value={active} label="Open now" tone={active ? "warn" : "brand"} />
        <Stat icon={Award} value={certified} label="Certificates earned" />
      </section>

      {!home.courses.length ? (
        <Card className="mt-9"><CardContent className="flex flex-col items-center gap-3 p-12 text-center text-stone-600">
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
                <span className="text-sm tabular-nums text-stone-500">{courses.length}</span>
                <p className="text-sm text-stone-600">{blurb}</p>
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

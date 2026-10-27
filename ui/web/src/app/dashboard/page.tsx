"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, BookOpenCheck, CirclePlus, Layers3, Send, UserRoundCheck, Users } from "lucide-react";
import { AppShell, Loading, Stat } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Analytics, API, ClientProgrammes, getJson, Run } from "@/lib/api";
import { useSession } from "@/lib/session";
import { ProgrammesPanel } from "@/components/programmes";

type Course = {
  id: string;
  run_id?: string;
  name: string;
  generic: string;
  area: string;
  status: string;
  progress: number;
  review_status?: "draft" | "in_review" | "approved" | "published";
  version?: number;
  assigned?: number;
  assigned_reviewers?: string[];
  generated_at?: string;
  /** Set when an older run of the same drug is the one currently in the field. */
  live_version?: number;
  live_assigned?: number;
};

/**
 * One card per drug.
 *
 * The API deliberately returns the live course and the newest draft separately, so
 * that generating during a demo cannot hide the course a cohort is working through.
 * On the dashboard that arrives as two cards for the same medicine, which reads as
 * two products. They collapse here into the newest run, carrying a line about the
 * version still in the field — the safeguard's information is kept, its duplicate
 * card is not.
 */
function oneCardPerDrug(all: Course[]): Course[] {
  const byDrug = new Map<string, Course[]>();
  for (const course of all.filter((entry) => entry.run_id)) {
    byDrug.set(course.id, [...(byDrug.get(course.id) ?? []), course]);
  }
  const cards = [...byDrug.values()].map((entries) => {
    const newest = entries.reduce((a, b) => ((b.generated_at ?? "") > (a.generated_at ?? "") ? b : a));
    const live = entries.find((entry) => entry.review_status === "published");
    return live && live.run_id !== newest.run_id
      ? { ...newest, live_version: live.version, live_assigned: live.assigned }
      : newest;
  });
  return [...cards, ...all.filter((entry) => !entry.run_id)];
}

const REVIEW_LABEL = { draft: "Draft", in_review: "In review", approved: "Approved", published: "Published" } as const;

function CourseCard({ course, mine }: { course: Course; mine?: boolean }) {
  return (
    <Card className={`h-full transition-shadow ${course.run_id ? "hover:shadow-md" : ""} ${mine ? "border-brand-600" : ""}`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <span className="rounded-xl bg-brand-50 p-2.5 text-brand-700"><BookOpenCheck size={20} /></span>
          <div className="flex flex-wrap justify-end gap-1.5">
            {/* Reads before the status chip, because on a shared queue "is this mine"
                is the question a reviewer opens the page with. */}
            {mine && <Badge className="bg-brand-600"><UserRoundCheck size={12} /> Assigned to you</Badge>}
            <Badge variant={course.review_status === "published" ? "default" : "secondary"} className={course.review_status === "published" ? "bg-brand-600" : ""}>
              {course.review_status ? REVIEW_LABEL[course.review_status] : course.status}
            </Badge>
          </div>
        </div>
        <CardTitle className="pt-3 text-lg">{course.name}</CardTitle>
        {/* Therapeutic area only, as in the programme list: a card is no place to
            restate a licensed-use claim away from the checks that scrutinise it. */}
        <p className="text-sm text-stone-600">{course.generic} · {course.area.split(/[–—-]/)[0].trim()}</p>
      </CardHeader>
      <CardContent>
        <Progress value={course.progress} />
        <div className="mt-3 flex justify-between text-xs text-stone-600">
          <span>{course.run_id ? `Version ${course.version ?? 1}` : "Content readiness"}</span>
          <span>{course.run_id && course.assigned ? `${course.assigned} assigned` : `${course.progress}%`}</span>
        </div>
        {course.live_version ? (
          <p className="mt-2 text-xs text-stone-600">
            v{course.live_version} is live with {course.live_assigned} trainee(s)
          </p>
        ) : null}
        {course.run_id && <p className="mt-4 flex items-center gap-1.5 text-sm font-medium text-brand-700">Open course <ArrowRight size={14} /></p>}
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const user = useSession(["admin", "reviewer"]);
  const router = useRouter();
  const [courses, setCourses] = useState<Course[]>([]);
  const [drug, setDrug] = useState("Ibrance");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [impact, setImpact] = useState<Analytics | null>(null);
  const [client, setClient] = useState<ClientProgrammes | null>(null);

  const loadClient = () => getJson<ClientProgrammes>("/api/clients/pfizer").then(setClient).catch(() => undefined);

  useEffect(() => {
    loadClient();
    getJson<Course[]>("/api/courses")
      .then((all) => {
        setCourses(all);
        const live = all.find((course) => course.review_status === "published");
        if (live?.run_id) getJson<Analytics>(`/api/runs/${live.run_id}/analytics`).then(setImpact).catch(() => undefined);
      })
      .catch(() => setError(`Start the API on ${API} to load courses.`));
  }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const response = await fetch(`${API}/api/runs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ drug }) });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Could not start run");
      const run: Run = await response.json();
      router.push(`/runs/${run.id}`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not start run"); setBusy(false); }
  }

  if (!user) return <AppShell><Loading /></AppShell>;
  const ready = courses.filter((course) => course.run_id);
  const published = ready.filter((course) => course.review_status === "published");
  const awaiting = ready.filter((course) => course.review_status !== "published");
  const assigned = ready.reduce((total, course) => total + (course.assigned ?? 0), 0);
  const admin = user.role === "admin";
  // Only a reviewer can have a course assigned to them; the admin assigning it is
  // not thereby reviewing it.
  const mineToReview = (course: Course) =>
    user.role === "reviewer" && (course.assigned_reviewers ?? []).includes(user.id);

  return (
    <AppShell user={user}>
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold text-brand-700">{admin ? "CONTENT OPERATIONS" : "MEDICAL REVIEW"}</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">{admin ? "Training dashboard" : "Review queue"}</h1>
          <p className="mt-2 text-stone-600">{admin ? "Create, review, publish and monitor evidence-backed learning." : "Open a course to comment on its assets and record your sign-off."}</p>
        </div>
        {admin && (
          <Dialog>
            <DialogTrigger render={<Button className="bg-brand-600 hover:bg-brand-800" />}><CirclePlus /> Create content</DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Create a training course</DialogTitle><DialogDescription>Search by brand or generic drug name.</DialogDescription></DialogHeader>
              <form onSubmit={create} className="space-y-5 pt-3">
                <div><label className="text-sm font-medium">Search for a drug</label><Input value={drug} onChange={(event) => setDrug(event.target.value)} className="mt-2" autoFocus /></div>
                <div className="rounded-xl bg-brand-50 p-4 text-sm text-brand-800">The agent will produce a PPTX, video storyboard, FAQ, and interactive quiz with citations.</div>
                {error && <p className="text-sm text-danger-600">{error}</p>}
                <Button type="submit" disabled={busy || !drug.trim()} className="w-full bg-brand-600 hover:bg-brand-800">{busy ? "Starting…" : "Create course"}<ArrowRight /></Button>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {error && <p className="mt-5 text-sm text-danger-600">{error}</p>}
      {impact && published[0] && (
        <Link href={`/courses/${published[0].run_id}`} className="mt-8 flex flex-col gap-3 rounded-xl bg-surface-deep p-5 text-white transition-colors hover:bg-brand-800 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <p className="text-sm font-semibold uppercase tracking-[.14em] text-brand-300">{published[0].name} v{published[0].version}</p>
            <p className="text-sm text-stone-200">
              Published in <b className="tabular-nums">{impact.roi.measured.days_to_publish} days</b> against a{" "}
              {impact.roi.baseline.first_version_days}-day manual build
            </p>
          </div>
          <div className="flex items-center gap-6">
            <p className="text-sm text-stone-200"><b className="text-xl font-semibold tabular-nums text-white">{impact.roi.saving.percent_faster}%</b> faster</p>
            <p className="text-sm text-stone-200"><b className="text-xl font-semibold tabular-nums text-white">${impact.roi.saving.cost_saved_usd?.toLocaleString("en-US")}</b> saved</p>
            <ArrowRight size={18} className="hidden text-brand-300 sm:block" />
          </div>
        </Link>
      )}
      {client && client.programmes.length > 0 && (
        <section className="mt-8"><ProgrammesPanel data={client} user={user} onChange={loadClient} /></section>
      )}

      <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={BookOpenCheck} value={ready.length} label="Generated courses" />
        <Stat icon={Layers3} value={awaiting.length} label="Awaiting publication" tone="warn" />
        <Stat icon={Send} value={published.length} label="Published" tone="brand" />
        <Stat icon={Users} value={assigned} label="Trainees assigned" />
      </section>

      <section className="mt-9">
        <h2 className="text-lg font-semibold">Courses</h2>
        {!courses.length && !error && (
          <Card className="mt-4"><CardContent className="flex flex-col items-center gap-3 p-12 text-center text-stone-600">
            <BookOpenCheck size={28} className="text-stone-300" />
            <p>No courses yet.</p>
            <p className="text-sm">{admin ? "Create content for a drug to generate the first one." : "Courses appear here once a medical education lead generates one."}</p>
          </CardContent></Card>
        )}
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {oneCardPerDrug(courses).map((course) => course.run_id
            ? <Link key={course.run_id} href={`/courses/${course.run_id}`}><CourseCard course={course} mine={mineToReview(course)} /></Link>
            : <CourseCard key={course.id} course={course} />)}
        </div>
      </section>
    </AppShell>
  );
}

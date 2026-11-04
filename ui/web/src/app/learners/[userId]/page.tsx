"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { AppShell, Loading } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { getJson } from "@/lib/api";
import { RAG_BADGE } from "@/lib/rag";
import { useSession } from "@/lib/session";

type LearnerDashboard = {
  user: { id: string; name: string; role: string; title: string };
  courses: { run_id: string; version: number; state: string; stage: string; percent: number; points: number; passed: boolean; certificate: { code: string } | null }[];
  points: number;
  certified: number;
  overdue: number;
  alerts: { user_id: string; name: string; severity: string; message: string }[];
};

/** One learner's whole picture, for the training team. */
export default function LearnerDashboardPage() {
  const { userId } = useParams<{ userId: string }>();
  const user = useSession(["admin", "reviewer"]);
  const [dashboard, setDashboard] = useState<LearnerDashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getJson<LearnerDashboard>(`/api/learners/${userId}/dashboard`).then(setDashboard).catch(() => setError("Could not load this learner."));
  }, [userId]);

  if (!user) return <AppShell><Loading /></AppShell>;
  if (error) return <AppShell user={user}><p className="mt-6 text-sm text-danger-600">{error}</p></AppShell>;
  if (!dashboard) return <AppShell user={user}><Loading label="Loading the learner dashboard…" /></AppShell>;

  return (
    <AppShell user={user}>
      <Link href="/dashboard" className="mb-5 inline-flex items-center gap-2 text-sm font-medium text-stone-600 hover:text-brand-700"><ArrowLeft size={16} /> Back to dashboard</Link>
      <div>
        <p className="text-sm text-stone-600">{dashboard.user.role} · {dashboard.user.title}</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{dashboard.user.name}</h1>
        <p className="mt-2 text-sm text-stone-600"><b className="text-ink">{dashboard.points} pts</b> · {dashboard.certified} certified · {dashboard.overdue} overdue</p>
      </div>

      {dashboard.alerts.length > 0 && (
        <Card className="mt-7 border-danger-200">
          <CardHeader><CardTitle className="text-base">Needs attention ({dashboard.alerts.length})</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {dashboard.alerts.map((alert, index) => (
              <p key={index} className="flex items-start gap-2 text-sm">
                <span className={`mt-0.5 rounded-full px-2 py-0.5 text-xs font-medium ${RAG_BADGE[alert.severity as "danger" | "warning"]}`}>{alert.severity === "danger" ? "Action needed" : "Watch"}</span>
                <span>{alert.message}</span>
              </p>
            ))}
          </CardContent>
        </Card>
      )}

      <div className="mt-7 grid gap-4 md:grid-cols-2">
        {dashboard.courses.map((course) => (
          <Link key={course.run_id} href={`/courses/${course.run_id}`}>
            <Card className="transition-shadow hover:shadow-md">
              <CardHeader><CardTitle className="text-base">{course.run_id} · v{course.version}</CardTitle></CardHeader>
              <CardContent>
                <div className="flex items-center justify-between text-sm"><span className="text-stone-600">{course.stage}</span><span className="font-semibold">{course.percent}% · {course.points} pts</span></div>
                <Progress value={course.percent} className="mt-2" />
                {course.certificate && <p className="mt-2 text-sm text-brand-700">Certified: {course.certificate.code}</p>}
              </CardContent>
            </Card>
          </Link>
        ))}
        {!dashboard.courses.length && <p className="text-sm text-stone-600">No assignments yet.</p>}
      </div>
    </AppShell>
  );
}

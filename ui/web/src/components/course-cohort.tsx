"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Award, CheckCircle2, MessageSquare, RotateCcw, Star, TrendingUp, UserCheck, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ROLE_LABEL, Stat } from "@/components/app-shell";
import { API, Cohort, CohortLearner, getJson, Person } from "@/lib/api";
import { RAG_BADGE } from "@/lib/rag";

const STAGE: Record<CohortLearner["stage"], { label: string; className: string }> = {
  not_started: { label: "Not started", className: "bg-stone-100 text-stone-600" },
  baseline: { label: "Baseline done", className: "bg-stone-100 text-stone-700" },
  learning: { label: "In the material", className: "bg-stone-100 text-stone-700" },
  final: { label: "Ready for final", className: "bg-warn-50 text-warn-700" },
  complete: { label: "Certified", className: "bg-brand-50 text-brand-700" },
};

/** One measure (final score) with the learner's baseline drawn as a reference marker. */
function ScoreTrack({ baseline, final }: { baseline: number | null; final: number | null }) {
  if (final === null && baseline === null) return <p className="text-sm text-stone-500">No assessment yet</p>;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-2 w-full min-w-24 rounded-full bg-stone-100">
        {final !== null && <div className="h-2 rounded-full bg-brand-600" style={{ width: `${final}%` }} />}
        {baseline !== null && (
          <span aria-hidden className="absolute top-1/2 h-3.5 w-0.5 -translate-y-1/2 rounded-full bg-stone-500 ring-2 ring-white" style={{ left: `calc(${baseline}% - 1px)` }} />
        )}
      </div>
      <span className="w-24 shrink-0 text-right text-sm tabular-nums">
        {baseline ?? "–"}<span className="text-stone-500"> → </span><b>{final ?? "–"}</b>
        {final !== null && baseline !== null && <span className={`ml-1 text-xs ${final - baseline >= 0 ? "text-brand-700" : "text-danger-600"}`}>{final - baseline >= 0 ? "+" : ""}{final - baseline}</span>}
      </span>
    </div>
  );
}

export function CourseCohortPanel({ runId, user }: { runId: string; user?: Person }) {
  type Alert = { user_id: string; name: string; severity: "danger" | "warning"; message: string };
  const [cohort, setCohort] = useState<Cohort | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    getJson<Cohort>(`/api/runs/${runId}/cohort`).then(setCohort).catch(() => setError("Could not load cohort progress."));
    getJson<Alert[]>(`/api/runs/${runId}/alerts`).then(setAlerts).catch(() => undefined);
  }, [runId]);

  async function resetAnswers(learnerId: string, name: string) {
    if (!user || !window.confirm(`Clear ${name}'s answers so they start over? Any certificate is revoked.`)) return;
    const response = await fetch(`${API}/api/learn/${learnerId}/${runId}/attempts?by=${user.id}`, { method: "DELETE" });
    if (!response.ok) { setError("Could not reset those answers."); return; }
    setCohort(await getJson<Cohort>(`/api/runs/${runId}/cohort`));
    setAlerts(await getJson<Alert[]>(`/api/runs/${runId}/alerts`));
  }

  if (!cohort) return <Card><CardContent className="p-8 text-center text-stone-600">{error || "Loading cohort progress…"}</CardContent></Card>;
  if (!cohort.assigned) return <Card><CardContent className="p-8 text-center text-stone-600">Publish this course to a group of trainees to start monitoring progress.</CardContent></Card>;

  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={Users} value={cohort.assigned} label="Assigned" tone="brand" />
        <Stat icon={UserCheck} value={cohort.started} label="Started" />
        <Stat icon={Award} value={cohort.certified} label="Certified" />
        <Stat icon={TrendingUp} value={cohort.average_uplift === null ? "–" : `+${cohort.average_uplift}`} label="Average knowledge uplift" tone="brand" />
      </section>

      <Card>
        <CardHeader className="flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>Learner progress</CardTitle>
            <p className="mt-2 text-sm text-stone-600">Bar shows the final score; the marker is where the learner started.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <a href={`${API}/api/runs/${runId}/export/completions`} className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-stone-50">Download CSV</a>
              <a href={`${API}/api/runs/${runId}/export/scorm`} className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-stone-50">Download SCORM</a>
              <a href={`${API}/api/runs/${runId}/export/xls`} className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-stone-50">Download Excel</a>
            </div>
          </div>
          {cohort.average_baseline !== null && (
            <p className="text-sm text-stone-600">Cohort average {cohort.average_baseline} → <b className="text-ink">{cohort.average_final ?? "–"}</b></p>
          )}
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[46rem] text-left">
            <thead>
              <tr className="border-b text-xs font-semibold uppercase tracking-wide text-stone-600">
                <th className="pb-3 pr-4">Learner</th>
                <th className="pb-3 pr-4">Stage</th>
                <th className="pb-3 pr-4">Modules</th>
                <th className="pb-3 pr-4">Baseline → final</th>
                <th className="pb-3">Certificate</th>
              </tr>
            </thead>
            <tbody>
              {cohort.learners.map((learner) => (
                <tr key={learner.user_id} className="border-b last:border-0">
                  <td className="py-4 pr-4">
                    {user?.role === "admin"
                      ? <Link href={`/learners/${learner.user_id}`} className="font-medium hover:text-brand-700 hover:underline">{learner.name}</Link>
                      : <p className="font-medium">{learner.name}</p>}
                    {learner.stage !== "complete" && (
                      <button type="button" onClick={() => { navigator.clipboard.writeText(`Hi ${learner.name} — a nudge on your training: stage "${STAGE[learner.stage].label}", ${learner.modules_complete}/${learner.modules_total} modules, ${learner.percent}% complete.`); setCopied(learner.user_id); setTimeout(() => setCopied((current) => current === learner.user_id ? null : current), 2000); }} className="mt-1 text-xs font-medium text-brand-700 hover:underline">{copied === learner.user_id ? "Copied" : "Copy reminder"}</button>
                    )}
                    <p className="text-xs text-stone-600">{ROLE_LABEL[learner.role]} · {learner.title}</p>
                  </td>
                  <td className="py-4 pr-4"><Badge className={STAGE[learner.stage].className}>{STAGE[learner.stage].label}</Badge>{learner.final_score !== null && !learner.passed && <Badge className={`ml-1 ${RAG_BADGE.red}`}>Below required</Badge>}</td>
                  <td className="py-4 pr-4 text-sm tabular-nums text-stone-600">{learner.modules_complete}/{learner.modules_total}</td>
                  <td className="py-4 pr-4"><ScoreTrack baseline={learner.baseline_score} final={learner.final_score} /></td>
                  <td className="py-4">
                    {learner.certificate
                      ? <span className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700"><CheckCircle2 size={15} /> {learner.certificate.code}</span>
                      : <span className="text-sm text-stone-500">Not earned</span>}
                    {user?.role === "admin" && learner.attempts > 0 && (
                      <button type="button" onClick={() => resetAnswers(learner.user_id, learner.name)} className="mt-1 flex items-center gap-1 text-xs font-medium text-stone-500 hover:text-danger-600 hover:underline"><RotateCcw size={12} /> Reset answers</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

        {alerts.length > 0 && (
        <Card className="border-danger-200">
          <CardHeader><CardTitle className="text-base">Noncompliance ({alerts.length})</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {alerts.map((alert, index) => (
              <p key={index} className="flex items-start gap-2 text-sm">
                <span className={`mt-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${RAG_BADGE[alert.severity]}`}>{alert.severity === "danger" ? "Action needed" : "Watch"}</span>
                <span><b>{alert.name}</b> — {alert.message}</span>
              </p>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle className="text-base">Content feedback</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {cohort.feedback.length ? cohort.feedback.map((entry) => (
            <div key={entry.id} className="rounded-xl border p-4">
              <div className="flex items-center gap-2">
                <MessageSquare size={15} className="text-stone-500" />
                <p className="text-sm font-medium">{entry.name}</p>
                <Badge variant="outline" className="capitalize">{entry.module_id}</Badge>
                <span className="ml-auto inline-flex items-center gap-1 text-sm tabular-nums text-stone-600"><Star size={14} className="fill-warn-400 text-warn-500" /> {entry.rating}/5</span>
              </div>
              {entry.comment && <p className="mt-2 leading-6 text-stone-600">{entry.comment}</p>}
            </div>
          )) : <p className="text-sm text-stone-600">No feedback yet. Learners can rate each module as they work through it.</p>}
        </CardContent>
      </Card>
    </div>
  );
}

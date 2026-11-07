"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Award, CheckCircle2, MessageSquare, RotateCcw, Star, TrendingUp, UserCheck, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ROLE_LABEL, Stat } from "@/components/app-shell";
import { API, Cohort, CohortLearner, getJson, Person } from "@/lib/api";
import { roleLabel } from "@/components/app-shell";
import { RAG_BADGE } from "@/lib/rag";

const STAGE: Record<CohortLearner["stage"], { label: string; className: string }> = {
  not_started: { label: "Not started", className: "bg-stone-100 dark:bg-muted text-stone-600 dark:text-muted-foreground" },
  baseline: { label: "Baseline done", className: "bg-stone-100 dark:bg-muted text-stone-700 dark:text-stone-200" },
  learning: { label: "In the material", className: "bg-stone-100 dark:bg-muted text-stone-700 dark:text-stone-200" },
  final: { label: "Ready for final", className: "bg-warn-50 dark:bg-warn-950 text-warn-700 dark:text-warn-400" },
  complete: { label: "Certified", className: "bg-brand-50 dark:bg-brand-950 text-brand-700 dark:text-brand-300" },
};

/** One measure (final score) with the learner's baseline drawn as a reference marker. */
function ScoreTrack({ baseline, final }: { baseline: number | null; final: number | null }) {
  if (final === null && baseline === null) return <p className="text-sm text-stone-500 dark:text-stone-400">No assessment yet</p>;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-2 w-full min-w-24 rounded-full bg-stone-100 dark:bg-muted">
        {final !== null && <div className="h-2 rounded-full bg-brand-600" style={{ width: `${final}%` }} />}
        {baseline !== null && (
          <span aria-hidden className="absolute top-1/2 h-3.5 w-0.5 -translate-y-1/2 rounded-full bg-stone-500 ring-2 ring-white dark:ring-stone-900" style={{ left: `calc(${baseline}% - 1px)` }} />
        )}
      </div>
      <span className="w-24 shrink-0 text-right text-sm tabular-nums">
        {baseline ?? "–"}<span className="text-stone-500 dark:text-stone-400"> → </span><b>{final ?? "–"}</b>
        {final !== null && baseline !== null && <span className={`ml-1 text-xs ${final - baseline >= 0 ? "text-brand-700 dark:text-brand-300" : "text-danger-600 dark:text-danger-300"}`}>{final - baseline >= 0 ? "+" : ""}{final - baseline}</span>}
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
  type Escalation = { key: string; user_id: string; name: string; severity: "danger" | "warning"; tier: number; message: string; level: number; level_name: string; owner: string; action: string; since: string; history: { at: string; note: string }[] };
  const [ladder, setLadder] = useState<{ items: Escalation[]; checked_at: string | null; checked_by: string | null } | null>(null);
  const [checking, setChecking] = useState(false);
  type RetentionClass = { id: string; label: string; description: string; keep_years: number; action: string; items: number; oldest: string | null; newest: string | null; first_due: string | null; due_for_review: number; status: string };
  const [retention, setRetention] = useState<RetentionClass[] | null>(null);

  useEffect(() => {
    getJson<Cohort>(`/api/runs/${runId}/cohort`).then(setCohort).catch(() => setError("Could not load cohort progress."));
    getJson<Alert[]>(`/api/runs/${runId}/alerts`).then(setAlerts).catch(() => undefined);
    getJson<{ items: Escalation[]; checked_at: string | null; checked_by: string | null }>(`/api/runs/${runId}/escalations`).then(setLadder).catch(() => undefined);
    getJson<{ classes: RetentionClass[] }>(`/api/runs/${runId}/retention`).then((report) => setRetention(report.classes)).catch(() => undefined);
  }, [runId]);

  async function runEscalationCheck() {
    if (!user) return;
    setChecking(true); setError("");
    try {
      const response = await fetch(`${API}/api/runs/${runId}/escalations/check`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: user.id }),
      });
      if (!response.ok) throw new Error("Could not run the escalation check");
      setLadder(await response.json());
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not run the escalation check"); }
    finally { setChecking(false); }
  }

  async function resetAnswers(learnerId: string, name: string) {
    if (!user || !window.confirm(`Clear ${name}'s answers so they start over? Any certificate is revoked.`)) return;
    const response = await fetch(`${API}/api/learn/${learnerId}/${runId}/attempts?by=${user.id}`, { method: "DELETE" });
    if (!response.ok) { setError("Could not reset those answers."); return; }
    setCohort(await getJson<Cohort>(`/api/runs/${runId}/cohort`));
    setAlerts(await getJson<Alert[]>(`/api/runs/${runId}/alerts`));
  }

  if (!cohort) return <Card><CardContent className="p-8 text-center text-stone-600 dark:text-muted-foreground">{error || "Loading cohort progress…"}</CardContent></Card>;
  if (!cohort.assigned) return <Card><CardContent className="p-8 text-center text-stone-600 dark:text-muted-foreground">Publish this course to a group of trainees to start monitoring progress.</CardContent></Card>;

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
            <p className="mt-2 text-sm text-stone-600 dark:text-muted-foreground">Bar shows the final score; the marker is where the learner started.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <a href={`${API}/api/runs/${runId}/export/completions`} className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-stone-50 dark:hover:bg-surface-sunk">Download CSV</a>
              <a href={`${API}/api/runs/${runId}/export/scorm`} className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-stone-50 dark:hover:bg-surface-sunk">Download SCORM</a>
              <a href={`${API}/api/runs/${runId}/export/xls`} className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-stone-50 dark:hover:bg-surface-sunk">Download Excel</a>
            </div>
          </div>
          {cohort.average_baseline !== null && (
            <p className="text-sm text-stone-600 dark:text-muted-foreground">Cohort average {cohort.average_baseline} → <b className="text-ink">{cohort.average_final ?? "–"}</b></p>
          )}
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[46rem] text-left">
            <thead>
              <tr className="border-b text-xs font-semibold uppercase tracking-wide text-stone-600 dark:text-muted-foreground">
                <th className="pb-3 pr-4">Learner</th>
                <th className="pb-3 pr-4">Stage</th>
                <th className="pb-3 pr-4">Modules</th>
                <th className="pb-3 pr-4">Baseline → final</th>
                <th className="pb-3 pr-4">Points</th>
                <th className="pb-3">Certificate</th>
              </tr>
            </thead>
            <tbody>
              {[...cohort.learners].sort((left, right) => right.points - left.points).map((learner, position) => (
                <tr key={learner.user_id} className="border-b last:border-0">
                  <td className="py-4 pr-4">
                    {user?.role === "admin"
                      ? <Link href={`/learners/${learner.user_id}`} className="font-medium hover:text-brand-700 dark:hover:text-brand-300 hover:underline">{learner.name}</Link>
                      : <p className="font-medium">{learner.name}</p>}
                    {learner.stage !== "complete" && (
                      <button type="button" onClick={() => { navigator.clipboard.writeText(`Hi ${learner.name} — a nudge on your training: stage "${STAGE[learner.stage].label}", ${learner.modules_complete}/${learner.modules_total} modules, ${learner.percent}% complete.`); setCopied(learner.user_id); setTimeout(() => setCopied((current) => current === learner.user_id ? null : current), 2000); }} className="mt-1 text-xs font-medium text-brand-700 dark:text-brand-300 hover:underline">{copied === learner.user_id ? "Copied" : "Copy reminder"}</button>
                    )}
                    <p className="text-xs text-stone-600 dark:text-muted-foreground">{ROLE_LABEL[learner.role]} · {learner.title}</p>
                  </td>
                  <td className="py-4 pr-4"><Badge className={STAGE[learner.stage].className}>{STAGE[learner.stage].label}</Badge>{learner.final_score !== null && !learner.passed && <Badge className={`ml-1 ${RAG_BADGE.red}`}>Below required</Badge>}</td>
                  <td className="py-4 pr-4 text-sm tabular-nums text-stone-600 dark:text-muted-foreground">{learner.modules_complete}/{learner.modules_total}</td>
                  <td className="py-4 pr-4"><ScoreTrack baseline={learner.baseline_score} final={learner.final_score} /></td>
                  <td className="py-4 pr-4 text-sm tabular-nums text-stone-600 dark:text-muted-foreground">{position < 3 ? <span className="mr-1 inline-grid size-5 place-items-center rounded-full bg-brand-600 text-[11px] font-bold text-white">{position + 1}</span> : <span className="mr-1 text-stone-400">#{position + 1}</span>}{learner.points} pts</td>
                  <td className="py-4">
                    {learner.certificate
                      ? <span className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 dark:text-brand-300"><CheckCircle2 size={15} /> {learner.certificate.code}</span>
                      : <span className="text-sm text-stone-500 dark:text-stone-400">Not earned</span>}
                    {user?.role === "admin" && learner.attempts > 0 && (
                      <button type="button" onClick={() => resetAnswers(learner.user_id, learner.name)} className="mt-1 flex items-center gap-1 text-xs font-medium text-stone-500 dark:text-stone-400 hover:text-danger-600 dark:hover:text-danger-300 hover:underline"><RotateCcw size={12} /> Reset answers</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

        {alerts.length > 0 && (
        <Card className="border-danger-200 dark:border-danger-800">
          <CardHeader><CardTitle className="text-base">Noncompliance ({alerts.length})</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {alerts.map((alert, index) => (
              <p key={index} className="flex items-start gap-2 text-sm">
                <span className={`mt-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${RAG_BADGE[alert.severity === "danger" ? "red" : "amber"]}`}>{alert.severity === "danger" ? "Action needed" : "Watch"}</span>
                <span><b>{alert.name}</b> — {alert.message}</span>
              </p>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="text-base">Escalation ladder ({ladder?.items.length ?? 0})</CardTitle>
              <p className="mt-2 text-sm text-stone-600 dark:text-muted-foreground">
                {ladder?.checked_at
                  ? `Last checked ${new Date(ladder.checked_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}${ladder.checked_by ? ` by ${ladder.checked_by}` : ""}.`
                  : "Not checked yet — run the check to stamp first-seen dates and record level changes."}
              </p>
            </div>
            <Button variant="outline" disabled={checking || !user} onClick={runEscalationCheck}>{checking ? "Checking…" : "Run escalation check"}</Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {(ladder?.items ?? []).map((item) => (
            <div key={item.key} className="rounded-xl border p-4">
              <p className="flex flex-wrap items-center gap-2 text-sm">
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${item.level === 3 ? "bg-stone-900 text-white" : item.level === 2 ? "bg-danger-50 dark:bg-danger-950 text-danger-700 dark:text-danger-300" : "bg-warn-50 dark:bg-warn-950 text-warn-700 dark:text-warn-400"}`}>L{item.level} · {item.level_name}</span>
                <span><b>{item.name}</b> — {item.message}</span>
              </p>
              <p className="mt-2 text-xs leading-5 text-stone-600 dark:text-muted-foreground">{item.action} Owner: {roleLabel(item.owner)}. Since {item.since}.{item.history.length ? ` ${item.history.length} record${item.history.length === 1 ? "" : "s"}: ${item.history[item.history.length - 1].note}.` : ""}</p>
            </div>
          ))}
          {!ladder?.items.length && <p className="text-sm text-stone-600 dark:text-muted-foreground">Nothing on the ladder — every flag is clear.</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Data retention</CardTitle><p className="mt-2 text-sm text-stone-600 dark:text-muted-foreground">What this course holds and how long each class stays. Report-only — nothing is deleted here.</p></CardHeader>
        <CardContent className="space-y-2">
          {(retention ?? []).map((entry) => (
            <div key={entry.id} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border p-4">
              <div className="min-w-0">
                <p className="text-sm font-medium">{entry.label} <span className="font-normal text-stone-500 dark:text-stone-400">· keep {entry.keep_years} year{entry.keep_years === 1 ? "" : "s"}</span></p>
                <p className="mt-1 text-xs leading-5 text-stone-600 dark:text-muted-foreground">{entry.description} {entry.items ? `Oldest ${entry.oldest!.slice(0, 10)}${entry.newest && entry.newest !== entry.oldest ? ` → newest ${entry.newest.slice(0, 10)}` : ""}.` : "Nothing stored."} {entry.action}</p>
              </div>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${entry.status === "due" ? "bg-danger-50 dark:bg-danger-950 text-danger-700 dark:text-danger-300" : entry.status === "within policy" ? "bg-brand-50 dark:bg-brand-950 text-brand-700 dark:text-brand-300" : "bg-stone-100 dark:bg-muted text-stone-600 dark:text-muted-foreground"}`}>
                {entry.status === "due" ? `${entry.due_for_review} due for review` : entry.status === "empty" ? "Empty" : `Until ${entry.first_due}`}
              </span>
            </div>
          ))}
          {!retention && <p className="text-sm text-stone-600 dark:text-muted-foreground">Loading the inventory…</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Content feedback</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {cohort.feedback.length ? cohort.feedback.map((entry) => (
            <div key={entry.id} className="rounded-xl border p-4">
              <div className="flex items-center gap-2">
                <MessageSquare size={15} className="text-stone-500 dark:text-stone-400" />
                <p className="text-sm font-medium">{entry.name}</p>
                <Badge variant="outline" className="capitalize">{entry.module_id}</Badge>
                <span className="ml-auto inline-flex items-center gap-1 text-sm tabular-nums text-stone-600 dark:text-muted-foreground"><Star size={14} className="fill-warn-400 text-warn-500" /> {entry.rating}/5</span>
              </div>
              {entry.comment && <p className="mt-2 leading-6 text-stone-600 dark:text-muted-foreground">{entry.comment}</p>}
            </div>
          )) : <p className="text-sm text-stone-600 dark:text-muted-foreground">No feedback yet. Learners can rate each module as they work through it.</p>}
        </CardContent>
      </Card>
    </div>
  );
}

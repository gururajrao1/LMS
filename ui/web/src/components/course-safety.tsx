"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getJson, Person, SafetyReport, sendJson } from "@/lib/api";

/**
 * Safety concerns raised from the field, and their triage.
 *
 * Reporting stays open to every assigned learner — silence is the failure
 * mode. Only staff with review rights see this list and mark reports
 * reviewed; the report itself is never edited, only triaged.
 */
export function CourseSafetyPanel({ runId, user }: { runId: string; user: Person }) {
  const [reports, setReports] = useState<SafetyReport[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const canTriage = (user.capabilities ?? []).includes("review.resolve") || (user.capabilities ?? []).includes("course.publish");

  const reload = () => getJson<SafetyReport[]>(`/api/runs/${runId}/safety?user_id=${user.id}`)
    .then(setReports).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load safety reports."));
  useEffect(() => { void reload(); }, [runId, user.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function triage(id: string) {
    setBusy(true); setError("");
    try {
      await sendJson(`/api/runs/${runId}/safety/${id}`, { user_id: user.id }, "PATCH");
      await reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not triage this report"); }
    finally { setBusy(false); }
  }

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><ShieldAlert size={18} /> Safety reports {reports.some((entry) => entry.status === "new") && <span className="rounded-full bg-danger-100 px-2 py-0.5 text-xs font-semibold text-danger-700 dark:text-danger-300">{reports.filter((entry) => entry.status === "new").length} new</span>}</CardTitle><p className="mt-2 text-sm text-stone-600 dark:text-muted-foreground">Concerns raised by the field. Learners report from training; triage happens here.</p></CardHeader>
      <CardContent className="space-y-3">
        {error && <p className="text-sm text-danger-600 dark:text-danger-300">{error}</p>}
        {reports.length === 0 && !error && <p className="text-sm text-stone-600 dark:text-muted-foreground">No safety concerns reported for this course.</p>}
        {reports.map((report) => (
          <div key={report.id} className="rounded-xl border p-4">
            <p className="leading-7">{report.concern}</p>
            <p className="mt-2 text-xs text-stone-500 dark:text-stone-400">Reported by {report.reporter_name} · {new Date(report.created_at).toLocaleString()}</p>
            {report.status === "reviewed"
              ? <p className="mt-2 flex items-center gap-1.5 text-sm font-medium text-brand-700 dark:text-brand-300"><CheckCircle2 size={15} /> Reviewed by {report.reviewed_by}</p>
              : canTriage && <Button variant="outline" disabled={busy} onClick={() => void triage(report.id)} className="mt-3">Mark triaged</Button>}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

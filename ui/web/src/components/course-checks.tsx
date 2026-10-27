"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, FileSearch, Quote, ScanLine, Send, ShieldCheck, TriangleAlert } from "lucide-react";
import { Stat } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckFinding, Checks, getJson, Person, sendJson, Severity } from "@/lib/api";

const CHECK_LABEL: Record<string, string> = {
  quote_not_found: "Quote not in source",
  quote_not_verbatim: "Quote not verbatim",
  untraceable: "No evidence collected",
  uncited: "No citation",
  promotional_only: "Promotional sources only",
  comparative_claim: "Comparative claim",
  unsupported: "Unsupported",
  overreach: "Overreach",
  needs_context: "Missing qualifier",
  under_cited: "Wrong citation attached",
  imprecise_effect: "Effect without its precision",
  not_covered: "Required topic not covered",
};

const SEVERITY: Record<Severity, string> = {
  blocking: "bg-danger-50 text-danger-700",
  major: "bg-warn-50 text-warn-700",
  minor: "bg-stone-100 text-stone-600",
};

function FindingCard({ finding, selectable, selected, onToggle }: {
  finding: CheckFinding;
  selectable: boolean;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <div className={`rounded-xl border p-4 ${selected ? "border-brand-600 bg-brand-50" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge className={SEVERITY[finding.severity]}>{finding.severity}</Badge>
        <Badge variant="outline">{CHECK_LABEL[finding.check] ?? finding.check}</Badge>
        <Badge variant="secondary" className="capitalize">{finding.asset}</Badge>
        {finding.promoted && (
          <span className="ml-auto inline-flex items-center gap-1.5 text-xs font-medium text-brand-700">
            <CheckCircle2 size={13} /> in the review queue{finding.promoted !== "open" ? ` · ${finding.promoted}` : ""}
          </span>
        )}
      </div>

      <p className="mt-3 font-medium leading-6">{finding.reference}</p>
      {finding.citations.length > 0 && (
        <p className="mt-1 text-xs text-stone-600">
          Citation: {finding.citations.map((citation) => `${citation.title ?? "Source"} · ${citation.locator}`).join(" | ")}
        </p>
      )}
      <p className="mt-1.5 leading-6 text-stone-700">{finding.message}</p>

      {(finding.asset_text || finding.source_text) && (
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {finding.asset_text && (
            <div className="rounded-lg bg-stone-50 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-600">What the course says</p>
              <p className="mt-1.5 text-sm leading-6 text-stone-700">{finding.asset_text}</p>
            </div>
          )}
          {finding.source_text && (
            <div className="rounded-lg border-l-2 border-brand-600 bg-brand-50 p-3">
              <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-stone-600">
                <Quote size={12} /> Recorded evidence
              </p>
              <p className="mt-1.5 text-sm leading-6 text-stone-700">{finding.source_text}</p>
            </div>
          )}
        </div>
      )}

      {finding.suggested_rewrite && (
        <p className="mt-3 rounded-lg bg-brand-50 p-3 text-sm leading-6 text-brand-800">
          <b>Suggested:</b> {finding.suggested_rewrite}
        </p>
      )}

      {selectable && !finding.promoted && (
        <label className="mt-3 inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-stone-700">
          <input type="checkbox" checked={selected} onChange={onToggle} className="size-4 accent-brand-600" />
          Send to the reviewer
        </label>
      )}
    </div>
  );
}

export function CourseChecksPanel({ runId, user, onChange }: { runId: string; user: Person; onChange?: () => void }) {
  const [checks, setChecks] = useState<Checks | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { getJson<Checks>(`/api/runs/${runId}/checks`).then(setChecks).catch(() => setError("Could not load the checks.")); }, [runId]);

  async function act(action: () => Promise<Checks>) {
    setBusy(true); setError("");
    try { setChecks(await action()); setSelected([]); onChange?.(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "That did not work"); }
    finally { setBusy(false); }
  }

  if (!checks) return <Card><CardContent className="p-8 text-center text-stone-600">{error || "Loading the checks…"}</CardContent></Card>;

  const admin = user.role === "admin";
  const stats = checks.stats;
  const blocking = checks.findings.filter((finding) => finding.severity === "blocking");
  const major = checks.findings.filter((finding) => finding.severity === "major");
  const minor = checks.findings.filter((finding) => finding.severity === "minor");
  const pendingMajor = major.filter((finding) => !finding.promoted);
  const grown = (checks.now?.coverage_percent ?? 0) > (stats.coverage_percent ?? 0);

  if (!checks.findings.length) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-4 p-12 text-center">
          <ScanLine size={30} className="text-stone-300" />
          <p className="text-stone-600">No automated checks have been run on this course yet.</p>
          {admin && (
            <Button disabled={busy} className="bg-brand-600 hover:bg-brand-800"
              onClick={() => act(() => sendJson<Checks>(`/api/runs/${runId}/checks`, { user_id: user.id }))}>
              <ScanLine /> {busy ? "Checking…" : "Run the checks"}
            </Button>
          )}
          {error && <p className="text-sm text-danger-600">{error}</p>}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      {/* The checker gets the signal hue wherever it appears, so a machine-raised
          finding is never mistaken for a colleague's. */}
      <section className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-signal-100 bg-signal-50 px-5 py-4">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-signal-600 text-white"><ScanLine size={18} /></span>
        <div className="min-w-0 flex-1">
          <p className="font-medium leading-6">Read before a human opened it</p>
          <p className="text-sm leading-6 text-stone-600">
            Every citable unit was checked against the stored source documents. Blocking findings are already in the review queue.
          </p>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={CircleAlert} value={blocking.length} label="Blocking — raised automatically" tone={blocking.length ? "warn" : "brand"} />
        <Stat icon={FileSearch} value={major.length} label={`Worth a look, across ${stats.units ?? 0} units`} />
        <Stat icon={Quote} value={`${stats.coverage_percent ?? 0}%`} label="Citations checkable against stored sources" tone="signal" />
        <Stat icon={ShieldCheck} value={checks.agreement.agreement_percent === null ? "–" : `${checks.agreement.agreement_percent}%`}
          label={`Reviewer agreement (${checks.agreement.settled} settled)`} />
      </section>

      <Card>
        <CardContent className="flex flex-col gap-3 p-5 text-sm text-stone-700 sm:flex-row sm:items-center sm:justify-between">
          <div className="leading-6">
            <p>
              {stats.verified ?? 0} quotes matched their source word for word, {stats.partial ?? 0} only partly.
              Coverage is limited to sources held in full — a citation we cannot open is reported as unverifiable, never as verified.
            </p>
            {/* The report is a snapshot of the draft. The corpus has grown since, and
                saying so is more honest than quietly restating the older figure. */}
            {grown && (
              <p className="mt-2 text-stone-600">
                Since this report was written the library has grown to <b className="text-stone-800">{checks.now!.documents} documents</b>,
                which would make <b className="text-stone-800">{checks.now!.coverage_percent}%</b> of citations checkable
                rather than {stats.coverage_percent ?? 0}%. Re-run to apply it to the findings.
              </p>
            )}
          </div>
          {admin && (
            <Button variant="outline" disabled={busy}
              onClick={() => act(() => sendJson<Checks>(`/api/runs/${runId}/checks`, { user_id: user.id }))}>
              <ScanLine /> {busy ? "Re-checking…" : "Re-run checks"}
            </Button>
          )}
        </CardContent>
      </Card>

      {error && <p className="text-sm text-danger-600">{error}</p>}

      {/* Calibration, deliberately not a leaderboard: counts always, a rate only
          where there is a sample behind it, and overrides shown separately because
          overruling the machine with a written reason is not the same as waving it
          away. The number that matters is whether the checker is worth its noise. */}
      {(checks.agreement.by_reviewer?.length ?? 0) > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">How the experts and the checker agree</CardTitle>
            <p className="mt-2 text-sm text-stone-600">
              A machine gate is only worth its noise if the experts who can overrule it usually do not. Rates are
              withheld below three settled findings — at that size the number describes the sample, not the reviewer.
            </p>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {checks.agreement.by_reviewer!.map((entry) => (
              <div key={entry.id || entry.name} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b pb-2.5 last:border-0 last:pb-0">
                <span className="font-medium text-stone-800">{entry.name}</span>
                {entry.title && <span className="text-xs text-stone-600">{entry.title}</span>}
                <span className="ml-auto text-sm tabular-nums text-stone-700">
                  {entry.accepted} accepted · {entry.dismissed} dismissed
                  {entry.overrides > 0 && <span className="text-warn-700"> · {entry.overrides} overridden</span>}
                </span>
                <span className="w-20 shrink-0 text-right text-sm font-semibold tabular-nums">
                  {entry.agreement_percent === null
                    ? <span className="font-normal text-stone-500">n={entry.settled}</span>
                    : `${entry.agreement_percent}%`}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {blocking.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><CircleAlert size={17} className="text-danger-600" /> Blocking ({blocking.length})</CardTitle>
            <p className="mt-2 text-sm text-stone-600">Raised automatically into the review queue. Publication stays blocked until a reviewer resolves them.</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {blocking.map((finding) => <FindingCard key={finding.id} finding={finding} selectable={false} selected={false} onToggle={() => undefined} />)}
          </CardContent>
        </Card>
      )}

      {major.length > 0 && (
        <Card>
          <CardHeader className="flex-row items-start justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2 text-base"><TriangleAlert size={17} className="text-warn-600" /> Worth a look ({major.length})</CardTitle>
              <p className="mt-2 text-sm text-stone-600">Not raised automatically. Choose which of these deserve a reviewer&apos;s time.</p>
            </div>
            {admin && pendingMajor.length > 0 && (
              <Button disabled={busy || !selected.length} className="bg-brand-600 hover:bg-brand-800"
                onClick={() => act(async () => {
                  const response = await sendJson<{ raised: number } & Checks>(
                    `/api/runs/${runId}/checks/promote`, { user_id: user.id, finding_ids: selected });
                  return response;
                })}>
                <Send /> Send {selected.length || ""} to review
              </Button>
            )}
          </CardHeader>
          <CardContent className="space-y-3">
            {major.map((finding) => (
              <FindingCard key={finding.id} finding={finding} selectable={admin} selected={selected.includes(finding.id)}
                onToggle={() => setSelected((current) => current.includes(finding.id)
                  ? current.filter((id) => id !== finding.id) : [...current, finding.id])} />
            ))}
          </CardContent>
        </Card>
      )}

      {minor.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Noted ({minor.length})</CardTitle>
            <p className="mt-2 text-sm text-stone-600">Recorded for completeness; no action expected.</p></CardHeader>
          <CardContent className="space-y-3">
            {minor.map((finding) => <FindingCard key={finding.id} finding={finding} selectable={admin} selected={selected.includes(finding.id)}
              onToggle={() => setSelected((current) => current.includes(finding.id)
                ? current.filter((id) => id !== finding.id) : [...current, finding.id])} />)}
          </CardContent>
        </Card>
      )}

      {checks.model_status && Object.entries(checks.model_status).some(([, value]) => value) && (
        <p className="text-xs leading-5 text-stone-600">
          {Object.entries(checks.model_status).map(([track, value]) => `${track ? `${track.toUpperCase()}: ` : ""}${value}`).join(" · ")}
        </p>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { Check, Minus, Send, TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Completeness, CoverageCell, CoverageState, getJson, Person, sendJson, Severity } from "@/lib/api";

const SEVERITY: Record<Severity, string> = {
  blocking: "bg-danger-50 text-danger-700",
  major: "bg-warn-50 text-warn-700",
  minor: "bg-stone-100 text-stone-600",
};

/**
 * Three states, not two. "Mentioned once" is the state a reviewer most needs
 * pointed out, because on a 101-unit course it reads as covered and is not.
 */
const STATE: Record<CoverageState, { label: string; cell: string; dot: string }> = {
  covered: { label: "Covered", cell: "bg-brand-50 text-brand-800", dot: "bg-brand-600" },
  thin: { label: "Mentioned once", cell: "bg-warn-50 text-warn-800", dot: "bg-warn-600" },
  missing: { label: "Not covered", cell: "bg-danger-50 text-danger-800", dot: "bg-danger-600" },
};

function Cell({ cell }: { cell: CoverageCell }) {
  if (!cell) {
    return (
      <td className="px-3 py-2.5 text-center text-stone-400" title="Not required of this audience">
        <Minus size={14} className="mx-auto" />
      </td>
    );
  }
  const state = STATE[cell.state];
  return (
    <td className="px-3 py-2.5">
      <span className={`flex items-center justify-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium ${state.cell}`}
        title={cell.units.map((unit) => unit.reference).join("\n") || "No unit addresses this"}>
        {cell.state === "covered" ? <Check size={12} /> : <span className={`size-1.5 rounded-full ${state.dot}`} />}
        {cell.total} {cell.total === 1 ? "unit" : "units"}
      </span>
    </td>
  );
}

export function CourseCompletenessPanel({ runId, user, onChange }: { runId: string; user: Person; onChange?: () => void }) {
  const [data, setData] = useState<Completeness | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getJson<Completeness>(`/api/runs/${runId}/completeness`)
      .then(setData)
      .catch(() => setError("Could not load the coverage matrix."));
  }, [runId]);

  if (!data) return <Card><CardContent className="p-8 text-center text-stone-600">{error || "Reading the course…"}</CardContent></Card>;

  const admin = user.role === "admin";
  const pending = data.gaps.filter((gap) => !gap.promoted);

  return (
    <div className="space-y-5">
      <section className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-line bg-white px-5 py-4">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-brand-600 text-white"><Check size={18} /></span>
        <div className="min-w-0 flex-1">
          <p className="font-medium leading-6">Is anything missing?</p>
          <p className="text-sm leading-6 text-stone-600">
            The accuracy checks ask whether what the course says is true. This asks whether anything a knowledgeable
            reader would expect is absent — {data.curriculum.name}, {data.curriculum.topics} required topics,
            last reviewed {data.curriculum.reviewed_on}.
          </p>
        </div>
        <p className="text-right">
          <span className="block text-2xl font-semibold tabular-nums">{data.stats.percent}%</span>
          <span className="text-sm text-stone-600">{data.stats.covered} of {data.stats.required} covered</span>
        </p>
      </section>

      {error && <p className="text-sm text-danger-600">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Coverage matrix</CardTitle>
          <p className="mt-2 text-sm text-stone-600">
            A topic counts as covered when at least {data.rows[0]?.min_units ?? 2} units address it. Matching detects
            whether a topic is addressed at all, never whether it is addressed well — that judgement stays with you.
          </p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[34rem] text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-stone-500">
                  <th className="py-2 pr-3 font-medium">Required topic</th>
                  {data.tracks.map((track) => (
                    <th key={track} className="px-3 py-2 text-center font-medium">{track.toUpperCase()}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.id} className="border-b last:border-0 align-middle">
                    <td className="py-2.5 pr-3">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-stone-800">{row.title}</span>
                        <Badge className={`${SEVERITY[row.severity]} text-[11px]`}>{row.severity}</Badge>
                      </span>
                      <span className="mt-0.5 block text-xs leading-5 text-stone-600">{row.why}</span>
                    </td>
                    {data.tracks.map((track) => <Cell key={track} cell={row.tracks[track]} />)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {data.gaps.length > 0 && (
        <Card>
          <CardHeader className="flex-row items-start justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <TriangleAlert size={17} className="text-warn-600" /> Gaps ({data.gaps.length})
              </CardTitle>
              <p className="mt-2 text-sm text-stone-600">
                Raise these into the review queue and they behave like any other comment: an expert addresses or
                dismisses them, and publication waits on the blocking ones.
              </p>
            </div>
            {admin && pending.length > 0 && (
              <Button disabled={busy || !selected.length} className="w-fit shrink-0 self-start bg-brand-600 hover:bg-brand-800"
                onClick={async () => {
                  setBusy(true); setError("");
                  try {
                    setData(await sendJson<Completeness>(`/api/runs/${runId}/completeness/promote`,
                      { user_id: user.id, finding_ids: selected }));
                    setSelected([]); onChange?.();
                  } catch (reason) {
                    setError(reason instanceof Error ? reason.message : "That did not work");
                  } finally { setBusy(false); }
                }}>
                <Send /> Send {selected.length || ""} to review
              </Button>
            )}
          </CardHeader>
          <CardContent className="space-y-3">
            {data.gaps.map((gap) => (
              <div key={gap.finding_id}
                className={`rounded-xl border p-4 ${selected.includes(gap.finding_id) ? "border-brand-600 bg-brand-50" : ""}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge className={SEVERITY[gap.severity]}>{gap.severity}</Badge>
                  <Badge variant="outline">{STATE[gap.state].label}</Badge>
                  <Badge variant="secondary">{gap.track.toUpperCase()}</Badge>
                  {gap.promoted && (
                    <span className="ml-auto text-xs font-medium text-brand-700">
                      in the review queue{gap.promoted !== "open" ? ` · ${gap.promoted}` : ""}
                    </span>
                  )}
                </div>
                <p className="mt-3 font-medium leading-6">{gap.title}</p>
                <p className="mt-1.5 leading-6 text-stone-700">
                  {gap.state === "missing"
                    ? `Nothing in the ${gap.track.toUpperCase()} track addresses this.`
                    : `Only ${gap.units} unit of the ${gap.track.toUpperCase()} track mentions this, below the ${gap.expected} expected. It reads as covered but is not.`}
                </p>
                <p className="mt-1.5 text-sm leading-6 text-stone-600">{gap.why}</p>
                {admin && !gap.promoted && (
                  <label className="mt-3 inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-stone-700">
                    <input type="checkbox" className="size-4 accent-brand-600"
                      checked={selected.includes(gap.finding_id)}
                      onChange={() => setSelected((current) => current.includes(gap.finding_id)
                        ? current.filter((id) => id !== gap.finding_id)
                        : [...current, gap.finding_id])} />
                    Send to the reviewer
                  </label>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

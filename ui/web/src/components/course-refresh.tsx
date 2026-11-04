"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getJson } from "@/lib/api";

type RefreshDiff = {
  run_id: string;
  against: string;
  added: string[];
  removed: string[];
  changed: string[];
  changed_count: number;
  recertification_required: boolean;
  note: string;
};

function IdList({ title, ids }: { title: string; ids: string[] }) {
  if (!ids.length) return null;
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-stone-500">{title} ({ids.length})</p>
      <ul className="mt-1 space-y-1 text-sm">
        {ids.map((id) => <li key={id} className="rounded bg-stone-50 px-2 py-1 font-mono text-xs">{id}</li>)}
      </ul>
    </div>
  );
}

/** Label-change refresh: compare this version against an earlier run. */
export function CourseRefreshPanel({ runId }: { runId: string }) {
  const [against, setAgainst] = useState("");
  const [diff, setDiff] = useState<RefreshDiff | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function compare(event: FormEvent) {
    event.preventDefault();
    if (!against.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      setDiff(await getJson<RefreshDiff>(`/api/runs/${runId}/refresh/diff?against=${encodeURIComponent(against.trim())}`));
    } catch {
      setError("Could not compare — check the other run id.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Label-change refresh</CardTitle>
        <p className="mt-2 text-sm text-stone-600">Compare this version against an earlier run to see what must be re-reviewed.</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="flex gap-2" onSubmit={compare}>
          <Input value={against} onChange={(event) => setAgainst(event.target.value)} placeholder="Earlier run id, e.g. ibrance-cycle-label-update" className="max-w-md" />
          <Button type="submit" disabled={busy}>Compare</Button>
        </form>
        {error && <p className="text-sm text-danger-600">{error}</p>}
        {diff && (
          <div className="space-y-3 rounded-xl border bg-surface-sunk p-4">
            <p className="text-sm">
              {diff.changed_count === 0
                ? "No question changes — nothing to re-review."
                : `${diff.changed_count} question${diff.changed_count === 1 ? "" : "s"} changed.`}{" "}
              {diff.recertification_required && <b>Re-certification required: certificates stamp the version.</b>}
            </p>
            <IdList title="Changed" ids={diff.changed} />
            <IdList title="Added" ids={diff.added} />
            <IdList title="Removed" ids={diff.removed} />
            <p className="text-xs text-stone-600">{diff.note}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

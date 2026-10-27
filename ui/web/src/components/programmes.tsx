"use client";

import Link from "next/link";
import { useState } from "react";
import { Archive, CalendarClock, RotateCcw, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ClientProgrammes, Person, Programme, ProgrammeState, sendJson } from "@/lib/api";
import { PromptDialog } from "@/components/prompt-dialog";

/**
 * State is derived from the calendar and the cohort on every read, so these labels
 * cannot go stale the way a stored status would. Only "archived" is a stored
 * decision, and it reads as neutral rather than negative — filing, not failure.
 */
const STATE: Record<ProgrammeState, { label: string; className: string }> = {
  draft: { label: "Not published", className: "bg-stone-100 text-stone-600" },
  scheduled: { label: "Scheduled", className: "bg-signal-50 text-signal-700" },
  live: { label: "Live", className: "bg-brand-50 text-brand-700" },
  completed: { label: "Completed", className: "bg-stone-100 text-stone-700" },
  archived: { label: "Archived", className: "bg-stone-100 text-stone-500" },
};

function when(value: string | null) {
  return value ? new Date(value).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "—";
}

function deadline(programme: Programme) {
  const { state, days_remaining: days } = programme;
  if (state === "archived" || days === null) return null;
  if (state === "scheduled") return `starts ${when(programme.starts_on)}`;
  if (state === "completed") return `closed ${when(programme.due_on)}`;
  if (days === 0) return "due today";
  return days > 0 ? `${days} day${days === 1 ? "" : "s"} left` : `${-days} days overdue`;
}

function ProgrammeRow({ programme, user, onChange }: {
  programme: Programme;
  user: Person;
  onChange: () => void;
}) {
  const admin = user.role === "admin";
  const [busy, setBusy] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const { cohort } = programme;
  const state = STATE[programme.state];

  async function act(path: string, body: Record<string, unknown>) {
    setBusy(true);
    try { await sendJson(path, body); onChange(); } finally { setBusy(false); }
  }

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-3 border-b py-4 last:border-0 last:pb-0">
      <div className="min-w-[11rem] flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link href={`/courses/${programme.run_id}`} className="font-medium text-stone-900 hover:underline">
            {programme.title ?? programme.drug.brand}
          </Link>
          <Badge className={state.className}>{state.label}</Badge>
          <span className="text-xs text-stone-600">v{programme.version}</span>
          {programme.overrides > 0 && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-warn-700"
              title="Published with a still-failing check, overridden on the record">
              <ShieldAlert size={12} /> {programme.overrides} override{programme.overrides === 1 ? "" : "s"}
            </span>
          )}
        </div>
        {/* The therapeutic area only. The full indication string belongs on the
            course, where it is shown against the checks that scrutinise it — a list
            row repeating a licensed-use claim out of context is how they spread. */}
        <p className="mt-1 text-sm text-stone-600">
          {programme.title ? `${programme.drug.brand} · ` : ""}{programme.drug.generic} ·{" "}
          {programme.drug.area.split(/[–—-]/)[0].trim()}
          {programme.reuses ? " · reuses approved content" : ""}
        </p>
      </div>

      <div className="min-w-[10rem] text-sm text-stone-700">
        <p className="flex items-center gap-1.5"><CalendarClock size={14} className="text-stone-500" />
          {when(programme.starts_on)} – {when(programme.due_on)}</p>
        {deadline(programme) && <p className="mt-0.5 pl-[1.375rem] text-xs text-stone-600">{deadline(programme)}</p>}
      </div>

      <div className="min-w-[9rem] text-sm tabular-nums text-stone-700">
        <p><b>{cohort.certified}</b> of {cohort.assigned} certified</p>
        <p className="mt-0.5 text-xs text-stone-600">
          {cohort.average_uplift === null ? "no paired scores yet" : `+${cohort.average_uplift} pts average uplift`}
        </p>
      </div>

      {admin && (
        <div className="flex items-center gap-2">
          {programme.state === "archived" ? (
            <Button size="sm" variant="ghost" disabled={busy}
              onClick={() => act(`/api/runs/${programme.run_id}/restore`, { user_id: user.id })}>
              <RotateCcw /> Restore
            </Button>
          ) : (
            <>
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => setArchiving(true)}>
                <Archive /> Archive
              </Button>
              {archiving && (
                <PromptDialog
                  open
                  busy={busy}
                  title="Archive this programme?"
                  description="It comes out of the running list. Nothing is deleted, and it can be restored."
                  label="Why is it being archived?"
                  placeholder="Superseded by the 2026 recertification cycle."
                  confirmLabel="Archive"
                  onCancel={() => setArchiving(false)}
                  onConfirm={async (note) => {
                    await act(`/api/runs/${programme.run_id}/archive`, { user_id: user.id, note });
                    setArchiving(false);
                  }}
                />
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function ProgrammesPanel({ data, user, onChange }: {
  data: ClientProgrammes;
  user: Person;
  onChange: () => void;
}) {
  const [showArchived, setShowArchived] = useState(false);
  const visible = data.programmes.filter((entry) => showArchived || entry.state !== "archived");
  const archived = data.states.archived ?? 0;

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-4">
        <div>
          <CardTitle className="text-base">{data.client.name} · training programmes</CardTitle>
          <p className="mt-2 text-sm text-stone-600">
            {data.states.live} live · {data.states.scheduled} scheduled · {data.states.completed} completed
            {archived > 0 && ` · ${archived} archived`}. State is read from the schedule and the cohort each time,
            so it is never a label someone forgot to change.
          </p>
        </div>
        {archived > 0 && (
          <Button size="sm" variant="outline" className="shrink-0" onClick={() => setShowArchived((current) => !current)}>
            {showArchived ? "Hide" : "Show"} archived
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {visible.length ? (
          visible.map((programme) => (
            <ProgrammeRow key={programme.run_id} programme={programme} user={user} onChange={onChange} />
          ))
        ) : (
          <p className="py-6 text-center text-sm text-stone-600">
            No programme is running yet. Publish a course to a cohort and it appears here.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

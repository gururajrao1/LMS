"use client";

import { useEffect, useState } from "react";
import { GitBranch } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getJson } from "@/lib/api";

type TimelineEvent = { at: string | null; kind: string; title: string; detail: string; actor: string };

const KIND_LABEL: Record<string, { label: string; className: string }> = {
  version: { label: "Version", className: "bg-brand-50 dark:bg-brand-950 text-brand-700 dark:text-brand-300" },
  signoff: { label: "Sign-off", className: "bg-stone-900 text-white" },
  publication: { label: "Published", className: "bg-warn-50 dark:bg-warn-950 text-warn-700 dark:text-warn-400" },
  assignment: { label: "Assigned", className: "bg-stone-100 dark:bg-muted text-stone-700 dark:text-stone-200" },
};

/** How this course got here: versions, sign-offs and publications, oldest first. */
export function CourseHistoryPanel({ runId }: { runId: string }) {
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [status, setStatus] = useState("");

  useEffect(() => {
    getJson<{ events: TimelineEvent[]; status: string }>(`/api/runs/${runId}/timeline`)
      .then((timeline) => { setEvents(timeline.events); setStatus(timeline.status); })
      .catch(() => setEvents([]));
  }, [runId]);

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><GitBranch size={17} className="text-brand-700 dark:text-brand-300" /> Version history{status ? ` · ${status}` : ""}</CardTitle>
        <p className="mt-2 text-sm text-stone-600 dark:text-muted-foreground">Upversioning on the record: every version, who signed it off, and what was published.</p>
      </CardHeader>
      <CardContent>
        {!events ? <p className="py-4 text-center text-sm text-stone-600 dark:text-muted-foreground">Loading the timeline…</p>
          : !events.length ? <p className="py-4 text-center text-sm text-stone-600 dark:text-muted-foreground">Nothing recorded yet.</p>
            : (
              <ol className="relative space-y-0 border-l-2 border-stone-200 dark:border-line pl-0">
                {events.map((event, index) => (
                  <li key={`${event.kind}-${event.title}-${index}`} className="relative pb-6 pl-8 last:pb-0">
                    <span aria-hidden className="absolute top-1 left-[-7px] size-3 rounded-full border-2 border-white bg-brand-600" />
                    <p className="flex flex-wrap items-center gap-2 text-sm">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${KIND_LABEL[event.kind]?.className ?? "bg-stone-100 dark:bg-muted text-stone-600 dark:text-muted-foreground"}`}>
                        {KIND_LABEL[event.kind]?.label ?? event.kind}
                      </span>
                      <b>{event.title}</b>
                    </p>
                    {event.detail && <p className="mt-1 text-sm leading-6 text-stone-600 dark:text-muted-foreground">{event.detail}</p>}
                    <p className="mt-1 text-xs text-stone-500 dark:text-stone-400">
                      {event.actor}{event.at ? ` · ${new Date(event.at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}` : ""}
                    </p>
                  </li>
                ))}
              </ol>
            )}
      </CardContent>
    </Card>
  );
}

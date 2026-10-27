"use client";

import { FormEvent, useEffect, useState } from "react";
import { CalendarDays, CircleAlert, Mail, Send, ShieldAlert, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ROLE_LABEL } from "@/components/app-shell";
import { CourseReview, getJson, Person, sendJson } from "@/lib/api";

function isoDate(offsetDays: number) {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  return date.toISOString().slice(0, 10);
}

export function CoursePublishPanel({ runId, user, review, onChange }: { runId: string; user: Person; review: CourseReview; onChange: (review: CourseReview) => void }) {
  const published = review.publication;
  const [people, setPeople] = useState<Person[]>([]);
  const [assignees, setAssignees] = useState<string[]>(published?.assignees ?? []);
  const [startsOn, setStartsOn] = useState(published?.starts_on ?? isoDate(0));
  const [dueOn, setDueOn] = useState(published?.due_on ?? isoDate(30));
  const [message, setMessage] = useState(published?.message ?? "Complete this course before the next cycle meeting.");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getJson<Person[]>("/api/people").then((roster) => {
      const learners = roster.filter((person) => person.role === "msl" || person.role === "hcp");
      setPeople(learners);
      setAssignees((current) => (current.length ? current : learners.map((person) => person.id)));
    }).catch(() => setError("Could not load the trainee roster."));
  }, []);

  async function publish(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      await sendJson(`/api/runs/${runId}/publication`, { user_id: user.id, starts_on: startsOn, due_on: dueOn, assignees, message });
      onChange(await getJson<CourseReview>(`/api/runs/${runId}/review`));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not publish"); }
    finally { setBusy(false); }
  }

  const toggle = (id: string) => setAssignees((current) => current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id]);
  const blocked = !review.readiness.can_publish;
  const publication = published;

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
      <Card>
        <CardHeader>
          <CardTitle>{publication ? "Update the training plan" : "Publish and schedule"}</CardTitle>
          <p className="mt-2 text-sm text-stone-600">Assign the course, set the window, and notify every trainee.</p>
        </CardHeader>
        <CardContent>
          {blocked && (
            <div className="mb-5 flex gap-3 rounded-xl bg-warn-50 p-4 text-sm text-warn-900">
              <CircleAlert size={18} className="mt-0.5 shrink-0" />
              <div>
                <p className="font-medium">Not ready to publish</p>
                <p className="mt-1 leading-6">
                  {review.readiness.open_blocking > 0 && `${review.readiness.open_blocking} blocking comment(s) are still open. `}
                  {review.readiness.changes_requested > 0 && `${review.readiness.changes_requested} reviewer(s) requested changes at v${review.version}. `}
                  {!review.readiness.approvals && "An approving sign-off is required."}
                </p>
              </div>
            </div>
          )}
          <form onSubmit={publish} className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="starts-on" className="text-sm font-medium">Training starts</label>
                <Input id="starts-on" type="date" value={startsOn} onChange={(event) => setStartsOn(event.target.value)} className="mt-2 h-9" />
              </div>
              <div>
                <label htmlFor="due-on" className="text-sm font-medium">Completion due</label>
                <Input id="due-on" type="date" value={dueOn} onChange={(event) => setDueOn(event.target.value)} className="mt-2 h-9" />
              </div>
            </div>

            <div>
              <p className="text-sm font-medium">Trainees ({assignees.length} selected)</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {people.map((person) => (
                  <label key={person.id} className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors ${assignees.includes(person.id) ? "border-brand-600 bg-brand-50" : "hover:bg-stone-50"}`}>
                    <input type="checkbox" checked={assignees.includes(person.id)} onChange={() => toggle(person.id)} className="mt-1 size-4 accent-brand-600" />
                    <span>
                      <span className="block text-sm font-medium">{person.name}</span>
                      <span className="block text-xs text-stone-600">{ROLE_LABEL[person.role]} · {person.title}</span>
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label htmlFor="publish-message" className="text-sm font-medium">Message to trainees</label>
              <Textarea id="publish-message" value={message} onChange={(event) => setMessage(event.target.value)} rows={3} className="mt-2" />
            </div>

            {error && <p className="text-sm text-danger-600">{error}</p>}
            <Button type="submit" disabled={busy || blocked || !assignees.length} className="bg-brand-600 hover:bg-brand-800">
              <Send /> {publication ? "Republish schedule" : `Publish v${review.version} to ${assignees.length} trainee(s)`}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-5">
        <Card>
          <CardHeader><CardTitle className="text-base">Publication status</CardTitle></CardHeader>
          <CardContent>
            {publication ? (
              <div className="space-y-3 text-sm">
                <Badge className="bg-brand-600">Published v{publication.version}</Badge>
                <p className="flex items-center gap-2 text-stone-600"><CalendarDays size={15} /> {publication.starts_on} → {publication.due_on}</p>
                <p className="flex items-center gap-2 text-stone-600"><Users size={15} /> {publication.assignees.length} trainee(s)</p>
                <p className="text-xs text-stone-600">Published by {publication.published_by}</p>
              </div>
            ) : <p className="text-sm text-stone-600">This course has not been published yet.</p>}
          </CardContent>
        </Card>

        {publication?.overrides?.length ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <ShieldAlert size={17} className="text-warn-600" /> Published with {publication.overrides.length} override(s)
              </CardTitle>
              <p className="mt-2 text-sm text-stone-600">
                Checks that still fail against the stored sources, carried through on a named
                decision. This travels with the course; it is not cleared by publishing.
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              {publication.overrides.map((override) => (
                <div key={override.comment_id} className="rounded-xl border border-warn-600/30 bg-warn-50 p-3">
                  <p className="text-sm font-medium text-warn-900">
                    {override.check} on {override.target}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-stone-700">{override.reason}</p>
                  <p className="mt-2 text-xs text-stone-600">
                    {override.actor_name}{override.actor_title ? ` · ${override.actor_title}` : ""}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        ) : null}

        {publication && (
          <Card>
            <CardHeader><CardTitle className="text-base">Notifications sent</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {publication.notifications.map((entry) => (
                <div key={entry.to} className="flex gap-3 rounded-lg border p-3">
                  <Mail size={15} className="mt-0.5 shrink-0 text-brand-700" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{entry.name}</p>
                    <p className="truncate text-xs text-stone-600">{entry.to}</p>
                    <p className="mt-1 text-xs leading-5 text-stone-600">{entry.subject}</p>
                  </div>
                </div>
              ))}
              <p className="text-xs text-stone-500">Demo notifications are recorded locally, not emailed.</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

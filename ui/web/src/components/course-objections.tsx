"use client";

import { useEffect, useState } from "react";
import { MessageCircle, Pencil, Plus, Undo2 } from "lucide-react";
import { Cites } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getJson, Objection, Person, sendJson } from "@/lib/api";

/**
 * Approved answers to the objections HCPs raise in the field.
 *
 * Written once by the training team, read by every trainee and shown on the
 * learner side verbatim. Retirement keeps the record — a retracted answer
 * disappears from training but stays in the audit trail.
 */
export function CourseObjectionsPanel({ runId, user }: { runId: string; user: Person }) {
  const [items, setItems] = useState<Objection[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const canManage = (user.capabilities ?? []).includes("course.publish");

  const reload = () => getJson<Objection[]>(`/api/runs/${runId}/objections`).then(setItems).catch(() => setError("Could not load approved answers."));
  useEffect(() => { void reload(); }, [runId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit() {
    if (!question.trim() || !answer.trim()) return;
    setBusy(true); setError("");
    try {
      if (editing) {
        await sendJson(`/api/runs/${runId}/objections/${editing}`, { user_id: user.id, question: question.trim(), answer: answer.trim() }, "PATCH");
      } else {
        await sendJson(`/api/runs/${runId}/objections`, { user_id: user.id, question: question.trim(), answer: answer.trim() }, "POST");
      }
      setQuestion(""); setAnswer(""); setEditing(null);
      await reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save this answer"); }
    finally { setBusy(false); }
  }

  async function retire(id: string, retired: boolean) {
    setBusy(true); setError("");
    try {
      await sendJson(`/api/runs/${runId}/objections/${id}`, { user_id: user.id, retired }, "PATCH");
      await reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update this answer"); }
    finally { setBusy(false); }
  }

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><MessageCircle size={18} /> Objection handling</CardTitle><p className="mt-2 text-sm text-stone-600">One approved answer per hard question. Trainees read these verbatim on the learning side.</p></CardHeader>
      <CardContent className="space-y-4">
        {error && <p className="text-sm text-danger-600">{error}</p>}
        {items.map((item) => (
          <div key={item.id} className="rounded-xl border p-4">
            <p className="font-semibold">{item.question}</p>
            <p className="mt-2 text-sm leading-7 text-stone-600">{item.answer}</p>
            <p className="mt-2 text-xs text-stone-500">Approved by {item.author_name}</p>
            <Cites runId={runId} citations={item.citations} />
            {canManage && (
              <div className="mt-3 flex gap-2">
                <Button variant="outline" disabled={busy} onClick={() => { setEditing(item.id); setQuestion(item.question); setAnswer(item.answer); }}><Pencil size={14} /> Edit</Button>
                <Button variant="outline" disabled={busy} onClick={() => void retire(item.id, true)}><Undo2 size={14} /> Retire</Button>
              </div>
            )}
          </div>
        ))}
        {canManage && (
          <div className="rounded-xl border border-dashed p-4">
            <p className="font-semibold">{editing ? "Edit approved answer" : "Add an approved answer"}</p>
            <Input className="mt-3" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="The objection, in the HCP's words" />
            <Textarea className="mt-3" value={answer} onChange={(event) => setAnswer(event.target.value)} rows={3} placeholder="The approved response, with the evidence behind it" />
            <div className="mt-3 flex gap-2">
              <Button disabled={busy || !question.trim() || !answer.trim()} onClick={() => void submit()} className="bg-brand-600 hover:bg-brand-800"><Plus size={16} /> {editing ? "Save changes" : "Publish answer"}</Button>
              {editing && <Button variant="outline" onClick={() => { setEditing(null); setQuestion(""); setAnswer(""); }}>Cancel</Button>}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

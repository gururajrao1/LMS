"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ExternalLink, Search, Send, Sparkles, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ChatReply, ChatStarters, Citation, getJson, Learner, sendJson } from "@/lib/api";

type Turn = { id: number; question: string; reply?: ChatReply; error?: string };

/** Where the answer came from. Named on every reply so nothing has to be assumed. */
const MODE: Record<ChatReply["mode"], string> = {
  model: "Model answer",
  retrieval: "Dossier retrieval",
  record: "From the record",
};

function Sources({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null;
  return (
    <div className="mt-3 space-y-1.5 border-t pt-3">
      {citations.map((citation, index) => (
        <a key={`${citation.title}-${citation.locator}-${index}`} href={citation.url} target="_blank" rel="noreferrer"
          className="flex items-start gap-2 text-xs leading-5 text-brand-700 hover:underline">
          <ExternalLink size={13} className="mt-0.5 shrink-0" />
          <span>{citation.title} · {citation.locator}</span>
        </a>
      ))}
    </div>
  );
}

export function CourseChat({ runId, learner, context = "material", userId, title = "Ask the course", blurb, onClose, fill = false }: {
  runId: string;
  learner: Learner;
  /** Which surface the reader is on. Decides which starter questions are offered. */
  context?: string;
  /** Set for a trainee, so "when is this due" answers about them, not the cohort. */
  userId?: string;
  title?: string;
  blurb?: string;
  onClose?: () => void;
  /** Stretch to the height of the container rather than sizing to the log. */
  fill?: boolean;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [starters, setStarters] = useState<ChatStarters["starters"]>([]);
  const log = useRef<HTMLDivElement>(null);
  const nextId = useRef(0);

  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" }); }, [turns]);

  // Fetched rather than hard-coded: the server only offers a question it has
  // checked it can answer, so a suggestion can never lead somewhere empty.
  useEffect(() => {
    let live = true;
    getJson<ChatStarters>(`/api/runs/${runId}/chat/starters?context=${encodeURIComponent(context)}`)
      .then((value) => { if (live) setStarters(value.starters); })
      .catch(() => { if (live) setStarters([]); });
    return () => { live = false; };
  }, [runId, context]);

  async function ask(value: string) {
    const text = value.trim();
    if (!text || busy) return;
    const id = (nextId.current += 1);
    setTurns((current) => [...current, { id, question: text }]);
    setQuestion(""); setBusy(true);
    try {
      const reply = await sendJson<ChatReply>(`/api/runs/${runId}/chat`, { question: text, learner, user_id: userId ?? "" });
      setTurns((current) => current.map((turn) => turn.id === id ? { ...turn, reply } : turn));
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "The assistant is unavailable";
      setTurns((current) => current.map((turn) => turn.id === id ? { ...turn, error: message } : turn));
    } finally { setBusy(false); }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    ask(question);
  }

  return (
    <Card className={fill ? "flex h-full flex-col gap-0 overflow-hidden rounded-none border-0 p-0 shadow-none" : "overflow-hidden p-0"}>
      <div className="border-b bg-white p-4">
        <div className="flex items-start justify-between gap-3">
          <p className="flex items-center gap-2 font-semibold"><Sparkles size={17} className="shrink-0 text-brand-700" /> {title}</p>
          <div className="flex shrink-0 items-center gap-2">
            {turns.some((turn) => turn.reply) && (
              <Badge variant="secondary">{MODE[turns.findLast((turn) => turn.reply)!.reply!.mode]}</Badge>
            )}
            {onClose && (
              <button type="button" onClick={onClose} aria-label="Close the assistant" className="-mr-1 rounded-lg p-1 text-stone-500 hover:bg-stone-100">
                <X size={16} />
              </button>
            )}
          </div>
        </div>
        <p className="mt-1.5 text-sm leading-5 text-stone-600">{blurb ?? "Answers come only from this course's cited dossier."}</p>
      </div>

      <CardContent ref={log} className={`space-y-4 overflow-y-auto overscroll-contain p-4 ${fill ? "min-h-0 flex-1" : "max-h-[min(26rem,55vh)]"}`}>
        {!turns.length && starters.length > 0 && (
          <div className="space-y-3">
            <p className="flex items-center gap-2 text-sm text-stone-600">
              <Search size={15} /> Questions this page tends to raise:
            </p>
            <div className="flex flex-col gap-2">
              {starters.map((starter) => (
                <button key={starter.question} type="button" onClick={() => ask(starter.question)}
                  className="flex items-start gap-2 rounded-lg border px-3 py-2 text-left text-xs font-medium leading-5 text-stone-700 transition-colors hover:border-brand-600 hover:bg-brand-50">
                  <span className="flex-1">{starter.question}</span>
                  {/* Says where the answer will come from before it is asked: the
                      programme's own record, or the cited dossier. */}
                  <span className="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-500">
                    {starter.kind === "record" ? "record" : "sources"}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
        {turns.map((turn) => (
          <div key={turn.id} className="space-y-3">
            <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-surface-deep px-4 py-2.5 text-sm text-white">{turn.question}</p>
            {turn.reply && (
              <div className="w-fit max-w-[92%] rounded-2xl rounded-bl-sm bg-stone-50 px-4 py-3">
                <p className="whitespace-pre-line text-sm leading-6 text-stone-700">{turn.reply.answer}</p>
                <Sources citations={turn.reply.citations} />
              </div>
            )}
            {turn.error && <p className="text-sm text-danger-600">{turn.error}</p>}
            {!turn.reply && !turn.error && <p className="text-sm text-stone-500">Searching the dossier…</p>}
          </div>
        ))}
      </CardContent>

      <form onSubmit={submit} className="flex gap-2 border-t bg-white p-3">
        <Input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about dosing, safety, evidence…" className="h-10" />
        <Button type="submit" disabled={busy || !question.trim()} className="h-10 bg-brand-600 hover:bg-brand-800"><Send /> Ask</Button>
      </form>
    </Card>
  );
}

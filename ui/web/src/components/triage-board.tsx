"use client";

import { useState } from "react";
import { Check, RotateCcw, X } from "lucide-react";
import { Cites } from "@/components/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { AskedQuestion, QuestionGroup, ReviewedQuestion } from "@/lib/api";

/**
 * The sort board — the gamified assessment format.
 *
 * One item at a time, two buckets, tap to place. Deliberately taps rather than
 * drag-and-drop: dragging is unusable on a touch screen held one-handed, is a
 * real accessibility problem, and is slower than pressing the bucket you mean.
 * The game here is the pace and the immediacy, not the gesture.
 *
 * Nothing about scoring lives in this component. Each item is an ordinary
 * question the server sent, and placing it in a bucket sets the same answer a
 * radio button would.
 */

function Chip({ label, tone, onClick }: { label: string; tone: string; onClick?: () => void }) {
  const Element = onClick ? "button" : "div";
  return (
    <Element
      {...(onClick ? { type: "button" as const, onClick } : {})}
      className={`w-full rounded-lg border px-3 py-2 text-left text-sm leading-5 ${tone} ${
        onClick ? "transition-colors hover:border-stone-400" : ""}`}
    >
      {label}
    </Element>
  );
}

export function TriageBoard({ group, items, answers, onAnswer, reviewed, runId }: {
  group: QuestionGroup;
  items: AskedQuestion[];
  answers: Record<string, number>;
  /** `null` clears the placement — an item with no answer is unplaced, not wrong. */
  onAnswer: (id: string, bucket: number | null) => void;
  reviewed?: Map<string, ReviewedQuestion>;
  runId?: string;
}) {
  // Placing an item reveals the next unplaced one, so the deck moves forward on
  // its own. Kept as an index into the unplaced list rather than a queue of its
  // own, so going back to change an answer cannot desynchronise the two.
  const [reopened, setReopened] = useState<string | null>(null);
  const done = Boolean(reviewed);
  const pending = items.filter((item) => answers[item.id] === undefined);
  const current = done ? null : items.find((item) => item.id === reopened) ?? pending[0] ?? null;
  const placed = items.length - pending.length;
  const buckets = group.buckets ?? [];

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b bg-stone-50 px-6 py-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-brand-700">Sort board</p>
          <h3 className="mt-1 font-semibold leading-6">{group.title}</h3>
        </div>
        <p className="text-sm tabular-nums text-stone-600">{placed} of {items.length} sorted</p>
      </div>

      <CardContent className="p-6">
        <p className="text-sm leading-6 text-stone-600">{group.instruction}</p>

        {current && (
          <div className="mt-5 rounded-xl border-2 border-brand-600 bg-white p-5 shadow-sm">
            <p className="text-lg font-medium leading-7">{current.prompt}</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {buckets.map((bucket, index) => (
                <button key={bucket} type="button"
                  onClick={() => { onAnswer(current.id, index); setReopened(null); }}
                  className="rounded-lg border border-stone-300 bg-white px-4 py-3 text-sm font-medium transition-colors hover:border-brand-600 hover:bg-brand-50 hover:text-brand-800">
                  {bucket}
                </button>
              ))}
            </div>
          </div>
        )}

        {!current && !done && (
          <p className="mt-5 rounded-xl border border-brand-600 bg-brand-50 px-5 py-4 text-sm text-brand-800">
            Every item is placed. Tap any card below to move it before you submit.
          </p>
        )}

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {buckets.map((bucket, index) => {
            const inBucket = items.filter((item) => answers[item.id] === index);
            return (
              <div key={bucket}>
                <p className="flex items-baseline justify-between gap-2 border-b pb-2 text-sm font-semibold">
                  {bucket} <span className="tabular-nums font-normal text-stone-500">{inBucket.length}</span>
                </p>
                <div className="mt-2 space-y-2">
                  {inBucket.map((item) => {
                    const result = reviewed?.get(item.id);
                    if (!result) {
                      return (
                        <Chip key={item.id} label={item.prompt} tone="border-stone-200 bg-white text-stone-700"
                          onClick={() => setReopened(item.id)} />
                      );
                    }
                    return (
                      <div key={item.id} className={`rounded-lg border p-3 text-sm ${result.correct
                        ? "border-brand-600 bg-brand-50" : "border-danger-600 bg-danger-50"}`}>
                        <p className="flex items-start gap-2 leading-5">
                          {result.correct
                            ? <Check size={15} className="mt-0.5 shrink-0 text-brand-700" />
                            : <X size={15} className="mt-0.5 shrink-0 text-danger-600" />}
                          <span>{item.prompt}</span>
                        </p>
                        {!result.correct && (
                          <p className="mt-2 pl-[1.4rem] text-xs font-medium text-danger-900">
                            Belongs in “{item.options[result.correct_index]}”
                          </p>
                        )}
                        <p className="mt-2 pl-[1.4rem] text-xs leading-5 text-stone-700">{result.rationale}</p>
                        <div className="pl-[1.4rem]"><Cites runId={runId} citations={result.citations} /></div>
                      </div>
                    );
                  })}
                  {!inBucket.length && (
                    <p className="rounded-lg border border-dashed px-3 py-4 text-center text-xs text-stone-500">
                      Nothing placed here yet
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {!done && placed > 0 && (
          <button type="button" onClick={() => { items.forEach((item) => onAnswer(item.id, null)); setReopened(null); }}
            className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-stone-600 hover:text-brand-700">
            <RotateCcw size={14} /> Start the board again
          </button>
        )}
      </CardContent>
    </Card>
  );
}

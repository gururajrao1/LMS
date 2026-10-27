"use client";

import { useState } from "react";
import { Check, X } from "lucide-react";
import { Cites } from "@/components/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { AskedQuestion, QuestionGroup, ReviewedQuestion } from "@/lib/api";

/**
 * Word building — the clinical form of it.
 *
 * The learner rebuilds a labelled instruction by choosing the phrase for each
 * slot. The chips are the words that change what a clinician would do: a
 * threshold, a timing, a dose. Assembling a drug name from letters would be the
 * consumer-edtech reading of the same mechanic and would teach nothing; getting
 * "Grade ≤2" rather than "Grade ≤1" into the sentence is the actual skill.
 *
 * Each slot is its own scored question. The sentence is only how they are shown.
 */
export function AssemblePanel({ group, items, answers, onAnswer, reviewed, runId }: {
  group: QuestionGroup;
  items: AskedQuestion[];
  answers: Record<string, number>;
  onAnswer: (id: string, choice: number | null) => void;
  reviewed?: Map<string, ReviewedQuestion>;
  runId?: string;
}) {
  const byId = new Map(items.map((item) => [item.id, item]));
  const [open, setOpen] = useState<string | null>(null);
  const done = Boolean(reviewed);
  const sentences = group.items ?? [];
  const slots = sentences.flatMap((sentence) => sentence.blanks.map((blank) => blank.id));
  const filled = slots.filter((id) => answers[id] !== undefined).length;

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b bg-stone-50 px-6 py-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-brand-700">Build the instruction</p>
          <h3 className="mt-1 font-semibold leading-6">{group.title}</h3>
        </div>
        <p className="text-sm tabular-nums text-stone-600">{filled} of {slots.length} filled</p>
      </div>

      <CardContent className="space-y-6 p-6">
        <p className="text-sm leading-6 text-stone-600">{group.instruction}</p>

        {sentences.map((sentence) => {
          const results = sentence.blanks.map((blank) => reviewed?.get(blank.id));
          const right = results.every((result) => result?.correct);
          return (
            <div key={sentence.id} className={`rounded-xl border p-5 ${done
              ? right ? "border-brand-600 bg-brand-50/50" : "border-danger-600 bg-danger-50/40"
              : "border-stone-200"}`}>
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{sentence.prompt}</p>

              <p className="mt-3 text-base leading-9">
                {sentence.blanks.map((blank) => {
                  const question = byId.get(blank.id);
                  const chosen = answers[blank.id];
                  const result = reviewed?.get(blank.id);
                  const label = chosen === undefined ? null : question?.options[chosen];
                  return (
                    <span key={blank.id}>
                      {blank.before}
                      <button type="button" disabled={done}
                        onClick={() => setOpen((current) => (current === blank.id ? null : blank.id))}
                        className={`mx-0.5 rounded-md border px-2 py-1 text-sm font-medium align-baseline ${result
                          ? result.correct
                            ? "border-brand-600 bg-brand-50 text-brand-800"
                            : "border-danger-600 bg-danger-50 text-danger-900 line-through"
                          : label
                            ? "border-brand-600 bg-brand-50 text-brand-800"
                            : "border-dashed border-stone-400 bg-white text-stone-500"}`}>
                        {label ?? "choose…"}
                      </button>
                      {result && !result.correct && (
                        <span className="mx-0.5 rounded-md border border-brand-600 bg-brand-50 px-2 py-1 text-sm font-medium text-brand-800">
                          {question?.options[result.correct_index]}
                        </span>
                      )}
                    </span>
                  );
                })}
                {sentence.tail}
              </p>

              {!done && open && sentence.blanks.some((blank) => blank.id === open) && (
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {(byId.get(open)?.options ?? []).map((option, index) => (
                    <button key={option} type="button"
                      onClick={() => { onAnswer(open, index); setOpen(null); }}
                      className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                        answers[open] === index ? "border-brand-600 bg-brand-50" : "hover:border-brand-600 hover:bg-brand-50"}`}>
                      {option}
                    </button>
                  ))}
                </div>
              )}

              {done && (
                <div className="mt-3 border-t pt-3">
                  <p className="flex items-start gap-2 text-sm leading-6 text-stone-700">
                    {right ? <Check size={15} className="mt-1 shrink-0 text-brand-700" />
                      : <X size={15} className="mt-1 shrink-0 text-danger-600" />}
                    <span>{results.find((result) => result)?.rationale}</span>
                  </p>
                  <Cites runId={runId} citations={results.find((result) => result)?.citations ?? []} />
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

"use client";

import { useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, FlaskConical, RotateCcw, XCircle } from "lucide-react";
import { Cites } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Citation, QuizQuestion } from "@/lib/api";

export type WalkScene = {
  id: number; title: string; narration: string; visual: string;
  on_screen_text: string; duration_seconds: number; citations: Citation[];
};

function citeKey(citation: Citation): string {
  return `${citation.url ?? ""}|${citation.locator ?? ""}|${citation.title ?? ""}`;
}

/**
 * The mechanism of action as steps you walk, not video you watch.
 *
 * Each storyboard scene pairs with a recorded quiz question that shares one
 * of its citations — a check the course already owns, never one invented for
 * the walkthrough. A step with no shared citation says so instead of
 * borrowing an unrelated question.
 */
export function MechanismWalkthrough({ runId, scenes, questions }: {
  runId: string;
  scenes: WalkScene[];
  questions: QuizQuestion[];
}) {
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<Record<number, number>>({});
  const [graded, setGraded] = useState<Record<number, boolean>>({});
  const scene = scenes[index];
  const check = useMemo(() => {
    const keys = new Set(scene.citations.map(citeKey));
    return questions.find((question) => question.citations.some((citation) => keys.has(citeKey(citation)))) ?? null;
  }, [scene, questions]);
  const answered = graded[scene.id] === true;
  const correct = check !== null && picked[scene.id] === check.correct_index;
  const score = scenes.filter((entry) => graded[entry.id]).length;

  function reset() {
    setIndex(0); setPicked({}); setGraded({});
  }

  if (!scenes.length) return <Card><CardContent className="p-8 text-center text-stone-600">No visual story has been recorded for this course yet.</CardContent></Card>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {scenes.map((entry, position) => (
          <button key={entry.id} type="button" onClick={() => setIndex(position)}
            aria-label={`Step ${position + 1}: ${entry.title}`}
            className={`grid size-9 place-items-center rounded-full text-sm font-semibold transition-colors ${position === index ? "bg-brand-600 text-white" : graded[entry.id] ? "bg-brand-100 text-brand-800" : "bg-white text-stone-500 shadow-sm hover:bg-stone-100"}`}>
            {position + 1}
          </button>
        ))}
        <span className="ml-auto text-sm text-stone-600 tabular-nums">{score}/{scenes.length} steps checked</span>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><FlaskConical size={18} /> Step {index + 1}: {scene.title}</CardTitle>
          <p className="mt-2 text-sm text-stone-600">{scene.duration_seconds} sec · walk it, then prove it below.</p>
        </CardHeader>
        <CardContent>
          <p className="leading-7 text-stone-600">{scene.narration}</p>
          <div className="mt-4 rounded-lg bg-stone-50 p-3 text-sm"><b>Visual:</b> {scene.visual}<br /><b>On screen:</b> {scene.on_screen_text}</div>
          <Cites runId={runId} citations={scene.citations} />
        </CardContent>
      </Card>

      {check ? (
        <Card className={answered ? (correct ? "border-brand-600" : "border-danger-300") : ""}>
          <CardHeader><CardTitle className="text-base">Check: {check.prompt}</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {check.options.map((option, optionIndex) => {
              const chosen = picked[scene.id] === optionIndex;
              return (
                <button key={option} type="button" disabled={answered} onClick={() => { setPicked({ ...picked, [scene.id]: optionIndex }); setGraded({ ...graded, [scene.id]: true }); }}
                  className={`w-full rounded-lg border p-3 text-left text-sm transition-colors ${answered && optionIndex === check.correct_index ? "border-brand-600 bg-brand-50 font-medium text-brand-800" : answered && chosen ? "border-danger-300 bg-danger-50" : chosen ? "border-brand-600" : "hover:bg-stone-50"}`}>
                  {option}
                </button>
              );
            })}
            {answered && (
              <div className="pt-2">
                <p className={`flex items-center gap-2 text-sm font-semibold ${correct ? "text-brand-700" : "text-danger-600"}`}>
                  {correct ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                  {correct ? "Correct — this is the mechanism to carry into the field." : "Not quite — re-read the step above, then try the quiz."}
                </p>
                <p className="mt-2 text-sm leading-6 text-stone-600">{check.rationale}</p>
                <Cites runId={runId} citations={check.citations} />
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card><CardContent className="p-5 text-sm text-stone-600">No recorded check shares this step&apos;s citations — the quiz covers it elsewhere.</CardContent></Card>
      )}

      <div className="flex items-center justify-between">
        <Button variant="outline" disabled={index === 0} onClick={() => setIndex(index - 1)}><ArrowLeft size={16} /> Back</Button>
        <Button variant="outline" onClick={reset}><RotateCcw size={16} /> Start over</Button>
        <Button disabled={index === scenes.length - 1} onClick={() => setIndex(index + 1)} className="bg-brand-600 hover:bg-brand-800">Next step <ArrowRight size={16} /></Button>
      </div>
    </div>
  );
}

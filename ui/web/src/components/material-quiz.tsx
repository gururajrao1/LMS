"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getJson, sendJson, StagedSource } from "@/lib/api";

type QAPair = { id: string; question: string; answer: string; source: string; locator: string };
type BuiltQuiz = {
  upload_id: string; title: string; passing_score: number;
  questions: { id: string; prompt: string; options: string[]; correct_index: number; rationale: string }[];
};

/** Extract Q&A pairs from staged material and turn them into scored practice quizzes. */
export function MaterialQuizPanel({ staged, refresh }: { staged: StagedSource[]; refresh: () => void }) {
  const [pairs, setPairs] = useState<Record<string, QAPair[]>>({});
  const [quizzes, setQuizzes] = useState<Record<string, BuiltQuiz>>({});
  const [chosen, setChosen] = useState<Record<string, Record<string, number>>>({});
  const [titles, setTitles] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function extract(entry: StagedSource) {
    setBusy(entry.id); setError("");
    try {
      const result = await sendJson<{ pairs: QAPair[] }>(`/api/uploads/${entry.id}/qa`, {});
      setPairs((current) => ({ ...current, [entry.id]: result.pairs }));
      refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not extract Q&A"); }
    finally { setBusy(null); }
  }

  async function buildQuiz(entry: StagedSource) {
    setBusy(entry.id); setError("");
    try {
      const quiz = await sendJson<BuiltQuiz>(`/api/uploads/${entry.id}/quiz`, { title: titles[entry.id] ?? "" });
      setQuizzes((current) => ({ ...current, [entry.id]: quiz }));
      setChosen((current) => ({ ...current, [entry.id]: {} }));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not build a quiz"); }
    finally { setBusy(null); }
  }

  async function loadQuiz(entry: StagedSource) {
    setBusy(entry.id); setError("");
    try {
      const quiz = await getJson<BuiltQuiz>(`/api/uploads/${entry.id}/quiz`);
      setQuizzes((current) => ({ ...current, [entry.id]: quiz }));
      setChosen((current) => ({ ...current, [entry.id]: {} }));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No built quiz for this document"); }
    finally { setBusy(null); }
  }

  if (!staged.length) return <p className="py-6 text-center text-stone-600 dark:text-muted-foreground">Stage a document first — Q&A pairs are extracted from staged material.</p>;

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-danger-600 dark:text-danger-300">{error}</p>}
      {staged.map((entry) => {
        const quiz = quizzes[entry.id];
        const picked = chosen[entry.id] ?? {};
        const answered = quiz?.questions.filter((question) => picked[question.id] !== undefined).length ?? 0;
        const correct = quiz?.questions.filter((question) => picked[question.id] === question.correct_index).length ?? 0;
        return (
          <Card key={entry.id}>
            <CardHeader>
              <CardTitle className="text-base">{entry.title || entry.name}</CardTitle>
              <p className="mt-1 text-sm text-stone-600 dark:text-muted-foreground">
                {(pairs[entry.id]?.length ?? entry.qa_count ?? 0) === 0
                  ? "No Q&A extracted yet."
                  : `${pairs[entry.id]?.length ?? entry.qa_count} question${(pairs[entry.id]?.length ?? entry.qa_count ?? 0) === 1 ? "" : "s"} extracted`}
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" disabled={busy === entry.id} onClick={() => extract(entry)}>Extract Q&A</Button>
                <Button variant="outline" disabled={busy === entry.id} onClick={() => loadQuiz(entry)}>Open quiz</Button>
              </div>
              {(pairs[entry.id] ?? []).slice(0, 5).map((pair) => (
                <div key={pair.id} className="rounded-xl border bg-stone-50 dark:bg-surface-sunk p-4">
                  <p className="text-sm font-medium">{pair.question}</p>
                  <p className="mt-1 text-sm leading-6 text-stone-600 dark:text-muted-foreground">{pair.answer.slice(0, 220)}{pair.answer.length > 220 ? "…" : ""}</p>
                </div>
              ))}
              <div className="flex flex-wrap gap-2">
                <Input value={titles[entry.id] ?? ""} onChange={(event) => setTitles((current) => ({ ...current, [entry.id]: event.target.value }))} placeholder="Quiz title (optional)" className="max-w-xs" />
                <Button disabled={busy === entry.id} onClick={() => buildQuiz(entry)} className="bg-brand-600 hover:bg-brand-800">Build quiz</Button>
              </div>
              {quiz && (
                <div className="space-y-3 rounded-xl border p-4">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{quiz.title}</p>
                    <p className="text-sm text-stone-600 dark:text-muted-foreground">{answered}/{quiz.questions.length} answered{answered === quiz.questions.length && <> · <b className={correct / quiz.questions.length * 100 >= quiz.passing_score ? "text-brand-700 dark:text-brand-300" : "text-danger-600 dark:text-danger-300"}>{Math.round(correct / quiz.questions.length * 100)}%</b> (pass {quiz.passing_score}%)</>}</p>
                  </div>
                  {quiz.questions.map((question, index) => {
                    const pick = picked[question.id];
                    return (
                      <div key={question.id} className="rounded-xl border p-4">
                        <p className="text-sm font-medium">{index + 1}. {question.prompt}</p>
                        <div className="mt-2 space-y-2">
                          {question.options.map((option, optionIndex) => {
                            const isPick = pick === optionIndex;
                            const decided = pick !== undefined;
                            return (
                              <button key={optionIndex} type="button" disabled={decided}
                                onClick={() => setChosen((current) => ({ ...current, [entry.id]: { ...(current[entry.id] ?? {}), [question.id]: optionIndex } }))}
                                className={`w-full rounded-lg border p-3 text-left text-sm ${decided ? (optionIndex === question.correct_index ? "border-brand-600 bg-brand-50 dark:bg-brand-950" : isPick ? "border-danger-500 bg-danger-50 dark:bg-danger-950" : "") : "hover:bg-stone-50 dark:hover:bg-surface-sunk"}`}>
                                {option}
                              </button>
                            );
                          })}
                        </div>
                        {pick !== undefined && pick !== question.correct_index && <p className="mt-2 text-sm text-stone-600 dark:text-muted-foreground">{question.rationale.slice(0, 300)}</p>}
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

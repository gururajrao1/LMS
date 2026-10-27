"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Award, CheckCircle2, RotateCcw, TrendingUp, XCircle } from "lucide-react";
import { AppShell, Cites, Loading } from "@/components/app-shell";
import { AssemblePanel } from "@/components/assemble-panel";
import { QuizFigure } from "@/components/quiz-figure";
import { TriageBoard } from "@/components/triage-board";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  AskedQuestion, Assessment, AssessmentResult, getJson, QuestionGroup, ReviewedQuestion, sendJson,
} from "@/lib/api";
import { useSession } from "@/lib/session";

function optionStyle(chosen: boolean, correct: boolean) {
  if (correct) return "border-brand-600 bg-brand-50 text-brand-800";
  if (chosen) return "border-danger-600 bg-danger-50 text-danger-900";
  return "border-stone-200 text-stone-600";
}

type Block =
  | { kind: "question"; question: AskedQuestion }
  | { kind: "group"; group: QuestionGroup; items: AskedQuestion[] };

/**
 * Gather each group's items into one block and lead with the groups.
 *
 * A group is one thing to the learner and many things to the scorer, and this is
 * the only place that difference exists. Groups come first because they are the
 * quick part — seven findings tapped into buckets is far less work than one
 * four-option question with a paragraph in every option — and a check that opens
 * with the fast thing gets finished.
 */
function blocks(questions: AskedQuestion[], groups: QuestionGroup[]): Block[] {
  const byId = new Map(groups.map((group) => [group.id, group]));
  const loose: Block[] = [];
  const gathered = new Map<string, Block & { kind: "group" }>();
  for (const question of questions) {
    const group = question.group ? byId.get(question.group) : undefined;
    if (!group) {
      loose.push({ kind: "question", question });
      continue;
    }
    const existing = gathered.get(group.id);
    if (existing) existing.items.push(question);
    else gathered.set(group.id, { kind: "group", group, items: [question] });
  }
  return [...gathered.values(), ...loose];
}

export default function AssessmentPage() {
  const { runId, kind } = useParams<{ runId: string; kind: "baseline" | "final" }>();
  const user = useSession(["msl", "hcp"]);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user) return;
    getJson<Assessment>(`/api/learn/${user.id}/${runId}/assessment/${kind}`).then(setAssessment)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load this assessment."));
  }, [user, runId, kind]);

  async function submit(fillUnanswered = false) {
    if (!user) return;
    setBusy(true); setError("");
    try {
      setResult(await sendJson<AssessmentResult>(`/api/learn/${user.id}/${runId}/assessment/${kind}`,
        { answers, fill_unanswered: fillUnanswered }));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not submit your answers"); }
    finally { setBusy(false); }
  }

  function retry() {
    setResult(null); setAnswers({});
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  if (!user) return <AppShell><Loading /></AppShell>;
  if (!assessment) return <AppShell user={user}><Loading label={error || "Loading the assessment…"} /></AppShell>;

  const baseline = kind === "baseline";
  const answered = Object.keys(answers).length;
  const passed = result?.attempt.passed;
  const asked = result ? result.review : assessment.questions;
  const layout = blocks(asked, (result ?? assessment).groups ?? []);
  const reviewedById = new Map<string, ReviewedQuestion>(
    (result?.review ?? []).map((question) => [question.id, question]),
  );
  // Boards are numbered by their heading, so only the standalone questions carry
  // a number — and it counts them, not the blocks they sit among.
  const numbers = new Map(layout.flatMap((block, index) =>
    block.kind === "question" ? [[index, layout.slice(0, index).filter((b) => b.kind === "question").length + 1]] : []));
  const number = (index: number) => numbers.get(index) ?? index + 1;

  function place(id: string, choice: number | null) {
    setAnswers((current) => {
      if (choice !== null) return { ...current, [id]: choice };
      const cleared = { ...current };
      delete cleared[id];
      return cleared;
    });
  }

  return (
    <AppShell user={user}>
      <Link href={`/learn/${runId}`} className="mb-5 inline-flex items-center gap-2 text-sm font-medium text-stone-600 hover:text-brand-700"><ArrowLeft size={16} /> Back to the course</Link>

      <div className="mx-auto max-w-3xl">
        <Badge className={baseline ? "bg-stone-100 text-stone-700" : "bg-brand-50 text-brand-700"}>{baseline ? "Baseline knowledge check" : "Final assessment"}</Badge>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight">{assessment.title}</h1>
        <p className="mt-2 leading-7 text-stone-600">
          {baseline
            ? "A short check before you start. It is not graded — it measures how much the course teaches you."
            : `Answer every question. You need ${assessment.passing_score}% to pass and earn your certificate.`}
        </p>

        {result ? (
          <Card className={`mt-7 border-2 ${passed ? "border-brand-600" : "border-warn-500"}`}>
            <CardContent className="p-6">
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                <div>
                  <p className="flex items-center gap-2 text-lg font-semibold">
                    {baseline ? <TrendingUp size={20} className="text-stone-600" /> : passed ? <CheckCircle2 size={20} className="text-brand-700" /> : <XCircle size={20} className="text-warn-600" />}
                    {baseline ? "Baseline recorded" : passed ? "Passed" : "Not passed yet"}
                  </p>
                  <p className="mt-1 text-sm text-stone-600">
                    {result.attempt.correct} of {result.attempt.total} correct
                    {!baseline && ` · ${assessment.passing_score}% needed`}
                    {result.summary.uplift !== null && ` · knowledge uplift ${result.summary.uplift >= 0 ? "+" : ""}${result.summary.uplift}`}
                  </p>
                </div>
                <p className="text-4xl font-semibold tabular-nums">{result.attempt.score}%</p>
              </div>
              <Progress value={result.attempt.score} className="mt-4" />
              <div className="mt-5 flex flex-wrap gap-3">
                {baseline && <Button nativeButton={false} render={<Link href={`/learn/${runId}`} />} className="bg-brand-600 hover:bg-brand-800">Start the material</Button>}
                {!baseline && passed && <Button nativeButton={false} render={<Link href={`/learn/${runId}/certificate`} />} className="bg-brand-600 hover:bg-brand-800"><Award /> Get your certificate</Button>}
                {!baseline && !passed && <Button onClick={retry} className="bg-brand-600 hover:bg-brand-800"><RotateCcw /> Try again</Button>}
                {!baseline && !passed && <Button nativeButton={false} variant="outline" render={<Link href={`/learn/${runId}`} />}>Review the material</Button>}
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="mt-7 flex items-center justify-between rounded-xl border bg-white p-4 shadow-sm">
            <p className="text-sm text-stone-600">{answered} of {assessment.questions.length} answered</p>
            <Progress value={Math.round((100 * answered) / assessment.questions.length)} className="ml-4 max-w-xs" />
          </div>
        )}

        {error && <p className="mt-5 text-sm text-danger-600">{error}</p>}

        <div className="mt-6 space-y-4">
          {layout.map((block, blockIndex) => {
            if (block.kind === "group") {
              const shared = {
                group: block.group, items: block.items, answers, onAnswer: place, runId,
                reviewed: result ? reviewedById : undefined,
              };
              return block.group.kind === "assemble"
                ? <AssemblePanel key={block.group.id} {...shared} />
                : <TriageBoard key={block.group.id} {...shared} />;
            }
            const { question } = block;
            const reviewed = reviewedById.get(question.id);
            return (
              <Card key={question.id}>
                <CardHeader><CardTitle className="text-base leading-6">{number(blockIndex)}. {question.prompt}</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {question.figure && <QuizFigure figure={question.figure} />}
                  {question.options.map((option, optionIndex) => (
                    <button key={option} type="button" disabled={Boolean(result)}
                      onClick={() => place(question.id, optionIndex)}
                      className={`w-full rounded-lg border p-3 text-left text-sm transition-colors ${reviewed
                        ? optionStyle(reviewed.chosen === optionIndex, optionIndex === reviewed.correct_index)
                        : answers[question.id] === optionIndex ? "border-brand-600 bg-brand-50" : "hover:bg-stone-50"}`}>
                      {option}
                    </button>
                  ))}
                  {reviewed && (
                    <div className="pt-2">
                      <p className="text-sm leading-6 text-stone-600"><b>{reviewed.correct ? "Correct." : "Not quite."}</b> {reviewed.rationale}</p>
                      <Cites runId={runId} citations={reviewed.citations} />
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>

        {!result && (
          <div className="sticky bottom-4 mt-6 flex items-center justify-between rounded-xl bg-surface-deep p-5 text-white shadow-lg">
            <div>
              <p className="text-sm text-stone-300">{baseline ? "Not graded" : `Pass mark ${assessment.passing_score}%`}</p>
              <p className="text-lg font-semibold">{answered}/{assessment.questions.length} answered</p>
            </div>
            <div className="flex items-center gap-3">
              {/* Only offered when the server says it will honour it, so the button
                  cannot appear on an install where pressing it would just error. */}
              {assessment.demo_fill && answered < assessment.questions.length && (
                <Button variant="outline" disabled={busy}
                  onClick={() => submit(true)}
                  className="border-white/30 bg-transparent text-white hover:bg-white/10">
                  Fill the rest and submit
                </Button>
              )}
              <Button onClick={() => submit()} disabled={busy || answered < assessment.questions.length}
                className="bg-white text-surface-deep hover:bg-stone-100">
                {busy ? "Submitting…" : baseline ? "Submit baseline" : "Submit assessment"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

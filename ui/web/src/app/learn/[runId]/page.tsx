"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, ArrowRight, Award, Check, CheckCircle2, Circle, Download, FileQuestion, Film, Lock, PlayCircle, Presentation, Star } from "lucide-react";
import { AppShell, Cites, Loading } from "@/components/app-shell";
import { CourseChatDock } from "@/components/course-chat-dock";
import { DeckGrid } from "@/components/deck";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { API, getJson, LearnerCourse, LearnerModule, sendJson } from "@/lib/api";
import { useSession } from "@/lib/session";

function Journey({ course, runId }: { course: LearnerCourse; runId: string }) {
  const { summary } = course;
  const steps = [
    { id: "baseline", title: "Baseline check", done: summary.baseline_score !== null, // Not a question count: how many the baseline asks depends on what the course
      // carries — a sort board is added whole rather than sampled — and a number
      // hard-coded here would be wrong for exactly the courses that have one.
      detail: summary.baseline_score !== null ? `Recorded at ${summary.baseline_score}%` : "A short check, not graded", href: `/learn/${runId}/assessment/baseline` },
    { id: "modules", title: "Learning material", done: summary.modules_complete === summary.modules_total, detail: `${summary.modules_complete} of ${summary.modules_total} modules`, href: null },
    { id: "final", title: "Final assessment", done: summary.passed, detail: summary.final_score !== null ? `Scored ${summary.final_score}%` : "Unlocks when every module is done", href: summary.modules_complete === summary.modules_total ? `/learn/${runId}/assessment/final` : null },
    { id: "certificate", title: "Certificate", done: Boolean(summary.certificate), detail: summary.certificate ? summary.certificate.code : "Awarded on passing", href: summary.certificate ? `/learn/${runId}/certificate` : null },
  ];
  return (
    <Card className="mt-6">
      <CardContent className="grid gap-4 p-5 md:grid-cols-4">
        {steps.map((step, index) => {
          const inner = (
            <div className={`flex h-full gap-3 rounded-xl border p-4 transition-colors ${step.href ? "hover:bg-stone-50" : ""} ${step.done ? "border-brand-200 bg-brand-50" : ""}`}>
              <span className={`mt-0.5 grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold ${step.done ? "bg-brand-600 text-white" : step.href ? "bg-brand-50 text-brand-700" : "bg-stone-100 text-stone-500"}`}>
                {step.done ? <Check size={15} /> : step.href ? index + 1 : <Lock size={13} />}
              </span>
              <div className="min-w-0">
                <p className="text-sm font-semibold">{step.title}</p>
                <p className="mt-1 text-xs leading-5 text-stone-600">{step.detail}</p>
                {step.href && !step.done && <p className="mt-2 flex items-center gap-1 text-xs font-medium text-brand-700">Open <ArrowRight size={12} /></p>}
              </div>
            </div>
          );
          return step.href ? <Link key={step.id} href={step.href}>{inner}</Link> : <div key={step.id}>{inner}</div>;
        })}
      </CardContent>
    </Card>
  );
}

function ModuleFooter({ module, runId, userId, onChange }: { module: LearnerModule; runId: string; userId: string; onChange: () => void }) {
  const [rating, setRating] = useState(module.feedback?.rating ?? 0);
  const [comment, setComment] = useState(module.feedback?.comment ?? "");
  const [saved, setSaved] = useState(Boolean(module.feedback));
  const [busy, setBusy] = useState(false);

  async function toggle() {
    setBusy(true);
    try { await sendJson(`/api/learn/${userId}/${runId}/modules`, { module_id: module.id, completed: !module.completed }); onChange(); }
    finally { setBusy(false); }
  }

  async function rate(value: number) {
    setRating(value);
    await sendJson(`/api/learn/${userId}/${runId}/feedback`, { module_id: module.id, rating: value, comment });
    setSaved(true); onChange();
  }

  async function saveComment() {
    if (!rating) return;
    await sendJson(`/api/learn/${userId}/${runId}/feedback`, { module_id: module.id, rating, comment });
    setSaved(true); onChange();
  }

  return (
    <div className="mt-5 flex flex-col gap-4 rounded-xl border bg-white p-5 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="font-semibold">{module.completed ? "Module complete" : `Finished the ${module.title.toLowerCase()}?`}</p>
        <div className="mt-2 flex items-center gap-1">
          <span className="mr-2 text-sm text-stone-600">Rate this module:</span>
          {[1, 2, 3, 4, 5].map((value) => (
            <button key={value} type="button" onClick={() => rate(value)} aria-label={`${value} star${value > 1 ? "s" : ""}`} className="rounded p-0.5 hover:bg-stone-100">
              <Star size={17} className={value <= rating ? "fill-warn-400 text-warn-400" : "text-stone-300"} />
            </button>
          ))}
          {saved && <span className="ml-2 text-xs text-brand-700">Saved</span>}
        </div>
        {rating > 0 && (
          <Input value={comment} onChange={(event) => { setComment(event.target.value); setSaved(false); }} onBlur={saveComment} placeholder="What would make this module better?" className="mt-3 max-w-md" />
        )}
      </div>
      <Button onClick={toggle} disabled={busy} variant={module.completed ? "outline" : "default"} className={module.completed ? "" : "bg-brand-600 hover:bg-brand-800"}>
        {module.completed ? <><CheckCircle2 /> Completed</> : <><Circle /> Mark complete</>}
      </Button>
    </div>
  );
}

export default function CoursePlayer() {
  const { runId } = useParams<{ runId: string }>();
  const user = useSession(["msl", "hcp"]);
  const [course, setCourse] = useState<LearnerCourse | null>(null);
  const [error, setError] = useState("");
  const [video, setVideo] = useState(0);

  const load = () => {
    if (!user) return;
    getJson<LearnerCourse>(`/api/learn/${user.id}/${runId}`).then(setCourse).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load this course."));
  };

  useEffect(load, [user, runId]);

  if (!user) return <AppShell><Loading /></AppShell>;
  if (!course) return <AppShell user={user}><Loading label={error || "Loading your course…"} /></AppShell>;

  const track = course.content;
  const step = (id: string) => course.modules.find((entry) => entry.id === id)!;
  const footer = (id: string) => <ModuleFooter module={step(id)} runId={runId} userId={user.id} onChange={load} />;
  const activeVideo = track.videos[video];

  return (
    <AppShell user={user}>
      <Link href="/learn" className="mb-5 inline-flex items-center gap-2 text-sm font-medium text-stone-600 hover:text-brand-700"><ArrowLeft size={16} /> Back to my training</Link>

      <div className="rounded-2xl bg-surface-deep p-7 text-white md:p-10">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="h-auto max-w-full whitespace-normal bg-white/10 py-1 text-left leading-5 text-brand-300">{course.manifest.drug.area}</Badge>
              <Badge className="bg-white/10 text-white">{course.track.toUpperCase()} track · v{course.version}</Badge>
            </div>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight">{course.manifest.drug.brand}</h1>
            <p className="mt-2 text-stone-300">{course.manifest.drug.generic} · due {new Date(`${course.publication.due_on}T12:00:00`).toLocaleDateString(undefined, { dateStyle: "medium" })}</p>
            {course.publication.message && <p className="mt-4 max-w-xl rounded-xl border border-white/15 bg-white/5 p-3 text-sm text-stone-200">{course.publication.message}</p>}
          </div>
          <div className="w-full max-w-xs">
            <div className="flex items-center justify-between text-sm"><span className="text-stone-300">Course progress</span><span className="font-semibold">{course.summary.percent}%</span></div>
            <Progress value={course.summary.percent} className="mt-2 bg-white/20" />
            {course.summary.certificate && (
              <Button nativeButton={false} render={<Link href={`/learn/${runId}/certificate`} />} className="mt-4 w-full bg-white text-surface-deep hover:bg-stone-100"><Award /> View certificate</Button>
            )}
          </div>
        </div>
      </div>

      <Journey course={course} runId={runId} />

      <Tabs defaultValue="deck" className="mt-7">
        <TabsList className="h-auto flex-wrap bg-white p-1 shadow-sm">
          <TabsTrigger value="deck"><Presentation /> Deck{step("deck").completed && <Check className="text-brand-700" />}</TabsTrigger>
          <TabsTrigger value="videos"><PlayCircle /> Videos{step("videos").completed && <Check className="text-brand-700" />}</TabsTrigger>
          <TabsTrigger value="storyboard"><Film /> Visual story{step("storyboard").completed && <Check className="text-brand-700" />}</TabsTrigger>
          <TabsTrigger value="faq"><FileQuestion /> FAQ{step("faq").completed && <Check className="text-brand-700" />}</TabsTrigger>
        </TabsList>

        <TabsContent value="deck" className="mt-5">
          <Card>
            <CardHeader className="flex-row items-start justify-between gap-4">
              <div><CardTitle>Clinical deck</CardTitle><p className="mt-2 text-sm text-stone-600">{track.deck.slides.length} slides written for the {course.track.toUpperCase()} track.</p></div>
              <Button nativeButton={false} render={<a href={`${API}${track.pptx_url}`} />} className="bg-brand-600 hover:bg-brand-800"><Download /> Download .pptx</Button>
            </CardHeader>
            <CardContent><DeckGrid slides={track.deck.slides} runId={runId} /></CardContent>
          </Card>
          {footer("deck")}
        </TabsContent>

        <TabsContent value="videos" className="mt-5">
          {track.videos.length ? (
            <Card className="overflow-hidden p-0">
              <div className="grid lg:grid-cols-[minmax(0,1fr)_320px]">
                <div className="min-w-0 bg-surface-deeper">
                  <video key={activeVideo.url} controls preload="metadata" onEnded={() => video < track.videos.length - 1 && setVideo(video + 1)} className="aspect-video w-full bg-black" aria-label={activeVideo.title}>
                    <source src={`${API}${activeVideo.url}`} />
                  </video>
                  <div className="p-5 text-white"><p className="text-xs font-semibold tracking-wider text-brand-300">VIDEO {video + 1} OF {track.videos.length}</p><h2 className="mt-2 text-xl font-semibold">{activeVideo.title}</h2></div>
                </div>
                <div className="max-h-[30rem] overflow-y-auto border-t bg-white lg:border-t-0 lg:border-l">
                  <div className="sticky top-0 z-10 border-b bg-white p-4"><p className="font-semibold">Playlist</p></div>
                  <div className="p-2">
                    {track.videos.map((entry, index) => (
                      <button key={entry.id} type="button" onClick={() => setVideo(index)} aria-current={index === video ? "true" : undefined}
                        className={`flex w-full gap-3 rounded-lg p-3 text-left transition-colors ${index === video ? "bg-brand-50 text-brand-700" : "hover:bg-stone-50"}`}>
                        <span className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-full ${index === video ? "bg-brand-600 text-white" : "bg-stone-100 text-stone-600"}`}>{index === video ? <PlayCircle size={17} /> : index + 1}</span>
                        <span className="text-sm font-medium leading-5">{entry.title}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          ) : <Card><CardContent className="p-8 text-center text-stone-600">No videos have been added to this track yet — the storyboard below is the visual script.</CardContent></Card>}
          {footer("videos")}
        </TabsContent>

        <TabsContent value="storyboard" className="mt-5">
          <div className="space-y-4">
            {track.storyboard.scenes.map((scene) => (
              <Card key={scene.id}>
                <CardContent className="grid gap-5 p-5 md:grid-cols-[90px_1fr]">
                  <div><span className="grid size-11 place-items-center rounded-full bg-surface-deep font-semibold text-white">{scene.id}</span><p className="mt-2 text-xs text-stone-600">{scene.duration_seconds} sec</p></div>
                  <div>
                    <h3 className="text-lg font-semibold">{scene.title}</h3>
                    <p className="mt-2 leading-7 text-stone-600">{scene.narration}</p>
                    <div className="mt-4 rounded-lg bg-stone-50 p-3 text-sm"><b>Visual:</b> {scene.visual}<br /><b>On screen:</b> {scene.on_screen_text}</div>
                    <Cites runId={runId} citations={scene.citations} />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
          {footer("storyboard")}
        </TabsContent>

        <TabsContent value="faq" className="mt-5">
          <Card>
            <CardHeader><CardTitle>Field FAQ</CardTitle><p className="mt-2 text-sm text-stone-600">The questions you will be asked, with the evidence behind each answer.</p></CardHeader>
            <CardContent>
              <Accordion>
                {track.faq.items.map((item, index) => (
                  <AccordionItem key={item.question} value={`faq-${index}`}>
                    <AccordionTrigger>{item.question}</AccordionTrigger>
                    <AccordionContent>
                      <p className="leading-7 text-stone-600">{item.answer}</p>
                      {item.nuance && <p className="mt-3 text-sm leading-6 text-stone-600"><b>Important context:</b> {item.nuance}</p>}
                      {item.escalation && <p className="mt-3 text-sm leading-6 text-stone-600"><b>Escalation:</b> {item.escalation}</p>}
                      <Cites runId={runId} citations={item.citations} />
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </CardContent>
          </Card>
          {footer("faq")}
        </TabsContent>

      </Tabs>

      <CourseChatDock runId={runId} learner={course.track} context="learner" userId={user.id}
        blurb="Ask anything about this course. Answers come from the cited dossier, or from your own training record." />
    </AppShell>
  );
}

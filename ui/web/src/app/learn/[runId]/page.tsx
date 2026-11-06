"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ALargeSmall, ArrowLeft, ArrowRight, Award, Check, CheckCircle2, ChevronLeft, ChevronRight, Circle, Download, BookOpen, FileQuestion, Film, FlaskConical, Layers, Lock, Medal, MessageCircle, PlayCircle, Presentation, RotateCcw, Search, ShieldAlert, Shuffle, Star } from "lucide-react";
import { AppShell, Cites, Loading } from "@/components/app-shell";
import { CourseChatDock } from "@/components/course-chat-dock";
import { MechanismWalkthrough } from "@/components/mechanism-walkthrough";
import { DeckGrid } from "@/components/deck";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { API, flushQueue, getJson, LearnerCourse, LearnerModule, Library, Objection, outboxDepth, sendJsonQueued } from "@/lib/api";
import { SourceSidecar } from "@/components/source-sidecar";
import { Textarea } from "@/components/ui/textarea";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
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
  const [notice, setNotice] = useState("");
  const [done, setDone] = useState(module.completed);
  // A parent reload can land between two fast taps: re-anchor the optimistic
  // flag when the server truth actually moves, during render, not in an effect.
  const [prevCompleted, setPrevCompleted] = useState(module.completed);
  if (prevCompleted !== module.completed) {
    setPrevCompleted(module.completed);
    setDone(module.completed);
  }

  function offlineNote(reason: unknown) {
    return (reason as Error & { queued?: boolean }).queued
      ? "Saved offline — will sync when you are back online."
      : reason instanceof Error ? reason.message : "Could not save.";
  }

  async function toggle() {
    const next = !done;
    setDone(next);
    setBusy(true);
    try { await sendJsonQueued(`/api/learn/${userId}/${runId}/modules`, { module_id: module.id, completed: next }); onChange(); }
    catch (reason) { setNotice(offlineNote(reason)); }
    finally { setBusy(false); }
  }

  async function rate(value: number) {
    setRating(value);
    try {
      await sendJsonQueued(`/api/learn/${userId}/${runId}/feedback`, { module_id: module.id, rating: value, comment });
      setSaved(true); onChange();
    } catch (reason) { setNotice(offlineNote(reason)); return; }
  }

  async function saveComment() {
    if (!rating) return;
    try {
      await sendJsonQueued(`/api/learn/${userId}/${runId}/feedback`, { module_id: module.id, rating, comment });
      setSaved(true); onChange();
    } catch (reason) { setNotice(offlineNote(reason)); }
  }

  return (
    <div className="mt-5 flex flex-col gap-4 rounded-xl border bg-white p-5 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="font-semibold">{done ? "Module complete" : `Finished the ${module.title.toLowerCase()}?`}</p>
        <div className="mt-2 flex items-center gap-1">
          <span className="mr-2 text-sm text-stone-600">Rate this module:</span>
          {[1, 2, 3, 4, 5].map((value) => (
            <button key={value} type="button" onClick={() => rate(value)} aria-label={`${value} star${value > 1 ? "s" : ""}`} className="rounded p-0.5 hover:bg-stone-100">
              <Star size={17} className={value <= rating ? "fill-warn-400 text-warn-400" : "text-stone-300"} />
            </button>
          ))}
          {saved && <span className="ml-2 text-xs text-brand-700">Saved</span>}
          {notice && <span className="ml-2 text-xs text-warn-700">{notice}</span>}
        </div>
        {rating > 0 && (
          <Input value={comment} onChange={(event) => { setComment(event.target.value); setSaved(false); }} onBlur={saveComment} placeholder="What would make this module better?" className="mt-3 max-w-md" />
        )}
      </div>
      <Button onClick={toggle} disabled={busy} variant={done ? "outline" : "default"} className={done ? "" : "bg-brand-600 hover:bg-brand-800"}>
        {done ? <><CheckCircle2 /> Completed</> : <><Circle /> Mark complete</>}
      </Button>
    </div>
  );
}

function PracticeMissed({ runId, userId }: { runId: string; userId: string }) {
  const [practice, setPractice] = useState<{ missed_count: number; questions: { id: string; prompt: string; options: string[] }[] } | null>(null);
  useEffect(() => { getJson<{ missed_count: number; questions: { id: string; prompt: string; options: string[] }[] }>(`/api/learn/${userId}/${runId}/reinforce`).then(setPractice).catch(() => {}); }, [runId, userId]);
  if (!practice || !practice.missed_count) return null;
  return (
    <Card className="mt-6">
      <CardHeader><CardTitle>Practice what you missed ({practice.missed_count})</CardTitle><p className="mt-2 text-sm text-stone-600">No answer key here — try each one, then check the material before retaking the final.</p></CardHeader>
      <CardContent className="space-y-3">
        {practice.questions.map((question, index) => (
          <div key={question.id} className="rounded-xl border p-4">
            <p className="text-sm font-medium">{index + 1}. {question.prompt}</p>
            <ul className="mt-2 space-y-1">{question.options.map((option, optionIndex) => <li key={optionIndex} className="rounded-lg bg-stone-50 px-3 py-2 text-sm text-stone-700">{option}</li>)}</ul>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

const COURSE_TABS = ["deck", "videos", "storyboard", "faq", "flashcards", "mechanism", "objections"] as const;

function readStored(key: string): string | null {
  try { return typeof window === "undefined" ? null : window.localStorage.getItem(key); }
  catch { return null; }
}

function writeStored(key: string, value: string) {
  try { if (typeof window !== "undefined") window.localStorage.setItem(key, value); }
  catch { /* private mode: memory only */ }
}

function Flashcards({ items, storageKey }: { items: { question: string; answer: string; nuance?: string }[]; storageKey: string }) {
  const [order, setOrder] = useState<number[]>(() => items.map((_, index) => index));
  const [position, setPosition] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [grades, setGrades] = useState<Record<string, "knew" | "missed">>(() => {
    try {
      const saved = readStored(storageKey);
      return saved ? JSON.parse(saved) as Record<string, "knew" | "missed"> : {};
    } catch { return {}; }
  });
  if (!items.length) return <Card><CardContent className="p-8 text-center text-stone-600">No revision cards in this course yet.</CardContent></Card>;
  const current = items[order[position % order.length]];
  const reviewed = Object.keys(grades).length;
  const knew = Object.values(grades).filter((grade) => grade === "knew").length;
  function grade(value: "knew" | "missed") {
    const next = { ...grades, [current.question]: value };
    setGrades(next);
    writeStored(storageKey, JSON.stringify(next));
    setFlipped(false);
    setPosition((at) => (at + 1) % order.length);
  }
  function shuffle() {
    const next = [...order];
    for (let i = next.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [next[i], next[j]] = [next[j], next[i]];
    }
    setOrder(next); setPosition(0); setFlipped(false);
  }
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-stone-600">
        <span>{reviewed} of {items.length} reviewed · {knew} knew</span>
        <span className="ml-auto flex gap-2">
          <Button variant="outline" onClick={shuffle}><Shuffle /> Shuffle</Button>
          <Button variant="outline" onClick={() => { setGrades({}); writeStored(storageKey, "{}"); setPosition(0); setFlipped(false); }}><RotateCcw /> Start over</Button>
        </span>
      </div>
      <button type="button" onClick={() => setFlipped((open) => !open)} aria-live="polite"
        className="block min-h-56 w-full rounded-2xl border bg-white p-8 text-left shadow-sm transition-shadow hover:shadow-md">
        <p className="text-xs font-semibold uppercase tracking-wide text-brand-700">{flipped ? "Answer — click to hide" : `Card ${position + 1} of ${order.length} — try it, then click to reveal`}</p>
        <p className="mt-3 text-xl font-semibold leading-8">{current.question}</p>
        {flipped && (<div className="mt-4 border-t pt-4"><p className="leading-7 text-stone-700">{current.answer}</p>
          {current.nuance && <p className="mt-3 text-sm leading-6 text-stone-600"><b>Important context:</b> {current.nuance}</p>}</div>)}
      </button>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button onClick={() => grade("missed")} variant="outline">Still fuzzy</Button>
        <Button onClick={() => grade("knew")} className="bg-brand-600 hover:bg-brand-800"><Check /> I knew it</Button>
        <span className="ml-auto flex gap-2">
          <Button variant="outline" onClick={() => { setFlipped(false); setPosition((at) => (at - 1 + order.length) % order.length); }}><ChevronLeft /> Prev</Button>
          <Button variant="outline" onClick={() => { setFlipped(false); setPosition((at) => (at + 1) % order.length); }}>Next <ChevronRight /></Button>
        </span>
      </div>
    </div>
  );
}

type SearchHit = { tab: string; anchor: string | null; title: string; snippet: string };

function MaterialSearch({ course, onJump }: { course: LearnerCourse; onJump: (tab: string, anchor: string | null) => void }) {
  const [query, setQuery] = useState("");
  const track = course.content;
  const hits: SearchHit[] = query.trim().length < 2 ? [] : (() => {
    const q = query.trim().toLowerCase();
    const out: SearchHit[] = [];
    track.deck.slides.forEach((slide) => {
      if (`${slide.title} ${slide.purpose}`.toLowerCase().includes(q))
        out.push({ tab: "deck", anchor: null, title: `Slide ${slide.number}: ${slide.title}`, snippet: slide.purpose.slice(0, 140) });
    });
    track.storyboard.scenes.forEach((scene) => {
      const hay = `${scene.title} ${scene.narration} ${scene.on_screen_text}`.toLowerCase();
      const at = hay.indexOf(q);
      if (at !== -1)
        out.push({ tab: "storyboard", anchor: `scene-${scene.id}`, title: `Scene ${scene.id}: ${scene.title}`,
          snippet: `${scene.on_screen_text.slice(0, 120)}` });
    });
    track.faq.items.forEach((item, index) => {
      if (`${item.question} ${item.answer}`.toLowerCase().includes(q))
        out.push({ tab: "faq", anchor: `faq-${index}`, title: item.question, snippet: item.answer.slice(0, 140) });
    });
    return out.slice(0, 8);
  })();
  return (
    <div className="relative">
      <Search size={16} className="pointer-events-none absolute left-3 top-3 text-stone-400" />
      <Input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Escape") setQuery(""); }} placeholder="Search the material — slides, scenes, FAQ…" className="pl-9" aria-label="Search the course material" />
      {query.trim().length >= 2 && (
        <div className="absolute z-20 mt-1 max-h-80 w-full overflow-y-auto rounded-xl border bg-white shadow-lg">
          {hits.length ? hits.map((hit, index) => (
            <button key={`${hit.tab}-${hit.anchor ?? "top"}-${index}`} type="button"
              onClick={() => { onJump(hit.tab, hit.anchor); setQuery(""); }}
              className="block w-full border-b p-3 text-left last:border-0 hover:bg-stone-50">
              <p className="text-sm font-semibold">{hit.title} <span className="ml-1 font-normal text-stone-500">· {hit.tab}</span></p>
              <p className="mt-1 text-sm text-stone-600">{hit.snippet}</p>
            </button>
          )) : <p className="p-3 text-sm text-stone-600">Nothing in this course matches.</p>}
        </div>
      )}
    </div>
  );
}

export default function CoursePlayer() {
  const { runId } = useParams<{ runId: string }>();
  const user = useSession(["msl", "hcp"], { anyLearner: true });
  const [course, setCourse] = useState<LearnerCourse | null>(null);
  const [error, setError] = useState("");
  const [video, setVideoState] = useState(() => {
    const saved = Number(readStored(`pl-video-${runId}`));
    return Number.isInteger(saved) && saved >= 0 ? saved : 0;
  });
  const [tab, setTab] = useState<string>(() => {
    const fromUrl = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("tab");
    if (fromUrl && (COURSE_TABS as readonly string[]).includes(fromUrl)) return fromUrl;
    const saved = readStored(`pl-tab-${runId}`);
    return saved && (COURSE_TABS as readonly string[]).includes(saved) ? saved : "deck";
  });
  const [simple, setSimple] = useState(() => readStored(`pl-simple-${runId}`) === "1");
  const [synced, setSynced] = useState("");
  const [objections, setObjections] = useState<Objection[]>([]);
  const [safetyOpen, setSafetyOpen] = useState(false);
  const [concern, setConcern] = useState("");
  const [safetyNote, setSafetyNote] = useState("");
  const [safetyBusy, setSafetyBusy] = useState(false);
  const [refUrl, setRefUrl] = useState<string | null>(null);
  const [library, setLibrary] = useState<Library | null>(null);

  function setVideo(index: number) {
    setVideoState(index);
    writeStored(`pl-video-${runId}`, String(index));
  }

  function changeTab(value: string) {
    setTab(value);
    writeStored(`pl-tab-${runId}`, value);
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("tab", value);
      window.history.replaceState(null, "", url.toString());
    } catch { /* ignore */ }
  }

  const [pendingAnchor, setPendingAnchor] = useState<string | null>(null);

  useEffect(() => {
    if (!pendingAnchor) return;
    const frame = window.setTimeout(() => {
      document.getElementById(pendingAnchor)?.scrollIntoView({ behavior: "smooth", block: "start" });
      setPendingAnchor(null);
    }, 60);
    return () => window.clearTimeout(frame);
  }, [pendingAnchor, tab]);

  async function submitSafety() {
    if (!user || !concern.trim()) return;
    setSafetyBusy(true); setSafetyNote("");
    try {
      await sendJsonQueued(`/api/runs/${runId}/safety`, { user_id: user.id, concern: concern.trim() }, "POST");
      setConcern(""); setSafetyOpen(false);
      setSynced("Safety concern recorded — the training team triages every report.");
    } catch (reason) {
      setSafetyNote(reason instanceof Error ? reason.message : "Could not record your report");
    } finally { setSafetyBusy(false); }
  }

  function jumpTo(targetTab: string, anchor: string | null) {
    setPendingAnchor(anchor);
    changeTab(targetTab);
  }

  function toggleSimple() {
    const next = !simple;
    setSimple(next);
    writeStored(`pl-simple-${runId}`, next ? "1" : "0");
  }

  const load = () => {
    if (!user) return;
    getJson<LearnerCourse>(`/api/learn/${user.id}/${runId}`).then(setCourse).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load this course."));
    getJson<Objection[]>(`/api/runs/${runId}/objections`).then(setObjections).catch(() => setObjections([]));
    getJson<Library>(`/api/runs/${runId}/library`).then(setLibrary).catch(() => setLibrary(null));
    void flushQueue().then((result) => {
      const depth = outboxDepth();
      if (result.sent) setSynced(`Back online — synced ${result.sent} saved change${result.sent === 1 ? "" : "s"}.`);
      else if (depth) setSynced(`${depth} change${depth === 1 ? "" : "s"} waiting to sync.`);
    });
  };

  useEffect(load, [user, runId]);

  if (!user) return <AppShell><Loading /></AppShell>;
  if (!course) return <AppShell user={user}><Loading label={error || "Loading your course…"} /></AppShell>;

  const track = course.content;
  const step = (id: string) => course.modules.find((entry) => entry.id === id)!;
  const footer = (id: string) => <ModuleFooter module={step(id)} runId={runId} userId={user.id} onChange={load} />;
  const activeVideo = track.videos[Math.min(video, Math.max(track.videos.length - 1, 0))];

  return (
    <AppShell user={user}>
      <Link href="/learn" className="mb-5 inline-flex items-center gap-2 text-sm font-medium text-stone-600 hover:text-brand-700"><ArrowLeft size={16} /> Back to my training</Link>
      {synced && <p className="mb-4 text-sm text-brand-700" role="status">{synced}</p>}

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
            <div className="flex items-center justify-between text-sm"><span className="text-stone-300">Course progress</span><span className="font-semibold">{course.summary.percent}% · {course.summary.points} pts</span></div>
            <Progress value={course.summary.percent} className="mt-2 bg-white/20" />
            <div className="mt-3 flex flex-wrap items-center gap-1.5" aria-label="Earned badges">
              {course.summary.badges.filter((badge) => badge.earned).map((badge) => (
                <span key={badge.id} title={badge.label} className="inline-flex items-center gap-1 rounded-full bg-brand-600 px-2.5 py-1 text-xs font-semibold text-white"><Medal size={12} /> {badge.label}</span>
              ))}
              {course.summary.streak_days > 1 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-white/10 px-2.5 py-1 text-xs font-semibold text-brand-300" title="Consecutive days with training activity">{course.summary.streak_days}-day streak</span>
              )}
            </div>
            {course.summary.certificate && (
              <Button nativeButton={false} render={<Link href={`/learn/${runId}/certificate`} />} className="mt-4 w-full bg-white text-surface-deep hover:bg-stone-100"><Award /> View certificate</Button>
            )}
          </div>
        </div>
      </div>

      <Journey course={course} runId={runId} />
      <Card className="mt-6"><CardContent className="flex flex-col gap-3 p-5 text-sm sm:flex-row sm:items-center"><div><p className="font-semibold">Next best action</p><p className="mt-1 text-stone-600">{course.summary.baseline_score === null ? "Start the baseline check to record your starting point." : course.summary.modules_complete !== course.summary.modules_total ? `Continue learning: ${course.summary.modules_complete} of ${course.summary.modules_total} modules done.` : !course.summary.passed ? "Take the final assessment; every module is done." : course.summary.certificate ? `Certified: ${course.summary.certificate.code}.` : "Review the material, then take the final."}</p></div><Button nativeButton={false} render={<Link href={course.summary.baseline_score === null ? `/learn/${runId}/assessment/baseline` : course.summary.modules_complete !== course.summary.modules_total ? `/learn/${runId}?tab=${tab}` : !course.summary.passed ? `/learn/${runId}/assessment/final` : `/learn/${runId}/certificate`} />} className="bg-brand-600 hover:bg-brand-800 sm:ml-auto"><ArrowRight /> Continue</Button></CardContent></Card>
      <PracticeMissed runId={runId} userId={user.id} />

      <div className="mt-6"><MaterialSearch course={course} onJump={jumpTo} /></div>
      <Tabs value={tab} onValueChange={changeTab} className="mt-4">
        <TabsList className="h-auto flex-wrap bg-white p-1 shadow-sm">
          <TabsTrigger value="deck"><Presentation /> Deck{step("deck").completed && <Check className="text-brand-700" />}</TabsTrigger>
          <TabsTrigger value="videos"><PlayCircle /> Videos{step("videos").completed && <Check className="text-brand-700" />}</TabsTrigger>
          <TabsTrigger value="storyboard"><Film /> Visual story{step("storyboard").completed && <Check className="text-brand-700" />}</TabsTrigger>
          <TabsTrigger value="faq"><FileQuestion /> FAQ{step("faq").completed && <Check className="text-brand-700" />}</TabsTrigger>
          <TabsTrigger value="flashcards"><Layers /> Flashcards</TabsTrigger>
          <TabsTrigger value="mechanism"><FlaskConical /> Mechanism</TabsTrigger>
          <TabsTrigger value="objections"><MessageCircle /> Objections</TabsTrigger>
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
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <span className="text-sm text-stone-600">Reading level:</span>
            <Button variant={simple ? "outline" : "default"} onClick={toggleSimple} className={simple ? "" : "bg-brand-600 hover:bg-brand-800"}><ALargeSmall /> Full detail</Button>
            <Button variant={simple ? "default" : "outline"} onClick={toggleSimple} className={simple ? "bg-brand-600 hover:bg-brand-800" : ""}><ALargeSmall /> Key points</Button>
          </div>
          <div className="space-y-4">
            {track.storyboard.scenes.map((scene) => (
              <Card key={scene.id} id={`scene-${scene.id}`}>
                <CardContent className="grid gap-5 p-5 md:grid-cols-[90px_1fr]">
                  <div><span className="grid size-11 place-items-center rounded-full bg-surface-deep font-semibold text-white">{scene.id}</span><p className="mt-2 text-xs text-stone-600">{scene.duration_seconds} sec</p></div>
                  <div>
                    <h3 className="text-lg font-semibold">{scene.title}</h3>
                    {simple
                      ? <p className="mt-2 text-lg font-medium leading-8">{scene.on_screen_text}</p>
                      : <p className="mt-2 leading-7 text-stone-600">{scene.narration}</p>}
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
                  <AccordionItem key={item.question} value={`faq-${index}`} id={`faq-${index}`}>
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

        <TabsContent value="mechanism" className="mt-5">
          <Card>
            <CardHeader><CardTitle>Mechanism walkthrough</CardTitle><p className="mt-2 text-sm text-stone-600">Walk each step of the action, then prove it with a recorded check. A step with no shared citation says so instead of borrowing one.</p></CardHeader>
            <CardContent>
              <MechanismWalkthrough runId={runId} scenes={track.storyboard.scenes} questions={track.quiz.questions} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="objections" className="mt-5">
          <Card>
            <CardHeader><CardTitle>Handling objections</CardTitle><p className="mt-2 text-sm text-stone-600">Approved answers to the hard questions you will hear in the field.</p></CardHeader>
            <CardContent>
              {objections.length ? (
                <Accordion>{objections.map((item, index) => (
                  <AccordionItem key={item.id} value={`obj-${index}`}>
                    <AccordionTrigger>{item.question}</AccordionTrigger>
                    <AccordionContent>
                      <p className="leading-7 text-stone-600">{item.answer}</p>
                      <p className="mt-3 text-xs text-stone-500">Approved answer · {item.author_name}</p>
                      <Cites runId={runId} citations={item.citations} />
                    </AccordionContent>
                  </AccordionItem>
                ))}</Accordion>
              ) : <p className="text-sm text-stone-600">No approved answers have been published for this course yet.</p>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="flashcards" className="mt-5">
          <Card>
            <CardHeader><CardTitle>Revision flashcards</CardTitle><p className="mt-2 text-sm text-stone-600">Try each question from memory, then flip the card. Your self-grades stay on this device.</p></CardHeader>
            <CardContent>
              <Flashcards
                key={`pl-flip-${runId}`}
                items={track.faq.items.map((item) => ({ question: item.question, answer: item.answer, nuance: item.nuance }))}
                storageKey={`pl-flip-${runId}`}
              />
            </CardContent>
          </Card>
        </TabsContent>

      </Tabs>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => { setSafetyNote(""); setSafetyOpen(true); }}><ShieldAlert size={16} /> Report a safety concern</Button>
      </div>
      <AlertDialog open={safetyOpen} onOpenChange={setSafetyOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Report a safety concern</AlertDialogTitle>
            <AlertDialogDescription>
              Seen in clinic or in training: an adverse event, a near miss, unclear safety wording. The training team triages every report. This does not replace your organisation&apos;s pharmacovigilance channel.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Textarea value={concern} onChange={(event) => setConcern(event.target.value)} rows={4} placeholder="What happened, and where?" />
          {safetyNote && <p className="text-sm text-danger-600">{safetyNote}</p>}
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-brand-600 hover:bg-brand-800" disabled={safetyBusy || !concern.trim()} onClick={() => void submitSafety()}>
              {safetyBusy ? "Recording…" : "Send report"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {(library?.documents ?? []).filter((doc) => doc.held).length > 0 && (
        <Card className="mt-4">
          <CardHeader><CardTitle className="flex items-center gap-2"><BookOpen size={18} /> Reference documents</CardTitle><p className="mt-2 text-sm text-stone-600">The sources this course was checked against — read them beside your material.</p></CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {(library?.documents ?? []).filter((doc) => doc.held).map((doc) => (
                <Button key={doc.url} variant="outline" onClick={() => setRefUrl(doc.url)}>{doc.title}</Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
      {refUrl && <SourceSidecar runId={runId} url={refUrl} onClose={() => setRefUrl(null)} />}

      <CourseChatDock runId={runId} learner={course.track} context="learner" userId={user.id}
        blurb="Ask anything about this course. Answers come from the cited dossier, or from your own training record." />
    </AppShell>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, ChartColumn, CheckCircle2, Download, ExternalLink, FileQuestion, Film, GitBranch, Layers, ListChecks, PlayCircle, Presentation, Route, Send, ScanLine, ShieldCheck, TrendingUp, Users } from "lucide-react";
import { AppShell, Cites, Loading } from "@/components/app-shell";
import { CourseChatDock } from "@/components/course-chat-dock";
import { CourseJourney } from "@/components/course-journey";
import { DeckGrid } from "@/components/deck";
import { CourseCohortPanel } from "@/components/course-cohort";
import { CourseChecksPanel } from "@/components/course-checks";
import { CourseCompletenessPanel } from "@/components/course-completeness";
import { CourseImpactPanel } from "@/components/course-impact";
import { CoursePublishPanel } from "@/components/course-publish";
import { CourseReviewPanel } from "@/components/course-review";
import { NavSection, SectionNav } from "@/components/section-nav";
import { SourceLibrary } from "@/components/source-library";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { API, CourseContent, CourseReview, getJson, Learner } from "@/lib/api";
import { useSession } from "@/lib/session";

const STATUS_LABEL = { draft: "Draft", in_review: "In review", approved: "Approved", published: "Published" } as const;

function VideoPlaylist({ videos, learner }: { videos: CourseContent["learners"]["hcp"]["videos"]; learner: Learner }) {
  const [current, setCurrent] = useState(0);
  if (!videos.length) return <Card><CardContent className="p-8 text-center text-stone-600">No {learner.toUpperCase()} videos have been added yet.</CardContent></Card>;
  const active = videos[current];
  return (
    <Card className="overflow-hidden p-0">
      <div className="grid lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 bg-surface-deeper">
          <video key={active.url} controls preload="metadata" onEnded={() => current < videos.length - 1 && setCurrent(current + 1)} className="aspect-video w-full bg-black" aria-label={active.title}>
            <source src={`${API}${active.url}`} />
          </video>
          <div className="p-5 text-white"><p className="text-xs font-semibold tracking-wider text-brand-300">{learner.toUpperCase()} VIDEO {current + 1} OF {videos.length}</p><h2 className="mt-2 text-xl font-semibold">{active.title}</h2></div>
        </div>
        <div className="max-h-[36rem] overflow-y-auto border-t bg-white lg:border-t-0 lg:border-l">
          <div className="sticky top-0 z-10 border-b bg-white p-4"><p className="font-semibold">Course playlist</p><p className="mt-1 text-xs text-stone-600">The next video plays automatically.</p></div>
          <div className="p-2">{videos.map((video, index) => <button key={video.id} type="button" aria-current={index === current ? "true" : undefined} onClick={() => setCurrent(index)} className={`flex w-full gap-3 rounded-lg p-3 text-left transition-colors ${index === current ? "bg-brand-50 text-brand-700" : "hover:bg-stone-50"}`}><span className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-full ${index === current ? "bg-brand-600 text-white" : "bg-stone-100 text-stone-600"}`}>{index === current ? <PlayCircle size={17} /> : index + 1}</span><span className="text-sm font-medium leading-5">{video.title}</span></button>)}</div>
        </div>
      </div>
    </Card>
  );
}

/**
 * Which starter questions each panel should offer.
 *
 * Thirteen panels, five kinds of question — a reader on Checks and a reader on
 * Sources both want to know what the evidence says, and a reader on Cohort or
 * Impact wants to know about the programme rather than the drug.
 */
const CONTEXT: Record<string, string> = {
  ppt: "material", videos: "material", story: "material", faq: "material", quiz: "material",
  sources: "evidence", checks: "evidence", coverage: "evidence",
  review: "review",
  journey: "programme", publish: "programme", cohort: "programme", impact: "programme",
};

export default function CourseWorkspace() {
  const { runId } = useParams<{ runId: string }>();
  const user = useSession(["admin", "reviewer"]);
  const [content, setContent] = useState<CourseContent | null>(null);
  const [review, setReview] = useState<CourseReview | null>(null);
  const [learner, setLearner] = useState<Learner>("hcp");
  // Which panel is open. The assistant sits outside the nav and its starter
  // questions depend on the open panel, so the choice is tracked here rather
  // than left to the nav. Null until the reader picks one, so the landing panel
  // stays derived from the role rather than being written into state by an
  // effect once the role loads.
  const [panel, setPanel] = useState<string | null>(null);

  useEffect(() => {
    getJson<CourseContent>(`/api/runs/${runId}/content`).then((data) => { setContent(data); setLearner(data.default_learner); });
    getJson<CourseReview>(`/api/runs/${runId}/review`).then(setReview);
  }, [runId]);

  if (!user) return <AppShell><Loading /></AppShell>;
  const track = content?.learners[learner];
  if (!content || !track || !review) return <AppShell user={user}><Loading label="Loading the course workspace…" /></AppShell>;
  const admin = user.role === "admin";
  // A reviewer lands on the queue they came for; an admin on the spine.
  const active = panel ?? (admin ? "journey" : "review");

  // Thirteen panels will not sit in one readable row, so they collapse into
  // five sections. Publish, Cohort and Impact are the admin's alone; a section
  // left with one item renders as a plain button, and an empty one not at all.
  const sections: NavSection[] = [
    { label: "Journey", icon: Route, items: [{ value: "journey", label: "Journey", icon: Route }] },
    { label: "Assets", icon: Layers, items: [
      { value: "ppt", label: "PPTX", icon: Presentation },
      { value: "videos", label: "Videos", icon: PlayCircle },
      { value: "story", label: "Storyboard", icon: Film },
      { value: "faq", label: "FAQ", icon: FileQuestion },
      { value: "quiz", label: "Quiz", icon: CheckCircle2 },
    ] },
    { label: "Sources", icon: ExternalLink, items: [{ value: "sources", label: "Sources", icon: ExternalLink }] },
    { label: "Governance", icon: ShieldCheck, items: [
      { value: "checks", label: "Checks", icon: ScanLine },
      { value: "coverage", label: "Coverage", icon: ListChecks },
      { value: "review", label: "Review", icon: GitBranch, count: review.readiness.open_comments },
      ...(admin ? [{ value: "publish", label: "Publish", icon: Send }] : []),
    ] },
    { label: "Analytics", icon: ChartColumn, items: admin ? [
      { value: "cohort", label: "Cohort", icon: Users },
      { value: "impact", label: "Impact", icon: TrendingUp },
    ] : [] },
  ];

  return (
    <AppShell user={user}>
      <Link href="/dashboard" className="mb-5 inline-flex items-center gap-2 text-sm font-medium text-stone-600 hover:text-brand-700"><ArrowLeft size={16} /> Back to dashboard</Link>

      <div className="rounded-2xl bg-surface-deep p-7 text-white md:p-10">
        <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="h-auto max-w-full whitespace-normal bg-white/10 py-1 text-left leading-5 text-brand-300">{content.manifest.drug.area}</Badge>
              <Badge className="bg-white/10 text-white">v{review.version} · {STATUS_LABEL[review.status]}</Badge>
            </div>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight">{content.manifest.drug.brand} course workspace</h1>
            <p className="mt-2 text-stone-300">{content.manifest.drug.generic} · previewing the {learner.toUpperCase()} track</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="rounded-xl border border-white/15 bg-white/5 p-4 text-sm"><p className="text-2xl font-semibold">{content.manifest.citation_count}</p><p className="text-stone-300">citations</p></div>
            <div className="rounded-xl border border-white/15 bg-white/5 p-4 text-sm"><p className="text-2xl font-semibold">{review.readiness.open_comments}</p><p className="text-stone-300">open comments</p></div>
          </div>
        </div>
      </div>

      <div className="mt-6 flex flex-col justify-between gap-4 rounded-xl border bg-white p-4 shadow-sm sm:flex-row sm:items-center">
        <div><p className="font-semibold">Preview a learning track</p><p className="mt-1 text-sm text-stone-600">Assets and knowledge checks adapt to the selected role.</p></div>
        <div className="inline-flex rounded-lg bg-stone-100 p-1">{(["hcp", "msl"] as const).map((value) => <button key={value} type="button" aria-pressed={learner === value} onClick={() => setLearner(value)} className={`rounded-md px-5 py-2 text-sm font-semibold transition-colors ${learner === value ? "bg-white text-brand-700 shadow-sm" : "text-stone-600 hover:text-stone-800"}`}>{value.toUpperCase()}</button>)}</div>
      </div>

      <SectionNav sections={sections} value={active} onValueChange={setPanel} className="mt-7" />

      {/* Keyed on the open panel so switching sections re-runs the fade. */}
      <div key={active} className="mt-5 animate-in fade-in-0 duration-150">

        {active === "journey" && <CourseJourney runId={runId} />}

        {active === "ppt" && <Card><CardHeader className="flex-row items-start justify-between gap-4"><div><CardTitle>{learner.toUpperCase()} clinical presentation</CardTitle><p className="mt-2 text-sm text-stone-600">A role-specific, citation-backed PowerPoint.</p></div><Button nativeButton={false} render={<a href={`${API}${track.pptx_url}`} />} className="bg-brand-600 hover:bg-brand-800"><Download /> Download .pptx</Button></CardHeader><CardContent><DeckGrid slides={track.deck.slides} runId={runId} /></CardContent></Card>}

        {active === "videos" && <VideoPlaylist key={learner} videos={track.videos} learner={learner} />}

        {active === "story" && <div className="space-y-4">{track.storyboard.scenes.map((scene) => <Card key={scene.id}><CardContent className="grid gap-5 p-5 md:grid-cols-[90px_1fr]"><div><span className="grid size-11 place-items-center rounded-full bg-surface-deep font-semibold text-white">{scene.id}</span><p className="mt-2 text-xs text-stone-600">{scene.duration_seconds} sec</p></div><div><h3 className="text-lg font-semibold">{scene.title}</h3><p className="mt-2 leading-7 text-stone-600">{scene.narration}</p><div className="mt-4 rounded-lg bg-stone-50 p-3 text-sm"><b>Visual:</b> {scene.visual}<br /><b>On screen:</b> {scene.on_screen_text}</div><Cites runId={runId} citations={scene.citations} /></div></CardContent></Card>)}</div>}

        {active === "faq" && <Card><CardHeader><CardTitle>{learner.toUpperCase()} FAQ</CardTitle></CardHeader><CardContent><Accordion>{track.faq.items.map((item, index) => <AccordionItem key={item.question} value={`faq-${index}`}><AccordionTrigger>{item.question}</AccordionTrigger><AccordionContent><p className="leading-7 text-stone-600">{item.answer}</p>{item.nuance && <p className="mt-3 text-sm leading-6 text-stone-600"><b>Important context:</b> {item.nuance}</p>}{item.escalation && <p className="mt-3 text-sm leading-6 text-stone-600"><b>Escalation:</b> {item.escalation}</p>}<Cites runId={runId} citations={item.citations} /></AccordionContent></AccordionItem>)}</Accordion></CardContent></Card>}

        {active === "quiz" && <div className="space-y-4"><p className="text-sm text-stone-600">Answers are shown here for review. Learners sit this quiz without them, and must score {track.quiz.passing_score}% to pass.</p>{track.quiz.questions.map((question, index) => <Card key={question.id}><CardHeader><CardTitle className="text-base">{index + 1}. {question.prompt}</CardTitle></CardHeader><CardContent className="space-y-2">{question.options.map((option, optionIndex) => <div key={option} className={`rounded-lg border p-3 text-sm ${optionIndex === question.correct_index ? "border-brand-600 bg-brand-50 text-brand-800" : "text-stone-600"}`}>{option}</div>)}<div className="pt-2"><p className="text-sm leading-6 text-stone-600">{question.rationale}</p><Cites runId={runId} citations={question.citations} /></div></CardContent></Card>)}</div>}

        {active === "sources" && <SourceLibrary runId={runId} />}

        {active === "checks" && <CourseChecksPanel runId={runId} user={user} onChange={() => getJson<CourseReview>(`/api/runs/${runId}/review`).then(setReview)} />}

        {active === "coverage" && <CourseCompletenessPanel runId={runId} user={user} onChange={() => getJson<CourseReview>(`/api/runs/${runId}/review`).then(setReview)} />}

        {active === "review" && <CourseReviewPanel runId={runId} user={user} onChange={setReview} />}

        {active === "publish" && <CoursePublishPanel key={review.publication?.published_at ?? "unpublished"} runId={runId} user={user} review={review} onChange={setReview} />}

        {active === "cohort" && <CourseCohortPanel runId={runId} />}

        {active === "impact" && <CourseImpactPanel runId={runId} />}
      </div>

      <CourseChatDock runId={runId} learner={learner} context={CONTEXT[active] ?? "material"}
        title="Fact check against the dossier"
        blurb="Check a claim before signing off. Answers come from the cited dossier, or from this programme's own record." />
    </AppShell>
  );
}

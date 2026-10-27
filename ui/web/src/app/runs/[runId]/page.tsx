"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Check, LoaderCircle, Sparkles } from "lucide-react";
import { AppShell, Loading } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { API, getJson, Run } from "@/lib/api";
import { AgentSequence } from "@/components/agent-sequence";
import { useSession } from "@/lib/session";

type Event = { stage: string; status: string; progress: number; message: string };

/* Named rather than inferred, so a replay is never shown as live research. */
const MODE_LABEL: Record<NonNullable<Run["mode"]>, string> = {
  live: "live research run",
  local: "local content run",
  replay: "prepared content run",
};

export default function RunProgress() {
  const { runId } = useParams<{ runId: string }>();
  const user = useSession(["admin", "reviewer"]);
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<Event[]>([]);

  useEffect(() => {
    getJson<Run>(`/api/runs/${runId}`).then(setRun);
    const stream = new EventSource(`${API}/api/runs/${runId}/events`);
    stream.onmessage = (message) => {
      const event: Event = JSON.parse(message.data);
      setEvents((current) => [...current.filter((item) => item.stage !== event.stage), event]);
      setRun((current) => current ? { ...current, status: event.status as Run["status"], progress: event.progress, current_stage: event.stage } : current);
      if (["completed", "failed"].includes(event.status)) stream.close();
    };
    return () => stream.close();
  }, [runId]);

  if (!user) return <AppShell><Loading /></AppShell>;
  const complete = run?.status === "completed";
  return (
    <AppShell user={user}>
      <div className="mx-auto max-w-3xl py-4">
        <Badge className="bg-brand-50 text-brand-700">{MODE_LABEL[run?.mode ?? "local"]}</Badge>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight">Building the Ibrance learning course</h1>
        <p className="mt-2 text-stone-600">Every handoff between the agents, as it happens — research gathers the evidence, an author writes from it, and a checker verifies each citation against the stored sources before anything reaches a reviewer.</p>
        <Card className="mt-7 overflow-hidden"><CardContent className="p-0">
          <div className="bg-surface-deep p-6 text-white"><div className="flex items-center justify-between"><span className="flex items-center gap-2 font-medium">{complete ? <Check size={19} /> : <LoaderCircle className="animate-spin" size={19} />} {complete ? "Generation complete" : "Agent working"}</span><span className="text-2xl font-semibold">{run?.progress ?? 0}%</span></div><Progress value={run?.progress ?? 0} className="mt-4 bg-white/20" /></div>
          <AgentSequence steps={events} running={!complete} />
        </CardContent></Card>
        {complete && <div className="mt-6 flex justify-end"><Button nativeButton={false} render={<Link href={`/courses/${runId}`} />} className="bg-brand-600 hover:bg-brand-800"><Sparkles /> Send for review</Button></div>}
      </div>
    </AppShell>
  );
}

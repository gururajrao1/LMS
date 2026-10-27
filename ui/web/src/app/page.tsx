"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle2, FileText, Presentation, Video } from "lucide-react";
import { Brand, ROLE_LABEL } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { getJson, Person, Role, sendJson } from "@/lib/api";
import { HOME, writeSession } from "@/lib/session";

const ROLES: { role: Role; blurb: string }[] = [
  { role: "admin", blurb: "Create courses, publish and schedule training" },
  { role: "reviewer", blurb: "Review content and sign it off" },
  { role: "msl", blurb: "Field medical training track" },
  { role: "hcp", blurb: "Clinical training track" },
];

export default function Login() {
  const router = useRouter();
  const [people, setPeople] = useState<Person[]>([]);
  const [role, setRole] = useState<Role>("admin");
  const [userId, setUserId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => { getJson<Person[]>("/api/people").then(setPeople).catch(() => setError("Start the API on port 8000 to sign in.")); }, []);

  const matching = people.filter((person) => person.role === role);
  const selected = matching.find((person) => person.id === userId) ?? matching[0];

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    try {
      const person = await sendJson<Person>("/api/session", { user_id: selected.id });
      writeSession(person);
      router.push(HOME[person.role]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not sign in"); }
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      {/* Deepest surface, not the slab green: over a full half-screen the mid step
          flattens out, and white type needs the extra depth behind it. */}
      <section className="relative hidden overflow-hidden bg-surface-deeper p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute inset-0 opacity-25 [background-image:radial-gradient(circle_at_15%_10%,var(--color-brand-500),transparent_45%),radial-gradient(circle_at_85%_75%,var(--color-signal-600),transparent_40%)]" />
        <div className="relative"><Brand dark /></div>
        <div className="relative max-w-xl">
          <p className="mb-5 text-sm font-semibold uppercase tracking-[.18em] text-brand-400">Medical learning, built with evidence</p>
          <h1 className="text-5xl font-semibold leading-[1.08] tracking-tight">Turn trusted sources into field-ready training.</h1>
          <div className="mt-10 grid grid-cols-3 gap-3 text-sm">
            {[[Presentation, "PPTX"], [Video, "Storyboard"], [FileText, "FAQ + Quiz"]].map(([Icon, label]) => {
              const AssetIcon = Icon as typeof Presentation;
              return <div key={label as string} className="rounded-xl border border-white/15 bg-white/8 p-4"><AssetIcon className="mb-3 text-brand-300" size={22} />{label as string}</div>;
            })}
          </div>
        </div>
        <p className="relative flex items-center gap-2 text-sm text-stone-300"><CheckCircle2 size={16} /> Every learning claim remains traceable.</p>
      </section>

      <section className="flex items-center justify-center bg-white px-6 py-12">
        <form onSubmit={submit} className="w-full max-w-md">
          <div className="mb-10 lg:hidden"><Brand /></div>
          <p className="text-sm font-semibold text-brand-700">Welcome back</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight">Sign in to PharmaLearn</h2>
          <p className="mt-2 text-sm leading-6 text-stone-600">Choose a role, then the person you want to sign in as.</p>

          <div className="mt-7 grid grid-cols-2 gap-2">
            {ROLES.map((entry) => (
              <button key={entry.role} type="button" aria-pressed={role === entry.role} onClick={() => { setRole(entry.role); setUserId(""); }}
                className={`rounded-xl border p-3 text-left transition-colors ${role === entry.role ? "border-brand-600 bg-brand-50" : "hover:bg-stone-50"}`}>
                <p className="text-sm font-semibold">{ROLE_LABEL[entry.role]}</p>
                <p className="mt-1 text-xs leading-5 text-stone-600">{entry.blurb}</p>
              </button>
            ))}
          </div>

          <div className="mt-5 space-y-2">
            {matching.map((person) => (
              <button key={person.id} type="button" aria-pressed={selected?.id === person.id} onClick={() => setUserId(person.id)}
                className={`flex w-full items-center justify-between gap-3 rounded-xl border p-3 text-left transition-colors ${selected?.id === person.id ? "border-brand-600 bg-brand-50" : "hover:bg-stone-50"}`}>
                <span>
                  <span className="block text-sm font-medium">{person.name}</span>
                  <span className="block text-xs text-stone-600">{person.title}</span>
                </span>
                {selected?.id === person.id && <CheckCircle2 size={17} className="shrink-0 text-brand-700" />}
              </button>
            ))}
            {!matching.length && !error && <p className="text-sm text-stone-600">Loading the demo roster…</p>}
          </div>

          {error && <p className="mt-5 text-sm text-danger-600">{error}</p>}
          <Button type="submit" disabled={!selected} className="mt-7 h-11 w-full bg-brand-600 hover:bg-brand-800">Sign in{selected ? ` as ${selected.name}` : ""} <ArrowRight /></Button>
          <p className="mt-6 text-center text-xs text-stone-500">For authorized medical education use</p>
        </form>
      </section>
    </main>
  );
}

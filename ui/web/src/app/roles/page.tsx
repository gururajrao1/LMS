"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { KeyRound, ShieldCheck, Trash2, UserCog } from "lucide-react";
import { AppShell, Loading, roleLabel } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { Capability, Person, RoleEntry, getJson, sendJson } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function RolesPage() {
  const user = useSession(["admin"], { capability: "roster.manage" });
  const [roles, setRoles] = useState<RoleEntry[]>([]);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [label, setLabel] = useState("");
  const [description, setDescription] = useState("");
  const [grants, setGrants] = useState<string[]>([]);
  const [learner, setLearner] = useState(false);
  const [track, setTrack] = useState("hcp");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(() => {
    if (!user) return;
    getJson<RoleEntry[]>("/api/roles").then(setRoles).catch(() => setError("Could not load roles."));
    getJson<Capability[]>("/api/capabilities").then(setCapabilities).catch(() => undefined);
    getJson<Person[]>("/api/people").then(setPeople).catch(() => setError("Could not load the roster."));
  }, [user]);

  useEffect(refresh, [refresh]);

  if (!user) return <AppShell><Loading /></AppShell>;

  const builtins = roles.filter((entry) => entry.builtin);
  const custom = roles.filter((entry) => !entry.builtin);

  function toggleGrant(id: string) {
    setGrants((current) => current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id]);
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      const entry = await sendJson<RoleEntry>("/api/roles", {
        by_user_id: user.id, label, description, capabilities: grants, learner, track,
      });
      setLabel(""); setDescription(""); setGrants([]); setLearner(false); setTrack("hcp");
      setNotice(`Role “${entry.label}” created — assign people to it below.`);
      refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not create the role"); }
    finally { setBusy(false); }
  }

  async function assign(person: Person, roleId: string) {
    setError(""); setNotice("");
    try {
      await sendJson(`/api/people/${person.id}/role`, { by_user_id: user!.id, role_id: roleId });
      setNotice(`${person.name} is now ${roleLabel(roleId)}.`);
      refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not assign the role"); }
  }

  async function remove(entry: RoleEntry) {
    setError(""); setNotice("");
    try {
      const response = await fetch(`/api/roles/${entry.id}?by_user_id=${user!.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Could not delete the role");
      setNotice(`Role “${entry.label}” deleted.`);
      refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not delete the role"); }
  }

  return (
    <AppShell user={user}>
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold text-brand-700">TEAM</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Roles & permissions</h1>
          <p className="mt-2 text-stone-600">Built-in roles keep their powers. Custom roles grant exactly the capabilities you tick — and every gated action checks them.</p>
        </div>
      </div>

      {(error || notice) && (
        <p className={`mt-5 text-sm ${error ? "text-danger-600" : "text-brand-700"}`}>{error || notice}</p>
      )}

      <Card className="mt-7">
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><ShieldCheck size={17} className="text-brand-700" /> Built-in roles</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {builtins.map((entry) => (
            <div key={entry.id} className="rounded-xl border p-4">
              <p className="font-medium">{entry.label} <Badge variant="secondary" className="ml-2">built-in</Badge></p>
              <p className="mt-1 text-sm text-stone-600">{entry.description}</p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {entry.capabilities.map((cap) => <Badge key={cap} variant="outline">{capabilities.find((option) => option.id === cap)?.label ?? cap}</Badge>)}
                {!entry.capabilities.length && <span className="text-xs text-stone-500">Learns through assignments — no staff permissions.</span>}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><KeyRound size={17} className="text-brand-700" /> Build a custom role</CardTitle>
            <p className="mt-2 text-sm text-stone-600">Example: an <b>Instructor</b> with sign-off and settle rights but no roster access; a <b>Trainee nurse</b> learner on the HCP track.</p>
          </CardHeader>
          <CardContent>
            <form onSubmit={create} className="space-y-4">
              <div>
                <label htmlFor="role-label" className="text-sm font-medium">Role name</label>
                <Input id="role-label" value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Instructor" className="mt-2 h-9" />
              </div>
              <div>
                <label htmlFor="role-description" className="text-sm font-medium">What is it for</label>
                <Textarea id="role-description" value={description} onChange={(event) => setDescription(event.target.value)} rows={2} className="mt-2" placeholder="Field trainers who review content but do not manage people" />
              </div>
              <div>
                <p className="text-sm font-medium">Capabilities ({grants.length} selected)</p>
                <div className="mt-2 space-y-2">
                  {capabilities.map((option) => (
                    <label key={option.id} className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors ${grants.includes(option.id) ? "border-brand-600 bg-brand-50" : "hover:bg-stone-50"}`}>
                      <input type="checkbox" checked={grants.includes(option.id)} onChange={() => toggleGrant(option.id)} className="mt-1 size-4 accent-brand-600" />
                      <span>
                        <span className="block text-sm font-medium">{option.label}</span>
                        <span className="block text-xs leading-5 text-stone-600">{option.description}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="flex cursor-pointer items-center gap-3 rounded-xl border p-3">
                  <input type="checkbox" checked={learner} onChange={(event) => setLearner(event.target.checked)} className="size-4 accent-brand-600" />
                  <span className="text-sm font-medium">Trains as a learner</span>
                </label>
                {learner && (
                  <div>
                    <label htmlFor="role-track" className="text-sm font-medium">Content track</label>
                    <NativeSelect id="role-track" value={track} onChange={(event) => setTrack(event.target.value)} className="mt-2 h-9">
                      <option value="msl">MSL track</option>
                      <option value="hcp">HCP track</option>
                    </NativeSelect>
                  </div>
                )}
              </div>
              <Button type="submit" disabled={busy || !label.trim()} className="bg-brand-600 hover:bg-brand-800"><KeyRound /> Create role</Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Custom roles ({custom.length})</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {custom.map((entry) => (
              <div key={entry.id} className="rounded-xl border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">{entry.label}</p>
                    {entry.description && <p className="mt-1 text-sm text-stone-600">{entry.description}</p>}
                    <p className="mt-1 text-xs text-stone-500">
                      {entry.learner ? `Learner · ${entry.track.toUpperCase()} track` : "Staff"} · {entry.capabilities.length} capabilit{entry.capabilities.length === 1 ? "y" : "ies"}
                    </p>
                  </div>
                  <Button variant="outline" onClick={() => remove(entry)} aria-label={`Delete ${entry.label}`}><Trash2 size={15} /></Button>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {entry.capabilities.map((cap) => <Badge key={cap} variant="outline">{capabilities.find((option) => option.id === cap)?.label ?? cap}</Badge>)}
                </div>
              </div>
            ))}
            {!custom.length && <p className="py-6 text-center text-sm text-stone-600">No custom roles yet — build the first one.</p>}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-5">
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><UserCog size={17} className="text-brand-700" /> Assign roles</CardTitle>
          <p className="mt-2 text-sm text-stone-600">Moving someone changes what they may do from their next sign-in.</p>
        </CardHeader>
        <CardContent className="space-y-3">
          {people.map((person) => (
            <div key={person.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3">
              <div className="min-w-0">
                <p className="text-sm font-medium">{person.name}</p>
                <p className="text-xs text-stone-600">{roleLabel(person.role)} · {person.title}</p>
              </div>
              <NativeSelect value={person.role} onChange={(event) => assign(person, event.target.value)} className="h-9 w-48" aria-label={`Role for ${person.name}`}>
                {roles.map((entry) => <option key={entry.id} value={entry.id}>{entry.label}{entry.builtin ? "" : " (custom)"}</option>)}
              </NativeSelect>
            </div>
          ))}
        </CardContent>
      </Card>
    </AppShell>
  );
}

"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getJson, NearbyRank, Person, sendJson } from "@/lib/api";

/** Opt-in peer board on the learner's own home: your rank plus anonymized neighbors.

Peer names never reach this component — the server sends ranks and points
only — and opting out removes you from every peer-visible list entirely.
The admin totals board is unaffected.
*/
export function PeerBoard({ userId }: { userId: string }) {
  const [optedIn, setOptedIn] = useState<boolean | null>(null);
  const [nearby, setNearby] = useState<NearbyRank | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = async (optIn: boolean) => {
    if (!optIn) { setNearby(null); return; }
    try {
      setNearby(await getJson<NearbyRank>(
        `/api/leaderboard/nearby?by_user_id=${encodeURIComponent(userId)}&user_id=${encodeURIComponent(userId)}`));
    } catch { setError("Could not load your nearby rank."); }
  };

  useEffect(() => {
    getJson<Person[]>("/api/people")
      .then((people) => {
        const on = !!people.find((entry) => entry.id === userId)?.board_opt_in;
        setOptedIn(on);
        void refresh(on);
      })
      .catch(() => setError("Could not load the peer board."));
  }, [userId]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = async (next: boolean) => {
    setBusy(true); setError("");
    try {
      await sendJson(`/api/people/${userId}/board-opt-in`, { by_user_id: userId, opt_in: next });
      setOptedIn(next);
      await refresh(next);
    } catch { setError("That did not work — try again."); }
    finally { setBusy(false); }
  };

  return (
    <Card className="mt-8">
      <CardHeader><CardTitle className="text-base">Peer board</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <label className="flex cursor-pointer items-start gap-2.5 text-sm">
          <input type="checkbox" className="mt-1 size-4 shrink-0 accent-brand-600"
            checked={!!optedIn} disabled={busy || optedIn === null}
            onChange={(event) => void toggle(event.target.checked)} />
          <span>Show me against nearby learners
            <span className="text-stone-600 dark:text-muted-foreground"> — opt-in only, neighbors stay anonymous, and opting out removes you entirely.</span>
          </span>
        </label>
        {optedIn && nearby && (
          <div>
            <p className="text-sm">You are <b>#{nearby.rank} of {nearby.of}</b> with <b>{nearby.points} pts</b>.</p>
            <ul className="mt-2 space-y-1.5">
              {nearby.neighbors.map((entry) => (
                <li key={entry.rank}
                  className={`flex items-center gap-3 rounded-lg border px-3 py-1.5 text-sm ${entry.you ? "border-brand-600 bg-white dark:bg-surface font-semibold" : "border-stone-200 dark:border-stone-800"}`}>
                  <span className="w-8 tabular-nums text-stone-500 dark:text-stone-400">#{entry.rank}</span>
                  <span>{entry.you ? "You" : "Fellow learner"}</span>
                  <span className="ml-auto tabular-nums">{entry.points} pts</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {error && <p className="text-sm text-danger-600 dark:text-danger-300">{error}</p>}
      </CardContent>
    </Card>
  );
}

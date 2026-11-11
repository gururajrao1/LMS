"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getJson, NearbyRank, Person, sendJson, TeamBoard } from "@/lib/api";

/** Opt-in peer boards on the learner's own home: your rank plus anonymized
neighbors, plus a team board when the training team assigned you to a team.

Peer names never reach this component — the server sends ranks and points
only. A private profile hides you from every peer-visible board at once, and
managers keep their own compliance views, which this card never touches.
*/
export function PeerBoard({ userId }: { userId: string }) {
  const [optedIn, setOptedIn] = useState<boolean | null>(null);
  const [isPrivate, setIsPrivate] = useState(false);
  const [team, setTeam] = useState("");
  const [nearby, setNearby] = useState<NearbyRank | null>(null);
  const [teamBoard, setTeamBoard] = useState<TeamBoard | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = async (optIn: boolean, privateProfile: boolean, teamName: string) => {
    if (!optIn || privateProfile) { setNearby(null); setTeamBoard(null); return; }
    try {
      setNearby(await getJson<NearbyRank>(
        `/api/leaderboard/nearby?by_user_id=${encodeURIComponent(userId)}&user_id=${encodeURIComponent(userId)}`));
    } catch { setError("Could not load your nearby rank."); }
    if (teamName) {
      try {
        setTeamBoard(await getJson<TeamBoard>(
          `/api/leaderboard/team?by_user_id=${encodeURIComponent(userId)}&user_id=${encodeURIComponent(userId)}&team=${encodeURIComponent(teamName)}`));
      } catch { setTeamBoard(null); }
    } else {
      setTeamBoard(null);
    }
  };

  useEffect(() => {
    getJson<Person[]>("/api/people")
      .then((people) => {
        const me = people.find((entry) => entry.id === userId);
        const on = !!me?.board_opt_in;
        const hidden = !!me?.private_profile;
        const teamName = me?.team ?? "";
        setOptedIn(on && !hidden);
        setIsPrivate(hidden);
        setTeam(teamName);
        void refresh(on, hidden, teamName);
      })
      .catch(() => setError("Could not load the peer board."));
  }, [userId]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleOptIn = async (next: boolean) => {
    setBusy(true); setError("");
    try {
      await sendJson(`/api/people/${userId}/board-opt-in`, { by_user_id: userId, opt_in: next });
      setOptedIn(next);
      await refresh(next, isPrivate, team);
    } catch { setError("That did not work — try again."); }
    finally { setBusy(false); }
  };

  const togglePrivacy = async (next: boolean) => {
    setBusy(true); setError("");
    try {
      await sendJson(`/api/people/${userId}/privacy`, { by_user_id: userId, private: next });
      setIsPrivate(next);
      if (next) setOptedIn(false);
      await refresh(next ? optedIn ?? false : false, next, team);
    } catch { setError("That did not work — try again."); }
    finally { setBusy(false); }
  };

  return (
    <Card className="mt-8">
      <CardHeader><CardTitle className="text-base">Peer board</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <label className="flex cursor-pointer items-start gap-2.5 text-sm">
          <input type="checkbox" className="mt-1 size-4 shrink-0 accent-brand-600"
            checked={isPrivate} disabled={busy}
            onChange={(event) => void togglePrivacy(event.target.checked)} />
          <span>Keep my completions private
            <span className="text-stone-600 dark:text-muted-foreground"> — hides you from every peer board. Managers still see their own reports.</span>
          </span>
        </label>
        {!isPrivate && (
          <label className="flex cursor-pointer items-start gap-2.5 text-sm">
            <input type="checkbox" className="mt-1 size-4 shrink-0 accent-brand-600"
              checked={!!optedIn} disabled={busy || optedIn === null}
              onChange={(event) => void toggleOptIn(event.target.checked)} />
            <span>Show me against nearby learners
              <span className="text-stone-600 dark:text-muted-foreground"> — opt-in only, neighbors stay anonymous, and opting out removes you entirely.</span>
            </span>
          </label>
        )}
        {isPrivate && (
          <p className="rounded-lg bg-stone-100 dark:bg-muted p-3 text-sm text-stone-600 dark:text-muted-foreground">
            Your completions are hidden from peers. Turn this off to compete again.
          </p>
        )}
        {optedIn && nearby && !isPrivate && (
          <RankList name="Everyone" rank={nearby} />
        )}
        {optedIn && teamBoard && !isPrivate && (
          <RankList name={teamBoard.team} rank={teamBoard} />
        )}
        {error && <p className="text-sm text-danger-600 dark:text-danger-300">{error}</p>}
      </CardContent>
    </Card>
  );
}

function RankList({ name, rank }: { name: string; rank: NearbyRank }) {
  return (
    <div>
      <p className="text-sm text-stone-600 dark:text-muted-foreground">{name}</p>
      <p className="mt-0.5 text-sm">You are <b>#{rank.rank} of {rank.of}</b> with <b>{rank.points} pts</b>.</p>
      <ul className="mt-2 space-y-1.5">
        {rank.neighbors.map((entry) => (
          <li key={entry.rank}
            className={`flex items-center gap-3 rounded-lg border px-3 py-1.5 text-sm ${entry.you ? "border-brand-600 bg-white dark:bg-surface font-semibold" : "border-stone-200 dark:border-stone-800"}`}>
            <span className="w-8 tabular-nums text-stone-500 dark:text-stone-400">#{entry.rank}</span>
            <span>{entry.you ? "You" : "Fellow learner"}</span>
            <span className="ml-auto tabular-nums">{entry.points} pts</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

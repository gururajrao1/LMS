"use client";

import { useEffect, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { Person } from "@/lib/api";

const KEY = "pharmalearn.session";

export const HOME: Record<string, string> = { admin: "/dashboard", reviewer: "/dashboard", checker: "/", msl: "/learn", hcp: "/learn" };

/** Where a person lands: built-in mapping first, then learnerhood, then staff. */
export function homeFor(person: Person): string {
  if (HOME[person.role]) return HOME[person.role];
  if (person.learner ?? (person.role === "msl" || person.role === "hcp")) return "/learn";
  return "/dashboard";
}

export type SessionGate = { anyLearner?: boolean; anyStaff?: boolean; capability?: string };

/** Whether the gate admits this person: named roles, any learner, any staffer, or a capability. */
export function admits(person: Person, allowed: string[] | undefined, gate: SessionGate = {}): boolean {
  if (!allowed) return true;
  if (allowed.includes(person.role)) return true;
  const learner = person.learner ?? (person.role === "msl" || person.role === "hcp");
  if (gate.anyLearner && learner) return true;
  if (gate.anyStaff && (person.capabilities ?? []).length > 0) return true;
  if (gate.capability && (person.capabilities ?? []).includes(gate.capability)) return true;
  return false;
}

const listeners = new Set<() => void>();
let cache: { raw: string | null; person: Person | null } = { raw: null, person: null };

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

/** Cached so repeated reads return the same object, as useSyncExternalStore requires. */
function getSnapshot(): Person | null {
  let raw: string | null = null;
  try { raw = window.localStorage.getItem(KEY); } catch { raw = null; }
  if (raw !== cache.raw) {
    let person: Person | null = null;
    try { person = raw ? (JSON.parse(raw) as Person) : null; } catch { person = null; }
    cache = { raw, person };
  }
  return cache.person;
}

const getServerSnapshot = (): Person | null => null;

export function readSession(): Person | null {
  return typeof window === "undefined" ? null : getSnapshot();
}

export function writeSession(person: Person | null) {
  if (person) window.localStorage.setItem(KEY, JSON.stringify(person));
  else window.localStorage.removeItem(KEY);
  listeners.forEach((listener) => listener());
}

/** The signed-in person, sending anyone without a session (or without access) somewhere useful. */
export function useSession(allowed?: string[], gate: SessionGate = {}) {
  const router = useRouter();
  const person = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const { anyLearner, anyStaff, capability } = gate;
  const roles = allowed?.join(",");
  const permitted = person !== null && admits(person, allowed, { anyLearner, anyStaff, capability });

  useEffect(() => {
    // Read the store here rather than trusting `person`: on the hydration pass it is
    // still the server snapshot (null), which would bounce a signed-in visitor to login.
    const current = getSnapshot();
    if (!current) router.replace("/");
    else if (roles && !admits(current, roles.split(","), { anyLearner, anyStaff, capability })) router.replace(homeFor(current));
  }, [person, roles, router, anyLearner, anyStaff, capability]);

  return permitted ? person : null;
}

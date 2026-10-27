"use client";

import { useEffect, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { Person, Role } from "@/lib/api";

const KEY = "pharmalearn.session";

export const HOME: Record<Role, string> = { admin: "/dashboard", reviewer: "/dashboard", checker: "/", msl: "/learn", hcp: "/learn" };

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

/** The signed-in person, sending anyone without a session (or with the wrong role) somewhere useful. */
export function useSession(allowed?: Role[]) {
  const router = useRouter();
  const person = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const roles = allowed?.join(",");
  const permitted = person !== null && (!roles || roles.split(",").includes(person.role));

  useEffect(() => {
    // Read the store here rather than trusting `person`: on the hydration pass it is
    // still the server snapshot (null), which would bounce a signed-in visitor to login.
    const current = getSnapshot();
    if (!current) router.replace("/");
    else if (roles && !roles.split(",").includes(current.role)) router.replace(HOME[current.role]);
  }, [person, roles, router]);

  return permitted ? person : null;
}

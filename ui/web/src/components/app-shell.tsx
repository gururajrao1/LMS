"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BookOpen, Database, GraduationCap, KeyRound, LayoutDashboard, LogOut, ShieldCheck, TrendingUp } from "lucide-react";
import { Person } from "@/lib/api";
import { writeSession } from "@/lib/session";

type NavLink = { href: string; label: string; icon: typeof LayoutDashboard };

const STAFF_NAV: NavLink[] = [
  { href: "/dashboard", label: "Review queue", icon: ShieldCheck },
  { href: "/knowledge", label: "Knowledge hub", icon: Database },
];

const NAV: Record<string, NavLink[]> = {
  admin: [
    { href: "/dashboard", label: "Courses", icon: LayoutDashboard },
    { href: "/portfolio", label: "Portfolio", icon: TrendingUp },
    { href: "/knowledge", label: "Knowledge hub", icon: Database },
    { href: "/roles", label: "Roles", icon: KeyRound },
  ],
  reviewer: [
    { href: "/dashboard", label: "Review queue", icon: ShieldCheck },
    { href: "/knowledge", label: "Knowledge hub", icon: Database },
  ],
  checker: [],
  msl: [{ href: "/learn", label: "My training", icon: GraduationCap }],
  hcp: [{ href: "/learn", label: "My training", icon: GraduationCap }],
};

export const ROLE_LABEL: Record<string, string> = { admin: "Admin", reviewer: "Reviewer", checker: "Automated check", msl: "MSL", hcp: "HCP" };

/** Navigation for anyone: built-in mapping first, then learnerhood, then staff fallback. */
export function navFor(user: Person): NavLink[] {
  if (NAV[user.role]) return NAV[user.role];
  if (user.learner ?? (user.role === "msl" || user.role === "hcp")) {
    return [{ href: "/learn", label: "My training", icon: GraduationCap }];
  }
  const links = [...STAFF_NAV];
  if ((user.capabilities ?? []).includes("roster.manage")) {
    links.push({ href: "/roles", label: "Roles", icon: KeyRound });
  }
  return (user.capabilities ?? []).length ? links : [];
}

/** Display name for any role: built-in label first, then the custom id. */
export function roleLabel(role: string): string {
  return ROLE_LABEL[role] ?? role;
}

export function Brand({ dark = false, href = "/" }: { dark?: boolean; href?: string }) {
  return (
    <Link href={href} className={`flex items-center gap-2 font-bold tracking-tight ${dark ? "text-white" : "text-ink"}`}>
      <span className="grid size-9 place-items-center rounded-xl bg-brand-600 text-white"><BookOpen size={19} /></span>
      PharmaLearn
    </Link>
  );
}

export function AppShell({ children, user }: { children: React.ReactNode; user?: Person | null }) {
  const pathname = usePathname();
  const router = useRouter();
  const links = user ? navFor(user) : [];

  function signOut() {
    writeSession(null);
    router.replace("/");
  }

  return (
    <div className="app-shell min-h-screen bg-surface-sunk text-ink">
      <header className="border-b bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-5 lg:px-8">
          <div className="flex items-center gap-8">
            <Brand href={links[0]?.href ?? "/"} />
            <nav className="hidden items-center gap-1 md:flex">
              {links.map(({ href, label, icon: Icon }) => (
                <Link key={href} href={href} aria-current={pathname.startsWith(href) ? "page" : undefined}
                  className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${pathname.startsWith(href) ? "bg-brand-50 text-brand-700" : "text-stone-600 hover:bg-stone-100"}`}>
                  <Icon size={16} /> {label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            {user && (
              <div className="hidden text-right sm:block">
                <p className="font-medium leading-5">{user.name}</p>
                <p className="text-xs text-stone-600">{roleLabel(user.role)} · {user.title}</p>
              </div>
            )}
            {user && <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-50 text-sm font-semibold text-brand-700">{initials(user.name)}</span>}
            <button type="button" onClick={signOut} aria-label="Sign out" className="rounded-lg p-2 text-stone-600 hover:bg-stone-100"><LogOut size={17} /></button>
          </div>
        </div>
        {links.length > 1 && (
          <nav className="flex gap-1 overflow-x-auto border-t px-5 py-2 md:hidden">
            {links.map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href} aria-current={pathname.startsWith(href) ? "page" : undefined}
                className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${pathname.startsWith(href) ? "bg-brand-50 text-brand-700" : "text-stone-600"}`}>
                <Icon size={16} /> {label}
              </Link>
            ))}
          </nav>
        )}
      </header>
      <main className="mx-auto max-w-7xl px-5 py-8 lg:px-8">{children}</main>
    </div>
  );
}

function initials(name: string) {
  return name.replace(/^Dr\.?\s+/i, "").split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

export { CitationChip, Cites } from "@/components/evidence";

/**
 * Tones are named for the job, not the hue: `brand` is the default, `signal`
 * marks anything the automated checker produced, `warn` is a reserved status.
 */
export function Stat({ icon: Icon, value, label, tone = "brand" }: { icon: typeof LayoutDashboard; value: string | number; label: string; tone?: "brand" | "signal" | "warn" }) {
  const tones = { brand: "bg-brand-50 text-brand-700", signal: "bg-signal-50 text-signal-700", warn: "bg-warn-50 text-warn-700" };
  return (
    <div className="flex items-center gap-4 rounded-xl border border-line bg-white p-5">
      <span className={`grid size-11 shrink-0 place-items-center rounded-xl ${tones[tone]}`}><Icon size={21} /></span>
      <div>
        <p className="text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
        <p className="text-sm leading-5 text-stone-600">{label}</p>
      </div>
    </div>
  );
}

function Block({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-stone-200/70 ${className}`} />;
}

/** A layout-shaped placeholder, so a page does not jump when its data lands. */
export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-6">
      <div className="space-y-3">
        <Block className="h-4 w-32" />
        <Block className="h-9 w-72 max-w-full" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((index) => <Block key={index} className="h-[92px]" />)}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {[0, 1].map((index) => <Block key={index} className="h-56" />)}
      </div>
      <span className="sr-only">{label}</span>
    </div>
  );
}

"use client";

import { ChevronDown } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

export type NavItem = { value: string; label: string; icon: LucideIcon; count?: number };

/**
 * A named group of panels. One item collapses to a plain button rather than a
 * dropdown with a single entry, so a section that a role can only partly see —
 * a reviewer's Governance without Publish — still reads as one clean control.
 */
export type NavSection = { label: string; icon: LucideIcon; items: NavItem[] };

const CHIP = "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors";
const ACTIVE = "bg-brand-50 text-brand-700";
const IDLE = "text-stone-600 hover:bg-stone-100";

/** A count that must stay visible once its item is folded into a dropdown. */
function Count({ value, active }: { value: number; active: boolean }) {
  return (
    <span className={`grid h-5 min-w-5 place-items-center rounded-full px-1.5 text-xs font-semibold tabular-nums ${active ? "bg-brand-600 text-white" : "bg-stone-200 text-stone-700"}`}>
      {value}
    </span>
  );
}

export function SectionNav({ sections, value, onValueChange, className = "" }: {
  sections: NavSection[];
  value: string;
  onValueChange: (value: string) => void;
  className?: string;
}) {
  return (
    <nav aria-label="Course workspace sections" className={`flex max-w-full flex-wrap items-center gap-1 rounded-xl border bg-white p-1.5 shadow-sm ${className}`}>
      {sections.map((section) => {
        if (!section.items.length) return null;

        if (section.items.length === 1) {
          const [item] = section.items;
          const active = item.value === value;
          const Icon = item.icon;
          return (
            <button key={section.label} type="button" aria-current={active ? "true" : undefined} onClick={() => onValueChange(item.value)} className={`${CHIP} ${active ? ACTIVE : IDLE}`}>
              <Icon size={16} /> {item.label}
              {item.count ? <Count value={item.count} active={active} /> : null}
            </button>
          );
        }

        const open = section.items.find((item) => item.value === value);
        const count = section.items.reduce((total, item) => total + (item.count ?? 0), 0);
        const Icon = open?.icon ?? section.icon;
        return (
          <DropdownMenu key={section.label}>
            <DropdownMenuTrigger className={`group/section ${CHIP} ${open ? ACTIVE : IDLE}`}>
              <Icon size={16} /> {section.label}
              {open && <span className="text-brand-600/80">· {open.label}</span>}
              {count > 0 && <Count value={count} active={Boolean(open)} />}
              <ChevronDown size={15} className="opacity-60 transition-transform group-data-[popup-open]/section:rotate-180" />
            </DropdownMenuTrigger>
            {/* Overrides the registry's default of matching the trigger width. */}
            <DropdownMenuContent className="w-auto min-w-52 p-1.5">
              <DropdownMenuRadioGroup value={value} onValueChange={(next) => onValueChange(String(next))}>
                <DropdownMenuLabel>{section.label}</DropdownMenuLabel>
                {section.items.map((item) => {
                  const ItemIcon = item.icon;
                  return (
                    <DropdownMenuRadioItem key={item.value} value={item.value} closeOnClick className="gap-2.5 px-1.5 py-2 font-medium data-checked:text-brand-700">
                      <ItemIcon size={16} />
                      <span className="flex-1">{item.label}</span>
                      {item.count ? <Count value={item.count} active={item.value === value} /> : null}
                    </DropdownMenuRadioItem>
                  );
                })}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        );
      })}
    </nav>
  );
}

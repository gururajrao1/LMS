/** Red/amber/green criticality labels shared by every surface that lists work. */

export type Rag = "red" | "amber" | "green" | "neutral";

export const RAG_BADGE: Record<Rag, string> = {
  red: "bg-danger-50 text-danger-700",
  amber: "bg-warn-50 text-warn-700",
  green: "bg-brand-50 text-brand-700",
  neutral: "bg-stone-100 text-stone-600",
};

export const RAG_DOT: Record<Rag, string> = {
  red: "bg-danger-500",
  amber: "bg-warn-500",
  green: "bg-brand-600",
  neutral: "bg-stone-300",
};

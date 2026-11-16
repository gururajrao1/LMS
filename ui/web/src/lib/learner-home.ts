import type { Assignment } from "./api";

export type DashboardAlert = {
  user_id: string;
  name: string;
  run_id: string;
  kind: "overdue" | "below_requirement" | "unbaselined";
  severity: "danger" | "warning";
  tier: number;
  message: string;
};

export type Nudge = { key: string; title: string; message: string; href: string; urgent: boolean };

/** Server flags plus due-soon courses, each with a deep link to the fix. */
export function buildNudges(courses: Assignment[], alerts: DashboardAlert[]): Nudge[] {
  const byRun: Record<string, Assignment> = Object.fromEntries(courses.map((course) => [course.run_id, course]));
  const titleOf = (run_id: string) => byRun[run_id]?.title ?? byRun[run_id]?.drug.brand ?? "Training";
  const nudges: Nudge[] = alerts.map((alert) => ({
    key: `${alert.run_id}-${alert.message}`,
    title: titleOf(alert.run_id),
    message: alert.message,
    href: alert.kind === "overdue"
      ? `/learn/${alert.run_id}`
      : alert.kind === "below_requirement"
        ? `/learn/${alert.run_id}/assessment/final`
        : `/learn/${alert.run_id}/assessment/baseline`,
    urgent: alert.severity === "danger",
  }));
  for (const course of courses) {
    const left = course.days_remaining;
    if (course.state === "due" && left !== null && left >= 0 && left <= 7 && !nudges.some((nudge) => nudge.href === `/learn/${course.run_id}`))
      nudges.push({
        key: `due-${course.run_id}`,
        title: course.title ?? course.drug.brand,
        message: left === 0 ? "Due today — finish it now." : `Due in ${left} ${left === 1 ? "day" : "days"} — still time to stay on plan.`,
        href: `/learn/${course.run_id}`,
        urgent: left <= 2,
      });
  }
  return nudges;
}

export function timing(course: Assignment) {
  const { state, days_remaining: left, days_until_start: until } = course;
  if (state === "completed") return { label: "Complete", urgent: false };
  if (state === "upcoming") return { label: until === 1 ? "Opens tomorrow" : `Opens in ${until} days`, urgent: false };
  if (left === null) return { label: "", urgent: false };
  if (left < 0) return { label: `${Math.abs(left)} ${Math.abs(left) === 1 ? "day" : "days"} overdue`, urgent: true };
  if (left === 0) return { label: "Due today", urgent: true };
  return { label: `${left} ${left === 1 ? "day" : "days"} left`, urgent: left <= 7 };
}

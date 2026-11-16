import { describe, expect, it } from "vitest";
import { buildNudges, timing, type DashboardAlert } from "./learner-home";
import type { Assignment } from "./api";

function course(partial: Partial<Assignment>): Assignment {
  return {
    run_id: "run-1",
    course_type: "drug",
    drug: { brand: "B", generic: "g", area: "a" },
    title: null,
    version: 2,
    starts_on: "2026-11-01",
    due_on: "2026-11-30",
    message: "",
    summary: null as never,
    state: "due",
    days_remaining: 5,
    days_until_start: null,
    ...partial,
  };
}

function alert(partial: Partial<DashboardAlert>): DashboardAlert {
  return {
    user_id: "u", name: "U", run_id: "run-1",
    kind: "overdue", severity: "danger", tier: 1, message: "Overdue.",
    ...partial,
  };
}

describe("timing", () => {
  it("marks overdue and due-today urgent", () => {
    expect(timing(course({ state: "overdue", days_remaining: -3 }))).toEqual({ label: "3 days overdue", urgent: true });
    expect(timing(course({ state: "due", days_remaining: -1 }))).toEqual({ label: "1 day overdue", urgent: true });
    expect(timing(course({ state: "due", days_remaining: 0 }))).toEqual({ label: "Due today", urgent: true });
  });

  it("marks near deadlines urgent and far ones calm", () => {
    expect(timing(course({ state: "due", days_remaining: 20 })).urgent).toBe(false);
    expect(timing(course({ state: "completed", days_remaining: null }))).toEqual({ label: "Complete", urgent: false });
    expect(timing(course({ state: "upcoming", days_until_start: 1 }))).toEqual({ label: "Opens tomorrow", urgent: false });
  });
});

describe("buildNudges", () => {
  it("deep-links each alert kind to its fix", () => {
    const nudges = buildNudges([], [
      alert({ kind: "overdue", run_id: "r1", message: "Late." }),
      alert({ kind: "below_requirement", run_id: "r2", message: "Below." }),
      alert({ kind: "unbaselined", run_id: "r3", message: "No baseline." }),
    ]);
    expect(nudges.map((n) => n.href)).toEqual([
      "/learn/r1",
      "/learn/r2/assessment/final",
      "/learn/r3/assessment/baseline",
    ]);
  });

  it("adds one due-soon nudge per course and never duplicates an alert link", () => {
    const courses = [course({ run_id: "r1", days_remaining: 2 }), course({ run_id: "r9", days_remaining: 30 })];
    const nudges = buildNudges(courses, [alert({ run_id: "r1", kind: "overdue", message: "Late." })]);
    const hrefs = nudges.map((n) => n.href);
    expect(hrefs.filter((h) => h === "/learn/r1")).toHaveLength(1);
    expect(hrefs).not.toContain("/learn/r9");
    expect(nudges.find((n) => n.key === "due-r1")).toBeUndefined();
  });

  it("says due-today when the deadline is today", () => {
    const nudges = buildNudges([course({ run_id: "r1", days_remaining: 0 })], []);
    expect(nudges).toHaveLength(1);
    expect(nudges[0].message).toBe("Due today — finish it now.");
    expect(nudges[0].urgent).toBe(true);
  });
});

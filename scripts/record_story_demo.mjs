/**
 * Full story demo: all major features + publish → trainee completes → cert.
 * Usage (repo root): node scripts/record_story_demo.mjs
 */
import { chromium } from "../ui/web/node_modules/playwright/index.mjs";
import { mkdirSync, copyFileSync, statSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { spawnSync } from "node:child_process";

const BASE = process.env.DEMO_BASE || "http://localhost:3000";
const API = process.env.DEMO_API || "http://127.0.0.1:8000";
const RUN = "patient-recruitment-2026";
const USER = "pattabhi";
const OUT_DIR = join(homedir(), "Videos");
const WORK = join(OUT_DIR, `pharmalearn-story-work-${Date.now()}`);
mkdirSync(WORK, { recursive: true });
mkdirSync(OUT_DIR, { recursive: true });

async function api(method, path, body) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status}: ${text.slice(0, 240)}`);
  return data;
}

async function person(id) {
  const list = await api("GET", "/api/people");
  const hit = list.find((p) => p.id === id);
  if (!hit) throw new Error(`person ${id} missing`);
  return hit;
}

async function resetTrainee() {
  await api("POST", `/api/runs/${RUN}/publication`, {
    user_id: "guru-raja",
    starts_on: "2026-11-17",
    due_on: "2026-11-30",
    assignees: ["guru-raja", "pattabhi", "shashidhar-gururao", "parimala"],
    group_ids: ["clinical-trial"],
    message: "Story demo: 15 min induction — 70% to pass.",
    frequency: "once",
    certificate_template: "modern",
    max_final_attempts: 3,
  });
  try {
    await api("DELETE", `/api/learn/${USER}/${RUN}/attempts?by=guru-raja`);
  } catch {
    /* already clean */
  }
  // Un-complete modules if still marked done after attempt reset.
  const course = await api("GET", `/api/learn/${USER}/${RUN}`);
  for (const module of course.modules || []) {
    if (module.completed) {
      await api("POST", `/api/learn/${USER}/${RUN}/modules`, { module_id: module.id, completed: false });
    }
  }
}

async function setSession(page, who) {
  await page.addInitScript((person) => {
    localStorage.setItem("pharmalearn.session", JSON.stringify(person));
  }, who);
  await page.evaluate((person) => {
    localStorage.setItem("pharmalearn.session", JSON.stringify(person));
  }, who).catch(() => undefined);
}

async function hold(page, ms = 1000) {
  await page.waitForTimeout(ms);
}

async function caption(page, title, detail) {
  await page.evaluate(({ title, detail }) => {
    let bar = document.getElementById("pl-demo-caption");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "pl-demo-caption";
      bar.style.cssText = [
        "position:fixed", "left:16px", "right:16px", "top:12px", "z-index:2147483646",
        "background:rgba(12,22,18,.94)", "color:#f3faf6", "border:1px solid #2f4a3c",
        "border-radius:12px", "padding:12px 16px", "font:600 15px Segoe UI,system-ui,sans-serif",
        "box-shadow:0 10px 30px rgba(0,0,0,.35)", "pointer-events:none",
      ].join(";");
      document.documentElement.appendChild(bar);
    }
    bar.innerHTML = `<div style="font-size:15px">${title}</div>`
      + (detail ? `<div style="margin-top:4px;font-weight:400;color:#a8c4b4;font-size:13px;line-height:1.35">${detail}</div>` : "");
  }, { title, detail });
}

async function hideChrome(page) {
  await page.addStyleTag({
    content: `
      nextjs-portal, [data-nextjs-toast], [data-next-badge-root],
      [data-nextjs-dev-overlay], #__next-build-watcher,
      [aria-label*="Next.js"], [aria-label*="issues"],
      a[href*="__nextjs"], button[aria-label*="issues"] { display: none !important; visibility: hidden !important; }
      #pl-demo-caption { display: block !important; }
    `,
  }).catch(() => undefined);
}

async function gotoReady(page, url, readyText, timeout = 25000) {
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await hideChrome(page);
  if (readyText) {
    await page.waitForFunction(
      (re) => new RegExp(re, "i").test(document.body?.innerText || ""),
      readyText,
      { timeout },
    ).catch(() => undefined);
  }
  await page.waitForLoadState("networkidle").catch(() => undefined);
}

async function openCoursePanel(page, panel) {
  await page.evaluate(({ runId, panel }) => {
    localStorage.setItem(`pharmalearn.panel.${runId}`, panel);
  }, { runId: RUN, panel });
  await gotoReady(page, `${BASE}/courses/${RUN}`, "Patient Recruitment|Publish|Journey|Cohort");
}

async function markModulesDone(page) {
  // Show material, then mark each module complete via UI toggles if present, else API.
  await gotoReady(page, `${BASE}/learn/${RUN}?tab=deck`, "Deck|Learning|modules|Patient");
  await caption(page, "Part 2 — Learning material", "Deck, visual story, FAQ. Empty Videos tab is hidden when there is no video.");
  await hold(page, 1400);

  for (const tab of ["deck", "storyboard", "faq"]) {
    await page.goto(`${BASE}/learn/${RUN}?tab=${tab}`, { waitUntil: "domcontentloaded" });
    await hideChrome(page);
    await caption(page, `Module — ${tab}`, "Trainee reviews the asset, then marks the module complete.");
    await hold(page, 700);
    const mark = page.getByRole("button", { name: /^Mark complete$/i }).first();
    if (await mark.count()) {
      await mark.scrollIntoViewIfNeeded().catch(() => undefined);
      await mark.click();
      await hold(page, 600);
    }
  }

  // Ensure server state is complete even if toggles were already on.
  const course = await api("GET", `/api/learn/${USER}/${RUN}`);
  for (const module of course.modules || []) {
    if (!module.completed) {
      await api("POST", `/api/learn/${USER}/${RUN}/modules`, { module_id: module.id, completed: true });
    }
  }
  await gotoReady(page, `${BASE}/learn/${RUN}`, "Final assessment|4 of 4|modules");
  await caption(page, "Modules complete", "All learning parts done — final assessment unlocks.");
  await hold(page, 1400);
}

async function answerQuizInUi(page) {
  const quiz = JSON.parse(readFileSync(
    join(process.cwd(), ".pharmalearn/content", RUN, "msl/quiz.json"),
    "utf8",
  ));
  // Click the correct option text for each question (stable even if order shuffles).
  for (const q of quiz.questions) {
    const idx = Number(q.correct_index ?? 0);
    const choice = (q.options || [])[idx];
    if (!choice) continue;
    const btn = page.getByRole("button", { name: choice, exact: true }).first();
    if (await btn.count()) {
      await btn.scrollIntoViewIfNeeded().catch(() => undefined);
      await btn.click({ timeout: 5000 }).catch(() => undefined);
      await page.waitForTimeout(90);
    }
  }
}

async function submitAssessment(page, kind) {
  const quiz = JSON.parse(readFileSync(
    join(process.cwd(), ".pharmalearn/content", RUN, "msl/quiz.json"),
    "utf8",
  ));
  const keys = Object.fromEntries(quiz.questions.map((q) => [q.id, q.correct_index]));
  const meta = await api("GET", `/api/learn/${USER}/${RUN}/assessment/${kind}`);
  const answers = Object.fromEntries(
    (meta.questions || []).filter((q) => q.id in keys).map((q) => [q.id, keys[q.id]]),
  );

  // Prefer on-camera submit; fall back to API then show the course journey result.
  await answerQuizInUi(page);
  await hold(page, 500);

  const fill = page.getByRole("button", { name: /Fill the rest and submit/i });
  const submit = page.getByRole("button", { name: /Submit baseline|Submit assessment/i });
  let submittedUi = false;
  if (await fill.count()) {
    await fill.click();
    submittedUi = true;
  } else if (await submit.count()) {
    const enabled = await submit.isEnabled().catch(() => false);
    if (enabled) {
      await submit.click();
      submittedUi = true;
    }
  }

  if (submittedUi) {
    await page.waitForFunction(
      () => /Baseline recorded|Passed|Not passed yet|of .* correct/i.test(document.body?.innerText || ""),
      { timeout: 20000 },
    ).catch(() => { submittedUi = false; });
  }

  if (!submittedUi) {
    await api("POST", `/api/learn/${USER}/${RUN}/assessment/${kind}`, { answers });
    await gotoReady(page, `${BASE}/learn/${RUN}`, "Part 1|Baseline|Patient|Certificate");
  }
}

async function runAssessment(page, kind) {
  const title = kind === "baseline"
    ? "Part 1 — Baseline check"
    : "Part 3 — Final assessment";
  const detail = kind === "baseline"
    ? "Not graded. Records starting knowledge so uplift can be measured after the final."
    : "Pass mark 70%. Trainee answers on camera, then submits for the certificate.";
  await gotoReady(page, `${BASE}/learn/${RUN}/assessment/${kind}`, "Baseline|Final|answered|questions|Submit");
  await caption(page, title, detail);
  await hold(page, 1000);

  await submitAssessment(page, kind);
  await caption(
    page,
    kind === "baseline" ? "Baseline recorded" : "Final passed — certificate unlocked",
    kind === "baseline"
      ? "Cold score saved. Next: work through the modules."
      : "Trainee earned a pass. Next: open the Modern certificate.",
  );
  await hold(page, 1800);
}

async function main() {
  const guru = await person("guru-raja");
  const pattabhi = await person("pattabhi");
  await resetTrainee();

  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-dev-shm-usage"],
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: WORK, size: { width: 1440, height: 900 } },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();
  page.on("load", () => { hideChrome(page).catch(() => undefined); });

  const beats = join(process.cwd(), "scripts/demo_story_beats.html").replace(/\\/g, "/");
  await page.goto(`file://${beats}`, { waitUntil: "domcontentloaded" });
  await hold(page, 2800);

  // --- Admin feature tour ---
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await setSession(page, guru);
  await gotoReady(page, `${BASE}/dashboard`, "Dashboard|Courses|Portfolio|Patient");
  await caption(page, "Admin dashboard", "Guru Raja sees portfolio readiness and which programmes need action.");
  await hold(page, 1600);

  await openCoursePanel(page, "journey");
  await caption(page, "Course journey", "How the induction is structured for HCP/MSL tracks before anyone trains.");
  await hold(page, 1400);

  await openCoursePanel(page, "ppt");
  await caption(page, "Assets — PPTX & learning pack", "Field deck and related assets stay tied to the dossier.");
  await hold(page, 1200);

  await openCoursePanel(page, "sources");
  await caption(page, "Sources", "Every claim stays traceable to source documents.");
  await hold(page, 1200);

  await openCoursePanel(page, "checks");
  await caption(page, "Governance — Checks", "Machine checks run before human review; findings stay auditable.");
  await hold(page, 1300);

  await openCoursePanel(page, "review");
  await caption(page, "Governance — Review", "Experts sign off; open comments must clear before publish.");
  await hold(page, 1200);

  // Publish
  await openCoursePanel(page, "publish");
  await caption(page, "Publish to trainees", "Pick group, Modern certificate, due window, 3 attempts — then notify.");
  await hold(page, 1000);

  const modern = page.locator('label:has-text("Modern")').first();
  if (await modern.count()) {
    await modern.scrollIntoViewIfNeeded();
    await modern.click();
    await hold(page, 500);
  }
  const clinical = page.getByText(/Clinical trial/i).first();
  if (await clinical.count()) {
    await clinical.scrollIntoViewIfNeeded();
    await clinical.click().catch(() => undefined);
    await hold(page, 500);
  }
  await page.evaluate(() => window.scrollBy(0, 340));
  await hold(page, 900);
  await caption(page, "Reach + notifications", "Clinical trial group expands to 4 people; demo notifies locally (not email).");
  await hold(page, 1000);

  const republish = page.getByRole("button", { name: /Republish schedule|Publish v\d/i }).first();
  if (await republish.count()) {
    await republish.scrollIntoViewIfNeeded();
    await republish.click();
    await page.waitForTimeout(900);
  }
  await caption(page, "Published", "Schedule live. Assignees now see the course on Learn.");
  await hold(page, 1400);

  // Cohort before trainee works
  await openCoursePanel(page, "cohort");
  await caption(page, "Cohort — before training", "4 assigned. Watch this board after Pattabhi certifies.");
  await hold(page, 1600);

  // Roles / people briefly
  await gotoReady(page, `${BASE}/roles`, "Roles|Groups|People|capability");
  await caption(page, "Roles & groups", "Managers, groups, and capabilities control who can publish and who trains.");
  await hold(page, 1400);

  // --- Trainee path ---
  await setSession(page, pattabhi);
  await gotoReady(page, `${BASE}/learn`, "Welcome|Patient|My training|Pattabhi");
  await caption(page, "Trainee Learn home", "Pattabhi’s assignment for Patient Recruitment appears after publish.");
  await hold(page, 1700);

  await gotoReady(page, `${BASE}/learn/${RUN}`, "Part 1|Baseline|Patient Recruitment");
  await caption(page, "Course journey (start)", "Parts 1–3. Certificate stays locked until the final is passed.");
  await hold(page, 1600);

  await runAssessment(page, "baseline");

  await markModulesDone(page);

  await runAssessment(page, "final");

  const certBtn = page.getByRole("link", { name: /Get your certificate|View certificate/i })
    .or(page.getByRole("button", { name: /Get your certificate|View certificate/i }))
    .first();
  if (await certBtn.count()) {
    await certBtn.click().catch(() => undefined);
  }
  await gotoReady(page, `${BASE}/learn/${RUN}/certificate`, "Verification code|CERTIFICATE|PL-PATIENT");
  await page.waitForFunction(
    () => /Verification code/i.test(document.body?.innerText || "")
      && /PL-PATIENT/i.test(document.body?.innerText || "")
      && !/Loading your certificate/i.test(document.body?.innerText || ""),
    { timeout: 30000 },
  );
  await caption(page, "Modern certificate issued", "Verification code on the Modern template — printable / save as PDF.");
  await hold(page, 3200);

  // Admin confirms — land on dashboard first so session hydrates before course panels
  await setSession(page, guru);
  await gotoReady(page, `${BASE}/dashboard`, "Guru Raja|Courses|Dashboard|Portfolio");
  await hold(page, 800);

  await openCoursePanel(page, "cohort");
  await page.waitForFunction(
    () => /Learner progress|Certified|Assigned/i.test(document.body?.innerText || "")
      && !/Loading cohort/i.test(document.body?.innerText || ""),
    { timeout: 30000 },
  ).catch(() => undefined);
  await caption(page, "Cohort after certify", "Pattabhi shows Certified with score and certificate code.");
  await hold(page, 1400);
  await page.evaluate(() => window.scrollBy(0, 420));
  await hold(page, 1800);

  await openCoursePanel(page, "impact");
  await page.waitForFunction(
    () => /impact|reach|uplift|programme|certified|completion|consolidated/i.test(document.body?.innerText || "")
      && !/Loading impact/i.test(document.body?.innerText || ""),
    { timeout: 30000 },
  ).catch(() => undefined);
  await caption(page, "Impact", "Programme-level reach, uplift, and completion across the induction.");
  await hold(page, 2000);

  await page.goto(`file://${beats}`, { waitUntil: "domcontentloaded" });
  await hold(page, 2000);

  const videoPath = await page.video().path();
  await context.close();
  await browser.close();

  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
  const dest = join(OUT_DIR, `pharmalearn-story-demo-${stamp}.mp4`);
  const ff = spawnSync(
    "ffmpeg",
    ["-y", "-i", videoPath, "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", dest],
    { encoding: "utf8" },
  );
  if (ff.status !== 0) {
    const webmDest = dest.replace(/\.mp4$/, ".webm");
    copyFileSync(videoPath, webmDest);
    console.log("ffmpeg convert failed; wrote", webmDest);
    console.log(ff.stderr?.slice(-800));
    process.exit(1);
  }
  copyFileSync(dest, join(OUT_DIR, "pharmalearn-story-demo-final.mp4"));
  console.log("VIDEO", dest);
  console.log("FINAL", join(OUT_DIR, "pharmalearn-story-demo-final.mp4"));
  console.log("BYTES", statSync(dest).size);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

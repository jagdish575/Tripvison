// Visual QA: drives the system Edge/Chrome through the main flows and saves screenshots.
// Usage: node scripts/screenshots.mjs [outDir] [baseUrl]   (frontend + backend must be running)
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright-core";

const out = process.argv[2] ?? "screenshots";
const base = process.argv[3] ?? "http://localhost:5173";
mkdirSync(out, { recursive: true });

const errors = [];
async function launch() {
  for (const channel of ["msedge", "chrome"]) {
    try {
      return await chromium.launch({ channel });
    } catch {
      /* try next */
    }
  }
  throw new Error("Neither Edge nor Chrome is installed.");
}

function watch(page, label) {
  page.on("console", (m) => m.type() === "error" && errors.push(`[${label}] console: ${m.text()}`));
  page.on("response", (r) => r.status() >= 400 && errors.push(`[${label}] HTTP ${r.status()} ${r.url()}`));
  page.on("pageerror", (e) => errors.push(`[${label}] pageerror: ${e.message}`));
}

const shot = (page, name, fullPage = true) => page.screenshot({ path: join(out, `${name}.png`), fullPage });

async function runMission(page, label) {
  await page.goto(`${base}/`, { waitUntil: "networkidle" });
  await shot(page, `${label}-01-landing`);
  await page.getByRole("button", { name: "Find my journey" }).first().click();
  await page.waitForURL(/analyzing/);
  await page.waitForTimeout(900);
  await shot(page, `${label}-02-analyzing`, false);
  await page.waitForURL(/results/, { timeout: 30000 });
  await page.waitForTimeout(1800);
  await shot(page, `${label}-03-results`);
  return page.url();
}

const browser = await launch();
try {
  // ---------------- desktop
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const page = await desktop.newPage();
  watch(page, "desktop");
  const resultsUrl = await runMission(page, "desktop");
  const missionId = resultsUrl.split("/results/")[1].split("?")[0];

  // email opt-in → preview → simulated change
  const email = page.locator("#notify-email");
  if (await email.count()) {
    await email.fill("candidate@example.com");
    await page.getByRole("button", { name: "Send me trip updates" }).click();
    await page.waitForTimeout(1200);
    await page.locator("#email-title").scrollIntoViewIfNeeded();
    await page.locator("section[aria-labelledby='email-title']").screenshot({ path: join(out, "desktop-11-email-panel.png") });
    const sim = page.getByRole("button", { name: /Simulate a 45-min delay/ });
    if (await sim.count()) {
      await sim.click();
      await page.waitForTimeout(2500);
      await page.locator("section[aria-labelledby='email-title']").screenshot({ path: join(out, "desktop-12-email-recheck.png") });
    }
    const status = await (await page.request.get(`${base}/api/v1/missions/${missionId}/notifications`)).json();
    if (status.messages?.length) {
      const preview = await browser.newPage({ viewport: { width: 760, height: 900 } });
      await preview.goto(`${base}${status.messages[status.messages.length - 1].preview_url}`);
      await preview.screenshot({ path: join(out, "email-summary.png"), fullPage: true });
      await preview.close();
    }
  }

  await page.goto(`${base}/results/${missionId}`, { waitUntil: "networkidle" });
  await page.getByRole("tab").nth(1).click();
  await page.waitForTimeout(900);
  await shot(page, "desktop-04-results-cheapest");

  await page.goto(`${base}/compare/${missionId}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  await shot(page, "desktop-05-compare");

  await page.goto(`${base}/plan`, { waitUntil: "networkidle" });
  await shot(page, "desktop-06-plan");

  await page.goto(`${base}/about`, { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  await shot(page, "desktop-07-about");

  // over-constrained mission → partial with suggestions
  const res = await page.request.post(`${base}/api/v1/missions/analyze?wait=true`, {
    data: {
      origin: "Indore", destination: "Bangalore", venue: "Manyata Tech Park", mission_type: "interview",
      travel_date: new Date(Date.now() + 2 * 864e5).toISOString().slice(0, 10), arrival_deadline: "10:00", budget: 5000,
    },
  });
  const partial = (await res.json()).mission_id;
  await page.goto(`${base}/results/${partial}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await shot(page, "desktop-08-partial");

  const res2 = await page.request.post(`${base}/api/v1/missions/analyze?wait=true`, {
    data: {
      origin: "Indore", destination: "Bangalore", venue: "Manyata Tech Park", mission_type: "exam",
      travel_date: new Date(Date.now() + 2 * 864e5).toISOString().slice(0, 10), arrival_deadline: "07:00", budget: 9000,
      allow_previous_day: false,
    },
  });
  const none = (await res2.json()).mission_id;
  await page.goto(`${base}/results/${none}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await shot(page, "desktop-09-no-options");

  await page.goto(`${base}/results/does-not-exist`, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  await shot(page, "desktop-10-not-found", false);

  // ---------------- mobile
  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const m = await mobile.newPage();
  watch(m, "mobile");
  await runMission(m, "mobile");
  for (let i = 0; i < 6; i++) {
    await m.evaluate((y) => window.scrollTo(0, y), i * 800);
    await m.waitForTimeout(500);
    await shot(m, `mobile-03-results-part${i}`, false);
  }
  await m.goto(`${base}/compare/${missionId}`, { waitUntil: "networkidle" });
  await shot(m, "mobile-05-compare");
  await m.goto(`${base}/plan`, { waitUntil: "networkidle" });
  await shot(m, "mobile-06-plan");

  // ---------------- tablet
  const tablet = await browser.newContext({ viewport: { width: 820, height: 1180 } });
  const t = await tablet.newPage();
  watch(t, "tablet");
  await t.goto(`${base}/results/${missionId}`, { waitUntil: "networkidle" });
  await t.waitForTimeout(1500);
  await shot(t, "tablet-03-results");
} finally {
  await browser.close();
}

console.log(errors.length ? `Console errors:\n${errors.join("\n")}` : "No console errors.");

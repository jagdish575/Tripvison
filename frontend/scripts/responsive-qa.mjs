// Responsive QA: signs in with Demo Mode, plans Indore → Ujjain (Mahakal Mandir), then checks every page at
// 320–1920 px for horizontal overflow and saves screenshots.
// Usage: node scripts/responsive-qa.mjs [outDir] [baseUrl]   (frontend + backend must be running)
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright-core";

const out = process.argv[2] ?? "screenshots/responsive";
const base = process.argv[3] ?? "http://localhost:5173";
const WIDTHS = [320, 375, 390, 768, 1024, 1440, 1920];
mkdirSync(out, { recursive: true });

async function launch() {
  for (const channel of ["msedge", "chrome"]) {
    try { return await chromium.launch({ channel }); } catch { /* next */ }
  }
  throw new Error("Neither Edge nor Chrome is installed.");
}

/** Elements wider than the viewport (the usual cause of sideways scrolling). */
const overflow = () => {
  const vw = document.documentElement.clientWidth;
  const bad = [];
  if (document.documentElement.scrollWidth > vw + 1) {
    for (const el of document.querySelectorAll("body *")) {
      const r = el.getBoundingClientRect();
      if (r.width && (r.right > vw + 1 || r.left < -1) && getComputedStyle(el).position !== "fixed") {
        let p = el.parentElement, clipped = false;
        while (p && p !== document.body) { const o = getComputedStyle(p).overflowX; if (o === "auto" || o === "scroll" || o === "hidden") { clipped = true; break; } p = p.parentElement; }
        if (!clipped) bad.push(`${el.tagName.toLowerCase()}.${String(el.className).slice(0, 60)} → ${Math.round(r.right)}px`);
      }
    }
  }
  return { scrollWidth: document.documentElement.scrollWidth, vw, bad: bad.slice(0, 5) };
};

const browser = await launch();
const problems = [];
const errors = [];
try {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => m.type() === "error" && !m.text().includes("tile.openstreetmap") && errors.push(`console: ${m.text()}`));

  // --- sign-in gate with form state preserved
  await page.goto(`${base}/`, { waitUntil: "networkidle" });
  // signed out: no separate "Sign in" button — every "Plan a mission" asks to sign in instead of navigating
  if (await page.locator("header").getByRole("button", { name: /^Sign in$/ }).count()) problems.push("navbar still has a Sign in button");
  for (const where of ["main", "footer"]) {
    await page.locator(where).getByRole("button", { name: "Plan a mission" }).last().click();
    if (!(await page.getByRole("dialog").isVisible({ timeout: 3000 }).catch(() => false))) problems.push(`${where} Plan a mission skipped sign-in`);
    if (page.url().includes("/plan")) problems.push(`${where} Plan a mission navigated without sign-in`);
    await page.keyboard.press("Escape");
    await page.getByRole("dialog").waitFor({ state: "detached" });
  }
  await page.goto(`${base}/plan`, { waitUntil: "networkidle" });
  if (await page.locator("#venue").count()) problems.push("/plan opened without sign-in");
  await page.goto(`${base}/`, { waitUntil: "networkidle" });
  await page.fill("#hero-origin", "Indore");
  await page.fill("#hero-destination", "Ujjain");
  await page.selectOption("#hero-type", "other");
  // the venue lives on the full form. Signed out, opening it asks to sign in first; the typed values survive.
  await page.getByRole("button", { name: /more constraints/ }).click();
  await page.getByRole("dialog").waitFor();
  await page.waitForTimeout(450); // let the modal finish fading in
  await page.screenshot({ path: join(out, "login-modal-1440.png") });
  await page.getByRole("button", { name: /Continue in Demo Mode/ }).click();
  await page.waitForURL(/\/plan/);
  await page.locator("#venue").waitFor();
  if ((await page.inputValue("#destination")) !== "Ujjain") problems.push("sign-in lost the destination");
  await page.fill("#venue", "Mahakal Mandir");
  // the "I need a hotel" switch must visibly change: thumb moves to the other side
  const sw = page.getByRole("switch", { name: "I need a hotel" });
  const thumbX = async () => (await sw.locator("span").boundingBox()).x;
  const before = await thumbX();
  await sw.click(); await page.waitForTimeout(250);
  const after = await thumbX();
  await sw.click(); await page.waitForTimeout(250);
  const box = await sw.boundingBox(), thumb = await sw.locator("span").boundingBox();
  if (Math.abs(after - before) < 10) problems.push("hotel switch thumb doesn't move");
  if (thumb.x < box.x - 1 || thumb.x + thumb.width > box.x + box.width + 1) problems.push("switch thumb overflows its track");
  await page.locator("button[type=submit]:visible").first().click();
  await page.waitForURL(/analyzing/, { timeout: 15000 });
  await page.waitForTimeout(700);
  await page.screenshot({ path: join(out, "analyzing-1440.png") });
  await page.waitForURL(/results/, { timeout: 30000 });
  await page.getByText("How we routed this trip").waitFor({ timeout: 30000 }); // results rendered, not just routed
  const missionId = page.url().split("/results/")[1].split("?")[0];
  const text = await page.textContent("body");
  for (const banned of ["data requests", "SerpApi request", "upstream_", "SERPAPI_API_KEY", "couldn't match"]) {
    if (text.includes(banned)) problems.push(`results page shows developer text: "${banned}"`);
  }
  if (!text.includes("doesn't have a commercial airport")) problems.push("airport fallback notice missing");
  if (!text.includes("Mahakal Mandir") || text.includes("couldn't pinpoint")) problems.push("venue not used as the endpoint");

  // save + trips
  await page.getByRole("button", { name: /Save journey/ }).click();
  await page.waitForTimeout(600);

  const pages = ["/", "/plan", `/results/${missionId}`, `/compare/${missionId}`, "/trips", "/trips?tab=saved", "/profile", "/about"];
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: width < 768 ? 800 : 900 });
    for (const path of pages) {
      await page.goto(`${base}${path}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(path.startsWith("/results") ? 900 : 300);
      const o = await page.evaluate(overflow);
      if (o.scrollWidth > o.vw + 1) problems.push(`${width}px ${path}: scrollWidth ${o.scrollWidth} > ${o.vw} :: ${o.bad.join(" | ")}`);
      if ([320, 390, 768, 1440, 1920].includes(width) && ["/", `/results/${missionId}`, "/trips", "/plan"].includes(path)) {
        const name = path === "/" ? "landing" : path.split("/")[1];
        await page.screenshot({ path: join(out, `${name}-${width}.png`), fullPage: width >= 1440 && name !== "results" ? false : false });
      }
    }
    if (width < 768) { // mobile menu
      await page.goto(`${base}/`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: "Open menu" }).click();
      await page.waitForTimeout(350);
      await page.screenshot({ path: join(out, `menu-${width}.png`) });
      const o = await page.evaluate(overflow);
      if (o.scrollWidth > o.vw + 1) problems.push(`${width}px mobile menu overflow`);
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${base}/results/${missionId}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: join(out, "results-full-1440.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: join(out, "results-full-390.png"), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${base}/`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /Account menu/ }).click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: join(out, "profile-menu-1440.png") });
} finally {
  await browser.close();
}
console.log(problems.length ? `PROBLEMS:\n${problems.join("\n")}` : "No horizontal overflow at any width.");
console.log(errors.length ? `ERRORS:\n${[...new Set(errors)].join("\n")}` : "No page errors.");

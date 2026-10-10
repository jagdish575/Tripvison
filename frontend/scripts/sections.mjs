// Visual QA helper: screenshots of individual results sections at full resolution.
// Usage: node scripts/sections.mjs <outDir> <missionId> [baseUrl] [width]
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright-core";

const [out = "screenshots", missionId, base = "http://localhost:5173", width = "1440"] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ channel: "msedge" }).catch(() => chromium.launch({ channel: "chrome" }));
const page = await browser.newPage({ viewport: { width: Number(width), height: 1000 } });
await page.goto(`${base}/results/${missionId}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1800);
const targets = {
  top: "main",
  options: "section[aria-labelledby='options-title']",
  picks: "section[aria-labelledby='picks-title']",
  detail: "#journey-detail",
  tradeoffs: "section[aria-labelledby='tradeoffs-title']",
  email: "section[aria-labelledby='email-title']",
};
for (const [name, selector] of Object.entries(targets)) {
  const el = page.locator(selector).first();
  if (!(await el.count())) continue;
  await el.scrollIntoViewIfNeeded();
  await page.waitForTimeout(700);
  if (name === "top") await page.screenshot({ path: join(out, `${width}-${name}.png`) });
  else await el.screenshot({ path: join(out, `${width}-${name}.png`) });
}
await browser.close();
console.log("done");

/** Repeatable UI evidence with controlled API fixtures; no real route generation. */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { resolve } from "node:path";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import { installCommonMocks, mockGeneration } from "../tests/support/functional-fixtures.js";

const output = resolve(process.argv[2] || "../test-results/ui-usability-audit");
const baseURL = process.env.UI_AUDIT_URL || "http://127.0.0.1:4175";
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const report = { created_at: new Date().toISOString(), browser: browser.version(),
  method: "Expert task walkthrough and automated browser checks with controlled API fixtures; no participant study.",
  source_sha256: Object.fromEntries(await Promise.all([
    "src/App.jsx", "src/styles.css", "src/studio.css", "src/RouteMap.jsx", "src/RouteSetupPanel.jsx",
    "src/WaitingSketchGame.jsx", "src/api.js", "vite.config.js", "package-lock.json",
  ].map(async path => [path, createHash("sha256").update(await readFile(path)).digest("hex")]))), views: [] };
try {
  for (const width of [1440, 390, 320]) {
    const context = await browser.newContext({ viewport: { width, height: width === 320 ? 568 : 900 }, baseURL });
    const page = await context.newPage();
    await installCommonMocks(page);
    await mockGeneration(page);
    async function capture(state) {
      if (state.startsWith("result")) await page.locator(".street-route-line").waitFor();
      await page.screenshot({ path: resolve(output, `${width}-${state}.png`), fullPage: true });
      const layout = await page.evaluate(() => ({
        width: innerWidth, height: innerHeight,
        overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth,
        overflowElements: [...document.querySelectorAll("main *")]
          .filter(el => el.getClientRects().length && el.getBoundingClientRect().right > innerWidth + 1)
          .slice(0, 16).map(el => ({ tag: el.tagName, class: el.className?.baseVal ?? el.className })),
        actionPosition: document.querySelector(".generate-button")?.getBoundingClientRect().top + scrollY || null,
        controls: [...document.querySelectorAll("button, a, input, select, textarea, summary")]
          .filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== "hidden")
          .map(el => { const r = el.getBoundingClientRect(); return { label: el.getAttribute("aria-label") || el.textContent.trim().slice(0, 70) || el.id,
            tag: el.tagName, width: r.width, height: r.height, top: r.top + scrollY, fontSize: getComputedStyle(el).fontSize }; }),
      }));
      const axe = await new AxeBuilder({ page }).analyze();
      report.views.push({ width, state, layout, violations: axe.violations.map(({ id, impact, description, helpUrl, nodes }) =>
        ({ id, impact, description, helpUrl, nodes: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })) })),
        incomplete: axe.incomplete.map(({ id, nodes }) => ({ id, nodes: nodes.map(n => n.target) })) });
      await writeFile(resolve(output, "audit.json"), JSON.stringify(report, null, 2));
      console.log(JSON.stringify({ width, state, overflow: layout.overflow, violations: report.views.at(-1).violations.map(v => [v.id, v.nodes.length]) }));
    }
    await page.goto("/");
    await page.getByLabel("Drawing and location").waitFor();
    await page.evaluate(() => window.scrollTo(0, 0));
    await capture("planner");
    await page.getByRole("button", { name: "Suggest a shape", exact: true }).click();
    await capture("fields");
    await page.goto("/");
    await page.getByRole("button", { name: "Review request", exact: true }).click();
    await page.getByRole("heading", { name: "Check your request" }).waitFor();
    await capture("review");
    await page.getByRole("button", { name: "Find routes", exact: true }).click();
    await page.locator(".result").waitFor();
    await capture("result");
    await page.locator(".candidate-card").nth(1).click();
    await capture("result-review");
    await page.getByText("More ways to use this route", { exact: true }).click();
    await page.getByRole("button", { name: "Record reel", exact: true }).click();
    await page.getByRole("dialog").waitFor();
    await capture("dialog");
    await context.close();
  }
} finally { await browser.close(); }

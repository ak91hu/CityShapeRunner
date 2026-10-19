/** Live integration smoke: read resources and review a request, never generate or publish. */
import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const baseURL = process.argv[2] || "http://127.0.0.1:8000";
const output = resolve(process.argv[3] || "../test-results/ui-usability-2026-10-19/live");
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const results = [];
try {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, baseURL });
    const page = await context.newPage();
    const responses = [];
    page.on("response", response => {
      const url = new URL(response.url());
      if (url.origin === new URL(baseURL).origin && !url.pathname.startsWith("/assets/")) {
        responses.push({ path: url.pathname, status: response.status(), type: response.headers()["content-type"] });
      }
    });
    // A smoke test must not spend routing quota or publish an image by mistake.
    await page.route("**/*", route => {
      const req = route.request();
      if (req.method() !== "GET" && new URL(req.url()).pathname !== "/interpret") return route.abort();
      return route.continue();
    });
    await page.goto("/");
    await page.getByLabel("Drawing and location").waitFor();
    const templates = await page.request.get("/shape-templates");
    if (!(templates.headers()["content-type"] || "").includes("application/json")) throw Error("Templates were served as HTML");
    const payload = await templates.json();
    await page.getByRole("button", { name: "Place on map", exact: true }).click();
    await page.waitForFunction(() => document.querySelectorAll("#map-placement-shape option").length >= 100);
    await page.getByRole("button", { name: "Review request", exact: true }).click();
    await page.getByRole("heading", { name: "Check your request" }).waitFor();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    if (overflow > 1) throw Error("Live review page overflows");
    await page.screenshot({ path: resolve(output, `${width}-live-review.png`), fullPage: true });
    results.push({ width, template_count: payload.shapes.length, overflow, responses });
    await context.close();
  }
} finally { await browser.close(); }
await writeFile(resolve(output, "smoke.json"), JSON.stringify({ baseURL, mode: "Live API; no generation, export or publication", results }, null, 2));
console.log(JSON.stringify(results.map(({ width, template_count, overflow }) => ({ width, template_count, overflow }))));

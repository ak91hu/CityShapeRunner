import { expect, test } from "playwright/test";
import {
  buildRouteResult,
  installCommonMocks,
  openGeneratedRoute,
  openOptionalRouteTools,
} from "./support/functional-fixtures.js";

async function startLiveGeneration(page) {
  await installCommonMocks(page);
  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window);
    window.generationRequestCount = 0;
    window.fetch = (input, options = {}) => {
      if (new URL(input, location.href).pathname !== "/generate") return originalFetch(input, options);
      window.generationRequestCount += 1;
      const encoder = new TextEncoder();
      return Promise.resolve(new Response(new ReadableStream({
        start(controller) {
          window.sendGeneration = (data) => controller.enqueue(encoder.encode(`${JSON.stringify(data)}\n`));
          window.finishGeneration = (data) => {
            window.sendGeneration({ type: "result", data });
            controller.close();
          };
          options.signal?.addEventListener("abort", () => controller.error(new DOMException("Cancelled", "AbortError")), { once: true });
          window.sendGeneration({
            type: "progress", stage: "preflight", status: "running", preflight_count: 99,
            search_areas: 16, connected_candidates: 0, routing_requests: { snap: 1, directions: 0 },
          });
        },
      }), { headers: { "Content-Type": "application/x-ndjson" } }));
    };
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Review request", exact: true }).click();
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  await expect(page.getByText("16 search areas explored", { exact: true })).toBeVisible();
}

test("live search counters describe real work and do not move backwards", async ({ page }) => {
  await startLiveGeneration(page);
  await page.evaluate(() => window.sendGeneration({
    type: "progress", stage: "validation", status: "completed", preflight_count: 180,
    search_areas: 19, connected_candidates: 3, routing_requests: { snap: 3, directions: 4 },
  }));
  await expect(page.getByText("3 street-connected candidates found", { exact: true })).toBeVisible();
  await page.evaluate(() => window.sendGeneration({
    type: "progress", stage: "snap", status: "running", preflight_count: 99,
    search_areas: 16, connected_candidates: 1, routing_requests: { snap: 1, directions: 2 },
  }));
  await expect(page.getByText("180 placements screened", { exact: true })).toBeVisible();
  await expect(page.getByText("19 search areas explored", { exact: true })).toBeVisible();
  await expect(page.getByText("3 street-connected candidates found", { exact: true })).toBeVisible();
  await expect(page.getByText("4 full street route requests so far", { exact: true })).toBeVisible();
  await expect(page.getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toHaveCount(0);
  await page.evaluate((result) => window.finishGeneration(result), buildRouteResult());
  await expect(page.locator(".result")).toBeVisible();
});

test("the sketch challenge works without changing or delaying generation", async ({ page }) => {
  await startLiveGeneration(page);
  const game = page.locator(".waiting-game");
  if (!(await game.evaluate((element) => element.open))) await game.locator("summary").click();
  await game.getByRole("button", { name: "Heart", exact: true }).click();
  await expect(game.getByRole("status")).toContainText("You got it!");
  await expect(game.getByRole("button", { name: "Heart", exact: true })).toBeDisabled();
  await expect(game.locator(".waiting-game-footer")).toContainText("1/1 correct");
  await game.getByRole("button", { name: "Next sketch" }).click();
  await game.getByRole("button", { name: "Flower", exact: true }).click();
  await expect(game.getByRole("status")).toContainText("It’s a star.");
  await expect(game.locator(".waiting-game-footer")).toContainText("Sketch 2/8 · 1/2 correct");
  expect(await page.evaluate(() => window.generationRequestCount)).toBe(1);

  const cancel = page.getByRole("button", { name: "Cancel", exact: true });
  if (page.viewportSize().width <= 768) {
    const bounds = await cancel.boundingBox();
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(page.viewportSize().height + 1);
  }
  await cancel.click();
  await expect(page.getByRole("button", { name: "Find routes", exact: true })).toBeEnabled();
  await expect(page.locator(".loading-card")).toHaveCount(0);
  await expect(page.locator(".error-card")).toHaveCount(0);
});

test("silence is explained without inventing progress and clears when events resume", async ({ page }) => {
  await page.clock.install();
  await startLiveGeneration(page);
  await page.clock.fastForward(13_000);
  await expect(page.locator(".loading-quiet-note")).toContainText("hasn’t sent a new update");
  await expect(page.getByRole("listitem").filter({ hasText: "Street fit" })).toHaveAttribute("aria-current", "step");
  await expect(page.getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");
  await page.evaluate(() => window.sendGeneration({
    type: "progress", stage: "validation", status: "running", preflight_count: 180,
    search_areas: 19, connected_candidates: 2, routing_requests: { directions: 3 },
  }));
  await expect(page.locator(".loading-quiet-note")).toHaveCount(0);
  await page.evaluate((result) => window.finishGeneration(result), buildRouteResult());
  await expect(page.locator(".result")).toBeVisible();
});


test("generated-route setup waits for late panels before clicking tools", async ({ page }) => {
  await installCommonMocks(page);
  let release;
  const chunk = new Promise(resolve => { release = resolve; });
  await page.route("**/src/RouteWalkthrough.jsx*", async route => {
    await chunk;
    await route.continue();
  });
  let ready = false;
  const generated = openGeneratedRoute(page).then(() => { ready = true; });
  try {
    await expect(page.locator(".street-route-line")).toBeVisible();
    await expect(page.locator(".result")).toBeFocused();
    expect(ready).toBe(false);
    release();
    await generated;
    await openOptionalRouteTools(page);
    await expect(page.getByRole("button", { name: "Check accessibility" })).toBeVisible();
  } finally {
    release();
    await generated;
  }
});

import { expect, test } from "playwright/test";
import { installCommonMocks, openGeneratedRoute } from "./support/functional-fixtures.js";

const STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";
if (process.env.WALKTHROUGH_TEST_ORIGIN) {
  test.use({ baseURL: process.env.WALKTHROUGH_TEST_ORIGIN });
}

test("the virtual walkthrough loads its worker and follows the route", async ({ page }) => {
  await installCommonMocks(page);
  if (!process.env.WALKTHROUGH_USE_LIVE_STYLE) {
    await page.route(STYLE_URL, (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        version: 8,
        sources: {},
        layers: [{ id: "background", type: "background", paint: { "background-color": "#f8f4f0" } }],
      }),
    }));
  }
  const pageErrors = [];
  const consoleErrors = [];
  let mapReady = false;
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
    if (message.text().includes("[walkthrough] 3D map and route layers loaded")) mapReady = true;
  });

  await openGeneratedRoute(page);
  await page.getByText("Virtually walk through your route").click();
  await expect.poll(() => mapReady).toBe(true);
  await expect.poll(() => page.workers().length).toBeGreaterThan(0);
  await expect(page.locator(".walkthrough-map-error")).toHaveCount(0);
  if (process.env.WALKTHROUGH_USE_LIVE_STYLE) {
    await page.locator(".walkthrough-map").screenshot({ path: test.info().outputPath("walkthrough-map.png") });
  }
  await page.getByRole("button", { name: "Next 100 m" }).click();
  await expect(page.locator(".walkthrough-progress strong")).toHaveText("100 m");
  expect(pageErrors).toEqual([]);
  expect(consoleErrors.filter((message) => message.includes("Worker failed to load"))).toEqual([]);
});

test("a blocked map style shows the precise failure and logs it", async ({ page }) => {
  await installCommonMocks(page);
  await page.route(STYLE_URL, (route) => route.fulfill({ status: 429, body: "Rate limited" }));
  const diagnostics = [];
  await page.route("**/walkthrough-diagnostics", (route) => {
    diagnostics.push(route.request().postDataJSON());
    return route.fulfill({ status: 204 });
  });

  await openGeneratedRoute(page);
  await page.getByText("Virtually walk through your route").click();
  await expect(page.getByRole("alert")).toContainText("HTTP 429");
  await expect.poll(() => diagnostics.length).toBeGreaterThan(0);
  expect(diagnostics[0]).toMatchObject({ code: "rate_limited", resource: "style", http_status: 429 });
});

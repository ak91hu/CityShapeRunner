import { expect, test } from "playwright/test";

import {
  buildRouteResult,
  installCommonMocks,
  openGeneratedRoute,
} from "./support/functional-fixtures.js";

test.beforeEach(async ({ page }) => {
  await installCommonMocks(page);
});

test("a completed generation moves focus to the result region", async ({ page }) => {
  await openGeneratedRoute(page);

  await expect(page.locator(".result")).toBeFocused();
  await expect(page.locator(".result")).toHaveAttribute("aria-labelledby", "result-title");
});

test("the result identifies the route and its request ID", async ({ page }) => {
  await openGeneratedRoute(page);

  await expect(page.getByRole("heading", { name: "Star in Debrecen" })).toBeVisible();
  await expect(page.locator(".debug-id")).toHaveText("Route ID: expanded-functional-1");
  await expect(page.locator(".route-state")).toContainText("Ready to download");
});

test("the candidate selector describes ready and review options", async ({ page }) => {
  await openGeneratedRoute(page);
  const selector = page.getByLabel("Route options");

  await expect(selector.locator("option")).toHaveCount(2);
  await expect(selector.locator("option").nth(0)).toContainText("91% · 19.82 km · Ready");
  await expect(selector.locator("option").nth(1)).toContainText(
    "61% · 21.40 km · Needs a look",
  );
  await expect(page.locator(".candidate-toolbar")).toContainText(
    "2 options: 1 ready, 1 need a look",
  );
});

test("selecting a review candidate updates all headline metrics", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.getByLabel("Route options").selectOption("candidate-review");

  await expect(page.locator(".route-state")).toContainText("Check before downloading");
  await expect(page.locator(".metric").filter({ hasText: "Overall match" })).toContainText("61%");
  await expect(
    page.locator(".metric").filter({ has: page.locator("dt", { hasText: /^Distance$/ }) }),
  ).toContainText("21.40 km");
  await expect(page.locator(".metric").filter({ hasText: "Shape match" })).toContainText("61%");
});

test("route-check details reveal every automatic gate and explanation", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.locator(".verification-heading").click();

  await expect(page.locator(".gate-list > li")).toHaveCount(13);
  await expect(page.getByText("Line order", { exact: true })).toBeVisible();
  await expect(page.getByText("No doubled-back lines", { exact: true })).toBeVisible();
  await expect(page.getByText("Returns to the start", { exact: true })).toBeVisible();
  await expect(page.getByText(/Higher scores mean a closer match/)).toBeVisible();
});

test("route details expose routing, distance, placement, and closure facts", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.getByText("Route details", { exact: true }).click();
  const facts = page.locator(".route-facts");

  await expect(facts).toContainText("842 / 401");
  await expect(facts).toContainText("19.82 km / 20.00 km");
  await expect(facts).toContainText("3 m");
  await expect(facts).toContainText("18.0° / 3200 m");
  await expect(facts).toContainText("83%");
});

test("earlier route versions are available as a labelled comparison table", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.locator(".detail-card summary").filter({ hasText: "Earlier versions" }).click();
  const table = page.getByRole("table", { name: "Scores for earlier versions of this route" });

  await expect(table.locator("tbody tr")).toHaveCount(2);
  await expect(table.locator("tbody tr").first()).toContainText("79%");
  await expect(table.locator("tbody tr").last()).toContainText("91%");
  await expect(table).toContainText("Distance accuracy");
});

test("the route audit distinguishes verified and review decisions", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.getByText("Routes tested").click();
  const table = page.getByRole("table", { name: "Scores for every route that was tested" });

  await expect(table.locator("tbody tr")).toHaveCount(2);
  await expect(table.locator("tbody tr").first()).toContainText("Ready");
  await expect(table.locator("tbody tr").last()).toContainText("Needs a look");
  await expect(table.locator("tbody tr").last()).toContainText("Overall Score");
});

test("route issues are deduplicated in the route issues disclosure", async ({ page }) => {
  await openGeneratedRoute(
    page,
    buildRouteResult({
      errors: ["Avoid the construction zone.", "Check seasonal access.", "Avoid the construction zone."],
    }),
  );
  await page.getByText("Route issues").click();

  const details = page.locator(".detail-card").filter({ hasText: "Route issues" });
  await expect(details.locator("li")).toHaveCount(2);
  await expect(details).toContainText("Avoid the construction zone.");
  await expect(details).toContainText("Check seasonal access.");
});

test("suggested generations explain which shape the planner selected", async ({ page }) => {
  await openGeneratedRoute(
    page,
    buildRouteResult({
      suggested_shape: "diamond",
      suggestion_reason:
        "For running, it aligns with the ordered street bearings and stays on one continuous stroke.",
    }),
  );

  const notice = page.locator(".notice--info");
  await expect(notice).toContainText("Suggested shape");
  await expect(notice).toContainText("Diamond");
  await expect(notice).toContainText("aligns with the ordered street bearings");
});

test("a generated custom drawing is clearly explained", async ({ page }) => {
  const result = buildRouteResult({
    prompt: "a platypus in Debrecen, cycling, 20 km",
    intent: {
      shape: "platypus",
      text: null,
      city: "Debrecen",
      sport: "bike",
      distance_km: 20,
      style: null,
    },
    shape: { name: "platypus", closed: true, source: "llm", n_paths: 1 },
    requested_shape: "platypus",
  });
  result.candidates = result.candidates.map((candidate) => ({
    ...candidate,
    shape_name: "platypus",
    shape_source: "llm",
  }));
  result.candidate_summary = {
    ...result.candidate_summary,
    selected_shape: "platypus",
  };

  await openGeneratedRoute(page, result);

  const notice = page.locator(".notice--info").filter({ hasText: "Made from your idea" });
  await expect(notice).toContainText("created for your description");
  await expect(notice).toContainText("Compare the dashed drawing");
});

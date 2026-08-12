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

test("the complete street map can be rotated and reset by hand", async ({ page }) => {
  await openGeneratedRoute(page);
  await expect(page.locator(".route-map .leaflet-overlay-pane path").first()).toBeVisible();

  const angle = page.getByLabel("Map rotation angle");
  const rotatePane = page.locator(".route-map .leaflet-rotate-pane");
  const northUp = page.getByRole("button", { name: "North up" });

  await expect(angle).toHaveValue("0");
  await expect(northUp).toBeDisabled();
  await page.getByRole("button", { name: "Rotate map 15 degrees right" }).click();

  await expect(angle).toHaveValue("15");
  await expect(page.locator(".map-rotation-value")).toHaveText("15°");
  await expect(northUp).toBeEnabled();
  await expect
    .poll(() => rotatePane.evaluate((element) => element.style.transform))
    .toContain("rotate(");

  await northUp.click();
  await expect(angle).toHaveValue("0");
  await expect(page.locator(".map-rotation-value")).toHaveText("0°");
  await expect(northUp).toBeDisabled();
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

test("recognition repair keeps route details, downloads, and gallery sharing directly below the route", async ({ page }) => {
  await page.route("**/recognition-repair", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        points_preview: [[47.4979, 19.0402], [47.4986, 19.0461], [47.4943, 19.0478], [47.4979, 19.0402]],
        guide_points: [[47.4979, 19.0402], [47.4986, 19.0461], [47.4943, 19.0478], [47.4979, 19.0402]],
        distance_km: 19.8,
        snapped: true,
        gpx: "<?xml version=\"1.0\"?><gpx version=\"1.1\"></gpx>",
        recognition_score: 0.94,
        readiness: {},
        message: "A crisper route is ready.",
      }),
    });
  });
  await openGeneratedRoute(page);
  await page.getByRole("button", { name: "Find a crisper version" }).click();

  const output = page.locator(".route-output");
  await expect(output.getByText("Route details", { exact: true })).toBeVisible();
  await expect(output.getByRole("button", { name: "Download edited GPX" })).toBeVisible();
  await expect(output.getByRole("button", { name: "Download TCX" })).toBeVisible();
  await expect(output.getByText("Publish map image", { exact: true })).toBeVisible();
  await expect(output.getByRole("checkbox")).toBeVisible();
  await expect(output.getByRole("button", { name: "Publish map" })).toBeVisible();
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

test("route readiness shows elevation, surfaces, and mapped concerns", async ({ page }) => {
  await openGeneratedRoute(page);
  const readiness = page.locator(".readiness-card");

  await expect(readiness).toContainText("Route readiness");
  await expect(readiness).toContainText("184 m");
  await expect(readiness).toContainText("8.4%");
  await expect(readiness).toContainText("92%");
  await expect(readiness).toContainText("Asphalt");
  await expect(readiness).toContainText("Compacted gravel");
  await expect(readiness).toContainText("Unpaved riding");
  await expect(readiness).toContainText("Surface data gap");
  await expect(page.locator(".route-concern-segment")).toHaveCount(2);
  await expect(page.getByText("Routes tested")).toHaveCount(0);
});

test("Street Canvas exposes the strongest nearby areas on the route map", async ({ page }) => {
  await openGeneratedRoute(page);
  const canvas = page.locator(".street-canvas-card");

  await expect(canvas).toContainText("Best nearby areas");
  await expect(canvas).toContainText("88% readable");
  await expect(canvas).toContainText("94% street support");
  await expect(page.locator(".street-canvas-marker")).toHaveCount(2);
});

test("community mural creates separate downloadable artist sections", async ({ page }) => {
  await page.route("**/mural-plan", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        sections: [
          { id: "mural-1", label: "Artist 1", distance_km: 4.2, gpx: "<gpx />" },
          { id: "mural-2", label: "Artist 2", distance_km: 4.1, gpx: "<gpx />" },
        ],
      }),
    });
  });
  await openGeneratedRoute(page);
  await page.getByRole("button", { name: "Create mural plan" }).click();

  const mural = page.locator(".mural-card");
  await expect(mural).toContainText("Artist 1, 4.20 km");
  await expect(mural).toContainText("Artist 2, 4.10 km");
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

test("an independently reviewed AI drawing shows its semantic result", async ({ page }) => {
  const result = buildRouteResult({
    shape: {
      name: "waving robot",
      closed: true,
      source: "llm",
      n_paths: 1,
      generated_candidate_count: 4,
      semantic_verification: {
        score: 0.86,
        independent: true,
        cue_results: [
          { feature_id: "head", present: true },
          { feature_id: "arm", present: true },
          { feature_id: "legs", present: false },
        ],
      },
    },
  });
  result.candidates = result.candidates.map((candidate) => ({
    ...candidate,
    shape_name: "waving robot",
    shape_source: "llm",
  }));

  await openGeneratedRoute(page, result);

  const notice = page.locator(".notice--info").filter({ hasText: "Made from your idea" });
  await expect(notice).toContainText("sketched 4 different versions");
  await expect(notice).toContainText("scored it 86%");
  await expect(notice).toContainText("found 2 of 3 defining features");

  await page.getByText("Recognition audit", { exact: true }).click();
  const audit = page.locator(".ai-recognition-card");
  await expect(audit.locator("li")).toHaveCount(3);
  await expect(audit).toContainText("Head");
  await expect(audit).toContainText("Legs");
  await expect(audit).toContainText("Missing");
});

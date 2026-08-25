import { expect, test } from "playwright/test";

import {
  buildRouteResult,
  installCommonMocks,
  openGeneratedRoute,
} from "./support/functional-fixtures.js";

test.beforeEach(async ({ page }) => {
  await installCommonMocks(page);
});

async function openOptionalRouteTools(page) {
  const tools = page.locator(".route-lab");
  if (!(await tools.locator(".route-lab-grid").isVisible())) {
    await tools.locator("summary").click();
  }
}

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
  await page.getByText("Route details", { exact: true }).click();
  await expect(page.locator(".route-facts")).toContainText("expanded-functional-1");
  await expect(page.locator(".route-state")).toContainText("Ready to download");
});

test("the result leads with the interpreted request and offers a correction path", async ({ page }) => {
  await openGeneratedRoute(page);

  const summary = page.locator(".request-summary-card");
  await expect(summary).toContainText("We understood Star");
  await expect(summary).toContainText("Debrecen");
  await expect(summary).toContainText("Cycling");
  await expect(summary).toContainText("20.00 km");

  await summary.getByRole("button", { name: "Change request" }).click();
  await expect(page.getByLabel("Drawing and location")).toBeFocused();
});

test("optional route tools are grouped after the decision and download cards", async ({ page }) => {
  await openGeneratedRoute(page);

  const lastPrimaryCard = page.locator(".route-output .route-facts");
  const lab = page.locator(".route-lab");
  const [primaryBox, labBox] = await Promise.all([
    lastPrimaryCard.boundingBox(),
    lab.boundingBox(),
  ]);

  expect(primaryBox).not.toBeNull();
  expect(labBox).not.toBeNull();
  expect(primaryBox.y + primaryBox.height).toBeLessThanOrEqual(labBox.y + 1);
  await expect(lab).toContainText("Safety, quality, group & classroom tools");
  if (!(await lab.locator(".street-canvas-card").isVisible())) {
    await lab.locator("summary").click();
  }
  await expect(lab.locator(".street-canvas-card")).toBeVisible();
  await expect(lab.locator(".recognition-repair-card")).toBeVisible();
});

test("the map is the first result panel and does not overlap later panels", async ({ page }) => {
  await openGeneratedRoute(page);

  const map = page.locator(".map-card");
  const metrics = page.locator(".result-sidebar .metrics");
  const exportCard = page.locator(".route-output .export-card");
  const routeFacts = page.locator(".route-output .route-facts");
  const [mapBox, metricsBox, exportBox, factsBox] = await Promise.all([
    map.boundingBox(),
    metrics.boundingBox(),
    exportCard.boundingBox(),
    routeFacts.boundingBox(),
  ]);

  expect(mapBox).not.toBeNull();
  expect(metricsBox).not.toBeNull();
  expect(exportBox).not.toBeNull();
  expect(factsBox).not.toBeNull();
  const sideBySide = metricsBox.y < mapBox.y + mapBox.height - 1;
  if (sideBySide) {
    expect(mapBox.x + mapBox.width).toBeLessThanOrEqual(metricsBox.x + 1);
    expect(metricsBox.y + metricsBox.height).toBeLessThanOrEqual(exportBox.y + 1);
    expect(mapBox.y + mapBox.height).toBeLessThanOrEqual(factsBox.y + 1);
  } else {
    expect(mapBox.y + mapBox.height).toBeLessThanOrEqual(metricsBox.y + 1);
    if ((await page.viewportSize()).width <= 768) {
      expect(mapBox.y + mapBox.height).toBeLessThanOrEqual(exportBox.y + 1);
      expect(exportBox.y + exportBox.height).toBeLessThanOrEqual(factsBox.y + 1);
      expect(factsBox.y + factsBox.height).toBeLessThanOrEqual(metricsBox.y + 1);
      const downloadBox = await page.getByRole("button", { name: "Download GPX", exact: true }).boundingBox();
      const requestDetailsBox = await page.locator(".request-summary-details > summary").boundingBox();
      expect(downloadBox).not.toBeNull();
      expect(requestDetailsBox).not.toBeNull();
      expect(downloadBox.height).toBeGreaterThanOrEqual(44);
      expect(requestDetailsBox.height).toBeGreaterThanOrEqual(44);
      expect(await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
      )).toBe(false);
    } else {
      expect(metricsBox.y + metricsBox.height).toBeLessThanOrEqual(exportBox.y + 1);
      expect(exportBox.y + exportBox.height).toBeLessThanOrEqual(factsBox.y + 1);
    }
  }
});

test("route option cards compare ready and review candidates", async ({ page }) => {
  await openGeneratedRoute(page);
  const options = page.getByRole("region", { name: "Route options" });
  const cards = options.locator(".candidate-card");

  await expect(cards).toHaveCount(2);
  await expect(cards.nth(0)).toContainText("Best overall match");
  await expect(cards.nth(0)).toContainText("91%");
  await expect(cards.nth(0)).toContainText("19.82");
  await expect(cards.nth(0)).toContainText("Ready");
  await expect(cards.nth(1)).toContainText("61%");
  await expect(cards.nth(1)).toContainText("21.40");
  await expect(cards.nth(1)).toContainText("Review");
  await expect(options).toContainText("1 ready · 1 to review");
  await expect(options).toContainText("164 placements screened");
  await expect(options).toContainText("2 street routes measured");
  await expect(options).toContainText("drawing likeness, distance, closure");
});

test("GPX export explains the account-free Garmin, Strava, and Komoot workflow", async ({
  page,
}) => {
  await openGeneratedRoute(page);

  const help = page.locator(".gpx-help");
  await help.getByText("Use this GPX with Garmin, Strava, or Komoot").click();
  await expect(help).toContainText("Download the GPX file");
  await expect(help).toContainText("route or course import tool");
  await expect(help).toContainText("does not connect to your account");
});

test("selecting a review candidate updates all headline metrics", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.locator(".candidate-card").nth(1).click();

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
  const repairButton = page.getByRole("button", { name: "Find a crisper version" });
  if (!(await repairButton.isVisible())) {
    await page.locator(".route-lab > summary").click();
  }
  await repairButton.click();

  const output = page.locator(".route-output");
  await expect(output.getByText("Route details", { exact: true })).toBeVisible();
  await expect(output.getByRole("button", { name: "Download edited GPX" })).toBeVisible();
  await expect(output.getByRole("button", { name: "Download TCX" })).toBeVisible();
  await output.getByText("Share map publicly", { exact: true }).click();
  await expect(output.getByRole("checkbox")).toBeVisible();
  await expect(output.getByRole("button", { name: "Publish map" })).toBeVisible();
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
  const unpaved = readiness.getByRole("button", { name: /Unpaved riding/ });
  await unpaved.click();
  await expect(unpaved).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".route-concern-segment--active")).toHaveCount(1);
  await expect(readiness.getByRole("button", { name: "Show full route" })).toBeVisible();
  await readiness.getByRole("button", { name: "Show full route" }).click();
  await expect(page.locator(".route-concern-segment--active")).toHaveCount(0);
  await expect(page.getByText("Routes tested")).toHaveCount(0);
});

test("Street Canvas exposes the strongest nearby areas on the route map", async ({ page }) => {
  await openGeneratedRoute(page);
  await openOptionalRouteTools(page);
  const canvas = page.locator(".street-canvas-card");

  await expect(canvas).toContainText("Best nearby areas");
  await expect(canvas).toContainText("88% readable");
  await expect(canvas).toContainText("94% street support");
  await expect(page.locator(".street-canvas-marker")).toHaveCount(2);
});

test("time-aware weather follows the selected departure hour", async ({ page }) => {
  const departures = [];
  await page.route("**/timed-readiness", async (route) => {
    const request = route.request().postDataJSON();
    departures.push(request.departure_at);
    const hour = new Date(request.departure_at).getUTCHours();
    const warm = hour >= 14;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        departure_at: request.departure_at,
        daylight: warm ? "daylight" : "after_dark",
        weather_status: "available",
        weather_message: null,
        weather: {
          forecast_at: new Date(request.departure_at).toISOString().replace(/:\d{2}\.000Z$/, ":00.000Z"),
          temperature_c: warm ? 27 : 8,
          precipitation_mm: warm ? 0 : 2.5,
          wind_kph: warm ? 9 : 21,
          weather_code: warm ? 1 : 61,
        },
      }),
    });
  });
  await openGeneratedRoute(page);
  await openOptionalRouteTools(page);

  const card = page.locator(".timed-readiness-card");
  const departure = card.getByLabel("Departure");
  await departure.fill("2026-08-14T08:00");
  await card.getByRole("button", { name: "Check conditions" }).click();
  await expect(card).toContainText("8°C");
  await expect(card).toContainText("21 km/h wind");
  await expect(card).toContainText("2.5 mm precipitation");

  await departure.fill("2026-08-14T16:00");
  await expect(card.locator(".timed-readiness-result")).toHaveCount(0);
  await card.getByRole("button", { name: "Check conditions" }).click();
  await expect(card).toContainText("27°C");
  await expect(card).toContainText("9 km/h wind");
  await expect(card).toContainText("0 mm precipitation");
  expect(departures).toHaveLength(2);
  expect(departures[0]).not.toBe(departures[1]);
});

test("time-aware weather explains departures outside the forecast window", async ({ page }) => {
  await page.route("**/timed-readiness", async (route) => {
    const request = route.request().postDataJSON();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        departure_at: request.departure_at,
        daylight: "daylight",
        weather: null,
        weather_status: "outside_forecast_window",
        weather_message: "Hourly weather is available up to 16 days ahead. Daylight is still calculated for your selected time.",
      }),
    });
  });
  await openGeneratedRoute(page);
  await openOptionalRouteTools(page);

  const card = page.locator(".timed-readiness-card");
  await card.getByLabel("Departure").fill("2026-10-14T12:00");
  await card.getByRole("button", { name: "Check conditions" }).click();
  await expect(card).toContainText("Hourly weather is available up to 16 days ahead");
  await expect(card).toContainText("Daylight expected");
});

test("Inkproof forecasts GPS drift and highlights fragile drawing details", async ({ page }) => {
  let requestBody;
  await page.route("**/inkproof-analysis", async (route) => {
    requestBody = route.request().postDataJSON();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        accuracy_m: 10,
        resilience_score: 0.78,
        expected_recognition: 0.91,
        fragile_share: 0.16,
        rating: "watch",
        fragile_segments: [{
          id: "inkproof-1",
          label: "Fragile ink area 1",
          reason: "A tight turn may be rounded off.",
          risk_score: 0.72,
          distance_m: 180,
          points_preview: [[47.4979, 19.0402], [47.4986, 19.0461]],
        }],
        tips: ["Slow down at the highlighted details."],
        method: "deterministic simulation",
      }),
    });
  });
  await openGeneratedRoute(page);
  await openOptionalRouteTools(page);
  await page.getByRole("button", { name: "Test recording durability" }).click();

  expect(requestBody.accuracy_m).toBe(10);
  expect(requestBody.points.length).toBeGreaterThan(3);
  const card = page.locator(".inkproof-card");
  await expect(card).toContainText("78% inkproof");
  await expect(card).toContainText("91%");
  await expect(page.locator(".route-analysis-segment--inkproof")).toHaveCount(1);
  await card.getByRole("button", { name: "Hide fragile ink on map" }).click();
  await expect(page.locator(".route-analysis-segment--inkproof")).toHaveCount(0);
});

test("post-activity Missing Ink rescue is offered for combining finished runs", async ({ page }) => {
  await openGeneratedRoute(page);
  await openOptionalRouteTools(page);

  const rescue = page.locator(".art-rescue-card");
  await expect(rescue.getByRole("heading", { name: "Combine finished runs" })).toBeVisible();
  await expect(rescue.getByRole("button", { name: "Compare recordings" })).toBeDisabled();
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
  await openOptionalRouteTools(page);
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

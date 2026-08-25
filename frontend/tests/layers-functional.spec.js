import { expect, test } from "playwright/test";

import {
  buildRouteResult,
  installCommonMocks,
  openGeneratedRoute,
  routePoints,
} from "./support/functional-fixtures.js";

test.beforeEach(async ({ page }) => {
  await installCommonMocks(page);
});

const OCCASIONS = {
  generated_on: "2026-08-23",
  days_ahead: 90,
  occasions: [
    {
      id: "state_foundation_day",
      name: "20 August — State Foundation & New Bread Day",
      date: "2026-08-20",
      days_until: 0,
      shape_prompt: "wheat",
      detail: "A wheat stalk for the new-bread and state-foundation holiday.",
      duration_days: 1,
    },
    {
      id: "halloween",
      name: "Halloween",
      date: "2026-10-31",
      days_until: 3,
      shape_prompt: "ghost",
      detail: "A friendly ghost that only exists on Strava.",
      duration_days: 1,
    },
    {
      id: "valentines_day",
      name: "Valentine's Day",
      date: "2027-02-14",
      days_until: 30,
      shape_prompt: "heart",
      detail: "Draw a heart for someone before the dinner reservation.",
      duration_days: 1,
    },
  ],
};

async function openOptionalRouteTools(page) {
  const tools = page.locator(".route-lab");
  if (!(await tools.locator(".route-lab-grid").isVisible())) {
    await tools.locator("summary").click();
  }
}

test("upcoming occasions fill the prompt with a dated drawing", async ({ page }) => {
  await page.route("**/occasions*", (route) =>
    route.fulfill({ contentType: "application/json", body: JSON.stringify(OCCASIONS) }),
  );
  await page.goto("/");
  const strip = page.getByRole("region", { name: "Route inspiration" });
  await expect(strip).toBeVisible();
  await expect(strip.locator(".occasion-chip")).toHaveCount(3);

  await strip.locator(".occasion-chip").first().click();
  const prompt = page.locator("#route-prompt");
  await expect(prompt).toHaveValue("wheat in Budapest, running, about 10 km");
  await expect(prompt).toBeFocused();
});

test("the occasion strip stays hidden when the service is unavailable", async ({ page }) => {
  await page.route("**/occasions*", (route) => route.fulfill({ status: 500, body: "{}" }));
  await page.goto("/");
  await expect(page.getByRole("region", { name: "Route inspiration" })).toHaveCount(0);
});

test("night-run check reports lighting shares and maps unlit sections", async ({ page }) => {
  await page.route("**/night-readiness", async (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        available: true,
        status: "review",
        lit_share: 0.72,
        unlit_share: 0.21,
        unknown_share: 0.07,
        traffic_exposure: 41.5,
        traffic_label: "moderate",
        concerns: [
          {
            code: "dark_section_1",
            label: "Unlit stretch 1",
            detail: "OpenStreetMap marks this part as not lit.",
            severity: "warning",
            distance_m: 640,
            segments_preview: [routePoints[0], routePoints[1]],
          },
        ],
        message: "Check the flagged stretches before heading out after dark.",
        note: "Lighting and traffic classes come from OpenStreetMap tags.",
      }),
    }),
  );
  await openGeneratedRoute(page);
  await openOptionalRouteTools(page);
  await page.getByRole("button", { name: "Check lighting" }).click();

  const card = page.locator(".night-card");
  await expect(card).toContainText("72%");
  await expect(card).toContainText("Moderate");
  await card.getByRole("button", { name: "Show unlit sections on map" }).click();
  await expect(page.locator(".route-analysis-segment--dark")).toHaveCount(1);
  await card.getByRole("button", { name: "Hide unlit sections" }).click();
  await expect(page.locator(".route-analysis-segment--dark")).toHaveCount(0);
});

test("night-run check explains when street data is unavailable", async ({ page }) => {
  await page.route("**/night-readiness", async (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        available: false,
        status: "unavailable",
        message: "The OpenStreetMap context service is temporarily unavailable.",
        concerns: [],
      }),
    }),
  );
  await openGeneratedRoute(page);
  await openOptionalRouteTools(page);
  await page.getByRole("button", { name: "Check lighting" }).click();

  await expect(page.locator(".night-card")).toContainText(
    "temporarily unavailable",
  );
});

test("sightseeing lists attractions in running order with map markers", async ({ page }) => {
  await page.route("**/route-landmarks", async (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        available: true,
        count: 2,
        corridor_m: 90,
        landmarks: [
          { name: "Great Library", kind: "museum", latitude: 47.53, longitude: 21.63, offset_km: 1.4 },
          { name: "Old Tower", kind: "historic", latitude: 47.54, longitude: 21.64, offset_km: 6.9 },
        ],
        message: "2 sight(s) sit right on this route.",
      }),
    }),
  );
  await openGeneratedRoute(page);
  await openOptionalRouteTools(page);
  await page.getByRole("button", { name: "Find sights" }).click();

  const list = page.locator(".landmarks-list");
  await expect(list.locator("li")).toHaveCount(2);
  await expect(list).toContainText("Great Library");
  await expect(list).toContainText("Old Tower");
  await expect(page.locator(".route-sight-marker")).toHaveCount(2);
});

test("combined recordings produce scores, merged GPX, and missing ink", async ({ page }) => {
  await page.route("**/art-rescue", async (route) => {
    const payload = route.request().postDataJSON();
    expect(payload.recordings).toHaveLength(2);
    expect(payload.planned_points.length).toBeGreaterThan(3);
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        recording_count: 2,
        track_segment_count: 2,
        coverage: 0.68,
        precision: 0.97,
        art_match: 0.8,
        tolerance_m: 25,
        recorded_distance_km: 18.4,
        missing_distance_km: 5.1,
        missing_segments: [
          {
            id: "missing-ink-1",
            label: "Missing ink 1",
            distance_m: 5100,
            points_preview: [routePoints[0], routePoints[2]],
            gpx: "<gpx />",
          },
        ],
        recorded_segments_preview: [routePoints],
        merged_recording_gpx: "<gpx><trkseg /></gpx>",
        missing_ink_gpx: "<gpx><trkseg /><trkseg /></gpx>",
        message: "1 separate repair mission(s) can complete the drawing.",
        authenticity: "The combined GPX contains recorded points only.",
        privacy: "Files were analysed in memory and were not stored.",
      }),
    });
  });

  await openGeneratedRoute(page);
  await openOptionalRouteTools(page);
  const rescue = page.locator(".art-rescue-card");
  await rescue.locator('input[type="file"]').setInputFiles([
    { name: "day-one.gpx", mimeType: "application/gpx+xml", buffer: Buffer.from("<gpx></gpx>") },
    { name: "day-two.gpx", mimeType: "application/gpx+xml", buffer: Buffer.from("<gpx></gpx>") },
  ]);
  await rescue.getByRole("button", { name: "Compare recordings" }).click();

  await expect(rescue).toContainText("68%");
  await expect(rescue).toContainText("repair mission");
  await expect(rescue.getByRole("button", { name: "Combined GPX" })).toBeVisible();
  await expect(rescue.getByRole("button", { name: "Missing-ink mission" })).toBeVisible();
  await rescue.getByRole("button", { name: "Show missing parts on map" }).click();
  await expect(page.locator(".route-analysis-segment--missing")).toHaveCount(1);
});

test("a road-routed route offers a printable gift poster", async ({ page }) => {
  await openGeneratedRoute(page);
  await expect(page.locator(".route-map .leaflet-overlay-pane path").first()).toBeVisible();
  await page.getByRole("button", { name: "Gift poster" }).click();

  const overlay = page.getByRole("dialog", { name: "Gift poster preview" });
  await expect(overlay).toBeVisible();
  await expect(overlay.locator("img")).toBeVisible();
  await expect(page.locator(".poster-stats")).toContainText("Star");

  await overlay.getByLabel("Dedication").fill("For Ada");
  await expect(overlay.locator(".poster-title")).toHaveText("For Ada");

  await overlay.getByRole("button", { name: "Close" }).click();
  await expect(overlay).toHaveCount(0);
});

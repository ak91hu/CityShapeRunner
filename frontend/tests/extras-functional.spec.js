import { expect, test } from "playwright/test";

import {
  installCommonMocks,
  openGeneratedRoute,
  routePoints,
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

test("route-lab groups its tools under four labelled headings", async ({ page }) => {
  await openGeneratedRoute(page);
  await openOptionalRouteTools(page);

  const titles = page.locator(".route-lab-group-title");
  await expect(titles).toHaveCount(4);
  await expect(titles.first()).toHaveText("On the day");
  await expect(titles.nth(1)).toHaveText("Sharpen the drawing");
  await expect(titles.nth(2)).toHaveText("Create together");
  await expect(titles.nth(3)).toHaveText("Teach & share");
});

test("accessibility check reports shares and maps barrier sections", async ({ page }) => {
  await page.route("**/accessibility-readiness", async (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        available: true,
        status: "review",
        wheelchair_yes_share: 0.55,
        wheelchair_no_share: 0.18,
        steps_share: 0.12,
        unpaved_share: 0.05,
        paved_share: 0.4,
        untagged_share: 0.1,
        concerns: [
          {
            code: "barrier_1",
            label: "Steps stretch 1",
            detail: "Steps make this section impassable for wheels.",
            severity: "warning",
            distance_m: 420,
            segments_preview: [routePoints[0], routePoints[1]],
          },
        ],
        message: "Check the flagged sections before planning a wheelchair or stroller ride.",
        note: "Untagged streets are unknown, not accessible.",
      }),
    }),
  );
  await openGeneratedRoute(page);
  await openOptionalRouteTools(page);
  await page.getByRole("button", { name: "Check accessibility" }).click();

  const card = page.locator(".accessibility-card");
  await expect(card).toContainText("55%");
  await expect(card).toContainText("30%");
  await card.getByRole("button", { name: "Show barriers on map" }).click();
  await expect(page.locator(".route-analysis-segment--dark")).toHaveCount(1);
});

test("lesson pack builds a printable worksheet with bearings", async ({ page }) => {
  await page.route("**/lesson-pack", async (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        available: true,
        title: "star walk in Debrecen",
        shape_name: "star",
        closed: true,
        waypoint_count: 5,
        waypoints: [
          { id: "A", to_id: "B", latitude: 47.53, longitude: 21.62, bearing_deg: 90, compass: "E", leg_distance_m: 820, cumulative_m: 0 },
          { id: "B", to_id: "C", latitude: 47.53, longitude: 21.63, bearing_deg: 180, compass: "S", leg_distance_m: 640, cumulative_m: 820 },
        ],
        total_distance_m: 2100,
        total_distance_km: 2.1,
        extent_m: 900,
        scale_ratio: 5294,
        notes: ["Bearings are measured from north."],
      }),
    }),
  );
  await openGeneratedRoute(page);
  await openOptionalRouteTools(page);
  await page.getByRole("button", { name: "Build worksheet" }).click();

  const sheet = page.getByRole("dialog", { name: "Classroom worksheet preview" });
  await expect(sheet).toBeVisible();
  await expect(sheet.locator(".lesson-table tbody tr")).toHaveCount(2);
  await expect(sheet).toContainText("1 : 5294");
  await expect(sheet.locator(".lesson-drawing svg > path")).toHaveCount(1);
  await sheet.getByRole("button", { name: "Close" }).click();
  await expect(sheet).toHaveCount(0);
});

test("reel recorder opens with a length choice and closes cleanly", async ({ page }) => {
  await openGeneratedRoute(page);
  await expect(page.locator(".route-map .leaflet-overlay-pane path").first()).toBeVisible();
  const opener = page.getByRole("button", { name: "Record reel" });
  await opener.click();

  const overlay = page.getByRole("dialog", { name: "Reel recorder" });
  await expect(overlay).toBeVisible();
  await expect(overlay.locator("select")).toHaveValue("8");
  await expect(overlay.locator("select")).toBeFocused();
  await expect(overlay.getByRole("button", { name: "Record reel" })).toBeEnabled({ timeout: 10_000 });
  await page.keyboard.press("Escape");
  await expect(overlay).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("a campaign link prefills the prompt and shows the banner", async ({ page }) => {
  await page.route("**/occasions*", (route) =>
    route.fulfill({ contentType: "application/json", body: JSON.stringify({ occasions: [] }) }),
  );
  await page.goto("/?campaign=Pink%20Ribbon%20Budapest&shape=ribbon&hashtag=%23runforcare&until=2026-10-31");

  const banner = page.locator(".campaign-banner");
  await expect(banner).toContainText("Pink Ribbon Budapest");
  await expect(banner).toContainText("#runforcare");
  await expect(page.locator("#route-prompt")).toHaveValue("ribbon in Budapest, running, about 10 km");

  await banner.locator(".campaign-banner-dismiss").click();
  await expect(banner).toHaveCount(0);
});

test("the campaign builder produces a shareable link", async ({ page }) => {
  await page.goto("/");
  const opener = page.getByRole("button", { name: "Organise a campaign" });
  await opener.click();

  const overlay = page.getByRole("dialog", { name: "Charity art campaign builder" });
  await expect(overlay).toBeVisible();
  await expect(overlay.getByLabel("Campaign name")).toBeFocused();
  await overlay.getByLabel("Campaign name").fill("Balatoni Szív Hét");
  await overlay.getByLabel("Drawing").selectOption("circle");
  await overlay.getByLabel("Campaign name").press("Enter");

  const link = overlay.locator(".campaign-link code");
  await expect(link).toContainText("campaign=Balatoni+Sz%C3%ADv+H%C3%A9t");
  await expect(link).toContainText("shape=circle");
  await page.keyboard.press("Escape");
  await expect(overlay).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("city picks appear for curated destinations and fill the prompt", async ({ page }) => {
  await page.route("**/occasions*", (route) =>
    route.fulfill({ contentType: "application/json", body: JSON.stringify({ occasions: [] }) }),
  );
  await page.route("**/destinations", async (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        destinations: [
          {
            city: "Balatonfured",
            shape_prompt: "fish",
            name: "Balaton fish",
            blurb: "Draw the lake's most famous resident.",
            distance_km: 8,
            sport: "run",
            partner_ready: true,
          },
        ],
      }),
    }),
  );
  await page.goto("/");
  // The suggestion form's city select contains the accented lakeshore name.
  await page.locator(".suggest-panel summary").click();
  const citySelect = page.locator("#suggest-city");
  await citySelect.selectOption({ label: "Balatonfüred" });

  const strip = page.getByRole("region", { name: "Route inspiration" });
  await expect(strip).toBeVisible();
  await strip.locator("summary").click();
  const chip = strip.locator(".city-pick-chip");
  await expect(chip).toHaveCount(1);
  await chip.click();
  await expect(page.locator("#route-prompt")).toHaveValue(/fish in Balatonf.+ about 8 km/);
});

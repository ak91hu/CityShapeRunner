import { readFile } from "node:fs/promises";
import { expect, test } from "playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { buildCandidate, buildRouteResult, installCommonMocks, moveEditPoint, openGeneratedRoute, routePoints } from "./support/functional-fixtures.js";

test.beforeEach(async ({ page }) => { await installCommonMocks(page); });

async function mockPlan(page, { failFirst = false, dense = false } = {}) {
  const requests = [];
  await page.route("**/mural-plan", async route => {
    const payload = route.request().postDataJSON();
    requests.push(payload);
    if (failFirst && requests.length === 1) {
      await route.fulfill({ status: 422, contentType: "application/json", body: JSON.stringify({ detail: "Ada's allocation exceeds their distance limit. Choose a shorter drawing." }) });
      return;
    }
    const points = dense ? [...Array.from({ length: 3000 }, (_, index) => {
      const leg = Math.floor(index / 1000);
      const fraction = (index % 1000) / 1000;
      return routePoints[leg].map((value, axis) => value + (routePoints[leg + 1][axis] - value) * fraction);
    }), routePoints.at(-1)] : payload.points;
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({
      points_preview: points, participant_count: payload.members.length,
      travel_note: payload.return_to_start ? "Meeting-point travel is included in each limit." : "Travel to the start and home is not included.",
      sections: payload.members.map((member, index) => ({
        id: `mural-${index + 1}`, label: member.name, max_distance_km: member.max_distance_km,
        distance_km: index === 0 ? 1.5 : 4, art_distance_km: index === 0 ? 1 : 3,
        travel_distance_km: index === 0 ? 0.5 : 1,
        start: routePoints[index], finish: routePoints[index + 1],
        points_preview: routePoints.slice(index, index + 2), travel_segments_preview: [],
        gpx: `<gpx><metadata><name>${member.name}</name></metadata></gpx>`,
      })),
    }) });
  });
  return requests;
}

async function groupResult(page) {
  await openGeneratedRoute(page);
  await page.getByRole("radio", { name: "Group", exact: true }).check();
  const group = page.getByRole("region", { name: "Create together" });
  await expect(group).toBeVisible();
  return group;
}

test("personal remains the default and switching modes preserves the route idea", async ({ page }) => {
  await page.goto("/");
  const personal = page.getByRole("radio", { name: "Personal", exact: true });
  const group = page.getByRole("radio", { name: "Group", exact: true });
  await expect(personal).toBeChecked();
  await expect(page.getByLabel("Open saved event")).toBeHidden();
  await page.getByLabel("Drawing and location").fill("a heart in Pécs, walking, 8 km");
  await personal.focus();
  await page.keyboard.press("ArrowRight");
  await expect(group).toBeChecked();
  await expect(group).toBeFocused();
  await expect(page).toHaveURL(/mode=group/);
  await expect(page.getByLabel("Open saved event")).toBeVisible();
  await expect(page.getByLabel("Drawing and location")).toHaveValue("a heart in Pécs, walking, 8 km");
  await personal.check();
  await expect(page).not.toHaveURL(/mode=group/);
  await expect(page.getByLabel("Drawing and location")).toHaveValue("a heart in Pécs, walking, 8 km");
});

test("named unequal assignments survive mode changes, map selection and saving", async ({ page }) => {
  const requests = await mockPlan(page, { dense: true });
  const group = await groupResult(page);
  await group.getByLabel("Participant 1", { exact: true }).fill("Ada");
  await group.getByLabel("Participant 2", { exact: true }).fill("Bea");
  await group.getByLabel("Maximum km for participant 1").fill("2");
  await group.getByLabel("Maximum km for participant 2").fill("8");
  await group.getByRole("checkbox", { name: /Meet and return/ }).check();
  await group.getByRole("button", { name: "Create mural plan" }).click();
  await expect(group.locator(".group-event-result")).toBeFocused();
  expect(requests[0].members).toEqual([{ name: "Ada", max_distance_km: 2 }, { name: "Bea", max_distance_km: 8 }]);
  expect(requests[0].return_to_start).toBe(true);
  await expect(group).toContainText("1.00 km drawing · 0.50 km travel · maximum 2 km");
  await group.getByRole("button", { name: "Show Ada on map" }).click();
  await expect(group.locator(".route-analysis-segment")).toHaveCount(1);
  await page.getByRole("radio", { name: "Personal", exact: true }).check();
  await expect(group).toBeHidden();
  await page.getByRole("radio", { name: "Group", exact: true }).check();
  await expect(group.getByLabel("Participant 1", { exact: true })).toHaveValue("Ada");
  await expect(group.getByRole("button", { name: "GPX for Ada" })).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await group.getByRole("button", { name: "Save event plan" }).click();
  const file = await downloadPromise;
  const saved = await readFile(await file.path(), "utf8");
  expect(JSON.parse(saved).members[0].max_distance_km).toBe(2);
  expect(JSON.parse(saved).points).toEqual(requests[0].points);
  await page.goto("/?mode=group");
  const resumed = page.getByRole("region", { name: "Create together" });
  await resumed.getByLabel("Open saved event").setInputFiles({ name: "event.json", mimeType: "application/json", buffer: Buffer.from(saved) });
  await expect(resumed).toContainText("Check the saved route against current streets");
  await expect(resumed.getByRole("button", { name: "GPX for Ada" })).toHaveCount(0);
  await resumed.getByRole("button", { name: "Create mural plan" }).click();
  await expect(resumed.getByRole("button", { name: "GPX for Ada" })).toBeDisabled();
  await resumed.getByRole("checkbox", { name: /I reviewed the restored street drawing/ }).check();
  await expect(resumed.getByRole("button", { name: "GPX for Ada" })).toBeVisible();
  await expect(resumed.getByRole("button", { name: "GPX for Ada" })).toBeEnabled();
});

test("capacity errors recover and changing the roster invalidates downloadable assignments", async ({ page }) => {
  const requests = await mockPlan(page, { failFirst: true });
  const group = await groupResult(page);
  await group.getByRole("button", { name: "Create mural plan" }).click();
  await expect(group.getByRole("alert")).toContainText("distance limit");
  await expect(group.getByRole("button", { name: "Save event plan" })).toHaveCount(0);
  await group.getByLabel("Maximum km for participant 1").fill("20");
  await group.getByRole("button", { name: "Create mural plan" }).click();
  await expect(group.getByRole("button", { name: "Save event plan" })).toBeVisible();
  await expect(group.locator(".group-event-result")).toBeFocused();
  expect(requests).toHaveLength(2);
  await group.getByLabel("Participant 1", { exact: true }).fill("Different artist");
  await expect(group.locator(".group-event-result")).toHaveCount(0);
  await page.locator(".candidate-card").nth(1).click();
  await expect(group.getByLabel("Participant 1", { exact: true })).toHaveValue("Different artist");
  await expect(group.getByRole("button", { name: "Create mural plan" })).toBeDisabled();
  await page.locator(".candidate-card").nth(0).click();
  await expect(group.getByRole("button", { name: "Create mural plan" })).toBeEnabled();
});

test("group completion shows missing missions without claiming verified participation", async ({ page }) => {
  await mockPlan(page);
  await page.route("**/art-rescue", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({
    coverage: 0.6, precision: 0.9, art_match: 0.72,
    message: "1 separate repair mission can complete the drawing.",
    authenticity: "Coverage uses the uploaded recordings. This is not proof of participation.",
    missing_segments: [{ id: "missing-1", label: "Missing ink 1", distance_m: 500, points_preview: routePoints.slice(0, 2), gpx: "<gpx />" }],
    merged_recording_gpx: "<gpx />", missing_ink_gpx: "<gpx />",
  }) }));
  const group = await groupResult(page);
  await group.getByRole("button", { name: "Create mural plan" }).click();
  const rescue = group.locator(".art-rescue-card");
  await rescue.getByLabel("Recordings").setInputFiles({ name: "outing.gpx", mimeType: "application/gpx+xml", buffer: Buffer.from("<gpx />") });
  await rescue.getByRole("button", { name: "Compare recordings" }).click();
  await expect(rescue).toContainText("60%");
  await expect(rescue).toContainText("not proof of participation");
  await expect(rescue.getByRole("button", { name: "GPX for Missing ink 1" })).toBeVisible();
  await rescue.getByRole("button", { name: "Show missing parts on map" }).click();
  await expect(group.locator(".route-analysis-segment--missing")).toHaveCount(1);
  await rescue.getByLabel("Recordings").setInputFiles([]);
  await expect(group.locator(".route-analysis-segment--missing")).toHaveCount(0);
});

test("invalid saved files do not replace the route or roster", async ({ page }) => {
  const group = await groupResult(page);
  await group.getByLabel("Participant 1", { exact: true }).fill("Ada");
  await group.getByLabel("Open saved event").setInputFiles({ name: "bad.json", mimeType: "application/json", buffer: Buffer.from('{"format":"paceasso-group-v1","members":"wrong"}') });
  await expect(group.getByRole("alert")).toContainText("invalid route or participant");
  await expect(group.getByLabel("Participant 1", { exact: true })).toHaveValue("Ada");
});

test("participant names appear literally in map tooltips without executing HTML", async ({ page }) => {
  await mockPlan(page);
  const group = await groupResult(page);
  const name = '<img src=x onerror="window.groupXss=1">';
  await group.getByLabel("Participant 1", { exact: true }).fill(name);
  await group.getByRole("button", { name: "Create mural plan" }).click();
  await group.getByRole("button", { name: `Show ${name} on map` }).click();
  await group.locator(".route-analysis-segment").dispatchEvent("mouseover");
  const tooltip = group.locator(".leaflet-tooltip");
  await expect(tooltip).toContainText(name);
  await expect(tooltip.locator("img")).toHaveCount(0);
  expect(await page.evaluate(() => window.groupXss)).toBeUndefined();
});

test("cancelling a recording comparison retains the files and ignores its late response", async ({ page }) => {
  await mockPlan(page);
  let release;
  await page.route("**/art-rescue", async route => {
    await new Promise(resolve => { release = resolve; });
    await route.fulfill({ contentType: "application/json", body: "{}" }).catch(() => {});
  });
  const group = await groupResult(page);
  await group.getByRole("button", { name: "Create mural plan" }).click();
  await expect(group.locator(".group-event-result")).toBeFocused();
  const rescue = group.locator(".art-rescue-card");
  await rescue.getByLabel("Recordings").setInputFiles({ name: "outing.gpx", mimeType: "application/gpx+xml", buffer: Buffer.from("<gpx />") });
  await rescue.getByRole("button", { name: "Compare recordings" }).click();
  await rescue.getByRole("button", { name: "Cancel comparison" }).click();
  await expect(rescue.getByRole("button", { name: "Compare recordings" })).toBeEnabled();
  await expect(rescue).toContainText("1 file ready");
  release();
  await expect(rescue.locator(".readiness-metrics")).toHaveCount(0);
});

test("cancelling a group check restores the form and ignores its late response", async ({ page }) => {
  let release;
  await page.route("**/mural-plan", async route => {
    await new Promise(resolve => { release = resolve; });
    await route.fulfill({ contentType: "application/json", body: "{}" }).catch(() => {});
  });
  const group = await groupResult(page);
  await group.getByRole("button", { name: "Create mural plan" }).click();
  await expect(group.getByLabel("Participant 1", { exact: true })).toBeDisabled();
  await group.getByRole("button", { name: "Cancel group check" }).click();
  await expect(group.getByLabel("Participant 1", { exact: true })).toBeEnabled();
  release();
  await group.getByLabel("Participant 1", { exact: true }).fill("Ada");
  await expect(group.locator(".group-event-result")).toHaveCount(0);
});

test("group forms and assignments remain accessible and fit a narrow viewport", async ({ page }, testInfo) => {
  test.slow();
  await page.setViewportSize({ width: 390, height: 844 });
  await mockPlan(page);
  const group = await groupResult(page);
  await group.getByRole("button", { name: "Add participant" }).click();
  await group.getByRole("button", { name: "Remove participant 3" }).click();
  await group.getByRole("button", { name: "Create mural plan" }).click();
  await expect(group.locator(".group-event-result")).toBeFocused();
  await expect(group.locator(".street-route-line")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("group-mode-mobile.png"), fullPage: true });
  const audit = await new AxeBuilder({ page }).analyze();
  expect(audit.violations.map(({ id, nodes }) => ({ id, targets: nodes.map(node => node.target) }))).toEqual([]);
  expect(await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth)).toBeLessThanOrEqual(1);
});

test("group export keeps the selected route's review gate", async ({ page }) => {
  await openGeneratedRoute(page, buildRouteResult({ candidates: [buildCandidate({ id: "needs-review", score: 0.6, distanceKm: 20 })] }));
  await page.getByRole("radio", { name: "Group", exact: true }).check();
  const group = page.getByRole("region", { name: "Create together" });
  await expect(group.getByRole("button", { name: "Create mural plan" })).toBeDisabled();
});

test("pending route edits invalidate group exports until the original route is restored", async ({ page }) => {
  await mockPlan(page);
  const group = await groupResult(page);
  await group.getByRole("button", { name: "Create mural plan" }).click();
  await expect(group.getByRole("button", { name: "GPX for Artist 1" })).toBeVisible();
  await page.getByRole("button", { name: "Edit this route" }).click();
  await moveEditPoint(page.locator(".route-edit-marker").first(), "ArrowUp");
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeDisabled();
  await expect(group.getByRole("button", { name: "Create mural plan" })).toBeDisabled();
  await expect(group.getByRole("button", { name: "GPX for Artist 1" })).toHaveCount(0);
  await page.getByRole("button", { name: "Start over" }).click();
  await expect(group.getByRole("button", { name: "Create mural plan" })).toBeEnabled();
  await expect(group.getByRole("button", { name: "GPX for Artist 1" })).toHaveCount(0);
});

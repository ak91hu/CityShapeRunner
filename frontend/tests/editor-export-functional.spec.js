import { expect, test } from "playwright/test";

import {
  buildEditedRoute,
  installCommonMocks,
  openGeneratedRoute,
  routePoints,
} from "./support/functional-fixtures.js";

test.beforeEach(async ({ page }) => {
  await installCommonMocks(page);
});

async function mockSuccessfulEdit(page, response = buildEditedRoute()) {
  let payload = null;
  await page.route("**/edit-route", async (route) => {
    payload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(response),
    });
  });
  return () => payload;
}

test("opening the editor exposes four labelled keyboard-operable points", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.getByRole("button", { name: "Edit this route" }).click();

  const markers = page.locator(".route-edit-marker");
  await expect(markers).toHaveCount(4);
  await expect(markers.first()).toHaveAttribute(
    "aria-label",
    "Edit point 1. Drag it or use the arrow keys to move it.",
  );
  await expect(markers.first()).toHaveAttribute("tabindex", "0");
  await expect(page.getByRole("button", { name: "Start over" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Apply changes" })).toBeVisible();
});

test("a clean editor can be closed without changing the route", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.getByRole("button", { name: "Edit this route" }).click();
  await expect(page.getByRole("button", { name: "Close editor" })).toBeVisible();
  await page.getByRole("button", { name: "Close editor" }).click();

  await expect(page.locator(".route-edit-marker")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Edit this route" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeEnabled();
});

test("ArrowRight changes longitude in the edit request", async ({ page }) => {
  const editPayload = await mockSuccessfulEdit(page);
  await openGeneratedRoute(page);
  await page.getByRole("button", { name: "Edit this route" }).click();
  const marker = page.locator(".route-edit-marker").first();
  await marker.focus();
  await marker.press("ArrowRight");
  await page.getByRole("button", { name: "Apply changes" }).click();

  await expect.poll(() => editPayload()).not.toBeNull();
  expect(editPayload().control_points[0][1]).toBeCloseTo(routePoints[0][1] + 0.0001, 6);
});

test("Shift plus an arrow key makes the documented larger adjustment", async ({ page }) => {
  const editPayload = await mockSuccessfulEdit(page);
  await openGeneratedRoute(page);
  await page.getByRole("button", { name: "Edit this route" }).click();
  const marker = page.locator(".route-edit-marker").first();
  await marker.focus();
  await marker.press("Shift+ArrowUp");
  await page.getByRole("button", { name: "Apply changes" }).click();

  await expect.poll(() => editPayload()).not.toBeNull();
  expect(editPayload().control_points[0][0]).toBeCloseTo(routePoints[0][0] + 0.0005, 6);
});

test("moving the first point of a closed route keeps the last point synchronized", async ({
  page,
}) => {
  const editPayload = await mockSuccessfulEdit(page);
  await openGeneratedRoute(page);
  await page.getByRole("button", { name: "Edit this route" }).click();
  const marker = page.locator(".route-edit-marker").first();
  await marker.focus();
  await marker.press("ArrowLeft");
  await page.getByRole("button", { name: "Apply changes" }).click();

  await expect.poll(() => editPayload()).not.toBeNull();
  expect(editPayload().control_points.at(-1)).toEqual(editPayload().control_points[0]);
});

test("Start over restores the original control points before applying", async ({ page }) => {
  const editPayload = await mockSuccessfulEdit(page);
  await openGeneratedRoute(page);
  await page.getByRole("button", { name: "Edit this route" }).click();
  const marker = page.locator(".route-edit-marker").first();
  await marker.focus();
  await marker.press("ArrowDown");
  await page.getByRole("button", { name: "Start over" }).click();
  await page.getByRole("button", { name: "Apply changes" }).click();

  await expect.poll(() => editPayload()).not.toBeNull();
  expect(editPayload().control_points[0]).toEqual(routePoints[0]);
});

test("resetting dirty edits restores downloads while the editor stays open", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.getByRole("button", { name: "Edit this route" }).click();
  const marker = page.locator(".route-edit-marker").first();
  await marker.focus();
  await marker.press("ArrowUp");

  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Download TCX", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Start over" }).click();
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Download TCX", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Close editor" })).toBeVisible();
});

test("a successful edit replaces distance and export state with the edited route", async ({
  page,
}) => {
  await mockSuccessfulEdit(page, buildEditedRoute({ distanceKm: 20.05 }));
  await openGeneratedRoute(page);
  await page.getByRole("button", { name: "Edit this route" }).click();
  await page.getByRole("button", { name: "Apply changes" }).click();

  await expect(page.getByText(/Changes saved: 20.05 km/)).toBeVisible();
  await expect(
    page.locator(".metric").filter({ has: page.locator("dt", { hasText: /^Distance$/ }) }),
  ).toContainText("20.05 km");
  await expect(page.getByRole("button", { name: "Download edited GPX" })).toBeEnabled();
  await expect(page.getByText("Publish map image")).toHaveCount(0);
});

test("the editor shows an applying state and prevents duplicate submission", async ({ page }) => {
  let releaseResponse;
  const responseGate = new Promise((resolve) => {
    releaseResponse = resolve;
  });
  let requestCount = 0;
  await page.route("**/edit-route", async (route) => {
    requestCount += 1;
    await responseGate;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildEditedRoute()),
    });
  });
  await openGeneratedRoute(page);
  await page.getByRole("button", { name: "Edit this route" }).click();
  await page.getByRole("button", { name: "Apply changes" }).click();

  const applying = page.getByRole("button", { name: "Applying changes…" });
  await expect(applying).toBeDisabled();
  expect(requestCount).toBe(1);
  releaseResponse();
  await expect(page.getByText(/Changes saved/)).toBeVisible();
  expect(requestCount).toBe(1);
});

test("approval of a review candidate remains scoped to that option", async ({ page }) => {
  let acceptancePayload = null;
  await page.unroute("**/route-acceptance");
  await page.route("**/route-acceptance", async (route) => {
    acceptancePayload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ recorded: true }),
    });
  });
  await openGeneratedRoute(page);
  const selector = page.getByLabel("Route options");
  await selector.selectOption("candidate-review");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Approve and download GPX" }).click();
  await downloadPromise;

  await expect.poll(() => acceptancePayload?.route_id).toBe("candidate-review");
  await selector.selectOption("candidate-ready");
  await expect(page.locator(".route-state")).toContainText("Ready to download");
  await selector.selectOption("candidate-review");
  await expect(page.locator(".route-state")).toContainText("Approved by you");
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeEnabled();
});

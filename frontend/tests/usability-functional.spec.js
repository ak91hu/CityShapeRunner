import { expect, test } from "playwright/test";

import {
  installCommonMocks,
  mockGeneration,
  openGeneratedRoute,
} from "./support/functional-fixtures.js";

test.beforeEach(async ({ page }) => {
  await installCommonMocks(page);
});

for (const [label, panel, field] of [
  ["Suggest a shape", "#planner-start-fields", "#suggest-city"],
  ["Place on map", "#planner-start-map", "#map-placement-shape"],
  ["Use image link", "#planner-start-image", "#image-reference-url"],
]) {
  test(`${label} opens its form directly without changing the route idea`, async ({ page }) => {
    const capture = await mockGeneration(page);
    await page.route("**/shape-templates", (route) => route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ shapes: [{ id: "heart", label: "Heart" }] }),
    }));
    await page.goto("/");
    const prompt = page.getByLabel("Drawing and location");
    await prompt.fill("a fox in Sopron, running, 12 km");
    const shortcut = page.getByRole("button", { name: label, exact: true });
    await shortcut.focus();
    await shortcut.press("Enter");

    await expect(page.locator(panel)).toHaveAttribute("open", "");
    await expect(page.locator(`${panel} > summary`)).toBeFocused();
    await expect(page.locator(field)).toBeVisible();
    await expect(prompt).toHaveValue("a fox in Sopron, running, 12 km");
    expect(capture.requests).toHaveLength(0);
  });
}

test("the catalog combines category and text filters and can recover from no matches", async ({ page }) => {
  await page.goto("/");
  await page.getByText("More shapes, letters, and numbers").click();
  await page.getByLabel("Category", { exact: true }).selectOption("Animals");
  await page.getByLabel("Filter options").fill("turtle");

  const catalog = page.locator(".idea-catalog");
  await expect(catalog.getByRole("region", { name: "Animals ideas" })).toBeVisible();
  await expect(catalog.locator(".idea-group button")).toHaveCount(1);
  await catalog.getByRole("button", { name: "Turtle", exact: true }).click();
  await expect(page.getByLabel("Drawing and location")).toHaveValue("a turtle run in Keszthely, about 14 km");

  await page.getByLabel("Category", { exact: true }).selectOption("Nature");
  await expect(catalog.locator(".idea-empty")).toBeVisible();
  await catalog.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByLabel("Filter options")).toBeFocused();
  await expect(page.getByLabel("Filter options")).toHaveValue("");
  await expect(page.getByLabel("Category", { exact: true })).toHaveValue("");
  await expect(catalog.locator(".idea-group button")).toHaveCount(158);
  await expect(page.getByLabel("Drawing and location")).toHaveValue("a turtle run in Keszthely, about 14 km");
});

test("review moves keyboard focus to the new step and Back restores the idea", async ({ page }) => {
  const capture = await mockGeneration(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Review request", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Check your request" })).toBeFocused();
  expect(capture.requests).toHaveLength(0);
  await page.getByRole("button", { name: "Back", exact: true }).click();
  await expect(page.getByLabel("Drawing and location")).toBeFocused();
});

test("a review candidate stays selected after visiting the gallery", async ({ page }) => {
  const capture = await openGeneratedRoute(page);
  await page.locator(".candidate-card").nth(1).click();
  await page.getByRole("link", { name: "Gallery", exact: true }).click();
  await expect(page.locator(".result")).toBeHidden();
  await page.getByRole("link", { name: "Your route", exact: true }).click();

  await expect(page.locator(".result")).toBeFocused();
  await expect(page.locator(".candidate-card").nth(1)).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".route-state")).toContainText("Check before downloading");
  await expect(page.getByRole("button", { name: "Approve and download GPX" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toHaveCount(0);
  expect(capture.requests).toHaveLength(1);
});

test("unfinished map edits remain intact and block download after leaving the result", async ({ page }) => {
  const capture = await openGeneratedRoute(page);
  await page.getByRole("button", { name: "Edit this route" }).click();
  await page.locator(".route-edit-marker").first().press("ArrowUp");
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeDisabled();

  await page.getByRole("link", { name: "Create route", exact: true }).click();
  await expect(page.getByLabel("Drawing and location")).toBeVisible();
  await page.getByRole("link", { name: "Your route", exact: true }).click();

  await expect(page.getByRole("button", { name: "Apply changes", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Download TCX", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Start over", exact: true }).click();
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeEnabled();
  expect(capture.requests).toHaveLength(1);
});

test("browser Back returns to the current route after opening Create route", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.getByRole("link", { name: "Your route", exact: true }).click();
  await page.getByRole("link", { name: "Create route", exact: true }).click();
  await expect(page.getByLabel("Drawing and location")).toBeVisible();
  await page.goBack();
  await expect(page.locator(".result")).toBeVisible();
  await expect(page.locator(".result")).toBeFocused();
});

test("browser Back closes route dialogs and releases the gallery's keyboard and scroll", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.getByRole("link", { name: "Gallery", exact: true }).click();
  await page.getByRole("link", { name: "Your route", exact: true }).click();
  await page.getByText("More ways to use this route", { exact: true }).click();
  await page.getByRole("button", { name: "Record reel", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.goBack();

  await expect(page.locator("#gallery")).toBeVisible();
  await expect(page.getByRole("dialog", { includeHidden: true })).toHaveCount(0);
  await expect.poll(() => page.locator("body").evaluate((element) => element.style.overflow)).not.toBe("hidden");
  const returnLink = page.getByRole("link", { name: "Your route", exact: true });
  await returnLink.focus();
  await returnLink.press("Enter");
  await expect(page.locator(".result")).toBeFocused();
  await expect(page.getByRole("dialog", { includeHidden: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Record reel", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("a failed generation provides a focused editing path without retrying", async ({ page }) => {
  let attempts = 0;
  await page.route("**/generate", (route) => {
    attempts += 1;
    return route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "No connected street route could be created." }),
    });
  });
  await page.goto("/");
  const prompt = page.getByLabel("Drawing and location");
  const idea = await prompt.inputValue();
  await page.getByRole("button", { name: "Review request", exact: true }).click();
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  await page.getByRole("button", { name: "Edit route idea", exact: true }).click();

  await expect(prompt).toBeFocused();
  await expect(prompt).toHaveValue(idea);
  await expect(page.locator(".error-card")).toHaveCount(0);
  expect(attempts).toBe(1);
});

test("compact layouts put the planner before the gallery and fit a 320px viewport", async ({ page }) => {
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");
    const planner = await page.locator(".designer-card").boundingBox();
    const example = await page.locator(".studio-art").boundingBox();
    expect(planner.y + planner.height).toBeLessThanOrEqual(example.y);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    for (const button of await page.locator(".planner-start-links button").all()) {
      expect((await button.boundingBox()).height).toBeGreaterThanOrEqual(44);
    }
  }
});

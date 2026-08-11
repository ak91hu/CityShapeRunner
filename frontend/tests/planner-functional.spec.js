import { expect, test } from "playwright/test";

import { installCommonMocks, mockGeneration } from "./support/functional-fixtures.js";

test.beforeEach(async ({ page }) => {
  await installCommonMocks(page);
});

test("primary navigation links reach each planner section", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { level: 1, name: "Plan a GPS art route" })).toBeVisible();
  await expect(page.locator(".journey-list, .eyebrow, .step-label, .keyboard-hint")).toHaveCount(0);
  await expect(page.getByText(/surprise me|need inspiration/i)).toHaveCount(0);
  await expect(page.getByText("Map data © OpenStreetMap contributors")).toHaveCount(1);
  expect(await page.locator("body").evaluate((element) => getComputedStyle(element).backgroundImage))
    .toBe("none");
  await expect(page.getByRole("link", { name: "Skip to route planner" })).toHaveAttribute(
    "href",
    "#route-designer",
  );
  const plannerLink = page.locator('.site-header nav a[href="#route-designer"]');
  const galleryLink = page.locator('.site-header nav a[href="#gallery"]');
  await expect(plannerLink).toHaveAttribute("href", "#route-designer");
  await expect(galleryLink).toHaveAttribute("href", "#gallery");
  await expect(page.locator("#route-designer")).toBeAttached();
  await expect(page.locator("#gallery")).toBeAttached();

  if (await plannerLink.isVisible()) {
    await plannerLink.click();
    await expect.poll(() => new URL(page.url()).hash).toBe("#route-designer");
    await galleryLink.click();
    await expect.poll(() => new URL(page.url()).hash).toBe("#gallery");
  }
});

test("the route idea exposes its help and character count to assistive technology", async ({
  page,
}) => {
  await page.goto("/");

  const prompt = page.getByLabel("Drawing and location");
  await expect(prompt).toHaveAttribute("aria-describedby", "prompt-help prompt-count");
  await expect(page.locator("#prompt-help")).toContainText("a flying pig in Budapest");
  await expect(page.locator("#prompt-count")).toHaveText("35/320");
  await expect(prompt).toBeFocused();
});

test("choosing a popular idea updates the prompt and selected state", async ({ page }) => {
  await page.goto("/");

  const heart = page.getByRole("button", { name: "Heart", exact: true });
  const star = page.getByRole("button", { name: "Star", exact: true });
  await expect(heart).toHaveAttribute("aria-pressed", "true");
  await star.click();

  await expect(star).toHaveAttribute("aria-pressed", "true");
  await expect(heart).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByLabel("Drawing and location")).toHaveValue(
    "a star bike route in Debrecen, about 20 km",
  );
});

test("the full idea catalogue exposes every category and all 141 options", async ({ page }) => {
  await page.goto("/");
  await page.getByText("More shapes, letters, and numbers").click();

  await expect(page.locator(".idea-catalog").getByRole("button")).toHaveCount(141);
  for (const category of [
    "Simple shapes",
    "Nature",
    "Animals",
    "Objects",
    "Symbols",
    "Letters, numbers & text",
  ]) {
    await expect(page.getByRole("region", { name: `${category} ideas` })).toBeVisible();
  }
});

test("the expanded catalogue filters by name and selects a detailed shape", async ({ page }) => {
  await page.goto("/");
  await page.getByText("More shapes, letters, and numbers").click();

  const filter = page.getByLabel("Filter options");
  await filter.fill("turtle");
  await expect(page.locator(".idea-filter")).toContainText("1 option");
  await expect(page.locator(".idea-catalog").getByRole("button")).toHaveCount(1);
  await page.getByRole("button", { name: "Turtle", exact: true }).click();
  await expect(page.getByLabel("Drawing and location")).toHaveValue(
    "a turtle run in Keszthely, about 14 km",
  );

  await filter.fill("not-a-shape");
  await expect(page.getByText("Nothing in the catalog")).toBeVisible();
  await expect(page.locator(".idea-catalog").getByRole("button")).toHaveCount(0);
});

test("a custom free-text drawing is submitted without catalog selection", async ({ page }) => {
  const capture = await mockGeneration(page);
  await page.goto("/");

  await page.getByLabel("Drawing and location").fill(
    "an octopus wearing a crown in Budapest, running, 12 km",
  );
  await page.getByRole("button", { name: "Find routes" }).click();

  await expect.poll(() => capture.lastPayload()).toEqual({
    prompt: "an octopus wearing a crown in Budapest, running, 12 km",
  });
});

test("mouse submission of an empty idea shows a persistent focused error", async ({ page }) => {
  await page.goto("/");
  const prompt = page.getByLabel("Drawing and location");
  await prompt.fill("   ");
  await page.getByRole("button", { name: "Find routes" }).click();

  await expect(prompt).toBeFocused();
  await expect(prompt).toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#prompt-error")).toContainText("Enter a route idea");
});

test("punctuation-only route ideas are identified beside the prompt", async ({ page }) => {
  await page.goto("/");
  const prompt = page.getByLabel("Drawing and location");
  await prompt.fill("!? ♥");
  await prompt.blur();

  await expect(prompt).toHaveAttribute("aria-errormessage", "prompt-error");
  await expect(page.locator("#prompt-error")).toHaveText(
    /Include a shape, word, letter, or number to draw/,
  );
  await expect(prompt).toHaveValue("!? ♥");
});

test("correcting a malformed route idea clears its error before submission", async ({ page }) => {
  await page.goto("/");
  const prompt = page.getByLabel("Drawing and location");
  await prompt.fill("!!!");
  await prompt.blur();
  await expect(page.locator("#prompt-error")).toBeVisible();

  await prompt.fill("letter A in Eger");
  await expect(page.locator("#prompt-error")).toHaveCount(0);
  await expect(prompt).toHaveAttribute("aria-invalid", "false");
  await expect(prompt).not.toHaveAttribute("aria-errormessage", /.+/);
});

test("running suggestions enforce both ends of the supported distance range", async ({ page }) => {
  await page.goto("/");
  await page.getByText("Choose city, activity, and distance").click();
  const distance = page.getByLabel("Distance");

  await expect(page.locator("#suggest-distance-help")).toHaveText("3–60 km for running.");
  await distance.fill("2");
  await distance.blur();
  await expect(page.locator("#suggest-distance-error")).toContainText("from 3 to 60 km");
  await distance.fill("61");
  await expect(page.locator("#suggest-distance-error")).toContainText("from 3 to 60 km");
  await distance.fill("60");
  await expect(page.locator("#suggest-distance-error")).toHaveCount(0);
});

test("suggestion distance distinguishes missing and fractional values", async ({ page }) => {
  const capture = await mockGeneration(page);
  await page.goto("/");
  await page.getByText("Choose city, activity, and distance").click();
  const distance = page.getByLabel("Distance");

  await distance.fill("");
  await page.getByRole("button", { name: "Find a route" }).click();
  await expect(page.locator("#suggest-distance-error")).toContainText(
    "Enter a distance in kilometres.",
  );
  expect(capture.requests).toHaveLength(0);

  await distance.fill("8.5");
  await expect(page.locator("#suggest-distance-error")).toContainText(
    "Enter the distance in whole kilometres.",
  );
  expect(capture.requests).toHaveLength(0);
});

test("a valid structured suggestion submits the selected city, activity, and distance", async ({
  page,
}) => {
  const capture = await mockGeneration(page);
  await page.goto("/");
  await page.getByText("Choose city, activity, and distance").click();
  await page.getByLabel("City").selectOption("Győr");
  await page.getByRole("radio", { name: "Running" }).check();
  await page.getByLabel("Distance").fill("12");
  await page.getByRole("button", { name: "Find a route" }).click();

  await expect.poll(() => capture.lastPayload()).toEqual({
    prompt: "suggest a run route in Győr, about 12 km",
  });
  await expect(page.getByLabel("Drawing and location")).toHaveValue(
    "suggest a run route in Győr, about 12 km",
  );
});

test("the major-city list submits a new Hungarian city without manual prompt editing", async ({
  page,
}) => {
  const capture = await mockGeneration(page);
  await page.goto("/");
  await page.getByText("Choose city, activity, and distance").click();

  const city = page.getByLabel("City");
  await expect(city.locator("option")).toHaveCount(230);
  await city.selectOption("Szolnok");
  await page.getByRole("radio", { name: "Cycling" }).check();
  await page.getByLabel("Distance").fill("24");
  await page.getByRole("button", { name: "Find a route" }).click();

  await expect.poll(() => capture.lastPayload()).toEqual({
    prompt: "suggest a bike route in Szolnok, about 24 km",
  });
  await expect(page.getByLabel("Drawing and location")).toHaveValue(
    "suggest a bike route in Szolnok, about 24 km",
  );
});

test("the expanded Europe group submits a newly catalogued accented destination", async ({ page }) => {
  const capture = await mockGeneration(page);
  await page.goto("/");
  await page.getByText("Choose city, activity, and distance").click();

  const city = page.getByLabel("City");
  await expect(city.locator('optgroup[label="Europe"] option')).toHaveCount(136);
  await expect(page.locator("#suggest-city-help")).toHaveCount(0);
  await city.selectOption("Timișoara");
  await page.getByRole("radio", { name: "Running" }).check();
  await page.getByLabel("Distance").fill("14");
  await page.getByRole("button", { name: "Find a route" }).click();

  await expect.poll(() => capture.lastPayload()).toEqual({
    prompt: "suggest a run route in Timișoara, about 14 km",
  });
  await expect(page.getByLabel("Drawing and location")).toHaveValue(
    "suggest a run route in Timișoara, about 14 km",
  );
});

test("the Balaton shore group submits a local accented settlement", async ({ page }) => {
  const capture = await mockGeneration(page);
  await page.goto("/");
  await page.getByText("Choose city, activity, and distance").click();

  const city = page.getByLabel("City");
  await expect(city.locator('optgroup[label="Lake Balaton shore"] option')).toHaveCount(44);
  await expect(city.locator('option[value="Siófok"]')).toHaveCount(1);
  await city.selectOption("Kővágóörs");
  await page.getByRole("radio", { name: "Cycling" }).check();
  await page.getByLabel("Distance").fill("22");
  await page.getByRole("button", { name: "Find a route" }).click();

  await expect.poll(() => capture.lastPayload()).toEqual({
    prompt: "suggest a bike route in Kővágóörs, about 22 km",
  });
  await expect(page.getByLabel("Drawing and location")).toHaveValue(
    "suggest a bike route in Kővágóörs, about 22 km",
  );
});

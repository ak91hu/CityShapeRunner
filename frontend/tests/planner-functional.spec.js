import { expect, test } from "playwright/test";

import { installCommonMocks, mockGeneration } from "./support/functional-fixtures.js";

test.beforeEach(async ({ page }) => {
  await installCommonMocks(page);
});

test("primary navigation links reach each planner section", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { level: 1, name: "Create GPS art on real streets" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Create route" })).toBeVisible();
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

test("the planner uses a compact responsive layout with optional panels collapsed", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page.locator(".image-reference-panel")).not.toHaveAttribute("open", "");
  await expect(page.locator(".suggest-panel")).not.toHaveAttribute("open", "");
  await expect(page.locator(".map-placement-panel")).not.toHaveAttribute("open", "");
  await expect(page.getByText("Other ways to start")).toBeVisible();
  const spacing = await page.locator(".generator-stage").evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      columnGap: Number.parseFloat(style.columnGap),
      paddingTop: Number.parseFloat(style.paddingTop),
      paddingBottom: Number.parseFloat(style.paddingBottom),
    };
  });

  expect(spacing.columnGap).toBeLessThanOrEqual(48);
  expect(spacing.paddingTop).toBeLessThanOrEqual(44);
  expect(spacing.paddingBottom).toBeLessThanOrEqual(44);
  const horizontalOverflow = await page.locator("body").evaluate(
    (element) => element.scrollWidth - element.clientWidth,
  );
  expect(horizontalOverflow).toBeLessThanOrEqual(1);
});

test("the header mark and favicon share one scalable route identity", async ({ page }) => {
  await page.goto("/");

  const home = page.getByRole("link", { name: "GPS Art Wizard home" });
  const mark = home.locator(".brand-mark");
  const markPath = await mark.locator("path").getAttribute("d");
  await expect(home).toHaveAttribute("href", "/");
  await expect(mark).toHaveAttribute("aria-hidden", "true");
  await expect(mark.locator("svg")).toHaveAttribute("viewBox", "0 0 48 48");
  await expect(mark.locator("rect")).toHaveCount(1);
  await expect(mark.locator("circle")).toHaveCount(2);
  await expect(page.locator(".brand-mark i")).toHaveCount(0);

  const faviconResponse = await page.request.get(new URL("/favicon.svg", page.url()).href);
  expect(faviconResponse.ok()).toBe(true);
  const favicon = await faviconResponse.text();
  const faviconPath = favicon.match(/<path d="([^"]+)"/)?.[1];
  const compactPath = (value) => value?.replace(/\s+/g, "");
  expect(compactPath(faviconPath)).toBe(compactPath(markPath));
  expect(favicon.match(/<circle\b/g)).toHaveLength(2);
});

test("alternative starts keep visual, DOM, and keyboard order aligned", async ({ page }) => {
  await page.goto("/");

  const prompt = page.getByLabel("Drawing and location");
  const initialPrompt = await prompt.inputValue();
  const mapPanel = page.locator(".map-placement-panel");
  const simplePanel = page.locator(".suggest-panel");
  const imagePanel = page.locator(".image-reference-panel");
  const mapSummary = mapPanel.locator(":scope > summary");
  const simpleSummary = simplePanel.locator(":scope > summary");
  const imageSummary = imagePanel.locator(":scope > summary");
  const domOrder = await page.evaluate(() => {
    const map = document.querySelector(".map-placement-panel");
    const simple = document.querySelector(".suggest-panel");
    const image = document.querySelector(".image-reference-panel");
    return Boolean(
      map
        && simple
        && (map.compareDocumentPosition(simple) & Node.DOCUMENT_POSITION_FOLLOWING)
        &&
      simple
        && image
        && (simple.compareDocumentPosition(image) & Node.DOCUMENT_POSITION_FOLLOWING),
    );
  });
  expect(domOrder).toBe(true);

  const mapBox = await mapPanel.boundingBox();
  const simpleBox = await simplePanel.boundingBox();
  const imageBox = await imagePanel.boundingBox();
  expect(mapBox).not.toBeNull();
  expect(simpleBox).not.toBeNull();
  expect(imageBox).not.toBeNull();
  expect(mapBox.y).toBeLessThan(simpleBox.y);
  expect(simpleBox.y).toBeLessThan(imageBox.y);

  await mapSummary.focus();
  await expect(mapSummary).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(simpleSummary).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(mapSummary).toBeFocused();
  await simpleSummary.focus();
  await expect(simpleSummary).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(imageSummary).toBeFocused();

  await simpleSummary.click();
  await expect(page.getByLabel("City", { exact: true })).toBeVisible();
  await simpleSummary.click();
  await imageSummary.click();
  await expect(page.getByLabel("Direct image URL")).toBeVisible();
  await expect(prompt).toHaveValue(initialPrompt);
  await expect(page.locator(".result, .loading-card")).toHaveCount(0);
});

test("a selected shape can be positioned on the map before street fitting", async ({ page }) => {
  await page.route("**/shape-templates", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        count: 2,
        shapes: [
          { id: "heart", label: "Heart" },
          { id: "star", label: "Star" },
        ],
      }),
    }),
  );
  await page.route("**/shape-placement-preview*", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        shape: "star",
        label: "Star",
        closed: true,
        paths: [[
          [0, 0.5], [0.12, 0.12], [0.48, 0.12], [0.2, -0.08],
          [0.3, -0.45], [0, -0.22], [-0.3, -0.45], [-0.2, -0.08],
          [-0.48, 0.12], [-0.12, 0.12], [0, 0.5],
        ]],
        city: "Budapest",
        city_substituted: false,
        center: [47.4979, 19.0402],
        city_bbox: [47.45, 47.56, 18.95, 19.15],
        scale_m: 2600,
        rotation_deg: 12,
        distance_km: 12,
        sport: "run",
      }),
    }),
  );
  const capture = await mockGeneration(page);
  await page.goto("/");

  await page.getByText("Place a shape on the map").click();
  const mapPanel = page.locator(".map-placement-panel");
  await mapPanel.getByLabel("Shape").selectOption("star");
  await mapPanel.getByLabel("Target distance", { exact: true }).fill("12");
  await mapPanel.getByRole("button", { name: "Open placement map" }).click();

  const dialog = page.getByRole("dialog", { name: "Position the star" });
  await expect(dialog).toBeVisible();
  await expect(dialog.locator(".shape-placement-outline")).toHaveCount(1);
  await dialog.getByLabel("Footprint size").fill("3000");
  await dialog.getByLabel("Rotation").fill("45");
  await dialog.getByLabel("Nearby fine-tuning").fill("700");
  await dialog.getByRole("button", { name: "Fit to streets and create GPX" }).click();

  await expect(page.locator(".result")).toBeVisible();
  await expect.poll(() => capture.lastPayload()).toMatchObject({
    prompt: "star in Budapest, running, about 12 km",
    map_placement: {
      center_lat: 47.4979,
      center_lon: 19.0402,
      scale_m: 3000,
      rotation_deg: 45,
      search_radius_m: 700,
    },
  });
  expect(capture.lastPayload().start_point).toBeUndefined();
  expect(capture.lastPayload().start_address).toBeUndefined();
});

test("primary planner controls keep a 44 pixel activation floor", async ({ page }) => {
  await page.goto("/");

  const controls = page.locator([
    ".brand",
    ".site-header nav a",
    ".idea-chip",
    ".generate-button",
    ".suggest-panel > summary",
    ".image-reference-panel > summary",
  ].join(", "));
  const visibleBoxes = [];
  for (const control of await controls.all()) {
    if (await control.isVisible()) visibleBoxes.push(await control.boundingBox());
  }
  expect(visibleBoxes.length).toBeGreaterThan(8);
  for (const box of visibleBoxes) {
    expect(box).not.toBeNull();
    expect(box.width).toBeGreaterThanOrEqual(44);
    expect(box.height).toBeGreaterThanOrEqual(44);
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

test("the full idea catalogue exposes every category and all 158 options", async ({ page }) => {
  await page.goto("/");
  await page.getByText("More shapes, letters, and numbers").click();

  await expect(page.locator(".idea-catalog").getByRole("button")).toHaveCount(158);
  for (const category of [
    "Hungarian ideas",
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

test("bug is submitted as a shape without exposing a letter B interpretation", async ({ page }) => {
  const capture = await mockGeneration(page);
  let interpretationRequests = 0;
  await page.route("**/interpret", async (route) => {
    interpretationRequests += 1;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
  await page.goto("/");

  const prompt = page.getByLabel("Drawing and location");
  await prompt.fill("a bug run in Tatabánya, about 8 km");
  await expect(page.getByText("Live understanding")).toHaveCount(0);
  await expect(page.getByText("Letter B", { exact: true })).toHaveCount(0);
  expect(capture.requests).toHaveLength(0);

  await page.getByRole("button", { name: "Find routes" }).click();
  await expect.poll(() => capture.lastPayload()).toEqual({
    prompt: "a bug run in Tatabánya, about 8 km",
  });
  expect(interpretationRequests).toBe(0);
});

test("optional start point, direction, and route preferences reach generation", async ({ page }) => {
  const capture = await mockGeneration(page);
  await page.goto("/");
  await page.getByLabel("Drawing and location").fill("a heart run in Tatabánya, about 8 km");

  await page.getByText("Start point, direction, and route preferences", { exact: true }).click();
  await page.getByLabel("Start address or place").fill("Hősök tere, Budapest");
  await page.getByLabel("Preferred first direction").selectOption("90");
  await page.getByRole("checkbox", { name: "Avoid steps" }).check();
  await page.getByRole("checkbox", { name: "Prefer greener streets (running)" }).check();
  await page.getByRole("button", { name: "Find routes" }).click();

  await expect.poll(() => capture.lastPayload()).toEqual({
    prompt: "a heart run in Tatabánya, about 8 km",
    start_address: "Hősök tere, Budapest",
    start_direction_deg: 90,
    route_preferences: {
      avoid_steps: true,
      avoid_ferries: false,
      avoid_fords: false,
      prefer_quiet: false,
      prefer_green: true,
    },
  });
});

test("request check confirms interpretation without starting route generation", async ({ page }) => {
  const capture = await mockGeneration(page);
  await page.route("**/interpret", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        prompt: "a heart run in Budapest, about 8 km",
        intent: { shape: "heart", city: "Budapest", sport: "run", distance_km: 8 },
        drawing_label: "heart",
        drawing_kind: "template",
        defaults_applied: [],
        confidence: { drawing: 1, city: 1, sport: 1, distance: 1 },
        needs_clarification: false,
        clarifications: [],
      }),
    }),
  );
  await page.goto("/");

  await page.getByRole("button", { name: "Preview request" }).click();

  const check = page.locator(".request-check-result");
  await expect(check).toContainText("We’ll plan heart");
  await expect(check).toContainText("Budapest");
  await expect(check).toContainText("8 km");
  expect(capture.requests).toHaveLength(0);
});

test("current location replaces an entered address and reaches generation", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: {
        getCurrentPosition(success) {
          success({ coords: { latitude: 47.497913, longitude: 19.040236 } });
        },
      },
    });
  });
  const capture = await mockGeneration(page);
  await page.goto("/");
  await page.getByText("Start point, direction, and route preferences", { exact: true }).click();
  await page.getByLabel("Start address or place").fill("Hősök tere, Budapest");

  await page.getByRole("button", { name: "Use current location" }).click();

  await expect(page.getByLabel("Start address or place")).toHaveValue("");
  await expect(page.getByText("Current location selected for this request only.")).toBeVisible();
  await page.getByRole("button", { name: "Find routes" }).click();
  await expect.poll(() => capture.lastPayload()).toEqual({
    prompt: "a heart run in Budapest, about 8 km",
    start_point: {
      latitude: 47.497913,
      longitude: 19.040236,
      label: "Current location",
    },
  });
});

test("a supported image link can generate an AI route in a selected city", async ({ page }) => {
  const capture = await mockGeneration(page);
  await page.goto("/");

  const imagePanel = page.locator(".image-reference-panel");
  await imagePanel.getByText("Use an image link").click();
  await imagePanel.getByLabel("Direct image URL").fill(
    "https://www.premiumsvg.com/wimg1/mug-icon.webp",
  );
  await imagePanel.getByLabel("Destination").selectOption("Pécs");
  await imagePanel.getByLabel("Travel mode").selectOption("bike");
  await imagePanel.getByLabel("Length").fill("24");
  await imagePanel.getByRole("button", { name: "Generate AI route" }).click();

  await expect.poll(() => capture.lastPayload()).toEqual({
    prompt: "a custom image in Pécs, cycling, about 24 km",
    reference_image_url: "https://www.premiumsvg.com/wimg1/mug-icon.webp",
  });
  await expect(page.getByLabel("Drawing and location")).toHaveValue(
    "a custom image in Pécs, cycling, about 24 km",
  );
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
  const distance = page.getByLabel("Distance", { exact: true });

  await expect(page.locator("#suggest-distance-help")).toHaveText("3 to 60 km for running.");
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
  const distance = page.getByLabel("Distance", { exact: true });

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
  await page.getByLabel("City", { exact: true }).selectOption("Győr");
  await page.getByRole("radio", { name: "Running" }).check();
  await page.getByLabel("Distance", { exact: true }).fill("12");
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

  const city = page.getByLabel("City", { exact: true });
  await expect(city.locator("option")).toHaveCount(230);
  await city.selectOption("Szolnok");
  await page.getByRole("radio", { name: "Cycling" }).check();
  await page.getByLabel("Distance", { exact: true }).fill("24");
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

  const city = page.getByLabel("City", { exact: true });
  await expect(city.locator('optgroup[label="Europe"] option')).toHaveCount(136);
  await expect(page.locator("#suggest-city-help")).toHaveCount(0);
  await city.selectOption("Timișoara");
  await page.getByRole("radio", { name: "Running" }).check();
  await page.getByLabel("Distance", { exact: true }).fill("14");
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

  const city = page.getByLabel("City", { exact: true });
  await expect(city.locator('optgroup[label="Lake Balaton shore"] option')).toHaveCount(44);
  await expect(city.locator('option[value="Siófok"]')).toHaveCount(1);
  await city.selectOption("Kővágóörs");
  await page.getByRole("radio", { name: "Cycling" }).check();
  await page.getByLabel("Distance", { exact: true }).fill("22");
  await page.getByRole("button", { name: "Find a route" }).click();

  await expect.poll(() => capture.lastPayload()).toEqual({
    prompt: "suggest a bike route in Kővágóörs, about 22 km",
  });
  await expect(page.getByLabel("Drawing and location")).toHaveValue(
    "suggest a bike route in Kővágóörs, about 22 km",
  );
});

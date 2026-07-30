import { expect, test } from "playwright/test";

const transparentTile = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

test.beforeEach(async ({ page }) => {
  await page.route("https://*.tile.openstreetmap.org/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/png",
      body: transparentTile,
    }),
  );
});

const successfulRoute = {
  prompt: "a star bike route in Debrecen, about 20 km",
  intent: {
    shape: "star",
    text: null,
    city: "Debrecen",
    sport: "bike",
    distance_km: 20,
    style: null,
  },
  shape: { name: "star", closed: true, source: "template", n_paths: 1 },
  suggested_shape: null,
  validation: {
    score: 0.91,
    closure: 0.99,
    distance_fit: 0.96,
    shape_fidelity: 0.87,
    issues: [],
    on_roads: true,
    coverage_similarity: 0.89,
    turning_similarity: 0.86,
    length_similarity: 0.91,
    extent_similarity: 0.94,
    route_length_ratio: 1.04,
  },
  distance_km: 19.82,
  snapped: true,
  iterations: 1,
  candidate_count: 2,
  preflight_count: 164,
  below_threshold: false,
  errors: [],
  history: [
    {
      iteration: 1,
      score: 0.91,
      delta_vs_best: 0.08,
      fidelity: 0.87,
      distance_fit: 0.96,
    },
  ],
  gpx: "<?xml version=\"1.0\"?><gpx version=\"1.1\"></gpx>",
  tcx: "<?xml version=\"1.0\"?><TrainingCenterDatabase></TrainingCenterDatabase>",
  file_paths: {},
  points_preview: [
    [47.5316, 21.6273],
    [47.538, 21.642],
    [47.523, 21.635],
    [47.5316, 21.6273],
  ],
  ideal_preview: [
    [47.5316, 21.6273],
    [47.537, 21.641],
    [47.524, 21.634],
    [47.5316, 21.6273],
  ],
};
successfulRoute.candidates = [
  {
    id: "candidate-1",
    shape_name: "star",
    shape_source: "template",
    points_preview: successfulRoute.points_preview,
    ideal_preview: successfulRoute.ideal_preview,
    distance_km: 19.82,
    snapped: true,
    closed: true,
    target_distance_km: 20,
    validation: successfulRoute.validation,
    below_recommended: false,
  },
  {
    id: "candidate-2",
    shape_name: "star",
    shape_source: "template",
    points_preview: successfulRoute.points_preview.map(([lat, lon], index) => [
      lat + index * 0.0001,
      lon,
    ]),
    ideal_preview: successfulRoute.ideal_preview,
    distance_km: 20.31,
    snapped: true,
    closed: true,
    target_distance_km: 20,
    validation: {
      ...successfulRoute.validation,
      score: 0.78,
      shape_fidelity: 0.73,
    },
    below_recommended: false,
  },
];

async function mockHealth(page, ok = true) {
  await page.route("**/health", (route) =>
    route.fulfill({
      status: ok ? 200 : 503,
      contentType: "application/json",
      body: JSON.stringify(ok ? { status: "ok" } : { detail: "Unavailable" }),
    }),
  );
}

async function mockGenerate(page, handler) {
  await page.route("**/generate", handler);
}

test("designer controls are accessible and fit a narrow viewport", async ({ page }) => {
  await mockHealth(page);
  await page.goto("/");

  await expect(page).toHaveTitle(/GPS Art Wizard/);
  await expect(
    page.getByRole("heading", { level: 1, name: /Turn your route into a drawing/ }),
  ).toBeVisible();
  await expect(page.getByLabel("Describe your idea")).toBeVisible();
  await expect(page.getByLabel("Describe your idea")).toBeFocused();
  await expect(page.getByText("Planner online")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Find matching routes" })).toBeEnabled();
  await page.getByText("Not sure what fits? Let the planner choose").click();
  await expect(page.getByLabel("City")).toBeVisible();
  await expect(page.getByLabel("Activity")).toBeVisible();
  await expect(page.getByLabel("Distance")).toBeVisible();
  await expect(page.getByRole("button", { name: "Choose an idea and find routes" })).toBeVisible();
  await expect(page.getByLabel("City").locator('option[value="Miskolc"]')).toHaveCount(1);
  await expect(page.getByLabel("City").locator('option[value="Eger"]')).toHaveCount(1);
  await page.getByText("Browse all 32 quick ideas").click();
  await expect(page.locator(".idea-catalog").getByRole("button")).toHaveCount(32);
  await expect(page.getByRole("button", { name: "Letter A" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Number 42" })).toBeVisible();

  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);

  for (const element of await page.locator("button:visible, input:visible, select:visible, textarea:visible").all()) {
    const box = await element.boundingBox();
    expect(box, "every interactive control should have a rendered box").not.toBeNull();
    expect(box.x, "control should not start outside the viewport").toBeGreaterThanOrEqual(0);
    expect(
      box.x + box.width,
      "control should not extend beyond the viewport",
    ).toBeLessThanOrEqual((await page.viewportSize()).width + 1);
  }
});

test("quick idea generation sends the prompt and renders a usable routed result", async ({
  page,
}) => {
  await mockHealth(page);
  let requestPayload;
  await mockGenerate(page, async (route) => {
    requestPayload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(successfulRoute),
    });
  });
  await page.goto("/");

  await page.getByRole("button", { name: "Star" }).click();
  await expect(page.getByLabel("Describe your idea")).toHaveValue(successfulRoute.prompt);
  await page.getByRole("button", { name: "Find matching routes" }).click();

  await expect(page.getByRole("heading", { name: "Star in Debrecen" })).toBeVisible();
  expect(requestPayload).toEqual({ prompt: successfulRoute.prompt });
  await expect(page.locator(".route-state")).toContainText("Validated street route");
  await expect(
    page.locator(".metric").filter({ hasText: "Route quality" }).locator("dd:not(.metric-detail)"),
  ).toHaveText("91%");
  await expect(
    page
      .locator(".metric")
      .filter({ hasText: "Distance" })
      .first()
      .locator("dd:not(.metric-detail)"),
  ).toHaveText("19.82 km");
  await expect(
    page.locator(".metric").filter({ hasText: "Full routes" }).locator(".metric-detail"),
  ).toHaveText("164 placements screened first");
  await expect(page.getByRole("region", { name: /Star street-route map/ })).toBeVisible();
  await expect(page.getByLabel("Generated route")).toHaveValue("candidate-1");
  await expect(page.getByLabel("Generated route").locator("option")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Download candidate GPX" })).toBeEnabled();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download candidate GPX" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("star-debrecen.gpx");
});

test("smart suggestion validates inputs and submits the selected city, activity, and distance", async ({
  page,
}) => {
  await mockHealth(page);
  let submittedPrompt = "";
  await mockGenerate(page, async (route) => {
    submittedPrompt = route.request().postDataJSON().prompt;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...successfulRoute,
        prompt: submittedPrompt,
        suggested_shape: "star",
      }),
    });
  });
  await page.goto("/");

  await page.getByText("Not sure what fits? Let the planner choose").click();
  await page.getByLabel("City").selectOption("Pécs");
  await page.getByLabel("Activity").selectOption("bike");
  await page.getByLabel("Distance").fill("25");
  await page.getByRole("button", { name: "Choose an idea and find routes" }).click();

  await expect.poll(() => submittedPrompt).toBe("suggest a bike route in Pécs, about 25 km");
  await expect(page.getByLabel("Describe your idea")).toHaveValue(submittedPrompt);
  await expect(page.getByText("Street-friendly suggestion")).toBeVisible();
});

test("API failures show a focused actionable error and allow retry", async ({ page }) => {
  await mockHealth(page);
  let attempts = 0;
  await mockGenerate(page, async (route) => {
    attempts += 1;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Road routing is temporarily unavailable." }),
    });
  });
  await page.goto("/");

  await page.getByRole("button", { name: "Find matching routes" }).click();

  const alert = page.getByRole("alert");
  await expect(alert).toBeVisible();
  await expect(alert).toBeFocused();
  await expect(alert).toContainText("Road routing is temporarily unavailable.");
  await expect(page.getByRole("button", { name: "Try this idea again" })).toBeVisible();

  await page.getByRole("button", { name: "Try this idea again" }).click();
  await expect.poll(() => attempts).toBe(2);
});

test("a straight-line fallback is retained, editable, and exported with warnings", async ({
  page,
}) => {
  await mockHealth(page);
  await mockGenerate(page, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...successfulRoute,
        snapped: false,
        below_threshold: true,
        validation: {
          ...successfulRoute.validation,
          score: 0.42,
          on_roads: false,
          issues: ["Route is not matched to the road network."],
        },
        candidates: successfulRoute.candidates.map((candidate) => ({
          ...candidate,
          snapped: false,
          below_recommended: true,
          validation: {
            ...candidate.validation,
            score: 0.42,
            on_roads: false,
            issues: ["Route is not matched to the road network."],
          },
        })),
      }),
    }),
  );
  await page.goto("/");

  await page.getByRole("button", { name: "Find matching routes" }).click();

  await expect(page.getByText("Preview only")).toBeVisible();
  await expect(
    page.getByRole("region", { name: /drawing preview.*not matched to streets/i }),
  ).toBeVisible();
  await expect(page.getByText("Drawing preview — not matched to streets")).toBeVisible();
  await expect(page.getByText("Manual review required")).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit this route" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Download candidate GPX" })).toBeEnabled();
});

test("a measured fallback explains why it replaced the requested drawing", async ({ page }) => {
  await mockHealth(page);
  await mockGenerate(page, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...successfulRoute,
        requested_shape: "cat",
        shape: { name: "diamond", closed: true, source: "template", n_paths: 1 },
        suggested_shape: "diamond",
        fit_decision: {
          requested_shape: "cat",
          selected_shape: "diamond",
          substituted: true,
          requested_score: 0.46,
          requested_fidelity: 0.41,
          selected_score: 0.84,
          selected_fidelity: 0.82,
          candidates_tested: ["triangle", "diamond"],
          reasons: [
            "The best requested-shape candidate preserved 41% of the recognisable silhouette; the required minimum is 70%.",
            "Diamond passed every quality gate on real streets.",
          ],
        },
        candidates: successfulRoute.candidates.map((candidate) => ({
          ...candidate,
          shape_name: "diamond",
        })),
      }),
    }),
  );
  await page.goto("/");

  await page.getByRole("button", { name: "Find matching routes" }).click();

  await expect(page.getByRole("heading", { name: "Diamond in Debrecen" })).toBeVisible();
  await expect(page.getByText("Cat did not fit — using Diamond")).toBeVisible();
  await expect(page.getByText(/preserved 41%/)).toBeVisible();
  await expect(page.getByText("Alternatives measured: Triangle, Diamond.")).toBeVisible();
  await expect(page.getByText("Validated street route")).toBeVisible();
});

test("the online editor reroutes control points and downloads the edited GPX", async ({
  page,
}) => {
  await mockHealth(page);
  await mockGenerate(page, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(successfulRoute),
    }),
  );
  let editPayload;
  await page.route("**/edit-route", async (route) => {
    editPayload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        request_id: "edit-1",
        points_preview: successfulRoute.points_preview,
        distance_km: 19.9,
        snapped: true,
        below_recommended: false,
        validation: successfulRoute.validation,
        gpx: "<?xml version=\"1.0\"?><gpx><trk><name>Edited</name></trk></gpx>",
        tcx: null,
        warnings: [],
      }),
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Find matching routes" }).click();

  await page.getByRole("button", { name: "Edit this route" }).click();
  await expect(page.locator(".route-edit-marker")).toHaveCount(4);
  await page.getByRole("button", { name: "Update street route" }).click();

  await expect.poll(() => editPayload?.control_points?.length).toBe(4);
  await expect(page.getByText(/Edited route ready: 19.90 km/)).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download edited GPX" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("star-debrecen.gpx");
});

import { expect, test } from "playwright/test";

const transparentTile = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

test.beforeEach(async ({ page }) => {
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/png",
      headers: { "Access-Control-Allow-Origin": "*" },
      body: transparentTile,
    }),
  );
  await page.route("https://res.cloudinary.com/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/png",
      body: transparentTile,
    }),
  );
  await page.route("**/gallery*", (route) => {
    const requestUrl = new URL(route.request().url());
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ configured: true, assets: [], next_cursor: null }),
      });
    }
    if (requestUrl.pathname.endsWith("/gallery/delete")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ removed: true }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        asset: {
          id: `gps-art-gallery/${"a".repeat(32)}`,
          image_url: "https://res.cloudinary.com/demo/image/upload/gallery-map.png",
          width: 900,
          height: 600,
        },
        removal_token: "b".repeat(64),
      }),
    });
  });
  await page.route("**/route-acceptance", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ recorded: true }),
    }),
  );
});

function buildVerification(validation, shapeName = "star") {
  const numericGate = (key, label, value, minimum, group = "shape") => ({
    key,
    label,
    value,
    minimum,
    group,
    applies: true,
    passed: value >= minimum,
    description: `${label} is checked independently.`,
  });
  const gates = [
    {
      key: "selected_shape",
      label: "Selected shape",
      value: shapeName,
      minimum: shapeName,
      group: "shape",
      applies: true,
      passed: true,
      description: "The candidate belongs to the selected shape.",
    },
    {
      key: "road_network",
      label: "Connected street route",
      value: validation.on_roads,
      minimum: true,
      group: "route",
      applies: true,
      passed: validation.on_roads,
      description: "The line follows connected streets.",
    },
    numericGate("overall_score", "Overall route quality", validation.score, 0.72, "route"),
    numericGate("shape_fidelity", "Combined shape likeness", validation.shape_fidelity, 0.7),
    numericGate("spatial_similarity", "Ordered curve match", validation.spatial_similarity, 0.7),
    numericGate("coverage_similarity", "Outline coverage", validation.coverage_similarity, 0.7),
    numericGate("turning_similarity", "Characteristic turns", validation.turning_similarity, 0.7),
    numericGate("landmark_similarity", "Salient landmarks", validation.landmark_similarity, 0.7),
    numericGate("length_similarity", "Detour control", validation.length_similarity, 0.7),
    numericGate("extent_similarity", "Width / height preservation", validation.extent_similarity, 0.7),
    numericGate("distance_fit", "Target-distance accuracy", validation.distance_fit, 0.6, "usability"),
    numericGate("closure", "Loop closure", validation.closure, 0.6, "usability"),
  ];
  const failed = gates.filter((gate) => !gate.passed).map((gate) => gate.key);
  return {
    passed: failed.length === 0,
    shape_following: gates.filter((gate) => gate.group === "shape").every((gate) => gate.passed),
    passed_count: gates.length - failed.length,
    required_count: gates.length,
    failed_gates: failed,
    gates,
    thresholds: { overall_score: 0.72, shape: 0.7, usability: 0.6 },
  };
}

function buildRouteDetails(validation, distanceKm = 19.82) {
  return {
    shape: { name: "star", source: "template", closed: true },
    routing: {
      activity: "bike",
      street_matched: validation.on_roads,
      route_point_count: 842,
      guide_point_count: 401,
      closure_gap_m: 3.4,
    },
    distance: {
      actual_km: distanceKm,
      target_km: 20,
      difference_km: distanceKm - 20,
      difference_percent: ((distanceKm - 20) / 20) * 100,
      route_to_guide_ratio: validation.route_length_ratio,
    },
    deviation: { mean_outline_deviation_ratio: 0.07 },
    placement: {
      rotation_deg: 18,
      scale_m: 3_200,
      lat_offset_m: 1_500,
      lon_offset_m: -750,
      preflight_score: 0.83,
    },
  };
}

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
    spatial_similarity: 0.9,
    coverage_similarity: 0.89,
    turning_similarity: 0.86,
    landmark_similarity: 0.88,
    length_similarity: 0.91,
    extent_similarity: 0.94,
    route_length_ratio: 1.04,
    mean_deviation_ratio: 0.07,
    closure_gap_m: 3.4,
    actual_distance_km: 19.82,
    target_distance_km: 20,
    route_point_count: 842,
    guide_point_count: 401,
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
  gallery_publish_token: "top-level-gallery-token",
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
  landmark_preview: [
    [47.5316, 21.6273],
    [47.537, 21.641],
    [47.524, 21.634],
  ],
};
successfulRoute.route_verification = buildVerification(successfulRoute.validation);
successfulRoute.route_details = buildRouteDetails(successfulRoute.validation);
successfulRoute.candidate_summary = {
  selected_shape: "star",
  accepted_count: 2,
  verified_count: 2,
  review_count: 0,
  shown_count: 2,
  rejected_selected_shape_count: 0,
  other_shape_count: 0,
  audited_count: 2,
  full_route_attempt_count: 2,
  preflight_count: 164,
};
successfulRoute.candidates = [
  {
    id: "candidate-1",
    shape_name: "star",
    shape_source: "template",
    points_preview: successfulRoute.points_preview,
    ideal_preview: successfulRoute.ideal_preview,
    landmark_preview: successfulRoute.landmark_preview,
    distance_km: 19.82,
    snapped: true,
    closed: true,
    target_distance_km: 20,
    validation: successfulRoute.validation,
    below_recommended: false,
    verification: successfulRoute.route_verification,
    details: successfulRoute.route_details,
    gpx: successfulRoute.gpx,
    tcx: successfulRoute.tcx,
    gallery_publish_token: `candidate-1-gallery-token`,
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
    landmark_preview: successfulRoute.landmark_preview,
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
    verification: buildVerification({
      ...successfulRoute.validation,
      score: 0.78,
      shape_fidelity: 0.73,
    }),
    details: buildRouteDetails(successfulRoute.validation, 20.31),
    gpx: successfulRoute.gpx,
    tcx: successfulRoute.tcx,
    gallery_publish_token: `candidate-2-gallery-token`,
  },
];
successfulRoute.candidate_audit = successfulRoute.candidates.map((candidate) => ({
  id: candidate.id,
  shape_name: candidate.shape_name,
  selected_shape_match: true,
  accepted: true,
  verified: true,
  decision: "verified",
  failed_gates: [],
  score: candidate.validation.score,
  shape_fidelity: candidate.validation.shape_fidelity,
  distance_km: candidate.distance_km,
  issues: [],
}));

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
    page.getByRole("heading", { level: 1, name: /Create GPS art on real streets/ }),
  ).toBeVisible();
  await expect(page.getByLabel("Drawing and location")).toBeVisible();
  await expect(page.getByLabel("Drawing and location")).toBeFocused();
  await expect(page.getByText("Planner online")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Find routes" })).toBeEnabled();
  await page.getByText("Choose city, activity, and distance").click();
  await expect(page.getByLabel("City")).toBeVisible();
  await expect(page.getByRole("group", { name: "Activity" })).toBeVisible();
  await expect(page.getByLabel("Distance")).toBeVisible();
  const suggestionButton = page.getByRole("button", { name: "Find a route" });
  await expect(suggestionButton).toBeVisible();
  await expect(
    page.getByText("We compare up to three shapes suited to these streets and this distance."),
  ).toBeVisible();
  const fieldsBox = await page.locator(".suggest-fields").boundingBox();
  const actionsBox = await page.locator(".suggest-actions").boundingBox();
  const suggestionButtonBox = await suggestionButton.boundingBox();
  expect(fieldsBox).not.toBeNull();
  expect(actionsBox).not.toBeNull();
  expect(suggestionButtonBox).not.toBeNull();
  expect(actionsBox.y).toBeGreaterThanOrEqual(fieldsBox.y + fieldsBox.height);
  expect(suggestionButtonBox.y).toBeGreaterThanOrEqual(actionsBox.y);
  if ((await page.viewportSize()).width <= 608) {
    expect(suggestionButtonBox.width).toBeGreaterThanOrEqual(actionsBox.width - 1);
  } else {
    expect(suggestionButtonBox.x + suggestionButtonBox.width).toBeGreaterThanOrEqual(
      actionsBox.x + actionsBox.width - 1,
    );
  }
  for (const option of await page.locator(".activity-option").all()) {
    const box = await option.boundingBox();
    expect(box).not.toBeNull();
    expect(box.height).toBeGreaterThanOrEqual(44);
  }
  await expect(page.getByLabel("City").locator('option[value="Miskolc"]')).toHaveCount(1);
  await expect(page.getByLabel("City").locator('option[value="Eger"]')).toHaveCount(1);
  await expect(page.getByLabel("City").locator("option")).toHaveCount(230);
  await expect(page.getByLabel("City").locator("optgroup")).toHaveCount(3);
  await expect(page.getByLabel("City").locator('optgroup[label="Hungary"] option')).toHaveCount(50);
  await expect(
    page.getByLabel("City").locator('optgroup[label="Lake Balaton shore"] option'),
  ).toHaveCount(44);
  await expect(page.getByLabel("City").locator('optgroup[label="Europe"] option')).toHaveCount(136);
  const cityValues = await page
    .getByLabel("City")
    .locator("option")
    .evaluateAll((options) => options.map((option) => option.value));
  expect(new Set(cityValues).size).toBe(230);
  await expect(page.getByLabel("City").locator('option[value="Érd"]')).toHaveCount(1);
  await expect(page.getByLabel("City").locator('option[value="Szolnok"]')).toHaveCount(1);
  await expect(
    page.getByLabel("City").locator('option[value="Szigetszentmiklós"]'),
  ).toHaveCount(1);
  await expect(page.getByLabel("City").locator('option[value="Tata"]')).toHaveCount(1);
  await expect(page.getByLabel("City").locator('option[value="Stockholm"]')).toHaveCount(1);
  await expect(page.getByLabel("City").locator('option[value="Kraków"]')).toHaveCount(1);
  await expect(page.getByLabel("City").locator('option[value="Timișoara"]')).toHaveCount(1);
  await page.getByText("More shapes, letters, and numbers").click();
  await expect(page.locator(".idea-catalog").getByRole("button")).toHaveCount(158);
  await expect(page.getByRole("button", { name: "Letter A" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Robot" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Paprika" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Number 42" })).toBeVisible();
  const catalogGlyphs = await page
    .locator('.idea-catalog .idea-chip span[aria-hidden="true"]')
    .allTextContents();
  expect(new Set(catalogGlyphs).size).toBe(catalogGlyphs.length);
  await expect(page.getByRole("button", { name: "Cat", exact: true }).locator("span")).toHaveText("🐈");
  await expect(page.getByRole("button", { name: "Dog", exact: true }).locator("span")).toHaveText("🐕");
  await expect(page.getByRole("button", { name: "Bird", exact: true }).locator("span")).toHaveText("🐦");
  await expect(page.getByRole("button", { name: "Bat", exact: true }).locator("span")).toHaveText("🦇");

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
  await expect(page.getByLabel("Drawing and location")).toHaveValue(successfulRoute.prompt);
  await page.getByRole("button", { name: "Find routes" }).click();

  await expect(page.getByRole("heading", { name: "Star in Debrecen" })).toBeVisible();
  expect(requestPayload).toEqual({ prompt: successfulRoute.prompt });
  await expect(page.locator(".route-state")).toContainText("Ready to download");
  await expect(
    page.locator(".metric").filter({ hasText: "Overall match" }).locator("dd:not(.metric-detail)"),
  ).toHaveText("91%");
  await expect(
    page
      .locator(".metric")
      .filter({ has: page.locator("dt", { hasText: /^Distance$/ }) })
      .first()
      .locator("dd:not(.metric-detail)"),
  ).toHaveText("19.82 km");
  await expect(
    page.locator(".metric").filter({ hasText: "Route options" }).locator(".metric-detail"),
  ).toHaveText("2 ready · 0 review · 164 locations");
  await expect(page.getByRole("region", { name: /Star street-route map/ })).toBeVisible();
  await expect(page.locator(".route-landmark-marker")).toHaveCount(3);
  await expect(page.locator('.candidate-card[data-candidate-id="candidate-1"]')).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.locator(".candidate-card")).toHaveCount(2);
  await expect(page.getByText("Checks passed")).toBeVisible();
  await expect(page.locator(".verification-heading")).toContainText("12 of 12 passed · show details");
  await expect(
    page.locator(".gate-list").getByText("Line order", { exact: true }),
  ).toBeHidden();
  await page.locator(".verification-heading").click();
  await expect(
    page.locator(".gate-list").getByText("Line order", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Higher scores mean a closer match to the drawing/)).toBeVisible();
  await expect(page.getByText("Route details", { exact: true })).toBeVisible();
  await page.getByText("Route details", { exact: true }).click();
  await expect(page.locator(".route-facts")).toContainText("842 / 401");
  await expect(page.locator(".route-facts")).toContainText("19.82 km / 20.00 km");
  await expect(page.getByText("Routes tested")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeEnabled();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download GPX", exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("star-debrecen.gpx");

  await page.setViewportSize({ width: 900, height: 900 });
  const mapBox = await page.locator(".map-card").boundingBox();
  const exportBox = await page.locator(".route-output .export-card").boundingBox();
  expect(mapBox).not.toBeNull();
  expect(exportBox).not.toBeNull();
  expect(exportBox.y).toBeGreaterThan(mapBox.y);
  expect(exportBox.x).toBeGreaterThanOrEqual(mapBox.x);
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

  await page.getByText("Choose city, activity, and distance").click();
  await page.getByLabel("City").selectOption("Pécs");
  await page.getByRole("radio", { name: "Cycling" }).check();
  await page.getByLabel("Distance").fill("25");
  await page.getByRole("button", { name: "Find a route" }).click();

  await expect.poll(() => submittedPrompt).toBe("suggest a bike route in Pécs, about 25 km");
  await expect(page.getByLabel("Drawing and location")).toHaveValue(submittedPrompt);
  await expect(page.getByText("Suggested shape")).toBeVisible();
});

test("API failures show a focused actionable error and allow retry", async ({ page }) => {
  await mockHealth(page);
  let attempts = 0;
  await mockGenerate(page, async (route) => {
    attempts += 1;
    if (attempts === 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        headers: {
          "X-Request-ID": "routing-503-test",
          "Retry-After": "5",
        },
        body: JSON.stringify({ detail: "Road routing is temporarily unavailable." }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(successfulRoute),
    });
  });
  await page.goto("/");

  await page.getByRole("button", { name: "Find routes" }).click();

  const alert = page.getByRole("alert");
  await expect(alert).toBeVisible();
  await expect(alert).toBeFocused();
  await expect(
    alert.getByRole("heading", { name: "Route planner temporarily unavailable" }),
  ).toBeVisible();
  await expect(alert).toContainText("Road routing is temporarily unavailable.");
  await expect(alert).toContainText("Your route idea is still here");
  await expect(alert).toContainText("waiting 5 seconds");
  await expect(alert).toContainText("routing-503-test");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();

  await page.getByRole("button", { name: "Try again" }).click();
  await expect.poll(() => attempts).toBe(2);
  await expect(page.getByRole("heading", { name: "Star in Debrecen" })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByLabel("Drawing and location")).toHaveValue(
    "a heart run in Budapest, about 8 km",
  );
});

test("a straight-line preview cannot be accepted or exported", async ({
  page,
}) => {
  await mockHealth(page);
  await mockGenerate(page, (route) => {
    const failedValidation = {
      ...successfulRoute.validation,
      score: 0.42,
      shape_fidelity: 0.3,
      distance_fit: 0.4,
      on_roads: false,
      issues: ["Route is not matched to the road network."],
    };
    const reviewVerification = buildVerification(failedValidation);
    const reviewCandidate = {
      ...successfulRoute.candidates[0],
      snapped: false,
      below_recommended: true,
      validation: failedValidation,
      verification: reviewVerification,
      verification_status: "review",
      requires_user_acceptance: true,
      details: buildRouteDetails(failedValidation),
    };
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...successfulRoute,
        snapped: false,
        below_threshold: true,
        validation: failedValidation,
        route_verification: reviewVerification,
        route_details: buildRouteDetails(failedValidation),
        candidate_summary: {
          ...successfulRoute.candidate_summary,
          accepted_count: 0,
          verified_count: 0,
          review_count: 1,
          shown_count: 1,
          rejected_selected_shape_count: 1,
        },
        candidate_audit: [
          {
            id: "candidate-1",
            shape_name: "star",
            selected_shape_match: true,
            accepted: false,
            verified: false,
            decision: "review",
            failed_gates: reviewVerification.failed_gates,
            score: failedValidation.score,
            shape_fidelity: failedValidation.shape_fidelity,
            distance_km: successfulRoute.distance_km,
            issues: failedValidation.issues,
          },
        ],
        candidates: [reviewCandidate],
      }),
    });
  });
  await page.goto("/");

  await page.getByRole("button", { name: "Find routes" }).click();

  await expect(page.getByText("Map preview only")).toBeVisible();
  await expect(
    page.getByRole("region", { name: /preview only.*not matched to streets/i }),
  ).toBeVisible();
  await expect(page.getByText("Preview only. Not matched to streets")).toBeVisible();
  await expect(page.getByText("Review this route")).toBeVisible();
  await expect(page.getByText(/items? to check/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit this route" })).toBeEnabled();
  await expect(page.getByRole("heading", { name: "Street route unavailable" })).toBeVisible();
  await expect(page.getByText(/No GPS file was created/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve and download GPX" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toHaveCount(0);
});

test("switching to a malformed unrouted option removes every export action", async ({
  page,
}) => {
  await mockHealth(page);
  const unsafeValidation = {
    ...successfulRoute.validation,
    score: 0.4,
    shape_fidelity: 0.3,
    on_roads: false,
    issues: ["Route is not matched to the road network."],
  };
  const unsafeCandidate = {
    ...successfulRoute.candidates[1],
    id: "candidate-unsafe",
    snapped: false,
    validation: unsafeValidation,
    verification: buildVerification(unsafeValidation),
    below_recommended: true,
    requires_user_acceptance: true,
    gpx: "<gpx>must not download</gpx>",
    tcx: "<TrainingCenterDatabase>must not download</TrainingCenterDatabase>",
    gallery_publish_token: "must-not-publish",
    details: buildRouteDetails(unsafeValidation, 20.31),
  };
  await mockGenerate(page, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...successfulRoute,
        candidates: [successfulRoute.candidates[0], unsafeCandidate],
        candidate_summary: {
          ...successfulRoute.candidate_summary,
          accepted_count: 1,
          verified_count: 1,
          review_count: 1,
        },
      }),
    }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Find routes" }).click();

  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeEnabled();
  await page.locator('.candidate-card[data-candidate-id="candidate-unsafe"]').click();

  await expect(page.getByText("Map preview only")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Street route unavailable" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve and download GPX" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Download TCX" })).toHaveCount(0);
  await page.getByText("Share map publicly", { exact: true }).click();
  await expect(page.getByRole("button", { name: "Publish map" })).toBeDisabled();
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
            "The closest route had a 41% shape match. We aim for at least 70%.",
            "Diamond was a clear match on nearby streets.",
          ],
        },
        candidates: successfulRoute.candidates.map((candidate) => ({
          ...candidate,
          shape_name: "diamond",
          verification: buildVerification(candidate.validation, "diamond"),
        })),
      }),
    }),
  );
  await page.goto("/");

  await page.getByRole("button", { name: "Find routes" }).click();

  await expect(page.getByRole("heading", { name: "Diamond in Debrecen" })).toBeVisible();
  await expect(page.getByText("Cat did not fit these streets. Here is a Diamond")).toBeVisible();
  await expect(page.getByText(/41% shape match/)).toBeVisible();
  await expect(page.getByText("Other shapes tried: Triangle, Diamond.")).toBeVisible();
  await expect(page.locator(".route-state")).toContainText("Ready to download");
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
        route_verification: successfulRoute.route_verification,
        route_details: buildRouteDetails(successfulRoute.validation, 19.9),
        gpx: "<?xml version=\"1.0\"?><gpx><trk><name>Edited</name></trk></gpx>",
        tcx: null,
        warnings: [],
      }),
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Find routes" }).click();

  await page.getByRole("button", { name: "Edit this route" }).click();
  await expect(page.locator(".route-edit-marker")).toHaveCount(4);
  await page.getByRole("button", { name: "Apply changes" }).click();

  await expect.poll(() => editPayload?.control_points?.length).toBe(4);
  expect(editPayload.shape_name).toBe("star");
  await expect(page.getByText(/Changes saved: 19.90 km/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Close editor" })).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download edited GPX" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("star-debrecen.gpx");
});

test("a verified route map can be published anonymously with streets and attribution", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => {
      throw new DOMException("Storage is unavailable.", "QuotaExceededError");
    };
  });
  await mockHealth(page);
  await mockGenerate(page, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(successfulRoute),
    }),
  );
  await page.unroute("**/gallery*");
  let publishedPayload = null;
  let published = false;
  await page.route("**/gallery*", (route) => {
    const requestUrl = new URL(route.request().url());
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          configured: true,
          assets: published
            ? [
                {
                  id: `gps-art-gallery/${"d".repeat(32)}`,
                  image_url: "https://res.cloudinary.com/demo/image/upload/published-map.png",
                  width: 900,
                  height: 600,
                },
              ]
            : [],
          next_cursor: null,
        }),
      });
    }
    if (requestUrl.pathname.endsWith("/gallery/delete")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ removed: true }),
      });
    }
    publishedPayload = route.request().postDataJSON();
    published = true;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        asset: {
          id: `gps-art-gallery/${"d".repeat(32)}`,
          image_url: "https://res.cloudinary.com/demo/image/upload/published-map.png",
          width: 900,
          height: 600,
        },
        removal_token: "e".repeat(64),
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Find routes" }).click();
  await page.getByText("Share map publicly", { exact: true }).click();
  await expect(page.getByRole("button", { name: "Publish map" })).toBeVisible();
  await expect(page.locator(".route-map .leaflet-overlay-pane path").first()).toBeVisible();
  await page.getByRole("button", { name: "Rotate map 15 degrees right" }).click();
  await page.getByRole("button", { name: "Rotate map 15 degrees right" }).click();
  await expect(page.locator(".map-rotation-value")).toHaveText("30°");
  await page
    .getByLabel("I understand that this location and its street names will be public.")
    .check();
  await page.getByRole("button", { name: "Publish map" }).click();

  await expect(page.getByText("Map published.")).toBeVisible();
  expect(publishedPayload.confirm_public_location).toBe(true);
  expect(publishedPayload.publish_token).toBe("candidate-1-gallery-token");
  expect(publishedPayload.image_data_url).toMatch(/^data:image\/png;base64,/);
  expect(publishedPayload).not.toHaveProperty("prompt");
  expect(publishedPayload).not.toHaveProperty("city");
  await expect(
    page.getByRole("img", {
      name: "Anonymous GPS art route on an OpenStreetMap street map",
    }),
  ).toBeVisible();
  await expect(page.getByText("Map data © OpenStreetMap contributors").first()).toBeVisible();
});

import { expect, test } from "playwright/test";
import { buildEditedRoute } from "./support/functional-fixtures.js";

const transparentTile = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

const routePoints = [
  [47.5316, 21.6273],
  [47.538, 21.642],
  [47.523, 21.635],
  [47.5316, 21.6273],
];

function buildValidation(score, { onRoads = true } = {}) {
  return {
    score,
    closure: 0.96,
    distance_fit: score,
    shape_fidelity: score,
    issues: onRoads ? [] : ["Route is not matched to the road network."],
    on_roads: onRoads,
    spatial_similarity: score,
    coverage_similarity: score,
    turning_similarity: score,
    landmark_similarity: score,
    length_similarity: score,
    extent_similarity: score,
    route_length_ratio: 1.03,
    mean_deviation_ratio: 0.08,
    closure_gap_m: 4.2,
    actual_distance_km: 8.1,
    target_distance_km: 8,
    route_point_count: 240,
    guide_point_count: 32,
  };
}

function buildVerification(validation) {
  const definitions = [
    ["overall_score", "Overall route quality", validation.score, 0.72, "route"],
    ["shape_fidelity", "Combined shape likeness", validation.shape_fidelity, 0.7, "shape"],
    ["distance_fit", "Target-distance accuracy", validation.distance_fit, 0.6, "usability"],
    ["closure", "Loop closure", validation.closure, 0.6, "usability"],
  ];
  const gates = [
    {
      key: "selected_shape",
      label: "Selected shape",
      value: "star",
      minimum: "star",
      group: "shape",
      applies: true,
      passed: true,
      description: "The route uses the selected drawing.",
    },
    {
      key: "road_network",
      label: "Connected street route",
      value: validation.on_roads,
      minimum: true,
      group: "route",
      applies: true,
      passed: validation.on_roads,
      description: "The route follows connected streets.",
    },
    ...definitions.map(([key, label, value, minimum, group]) => ({
      key,
      label,
      value,
      minimum,
      group,
      applies: true,
      passed: value >= minimum,
      description: `${label} is checked independently.`,
    })),
  ];
  const failedGates = gates.filter((gate) => !gate.passed).map((gate) => gate.key);
  return {
    passed: failedGates.length === 0,
    shape_following: !failedGates.includes("shape_fidelity"),
    passed_count: gates.length - failedGates.length,
    required_count: gates.length,
    failed_gates: failedGates,
    gates,
    thresholds: { overall_score: 0.72, shape: 0.7, usability: 0.6 },
  };
}

function buildDetails(validation, distanceKm) {
  return {
    shape: { name: "star", source: "template", closed: true },
    routing: {
      activity: "run",
      street_matched: validation.on_roads,
      route_point_count: 240,
      guide_point_count: 32,
      closure_gap_m: validation.closure_gap_m,
    },
    distance: {
      actual_km: distanceKm,
      target_km: 8,
      difference_km: distanceKm - 8,
      difference_percent: ((distanceKm - 8) / 8) * 100,
      route_to_guide_ratio: validation.route_length_ratio,
    },
    deviation: { mean_outline_deviation_ratio: validation.mean_deviation_ratio },
    placement: { rotation_deg: 12, scale_m: 1_800, lat_offset_m: 0, lon_offset_m: 0 },
  };
}

function buildCandidate(id, score, distanceKm, { publishable = false } = {}) {
  const validation = buildValidation(score);
  return {
    id,
    shape_name: "star",
    shape_source: "template",
    points_preview: routePoints,
    ideal_preview: routePoints,
    landmark_preview: routePoints.slice(0, 3),
    distance_km: distanceKm,
    snapped: true,
    closed: true,
    target_distance_km: 8,
    validation,
    below_recommended: score < 0.72,
    verification: buildVerification(validation),
    details: buildDetails(validation, distanceKm),
    gpx: "<?xml version=\"1.0\"?><gpx version=\"1.1\"></gpx>",
    tcx: "<?xml version=\"1.0\"?><TrainingCenterDatabase></TrainingCenterDatabase>",
    gallery_publish_token: publishable ? "publish-token-for-ready-route" : null,
  };
}

function buildResult() {
  const ready = buildCandidate("candidate-ready", 0.9, 8.1, { publishable: true });
  const review = buildCandidate("candidate-review", 0.61, 9.4);
  return {
    request_id: "functional-workflow-1",
    prompt: "a star run in Debrecen, about 8 km",
    intent: {
      shape: "star",
      text: null,
      city: "Debrecen",
      sport: "run",
      distance_km: 8,
      style: null,
    },
    shape: { name: "star", closed: true, source: "template", n_paths: 1 },
    suggested_shape: null,
    requested_shape: "star",
    fit_decision: null,
    validation: ready.validation,
    distance_km: ready.distance_km,
    snapped: true,
    iterations: 1,
    candidate_count: 2,
    preflight_count: 24,
    below_threshold: false,
    errors: [],
    history: [],
    gpx: ready.gpx,
    tcx: ready.tcx,
    file_paths: {},
    points_preview: ready.points_preview,
    ideal_preview: ready.ideal_preview,
    landmark_preview: ready.landmark_preview,
    candidates: [ready, review],
    candidate_audit: [],
    candidate_summary: {
      selected_shape: "star",
      accepted_count: 1,
      verified_count: 1,
      review_count: 1,
      shown_count: 2,
      rejected_selected_shape_count: 1,
      other_shape_count: 0,
      audited_count: 2,
      full_route_attempt_count: 2,
      preflight_count: 24,
    },
    preflight_candidates: [],
    route_verification: ready.verification,
    route_details: ready.details,
    gallery_publish_token: ready.gallery_publish_token,
  };
}

async function installEmptyGallery(page) {
  await page.route("**/gallery*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configured: true, assets: [], next_cursor: null }),
    }),
  );
}

async function installSuccessfulGeneration(page, result = buildResult()) {
  let payload = null;
  await page.route("**/generate", async (route) => {
    payload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(result),
    });
  });
  return () => payload;
}

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
});

test("the prompt counter and keyboard shortcut submit a normalised idea", async ({ page }) => {
  await installEmptyGallery(page);
  const submittedPayload = await installSuccessfulGeneration(page);
  await page.goto("/");

  const prompt = page.getByLabel("Drawing and location");
  await prompt.fill("x".repeat(320));
  await expect(page.locator("#prompt-count")).toHaveText("320/320");
  await prompt.fill("   ａ moon   run in Eger, about 8 km   ");
  await prompt.press("Control+Enter");

  await expect(page.getByRole("heading", { name: "Star in Debrecen" })).toBeVisible();
  expect(submittedPayload()).toEqual({ prompt: "a moon run in Eger, about 8 km" });
  await expect(prompt).toHaveValue("a moon run in Eger, about 8 km");
});

test("cancelling an in-flight generation restores the designer without an error", async ({
  page,
}) => {
  await installEmptyGallery(page);
  let requestStarted = false;
  await page.route("**/generate", async (route) => {
    requestStarted = true;
    await new Promise((resolve) => setTimeout(resolve, 7_000));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildResult()),
    }).catch(() => {});
  });
  await page.goto("/");

  await page.getByRole("button", { name: "Find routes" }).click();
  await expect.poll(() => requestStarted).toBe(true);
  await expect(page.getByRole("heading", { name: "Finding routes" })).toBeVisible();
  await expect(page.locator(".loading-card--journey")).toBeFocused();
  await expect(page.getByText("Live route lab")).toHaveCount(0);
  await expect(page.getByRole("progressbar", { name: "Route generation is in progress" })).toBeVisible();
  await expect(page.getByText("Timing is illustrative")).toBeVisible();
  await expect(page.getByRole("list", { name: "Typical planning stages" })).toBeVisible();
  await expect(page.locator(".gps-route-animation")).toBeVisible();
  if ((await page.viewportSize()).width > 768) {
    await expect(page.getByText("Quality checks stay on")).toBeVisible();
  }
  await expect(page.getByText("Sketching the outline without colouring outside the city.")).toBeVisible();
  await page.waitForTimeout(5_100);
  await expect(page.getByText("Asking nearby streets to cooperate nicely.")).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Street fit" })).toHaveAttribute("aria-current", "step");
  await expect(page.getByLabel(/seconds elapsed/)).toHaveText("5s");
  if ((await page.viewportSize()).width <= 768) {
    const waitingBox = await page.locator(".loading-card--journey").boundingBox();
    const cancelBox = await page.getByRole("button", { name: "Cancel" }).boundingBox();
    expect(waitingBox).not.toBeNull();
    expect(cancelBox).not.toBeNull();
    expect(waitingBox.x).toBeLessThanOrEqual(1);
    expect(waitingBox.width).toBeGreaterThanOrEqual((await page.viewportSize()).width - 1);
    expect(cancelBox.y + cancelBox.height).toBeLessThanOrEqual((await page.viewportSize()).height + 1);
  }
  await page.getByRole("button", { name: "Cancel" }).click();

  await expect(page.getByRole("button", { name: "Find routes" })).toBeEnabled();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.locator(".result")).toHaveCount(0);
});

test("an aborted older response cannot overwrite a newer route", async ({ page }) => {
  await installEmptyGallery(page);
  let requestCount = 0;
  let releaseFirstRequest;
  const firstRequestGate = new Promise((resolve) => {
    releaseFirstRequest = resolve;
  });
  const newerResult = buildResult();
  newerResult.request_id = "newer-route-request";
  newerResult.prompt = "a star run in Szeged, about 8 km";
  newerResult.intent = { ...newerResult.intent, city: "Szeged" };

  await page.route("**/generate", async (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      await firstRequestGate;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(buildResult()),
      }).catch(() => {});
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(newerResult),
    });
  });
  await page.goto("/");

  await page.getByRole("button", { name: "Find routes" }).click();
  await expect.poll(() => requestCount).toBe(1);
  await page.getByRole("button", { name: "Cancel" }).click();
  await page.getByLabel("Drawing and location").fill(newerResult.prompt);
  await page.getByRole("button", { name: "Find routes" }).click();

  await expect(page.getByRole("heading", { name: "Star in Szeged" })).toBeVisible();
  releaseFirstRequest();
  await page.waitForTimeout(300);
  await expect(page.getByRole("heading", { name: "Star in Szeged" })).toBeVisible();
  await expect(page.locator(".route-facts")).toContainText("newer-route-request");
});

test("reduced motion keeps route generation informative without moving graphics", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await installEmptyGallery(page);
  let requestStarted = false;
  await page.route("**/generate", async (route) => {
    requestStarted = true;
    await new Promise((resolve) => setTimeout(resolve, 4_000));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildResult()),
    }).catch(() => {});
  });
  await page.goto("/");

  await page.getByRole("button", { name: "Find routes" }).click();
  await expect.poll(() => requestStarted).toBe(true);
  await expect(page.getByRole("heading", { name: "Finding routes" })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Route generation is in progress" })).toBeVisible();
  await expect(page.getByText("Sketching the outline without colouring outside the city.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel" })).toBeVisible();

  const animationNames = await page.locator([
    ".gps-route-line",
    ".gps-route-traveller",
    ".gps-route-traveller-halo",
    ".loading-progress-track > span",
  ].join(", ")).evaluateAll((elements) =>
    elements.map((element) => getComputedStyle(element).animationName));
  expect(animationNames).toEqual(["none", "none", "none", "none"]);
  await expect(page.locator(".gps-route-traveller")).toHaveCSS("offset-distance", "72%");

  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("button", { name: "Find routes" })).toBeEnabled();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("switching route options updates quality, distance, and export state", async ({ page }) => {
  await installEmptyGallery(page);
  await installSuccessfulGeneration(page);
  await page.route("**/route-acceptance", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ recorded: true }),
    }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Find routes" }).click();

  const readyOption = page.locator('.candidate-card[data-candidate-id="candidate-ready"]');
  const reviewOption = page.locator('.candidate-card[data-candidate-id="candidate-review"]');
  await reviewOption.click();
  await expect(page.locator(".route-state")).toContainText("Check before downloading");
  await expect(
    page.locator(".metric").filter({ hasText: "Overall match" }).locator("dd").first(),
  ).toHaveText("61%");
  await expect(
    page
      .locator(".metric")
      .filter({ has: page.locator("dt", { hasText: /^Distance$/ }) })
      .first()
      .locator("dd")
      .first(),
  ).toHaveText("9.40 km");
  await expect(page.getByRole("button", { name: "Approve and download GPX" })).toBeEnabled();

  await readyOption.click();
  await expect(page.locator(".route-state")).toContainText("Ready to download");
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeEnabled();
  await expect(page.getByText("Share map publicly", { exact: true })).toBeVisible();

  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
  for (const control of [
    readyOption,
    page.getByRole("button", { name: "Edit this route" }),
    page.getByRole("button", { name: "Download GPX", exact: true }),
  ]) {
    const box = await control.boundingBox();
    expect(box).not.toBeNull();
    expect(box.height).toBeGreaterThanOrEqual(44);
  }
});

test("an edit API failure keeps the editor open and allows another attempt", async ({ page }) => {
  await installEmptyGallery(page);
  await installSuccessfulGeneration(page);
  let editAttempts = 0;
  let editPayload = null;
  await page.route("**/edit-route", async (route) => {
    editAttempts += 1;
    editPayload = route.request().postDataJSON();
    if (editAttempts === 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "The street graph is busy. Try again." }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildEditedRoute()),
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Find routes" }).click();
  await page.getByRole("button", { name: "Edit this route" }).click();
  const firstEditPoint = page.locator(".route-edit-marker").first();
  await firstEditPoint.focus();
  await firstEditPoint.press("ArrowUp");
  await page.getByRole("button", { name: "Apply changes" }).click();

  await expect.poll(() => editAttempts).toBe(1);
  expect(editPayload.control_points[0][0]).toBeGreaterThan(routePoints[0][0]);
  await expect(page.getByRole("alert")).toContainText("The street graph is busy. Try again.");
  await expect(page.getByRole("button", { name: "Apply changes" })).toBeEnabled();
  await expect(page.locator(".route-edit-marker")).toHaveCount(4);

  await page.getByRole("button", { name: "Apply changes" }).click();
  await expect.poll(() => editAttempts).toBe(2);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Download edited GPX" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Download TCX" })).toBeEnabled();
});

test("prompt validation explains malformed input and recovers without losing the idea", async ({
  page,
}) => {
  await installEmptyGallery(page);
  let generateRequests = 0;
  await page.route("**/generate", async (route) => {
    generateRequests += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildResult()),
    });
  });
  await page.goto("/");

  const prompt = page.getByLabel("Drawing and location");
  await prompt.fill("     ");
  await expect(page.getByRole("button", { name: "Find routes" })).toBeEnabled();
  await prompt.press("Control+Enter");

  expect(generateRequests).toBe(0);
  await expect(prompt).toBeFocused();
  await expect(prompt).toHaveAttribute("aria-invalid", "true");
  await expect(prompt).toHaveAttribute("aria-errormessage", "prompt-error");
  await expect(page.getByRole("alert")).toContainText("Enter a route idea");

  await prompt.fill("!? ♥");
  await expect(page.getByRole("alert")).toContainText(
    "Include a shape, word, letter, or number to draw.",
  );
  await prompt.fill("a circle run in Eger, about 8 km");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await prompt.press("Control+Enter");

  await expect.poll(() => generateRequests).toBe(1);
  await expect(page.getByRole("heading", { name: "Star in Debrecen" })).toBeVisible();
});

test("choosing cycling raises the suggested distance to its valid minimum", async ({ page }) => {
  await installEmptyGallery(page);
  const submittedPayload = await installSuccessfulGeneration(page);
  await page.goto("/");

  await page.getByText("Choose city, activity, and distance").click();
  const distance = page.getByLabel("Distance");
  await distance.fill("3");
  await page.getByRole("radio", { name: "Cycling" }).check();

  await expect(distance).toHaveValue("10");
  await expect(distance).toHaveAttribute("min", "10");
  await expect(distance).toHaveAttribute("max", "200");
  await expect(page.getByText("Cycling routes start at 10 km.")).toBeVisible();

  await distance.fill("10.5");
  await distance.blur();
  await expect(distance).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByRole("alert")).toContainText(
    "Enter the distance in whole kilometres.",
  );
  await page.getByRole("button", { name: "Find a route" }).click();
  expect(submittedPayload()).toBeNull();
  await expect(distance).toBeFocused();

  await distance.fill("9");
  await expect(page.getByRole("alert")).toContainText(
    "Enter a cycling distance from 10 to 200 km.",
  );
  await distance.fill("10");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByRole("button", { name: "Find a route" }).click();

  await expect(page.getByRole("heading", { name: "Star in Debrecen" })).toBeVisible();
  expect(submittedPayload()).toEqual({
    prompt: "suggest a bike route in Budapest, about 10 km",
  });
});

test("unfinished point edits block every export and can be discarded", async ({ page }) => {
  await installEmptyGallery(page);
  await installSuccessfulGeneration(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Find routes" }).click();
  await page.getByRole("button", { name: "Edit this route" }).click();

  const firstEditPoint = page.locator(".route-edit-marker").first();
  await firstEditPoint.focus();
  await firstEditPoint.press("ArrowRight");

  await expect(page.getByRole("button", { name: "Discard point changes" })).toBeVisible();
  await expect(page.getByText("Apply or discard your changes before downloading.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Download TCX", exact: true })).toBeDisabled();

  await page.getByRole("button", { name: "Discard point changes" }).click();
  await expect(page.locator(".route-edit-marker")).toHaveCount(0);
  await expect(page.getByText("Apply or discard your changes before downloading.")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Download TCX", exact: true })).toBeEnabled();
});

test("acceptance telemetry failure does not block a reviewed route download", async ({ page }) => {
  await installEmptyGallery(page);
  await installSuccessfulGeneration(page);
  let acceptancePayload = null;
  await page.route("**/route-acceptance", async (route) => {
    acceptancePayload = route.request().postDataJSON();
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Acceptance telemetry is unavailable." }),
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Find routes" }).click();
  await page.locator('.candidate-card[data-candidate-id="candidate-review"]').click();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Approve and download GPX" }).click();
  const download = await downloadPromise;

  expect(download.suggestedFilename()).toBe("star-debrecen.gpx");
  await expect.poll(() => acceptancePayload).toMatchObject({
    generation_request_id: "functional-workflow-1",
    route_id: "candidate-review",
    shape_name: "star",
    automatic_checks_passed: false,
    snapped: true,
    failed_gates: ["overall_score", "shape_fidelity"],
    score: 0.61,
    shape_fidelity: 0.61,
    distance_km: 9.4,
  });
  await expect(page.getByText("Approved by you")).toBeVisible();
  await expect(page.getByRole("button", { name: "Download GPX", exact: true })).toBeEnabled();
});

test("TCX export downloads the selected route with a safe filename", async ({ page }) => {
  await installEmptyGallery(page);
  await installSuccessfulGeneration(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Find routes" }).click();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download TCX", exact: true }).click();
  const download = await downloadPromise;

  expect(download.suggestedFilename()).toBe("star-debrecen.tcx");
  await expect(page.locator('.sr-only[aria-live="polite"]')).toContainText(
    "TCX download started.",
  );
});

test("switching route options clears an unfinished editor session", async ({ page }) => {
  await installEmptyGallery(page);
  await installSuccessfulGeneration(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Find routes" }).click();
  await page.getByRole("button", { name: "Edit this route" }).click();

  const firstEditPoint = page.locator(".route-edit-marker").first();
  await firstEditPoint.focus();
  await firstEditPoint.press("ArrowUp");
  await expect(page.getByRole("button", { name: "Discard point changes" })).toBeVisible();

  await page.locator('.candidate-card[data-candidate-id="candidate-review"]').click();

  await expect(page.locator(".route-edit-marker")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Edit this route" })).toBeVisible();
  await expect(page.getByText("Apply or discard your changes before downloading.")).toHaveCount(0);
  await expect(page.locator(".route-state")).toContainText("Check before downloading");
});

test("a gallery outage stays isolated from route generation", async ({ page }) => {
  await page.route("**/gallery*", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "The gallery is temporarily unavailable." }),
    }),
  );
  await installSuccessfulGeneration(page);
  await page.goto("/");

  await expect(page.locator(".gallery").getByRole("alert")).toContainText(
    "The gallery is temporarily unavailable.",
  );
  await page.getByRole("button", { name: "Find routes" }).click();

  await expect(page.getByRole("heading", { name: "Star in Debrecen" })).toBeVisible();
  await expect(page.locator(".route-state")).toContainText("Ready to download");
  await expect(page.locator(".gallery").getByRole("alert")).toContainText(
    "The gallery is temporarily unavailable.",
  );
});

test("gallery pagination merges assets and a saved removal token deletes its map", async ({
  page,
}) => {
  const firstId = `gps-art-gallery/${"a".repeat(32)}`;
  const secondId = `gps-art-gallery/${"b".repeat(32)}`;
  const removalToken = "c".repeat(64);
  await page.addInitScript(
    ({ storageKey, assetId, token }) => {
      window.localStorage.setItem(storageKey, JSON.stringify({ [assetId]: token }));
    },
    {
      storageKey: "gps-art-gallery-removal-tokens-v1",
      assetId: firstId,
      token: removalToken,
    },
  );
  let deletePayload = null;
  await page.route("**/gallery/delete", async (route) => {
    deletePayload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ removed: true }),
    });
  });
  await page.route("**/gallery*", async (route) => {
    const url = new URL(route.request().url());
    const secondPage = url.searchParams.get("cursor") === "page-2";
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        configured: true,
        assets: [
          {
            id: secondPage ? secondId : firstId,
            image_url: `https://res.cloudinary.com/demo/image/upload/${secondPage ? "two" : "one"}.png`,
            width: 900,
            height: 600,
          },
        ],
        next_cursor: secondPage ? null : "page-2",
      }),
    });
  });
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/");

  await expect(page.getByRole("img", { name: "Anonymous GPS art route on an OpenStreetMap street map" })).toHaveCount(1);
  await page.getByRole("button", { name: "Show more routes" }).click();
  await expect(page.getByRole("img", { name: "Anonymous GPS art route on an OpenStreetMap street map" })).toHaveCount(2);
  await page.getByRole("button", { name: "Remove my post" }).click();

  await expect.poll(() => deletePayload).toEqual({
    public_id: firstId,
    removal_token: removalToken,
  });
  await expect(page.getByRole("img", { name: "Anonymous GPS art route on an OpenStreetMap street map" })).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Remove my post" })).toHaveCount(0);
});

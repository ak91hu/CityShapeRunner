import { expect } from "playwright/test";

const transparentTile = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

export const routePoints = [
  [47.5316, 21.6273],
  [47.538, 21.642],
  [47.523, 21.635],
  [47.5316, 21.6273],
];

const idealPoints = [
  [47.5316, 21.6273],
  [47.537, 21.641],
  [47.524, 21.634],
  [47.5316, 21.6273],
];

const landmarkPoints = idealPoints.slice(0, 3);

export function buildValidation(overrides = {}) {
  const score = overrides.score ?? 0.91;
  return {
    score,
    closure: 0.99,
    distance_fit: score,
    shape_fidelity: score,
    issues: [],
    on_roads: true,
    spatial_similarity: score,
    coverage_similarity: score,
    turning_similarity: score,
    landmark_similarity: score,
    reversal_similarity: score,
    length_similarity: score,
    extent_similarity: score,
    route_length_ratio: 1.04,
    mean_deviation_ratio: 0.07,
    closure_gap_m: 3.4,
    actual_distance_km: 19.82,
    target_distance_km: 20,
    route_point_count: 842,
    guide_point_count: 401,
    ...overrides,
  };
}

export function buildVerification(validation, shapeName = "star") {
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
    numericGate(
      "reversal_similarity",
      "No unintended backtracking",
      validation.reversal_similarity,
      0.7,
    ),
    numericGate("length_similarity", "Detour control", validation.length_similarity, 0.7),
    numericGate("extent_similarity", "Width / height preservation", validation.extent_similarity, 0.7),
    numericGate("distance_fit", "Target-distance accuracy", validation.distance_fit, 0.6, "usability"),
    numericGate("closure", "Loop closure", validation.closure, 0.6, "usability"),
  ];
  const failedGates = gates.filter((gate) => !gate.passed).map((gate) => gate.key);
  return {
    passed: failedGates.length === 0,
    shape_following: gates.filter((gate) => gate.group === "shape").every((gate) => gate.passed),
    passed_count: gates.length - failedGates.length,
    required_count: gates.length,
    failed_gates: failedGates,
    gates,
    thresholds: { overall_score: 0.72, shape: 0.7, usability: 0.6 },
  };
}

export function buildRouteDetails(validation, distanceKm = 19.82) {
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

export function buildCandidate({
  id,
  score,
  distanceKm,
  publishable = false,
  snapped = true,
  gpx = true,
  tcx = true,
} = {}) {
  const validation = buildValidation({
    score,
    shape_fidelity: score,
    distance_fit: score,
    on_roads: snapped,
    issues: snapped ? [] : ["Route is not matched to the road network."],
  });
  return {
    id,
    shape_name: "star",
    shape_source: "template",
    points_preview: routePoints,
    ideal_preview: idealPoints,
    landmark_preview: landmarkPoints,
    distance_km: distanceKm,
    snapped,
    closed: true,
    target_distance_km: 20,
    validation,
    below_recommended: score < 0.72,
    verification: buildVerification(validation),
    details: buildRouteDetails(validation, distanceKm),
    gpx: gpx ? "<?xml version=\"1.0\"?><gpx version=\"1.1\"></gpx>" : null,
    tcx: tcx
      ? "<?xml version=\"1.0\"?><TrainingCenterDatabase></TrainingCenterDatabase>"
      : null,
    gallery_publish_token: publishable ? `publish-${id}-token` : null,
  };
}

export function buildRouteResult(overrides = {}) {
  const ready = buildCandidate({
    id: "candidate-ready",
    score: 0.91,
    distanceKm: 19.82,
    publishable: true,
  });
  const review = buildCandidate({
    id: "candidate-review",
    score: 0.61,
    distanceKm: 21.4,
  });
  const candidates = [ready, review];
  const result = {
    request_id: "expanded-functional-1",
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
    suggestion_reason: null,
    requested_shape: "star",
    fit_decision: null,
    validation: ready.validation,
    distance_km: ready.distance_km,
    snapped: true,
    iterations: 2,
    candidate_count: 2,
    preflight_count: 164,
    below_threshold: false,
    errors: [],
    history: [
      { iteration: 1, score: 0.79, delta_vs_best: -0.12, fidelity: 0.76, distance_fit: 0.83 },
      { iteration: 2, score: 0.91, delta_vs_best: 0.12, fidelity: 0.91, distance_fit: 0.91 },
    ],
    gpx: ready.gpx,
    tcx: ready.tcx,
    file_paths: {},
    gallery_publish_token: ready.gallery_publish_token,
    points_preview: ready.points_preview,
    ideal_preview: ready.ideal_preview,
    landmark_preview: ready.landmark_preview,
    candidates,
    candidate_audit: candidates.map((candidate) => ({
      id: candidate.id,
      shape_name: candidate.shape_name,
      selected_shape_match: true,
      accepted: candidate.verification.passed,
      verified: candidate.verification.passed,
      decision: candidate.verification.passed ? "verified" : "review",
      failed_gates: candidate.verification.failed_gates,
      score: candidate.validation.score,
      shape_fidelity: candidate.validation.shape_fidelity,
      distance_km: candidate.distance_km,
      issues: candidate.validation.issues,
    })),
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
      preflight_count: 164,
    },
    preflight_candidates: [],
    route_verification: ready.verification,
    route_details: ready.details,
  };
  return { ...result, ...overrides };
}

export function galleryAsset(character = "a", imageName = "gallery-map") {
  return {
    id: `gps-art-gallery/${character.repeat(32)}`,
    image_url: `https://res.cloudinary.com/demo/image/upload/${imageName}.png`,
    width: 900,
    height: 600,
  };
}

export async function installCommonMocks(page) {
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/png",
      headers: { "Access-Control-Allow-Origin": "*" },
      body: transparentTile,
    }),
  );
  await page.route("https://res.cloudinary.com/**", (route) =>
    route.fulfill({ status: 200, contentType: "image/png", body: transparentTile }),
  );
  await page.route("**/gallery*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configured: true, assets: [], next_cursor: null }),
    }),
  );
  await page.route("**/route-acceptance", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ recorded: true }),
    }),
  );
}

export async function replaceGalleryRoute(page, handler) {
  await page.unroute("**/gallery*");
  await page.route("**/gallery*", handler);
}

export async function mockGeneration(page, result = buildRouteResult()) {
  const requests = [];
  await page.route("**/generate", async (route) => {
    requests.push(route.request().postDataJSON());
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(result),
    });
  });
  return {
    requests,
    lastPayload: () => requests.at(-1) ?? null,
  };
}

export async function openGeneratedRoute(page, result = buildRouteResult()) {
  const capture = await mockGeneration(page, result);
  await page.goto("/");
  await page.getByRole("button", { name: "Find routes" }).click();
  await expect(page.getByRole("heading", { name: /Star in Debrecen/i })).toBeVisible();
  return capture;
}

export function buildEditedRoute({ passed = true, distanceKm = 20.05 } = {}) {
  const score = passed ? 0.88 : 0.58;
  const validation = buildValidation({ score, shape_fidelity: score, distance_fit: score });
  return {
    request_id: "edited-functional-1",
    points_preview: routePoints.map(([lat, lon], index) => [lat + index * 0.0002, lon]),
    distance_km: distanceKm,
    snapped: true,
    below_recommended: !passed,
    validation,
    route_verification: buildVerification(validation),
    route_details: buildRouteDetails(validation, distanceKm),
    gpx: "<?xml version=\"1.0\"?><gpx><trk><name>Edited</name></trk></gpx>",
    tcx: passed
      ? "<?xml version=\"1.0\"?><TrainingCenterDatabase></TrainingCenterDatabase>"
      : null,
    warnings: passed ? [] : ["Edited route needs review."],
  };
}

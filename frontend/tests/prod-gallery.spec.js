import { expect, test } from "playwright/test";

const RUN_PROD = process.env.RUN_PROD_GALLERY === "1";
const PUBLISH = process.env.PROD_PUBLISH_GALLERY === "1";
const TARGET_COUNT = Number.parseInt(process.env.PROD_GALLERY_TARGET_COUNT ?? "2", 10);

const DEFAULT_CASES = [
  { name: "suggest-debrecen", prompt: "suggest a cycling route in Debrecen, 20 km" },
  { name: "suggest-barcelona", prompt: "suggest a cycling route in Barcelona, 20 km" },
  { name: "suggest-szeged", prompt: "suggest a cycling route in Szeged, 18 km" },
  { name: "suggest-cegled", prompt: "suggest a cycling route in Cegléd, 18 km" },
  { name: "heart-budapest", prompt: "a heart run in Budapest, 8 km", shape: "heart" },
];

function configuredCases() {
  const raw = process.env.PROD_GALLERY_CASES_JSON;
  if (!raw) return DEFAULT_CASES;
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed) || parsed.length === 0) {
    throw new Error("PROD_GALLERY_CASES_JSON must be a non-empty JSON array.");
  }
  return parsed;
}

function qualityFailures(candidate, expectedShape) {
  const validation = candidate?.validation ?? {};
  const checks = [
    ["road-routed", candidate?.snapped === true],
    ["selected shape", candidate?.shape_name?.toLowerCase() === expectedShape.toLowerCase()],
    ["overall score", validation.score >= 0.78],
    ["combined likeness", validation.shape_fidelity >= 0.75],
    ["ordered curve", validation.spatial_similarity >= 0.7],
    ["outline coverage", validation.coverage_similarity >= 0.7],
    ["turn sequence", validation.turning_similarity >= 0.55],
    ["salient landmarks", validation.landmark_similarity >= 0.65],
    ["no backtracking", validation.reversal_similarity >= 0.44],
    ["detour control", validation.length_similarity >= 0.55],
    ["proportions", validation.extent_similarity >= 0.7],
    ["distance fit", validation.distance_fit >= 0.6],
    ["closure", candidate?.closed === false || validation.closure >= 0.6],
  ];
  return checks.filter(([, passed]) => !passed).map(([name]) => name);
}

function bestPublishableCandidate(result, expectedShape) {
  return (result.candidates ?? [])
    .filter((candidate) => qualityFailures(candidate, expectedShape).length === 0)
    .sort((left, right) => {
      const verificationDifference = Number(right.verification?.passed) - Number(left.verification?.passed);
      return verificationDifference || right.validation.score - left.validation.score;
    })[0] ?? null;
}

async function generateThroughProductionUi(page, routeCase) {
  await page.goto("/");
  const responsePromise = page.waitForResponse(
    (response) => response.url().endsWith("/generate") && response.request().method() === "POST",
    { timeout: 240_000 },
  );
  await page.getByLabel("Drawing and location").fill(routeCase.prompt);
  await page.getByRole("button", { name: "Find routes" }).click();
  const response = await responsePromise;
  expect(response.ok(), `${routeCase.name}: production /generate failed`).toBe(true);
  const result = await response.json();
  await expect(page.locator(".result")).toBeVisible({ timeout: 30_000 });
  return result;
}

async function publishSelectedCandidate(page, candidate) {
  await page.getByLabel("Route options").selectOption(candidate.id);
  await expect(page.getByRole("region", { name: new RegExp(`${candidate.shape_name} street-route map`, "i") }))
    .toBeVisible();

  if (!candidate.verification?.passed) {
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Approve and download GPX" }).click();
    await downloadPromise;
  }

  await page.getByLabel(/I understand that this location/).check();
  const publishResponsePromise = page.waitForResponse(
    (response) => response.url().endsWith("/gallery") && response.request().method() === "POST",
    { timeout: 60_000 },
  );
  await page.getByRole("button", { name: "Publish map" }).click();
  const publishResponse = await publishResponsePromise;
  expect(publishResponse.ok(), "production gallery upload failed").toBe(true);
  const payload = await publishResponse.json();
  expect(payload.asset.id).toMatch(/^gps-art-gallery\/[a-f0-9]{32}$/);
  expect(payload.asset.width).toBeGreaterThanOrEqual(240);
  expect(payload.asset.height).toBeGreaterThanOrEqual(180);
  await expect(page.getByText("Map published.")).toBeVisible();
  return payload.asset;
}

test.describe("production GPS-art curation and gallery publication", () => {
  test.skip(!RUN_PROD, "Set RUN_PROD_GALLERY=1 to exercise the live production service.");
  test.describe.configure({ mode: "serial" });

  test("production health and gallery contracts are ready", async ({ request }) => {
    const healthResponse = await request.get("/health");
    expect(healthResponse.ok()).toBe(true);
    const health = await healthResponse.json();
    expect(health.status).toBe("ok");
    expect(health.gallery?.configured).toBe(true);

    const galleryResponse = await request.get("/gallery?limit=1");
    expect(galleryResponse.ok()).toBe(true);
    const gallery = await galleryResponse.json();
    expect(gallery.configured).toBe(true);
    expect(Array.isArray(gallery.assets)).toBe(true);
  });

  test("production gallery viewer contains the complete image", async ({ page }) => {
    await page.goto("/");
    const galleryCards = page.locator(".gallery-card");
    await expect(galleryCards.first()).toBeVisible();
    const cardCount = await galleryCards.count();
    await page
      .getByRole("button", { name: `Open gallery image 1 of ${cardCount}` })
      .click();

    const viewer = page.getByRole("dialog", { name: "Gallery viewer" });
    await expect(viewer).toBeVisible();
    const fittedImage = await viewer.getByRole("img").evaluate((element) => {
      const imageBox = element.getBoundingClientRect();
      const media = element.closest(".gallery-lightbox-media");
      const stage = element.closest(".gallery-lightbox-stage");
      if (!media || !stage) return null;
      const mediaBox = media.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return {
        objectFit: style.objectFit,
        objectPosition: style.objectPosition,
        imageWidth: imageBox.width,
        imageHeight: imageBox.height,
        mediaWidth: mediaBox.width,
        mediaHeight: mediaBox.height,
        stageClipsHorizontally: stage.scrollWidth > stage.clientWidth,
        stageClipsVertically: stage.scrollHeight > stage.clientHeight,
      };
    });

    expect(fittedImage).not.toBeNull();
    expect(fittedImage.objectFit).toBe("contain");
    expect(fittedImage.objectPosition).toBe("50% 50%");
    expect(fittedImage.imageWidth).toBeCloseTo(fittedImage.mediaWidth, 0);
    expect(fittedImage.imageHeight).toBeCloseTo(fittedImage.mediaHeight, 0);
    expect(fittedImage.stageClipsHorizontally).toBe(false);
    expect(fittedImage.stageClipsVertically).toBe(false);
  });

  test("quality-gates production routes and optionally publishes the best maps", async ({ page }, testInfo) => {
    expect(Number.isInteger(TARGET_COUNT) && TARGET_COUNT > 0).toBe(true);
    const accepted = [];
    const diagnostics = [];

    for (const routeCase of configuredCases()) {
      const result = await generateThroughProductionUi(page, routeCase);
      const expectedShape = routeCase.shape ?? result.candidate_summary?.selected_shape;
      expect(expectedShape, `${routeCase.name}: production did not select a shape`).toBeTruthy();
      const candidate = bestPublishableCandidate(result, expectedShape);
      diagnostics.push({
        case: routeCase.name,
        selected: candidate?.id ?? null,
        bestScore: Math.max(...(result.candidates ?? []).map((item) => item.validation?.score ?? 0)),
        failures: candidate
          ? []
          : (result.candidates ?? []).slice(0, 2).map((item) => ({
              id: item.id,
              failures: qualityFailures(item, expectedShape),
            })),
      });
      if (!candidate) continue;

      await page.getByLabel("Route options").selectOption(candidate.id);
      const map = page.getByRole("region", {
        name: new RegExp(`${candidate.shape_name} street-route map`, "i"),
      });
      await expect(map).toBeVisible();
      await page.waitForFunction(() =>
        [...document.querySelectorAll(".route-map img.leaflet-tile")]
          .some((tile) => tile.complete && tile.naturalWidth > 0),
      );
      const auditScreenshot = testInfo.outputPath(`${routeCase.name}-${candidate.id}.png`);
      await page.locator(".map-card").screenshot({ path: auditScreenshot });
      await testInfo.attach(`${routeCase.name}-${candidate.id}.png`, {
        path: auditScreenshot,
        contentType: "image/png",
      });

      const asset = PUBLISH ? await publishSelectedCandidate(page, candidate) : null;
      accepted.push({
        case: routeCase.name,
        candidate: candidate.id,
        score: candidate.validation.score,
        fidelity: candidate.validation.shape_fidelity,
        spatial: candidate.validation.spatial_similarity,
        coverage: candidate.validation.coverage_similarity,
        turning: candidate.validation.turning_similarity,
        landmarks: candidate.validation.landmark_similarity,
        reversal: candidate.validation.reversal_similarity,
        detour: candidate.validation.length_similarity,
        proportions: candidate.validation.extent_similarity,
        automaticallyVerified: Boolean(candidate.verification?.passed),
        asset,
      });
      if (accepted.length >= TARGET_COUNT) break;
    }

    console.log(JSON.stringify({ publish: PUBLISH, accepted, diagnostics }, null, 2));
    expect(
      accepted.length,
      `Only ${accepted.length}/${TARGET_COUNT} production routes met the visual quality contract.`,
    ).toBeGreaterThanOrEqual(TARGET_COUNT);

    if (PUBLISH) {
      const expectedIds = new Set(accepted.map(({ asset }) => asset.id));
      await expect.poll(async () => {
        const galleryResponse = await page.request.get(
          `/gallery?limit=50&index_probe=${Date.now()}`,
        );
        if (!galleryResponse.ok()) return false;
        const gallery = await galleryResponse.json();
        const galleryIds = new Set(gallery.assets.map((asset) => asset.id));
        return [...expectedIds].every((id) => galleryIds.has(id));
      }, {
        message: "Cloudinary search did not index every newly published gallery image.",
        timeout: 90_000,
        intervals: [2_000, 5_000, 10_000],
      }).toBe(true);
    }
  });
});

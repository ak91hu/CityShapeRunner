import { expect, test } from "playwright/test";

import {
  galleryAsset,
  installCommonMocks,
  openGeneratedRoute,
  replaceGalleryRoute,
} from "./support/functional-fixtures.js";

const removalStorageKey = "gps-art-gallery-removal-tokens-v1";

test.beforeEach(async ({ page }) => {
  await installCommonMocks(page);
});

test("an empty configured gallery invites the first shared route", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("No maps have been shared.")).toBeVisible();
  await expect(page.getByText("Publish a route map to add the first.")).toBeVisible();
  await expect(page.locator(".gallery-grid")).toHaveCount(0);
});

test("an unconfigured gallery explains that route creation still works", async ({ page }) => {
  await replaceGalleryRoute(page, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configured: false, assets: [], next_cursor: null }),
    }),
  );
  await page.goto("/");

  await expect(page.getByText("Gallery unavailable")).toBeVisible();
  await expect(page.getByText("Route planning and downloads still work.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Find routes" })).toBeEnabled();
});

test("a gallery loading error is shown inside the gallery region", async ({ page }) => {
  await replaceGalleryRoute(page, (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Gallery maintenance is in progress." }),
    }),
  );
  await page.goto("/");

  const gallery = page.getByRole("region", { name: "Public gallery" });
  await expect(gallery.getByRole("alert")).toHaveText("Gallery maintenance is in progress.");
  await expect(page.getByLabel("Drawing and location")).toBeEditable();
});

test("gallery cards open a viewer with dimensions and an original-image link", async ({
  page,
}) => {
  const asset = {
    ...galleryAsset("a", "first-map"),
    thumbnail_url: (
      "https://res.cloudinary.com/demo/image/upload/"
      + "c_limit,f_auto,q_auto:good,w_720/first-map.png"
    ),
    preview_url: (
      "https://res.cloudinary.com/demo/image/upload/"
      + "c_limit,f_auto,q_auto:good,w_1600/first-map.png"
    ),
  };
  await replaceGalleryRoute(page, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configured: true, assets: [asset], next_cursor: null }),
    }),
  );
  await page.goto("/");

  const image = page.getByRole("img", {
    name: "Anonymous GPS art route on an OpenStreetMap street map",
  });
  await expect(image).toHaveAttribute("src", asset.thumbnail_url);
  await expect(image).toHaveAttribute("loading", "eager");
  await expect(image).toHaveAttribute("fetchpriority", "high");
  await expect(image).toHaveAttribute("decoding", "async");
  await expect(image).toHaveAttribute("width", "900");
  await expect(image).toHaveAttribute("height", "600");
  await page.getByRole("button", { name: "Open gallery image 1 of 1" }).click();

  const viewer = page.getByRole("dialog", { name: "Gallery viewer" });
  await expect(viewer).toBeVisible();
  await expect(viewer).toHaveAttribute("aria-modal", "true");
  await expect(viewer.getByText("Image 1 of 1")).toBeVisible();
  const viewerImage = viewer.getByRole("img");
  await expect(viewerImage).toHaveAttribute("src", asset.preview_url);
  const fittedImage = await viewerImage.evaluate((element) => {
    const imageBox = element.getBoundingClientRect();
    const mediaBox = element.closest(".gallery-lightbox-media").getBoundingClientRect();
    const stage = element.closest(".gallery-lightbox-stage");
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
  expect(fittedImage.objectFit).toBe("contain");
  expect(fittedImage.objectPosition).toBe("50% 50%");
  expect(fittedImage.imageWidth).toBeCloseTo(fittedImage.mediaWidth, 0);
  expect(fittedImage.imageHeight).toBeCloseTo(fittedImage.mediaHeight, 0);
  expect(fittedImage.stageClipsHorizontally).toBe(false);
  expect(fittedImage.stageClipsVertically).toBe(false);
  const originalLink = viewer.getByRole("link", { name: "Open original" });
  await expect(originalLink).toHaveAttribute("href", asset.image_url);
  await expect(originalLink).toHaveAttribute("target", "_blank");
  await expect(originalLink).toHaveAttribute("rel", "noreferrer");
  await expect(viewer.getByRole("button", { name: "Previous gallery image" })).toHaveCount(0);
  await expect(viewer.getByRole("button", { name: "Next gallery image" })).toHaveCount(0);
});

test("gallery defers thumbnails beyond the first visible row", async ({ page }) => {
  const assets = ["a", "b", "c", "d", "e"].map((character, index) => ({
    ...galleryAsset(character, `map-${index + 1}`),
    thumbnail_url: `https://res.cloudinary.com/demo/image/upload/thumb-${index + 1}.webp`,
  }));
  await replaceGalleryRoute(page, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configured: true, assets, next_cursor: null }),
    }),
  );
  await page.goto("/");

  const thumbnails = page.locator(".gallery-thumbnail img");
  await expect(thumbnails).toHaveCount(5);
  await expect(thumbnails.nth(1)).toHaveAttribute("fetchpriority", "low");
  await expect(thumbnails.nth(3)).toHaveAttribute("loading", "eager");
  await expect(thumbnails.nth(4)).toHaveAttribute("loading", "lazy");
});

test("gallery viewer navigates with controls and keyboard while preserving the list", async ({
  page,
}) => {
  const assets = [
    galleryAsset("a", "first-map"),
    galleryAsset("b", "second-map"),
    galleryAsset("c", "third-map"),
  ];
  await replaceGalleryRoute(page, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configured: true, assets, next_cursor: null }),
    }),
  );
  await page.goto("/");

  const cards = page.locator(".gallery-card");
  const opener = page.getByRole("button", { name: "Open gallery image 1 of 3" });
  await expect(cards).toHaveCount(3);
  await opener.click();

  const viewer = page.getByRole("dialog", { name: "Gallery viewer" });
  const viewerImage = viewer.getByRole("img");
  await expect(viewerImage).toHaveAttribute("src", assets[0].image_url);
  await expect(viewer.getByRole("button", { name: "Close gallery viewer" })).toBeFocused();

  await page.keyboard.press("Shift+Tab");
  await expect(viewer.getByRole("link", { name: "Open original" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(viewer.getByRole("button", { name: "Close gallery viewer" })).toBeFocused();

  await viewer.getByRole("button", { name: "Next gallery image" }).click();
  await expect(viewerImage).toHaveAttribute("src", assets[1].image_url);
  await expect(viewer.getByText("Image 2 of 3")).toBeVisible();

  await page.keyboard.press("ArrowLeft");
  await expect(viewerImage).toHaveAttribute("src", assets[0].image_url);
  await page.keyboard.press("ArrowLeft");
  await expect(viewerImage).toHaveAttribute("src", assets[2].image_url);

  await page.keyboard.press("Escape");
  await expect(viewer).toHaveCount(0);
  await expect(opener).toBeFocused();
  await expect(cards).toHaveCount(3);
});

test("gallery pagination shows a busy state and appends the next page", async ({ page }) => {
  let releaseSecondPage;
  const secondPageGate = new Promise((resolve) => {
    releaseSecondPage = resolve;
  });
  await replaceGalleryRoute(page, async (route) => {
    const cursor = new URL(route.request().url()).searchParams.get("cursor");
    if (cursor) await secondPageGate;
    const asset = cursor ? galleryAsset("b", "second-map") : galleryAsset("a", "first-map");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        configured: true,
        assets: [asset],
        next_cursor: cursor ? null : "page-2",
      }),
    });
  });
  await page.goto("/");
  await expect(page.locator(".gallery-card")).toHaveCount(1);
  await page.getByRole("button", { name: "Show more routes" }).click();

  await expect(page.getByRole("button", { name: "Loading…" })).toBeDisabled();
  releaseSecondPage();
  await expect(page.locator(".gallery-card")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Show more routes" })).toHaveCount(0);
});

test("only an asset with a saved removal token gets an owner control", async ({ page }) => {
  const owned = galleryAsset("a", "owned-map");
  const anonymous = galleryAsset("b", "other-map");
  await page.addInitScript(
    ({ key, id, token }) => localStorage.setItem(key, JSON.stringify({ [id]: token })),
    { key: removalStorageKey, id: owned.id, token: "c".repeat(64) },
  );
  await replaceGalleryRoute(page, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configured: true, assets: [owned, anonymous], next_cursor: null }),
    }),
  );
  await page.goto("/");

  await expect(page.locator(".gallery-card")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Remove my post" })).toHaveCount(1);
  await expect(page.locator(".gallery-card").first()).toContainText("Remove my post");
});

test("cancelling gallery removal keeps the card and sends no delete request", async ({ page }) => {
  const owned = galleryAsset("a", "owned-map");
  await page.addInitScript(
    ({ key, id, token }) => localStorage.setItem(key, JSON.stringify({ [id]: token })),
    { key: removalStorageKey, id: owned.id, token: "d".repeat(64) },
  );
  let deleteRequests = 0;
  await page.route("**/gallery/delete", (route) => {
    deleteRequests += 1;
    return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
  await replaceGalleryRoute(page, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configured: true, assets: [owned], next_cursor: null }),
    }),
  );
  page.on("dialog", (dialog) => dialog.dismiss());
  await page.goto("/");
  await page.getByRole("button", { name: "Remove my post" }).click();

  expect(deleteRequests).toBe(0);
  await expect(page.locator(".gallery-card")).toHaveCount(1);
});

test("a failed gallery removal preserves the card and shows an actionable error", async ({
  page,
}) => {
  const owned = galleryAsset("a", "owned-map");
  await page.addInitScript(
    ({ key, id, token }) => localStorage.setItem(key, JSON.stringify({ [id]: token })),
    { key: removalStorageKey, id: owned.id, token: "e".repeat(64) },
  );
  await page.route("**/gallery/delete", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "The gallery could not remove this map." }),
    }),
  );
  await replaceGalleryRoute(page, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configured: true, assets: [owned], next_cursor: null }),
    }),
  );
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/");
  await page.getByRole("button", { name: "Remove my post" }).click();

  await expect(page.getByRole("region", { name: "Public gallery" }).getByRole("alert"))
    .toHaveText("The gallery could not remove this map.");
  await expect(page.locator(".gallery-card")).toHaveCount(1);
});

test("gallery consent is cleared when route options change", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.getByText("Share map publicly", { exact: true }).click();
  const consent = page.getByLabel(
    "I understand that this location and its street names will be public.",
  );
  await consent.check();
  await expect(consent).toBeChecked();

  await page.locator('.candidate-card[data-candidate-id="candidate-review"]').click();
  await expect(consent).toHaveCount(0);
  await page.locator('.candidate-card[data-candidate-id="candidate-ready"]').click();
  await page.getByText("Share map publicly", { exact: true }).click();
  await expect(consent).not.toBeChecked();
  await expect(page.getByRole("button", { name: "Publish map" })).toBeDisabled();
});

test("publishing sends only the approved map payload and refreshes the mocked gallery", async ({
  page,
}) => {
  const publishedAsset = galleryAsset("f", "published-map");
  let publishedPayload = null;
  let published = false;
  await replaceGalleryRoute(page, async (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          configured: true,
          assets: published ? [publishedAsset] : [],
          next_cursor: null,
        }),
      });
    }
    publishedPayload = route.request().postDataJSON();
    published = true;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ asset: publishedAsset, removal_token: "f".repeat(64) }),
    });
  });
  await openGeneratedRoute(page);
  await expect(page.locator(".route-map .leaflet-overlay-pane path").first()).toBeVisible();
  await page.getByText("Share map publicly", { exact: true }).click();
  await page
    .getByLabel("I understand that this location and its street names will be public.")
    .check();
  await page.getByRole("button", { name: "Publish map" }).click();

  await expect(page.getByText("Map published.")).toBeVisible();
  expect(publishedPayload.confirm_public_location).toBe(true);
  expect(publishedPayload.publish_token).toBe("publish-candidate-ready-token");
  expect(publishedPayload.image_data_url).toMatch(/^data:image\/png;base64,/);
  expect(publishedPayload).not.toHaveProperty("prompt");
  expect(publishedPayload).not.toHaveProperty("city");
  await expect(page.locator(".gallery-card")).toHaveCount(1);
});

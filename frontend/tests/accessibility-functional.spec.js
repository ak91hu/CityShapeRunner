import { expect, test } from "playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { galleryAsset, installCommonMocks, openGeneratedRoute, replaceGalleryRoute } from "./support/functional-fixtures.js";

async function accessible(page) {
  const audit = await new AxeBuilder({ page }).analyze();
  expect(audit.violations.map(({ id, nodes }) => ({ id, targets: nodes.map(node => node.target) }))).toEqual([]);
}

async function fits(page) {
  expect(await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth)).toBeLessThanOrEqual(1);
}

test.beforeEach(async ({ page }) => { await installCommonMocks(page); });

test("the main action follows the idea directly in reading and keyboard order", async ({ page }) => {
  await page.goto("/");
  const prompt = page.getByLabel("Drawing and location");
  await prompt.focus();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Review request", exact: true })).toBeFocused();
  const ordered = await page.evaluate(() => document.querySelector(".prompt-actions").getBoundingClientRect().bottom
    <= document.querySelector(".idea-picker").getBoundingClientRect().top);
  expect(ordered).toBe(true);
  await accessible(page);
  await prompt.fill("");
  await page.getByRole("button", { name: "Review request", exact: true }).click();
  await expect(prompt).toHaveAttribute("aria-invalid", "true");
  await expect(prompt).toBeFocused();
  await accessible(page);
});

test("checking a request prevents duplicate submissions and recovers cleanly", async ({ page }) => {
  let release;
  let calls = 0;
  await page.route("**/interpret", async route => {
    calls += 1;
    await new Promise(resolve => { release = resolve; });
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({
      drawing_label: "Heart", intent: { shape: "heart", city: "Budapest", sport: "run", distance_km: 8 },
    }) });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Review request", exact: true }).click();
  await expect(page.getByRole("button", { name: "Checking request…", exact: true })).toBeDisabled();
  await expect.poll(() => calls).toBe(1);
  release();
  await expect(page.getByRole("heading", { name: "Check your request" })).toBeFocused();
  await expect(page.getByRole("button", { name: "Find routes", exact: true })).toBeEnabled();
});

test("choosing an example reveals its complete request before review", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".idea-picker")).toContainText("Examples include a place, activity, and distance");
  await page.getByRole("button", { name: "Star", exact: true }).click();
  await expect(page.getByLabel("Drawing and location")).toBeFocused();
  await expect(page.getByLabel("Drawing and location")).toHaveValue("a star bike route in Debrecen, about 20 km");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Review request", exact: true })).toBeFocused();
});

test("all starting methods and optional review settings have accessible controls", async ({ page }) => {
  // Four full axe scans share this case's budget, especially on Firefox/WebKit.
  test.slow();
  await page.route("**/shape-templates", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({ shapes: [{ id: "heart", label: "Heart" }] }) }));
  await page.goto("/");
  for (const name of ["Suggest a shape", "Place on map", "Use image link"]) {
    await page.getByRole("button", { name, exact: true }).click();
    await accessible(page);
    await fits(page);
  }
  await page.getByRole("button", { name: "Review request", exact: true }).click();
  await page.locator(".route-setup-panel > summary").click();
  await page.getByRole("radio", { name: /Address or place/ }).check();
  await accessible(page);
  await fits(page);
});

test("inspiration remains a named region with a native disclosure", async ({ page }) => {
  await page.route("**/occasions*", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({
    country_name: "Hungary", occasions: [{ id: "test-day", name: "Art day", date: "2026-11-01", shape: "heart", reason: "A seasonal drawing", shape_prompt: "a heart", suggested_distance_km: 8 }],
  }) }));
  await page.goto("/");
  const inspiration = page.getByRole("region", { name: "Route inspiration" });
  await expect(inspiration).toBeVisible();
  await inspiration.locator("summary").click();
  await accessible(page);
  await fits(page);
});

test("result selection and route dialogs retain correct semantics and focus", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.locator(".street-route-line").waitFor();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Star in Debrecen");
  const choices = page.getByRole("listitem").filter({ has: page.locator(".candidate-card") });
  await expect(choices).toHaveCount(2);
  await page.locator(".candidate-card").nth(1).focus();
  await page.keyboard.press("Space");
  await expect(page.locator(".candidate-card").nth(1)).toHaveAttribute("aria-pressed", "true");
  await accessible(page);
  await page.getByText("More ways to use this route", { exact: true }).click();
  const trigger = page.getByRole("button", { name: "Record reel", exact: true });
  await trigger.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  for (let i = 0; i < 12; i += 1) {
    await page.keyboard.press("Tab");
    expect(await dialog.evaluate(el => el.contains(document.activeElement))).toBe(true);
  }
  await accessible(page);
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await page.getByRole("link", { name: "Gallery", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Public gallery");
  await accessible(page);
});

test("results reflow across phone, tablet, landscape and desktop widths", async ({ page }) => {
  await openGeneratedRoute(page);
  await page.locator(".street-route-line").waitFor();
  for (const [width, height] of [[320,568],[390,844],[768,1024],[844,390],[1024,768],[1440,900]]) {
    await page.setViewportSize({ width, height });
    await fits(page);
    if (width <= 768) {
      const cards = page.locator(".candidate-card");
      const first = await cards.nth(0).boundingBox();
      const second = await cards.nth(1).boundingBox();
      expect(second.y).toBeGreaterThanOrEqual(first.y + first.height);
      expect(second.x).toBe(first.x);
      expect(second.x + second.width).toBeLessThanOrEqual(width);
    }
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.addStyleTag({ content: "html { font-size: 200%; }" });
  await fits(page);
});

test("the gallery viewer isolates its background and restores focus", async ({ page }) => {
  await replaceGalleryRoute(page, route => route.fulfill({ contentType: "application/json", body: JSON.stringify({
    configured: true, assets: [galleryAsset("a", "first-map")], next_cursor: null,
  }) }));
  await page.goto("/#gallery");
  const trigger = page.getByRole("button", { name: "Open gallery image 1 of 1" });
  await trigger.click();
  await expect(page.getByRole("dialog", { name: "Gallery viewer" })).toBeVisible();
  await accessible(page);
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await expect(page.locator("[inert]")).toHaveCount(0);
});

test("mobile waiting traps focus and releases scrolling when rotated or cancelled", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    const fetch = window.fetch.bind(window);
    window.fetch = (input, options) => {
      if (!String(input).endsWith("/generate")) return fetch(input, options);
      return Promise.resolve(new Response(new ReadableStream({
        start(controller) {
          options.signal.addEventListener("abort", () => controller.error(new DOMException("Cancelled", "AbortError")), { once: true });
          controller.enqueue(new TextEncoder().encode(JSON.stringify({ type: "progress", stage: "preflight", status: "running", preflight_count: 99 }) + "\n"));
        },
      }), { headers: { "Content-Type": "application/x-ndjson" } }));
    };
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Review request", exact: true }).click();
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Finding routes" });
  await expect(dialog).toBeVisible();
  await expect(page.getByRole("heading", { name: "Finding routes" })).toBeFocused();
  for (let i=0;i<5;i+=1) {
    await page.keyboard.press("Tab");
    expect(await dialog.evaluate(el => el.contains(document.activeElement))).toBe(true);
  }
  await accessible(page);
  await page.setViewportSize({ width: 844, height: 390 });
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect.poll(() => page.locator("body").evaluate(el => el.style.overflow)).not.toBe("hidden");
  await fits(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator(".loading-card")).toHaveCount(0);
  await expect.poll(() => page.locator("body").evaluate(el => el.style.overflow)).not.toBe("hidden");
  await expect(page.getByRole("button", { name: "Find routes", exact: true })).toBeVisible();
});

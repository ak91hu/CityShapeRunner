import { expect, test } from "playwright/test";

test("the initial HTML is useful to crawlers and survives a JavaScript failure", async ({
  request,
}) => {
  const response = await request.get("/");
  expect(response.ok()).toBe(true);
  const html = await response.text();

  expect(html).toContain("<h1>Find the best GPS art route on real streets</h1>");
  expect(html).toContain('rel="canonical"');
  expect(html).toContain('property="og:title"');
  expect(html).toContain('type="application/ld+json"');
  expect(html).toContain("Multiple routed candidate comparison");
});

test("robots and sitemap expose the public landing page", async ({ request }) => {
  const [robotsResponse, sitemapResponse] = await Promise.all([
    request.get("/robots.txt"),
    request.get("/sitemap.xml"),
  ]);

  expect(robotsResponse.ok()).toBe(true);
  expect(await robotsResponse.text()).toContain("Sitemap:");
  expect(sitemapResponse.ok()).toBe(true);
  expect(await sitemapResponse.text()).toContain(
    "https://p01--cityshaperunner--vnycn2g6bghl.code.run/",
  );
});

test("the hydrated planner leads with a short, explicit creation path", async ({ page }) => {
  await page.route("**/gallery*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configured: true, assets: [], next_cursor: null }),
    }),
  );
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Create GPS art on real streets" })).toBeVisible();
  const progress = page.getByRole("list", { name: "Route creation progress" });
  await expect(progress).toContainText("Describe your idea");
  await expect(progress).toContainText("Review the request");
  await expect(progress).toContainText("Choose and download");
});

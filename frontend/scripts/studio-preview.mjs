// Local visual QA against an already running Vite server.
// API fixtures keep screenshots reproducible without backend credentials.
import { chromium } from "playwright";
import { installCommonMocks, mockGeneration, reviewAndFindRoutes } from "../tests/support/functional-fixtures.js";

const browser = await chromium.launch();
try {
  for (const [label, width, height] of [["desktop", 1440, 1100], ["mobile", 390, 844], ["narrow", 320, 740]]) {
    const page = await browser.newPage({ viewport: { width, height }, reducedMotion: "reduce" });
    await installCommonMocks(page);
    await mockGeneration(page);
    await page.goto("http://127.0.0.1:4173");
    await page.getByRole("heading", { level: 1 }).waitFor();
    await page.screenshot({ path: `../.tmp/studio-${label}.png`, fullPage: true });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    if (overflow) throw new Error(`${label}: horizontal overflow`);
    if (label !== "narrow") {
      await reviewAndFindRoutes(page);
      await page.locator(".result").waitFor();
      await page.locator(".route-map .leaflet-overlay-pane path").first().waitFor();
      await page.screenshot({ path: `../.tmp/studio-${label}-result.png`, fullPage: true });
      await page.getByRole("link", { name: "Gallery", exact: true }).click();
      await page.locator("#gallery").waitFor();
      await page.screenshot({ path: `../.tmp/studio-${label}-gallery.png`, fullPage: true });
    }
    console.log(`${label}: screenshots captured; no horizontal overflow`);
    await page.close();
  }
} finally {
  await browser.close();
}

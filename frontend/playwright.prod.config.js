import { defineConfig, devices } from "playwright/test";

const PROD_BASE_URL = (
  process.env.PROD_BASE_URL ??
  "https://p01--cityshaperunner--vnycn2g6bghl.code.run"
).replace(/\/$/, "");

export default defineConfig({
  testDir: "./tests",
  testMatch: "prod-gallery.spec.js",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "line",
  timeout: 15 * 60_000,
  expect: { timeout: 30_000 },
  use: {
    ...devices["Desktop Chrome"],
    baseURL: PROD_BASE_URL,
    viewport: { width: 1440, height: 1000 },
    actionTimeout: 30_000,
    navigationTimeout: 60_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});

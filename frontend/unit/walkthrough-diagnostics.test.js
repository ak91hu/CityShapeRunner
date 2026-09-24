import assert from "node:assert/strict";
import test from "node:test";
import { classifyWalkthroughError } from "../src/walkthroughDiagnostics.js";

test("missing MapLibre worker is identified separately from an internet failure", () => {
  const result = classifyWalkthroughError(new Error("Worker failed to load. Check that the worker URL is correct."));
  assert.equal(result.code, "worker_failed");
  assert.match(result.message, /renderer did not start/);
  assert.doesNotMatch(result.message, /connection/i);
});

test("map service rate limits and missing files name the affected resource", () => {
  const limited = classifyWalkthroughError({ status: 429, url: "https://tiles.openfreemap.org/planet/1/2/3.pbf" });
  assert.equal(limited.code, "rate_limited");
  assert.match(limited.message, /tile, HTTP 429/);

  const missing = classifyWalkthroughError({ status: 404, url: "https://tiles.openfreemap.org/styles/liberty" });
  assert.equal(missing.code, "resource_missing");
  assert.match(missing.message, /style, HTTP 404/);
});

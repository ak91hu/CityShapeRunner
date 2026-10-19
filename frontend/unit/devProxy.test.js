import { readFile } from "node:fs/promises";
import assert from "node:assert/strict";
import test from "node:test";
import config from "../vite.config.js";

test("the default development server forwards every client API resource to FastAPI", async () => {
  const source = await readFile(new URL("../src/api.js", import.meta.url), "utf8");
  const paths = [...source.matchAll(/request\(["'`]([^"'`?]+)/g)].map(match => match[1]);
  assert.ok(paths.length >= 20, "Read the real API request sites");
  for (const path of paths) {
    const prefix = Object.keys(config.server.proxy).find(key => path === key || path.startsWith(`${key}/`));
    assert.equal(config.server.proxy[prefix], "http://127.0.0.1:8000", path);
  }
  assert.equal(config.server.proxy["/src"], undefined);
  assert.equal(config.server.proxy["/assets"], undefined);
});

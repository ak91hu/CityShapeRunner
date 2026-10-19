import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { ApiError, generate } from "../src/api.js";

const previousWindow = globalThis.window;
const previousFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = previousFetch;
  if (previousWindow === undefined) delete globalThis.window;
  else globalThis.window = previousWindow;
});

function mockStream(chunks, { close = true, cancel = () => {} } = {}) {
  globalThis.window = globalThis;
  const body = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk);
      if (close) controller.close();
    },
    cancel,
  });
  globalThis.fetch = async () => new Response(body, { headers: {
    "Content-Type": "application/x-ndjson", "X-Request-ID": "stream-test", "Retry-After": "5",
  } });
  return body;
}

test("generation retains split UTF-8, progress and a final line without a newline", async () => {
  const bytes = new TextEncoder().encode([
    JSON.stringify({ type: "progress", stage: "snap", status: "running" }),
    JSON.stringify({ type: "preview", points: [[47, 19], [47.01, 19.01]] }),
    JSON.stringify({ type: "result", data: { city: "Pécs", snapped: true } }),
  ].join("\n"));
  mockStream([...bytes].map(byte => new Uint8Array([byte])));
  const updates = [];
  assert.deepEqual(await generate("heart", { onUpdate: event => updates.push(event) }),
    { city: "Pécs", snapped: true });
  assert.deepEqual(updates.map(event => event.type), ["progress", "preview"]);
});

for (const payload of ["not-json", "null", "[]", '{"type":"result","data":42}']) {
  test(`invalid stream is diagnosed as a response error and cancelled: ${payload}`, async () => {
    let cancelled = 0;
    const body = mockStream([new TextEncoder().encode(payload + "\n")],
      { close: false, cancel: () => { cancelled += 1; } });
    await assert.rejects(generate("heart"), error => error instanceof ApiError
      && error.category === "response" && error.requestId === "stream-test");
    assert.equal(cancelled, 1);
    assert.equal(body.locked, false);
  });
}

test("a streamed service error retains correlation and survives failed cleanup", async () => {
  const body = mockStream([new TextEncoder().encode(JSON.stringify({
    type: "error", status: 503, detail: "No connected street route.",
  }) + "\n")], { close: false, cancel: () => { throw new Error("Already disconnected"); } });
  await assert.rejects(generate("heart"), error => error instanceof ApiError
    && error.status === 503 && error.category === "service"
    && error.requestId === "stream-test" && error.retryAfter === "5"
    && error.message === "No connected street route.");
  assert.equal(body.locked, false);
});

test("a stream without a final result cannot become a successful route", async () => {
  mockStream([new TextEncoder().encode('{"type":"progress","stage":"snap"}\n')]);
  await assert.rejects(generate("heart"), error => error instanceof ApiError && error.category === "response");
});

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, { signal, timeoutMs = 15_000, ...options } = {}) {
  const controller = new AbortController();
  let timedOut = false;

  const forwardAbort = () => controller.abort(signal?.reason);
  if (signal?.aborted) {
    forwardAbort();
  } else {
    signal?.addEventListener("abort", forwardAbort, { once: true });
  }

  const timeoutId = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    const response = await fetch(`${BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...options.headers,
      },
    });
    const data = await response.json().catch(() => null);

    if (!response.ok) {
      const detail = typeof data?.detail === "string" ? data.detail : null;
      throw new ApiError(
        detail || `The route service returned an error (${response.status}).`,
        response.status,
      );
    }
    if (data == null) {
      throw new ApiError("The route service returned an empty response.", response.status);
    }

    return data;
  } catch (error) {
    if (timedOut) {
      throw new ApiError("The route service took too long to respond. Please try again.");
    }
    if (signal?.aborted) {
      throw new DOMException("The request was cancelled.", "AbortError");
    }
    if (error instanceof ApiError) throw error;
    if (error?.name === "AbortError") throw error;
    throw new ApiError("The route service is unavailable. Check your connection and try again.");
  } finally {
    window.clearTimeout(timeoutId);
    signal?.removeEventListener("abort", forwardAbort);
  }
}

export function health(options = {}) {
  return request("/health", { ...options, timeoutMs: 7_000 });
}

export function generate(prompt, options = {}) {
  return request("/generate", {
    ...options,
    timeoutMs: 180_000,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
}

export function editRoute(payload, options = {}) {
  return request("/edit-route", {
    ...options,
    timeoutMs: 180_000,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function recordRouteAcceptance(payload, options = {}) {
  return request("/route-acceptance", {
    ...options,
    timeoutMs: 7_000,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

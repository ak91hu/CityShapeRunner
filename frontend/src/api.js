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
        detail || `Something went wrong while planning your route (${response.status}).`,
        response.status,
      );
    }
    if (data == null) {
      throw new ApiError("We didn’t receive a route. Please try again.", response.status);
    }

    return data;
  } catch (error) {
    if (timedOut) {
      throw new ApiError("This is taking longer than expected. Please try again.");
    }
    if (signal?.aborted) {
      throw new DOMException("The request was cancelled.", "AbortError");
    }
    if (error instanceof ApiError) throw error;
    if (error?.name === "AbortError") throw error;
    throw new ApiError("We can’t reach the route planner. Check your connection and try again.");
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

export function listGallery({ cursor = null, limit = 24, ...options } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set("cursor", cursor);
  return request(`/gallery?${params}`, { ...options, timeoutMs: 15_000 });
}

export function publishGalleryImage(payload, options = {}) {
  return request("/gallery", {
    ...options,
    timeoutMs: 45_000,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function removeGalleryImage(payload, options = {}) {
  return request("/gallery/delete", {
    ...options,
    timeoutMs: 15_000,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

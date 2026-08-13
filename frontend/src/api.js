const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(
  path,
  { signal, timeoutMs = 15_000, timeoutMessage, ...options } = {},
) {
  const controller = new AbortController();
  let timedOut = false;
  let timeoutId = null;

  const forwardAbort = () => controller.abort(signal?.reason);
  if (signal?.aborted) {
    forwardAbort();
  } else {
    signal?.addEventListener("abort", forwardAbort, { once: true });
  }

  if (Number.isFinite(timeoutMs) && timeoutMs > 0) {
    timeoutId = window.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
  }

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
      throw new ApiError(
        timeoutMessage || "The service didn’t respond in time. Please try again.",
      );
    }
    if (signal?.aborted) {
      throw new DOMException("The request was cancelled.", "AbortError");
    }
    if (error instanceof ApiError) throw error;
    if (error?.name === "AbortError") throw error;
    throw new ApiError("We can’t reach the route planner. Check your connection and try again.");
  } finally {
    if (timeoutId !== null) window.clearTimeout(timeoutId);
    signal?.removeEventListener("abort", forwardAbort);
  }
}

export function health(options = {}) {
  return request("/health", { ...options, timeoutMs: 7_000 });
}

export function generate(prompt, options = {}) {
  const { payload = {}, ...requestOptions } = options;
  const usesImage = Boolean(payload.reference_image_url);
  return request("/generate", {
    ...requestOptions,
    timeoutMs: usesImage ? 120_000 : 180_000,
    timeoutMessage: usesImage
      ? "The image route took too long. Try a simpler image or retry; the planner has stopped safely."
      : "Route planning took too long. Try a simpler drawing or a shorter distance.",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, ...payload }),
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

export function requestTimedReadiness(payload, options = {}) {
  return request("/timed-readiness", {
    ...options,
    timeoutMs: 8_000,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function createMuralPlan(payload, options = {}) {
  return request("/mural-plan", {
    ...options,
    timeoutMs: 20_000,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function repairRecognition(payload, options = {}) {
  return request("/recognition-repair", {
    ...options,
    timeoutMs: 180_000,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function analyseInkproof(payload, options = {}) {
  return request("/inkproof-analysis", {
    ...options,
    timeoutMs: 30_000,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

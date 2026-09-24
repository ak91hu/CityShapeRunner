const DIAGNOSTIC_URL = "/walkthrough-diagnostics";

function resourceFromUrl(url) {
  if (!url) return "unknown";
  if (url.includes("maplibre-gl-worker")) return "worker";
  if (url.includes("/styles/")) return "style";
  if (url.includes("/sprites/")) return "sprite";
  if (url.includes("/fonts/")) return "glyph";
  if (url.includes(".pbf") || url.includes("/planet")) return "tile";
  return "unknown";
}

export function classifyWalkthroughError(error, phase = "loading") {
  const cause = error?.error ?? error;
  const detail = String(cause?.message ?? cause ?? "Unknown map error")
    .replace(/https?:\/\/\S+/g, "[map URL]")
    .replace(/[\r\n\t]/g, " ")
    .slice(0, 240);
  const url = String(cause?.url ?? "");
  const resource = resourceFromUrl(url);
  const httpStatus = Number.isInteger(cause?.status) ? cause.status : null;
  let code = "map_error";
  let message = "The 3D map could not finish loading. Reload the page and try again.";

  if (/worker failed to load|failed to fetch worker script/i.test(detail)) {
    code = "worker_failed";
    message = "The 3D map renderer did not start because its processing file failed to load. Reload the page to fetch the latest version.";
  } else if (/timed out waiting for map resources/i.test(detail)) {
    code = "timeout";
    message = "The 3D map did not finish loading within 15 seconds. The map service or browser may be blocking a required file; reload to try again.";
  } else if (httpStatus === 429) {
    code = "rate_limited";
    message = `The free map service is limiting requests (${resource}, HTTP 429). Please try again in a few minutes.`;
  } else if (httpStatus === 404) {
    code = "resource_missing";
    message = `A required map file is missing (${resource}, HTTP 404). Reload the page; if this continues, report the error.`;
  } else if (httpStatus >= 500) {
    code = "service_unavailable";
    message = `The map data service is temporarily unavailable (${resource}, HTTP ${httpStatus}). Please try again later.`;
  } else if (/failed to fetch|networkerror|load failed/i.test(detail)) {
    code = "request_blocked";
    message = `A map request was blocked or failed (${resource}). Check browser privacy extensions or network filtering, then reload.`;
  } else if (resource === "tile" || resource === "sprite" || resource === "glyph") {
    code = "map_data_failed";
    message = `Some map data could not load (${resource}${httpStatus ? `, HTTP ${httpStatus}` : ""}). The route may be incomplete; reload to try again.`;
  } else if (phase === "rendering") {
    code = "render_failed";
    message = "The 3D map could not be drawn on this device. Reload the page or try a different browser.";
  }

  return { code, phase, resource, http_status: httpStatus, detail, message };
}

export function reportWalkthroughError(diagnostic) {
  const { message, ...logData } = diagnostic;
  console.error("[walkthrough]", logData);
  try {
    void fetch(DIAGNOSTIC_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(logData),
      keepalive: true,
    }).catch((error) => console.warn("[walkthrough] Diagnostic delivery failed:", error));
  } catch (error) {
    console.warn("[walkthrough] Diagnostic delivery failed:", error);
  }
}

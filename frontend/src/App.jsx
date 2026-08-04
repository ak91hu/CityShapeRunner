import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  editRoute,
  generate as generateRoute,
  listGallery,
  publishGalleryImage,
  recordRouteAcceptance,
  removeGalleryImage,
} from "./api.js";

const RouteMap = lazy(() => import("./RouteMap.jsx"));
const GALLERY_REMOVAL_STORAGE_KEY = "gps-art-gallery-removal-tokens-v1";

const QUICK_IDEAS = [
  { glyph: "♥", label: "Heart", category: "Simple shapes", featured: true, prompt: "a heart run in Budapest, about 8 km" },
  { glyph: "★", label: "Star", category: "Simple shapes", featured: true, prompt: "a star bike route in Debrecen, about 20 km" },
  { glyph: "○", label: "Circle", category: "Simple shapes", featured: true, prompt: "a circle run in Kecskemét, about 8 km" },
  { glyph: "◆", label: "Diamond", category: "Simple shapes", featured: true, prompt: "a diamond run in Szombathely, about 8 km" },
  { glyph: "△", label: "Triangle", category: "Simple shapes", featured: true, prompt: "a triangle run in Tatabánya, about 10 km" },
  { glyph: "□", label: "Square", category: "Simple shapes", featured: true, prompt: "a square run in Szombathely, about 8 km" },
  { glyph: "∞", label: "Infinity", category: "Simple shapes", featured: true, prompt: "an infinity run in Szeged, about 10 km" },
  { glyph: "➜", label: "Arrow", category: "Simple shapes", featured: true, prompt: "an arrow run in Siófok, about 8 km" },
  { glyph: "✚", label: "Cross", category: "Simple shapes", featured: true, prompt: "a cross run in Nyíregyháza, about 8 km" },
  { glyph: "ϟ", label: "Lightning", category: "Simple shapes", featured: true, prompt: "a lightning run in Cegléd, about 8 km" },
  { glyph: "∿", label: "Wave", category: "Simple shapes", featured: true, prompt: "a wave run in Siófok, about 8 km" },
  { glyph: "☾", label: "Moon", category: "Simple shapes", featured: true, prompt: "a moon run in Kecskemét, about 8 km" },
  { glyph: "✿", label: "Flower", category: "Nature", prompt: "a flower run in Debrecen, about 12 km" },
  { glyph: "♣", label: "Tree", category: "Nature", prompt: "a tree run in Tatabánya, about 10 km" },
  { glyph: "⌃", label: "Mountain", category: "Nature", prompt: "a mountain run in Miskolc, about 10 km" },
  { glyph: "Ƹ", label: "Butterfly", category: "Nature", prompt: "a butterfly run in Kecskemét, about 10 km" },
  { glyph: "⌃", label: "Cat", category: "Animals", prompt: "a cat run in Tatabánya, about 10 km" },
  { glyph: "⌁", label: "Dog", category: "Animals", prompt: "a dog run in Tatabánya, about 10 km" },
  { glyph: "♛", label: "Crown", category: "Symbols", prompt: "a crown run in Székesfehérvár, about 10 km" },
  { glyph: "A", label: "Letter A", category: "Letters, numbers & text", prompt: "draw the letter A while running in Miskolc, about 10 km" },
  { glyph: "C", label: "Letter C", category: "Letters, numbers & text", prompt: "draw the letter C while running in Szeged, about 8 km" },
  { glyph: "L", label: "Letter L", category: "Letters, numbers & text", prompt: "draw the letter L while running in Kecskemét, about 8 km" },
  { glyph: "M", label: "Letter M", category: "Letters, numbers & text", prompt: "draw the letter M while running in Debrecen, about 10 km" },
  { glyph: "N", label: "Letter N", category: "Letters, numbers & text", prompt: "draw the letter N while running in Nyíregyháza, about 10 km" },
  { glyph: "S", label: "Letter S", category: "Letters, numbers & text", prompt: "draw the letter S while running in Szeged, about 10 km" },
  { glyph: "U", label: "Letter U", category: "Letters, numbers & text", prompt: "draw the letter U while running in Győr, about 10 km" },
  { glyph: "V", label: "Letter V", category: "Letters, numbers & text", prompt: "draw the letter V while running in Veszprém, about 8 km" },
  { glyph: "Z", label: "Letter Z", category: "Letters, numbers & text", prompt: "draw the letter Z while running in Zalaegerszeg, about 10 km" },
  { glyph: "2", label: "Number 2", category: "Letters, numbers & text", prompt: "draw the number 2 while running in Eger, about 8 km" },
  { glyph: "7", label: "Number 7", category: "Letters, numbers & text", prompt: "draw the number 7 while running in Debrecen, about 8 km" },
  { glyph: "42", label: "Number 42", category: "Letters, numbers & text", prompt: "draw the number 42 while cycling in Eger, about 20 km" },
  { glyph: "GPS", label: "Text GPS", category: "Letters, numbers & text", prompt: "write GPS while cycling in Budapest, about 25 km" },
];

const IDEA_CATEGORIES = ["Simple shapes", "Nature", "Animals", "Symbols", "Letters, numbers & text"];
const FEATURED_IDEAS = QUICK_IDEAS.filter((idea) => idea.featured);

const SUGGEST_CITIES = [
  "Budapest",
  "Debrecen",
  "Szeged",
  "Miskolc",
  "Pécs",
  "Győr",
  "Kecskemét",
  "Nyíregyháza",
  "Eger",
  "Sopron",
  "Szombathely",
  "Zalaegerszeg",
  "Kaposvár",
  "Szekszárd",
  "Békéscsaba",
  "Cegléd",
  "Székesfehérvár",
  "Siófok",
  "Veszprém",
  "Keszthely",
  "Tapolca",
  "Tatabánya",
  "Vonyarcvashegy",
];

const PROMPT_LIMIT = 320;

function formatMetric(value, digits = 2) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
}

function formatPercent(value) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${Math.round(value * 100)}%`
    : "—";
}

function formatSigned(value, digits = 2, suffix = "") {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}${suffix}`;
}

function formatGateValue(gate) {
  if (!gate?.applies) return "Not required";
  if (typeof gate.value === "boolean") return gate.value ? "Yes" : "No";
  if (typeof gate.value === "number") return formatPercent(gate.value);
  return normaliseLabel(gate.value);
}

function formatGateMinimum(gate) {
  if (!gate?.applies || typeof gate.minimum === "boolean") return "";
  if (typeof gate.minimum === "number") return `minimum ${formatPercent(gate.minimum)}`;
  return gate.minimum ? `must be ${normaliseLabel(gate.minimum)}` : "";
}

function explainGateResult(gate) {
  if (!gate?.applies) return "This check does not apply to this route.";
  if (typeof gate.value === "boolean") {
    return gate.passed
      ? "The required condition was observed."
      : "The required condition was not observed, so manual inspection matters.";
  }
  if (typeof gate.value === "number" && typeof gate.minimum === "number") {
    const difference = Math.round(Math.abs(gate.value - gate.minimum) * 100);
    return gate.passed
      ? `${difference} percentage point${difference === 1 ? "" : "s"} above the automatic target; higher is better.`
      : `${difference} percentage point${difference === 1 ? "" : "s"} below the automatic target; this signals visible distortion, not a probability of failure.`;
  }
  return gate.passed
    ? "This route matches the selected value."
    : "This route does not match the selected value.";
}

function normaliseLabel(value) {
  if (!value) return "—";
  return String(value)
    .replaceAll("_", " ")
    .replace(/(^|[\s-])(\p{L})/gu, (_, prefix, letter) => `${prefix}${letter.toUpperCase()}`);
}

function safeFilePart(value) {
  const cleaned = String(value || "gps-art-route")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 48);
  return cleaned || "gps-art-route";
}

function saveFile(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

function readGalleryRemovalTokens() {
  try {
    const stored = JSON.parse(
      window.localStorage.getItem(GALLERY_REMOVAL_STORAGE_KEY) ?? "{}",
    );
    if (!stored || typeof stored !== "object" || Array.isArray(stored)) return {};
    return Object.fromEntries(
      Object.entries(stored).filter(
        ([publicId, token]) => publicId && typeof token === "string" && token,
      ),
    );
  } catch {
    return {};
  }
}

function rememberGalleryRemovalToken(publicId, token) {
  const next = { ...readGalleryRemovalTokens(), [publicId]: token };
  try {
    window.localStorage.setItem(GALLERY_REMOVAL_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // A private-browsing/storage failure must not turn a successful upload
    // into a false publication error or encourage a duplicate retry.
  }
  return next;
}

function forgetGalleryRemovalToken(publicId) {
  const next = { ...readGalleryRemovalTokens() };
  delete next[publicId];
  try {
    window.localStorage.setItem(GALLERY_REMOVAL_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // The server deletion still succeeded; keep the UI truthful for this session.
  }
  return next;
}

function mergeGalleryAssets(current, received, { replace, publishedAsset, removedIds }) {
  const visibleReceived = (Array.isArray(received) ? received : []).filter(
    (asset) => asset?.id && !removedIds.has(asset.id),
  );
  let next = replace ? visibleReceived : [...current, ...visibleReceived];
  if (publishedAsset?.id && !removedIds.has(publishedAsset.id)) {
    next = [publishedAsset, ...next.filter((asset) => asset.id !== publishedAsset.id)];
  }
  const seen = new Set();
  return next.filter((asset) => {
    if (!asset?.id || seen.has(asset.id) || removedIds.has(asset.id)) return false;
    seen.add(asset.id);
    return true;
  });
}

function sampleControlPoints(points, maximum = 18) {
  const valid = (Array.isArray(points) ? points : []).filter(
    (point) =>
      Array.isArray(point) &&
      Number.isFinite(point[0]) &&
      Number.isFinite(point[1]),
  );
  if (valid.length <= maximum) return valid.map((point) => [...point]);
  const indices = Array.from(
    { length: maximum },
    (_, index) => Math.round((index * (valid.length - 1)) / (maximum - 1)),
  );
  return [...new Set(indices)].map((index) => [...valid[index]]);
}

function MetricCard({ label, value, detail, tone = "neutral" }) {
  return (
    <div className={`metric metric--${tone}`}>
      <dt>{label}</dt>
      <dd>{value}</dd>
      {detail && <dd className="metric-detail">{detail}</dd>}
    </div>
  );
}

function LoadingState({ onCancel }) {
  return (
    <section className="loading-card" aria-live="polite" aria-busy="true">
      <div className="route-loader" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </div>
      <div>
        <p className="eyebrow">Building route candidates</p>
        <h2>Testing your drawing against real streets…</h2>
        <p>
          We’re comparing scale, orientation, and nearby street grids. Detailed ideas can take a
          little longer.
        </p>
      </div>
      <button type="button" className="button button--quiet" onClick={onCancel}>
        Stop
      </button>
    </section>
  );
}

function GallerySection({ refreshKey = 0, publishedAsset = null }) {
  const [assets, setAssets] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [configured, setConfigured] = useState(true);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [removalTokens, setRemovalTokens] = useState(readGalleryRemovalTokens);
  const removedAssetIdsRef = useRef(new Set());

  const loadGalleryPage = useCallback(async (cursor = null, replace = false) => {
    if (replace) setLoading(true);
    else setLoadingMore(true);
    setError("");
    try {
      const response = await listGallery({ cursor, limit: 24 });
      setConfigured(response.configured !== false);
      setAssets((current) =>
        mergeGalleryAssets(current, response.assets, {
          replace,
          publishedAsset,
          removedIds: removedAssetIdsRef.current,
        }),
      );
      setNextCursor(response.next_cursor ?? null);
    } catch (galleryError) {
      setError(galleryError.message || "The anonymous map gallery could not be loaded.");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [publishedAsset]);

  useEffect(() => {
    setRemovalTokens(readGalleryRemovalTokens());
    loadGalleryPage(null, true);
  }, [loadGalleryPage, refreshKey]);

  const removeAsset = useCallback(async (asset) => {
    const token = removalTokens[asset.id];
    if (!token || !window.confirm("Remove this map screenshot from the public gallery?")) return;
    setError("");
    try {
      await removeGalleryImage({ public_id: asset.id, removal_token: token });
      removedAssetIdsRef.current.add(asset.id);
      setAssets((current) => current.filter((item) => item.id !== asset.id));
      setRemovalTokens(forgetGalleryRemovalToken(asset.id));
    } catch (removalError) {
      setError(removalError.message || "The gallery image could not be removed.");
    }
  }, [removalTokens]);

  return (
    <section className="gallery" id="gallery" aria-labelledby="gallery-title">
      <div className="section-heading gallery-heading">
        <div>
          <p className="eyebrow">Anonymous community maps</p>
          <h2 id="gallery-title">GPS art gallery</h2>
          <p>
            Public route screenshots preserve the map, street names, and OpenStreetMap
            attribution—without prompts, profiles, or activity histories.
          </p>
        </div>
        <a className="button button--quiet" href="#route-designer">
          Create an artwork
        </a>
      </div>

      {loading && (
        <div className="gallery-state" role="status">
          Loading public map screenshots…
        </div>
      )}
      {!loading && !configured && (
        <div className="gallery-state">
          <strong>The gallery is ready for Cloudinary credentials.</strong>
          <span>Route generation and downloads remain available.</span>
        </div>
      )}
      {error && (
        <p className="gallery-error" role="alert">
          {error}
        </p>
      )}
      {!loading && configured && assets.length === 0 && !error && (
        <div className="gallery-state">
          <strong>No public map artwork yet.</strong>
          <span>Generate a route and publish its map screenshot to start the gallery.</span>
        </div>
      )}
      {assets.length > 0 && (
        <div className="gallery-grid">
          {assets.map((asset) => (
            <article className="gallery-card" key={asset.id}>
              <a href={asset.image_url} target="_blank" rel="noreferrer">
                <img
                  src={asset.image_url}
                  alt="Anonymous GPS art route on an OpenStreetMap street map"
                  loading="lazy"
                  width={asset.width || undefined}
                  height={asset.height || undefined}
                />
              </a>
              <div>
                <span>Map data © OpenStreetMap contributors</span>
                {removalTokens[asset.id] && (
                  <button type="button" onClick={() => removeAsset(asset)}>
                    Remove mine
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      {nextCursor && (
        <button
          type="button"
          className="button button--secondary gallery-more"
          onClick={() => loadGalleryPage(nextCursor, false)}
          disabled={loadingMore}
        >
          {loadingMore ? "Loading…" : "Load more map artwork"}
        </button>
      )}
      <p className="gallery-attribution">
        Map data ©{" "}
        <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
          OpenStreetMap contributors
        </a>
        .
      </p>
    </section>
  );
}

function ResultPanel({ result, onDownload, onGalleryPublished, focusRef }) {
  const candidates = result.candidates ?? [];
  const [selectedCandidateId, setSelectedCandidateId] = useState(
    candidates[0]?.id ?? "best",
  );
  const [editing, setEditing] = useState(false);
  const [controlPoints, setControlPoints] = useState([]);
  const [editedRoute, setEditedRoute] = useState(null);
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState("");
  const [editDirty, setEditDirty] = useState(false);
  const [acceptedRouteIds, setAcceptedRouteIds] = useState(() => new Set());
  const [galleryConsent, setGalleryConsent] = useState(false);
  const [galleryBusy, setGalleryBusy] = useState(false);
  const [galleryError, setGalleryError] = useState("");
  const [publishedAsset, setPublishedAsset] = useState(null);
  const mapCaptureRef = useRef(null);

  useEffect(() => {
    setSelectedCandidateId(candidates[0]?.id ?? "best");
    setEditing(false);
    setControlPoints([]);
    setEditedRoute(null);
    setEditError("");
    setEditDirty(false);
    setAcceptedRouteIds(new Set());
    setGalleryConsent(false);
    setGalleryBusy(false);
    setGalleryError("");
    setPublishedAsset(null);
  }, [result.request_id, result.prompt]);

  const selectedCandidate =
    candidates.find((candidate) => candidate.id === selectedCandidateId) ??
    candidates[0] ??
    null;
  const activeRoute =
    editedRoute ??
    selectedCandidate ?? {
      id: "best",
      shape_name: result.shape?.name,
      points_preview: result.points_preview,
      ideal_preview: result.ideal_preview,
      distance_km: result.distance_km,
      snapped: result.snapped,
      closed: result.shape?.closed,
      target_distance_km: result.intent?.distance_km,
      validation: result.validation,
      below_recommended: result.below_threshold,
      verification: result.route_verification,
      details: result.route_details,
      gpx: result.gpx,
      tcx: result.tcx,
      gallery_publish_token: result.gallery_publish_token,
    };
  const validation = activeRoute.validation ?? result.validation;
  const verification = activeRoute.verification ?? result.route_verification;
  const routeDetails = activeRoute.details ?? result.route_details;
  const distanceDetails = routeDetails?.distance ?? {};
  const routingDetails = routeDetails?.routing ?? {};
  const placementDetails = routeDetails?.placement ?? {};
  const deviationDetails = routeDetails?.deviation ?? {};
  const score = validation?.score;
  const automaticChecksPassed = verification
    ? Boolean(verification.passed)
    : Boolean(activeRoute.snapped) && !Boolean(activeRoute.below_recommended);
  const activeRouteId = String(activeRoute.id ?? "best");
  const userAccepted = acceptedRouteIds.has(activeRouteId);
  const exportReady = automaticChecksPassed || userAccepted;
  const exportBlockedByPendingEdits = editing && editDirty;
  const qualityTone = score == null ? "neutral" : automaticChecksPassed ? "good" : "warn";
  const shapeName = normaliseLabel(activeRoute.shape_name ?? result.shape?.name);
  const fitDecision = result.fit_decision;
  const requestedShape = normaliseLabel(
    fitDecision?.requested_shape ?? result.requested_shape ?? result.shape?.name,
  );
  const city = result.intent?.city ? normaliseLabel(result.intent.city) : "your selected area";
  const historyRows = (result.history ?? []).filter((entry) => Number.isFinite(entry.score));
  const auditRows = Array.isArray(result.candidate_audit) ? result.candidate_audit : [];
  const candidateSummary = result.candidate_summary ?? {};
  const auditedCount = Number.isFinite(candidateSummary.audited_count)
    ? candidateSummary.audited_count
    : candidates.length;
  const reviewCount = Number.isFinite(candidateSummary.review_count)
    ? candidateSummary.review_count
    : Number.isFinite(candidateSummary.rejected_selected_shape_count)
      ? candidateSummary.rejected_selected_shape_count
    : 0;
  const otherShapeCount = Number.isFinite(candidateSummary.other_shape_count)
    ? candidateSummary.other_shape_count
    : 0;
  const issueList = [
    ...new Set([
      ...(validation?.issues ?? []),
      ...(editedRoute?.warnings ?? []),
      ...(result.errors ?? []),
    ]),
  ];
  const stateLabel = automaticChecksPassed
    ? "Automatic checks passed"
    : userAccepted
      ? "Accepted by you"
      : activeRoute.snapped
        ? "Ready for your review"
        : "Guide — review required";
  const canPublishGallery = Boolean(
    activeRoute.gallery_publish_token &&
    activeRoute.snapped &&
    exportReady &&
    !editedRoute &&
    !editing,
  );

  useEffect(() => {
    setGalleryConsent(false);
    setGalleryError("");
    setPublishedAsset(null);
  }, [activeRouteId]);

  const resetEditor = useCallback(() => {
    setControlPoints(sampleControlPoints(activeRoute.points_preview));
    setEditError("");
    setEditDirty(false);
  }, [activeRoute.points_preview]);

  const handleEditPoint = useCallback(
    (index, point) => {
      setEditDirty(true);
      setControlPoints((current) => {
        const next = current.map((item) => [...item]);
        next[index] = point;
        if (activeRoute.closed && next.length > 1) {
          if (index === 0) next[next.length - 1] = [...point];
          if (index === next.length - 1) next[0] = [...point];
        }
        return next;
      });
    },
    [activeRoute.closed],
  );

  const rerouteEdited = useCallback(async () => {
    if (controlPoints.length < 2 || editBusy) return;
    setEditBusy(true);
    setEditError("");
    try {
      const response = await editRoute({
        control_points: controlPoints,
        reference_points:
          activeRoute.ideal_preview?.length > 1
            ? activeRoute.ideal_preview
            : controlPoints,
        sport: result.intent?.sport === "bike" ? "bike" : "run",
        closed: Boolean(activeRoute.closed),
        target_distance_km:
          activeRoute.target_distance_km ?? result.intent?.distance_km ?? null,
        name: `${shapeName} in ${city}`,
        shape_name: activeRoute.shape_name ?? result.shape?.name ?? "edited",
      });
      const editedRouteId = `${selectedCandidate?.id ?? "best"}-edited`;
      setAcceptedRouteIds((current) => {
        const next = new Set(current);
        next.delete(editedRouteId);
        return next;
      });
      setEditedRoute({
        ...activeRoute,
        id: editedRouteId,
        points_preview: response.points_preview,
        distance_km: response.distance_km,
        snapped: response.snapped,
        validation: response.validation,
        verification: response.route_verification,
        details: response.route_details,
        below_recommended:
          response.below_recommended ??
          !(
            response.snapped &&
            response.validation?.score >= 0.72 &&
            response.validation?.shape_fidelity >= 0.7 &&
            response.validation?.distance_fit >= 0.6 &&
            response.validation?.closure >= 0.6
          ),
        gpx: response.gpx,
        tcx: response.tcx,
        warnings: response.warnings,
      });
      setControlPoints(sampleControlPoints(response.points_preview));
      setEditDirty(false);
    } catch (error) {
      setEditError(error.message || "The edited guide could not be re-routed.");
    } finally {
      setEditBusy(false);
    }
  }, [
    activeRoute,
    city,
    controlPoints,
    editBusy,
    result.intent,
    selectedCandidate?.id,
    shapeName,
  ]);

  const publishMapScreenshot = useCallback(async () => {
    if (!canPublishGallery || !galleryConsent || galleryBusy) return;
    setGalleryBusy(true);
    setGalleryError("");
    try {
      const imageDataUrl = await mapCaptureRef.current?.capturePng();
      if (!imageDataUrl) throw new Error("The route map is not ready to capture yet.");
      const response = await publishGalleryImage({
        image_data_url: imageDataUrl,
        publish_token: activeRoute.gallery_publish_token,
        confirm_public_location: true,
      });
      rememberGalleryRemovalToken(response.asset.id, response.removal_token);
      setPublishedAsset(response.asset);
      onGalleryPublished?.(response.asset);
    } catch (publishError) {
      setGalleryError(
        publishError.message || "The map screenshot could not be published.",
      );
    } finally {
      setGalleryBusy(false);
    }
  }, [
    activeRoute.gallery_publish_token,
    canPublishGallery,
    galleryBusy,
    galleryConsent,
    onGalleryPublished,
  ]);

  return (
    <section
      ref={focusRef}
      className="result"
      aria-labelledby="result-title"
      tabIndex="-1"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">
            {automaticChecksPassed
              ? "Route checks passed"
              : "Selected-shape route for review"}
          </p>
          <h2 id="result-title">
            {shapeName} in {city}
          </h2>
          {result.request_id && (
            <p className="debug-id">
              Debug ID: <code>{result.request_id}</code>
            </p>
          )}
        </div>
        <span
          className={`route-state route-state--${automaticChecksPassed ? "good" : "warn"}`}
        >
          <span aria-hidden="true">{automaticChecksPassed || userAccepted ? "✓" : "!"}</span>
          {stateLabel}
        </span>
      </div>

      <div className="result-layout">
        <div className="map-card">
          <div className="candidate-toolbar">
            <label htmlFor="route-candidate">Selected-shape route</label>
            <select
              id="route-candidate"
              value={selectedCandidate?.id ?? "best"}
              onChange={(event) => {
                setSelectedCandidateId(event.target.value);
                setEditing(false);
                setEditedRoute(null);
                setControlPoints([]);
                setEditError("");
                setEditDirty(false);
                setGalleryConsent(false);
                setGalleryError("");
                setPublishedAsset(null);
              }}
            >
              {candidates.length > 0 ? (
                candidates.map((candidate, index) => (
                  <option key={candidate.id} value={candidate.id}>
                    {index + 1}. {normaliseLabel(candidate.shape_name)} ·{" "}
                    {formatPercent(candidate.validation?.score)} ·{" "}
                    {formatMetric(candidate.distance_km)} km ·{" "}
                    {candidate.verification?.passed ? "Checks passed" : "Review"}
                  </option>
                ))
              ) : (
                <option value="best">Best selected-shape route</option>
              )}
            </select>
            <span>
              {candidates.length > 0
                ? `${candidates.length} selected-shape route${candidates.length === 1 ? "" : "s"} shown; ${candidateSummary.verified_count ?? candidateSummary.accepted_count ?? 0} passed checks, ${reviewCount} for review`
                : `${auditedCount} evaluated; the best route remains available for review`}
            </span>
          </div>

          {(activeRoute.points_preview ?? []).length > 0 ? (
            <Suspense
              fallback={
                <div className="route-map route-map--empty" role="status">
                  <span className="map-spinner" aria-hidden="true" />
                  <strong>Loading street route…</strong>
                </div>
              }
            >
              <RouteMap
                ref={mapCaptureRef}
                points={activeRoute.points_preview}
                idealPoints={activeRoute.ideal_preview ?? result.ideal_preview}
                landmarkPoints={
                  activeRoute.landmark_preview ?? result.landmark_preview
                }
                editPoints={controlPoints}
                shapeName={shapeName}
                roadRouted={Boolean(activeRoute.snapped)}
                accepted={exportReady}
                editing={editing}
                onEditPoint={handleEditPoint}
              />
            </Suspense>
          ) : (
            <div className="route-map route-map--empty" role="status">
              <strong>No route line was returned</strong>
              <span>Adjust the idea and try another candidate.</span>
            </div>
          )}
          <div className="route-editor" aria-label="Route editor">
            <div>
              <strong>Manual route editor</strong>
              <p>
                Drag the numbered control points, then rebuild the line on the
                street network. The updated measurements replace the current
                result; routes below a target still require your explicit review.
              </p>
            </div>
            <div className="editor-actions">
              <button
                type="button"
                className="button button--secondary"
                onClick={() => {
                  resetEditor();
                  setEditing((value) => !value);
                }}
              >
                {editing
                  ? editDirty
                    ? "Discard point changes"
                    : "Close editor"
                  : "Edit this route"}
              </button>
              {editing && (
                <>
                  <button
                    type="button"
                    className="button button--quiet"
                    onClick={resetEditor}
                    disabled={editBusy}
                  >
                    Reset points
                  </button>
                  <button
                    type="button"
                    className="button button--primary"
                    onClick={rerouteEdited}
                    disabled={editBusy || controlPoints.length < 2}
                  >
                    {editBusy ? "Re-routing…" : "Update street route"}
                  </button>
                </>
              )}
            </div>
            {editError && (
              <p className="editor-error" role="alert">
                {editError}
              </p>
            )}
            {editedRoute && (
              <p className="editor-success" role="status">
                Edited route ready: {formatMetric(editedRoute.distance_km)} km,
                {editedRoute.verification?.passed
                  ? " matched to streets and passed every automatic check."
                  : " with updated measurements; review the highlighted checks before accepting it."}
              </p>
            )}
          </div>
          <div className="map-caption">
            {(activeRoute.ideal_preview ?? result.ideal_preview ?? []).length > 1 && (
              <span>
                <span className="legend-line legend-line--guide" aria-hidden="true" /> Intended
                outline
              </span>
            )}
            {(activeRoute.landmark_preview ?? result.landmark_preview ?? []).length > 0 && (
              <span>
                <span className="legend-dot legend-dot--landmark" aria-hidden="true" /> Salient
                landmarks
              </span>
            )}
            <span>
              <span className="legend-dot legend-dot--start" aria-hidden="true" /> Start
            </span>
            <span>
              <span className="legend-dot legend-dot--finish" aria-hidden="true" /> Finish
            </span>
            <span className="point-count">
              {activeRoute.snapped
                ? `${(activeRoute.points_preview ?? []).length.toLocaleString()} displayed of ${(
                    routingDetails.route_point_count ??
                    (activeRoute.points_preview ?? []).length
                  ).toLocaleString()} route points`
                : "Drawing preview — not matched to streets"}
            </span>
          </div>
        </div>

        <div className="result-sidebar">
          <dl className="metrics">
            <MetricCard
              label="Route quality"
              value={formatPercent(score)}
              detail="combined fit score"
              tone={qualityTone}
            />
            <MetricCard
              label="Distance"
              value={
                activeRoute.distance_km != null
                  ? `${formatMetric(activeRoute.distance_km)} km`
                  : "—"
              }
              detail={normaliseLabel(result.intent?.sport)}
            />
            <MetricCard
              label="Shape likeness"
              value={formatPercent(validation?.shape_fidelity)}
              detail="outline preserved"
              tone={validation?.shape_fidelity >= 0.7 ? "good" : "warn"}
            />
            <MetricCard
              label="Distance accuracy"
              value={formatPercent(validation?.distance_fit)}
              detail="target match"
            />
            <MetricCard
              label="Loop closure"
              value={activeRoute.closed ? formatPercent(validation?.closure) : "Open"}
              detail={activeRoute.closed ? "start-to-finish fit" : "open-path design"}
              tone={
                activeRoute.closed && Number.isFinite(validation?.closure)
                  ? validation.closure >= 0.6
                    ? "good"
                    : "warn"
                  : "neutral"
              }
            />
            <MetricCard
              label="Routes shown"
              value={
                Number.isFinite(candidateSummary.shown_count)
                  ? candidateSummary.shown_count
                  : candidates.length
              }
              detail={
                `${candidateSummary.verified_count ?? candidateSummary.accepted_count ?? 0} passed checks, ${reviewCount} for review; ${auditedCount} evaluated${
                  Number.isFinite(result.preflight_count) && result.preflight_count > 0
                    ? `; ${result.preflight_count} placements screened`
                    : ""
                }`
              }
              tone={(candidateSummary.verified_count ?? 0) > 0 ? "good" : "warn"}
            />
          </dl>

          {fitDecision && (
            <div className={`notice ${fitDecision.substituted ? "notice--success" : "notice--warning"}`}>
              <strong>
                {fitDecision.substituted
                  ? `${requestedShape} did not fit — using ${shapeName}`
                  : `Quality notes for ${requestedShape}`}
              </strong>
              <ul className="decision-reasons">
                {(fitDecision.reasons ?? []).map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              {(fitDecision.candidates_tested ?? []).length > 0 && (
                <p>
                  Alternatives measured:{" "}
                  {fitDecision.candidates_tested.map(normaliseLabel).join(", ")}.
                </p>
              )}
            </div>
          )}

          {result.suggested_shape && !fitDecision?.substituted && (
            <div className="notice notice--info">
              <strong>Street-friendly suggestion</strong>
              <p>{normaliseLabel(result.suggested_shape)}</p>
            </div>
          )}

          {!automaticChecksPassed && (
            <div className="notice notice--warning" role="status">
              <strong>Automatic verification recommends a closer look</strong>
              <p>
                {!activeRoute.snapped
                  ? "The routing provider did not confirm connected streets, so the line may cross buildings, water, or inaccessible land. You can still accept and export the shown guide after inspecting it carefully."
                  : "One or more geometric scores missed the automatic target. The route remains the selected shape and is available for your judgment, editing, and explicit GPX acceptance."}
              </p>
            </div>
          )}

          {verification?.gates?.length > 0 && (
            <details
              className={`verification-card verification-card--${automaticChecksPassed ? "pass" : "fail"}`}
            >
              <summary className="verification-heading">
                <span>
                  <span className="eyebrow">Shape-following verification</span>
                  <span className="verification-title">
                    {automaticChecksPassed
                      ? "All automatic targets reached"
                      : `${verification.failed_gates?.length ?? 0} metric target${verification.failed_gates?.length === 1 ? "" : "s"} need review`}
                  </span>
                </span>
                <span className="verification-count">
                  {verification.passed_count}/{verification.required_count} · view data
                </span>
              </summary>
              <div className="verification-body">
                <div className="score-explainer">
                  <strong>How to read these numbers</strong>
                  <p>
                    Scores are 0–100 geometric similarity indices: higher means the routed
                    line preserves more of the intended drawing. They are not probabilities
                    and do not measure traffic or personal safety. The displayed minimums are
                    conservative automatic-review targets; your visual judgment remains final.
                  </p>
                </div>
                <ul className="gate-list">
                  {verification.gates
                    .filter((gate) => gate.applies)
                    .map((gate) => (
                      <li key={gate.key} className={gate.passed ? "gate--pass" : "gate--fail"}>
                        <span className="gate-icon" aria-hidden="true">
                          {gate.passed ? "✓" : "!"}
                        </span>
                        <span>
                          <strong>{gate.label}</strong>
                          <small>{gate.description}</small>
                          <small className="gate-interpretation">
                            {explainGateResult(gate)}
                          </small>
                        </span>
                        <span className="gate-value">
                          {formatGateValue(gate)}
                          {formatGateMinimum(gate) && <small>{formatGateMinimum(gate)}</small>}
                        </span>
                      </li>
                    ))}
                </ul>
              </div>
            </details>
          )}

          {routeDetails && (
            <details className="route-facts">
              <summary>Generated route details</summary>
              <p className="route-facts-intro">
                Route/guide length shows detour added by streets (1.00× means no added
                length). Mean deviation is the average outline offset divided by the guide’s
                overall size, so smaller is better.
              </p>
              <dl>
                <div>
                  <dt>Selected shape</dt>
                  <dd>{shapeName}</dd>
                </div>
                <div>
                  <dt>Activity profile</dt>
                  <dd>{normaliseLabel(routingDetails.activity)}</dd>
                </div>
                <div>
                  <dt>Street matched</dt>
                  <dd>{routingDetails.street_matched ? "Yes" : "No"}</dd>
                </div>
                <div>
                  <dt>Route / guide points</dt>
                  <dd>
                    {routingDetails.route_point_count ?? "—"} / {routingDetails.guide_point_count ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt>Actual / target distance</dt>
                  <dd>
                    {formatMetric(distanceDetails.actual_km)} km / {formatMetric(distanceDetails.target_km)} km
                  </dd>
                </div>
                <div>
                  <dt>Distance difference</dt>
                  <dd>
                    {formatSigned(distanceDetails.difference_km, 2, " km")} ({formatSigned(
                      distanceDetails.difference_percent,
                      1,
                      "%",
                    )})
                  </dd>
                </div>
                <div>
                  <dt>Route / guide length</dt>
                  <dd>{formatMetric(distanceDetails.route_to_guide_ratio, 2)}×</dd>
                </div>
                <div>
                  <dt>Mean deviation / guide extent</dt>
                  <dd>{formatPercent(deviationDetails.mean_outline_deviation_ratio)}</dd>
                </div>
                {activeRoute.closed && (
                  <div>
                    <dt>Start–finish gap</dt>
                    <dd>{formatMetric(routingDetails.closure_gap_m, 0)} m</dd>
                  </div>
                )}
                <div>
                  <dt>Rotation / physical scale</dt>
                  <dd>
                    {formatMetric(placementDetails.rotation_deg, 1)}° / {formatMetric(
                      placementDetails.scale_m,
                      0,
                    )} m
                  </dd>
                </div>
                <div>
                  <dt>Placement offset N / E</dt>
                  <dd>
                    {formatSigned(placementDetails.lat_offset_m, 0, " m")} / {formatSigned(
                      placementDetails.lon_offset_m,
                      0,
                      " m",
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Preflight road fit</dt>
                  <dd>{formatPercent(placementDetails.preflight_score)}</dd>
                </div>
              </dl>
            </details>
          )}

          <div className="export-card">
            <div>
              <p className="eyebrow">Your route, your decision</p>
              <h3>
                {automaticChecksPassed
                  ? "Checked GPX ready"
                  : userAccepted
                    ? "Your accepted route is ready"
                    : "Review the evidence, then accept or edit"}
              </h3>
            </div>
            {!automaticChecksPassed && !userAccepted && (
              <p className="acceptance-copy">
                Accepting means you choose this exact shown geometry despite the highlighted
                automatic checks. Inspect the map and local accessibility before using it.
              </p>
            )}
            <div className="download-actions">
              {!automaticChecksPassed && !userAccepted && activeRoute.gpx && (
                <button
                  type="button"
                  className="button button--primary accept-route-button"
                  onClick={() => {
                    setAcceptedRouteIds((current) => new Set(current).add(activeRouteId));
                    recordRouteAcceptance({
                      generation_request_id: result.request_id ?? null,
                      route_id: activeRouteId,
                      shape_name: activeRoute.shape_name ?? result.shape?.name ?? "route",
                      automatic_checks_passed: automaticChecksPassed,
                      snapped: Boolean(activeRoute.snapped),
                      failed_gates: verification?.failed_gates ?? [],
                      score: validation?.score ?? null,
                      shape_fidelity: validation?.shape_fidelity ?? null,
                      distance_km: activeRoute.distance_km ?? null,
                    }).catch(() => {
                      // Telemetry must never block the user's chosen export.
                    });
                    onDownload("gpx", activeRoute.gpx);
                  }}
                  disabled={exportBlockedByPendingEdits}
                >
                  Accept shown route &amp; download GPX
                </button>
              )}
              {exportReady && activeRoute.gpx && (
                <button
                  type="button"
                  className="button button--primary"
                  onClick={() => onDownload("gpx", activeRoute.gpx)}
                  disabled={exportBlockedByPendingEdits}
                >
                  {editedRoute?.gpx ? "Download edited GPX" : "Download candidate GPX"}
                </button>
              )}
              {exportReady && activeRoute.tcx && (
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => onDownload("tcx", activeRoute.tcx)}
                  disabled={exportBlockedByPendingEdits}
                >
                  Download TCX
                </button>
              )}
            </div>
            {exportBlockedByPendingEdits && (
              <p className="pending-edit-note" role="status">
                Apply the moved points with “Update street route,” or discard them, before
                downloading this route.
              </p>
            )}
            {activeRoute.gallery_publish_token && !editedRoute && (
              <div className="gallery-publish">
                <div>
                  <strong>Publish this street map anonymously</strong>
                  <p>
                    The PNG will show this exact mapped area, street names, route line, and
                    OpenStreetMap attribution. No prompt, profile, or route file is attached.
                  </p>
                </div>
                {!publishedAsset ? (
                  <>
                    <label>
                      <input
                        type="checkbox"
                        checked={galleryConsent}
                        onChange={(event) => setGalleryConsent(event.target.checked)}
                        disabled={galleryBusy}
                      />
                      I understand that this location and its street names will be public.
                    </label>
                    <button
                      type="button"
                      className="button button--secondary"
                      onClick={publishMapScreenshot}
                      disabled={!canPublishGallery || !galleryConsent || galleryBusy}
                    >
                      {galleryBusy ? "Capturing and publishing…" : "Publish map screenshot"}
                    </button>
                  </>
                ) : (
                  <p className="gallery-publish-success" role="status">
                    Published anonymously. <a href="#gallery">View it in the gallery</a>.
                  </p>
                )}
                {galleryError && (
                  <p className="gallery-publish-error" role="alert">
                    {galleryError}
                  </p>
                )}
                {!exportReady && (
                  <small>Accept or verify this street-routed candidate before publishing.</small>
                )}
                {editing && <small>Finish the current map edit before publishing.</small>}
              </div>
            )}
            {!activeRoute.gpx && (
              <p className="export-unavailable">
                The route service did not return enough geometry to build a GPX. Edit or
                regenerate the route and try again.
              </p>
            )}
            <p className="safety-note">
              Always check crossings, access, surface, traffic, and current conditions before
              following a generated route.
            </p>
          </div>
        </div>
      </div>

      {(issueList.length > 0 || historyRows.length > 0 || auditRows.length > 0) && (
        <div className="details-grid">
          {issueList.length > 0 && (
            <details className="detail-card">
              <summary>
                Candidate notes <span>{issueList.length}</span>
              </summary>
              <ul>
                {issueList.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            </details>
          )}

          {historyRows.length > 0 && (
            <details className="detail-card">
              <summary>
                Candidate history <span>{historyRows.length}</span>
              </summary>
              <div className="table-wrap">
                <table>
                  <caption className="sr-only">Route candidate quality scores</caption>
                  <thead>
                    <tr>
                      <th scope="col">Pass</th>
                      <th scope="col">Score</th>
                      <th scope="col">Change</th>
                      <th scope="col">Shape match</th>
                      <th scope="col">Distance accuracy</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historyRows.map((entry, index) => (
                      <tr key={`${entry.iteration ?? index}-${index}`}>
                        <td data-label="Pass">{entry.iteration ?? index}</td>
                        <td data-label="Score">{formatPercent(entry.score)}</td>
                        <td data-label="Change">
                          {Number.isFinite(entry.delta_vs_best)
                            ? `${entry.delta_vs_best >= 0 ? "+" : ""}${formatMetric(entry.delta_vs_best, 3)}`
                            : "—"}
                        </td>
                        <td data-label="Shape match">
                          {formatPercent(entry.fidelity ?? entry.shape_fidelity)}
                        </td>
                        <td data-label="Distance accuracy">{formatPercent(entry.distance_fit)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}

          {auditRows.length > 0 && (
            <details className="detail-card">
              <summary>
                Route-attempt audit <span>{auditRows.length}</span>
              </summary>
              <div className="table-wrap">
                <table>
                  <caption className="sr-only">
                    Acceptance results for every fully evaluated route attempt
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Attempt</th>
                      <th scope="col">Shape</th>
                      <th scope="col">Decision</th>
                      <th scope="col">Score</th>
                      <th scope="col">Likeness</th>
                      <th scope="col">Distance</th>
                      <th scope="col">Failed checks</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditRows.map((entry) => (
                      <tr key={entry.id}>
                        <td data-label="Attempt">{entry.id}</td>
                        <td data-label="Shape">{normaliseLabel(entry.shape_name)}</td>
                        <td data-label="Decision">
                          {entry.decision === "verified"
                            ? "Checks passed"
                            : entry.decision === "review"
                              ? "Review"
                              : "Other shape"}
                        </td>
                        <td data-label="Score">{formatPercent(entry.score)}</td>
                        <td data-label="Likeness">{formatPercent(entry.shape_fidelity)}</td>
                        <td data-label="Distance">{formatMetric(entry.distance_km)} km</td>
                        <td data-label="Failed checks">
                          {(entry.failed_gates ?? []).length > 0
                            ? entry.failed_gates.map(normaliseLabel).join(", ")
                            : "None"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </div>
      )}
    </section>
  );
}

export default function App() {
  const [prompt, setPrompt] = useState(QUICK_IDEAS[0].prompt);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [suggestCity, setSuggestCity] = useState(SUGGEST_CITIES[0]);
  const [suggestSport, setSuggestSport] = useState("run");
  const [suggestDistance, setSuggestDistance] = useState("10");
  const [downloadNotice, setDownloadNotice] = useState("");
  const [galleryRefreshKey, setGalleryRefreshKey] = useState(0);
  const [lastPublishedGalleryAsset, setLastPublishedGalleryAsset] = useState(null);
  const requestRef = useRef(null);
  const resultRef = useRef(null);
  const errorRef = useRef(null);

  useEffect(() => {
    if (result) resultRef.current?.focus();
  }, [result]);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  useEffect(() => () => requestRef.current?.abort(), []);

  const activeIdea = useMemo(
    () => QUICK_IDEAS.find((idea) => idea.prompt === prompt)?.label,
    [prompt],
  );

  const generate = useCallback(async (nextPrompt) => {
    const cleanPrompt = nextPrompt.trim();
    if (!cleanPrompt) return;

    const controller = new AbortController();
    requestRef.current?.abort();
    requestRef.current = controller;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await generateRoute(cleanPrompt, { signal: controller.signal });
      setResult(response);
    } catch (generationError) {
      if (generationError.name !== "AbortError") {
        setError(
          generationError.message ||
            "We couldn’t create a route candidate. Check the idea and try again.",
        );
      }
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setLoading(false);
      }
    }
  }, []);

  function handleSubmit(event) {
    event.preventDefault();
    if (!loading) generate(prompt);
  }

  function handleSuggest(event) {
    event.preventDefault();
    if (loading) return;
    const distance = suggestDistance ? `, about ${suggestDistance} km` : "";
    const suggestionPrompt = `suggest a ${suggestSport} route in ${suggestCity}${distance}`;
    setPrompt(suggestionPrompt);
    generate(suggestionPrompt);
  }

  function cancelGeneration() {
    requestRef.current?.abort();
  }

  function handleDownload(extension, content) {
    const routeName = safeFilePart(
      `${result?.shape?.name ?? "gps-art"}-${result?.intent?.city ?? "route"}`,
    );
    const contentType = extension === "gpx" ? "application/gpx+xml" : "application/vnd.garmin.tcx+xml";
    saveFile(`${routeName}.${extension}`, content, contentType);
    setDownloadNotice(`${extension.toUpperCase()} download started.`);
  }

  const minimumDistance = suggestSport === "bike" ? 10 : 3;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#route-designer">
        Skip to route generator
      </a>

      <header className="site-header">
        <a className="brand" href="/" aria-label="GPS Art Wizard home">
          <span className="brand-mark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span>
            GPS Art <strong>Wizard</strong>
          </span>
        </a>
        <nav aria-label="Primary navigation">
          <a href="#route-designer">Create</a>
          <a href="#gallery">Gallery</a>
        </nav>
      </header>

      <main>
        <section
          className="workspace generator-stage"
          id="route-designer"
          aria-labelledby="designer-title"
        >
          <div className="designer-card">
            <div className="card-heading">
              <div>
                <p className="step-label">Street-aware GPS art</p>
                <h1 id="designer-title">Turn your route into a drawing.</h1>
              </div>
              <span className="keyboard-hint" aria-hidden="true">
                Ctrl ↵ to generate
              </span>
            </div>

            <form onSubmit={handleSubmit}>
              <label className="field-label" htmlFor="route-prompt">
                Describe your idea
              </label>
              <div className="textarea-wrap">
                <textarea
                  id="route-prompt"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  onKeyDown={(event) => {
                    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                  rows={3}
                  maxLength={PROMPT_LIMIT}
                  placeholder="Try: a heart run in Budapest, about 8 km"
                  aria-describedby="prompt-help prompt-count"
                  disabled={loading}
                  autoFocus
                  required
                />
                <span id="prompt-count" className="character-count">
                  {prompt.length}/{PROMPT_LIMIT}
                </span>
              </div>
              <p id="prompt-help" className="field-help">
                Include what to draw, the city, your activity, and a target distance.
              </p>

              <fieldset className="idea-picker">
                <legend>Street-friendly quick ideas</legend>
                <div className="idea-list">
                  {FEATURED_IDEAS.map((idea) => (
                    <button
                      type="button"
                      key={idea.label}
                      className="idea-chip"
                      aria-pressed={activeIdea === idea.label}
                      onClick={() => setPrompt(idea.prompt)}
                      disabled={loading}
                    >
                      <span aria-hidden="true">{idea.glyph}</span>
                      {idea.label}
                    </button>
                  ))}
                </div>
              </fieldset>

              <details className="idea-catalog">
                <summary>
                  <span>
                    <strong>Browse all {QUICK_IDEAS.length} quick ideas</strong>
                    <small>Curated for clear silhouettes and mostly continuous lines.</small>
                  </span>
                  <b aria-hidden="true">+</b>
                </summary>
                <div className="idea-groups">
                  {IDEA_CATEGORIES.map((category) => (
                    <section className="idea-group" key={category} aria-label={`${category} ideas`}>
                      <h3>{category}</h3>
                      <div className="idea-list">
                        {QUICK_IDEAS.filter((idea) => idea.category === category).map((idea) => (
                          <button
                            type="button"
                            key={idea.label}
                            className="idea-chip"
                            aria-pressed={activeIdea === idea.label}
                            onClick={() => setPrompt(idea.prompt)}
                            disabled={loading}
                          >
                            <span aria-hidden="true">{idea.glyph}</span>
                            {idea.label}
                          </button>
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              </details>

              <button
                type="submit"
                className="button button--primary generate-button"
                disabled={loading || !prompt.trim()}
              >
                <span>{loading ? "Finding routes…" : "Find matching routes"}</span>
                <span aria-hidden="true">→</span>
              </button>
            </form>

            <details className="suggest-panel">
              <summary>
                Not sure what fits? Let the planner choose
                <span aria-hidden="true">+</span>
              </summary>
              <form className="suggest-form" onSubmit={handleSuggest}>
                <div className="suggest-heading">
                  <p className="step-label">City suggestion</p>
                  <h3>Choose an idea likely to fit the local street grid</h3>
                </div>
                <div className="suggest-fields">
                  <div className="field">
                    <label htmlFor="suggest-city">City</label>
                    <select
                      id="suggest-city"
                      value={suggestCity}
                      onChange={(event) => setSuggestCity(event.target.value)}
                      disabled={loading}
                    >
                      {SUGGEST_CITIES.map((cityName) => (
                        <option key={cityName} value={cityName}>
                          {cityName}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="suggest-sport">Activity</label>
                    <select
                      id="suggest-sport"
                      value={suggestSport}
                      onChange={(event) => {
                        const nextSport = event.target.value;
                        setSuggestSport(nextSport);
                        if (nextSport === "bike" && Number(suggestDistance) < 10) {
                          setSuggestDistance("10");
                        }
                      }}
                      disabled={loading}
                    >
                      <option value="run">Running</option>
                      <option value="bike">Cycling</option>
                    </select>
                  </div>
                  <div className="field field--distance">
                    <label htmlFor="suggest-distance">Distance</label>
                    <div className="input-suffix">
                      <input
                        id="suggest-distance"
                        type="number"
                        inputMode="decimal"
                        min={minimumDistance}
                        max={suggestSport === "bike" ? 200 : 60}
                        step="1"
                        value={suggestDistance}
                        onChange={(event) => setSuggestDistance(event.target.value)}
                        disabled={loading}
                        required
                      />
                      <span>km</span>
                    </div>
                  </div>
                </div>
                <button type="submit" className="button button--secondary" disabled={loading}>
                  Choose an idea and find routes
                </button>
              </form>
            </details>
          </div>
        </section>

        {loading && <LoadingState onCancel={cancelGeneration} />}

        {error && (
          <section className="error-card" role="alert" tabIndex="-1" ref={errorRef}>
            <div className="error-symbol" aria-hidden="true">
              !
            </div>
            <div>
              <p className="eyebrow">No candidate created</p>
              <h2>We couldn’t find a route for this idea</h2>
              <p>{error}</p>
              <button
                type="button"
                className="button button--secondary"
                onClick={() => generate(prompt)}
              >
                Try this idea again
              </button>
            </div>
          </section>
        )}

        {result && (
          <ResultPanel
            result={result}
            onDownload={handleDownload}
            onGalleryPublished={(asset) => {
              setLastPublishedGalleryAsset(asset);
              setGalleryRefreshKey((current) => current + 1);
            }}
            focusRef={resultRef}
          />
        )}
        <GallerySection
          refreshKey={galleryRefreshKey}
          publishedAsset={lastPublishedGalleryAsset}
        />
      </main>

      <footer>
        <p>Draw boldly. Check the route. Move safely.</p>
        <p>Map data © OpenStreetMap contributors.</p>
      </footer>
      <div className="sr-only" aria-live="polite">
        {downloadNotice}
      </div>
    </div>
  );
}

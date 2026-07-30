import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { editRoute, generate as generateRoute } from "./api.js";

const RouteMap = lazy(() => import("./RouteMap.jsx"));

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

function pointsToGpx(points, name) {
  const escapeXml = (value) =>
    String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&apos;");
  const trackPoints = (Array.isArray(points) ? points : [])
    .filter(
      (point) =>
        Array.isArray(point) &&
        Number.isFinite(point[0]) &&
        Number.isFinite(point[1]),
    )
    .map(
      ([latitude, longitude]) =>
        `<trkpt lat="${latitude.toFixed(7)}" lon="${longitude.toFixed(7)}"></trkpt>`,
    )
    .join("");
  return `<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="GPS Art Wizard" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>${escapeXml(name)}</name><trkseg>${trackPoints}</trkseg></trk></gpx>`;
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

function ResultPanel({ result, onDownload, focusRef }) {
  const candidates = result.candidates ?? [];
  const [selectedCandidateId, setSelectedCandidateId] = useState(
    candidates[0]?.id ?? "best",
  );
  const [editing, setEditing] = useState(false);
  const [controlPoints, setControlPoints] = useState([]);
  const [editedRoute, setEditedRoute] = useState(null);
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState("");

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
    };
  const validation = activeRoute.validation ?? result.validation;
  const score = validation?.score;
  const routeReady =
    Boolean(activeRoute.snapped) &&
    !Boolean(activeRoute.below_recommended);
  const qualityTone = score == null ? "neutral" : routeReady ? "good" : "warn";
  const shapeName = normaliseLabel(activeRoute.shape_name ?? result.shape?.name);
  const fitDecision = result.fit_decision;
  const requestedShape = normaliseLabel(
    fitDecision?.requested_shape ?? result.requested_shape ?? result.shape?.name,
  );
  const city = result.intent?.city ? normaliseLabel(result.intent.city) : "your selected area";
  const historyRows = (result.history ?? []).filter((entry) => Number.isFinite(entry.score));
  const issueList = [
    ...new Set([
      ...(validation?.issues ?? []),
      ...(editedRoute?.warnings ?? []),
      ...(result.errors ?? []),
    ]),
  ];
  const stateLabel = !activeRoute.snapped
    ? "Preview only"
    : routeReady
      ? "Validated street route"
      : "Editable candidate";

  const resetEditor = useCallback(() => {
    setControlPoints(sampleControlPoints(activeRoute.points_preview));
    setEditError("");
  }, [activeRoute.points_preview]);

  const handleEditPoint = useCallback(
    (index, point) => {
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
      });
      setEditedRoute({
        ...activeRoute,
        id: `${activeRoute.id}-edited`,
        points_preview: response.points_preview,
        distance_km: response.distance_km,
        snapped: response.snapped,
        validation: response.validation,
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
    shapeName,
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
            {routeReady ? "Recommended GPS art" : "Editable GPS-art candidate"}
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
        <span className={`route-state route-state--${routeReady ? "good" : "warn"}`}>
          <span aria-hidden="true">{routeReady ? "✓" : "!"}</span>
          {stateLabel}
        </span>
      </div>

      <div className="result-layout">
        <div className="map-card">
          <div className="candidate-toolbar">
            <label htmlFor="route-candidate">Generated route</label>
            <select
              id="route-candidate"
              value={selectedCandidate?.id ?? "best"}
              onChange={(event) => {
                setSelectedCandidateId(event.target.value);
                setEditing(false);
                setEditedRoute(null);
                setControlPoints([]);
                setEditError("");
              }}
            >
              {candidates.length > 0 ? (
                candidates.map((candidate, index) => (
                  <option key={candidate.id} value={candidate.id}>
                    {index + 1}. {normaliseLabel(candidate.shape_name)} ·{" "}
                    {formatPercent(candidate.validation?.score)} ·{" "}
                    {formatMetric(candidate.distance_km)} km
                  </option>
                ))
              ) : (
                <option value="best">Generated candidate</option>
              )}
            </select>
            <span>
              {candidates.length > 0
                ? `${candidates.length} fully routed candidates retained`
                : "Candidate retained for editing"}
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
                points={activeRoute.points_preview}
                idealPoints={activeRoute.ideal_preview ?? result.ideal_preview}
                editPoints={controlPoints}
                shapeName={shapeName}
                roadRouted={Boolean(activeRoute.snapped)}
                accepted={routeReady}
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
                street network. Every candidate remains available.
              </p>
            </div>
            <div className="editor-actions">
              <button
                type="button"
                className="button button--secondary"
                onClick={() => {
                  if (!editing) resetEditor();
                  setEditing((value) => !value);
                }}
              >
                {editing ? "Finish moving points" : "Edit this route"}
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
                {editedRoute.snapped
                  ? " matched to streets."
                  : " exported as a manual guide because street routing was unavailable."}
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
            <span>
              <span className="legend-dot legend-dot--start" aria-hidden="true" /> Start
            </span>
            <span>
              <span className="legend-dot legend-dot--finish" aria-hidden="true" /> Finish
            </span>
            <span className="point-count">
              {activeRoute.snapped
                ? `${(activeRoute.points_preview ?? []).length.toLocaleString()} street-route points`
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
              label="Full routes"
              value={
                Number.isFinite(result.candidate_count)
                  ? result.candidate_count
                  : Number.isFinite(result.iterations)
                    ? result.iterations + 1
                    : "—"
              }
              detail={
                Number.isFinite(result.preflight_count) && result.preflight_count > 0
                  ? `${result.preflight_count} placements screened first`
                  : "route variants tested"
              }
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

          {(activeRoute.below_recommended || !activeRoute.snapped) && (
            <div className="notice notice--warning" role="status">
              <strong>
                {!activeRoute.snapped
                  ? "Manual review required"
                  : "This candidate can be improved"}
              </strong>
              <p>
                {!activeRoute.snapped
                  ? "Street routing was unavailable. The candidate is retained and exportable as a guide, but it may cross inaccessible areas; edit and review every segment."
                  : "One or more recommended recognition or usability targets were missed. The candidate is retained: compare alternatives or correct it in the map editor before export."}
              </p>
            </div>
          )}

          {validation && activeRoute.snapped && (
            <details className="recognition-checks" open={!routeReady}>
              <summary>Recognition checks</summary>
              <dl>
                <div>
                  <dt>Outline coverage</dt>
                  <dd>{formatPercent(validation.coverage_similarity)}</dd>
                </div>
                <div>
                  <dt>Characteristic turns</dt>
                  <dd>{formatPercent(validation.turning_similarity)}</dd>
                </div>
                <div>
                  <dt>Detour control</dt>
                  <dd>{formatPercent(validation.length_similarity)}</dd>
                </div>
                <div>
                  <dt>Width / height</dt>
                  <dd>{formatPercent(validation.extent_similarity)}</dd>
                </div>
              </dl>
            </details>
          )}

          <div className="export-card">
            <div>
              <p className="eyebrow">Your selected candidate</p>
              <h3>Download GPX or refine it first</h3>
            </div>
            <div className="download-actions">
              {(editedRoute?.gpx ||
                (activeRoute.points_preview ?? []).length > 1) && (
                <button
                  type="button"
                  className="button button--primary"
                  onClick={() =>
                    onDownload(
                      "gpx",
                      editedRoute?.gpx ??
                        pointsToGpx(
                          activeRoute.points_preview,
                          `${shapeName} in ${city}`,
                        ),
                    )
                  }
                >
                  {editedRoute?.gpx ? "Download edited GPX" : "Download candidate GPX"}
                </button>
              )}
              {editedRoute?.tcx && (
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => onDownload("tcx", editedRoute.tcx)}
                >
                  Download edited TCX
                </button>
              )}
            </div>
            {!routeReady && (
              <p className="export-unavailable">
                This candidate is below one or more recommended quality targets
                but remains exportable. Inspect and edit it before use.
              </p>
            )}
            <p className="safety-note">
              Always check crossings, access, surface, traffic, and current conditions before
              following a generated route.
            </p>
          </div>
        </div>
      </div>

      {(issueList.length > 0 || historyRows.length > 0) && (
        <div className="details-grid">
          {issueList.length > 0 && (
            <details
              className="detail-card"
              open={activeRoute.below_recommended || !activeRoute.snapped}
            >
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
          <ResultPanel result={result} onDownload={handleDownload} focusRef={resultRef} />
        )}
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

import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { buildWalkthrough, locateOnWalkthrough } from "./routeWalkthrough.js";

const PREVIEW_METRES_PER_SECOND = 35;
const STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";
const FOLLOW_ZOOM = 18;
const FOLLOW_PITCH = 65;
const toLngLat = (points) => points.map(([lat, lng]) => [lng, lat]);
const lineFeature = (points) => ({ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: points } });
const pointFeature = (point) => ({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: point } });

function followCamera(location) {
  const [latitude, longitude] = location.position;
  return { center: [longitude, latitude], bearing: location.heading,
    zoom: FOLLOW_ZOOM, pitch: FOLLOW_PITCH };
}

function RouteWalkthroughMap({ walkthrough, location }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const locationRef = useRef(location);
  const [mapError, setMapError] = useState("");
  locationRef.current = location;

  useEffect(() => {
    if (!document.createElement("canvas").getContext("webgl2")) {
      setMapError("This browser cannot display the 3D route view.");
      return undefined;
    }
    const routeCoordinates = toLngLat(walkthrough.coordinates);
    let map;
    try {
      map = new maplibregl.Map({
        container: containerRef.current, style: STYLE_URL,
        ...followCamera(location), interactive: false,
        canvasContextAttributes: { antialias: true },
      });
    } catch {
      setMapError("This browser cannot display the 3D route view.");
      return undefined;
    }
    mapRef.current = map;
    map.on("load", () => {
      map.addSource("walkthrough-route", { type: "geojson", data: lineFeature(routeCoordinates) });
      map.addSource("walkthrough-travelled", {
        type: "geojson", data: lineFeature([routeCoordinates[0], routeCoordinates[0]]),
      });
      map.addSource("walkthrough-position", { type: "geojson", data: pointFeature(routeCoordinates[0]) });
      map.addLayer({
        id: "walkthrough-route-halo", type: "line", source: "walkthrough-route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#fff", "line-width": 11, "line-opacity": 0.95 },
      });
      map.addLayer({
        id: "walkthrough-route-line", type: "line", source: "walkthrough-route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#087b61", "line-width": 7 },
      });
      map.addLayer({
        id: "walkthrough-travelled-line", type: "line", source: "walkthrough-travelled",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#8b9c95", "line-width": 7 },
      });
      map.addLayer({
        id: "walkthrough-position-dot", type: "circle", source: "walkthrough-position",
        paint: { "circle-radius": 9, "circle-color": "#123d30",
          "circle-stroke-color": "#fff", "circle-stroke-width": 3 },
      });
      const current = locationRef.current;
      const [currentLatitude, currentLongitude] = current.position;
      map.jumpTo(followCamera(current));
      map.getSource("walkthrough-position").setData(pointFeature([currentLongitude, currentLatitude]));
      map.getSource("walkthrough-travelled").setData(lineFeature(toLngLat(current.travelled)));
      setMapError("");
    });
    map.on("error", () => {
      if (!map.isStyleLoaded()) setMapError("The 3D map could not be loaded. Check your connection and try again.");
    });
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(containerRef.current);
    return () => { observer.disconnect(); map.remove(); mapRef.current = null; };
  }, [walkthrough]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !location) return;
    const [latitude, longitude] = location.position;
    map.easeTo({ ...followCamera(location), duration: 65,
      easing: (progress) => progress, essential: true });
    map.getSource("walkthrough-position")?.setData(pointFeature([longitude, latitude]));
    map.getSource("walkthrough-travelled")?.setData(lineFeature(toLngLat(location.travelled)));
  }, [location]);

  return (
    <div className="walkthrough-scene">
      <div ref={containerRef} className="walkthrough-map" role="region"
        aria-label="Animated 3D map of the planned route and mapped buildings" />
      {mapError && <p className="walkthrough-map-error" role="alert">{mapError}</p>}
    </div>
  );
}

export default function RouteWalkthrough({ points, shapeName }) {
  const [open, setOpen] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [metres, setMetres] = useState(0);
  const walkthrough = useMemo(() => buildWalkthrough(points), [points]);
  const location = useMemo(() => locateOnWalkthrough(walkthrough, metres), [walkthrough, metres]);

  useEffect(() => { setMetres(0); setPlaying(false); }, [walkthrough]);
  useEffect(() => {
    if (!playing || !open) return undefined;
    let frame;
    let last = performance.now();
    const tick = (now) => {
      if (now - last >= 50) {
        const elapsed = (now - last) / 1000;
        setMetres((current) => Math.min(walkthrough.total, current + elapsed * PREVIEW_METRES_PER_SECOND));
        last = now;
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, open, walkthrough.total]);
  useEffect(() => {
    if (playing && metres >= walkthrough.total) setPlaying(false);
  }, [playing, metres, walkthrough.total]);

  if (walkthrough.coordinates.length < 2 || walkthrough.total < 1) return null;

  return (
    <details className="walkthrough" onToggle={(event) => {
      setOpen(event.currentTarget.open);
      if (!event.currentTarget.open) setPlaying(false);
    }}>
      <summary className="walkthrough-heading">
        <div>
          <span className="eyebrow">Before you head out</span>
          <strong>Virtually walk through your route</strong>
          <small>Follow the planned GPS line through mapped streets and buildings.</small>
        </div>
        <span className="walkthrough-chevron" aria-hidden="true">⌄</span>
      </summary>
      {open && <div className="walkthrough-body">
        <RouteWalkthroughMap walkthrough={walkthrough} location={location} />
        <div className="walkthrough-controls">
          <div className="walkthrough-progress">
            <strong>{Math.round(metres).toLocaleString()} m</strong>
            <span>of {Math.round(walkthrough.total).toLocaleString()} m · {shapeName}</span>
          </div>
          <label htmlFor="walkthrough-distance" className="sr-only">Position along the planned route</label>
          <input id="walkthrough-distance" type="range" min="0" max={Math.ceil(walkthrough.total)}
            step="1" value={Math.round(metres)} onChange={(event) => {
              setPlaying(false);
              setMetres(Math.min(walkthrough.total, Number(event.target.value)));
            }} />
          <div className="walkthrough-actions">
            <button type="button" className="button button--primary" onClick={() => {
              if (metres >= walkthrough.total) setMetres(0);
              setPlaying((value) => !value);
            }}>{playing ? "Pause walkthrough" : metres >= walkthrough.total ? "Replay walkthrough" : "Play walkthrough"}</button>
            <button type="button" className="button button--secondary" disabled={metres <= 0}
              onClick={() => { setPlaying(false); setMetres((value) => Math.max(0, value - 100)); }}>← Back 100 m</button>
            <button type="button" className="button button--secondary" disabled={metres >= walkthrough.total}
              onClick={() => { setPlaying(false); setMetres((value) => Math.min(walkthrough.total, value + 100)); }}>Next 100 m →</button>
          </div>
          <p className="walkthrough-note">The green line is the planned route; grey shows the section already visited. Streets and building outlines come from OpenStreetMap. 3D heights appear where mapped. The moving camera simulates travel along the route.</p>
        </div>
      </div>}
    </details>
  );
}

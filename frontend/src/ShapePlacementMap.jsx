import { memo, useEffect, useMemo, useRef } from "react";
import L from "leaflet-rotate-map";

const EARTH_RADIUS_M = 6_371_000;
const DEFAULT_CENTER = [47.4979, 19.0402];

function isCoordinate(value) {
  return (
    Array.isArray(value) &&
    value.length >= 2 &&
    Number.isFinite(value[0]) &&
    Number.isFinite(value[1]) &&
    Math.abs(value[0]) <= 85 &&
    Math.abs(value[1]) <= 180
  );
}

function projectPoint([x, y], center, scaleM, rotationDeg) {
  const angle = (rotationDeg * Math.PI) / 180;
  const rotatedX = x * Math.cos(angle) - y * Math.sin(angle);
  const rotatedY = x * Math.sin(angle) + y * Math.cos(angle);
  const latitude = center[0] + ((rotatedY * scaleM) / EARTH_RADIUS_M) * (180 / Math.PI);
  const longitude =
    center[1] +
    ((rotatedX * scaleM) /
      (EARTH_RADIUS_M * Math.max(0.01, Math.cos((center[0] * Math.PI) / 180)))) *
      (180 / Math.PI);
  return [latitude, longitude];
}

function projectPaths(paths, center, scaleM, rotationDeg) {
  return paths.map((path) =>
    path
      .filter((point) => Array.isArray(point) && point.length >= 2)
      .map((point) => projectPoint(point, center, scaleM, rotationDeg)),
  );
}

function ShapePlacementMap({
  paths = [],
  center = DEFAULT_CENTER,
  cityBbox = null,
  scaleM = 2_000,
  rotationDeg = 0,
  shapeLabel = "shape",
  onCenterChange,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const didFitRef = useRef(false);
  const onCenterChangeRef = useRef(onCenterChange);

  useEffect(() => {
    onCenterChangeRef.current = onCenterChange;
  }, [onCenterChange]);

  const safeCenter = useMemo(
    () => (isCoordinate(center) ? [Number(center[0]), Number(center[1])] : DEFAULT_CENTER),
    [center],
  );
  const projectedPaths = useMemo(
    () => projectPaths(paths, safeCenter, scaleM, rotationDeg),
    [paths, rotationDeg, safeCenter, scaleM],
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;
    const map = L.map(containerRef.current, {
      center: safeCenter,
      zoom: 13,
      zoomControl: true,
      scrollWheelZoom: true,
    });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    const placeAtClick = (event) => {
      onCenterChangeRef.current?.([event.latlng.lat, event.latlng.lng]);
    };
    map.on("click", placeAtClick);

    const resizeObserver = new ResizeObserver(() => map.invalidateSize({ pan: false }));
    resizeObserver.observe(containerRef.current);
    return () => {
      resizeObserver.disconnect();
      map.off("click", placeAtClick);
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();

    const lines = projectedPaths
      .filter((path) => path.length >= 2)
      .map((path) =>
        L.polyline(path, {
          color: "#e4542f",
          weight: 6,
          opacity: 0.9,
          dashArray: "10 7",
          lineCap: "round",
          lineJoin: "round",
          interactive: false,
          className: "shape-placement-outline",
        }).addTo(layer),
      );

    const marker = L.marker(safeCenter, {
      draggable: true,
      keyboard: true,
      title: `Move ${shapeLabel}`,
      icon: L.divIcon({
        className: "shape-placement-handle",
        html: '<span aria-hidden="true">↕</span>',
        iconSize: [44, 44],
        iconAnchor: [22, 22],
      }),
    }).addTo(layer);
    marker.bindTooltip(`Drag to move ${shapeLabel}`, { direction: "top" });
    marker.on("drag", () => {
      const position = marker.getLatLng();
      const liveCenter = [position.lat, position.lng];
      const livePaths = projectPaths(paths, liveCenter, scaleM, rotationDeg);
      lines.forEach((line, index) => line.setLatLngs(livePaths[index] ?? []));
    });
    marker.on("dragend", () => {
      const position = marker.getLatLng();
      onCenterChangeRef.current?.([position.lat, position.lng]);
    });
    const markerElement = marker.getElement();
    if (markerElement) {
      markerElement.setAttribute(
        "aria-label",
        `Move ${shapeLabel}. Drag it or use the arrow keys.`,
      );
      markerElement.addEventListener("keydown", (event) => {
        const movement = {
          ArrowUp: [1, 0],
          ArrowDown: [-1, 0],
          ArrowLeft: [0, -1],
          ArrowRight: [0, 1],
        }[event.key];
        if (!movement) return;
        event.preventDefault();
        const step = event.shiftKey ? 0.001 : 0.00025;
        onCenterChangeRef.current?.([
          safeCenter[0] + movement[0] * step,
          safeCenter[1] + movement[1] * step,
        ]);
      });
    }

    if (!didFitRef.current) {
      const validBbox =
        Array.isArray(cityBbox) &&
        cityBbox.length >= 4 &&
        cityBbox.every(Number.isFinite) &&
        cityBbox[0] < cityBbox[1] &&
        cityBbox[2] < cityBbox[3];
      if (validBbox) {
        map.fitBounds(
          [
            [cityBbox[0], cityBbox[2]],
            [cityBbox[1], cityBbox[3]],
          ],
          { padding: [36, 36], maxZoom: 14 },
        );
      } else if (lines.length > 0) {
        const bounds = lines.slice(1).reduce(
          (combined, line) => combined.extend(line.getBounds()),
          lines[0].getBounds(),
        );
        map.fitBounds(bounds, { padding: [64, 64], maxZoom: 15 });
      } else {
        map.setView(safeCenter, 13);
      }
      didFitRef.current = true;
    }
  }, [cityBbox, paths, projectedPaths, rotationDeg, safeCenter, scaleM, shapeLabel]);

  return (
    <div
      ref={containerRef}
      className="shape-placement-map"
      role="application"
      aria-label={`Map for positioning ${shapeLabel}`}
      tabIndex={0}
    />
  );
}

export default memo(ShapePlacementMap);

import {
  forwardRef,
  memo,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import L from "leaflet-rotate-map";

const DEFAULT_CENTER = [47.4979, 19.0402];

function normaliseBearing(value) {
  if (!Number.isFinite(value)) return 0;
  const wrapped = ((value + 180) % 360 + 360) % 360 - 180;
  return Math.abs(wrapped) < 0.5 ? 0 : Math.round(wrapped * 10) / 10;
}

function isCoordinate(point) {
  return (
    Array.isArray(point) &&
    point.length >= 2 &&
    Number.isFinite(point[0]) &&
    Number.isFinite(point[1]) &&
    Math.abs(point[0]) <= 90 &&
    Math.abs(point[1]) <= 180
  );
}

function waitForVisibleTiles(container, timeoutMs = 6_000) {
  const tiles = [...container.querySelectorAll("img.leaflet-tile")];
  const pending = tiles.filter((tile) => !tile.complete);
  if (pending.length === 0) return Promise.resolve();
  return new Promise((resolve) => {
    let remaining = pending.length;
    let settled = false;
    let timeoutId;
    const finish = () => {
      remaining -= 1;
      if (!settled && remaining <= 0) {
        settled = true;
        window.clearTimeout(timeoutId);
        resolve();
      }
    };
    pending.forEach((tile) => {
      tile.addEventListener("load", finish, { once: true });
      tile.addEventListener("error", finish, { once: true });
    });
    timeoutId = window.setTimeout(() => {
      if (!settled) {
        settled = true;
        resolve();
      }
    }, timeoutMs);
  });
}

function drawMapTiles(context, map, tileLayer, container, containerRect) {
  let drawn = 0;
  const tiles = Object.values(tileLayer?._tiles ?? {});
  tiles.forEach((record) => {
    const tile = record?.el;
    if (
      !record?.coords ||
      record.current === false ||
      !tile?.complete ||
      tile.naturalWidth < 1 ||
      tile.naturalHeight < 1
    ) {
      return;
    }
    const bounds = tileLayer._tileCoordsToBounds?.(record.coords);
    if (!bounds) return;
    const northWest = map.latLngToContainerPoint(bounds.getNorthWest());
    const northEast = map.latLngToContainerPoint(bounds.getNorthEast());
    const southWest = map.latLngToContainerPoint(bounds.getSouthWest());
    const width = tile.naturalWidth;
    const height = tile.naturalHeight;
    context.save();
    context.transform(
      (northEast.x - northWest.x) / width,
      (northEast.y - northWest.y) / width,
      (southWest.x - northWest.x) / height,
      (southWest.y - northWest.y) / height,
      northWest.x,
      northWest.y,
    );
    context.drawImage(tile, 0, 0, width, height);
    context.restore();
    drawn += 1;
  });
  if (drawn > 0) return drawn;

  // Defensive fallback for a future Leaflet build that changes its tile cache.
  [...container.querySelectorAll("img.leaflet-tile")]
    .filter((tile) => tile.complete && tile.naturalWidth > 0)
    .forEach((tile) => {
      const tileRect = tile.getBoundingClientRect();
      const x = tileRect.left - containerRect.left;
      const y = tileRect.top - containerRect.top;
      context.drawImage(tile, x, y, tileRect.width, tileRect.height);
      drawn += 1;
    });
  return drawn;
}

function drawCoordinatePath(context, map, coordinates, options) {
  if (coordinates.length < 2) return;
  context.save();
  context.beginPath();
  coordinates.forEach((coordinate, index) => {
    const point = map.latLngToContainerPoint(coordinate);
    if (index === 0) context.moveTo(point.x, point.y);
    else context.lineTo(point.x, point.y);
  });
  context.strokeStyle = options.color;
  context.lineWidth = options.width;
  context.globalAlpha = options.opacity ?? 1;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.setLineDash(options.dash ?? []);
  context.stroke();
  context.restore();
}

function drawEndpoint(context, map, coordinate, fillColor) {
  const point = map.latLngToContainerPoint(coordinate);
  context.save();
  context.beginPath();
  context.arc(point.x, point.y, 7, 0, Math.PI * 2);
  context.fillStyle = fillColor;
  context.fill();
  context.lineWidth = 3;
  context.strokeStyle = "#ffffff";
  context.stroke();
  context.restore();
}

const RouteMap = forwardRef(function RouteMap({
  points = [],
  idealPoints = [],
  landmarkPoints = [],
  readinessConcerns = [],
  streetCanvasCandidates = [],
  editPoints = [],
  shapeName = "GPS art",
  roadRouted = false,
  accepted = true,
  editing = false,
  onEditPoint,
}, forwardedRef) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const routeLayerRef = useRef(null);
  const tileLayerRef = useRef(null);
  const [bearing, setBearing] = useState(0);

  const applyBearing = useCallback((value) => {
    const next = normaliseBearing(Number(value));
    setBearing(next);
    // This rotating Leaflet build internally uses a near-zero value to keep
    // every SVG renderer mounted, while the UI still presents it as north-up.
    mapRef.current?.setBearing(next === 0 ? 0.0001 : next);
  }, []);

  const coordinates = useMemo(
    () =>
      (Array.isArray(points) ? points : [])
        .filter(isCoordinate)
        .map(([latitude, longitude]) => [latitude, longitude]),
    [points],
  );
  const idealCoordinates = useMemo(
    () =>
      (Array.isArray(idealPoints) ? idealPoints : [])
        .filter(isCoordinate)
        .map(([latitude, longitude]) => [latitude, longitude]),
    [idealPoints],
  );
  const editableCoordinates = useMemo(
    () =>
      (Array.isArray(editPoints) ? editPoints : [])
        .filter(isCoordinate)
        .map(([latitude, longitude]) => [latitude, longitude]),
    [editPoints],
  );
  const landmarkCoordinates = useMemo(
    () =>
      (Array.isArray(landmarkPoints) ? landmarkPoints : [])
        .filter(isCoordinate)
        .map(([latitude, longitude]) => [latitude, longitude]),
    [landmarkPoints],
  );
  const concernSegments = useMemo(() => {
    if (!Array.isArray(readinessConcerns)) return [];
    return readinessConcerns.flatMap((concern) =>
      (Array.isArray(concern?.segments_preview) ? concern.segments_preview : [])
        .map((segment) =>
          (Array.isArray(segment) ? segment : [])
            .filter(isCoordinate)
            .map(([latitude, longitude]) => [latitude, longitude]),
        )
        .filter((segment) => segment.length > 1)
        .map((segment) => ({
          coordinates: segment,
          label: String(concern.label || "Section to review"),
          severity: concern.severity === "warning" ? "warning" : "info",
        })),
    );
  }, [readinessConcerns]);
  const canvasCoordinates = useMemo(
    () => (Array.isArray(streetCanvasCandidates) ? streetCanvasCandidates : [])
      .filter((candidate) => Number.isFinite(candidate?.latitude) && Number.isFinite(candidate?.longitude))
      .slice(0, 4),
    [streetCanvasCandidates],
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;

    const map = L.map(containerRef.current, {
      center: DEFAULT_CENTER,
      zoom: 12,
      scrollWheelZoom: false,
      zoomControl: true,
      rotate: true,
    });

    const tileLayer = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      crossOrigin: "anonymous",
      maxZoom: 19,
    }).addTo(map);

    mapRef.current = map;
    tileLayerRef.current = tileLayer;
    routeLayerRef.current = L.layerGroup().addTo(map);

    const syncBearing = () => setBearing(normaliseBearing(map.getBearing()));
    map.on("rotate", syncBearing);

    let disposed = false;
    const resizeObserver = new ResizeObserver(() => {
      if (!disposed && containerRef.current?.isConnected) {
        map.invalidateSize({ pan: false });
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      disposed = true;
      resizeObserver.disconnect();
      map.off("rotate", syncBearing);
      map.remove();
      mapRef.current = null;
      routeLayerRef.current = null;
      tileLayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const routeLayer = routeLayerRef.current;
    if (!map || !routeLayer) return;

    routeLayer.clearLayers();
    if (coordinates.length === 0) {
      map.setView(DEFAULT_CENTER, 12);
      return;
    }

    let guideLine = null;
    if (idealCoordinates.length > 1) {
      guideLine = L.polyline(idealCoordinates, {
        color: "#e4542f",
        weight: 3,
        opacity: 0.65,
        dashArray: "9 9",
        lineCap: "round",
        lineJoin: "round",
        interactive: false,
      }).addTo(routeLayer);
    }

    const line = L.polyline(coordinates, {
      color: roadRouted ? (accepted ? "#0b6b57" : "#b45309") : "#b45309",
      weight: 5,
      opacity: roadRouted ? 0.95 : 0.8,
      lineCap: "round",
      lineJoin: "round",
      dashArray: roadRouted ? undefined : "10 10",
      interactive: false,
    }).addTo(routeLayer);

    concernSegments.forEach((segment) => {
      L.polyline(segment.coordinates, {
        color: segment.severity === "warning" ? "#c2412d" : "#9a6700",
        weight: 8,
        opacity: 0.92,
        dashArray: "4 8",
        lineCap: "round",
        lineJoin: "round",
        className: `route-concern-segment route-concern-segment--${segment.severity}`,
      })
        .bindTooltip(segment.label)
        .addTo(routeLayer);
    });

    canvasCoordinates.forEach((candidate) => {
      L.circleMarker([candidate.latitude, candidate.longitude], {
        radius: candidate.rank === 1 ? 8 : 6,
        color: "#ffffff",
        weight: 2,
        fillColor: candidate.rank === 1 ? "#245f9f" : "#6b8db8",
        fillOpacity: 0.95,
        className: "street-canvas-marker",
      })
        .bindTooltip(`Street Canvas area ${candidate.rank}: ${Math.round((candidate.readability_score ?? 0) * 100)}% fit`)
        .addTo(routeLayer);
    });

    landmarkCoordinates.forEach((coordinate, index) => {
      L.circleMarker(coordinate, {
        radius: 5,
        color: "#ffffff",
        weight: 2,
        fillColor: "#10b981",
        fillOpacity: 1,
        className: "route-landmark-marker",
      })
        .bindTooltip(`Key point ${index + 1}`)
        .addTo(routeLayer);
    });

    let editLine = null;
    if (editing && editableCoordinates.length > 1) {
      editLine = L.polyline(editableCoordinates, {
        color: "#2563eb",
        weight: 3,
        opacity: 0.9,
        dashArray: "5 7",
        lineCap: "round",
        lineJoin: "round",
      }).addTo(routeLayer);
      const markers = editableCoordinates.map((coordinate, index) => {
        const marker = L.marker(coordinate, {
          draggable: true,
          keyboard: true,
          title: `Edit point ${index + 1}`,
          icon: L.divIcon({
            className: "route-edit-marker",
            html: `<span>${index + 1}</span>`,
            iconSize: [44, 44],
            iconAnchor: [22, 22],
          }),
        }).addTo(routeLayer);
        marker.bindTooltip(`Move route point ${index + 1}`, {
          direction: "top",
        });
        marker.on("drag", () => {
          editLine.setLatLngs(markers.map((item) => item.getLatLng()));
        });
        marker.on("dragend", () => {
          const position = marker.getLatLng();
          onEditPoint?.(index, [position.lat, position.lng]);
        });
        const element = marker.getElement();
        if (element) {
          element.setAttribute(
            "aria-label",
            `Edit point ${index + 1}. Drag it or use the arrow keys to move it.`,
          );
          element.addEventListener("keydown", (event) => {
            const movement = {
              ArrowUp: [1, 0],
              ArrowDown: [-1, 0],
              ArrowLeft: [0, -1],
              ArrowRight: [0, 1],
            }[event.key];
            if (!movement) return;
            event.preventDefault();
            const step = event.shiftKey ? 0.0005 : 0.0001;
            const current = marker.getLatLng();
            const next = L.latLng(
              current.lat + movement[0] * step,
              current.lng + movement[1] * step,
            );
            marker.setLatLng(next);
            editLine.setLatLngs(markers.map((item) => item.getLatLng()));
            onEditPoint?.(index, [next.lat, next.lng]);
          });
        }
        return marker;
      });
    }

    L.circleMarker(coordinates[0], {
      radius: 7,
      color: "#ffffff",
      weight: 3,
      fillColor: "#0b6b57",
      fillOpacity: 1,
    })
      .bindTooltip("Start")
      .addTo(routeLayer);

    if (coordinates.length > 1) {
      L.circleMarker(coordinates.at(-1), {
        radius: 7,
        color: "#ffffff",
        weight: 3,
        fillColor: "#e4542f",
        fillOpacity: 1,
      })
        .bindTooltip("Finish")
        .addTo(routeLayer);
    }

    if (coordinates.length === 1) {
      map.setView(coordinates[0], 15);
    } else {
      const bounds = guideLine
        ? line.getBounds().extend(guideLine.getBounds())
        : line.getBounds();
      if (editLine) bounds.extend(editLine.getBounds());
      map.fitBounds(bounds, { padding: [48, 48], maxZoom: 16 });
    }
  }, [
    accepted,
    concernSegments,
    canvasCoordinates,
    coordinates,
    editableCoordinates,
    editing,
    idealCoordinates,
    landmarkCoordinates,
    onEditPoint,
    roadRouted,
  ]);

  useImperativeHandle(
    forwardedRef,
    () => ({
      async capturePng() {
        const container = containerRef.current;
        const map = mapRef.current;
        if (!container || !map || coordinates.length < 2) {
          throw new Error("The map isn’t ready to share yet.");
        }
        await waitForVisibleTiles(container);
        if (document.fonts?.ready) await document.fonts.ready;

        const containerRect = container.getBoundingClientRect();
        const cssWidth = Math.round(containerRect.width);
        const cssHeight = Math.round(containerRect.height);
        if (cssWidth < 240 || cssHeight < 180) {
          throw new Error("The map is too small to share.");
        }
        const pixelRatio = Math.min(Math.max(window.devicePixelRatio || 1, 1), 2);
        const canvas = document.createElement("canvas");
        canvas.width = Math.round(cssWidth * pixelRatio);
        canvas.height = Math.round(cssHeight * pixelRatio);
        const context = canvas.getContext("2d");
        if (!context) throw new Error("This browser can’t create a shareable map image.");
        context.scale(pixelRatio, pixelRatio);
        context.fillStyle = "#e7e3dc";
        context.fillRect(0, 0, cssWidth, cssHeight);

        try {
          const drawnTiles = drawMapTiles(
            context,
            map,
            tileLayerRef.current,
            container,
            containerRect,
          );
          if (drawnTiles === 0) {
            throw new Error("The street map is still loading. Try again in a moment.");
          }
        } catch (error) {
          if (error?.message?.includes("still loading")) throw error;
          throw new Error(
            "This browser couldn’t capture the street map.",
            { cause: error },
          );
        }

        drawCoordinatePath(context, map, idealCoordinates, {
          color: "#e4542f",
          width: 3,
          opacity: 0.65,
          dash: [9, 9],
        });
        drawCoordinatePath(context, map, coordinates, {
          color: roadRouted ? (accepted ? "#0b6b57" : "#b45309") : "#b45309",
          width: 5,
          opacity: roadRouted ? 0.95 : 0.8,
          dash: roadRouted ? [] : [10, 10],
        });
        concernSegments.forEach((segment) => {
          drawCoordinatePath(context, map, segment.coordinates, {
            color: segment.severity === "warning" ? "#c2412d" : "#9a6700",
            width: 8,
            opacity: 0.92,
            dash: [4, 8],
          });
        });
        drawEndpoint(context, map, coordinates[0], "#0b6b57");
        drawEndpoint(context, map, coordinates.at(-1), "#e4542f");

        const attribution = "© OpenStreetMap contributors";
        context.save();
        context.font = "12px system-ui, -apple-system, sans-serif";
        context.textBaseline = "middle";
        const attributionWidth = Math.ceil(context.measureText(attribution).width) + 16;
        context.fillStyle = "rgba(255, 255, 255, 0.88)";
        context.fillRect(
          cssWidth - attributionWidth,
          cssHeight - 24,
          attributionWidth,
          24,
        );
        context.fillStyle = "#24332e";
        context.fillText(attribution, cssWidth - attributionWidth + 8, cssHeight - 12);
        context.restore();

        try {
          return canvas.toDataURL("image/png");
        } catch (error) {
          throw new Error(
            "We couldn’t turn this map into a gallery image.",
            { cause: error },
          );
        }
      },
    }),
    [accepted, concernSegments, coordinates, idealCoordinates, roadRouted],
  );

  return (
    <div className="route-map-shell">
      <div
        ref={containerRef}
        className="route-map"
        role="region"
        aria-label={
          roadRouted
            ? `${shapeName} street-route map. ${
                editing
                  ? "Drag the numbered blue control points or use their arrow keys to edit the route."
                  : "Use the controls to pan, zoom, and rotate the complete map."
              }`
            : `${shapeName} preview only. This line is not matched to streets.`
        }
      />
      <div className="map-rotation-toolbar" aria-label="Map rotation controls">
        <div className="map-rotation-copy">
          <strong>Rotate the view</strong>
          <span>Turn the map until the drawing reads best.</span>
        </div>
        <button
          type="button"
          className="map-rotation-step"
          onClick={() => applyBearing(bearing - 15)}
          aria-label="Rotate map 15 degrees left"
          title="Rotate 15° left"
        >
          ↺ <span>15°</span>
        </button>
        <label className="map-rotation-slider">
          <input
            aria-label="Map rotation angle"
            type="range"
            min="-180"
            max="180"
            step="1"
            value={bearing}
            onChange={(event) => applyBearing(event.target.value)}
          />
        </label>
        <output className="map-rotation-value" aria-live="polite">
          {Math.round(bearing)}°
        </output>
        <button
          type="button"
          className="map-rotation-step"
          onClick={() => applyBearing(bearing + 15)}
          aria-label="Rotate map 15 degrees right"
          title="Rotate 15° right"
        >
          ↻ <span>15°</span>
        </button>
        <button
          type="button"
          className="map-rotation-reset"
          onClick={() => applyBearing(0)}
          disabled={bearing === 0}
        >
          North up
        </button>
      </div>
    </div>
  );
});

export default memo(RouteMap);

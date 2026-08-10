import { forwardRef, memo, useEffect, useImperativeHandle, useMemo, useRef } from "react";
import L from "leaflet";

const DEFAULT_CENTER = [47.4979, 19.0402];

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

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;

    const map = L.map(containerRef.current, {
      center: DEFAULT_CENTER,
      zoom: 12,
      scrollWheelZoom: false,
      zoomControl: true,
    });

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      crossOrigin: "anonymous",
      maxZoom: 19,
    }).addTo(map);

    mapRef.current = map;
    routeLayerRef.current = L.layerGroup().addTo(map);

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
      map.remove();
      mapRef.current = null;
      routeLayerRef.current = null;
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

        const visibleTiles = [...container.querySelectorAll("img.leaflet-tile")].filter(
          (tile) => tile.complete && tile.naturalWidth > 0,
        );
        if (visibleTiles.length === 0) {
          throw new Error("The street map is still loading. Try again in a moment.");
        }
        try {
          visibleTiles.forEach((tile) => {
            const tileRect = tile.getBoundingClientRect();
            const x = tileRect.left - containerRect.left;
            const y = tileRect.top - containerRect.top;
            if (
              x < cssWidth &&
              y < cssHeight &&
              x + tileRect.width > 0 &&
              y + tileRect.height > 0
            ) {
              context.drawImage(tile, x, y, tileRect.width, tileRect.height);
            }
          });
        } catch (error) {
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
    [accepted, coordinates, idealCoordinates, roadRouted],
  );

  return (
    <div
      ref={containerRef}
      className="route-map"
      role="region"
      aria-label={
        roadRouted
          ? `${shapeName} street-route map. ${
              editing
                ? "Drag the numbered blue control points or use their arrow keys to edit the route."
                : "Use the map controls to pan and zoom."
            }`
          : `${shapeName} preview only. This line is not matched to streets.`
      }
    />
  );
});

export default memo(RouteMap);

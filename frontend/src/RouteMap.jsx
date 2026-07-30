import { memo, useEffect, useMemo, useRef } from "react";
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

function RouteMap({
  points = [],
  idealPoints = [],
  editPoints = [],
  shapeName = "GPS art",
  roadRouted = false,
  accepted = true,
  editing = false,
  onEditPoint,
}) {
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

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;

    const map = L.map(containerRef.current, {
      center: DEFAULT_CENTER,
      zoom: 12,
      scrollWheelZoom: false,
      zoomControl: true,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
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
            iconSize: [28, 28],
            iconAnchor: [14, 14],
          }),
        }).addTo(routeLayer);
        marker.bindTooltip(`Drag route control point ${index + 1}`, {
          direction: "top",
        });
        marker.on("drag", () => {
          editLine.setLatLngs(markers.map((item) => item.getLatLng()));
        });
        marker.on("dragend", () => {
          const position = marker.getLatLng();
          onEditPoint?.(index, [position.lat, position.lng]);
        });
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
    onEditPoint,
    roadRouted,
  ]);

  return (
    <div
      ref={containerRef}
      className="route-map"
      role="region"
      aria-label={
        roadRouted
          ? `${shapeName} street-route map. ${
              editing
                ? "Drag the numbered blue control points to edit the route."
                : "Use the map controls to pan and zoom."
            }`
          : `${shapeName} drawing preview. The line is not matched to streets.`
      }
    />
  );
}

export default memo(RouteMap);

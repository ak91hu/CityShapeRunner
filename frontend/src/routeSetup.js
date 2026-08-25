export const EMPTY_ROUTE_PREFERENCES = Object.freeze({
  avoid_steps: false,
  avoid_ferries: false,
  avoid_fords: false,
  prefer_quiet: false,
  prefer_green: false,
});

export const START_DIRECTIONS = Object.freeze([
  { value: "315", label: "North-west", shortLabel: "NW", glyph: "↖" },
  { value: "0", label: "North", shortLabel: "N", glyph: "↑" },
  { value: "45", label: "North-east", shortLabel: "NE", glyph: "↗" },
  { value: "270", label: "West", shortLabel: "W", glyph: "←" },
  { value: "", label: "Any direction", shortLabel: "Any", glyph: "◎" },
  { value: "90", label: "East", shortLabel: "E", glyph: "→" },
  { value: "225", label: "South-west", shortLabel: "SW", glyph: "↙" },
  { value: "180", label: "South", shortLabel: "S", glyph: "↓" },
  { value: "135", label: "South-east", shortLabel: "SE", glyph: "↘" },
]);

function validPoint(point) {
  return Boolean(
    point
      && Number.isFinite(point.latitude)
      && Number.isFinite(point.longitude)
      && point.latitude >= -90
      && point.latitude <= 90
      && point.longitude >= -180
      && point.longitude <= 180,
  );
}

export function normaliseRoutePreferences(preferences = {}) {
  return Object.fromEntries(
    Object.keys(EMPTY_ROUTE_PREFERENCES).map((key) => [key, preferences[key] === true]),
  );
}

export function buildRouteSetupPayload(
  {
    startMode = "any",
    startAddress = "",
    startPoint = null,
    startDirection = "",
    routePreferences = EMPTY_ROUTE_PREFERENCES,
  } = {},
  extraPayload = {},
  { includeStartConstraints = true } = {},
) {
  const payload = { ...extraPayload };
  if (includeStartConstraints) {
    if (startMode === "address") {
      const cleanAddress = String(startAddress || "").replace(/\s+/g, " ").trim();
      if (cleanAddress) payload.start_address = cleanAddress;
    } else if (startMode === "location" && validPoint(startPoint)) {
      payload.start_point = {
        latitude: startPoint.latitude,
        longitude: startPoint.longitude,
        label: String(startPoint.label || "Current location").trim() || "Current location",
      };
    }

    if (startDirection !== "") {
      const direction = Number(startDirection);
      if (Number.isFinite(direction) && direction >= 0 && direction < 360) {
        payload.start_direction_deg = direction;
      }
    }
  }

  const preferences = normaliseRoutePreferences(routePreferences);
  if (Object.values(preferences).some(Boolean)) payload.route_preferences = preferences;
  return payload;
}

export function countRouteSetupSelections({
  startMode = "any",
  startAddress = "",
  startPoint = null,
  startDirection = "",
  routePreferences = EMPTY_ROUTE_PREFERENCES,
} = {}) {
  const hasStart =
    (startMode === "address" && Boolean(String(startAddress || "").trim()))
    || (startMode === "location" && validPoint(startPoint));
  return (
    (hasStart ? 1 : 0)
    + (startDirection !== "" ? 1 : 0)
    + Object.values(normaliseRoutePreferences(routePreferences)).filter(Boolean).length
  );
}

export function routeSetupSummary({
  startMode = "any",
  startAddress = "",
  startPoint = null,
  startDirection = "",
  routePreferences = EMPTY_ROUTE_PREFERENCES,
} = {}) {
  const parts = [];
  if (startMode === "address" && String(startAddress || "").trim()) {
    parts.push("Address start");
  } else if (startMode === "location" && validPoint(startPoint)) {
    parts.push("Current location");
  } else {
    parts.push("Flexible start");
  }
  const direction = START_DIRECTIONS.find((option) => option.value === String(startDirection));
  if (direction && direction.value !== "") parts.push(direction.label);
  const preferenceCount = Object.values(normaliseRoutePreferences(routePreferences)).filter(Boolean).length;
  if (preferenceCount) {
    parts.push(`${preferenceCount} street preference${preferenceCount === 1 ? "" : "s"}`);
  }
  return parts.join(" · ");
}

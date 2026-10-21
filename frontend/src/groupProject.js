import { EMPTY_ROUTE_PREFERENCES } from "./routeSetup.js";

export function parseGroupProject(text) {
  if (text.length > 1_000_000) throw new Error("The event file is too large (maximum 1 MB).");
  let data;
  try { data = JSON.parse(text); } catch { throw new Error("Choose a valid Paceasso event JSON file."); }
  const validPoint = point => Array.isArray(point) && point.length === 2 &&
    point.every(Number.isFinite) && Math.abs(point[0]) <= 90 && Math.abs(point[1]) <= 180;
  if (data?.format !== "paceasso-group-v1" || typeof data.name !== "string" ||
      !data.name.trim() || data.name.length > 100 || !["run", "bike"].includes(data.sport) ||
      typeof data.return_to_start !== "boolean" ||
      !Array.isArray(data.points) || data.points.length < 4 || data.points.length > 2000 ||
      !data.points.every(validPoint) ||
      !Array.isArray(data.members) || data.members.length < 2 || data.members.length > 24 ||
      !data.members.every(member => typeof member?.name === "string" && member.name.trim() &&
        member.name.length <= 80 && Number.isFinite(member.max_distance_km) &&
        member.max_distance_km >= 0.05 && member.max_distance_km <= 500)) {
    throw new Error("This event file has invalid route or participant details.");
  }
  const names = data.members.map(member => member.name.trim().toLocaleLowerCase());
  if (new Set(names).size !== names.length) throw new Error("Participant names must be distinct.");
  return {
    name: data.name.trim(), points: data.points, sport: data.sport,
    return_to_start: data.return_to_start,
    members: data.members.map(({ name, max_distance_km }) => ({ name: name.trim(), max_distance_km })),
    route_preferences: Object.fromEntries(Object.keys(EMPTY_ROUTE_PREFERENCES)
      .map(key => [key, data.route_preferences?.[key] === true])),
  };
}

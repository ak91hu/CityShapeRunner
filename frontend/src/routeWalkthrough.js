function distanceMetres([lat1, lon1], [lat2, lon2]) {
  const radians = Math.PI / 180;
  const north = (lat2 - lat1) * radians;
  const east = (lon2 - lon1) * radians;
  const arc = Math.sin(north / 2) ** 2 + Math.cos(lat1 * radians) *
    Math.cos(lat2 * radians) * Math.sin(east / 2) ** 2;
  return 6371000 * 2 * Math.atan2(Math.sqrt(arc), Math.sqrt(1 - arc));
}

function bearingDegrees(from, to) {
  const radians = Math.PI / 180;
  const lat1 = from[0] * radians;
  const lat2 = to[0] * radians;
  const east = (to[1] - from[1]) * radians;
  const y = Math.sin(east) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(east);
  return (Math.atan2(y, x) / radians + 360) % 360;
}

export function buildWalkthrough(points) {
  const coordinates = (Array.isArray(points) ? points : []).filter((point) =>
    Array.isArray(point) && point.length >= 2 && Number.isFinite(point[0]) &&
    Number.isFinite(point[1]) && Math.abs(point[0]) <= 90 && Math.abs(point[1]) <= 180);
  const distances = [0];
  for (let index = 1; index < coordinates.length; index += 1) {
    distances.push(distances[index - 1] + distanceMetres(coordinates[index - 1], coordinates[index]));
  }
  return { coordinates, distances, total: distances.at(-1) ?? 0 };
}

export function locateOnWalkthrough(walkthrough, metres) {
  const { coordinates, distances, total } = walkthrough;
  if (coordinates.length < 2) return null;
  const progress = Math.max(0, Math.min(total, metres));
  let index = 1;
  while (index < distances.length - 1 && distances[index] < progress) index += 1;
  const segmentLength = distances[index] - distances[index - 1];
  const fraction = segmentLength > 0 ? (progress - distances[index - 1]) / segmentLength : 0;
  const start = coordinates[index - 1];
  const end = coordinates[index];
  const position = [start[0] + (end[0] - start[0]) * fraction,
    start[1] + (end[1] - start[1]) * fraction];
  return {
    position,
    heading: bearingDegrees(start, end),
    travelled: [...coordinates.slice(0, index), position],
    remaining: [position, ...coordinates.slice(index)],
  };
}

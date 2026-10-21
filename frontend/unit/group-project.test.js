import test from "node:test";
import assert from "node:assert/strict";
import { parseGroupProject } from "../src/groupProject.js";

const event = {
  format: "paceasso-group-v1", name: "Club heart", sport: "run", return_to_start: true,
  points: [[47, 19], [47.001, 19], [47.001, 19.001], [47, 19]],
  members: [{ name: "Ada", max_distance_km: 2 }, { name: "Bea", max_distance_km: 8 }],
};

test("a saved event restores route, unequal limits and only supported preferences", () => {
  const restored = parseGroupProject(JSON.stringify({ ...event,
    route_preferences: { avoid_steps: true, avoid_ferries: "yes", secret: "discard" },
    gpx: "untrusted executable export", token: "discard",
  }));
  assert.deepEqual(restored.points, event.points);
  assert.deepEqual(restored.members, event.members);
  assert.equal(restored.return_to_start, true);
  assert.equal(restored.route_preferences.avoid_steps, true);
  assert.equal(restored.route_preferences.avoid_ferries, false);
  assert.equal("secret" in restored.route_preferences, false);
  assert.equal("gpx" in restored, false);
  assert.equal("token" in restored, false);
});

test("malformed events cannot replace a usable group project", () => {
  for (const data of [null, {}, { ...event, points: [[91, 19]] }, { ...event, name: [] },
    { ...event, sport: "drive" }, { ...event, members: [event.members[0]] },
    { ...event, members: [{ name: "Ada", max_distance_km: -2 }, event.members[1]] },
    { ...event, members: [{ name: "Ada", max_distance_km: 2 }, { name: " ada ", max_distance_km: 8 }] },
  ]) assert.throws(() => parseGroupProject(JSON.stringify(data)));
  assert.throws(() => parseGroupProject("broken json"));
  assert.throws(() => parseGroupProject(" ".repeat(1_000_001)), /too large/);
});

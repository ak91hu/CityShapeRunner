import assert from "node:assert/strict";
import test from "node:test";
import { buildWalkthrough, locateOnWalkthrough } from "../src/routeWalkthrough.js";

test("walkthrough follows the full route in distance order, including its turn", () => {
  const route = buildWalkthrough([[47.5, 19], [47.501, 19], [47.501, 19.002]]);
  assert.equal(route.coordinates.length, 3);
  assert.ok(route.total > 200);
  const beforeTurn = locateOnWalkthrough(route, route.distances[1] / 2);
  assert.ok(beforeTurn.position[0] > 47.5 && beforeTurn.position[0] < 47.501);
  assert.equal(beforeTurn.position[1], 19);
  assert.ok(beforeTurn.heading < 1 || beforeTurn.heading > 359);
  const afterTurn = locateOnWalkthrough(route, (route.distances[1] + route.total) / 2);
  assert.equal(afterTurn.position[0], 47.501);
  assert.ok(afterTurn.position[1] > 19 && afterTurn.position[1] < 19.002);
  assert.ok(afterTurn.heading > 89 && afterTurn.heading < 91);
  assert.deepEqual(afterTurn.remaining.at(-1), [47.501, 19.002]);
  assert.deepEqual(locateOnWalkthrough(route, route.total + 100).position, [47.501, 19.002]);
});

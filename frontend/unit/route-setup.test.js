import assert from "node:assert/strict";
import test from "node:test";

import {
  EMPTY_ROUTE_PREFERENCES,
  START_DIRECTIONS,
  buildRouteSetupPayload,
  countRouteSetupSelections,
  normaliseRoutePreferences,
  routeSetupSummary,
} from "../src/routeSetup.js";

test("empty setup does not add optional API fields", () => {
  assert.deepEqual(buildRouteSetupPayload(), {});
});

test("address mode trims whitespace and keeps a zero-degree heading", () => {
  assert.deepEqual(
    buildRouteSetupPayload({
      startMode: "address",
      startAddress: "  Hősök   tere, Budapest  ",
      startDirection: "0",
    }),
    { start_address: "Hősök tere, Budapest", start_direction_deg: 0 },
  );
});

test("location mode sends only a valid selected point", () => {
  assert.deepEqual(
    buildRouteSetupPayload({
      startMode: "location",
      startAddress: "stale address",
      startPoint: { latitude: 47.497913, longitude: 19.040236, label: "Current location" },
    }),
    {
      start_point: {
        latitude: 47.497913,
        longitude: 19.040236,
        label: "Current location",
      },
    },
  );
});

test("stale start values are ignored in flexible mode", () => {
  assert.deepEqual(
    buildRouteSetupPayload({
      startMode: "any",
      startAddress: "Hősök tere",
      startPoint: { latitude: 47.5, longitude: 19.0 },
    }),
    {},
  );
});

test("invalid coordinates and headings are never serialized", () => {
  assert.deepEqual(
    buildRouteSetupPayload({
      startMode: "location",
      startPoint: { latitude: 91, longitude: 19 },
      startDirection: "360",
    }),
    {},
  );
});

test("enabled preferences are normalized to the complete API contract", () => {
  assert.deepEqual(
    buildRouteSetupPayload({ routePreferences: { avoid_steps: true, prefer_green: true } }),
    {
      route_preferences: {
        avoid_steps: true,
        avoid_ferries: false,
        avoid_fords: false,
        prefer_quiet: false,
        prefer_green: true,
      },
    },
  );
});

test("normalization ignores unknown and truthy non-boolean preference values", () => {
  assert.deepEqual(normaliseRoutePreferences({ avoid_steps: "yes", unknown: true }), {
    ...EMPTY_ROUTE_PREFERENCES,
  });
});

test("map placement can omit incompatible start constraints but retain preferences", () => {
  assert.deepEqual(
    buildRouteSetupPayload(
      {
        startMode: "address",
        startAddress: "Hősök tere",
        startDirection: "90",
        routePreferences: { avoid_ferries: true },
      },
      { map_placement: { center_lat: 47.5 } },
      { includeStartConstraints: false },
    ),
    {
      map_placement: { center_lat: 47.5 },
      route_preferences: {
        avoid_steps: false,
        avoid_ferries: true,
        avoid_fords: false,
        prefer_quiet: false,
        prefer_green: false,
      },
    },
  );
});

test("selection count and summary describe only effective choices", () => {
  const setup = {
    startMode: "address",
    startAddress: "Hősök tere",
    startDirection: "90",
    routePreferences: { avoid_steps: true, prefer_green: true },
  };
  assert.equal(countRouteSetupSelections(setup), 4);
  assert.equal(routeSetupSummary(setup), "Address start · East · 2 street preferences");
});

test("the compass exposes every octant plus an unrestricted choice", () => {
  assert.equal(START_DIRECTIONS.length, 9);
  assert.deepEqual(
    new Set(START_DIRECTIONS.map(({ value }) => value)),
    new Set(["", "0", "45", "90", "135", "180", "225", "270", "315"]),
  );
  assert.deepEqual(
    START_DIRECTIONS.map(({ shortLabel }) => shortLabel),
    ["NW", "N", "NE", "W", "Any", "E", "SW", "S", "SE"],
  );
});

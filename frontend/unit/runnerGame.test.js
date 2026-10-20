import assert from "node:assert/strict";
import { test } from "node:test";
import { advanceRunner, createRunnerState, jumpRunner, RUNNER_HURDLES } from "../src/runnerGame.js";

test("grounded runners collide, while a timed jump clears the same obstacle and scores", () => {
  let grounded = { ...createRunnerState(), obstacleX: 110 };
  for (let i = 0; i < 60; i++) grounded = advanceRunner(grounded, 1 / 60);
  assert.equal(grounded.over, true);
  assert.equal(grounded.score, 0);
  assert.equal(advanceRunner(grounded, 1), grounded);

  let jumping = jumpRunner({ ...createRunnerState(), obstacleX: 110 });
  assert.equal(advanceRunner(jumping, 0), jumping, "a zero-length frame must not cancel a queued jump");
  assert.equal(jumpRunner(jumping), jumping, "a held key cannot add a second jump");
  jumping = advanceRunner(jumping, 1 / 60);
  assert(jumping.y > 0);
  assert.equal(jumpRunner(jumping), jumping, "airborne jumps cannot reset vertical speed");
  for (let i = 0; i < 59; i++) jumping = advanceRunner(jumping, 1 / 60);
  assert.equal(jumping.over, false);
  assert.equal(jumping.score, 1);
  assert.equal(jumping.y, 0);
  assert.equal(jumping.velocity, 0);
  assert.notEqual(RUNNER_HURDLES[jumping.hurdle].height, RUNNER_HURDLES[0].height);
  assert(jumping.obstacleX > 100);
  assert(jumpRunner(jumping).velocity > 0, "landing permits another jump");
});

test("late frames are bounded, and taller obstacles require enough jump clearance", () => {
  const state = { ...createRunnerState(), obstacleX: 110 };
  assert.deepEqual(advanceRunner(state, 10), advanceRunner(state, 0.05));
  assert.equal(state.obstacleX, 110, "advancing leaves the previous frame intact");
  for (let hurdle = 0; hurdle < RUNNER_HURDLES.length; hurdle++) {
    const approaching = { ...state, hurdle, obstacleX: 75, y: 10, velocity: 1 };
    assert.equal(advanceRunner(approaching, 1 / 60).over, true);
    assert.equal(advanceRunner({ ...approaching, y: 65 }, 1 / 60).over, false);
  }
});

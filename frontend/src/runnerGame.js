export const RUNNER_GROUND = 130;
export const RUNNER_PLAYER = { x: 55, size: 36 };
export const RUNNER_HURDLES = [
  { width: 24, height: 28 },
  { width: 30, height: 40 },
  { width: 22, height: 48 },
];

export function createRunnerState() {
  return { y: 0, velocity: 0, obstacleX: 600, hurdle: 0, score: 0, over: false };
}

export function jumpRunner(state) {
  return state.y === 0 && state.velocity === 0 && !state.over
    ? { ...state, velocity: 520 }
    : state;
}

export function advanceRunner(state, seconds) {
  if (state.over) return state;
  // Bound each frame so a delayed tab cannot skip straight through an obstacle.
  const dt = Math.min(0.05, Math.max(0, seconds));
  if (dt === 0) return state;
  const next = { ...state };
  next.y = Math.max(0, state.y + state.velocity * dt - 800 * dt * dt);
  next.velocity = next.y > 0 ? state.velocity - 1600 * dt : 0;
  next.obstacleX -= (210 + Math.min(state.score * 8, 110)) * dt;
  const hurdle = RUNNER_HURDLES[state.hurdle];
  next.over = next.obstacleX < RUNNER_PLAYER.x + RUNNER_PLAYER.size - 6
    && next.obstacleX + hurdle.width > RUNNER_PLAYER.x + 6
    && next.y < hurdle.height - 5;
  if (!next.over && next.obstacleX + hurdle.width < 0) {
    next.score += 1;
    next.hurdle = next.score % RUNNER_HURDLES.length;
    next.obstacleX = 600 + (next.score * 137) % 160;
  }
  return next;
}

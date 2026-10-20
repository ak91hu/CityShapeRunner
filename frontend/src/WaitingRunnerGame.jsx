import { useEffect, useRef, useState } from "react";
import { SKETCHES } from "./WaitingSketchGame.jsx";
import { advanceRunner, createRunnerState, jumpRunner, RUNNER_GROUND, RUNNER_HURDLES, RUNNER_PLAYER } from "./runnerGame.js";

export default function WaitingRunnerGame() {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState("ready");
  const [character, setCharacter] = useState(0);
  const [frame, setFrame] = useState(createRunnerState);
  const runRef = useRef(frame);
  const trackRef = useRef(null);
  const panelRef = useRef(null);
  const hurdle = RUNNER_HURDLES[frame.hurdle];

  useEffect(() => {
    const pause = () => {
      if (document.hidden) setStatus(current => current === "running" ? "paused" : current);
    };
    document.addEventListener("visibilitychange", pause);
    return () => document.removeEventListener("visibilitychange", pause);
  }, []);

  useEffect(() => {
    if (!open || status !== "running") return undefined;
    let last = performance.now();
    let animation;
    const tick = now => {
      runRef.current = advanceRunner(runRef.current, (now - last) / 1000);
      last = now;
      setFrame(runRef.current);
      if (runRef.current.over) setStatus("over");
      else animation = requestAnimationFrame(tick);
    };
    animation = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animation);
  }, [open, status]);

  const jump = () => {
    if (status === "running") runRef.current = jumpRunner(runRef.current);
  };
  const start = () => {
    if (status !== "paused") {
      runRef.current = createRunnerState();
      setFrame(runRef.current);
    }
    setStatus("running");
    requestAnimationFrame(() => trackRef.current?.focus({ preventScroll: true }));
  };

  return (
    <details ref={panelRef} className="waiting-game waiting-runner" open={open}
      onToggle={event => {
        setOpen(event.currentTarget.open);
        if (!event.currentTarget.open) setStatus(current => current === "running" ? "paused" : current);
        else if (window.matchMedia("(max-width: 48rem)").matches) {
          panelRef.current?.scrollIntoView({ block: "nearest", behavior: "instant" });
        }
      }}>
      <summary>
        <span><strong>Shape sprint</strong><small>Pick a shape and jump over the street obstacles</small></span>
        <span aria-hidden="true">{open ? "−" : "+"}</span>
      </summary>
      <div className="runner-body">
        <label className="runner-character">Runner shape
          <select value={character} disabled={status === "running"} onChange={event => setCharacter(Number(event.target.value))}>
            {SKETCHES.map((sketch, index) => <option key={sketch.answer} value={index}>{sketch.answer}</option>)}
          </select>
        </label>
        <p id="runner-help">Tap the track, or focus it and press Space or ↑ to jump. The game starts only when you choose Start run.</p>
        <button ref={trackRef} type="button" className="runner-track" aria-label="Jump over obstacles"
          aria-describedby="runner-help" disabled={status !== "running"} onClick={jump}
          onKeyDown={event => {
            if (event.code === "Space" || event.key === "ArrowUp") {
              event.preventDefault();
              if (!event.repeat) jump();
            }
          }}>
          <svg viewBox="0 0 600 160" aria-hidden="true">
            <path className="runner-ground" d={`M0 ${RUNNER_GROUND}H600`} />
            <path className="runner-skyline" d="M0 110V85H35V110M120 110V65H160V110M255 110V80H300V110M410 110V55H460V110M540 110V85H580V110" />
            <svg className="runner-player" data-height={frame.y} x={RUNNER_PLAYER.x} y={RUNNER_GROUND - RUNNER_PLAYER.size - frame.y}
              width={RUNNER_PLAYER.size} height={RUNNER_PLAYER.size} viewBox="0 0 100 100">
              <path d={SKETCHES[character].path} />
            </svg>
            <svg className="runner-obstacle" x={frame.obstacleX} y={RUNNER_GROUND - hurdle.height}
              width={hurdle.width} height={hurdle.height} viewBox="0 0 100 100" preserveAspectRatio="none">
              <path d={frame.hurdle === 0 ? "M5 95L50 5L95 95Z" : frame.hurdle === 1 ? "M5 95V30H35V5H65V30H95V95Z" : "M50 5L95 50L50 95L5 50Z"} />
            </svg>
          </svg>
        </button>
        <div className="runner-controls">
          <strong>Score: <output aria-label="Obstacles cleared" aria-live="off">{frame.score}</output></strong>
          {status === "running"
            ? <button type="button" onClick={() => setStatus("paused")}>Pause game</button>
            : <button type="button" onClick={start}>{status === "over" ? "Play again" : status === "paused" ? "Resume run" : "Start run"}</button>}
        </div>
        <p className="runner-status" role="status">{status === "over" ? "You hit an obstacle. Pick another shape or play again!"
          : status === "paused" ? "Game paused. Your route keeps generating."
            : status === "running" ? "Jump over the obstacles! Your route keeps generating." : "Ready when you are. Your route keeps generating."}</p>
      </div>
    </details>
  );
}

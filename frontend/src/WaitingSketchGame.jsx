import { useEffect, useRef, useState } from "react";
import { shuffled } from "./inspiration.js";

export const SKETCHES = [
  {
    answer: "Heart",
    options: ["Heart", "Butterfly", "Leaf"],
    clue: "Two rounded lobes meet at a pointed base. What is this sketch?",
    path: "M50 83C37 71 12 52 12 32C12 10 39 7 50 26C61 7 88 10 88 32C88 52 63 71 50 83Z",
    tip: "A heart reads best when both lobes and the bottom tip survive the street detours.",
  },
  {
    answer: "Star",
    options: ["Flower", "Star", "Crown"],
    clue: "Five pointed tips alternate with five deep notches. Which shape is it?",
    path: "M50 8L61 36L92 38L68 58L75 89L50 72L25 89L32 58L8 38L39 36Z",
    tip: "A star needs its notches as well as its tips. More GPS points alone cannot fix a missing corner.",
  },
  {
    answer: "Diamond",
    options: ["Circle", "Arrow", "Diamond"],
    clue: "Four straight sides connect a top, bottom, left and right point. Name this outline.",
    path: "M50 8L88 50L50 92L12 50Z",
    tip: "A simple outline can become striking GPS art when its direction matches the local street grid.",
  },
  {
    answer: "Sailboat",
    options: ["Mountain", "Sailboat", "Arrow"],
    clue: "A tall triangular section sits above a shallow curved base. What could it become?",
    path: "M50 10L50 65L15 65L50 10L85 65L50 65L50 75L90 75L78 90L22 90L10 75L50 75",
    tip: "Water can inspire the drawing, but the route still needs connected streets or paths on land.",
  },
  {
    answer: "Arrow",
    options: ["Arrow", "House", "Tree"],
    clue: "A narrow stem ends in a broad pointed head. Which outline is this?",
    path: "M40 90L40 45L15 45L50 10L85 45L60 45L60 90Z",
    tip: "The arrowhead must stay wider than the shaft. We check proportions as well as route distance.",
  },
  {
    answer: "Moon",
    options: ["Leaf", "Circle", "Moon"],
    clue: "One curved edge turns inward while the other curves outward. Name the sketch.",
    path: "M72 12C8 2 0 85 65 92C32 70 31 36 72 12Z",
    tip: "A crescent loses its identity if a street detour fills in the hollow. Outline coverage helps catch that.",
  },
  {
    answer: "House",
    options: ["Crown", "House", "Diamond"],
    clue: "A peaked roof sits on a square base. What is the drawing?",
    path: "M15 45L50 12L85 45L78 45L78 88L22 88L22 45Z",
    tip: "A roof corner can matter more than dozens of small bends. Distinctive turns get their own quality check.",
  },
  {
    answer: "Infinity",
    options: ["Butterfly", "Infinity", "Glasses"],
    clue: "Two rounded loops share one crossing in a continuous line. Which symbol is it?",
    path: "M50 50C25 10 5 30 10 55C15 80 35 80 50 50C65 20 85 20 90 45C95 70 75 90 50 50Z",
    tip: "A crossing on a sketch is easy. On the map, a bridge and the street beneath it may never connect.",
  },
  {
    answer: "Tree",
    options: ["Arrow", "Tree", "House"],
    clue: "Three tiers of branches sit above a short trunk. What is growing here?",
    path: "M50 8L73 35L63 35L84 60L68 60L90 80L59 80L59 94L41 94L41 80L10 80L32 60L16 60L37 35L27 35Z",
    tip: "Branch tips need room on the street grid. A larger drawing can preserve more of them.",
  },
  {
    answer: "Fish",
    options: ["Fish", "Leaf", "Moon"],
    clue: "A rounded body meets a triangular tail. Which animal is swimming?",
    path: "M12 50Q44 5 75 40L95 23L90 50L95 77L75 60Q44 95 12 50Z",
    tip: "A fish needs a distinct tail. Its outline still has to follow connected paths on land.",
  },
  {
    answer: "Lightning",
    options: ["Star", "Arrow", "Lightning"],
    clue: "A sharp zigzag falls from top to bottom. What flashes in the sky?",
    path: "M57 5L18 57L44 57L36 95L83 39L56 39Z",
    tip: "Long straight sections and clear corners help a lightning bolt survive street detours.",
  },
  {
    answer: "Crown",
    options: ["Mountain", "Crown", "Sailboat"],
    clue: "Three high points sit above one broad base. What would a king wear?",
    path: "M12 25L32 48L50 12L68 48L88 25L78 85L22 85Z",
    tip: "A crown needs the gaps between its points as much as the points themselves.",
  },
];

export default function WaitingSketchGame() {
  const [open, setOpen] = useState(() => !window.matchMedia("(max-width: 48rem)").matches);
  const [index, setIndex] = useState(0);
  const [deck, setDeck] = useState(() => shuffled(SKETCHES));
  const [answer, setAnswer] = useState(null);
  const [score, setScore] = useState(0);
  const [answered, setAnswered] = useState(0);
  const panelRef = useRef(null);
  const sketch = deck[index];
  useEffect(() => {
    if (open && window.matchMedia("(max-width: 48rem)").matches) {
      panelRef.current?.scrollIntoView({ block: "nearest", behavior: "auto" });
    }
  }, [open, answer, index]);
  return (
    <details ref={panelRef} className="waiting-game" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>
        <span><strong>Guess the sketch</strong><small>A quick GPS-art challenge while the planner works</small></span>
        <span aria-hidden="true">{open ? "−" : "+"}</span>
      </summary>
      <div className="waiting-game-body">
        <svg viewBox="0 0 100 100" aria-hidden="true"><path d={sketch.path} /></svg>
        <div>
          <p>{sketch.clue}</p>
          <div className="waiting-game-answers" role="group" aria-label="Sketch answers">
            {sketch.options.map((option) => (
              <button key={option} type="button" aria-pressed={answer === option} disabled={answer !== null} onClick={() => {
                setAnswer(option);
                setAnswered((current) => current + 1);
                if (option === sketch.answer) setScore((current) => current + 1);
              }}>
                {option}
              </button>
            ))}
          </div>
        </div>
        {answer && <p className="waiting-game-feedback" role="status">
          <strong>{answer === sketch.answer ? "You got it!" : `It’s a ${sketch.answer.toLowerCase()}.`}</strong>{" "}{sketch.tip}
        </p>}
        <div className="waiting-game-footer">
          <small>Sketch {index + 1}/{SKETCHES.length} · {score}/{answered} correct<br />Illustration · your route keeps generating</small>
          <button type="button" onClick={() => {
            if (index === deck.length - 1) {
              const next = shuffled(SKETCHES);
              if (next[0] === sketch) [next[0], next[1]] = [next[1], next[0]];
              setDeck(next);
            }
            setIndex((current) => (current + 1) % SKETCHES.length);
            setAnswer(null);
          }}>Next sketch →</button>
        </div>
      </div>
    </details>
  );
}

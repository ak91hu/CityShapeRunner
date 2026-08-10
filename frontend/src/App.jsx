import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  editRoute,
  generate as generateRoute,
  listGallery,
  publishGalleryImage,
  recordRouteAcceptance,
  removeGalleryImage,
} from "./api.js";

const RouteMap = lazy(() => import("./RouteMap.jsx"));
const GALLERY_REMOVAL_STORAGE_KEY = "gps-art-gallery-removal-tokens-v1";

const QUICK_IDEAS = [
  { glyph: "♥", label: "Heart", category: "Simple shapes", featured: true, prompt: "a heart run in Budapest, about 8 km" },
  { glyph: "★", label: "Star", category: "Simple shapes", featured: true, prompt: "a star bike route in Debrecen, about 20 km" },
  { glyph: "○", label: "Circle", category: "Simple shapes", featured: true, prompt: "a circle run in Kecskemét, about 8 km" },
  { glyph: "◆", label: "Diamond", category: "Simple shapes", featured: true, prompt: "a diamond run in Szombathely, about 8 km" },
  { glyph: "△", label: "Triangle", category: "Simple shapes", featured: true, prompt: "a triangle run in Tatabánya, about 10 km" },
  { glyph: "□", label: "Square", category: "Simple shapes", featured: true, prompt: "a square run in Szombathely, about 8 km" },
  { glyph: "∞", label: "Infinity", category: "Simple shapes", featured: true, prompt: "an infinity run in Szeged, about 10 km" },
  { glyph: "➜", label: "Arrow", category: "Simple shapes", featured: true, prompt: "an arrow run in Siófok, about 8 km" },
  { glyph: "✚", label: "Cross", category: "Simple shapes", featured: true, prompt: "a cross run in Nyíregyháza, about 8 km" },
  { glyph: "ϟ", label: "Lightning", category: "Simple shapes", featured: true, prompt: "a lightning run in Cegléd, about 8 km" },
  { glyph: "∿", label: "Wave", category: "Simple shapes", featured: true, prompt: "a wave run in Siófok, about 8 km" },
  { glyph: "☾", label: "Moon", category: "Simple shapes", featured: true, prompt: "a moon run in Kecskemét, about 8 km" },
  { glyph: "⬡", label: "Hexagon", category: "Simple shapes", prompt: "a hexagon run in Győr, about 8 km" },
  { glyph: "8", label: "Octagon", category: "Simple shapes", prompt: "an octagon run in Kecskemét, about 10 km" },
  { glyph: "◒", label: "Teardrop", category: "Simple shapes", prompt: "a teardrop run in Szeged, about 10 km" },
  { glyph: "◈", label: "Shield", category: "Simple shapes", prompt: "a shield run in Debrecen, about 12 km" },
  { glyph: "♧", label: "Clover", category: "Simple shapes", prompt: "a clover run in Szombathely, about 12 km" },
  { glyph: "◎", label: "Spiral", category: "Simple shapes", prompt: "a spiral bike route in Budapest, about 20 km" },
  { glyph: "⧖", label: "Hourglass", category: "Simple shapes", prompt: "an hourglass run in Nyíregyháza, about 12 km" },
  { glyph: "✿", label: "Flower", category: "Nature", prompt: "a flower run in Debrecen, about 12 km" },
  { glyph: "♣", label: "Tree", category: "Nature", prompt: "a tree run in Tatabánya, about 10 km" },
  { glyph: "⌃", label: "Mountain", category: "Nature", prompt: "a mountain run in Miskolc, about 10 km" },
  { glyph: "Ƹ", label: "Butterfly", category: "Nature", prompt: "a butterfly run in Kecskemét, about 10 km" },
  { glyph: "☀", label: "Sun", category: "Nature", prompt: "a sun bike route in Debrecen, about 20 km" },
  { glyph: "◜", label: "Leaf", category: "Nature", prompt: "a leaf run in Eger, about 10 km" },
  { glyph: "♠", label: "Pine tree", category: "Nature", prompt: "a pine tree run in Sopron, about 12 km" },
  { glyph: "◠", label: "Mushroom", category: "Nature", prompt: "a mushroom run in Tatabánya, about 12 km" },
  { glyph: "☁", label: "Cloud", category: "Nature", prompt: "a cloud run in Győr, about 10 km" },
  { glyph: "❄", label: "Snowflake", category: "Nature", prompt: "a snowflake bike route in Debrecen, about 24 km" },
  { glyph: "Ψ", label: "Cactus", category: "Nature", prompt: "a cactus run in Szeged, about 12 km" },
  { glyph: "●", label: "Apple", category: "Nature", prompt: "an apple run in Kecskemét, about 10 km" },
  { glyph: "◐", label: "Pear", category: "Nature", prompt: "a pear run in Eger, about 10 km" },
  { glyph: "♤", label: "Tulip", category: "Nature", prompt: "a tulip run in Debrecen, about 12 km" },
  { glyph: "♨", label: "Flame", category: "Nature", prompt: "a flame run in Cegléd, about 12 km" },
  { glyph: "✣", label: "Maple leaf", category: "Nature", prompt: "a maple leaf bike route in Budapest, about 24 km" },
  { glyph: "⌃", label: "Cat", category: "Animals", prompt: "a cat run in Tatabánya, about 10 km" },
  { glyph: "⌁", label: "Dog", category: "Animals", prompt: "a dog run in Tatabánya, about 10 km" },
  { glyph: "≈", label: "Fish", category: "Animals", prompt: "a fish run in Siófok, about 12 km" },
  { glyph: "⌁", label: "Bird", category: "Animals", prompt: "a bird run in Szeged, about 12 km" },
  { glyph: "◠", label: "Rabbit", category: "Animals", prompt: "a rabbit bike route in Kecskemét, about 20 km" },
  { glyph: "♞", label: "Horse", category: "Animals", prompt: "a horse bike route in Debrecen, about 22 km" },
  { glyph: "∽", label: "Dolphin", category: "Animals", prompt: "a dolphin bike route in Siófok, about 20 km" },
  { glyph: "ϟ", label: "Dragon", category: "Animals", prompt: "a dragon bike route in Budapest, about 28 km" },
  { glyph: "◉", label: "Turtle", category: "Animals", prompt: "a turtle run in Keszthely, about 14 km" },
  { glyph: "≋", label: "Whale", category: "Animals", prompt: "a whale bike route in Siófok, about 22 km" },
  { glyph: "▶", label: "Shark", category: "Animals", prompt: "a shark bike route in Szeged, about 22 km" },
  { glyph: "⋏", label: "Fox", category: "Animals", prompt: "a fox run in Sopron, about 14 km" },
  { glyph: "◉", label: "Owl", category: "Animals", prompt: "an owl run in Eger, about 14 km" },
  { glyph: "≈", label: "Duck", category: "Animals", prompt: "a duck run in Keszthely, about 12 km" },
  { glyph: "@", label: "Snail", category: "Animals", prompt: "a snail run in Győr, about 12 km" },
  { glyph: "Ɛ", label: "Elephant", category: "Animals", prompt: "an elephant bike route in Budapest, about 26 km" },
  { glyph: "⌁", label: "Bat", category: "Animals", prompt: "a bat run in Miskolc, about 14 km" },
  { glyph: "◉", label: "Bear", category: "Animals", prompt: "a bear run in Tatabánya, about 14 km" },
  { glyph: "◒", label: "Penguin", category: "Animals", prompt: "a penguin run in Szombathely, about 14 km" },
  { glyph: "⚓", label: "Anchor", category: "Objects", prompt: "an anchor bike route in Siófok, about 22 km" },
  { glyph: "⚿", label: "Key", category: "Objects", prompt: "a key bike route in Győr, about 18 km" },
  { glyph: "▣", label: "Mug", category: "Objects", prompt: "a mug bike route in Budapest, about 20 km" },
  { glyph: "♪", label: "Musical note", category: "Objects", prompt: "a musical note bike route in Szeged, about 18 km" },
  { glyph: "⛵", label: "Sailboat", category: "Objects", prompt: "a sailboat bike route in Siófok, about 24 km" },
  { glyph: "⌂", label: "House", category: "Objects", prompt: "a house run in Kecskemét, about 12 km" },
  { glyph: "↑", label: "Rocket", category: "Objects", prompt: "a rocket bike route in Debrecen, about 22 km" },
  { glyph: "✈", label: "Airplane", category: "Objects", prompt: "an airplane bike route in Budapest, about 24 km" },
  { glyph: "▰", label: "Car", category: "Objects", prompt: "a car run in Győr, about 14 km" },
  { glyph: "☂", label: "Umbrella", category: "Objects", prompt: "an umbrella run in Szeged, about 14 km" },
  { glyph: "◇", label: "Bell", category: "Objects", prompt: "a bell run in Eger, about 12 km" },
  { glyph: "♫", label: "Guitar", category: "Objects", prompt: "a guitar bike route in Budapest, about 24 km" },
  { glyph: "♜", label: "Castle", category: "Objects", prompt: "a castle bike route in Székesfehérvár, about 24 km" },
  { glyph: "♕", label: "Trophy", category: "Objects", prompt: "a trophy bike route in Debrecen, about 22 km" },
  { glyph: "♛", label: "Crown", category: "Symbols", prompt: "a crown run in Székesfehérvár, about 10 km" },
  { glyph: "☠", label: "Skull", category: "Symbols", prompt: "a skull bike route in Miskolc, about 22 km" },
  { glyph: "≋", label: "DNA helix", category: "Symbols", prompt: "a DNA helix bike route in Budapest, about 25 km" },
  { glyph: "◰", label: "Speech bubble", category: "Symbols", prompt: "a speech bubble run in Debrecen, about 12 km" },
  { glyph: "⌖", label: "Location pin", category: "Symbols", prompt: "a location pin run in Győr, about 12 km" },
  { glyph: "A", label: "Letter A", category: "Letters, numbers & text", prompt: "draw the letter A while running in Miskolc, about 10 km" },
  { glyph: "C", label: "Letter C", category: "Letters, numbers & text", prompt: "draw the letter C while running in Szeged, about 8 km" },
  { glyph: "L", label: "Letter L", category: "Letters, numbers & text", prompt: "draw the letter L while running in Kecskemét, about 8 km" },
  { glyph: "M", label: "Letter M", category: "Letters, numbers & text", prompt: "draw the letter M while running in Debrecen, about 10 km" },
  { glyph: "N", label: "Letter N", category: "Letters, numbers & text", prompt: "draw the letter N while running in Nyíregyháza, about 10 km" },
  { glyph: "S", label: "Letter S", category: "Letters, numbers & text", prompt: "draw the letter S while running in Szeged, about 10 km" },
  { glyph: "U", label: "Letter U", category: "Letters, numbers & text", prompt: "draw the letter U while running in Győr, about 10 km" },
  { glyph: "V", label: "Letter V", category: "Letters, numbers & text", prompt: "draw the letter V while running in Veszprém, about 8 km" },
  { glyph: "Z", label: "Letter Z", category: "Letters, numbers & text", prompt: "draw the letter Z while running in Zalaegerszeg, about 10 km" },
  { glyph: "2", label: "Number 2", category: "Letters, numbers & text", prompt: "draw the number 2 while running in Eger, about 8 km" },
  { glyph: "7", label: "Number 7", category: "Letters, numbers & text", prompt: "draw the number 7 while running in Debrecen, about 8 km" },
  { glyph: "42", label: "Number 42", category: "Letters, numbers & text", prompt: "draw the number 42 while cycling in Eger, about 20 km" },
  { glyph: "GPS", label: "Text GPS", category: "Letters, numbers & text", prompt: "write GPS while cycling in Budapest, about 25 km" },
];

const IDEA_CATEGORIES = ["Simple shapes", "Nature", "Animals", "Objects", "Symbols", "Letters, numbers & text"];
const FEATURED_IDEAS = QUICK_IDEAS.filter((idea) => idea.featured).slice(0, 6);

const HUNGARIAN_CITIES = [
  "Budapest",
  "Debrecen",
  "Szeged",
  "Miskolc",
  "Pécs",
  "Győr",
  "Nyíregyháza",
  "Kecskemét",
  "Székesfehérvár",
  "Szombathely",
  "Érd",
  "Szolnok",
  "Tatabánya",
  "Sopron",
  "Kaposvár",
  "Veszprém",
  "Zalaegerszeg",
  "Békéscsaba",
  "Eger",
  "Dunakeszi",
  "Nagykanizsa",
  "Hódmezővásárhely",
  "Dunaújváros",
  "Szigetszentmiklós",
  "Cegléd",
  "Vác",
  "Mosonmagyaróvár",
  "Gödöllő",
  "Baja",
  "Salgótarján",
  "Ózd",
  "Szekszárd",
  "Hajdúböszörmény",
  "Budaörs",
  "Esztergom",
  "Szentendre",
  "Kiskunfélegyháza",
  "Pápa",
  "Gyula",
  "Gyöngyös",
  "Ajka",
  "Kiskunhalas",
  "Jászberény",
  "Orosháza",
  "Szentes",
  "Gyál",
  "Hajdúszoboszló",
  "Siófok",
  "Dunaharaszti",
  "Tata",
];

// The official Lake Balaton shore-municipality list contains 45 places.
// Siófok remains in the main Hungary group above, so it is omitted here to
// keep every select value unique.
const BALATON_SHORE_CITIES = [
  "Alsóörs",
  "Aszófő",
  "Ábrahámhegy",
  "Badacsonytomaj",
  "Badacsonytördemic",
  "Balatonakali",
  "Balatonakarattya",
  "Balatonalmádi",
  "Balatonberény",
  "Balatonboglár",
  "Balatonederics",
  "Balatonfenyves",
  "Balatonfőkajár",
  "Balatonföldvár",
  "Balatonfüred",
  "Balatonfűzfő",
  "Balatongyörök",
  "Balatonkenese",
  "Balatonkeresztúr",
  "Balatonlelle",
  "Balatonmáriafürdő",
  "Balatonőszöd",
  "Balatonrendes",
  "Balatonszabadi",
  "Balatonszárszó",
  "Balatonszemes",
  "Balatonszentgyörgy",
  "Balatonszepezd",
  "Balatonudvari",
  "Balatonvilágos",
  "Csopak",
  "Fonyód",
  "Gyenesdiás",
  "Keszthely",
  "Kővágóörs",
  "Örvényes",
  "Paloznak",
  "Révfülöp",
  "Szántód",
  "Szigliget",
  "Tihany",
  "Vonyarcvashegy",
  "Zamárdi",
  "Zánka",
];

const EUROPEAN_CITIES = [
  "London",
  "Paris",
  "Berlin",
  "Madrid",
  "Rome",
  "Barcelona",
  "Vienna",
  "Amsterdam",
  "Prague",
  "Brussels",
  "Copenhagen",
  "Stockholm",
  "Oslo",
  "Helsinki",
  "Warsaw",
  "Kraków",
  "Bratislava",
  "Ljubljana",
  "Zagreb",
  "Bucharest",
  "Sofia",
  "Athens",
  "Dublin",
  "Munich",
  "Milan",
  "Lisbon",
  "Porto",
  "Zurich",
  "Tallinn",
  "Riga",
];

const SUGGEST_CITY_GROUPS = [
  { label: "Hungary", cities: HUNGARIAN_CITIES },
  { label: "Lake Balaton shore", cities: BALATON_SHORE_CITIES },
  { label: "Europe", cities: EUROPEAN_CITIES },
];
const SUGGEST_CITIES = [
  ...HUNGARIAN_CITIES,
  ...BALATON_SHORE_CITIES,
  ...EUROPEAN_CITIES,
];

const PROMPT_LIMIT = 320;
const PROMPT_CONTROL_CHARACTERS = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/u;
const PROMPT_MEANINGFUL_CHARACTER = /[\p{L}\p{N}]/u;

function normaliseRoutePrompt(value) {
  return value.normalize("NFKC").replace(/\s+/gu, " ").trim();
}

function validateRoutePrompt(value) {
  const normalised = value.normalize("NFKC");
  if (PROMPT_CONTROL_CHARACTERS.test(normalised)) {
    return {
      value: normaliseRoutePrompt(normalised),
      error: "Remove unsupported control characters from the route idea.",
    };
  }

  const cleaned = normaliseRoutePrompt(normalised);
  if (!cleaned) {
    return {
      value: cleaned,
      error: "Enter a route idea. Try ‘a heart run in Budapest, about 8 km’.",
    };
  }
  if (cleaned.length > PROMPT_LIMIT) {
    return {
      value: cleaned,
      error: `Keep the route idea to ${PROMPT_LIMIT} characters or fewer.`,
    };
  }
  if (!PROMPT_MEANINGFUL_CHARACTER.test(cleaned)) {
    return {
      value: cleaned,
      error: "Include a shape, word, letter, or number to draw.",
    };
  }
  return { value: cleaned, error: "" };
}

function distanceLimits(sport) {
  return sport === "bike"
    ? { minimum: 10, maximum: 200, activity: "cycling" }
    : { minimum: 3, maximum: 60, activity: "running" };
}

function validateSuggestion({ city, sport, distance }) {
  const errors = {};
  if (!SUGGEST_CITIES.includes(city)) {
    errors.city = "Choose a city from the list.";
  }
  if (!["run", "bike"].includes(sport)) {
    errors.sport = "Choose running or cycling.";
  }

  const { minimum, maximum, activity } = distanceLimits(sport);
  const numericDistance = Number(distance);
  if (String(distance).trim() === "") {
    errors.distance = "Enter a distance in kilometres.";
  } else if (!Number.isFinite(numericDistance)) {
    errors.distance = "Enter the distance as a number.";
  } else if (!Number.isInteger(numericDistance)) {
    errors.distance = "Enter the distance in whole kilometres.";
  } else if (numericDistance < minimum || numericDistance > maximum) {
    errors.distance = `Enter a ${activity} distance from ${minimum} to ${maximum} km.`;
  }

  return { errors, numericDistance };
}

const GATE_COPY = {
  selected_shape: {
    label: "Drawing",
    description: "This route uses the drawing you chose.",
  },
  road_network: {
    label: "Follows connected streets",
    description: "The route uses connected roads or paths instead of straight guide lines.",
  },
  overall_score: {
    label: "Overall match",
    description: "A combined look at the drawing, distance, and start-to-finish gap.",
  },
  shape_fidelity: {
    label: "Shape match",
    description: "How closely the route still looks like your drawing.",
  },
  spatial_similarity: {
    label: "Line order",
    description: "The route traces the parts of the drawing in the right order.",
  },
  coverage_similarity: {
    label: "Outline coverage",
    description: "The route covers the full drawing without skipping large sections.",
  },
  turning_similarity: {
    label: "Turns and curves",
    description: "The drawing’s distinctive corners and curves are still visible.",
  },
  landmark_similarity: {
    label: "Key points",
    description: "Important tips, corners, and notches are in the right places.",
  },
  reversal_similarity: {
    label: "No doubled-back lines",
    description: "The street route does not add U-turns that muddle the drawing.",
  },
  length_similarity: {
    label: "Extra detours",
    description: "Street detours do not add confusing extra lines to the drawing.",
  },
  extent_similarity: {
    label: "Shape proportions",
    description: "The drawing keeps roughly the same width and height.",
  },
  distance_fit: {
    label: "Requested distance",
    description: "The route is close to the distance you asked for.",
  },
  closure: {
    label: "Returns to the start",
    description: "For a loop, the finish is close to the starting point.",
  },
};

function formatMetric(value, digits = 2) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
}

function formatPercent(value) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${Math.round(value * 100)}%`
    : "—";
}

function formatSigned(value, digits = 2, suffix = "") {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}${suffix}`;
}

function formatGateValue(gate) {
  if (!gate?.applies) return "Not required";
  if (typeof gate.value === "boolean") return gate.value ? "Yes" : "No";
  if (typeof gate.value === "number") return formatPercent(gate.value);
  return normaliseLabel(gate.value);
}

function formatGateMinimum(gate) {
  if (!gate?.applies || typeof gate.minimum === "boolean") return "";
  if (typeof gate.minimum === "number") return `target ${formatPercent(gate.minimum)}`;
  return gate.minimum ? `target: ${normaliseLabel(gate.minimum)}` : "";
}

function explainGateResult(gate) {
  if (!gate?.applies) return "Not needed for this route.";
  if (typeof gate.value === "boolean") {
    return gate.passed
      ? "Looks good."
      : "We couldn’t confirm this. Check the map before using the route.";
  }
  if (typeof gate.value === "number" && typeof gate.minimum === "number") {
    const difference = Math.round(Math.abs(gate.value - gate.minimum) * 100);
    return gate.passed
      ? `${difference} point${difference === 1 ? "" : "s"} above the target.`
      : `${difference} point${difference === 1 ? "" : "s"} below the target. Check how it looks on the map.`;
  }
  return gate.passed
    ? "Matches your choice."
    : "Doesn’t match your choice.";
}

function normaliseLabel(value) {
  if (!value) return "—";
  return String(value)
    .replaceAll("_", " ")
    .replace(/(^|[\s-])(\p{L})/gu, (_, prefix, letter) => `${prefix}${letter.toUpperCase()}`);
}

function safeFilePart(value) {
  const cleaned = String(value || "gps-art-route")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 48);
  return cleaned || "gps-art-route";
}

function saveFile(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

function readGalleryRemovalTokens() {
  try {
    const stored = JSON.parse(
      window.localStorage.getItem(GALLERY_REMOVAL_STORAGE_KEY) ?? "{}",
    );
    if (!stored || typeof stored !== "object" || Array.isArray(stored)) return {};
    return Object.fromEntries(
      Object.entries(stored).filter(
        ([publicId, token]) => publicId && typeof token === "string" && token,
      ),
    );
  } catch {
    return {};
  }
}

function rememberGalleryRemovalToken(publicId, token) {
  const next = { ...readGalleryRemovalTokens(), [publicId]: token };
  try {
    window.localStorage.setItem(GALLERY_REMOVAL_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // A private-browsing/storage failure must not turn a successful upload
    // into a false publication error or encourage a duplicate retry.
  }
  return next;
}

function forgetGalleryRemovalToken(publicId) {
  const next = { ...readGalleryRemovalTokens() };
  delete next[publicId];
  try {
    window.localStorage.setItem(GALLERY_REMOVAL_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // The server deletion still succeeded; keep the UI truthful for this session.
  }
  return next;
}

function mergeGalleryAssets(current, received, { replace, publishedAsset, removedIds }) {
  const visibleReceived = (Array.isArray(received) ? received : []).filter(
    (asset) => asset?.id && !removedIds.has(asset.id),
  );
  let next = replace ? visibleReceived : [...current, ...visibleReceived];
  if (publishedAsset?.id && !removedIds.has(publishedAsset.id)) {
    next = [publishedAsset, ...next.filter((asset) => asset.id !== publishedAsset.id)];
  }
  const seen = new Set();
  return next.filter((asset) => {
    if (!asset?.id || seen.has(asset.id) || removedIds.has(asset.id)) return false;
    seen.add(asset.id);
    return true;
  });
}

function sampleControlPoints(points, maximum = 18) {
  const valid = (Array.isArray(points) ? points : []).filter(
    (point) =>
      Array.isArray(point) &&
      Number.isFinite(point[0]) &&
      Number.isFinite(point[1]),
  );
  if (valid.length <= maximum) return valid.map((point) => [...point]);
  const indices = Array.from(
    { length: maximum },
    (_, index) => Math.round((index * (valid.length - 1)) / (maximum - 1)),
  );
  return [...new Set(indices)].map((index) => [...valid[index]]);
}

function MetricCard({ label, value, detail, tone = "neutral" }) {
  return (
    <div className={`metric metric--${tone}`}>
      <dt>{label}</dt>
      <dd>{value}</dd>
      {detail && <dd className="metric-detail">{detail}</dd>}
    </div>
  );
}

function LoadingState({ onCancel }) {
  return (
    <section className="loading-card" aria-live="polite" aria-busy="true">
      <div className="route-loader" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </div>
      <div>
        <h2>Finding routes</h2>
        <p>Testing nearby streets against your drawing. Complex drawings can take longer.</p>
      </div>
      <button type="button" className="button button--quiet" onClick={onCancel}>
        Cancel
      </button>
    </section>
  );
}

function GallerySection({ refreshKey = 0, publishedAsset = null }) {
  const [assets, setAssets] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [configured, setConfigured] = useState(true);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [removalTokens, setRemovalTokens] = useState(readGalleryRemovalTokens);
  const removedAssetIdsRef = useRef(new Set());

  const loadGalleryPage = useCallback(async (cursor = null, replace = false) => {
    if (replace) setLoading(true);
    else setLoadingMore(true);
    setError("");
    try {
      const response = await listGallery({ cursor, limit: 24 });
      setConfigured(response.configured !== false);
      setAssets((current) =>
        mergeGalleryAssets(current, response.assets, {
          replace,
          publishedAsset,
          removedIds: removedAssetIdsRef.current,
        }),
      );
      setNextCursor(response.next_cursor ?? null);
    } catch (galleryError) {
      setError(galleryError.message || "We couldn’t load the gallery. Please try again.");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [publishedAsset]);

  useEffect(() => {
    setRemovalTokens(readGalleryRemovalTokens());
    loadGalleryPage(null, true);
  }, [loadGalleryPage, refreshKey]);

  const removeAsset = useCallback(async (asset) => {
    const token = removalTokens[asset.id];
    if (!token || !window.confirm("Remove your map from the public gallery?")) return;
    setError("");
    try {
      await removeGalleryImage({ public_id: asset.id, removal_token: token });
      removedAssetIdsRef.current.add(asset.id);
      setAssets((current) => current.filter((item) => item.id !== asset.id));
      setRemovalTokens(forgetGalleryRemovalToken(asset.id));
    } catch (removalError) {
      setError(removalError.message || "We couldn’t remove that map. Please try again.");
    }
  }, [removalTokens]);

  return (
    <section className="gallery" id="gallery" aria-labelledby="gallery-title">
      <div className="section-heading gallery-heading">
        <div>
          <h2 id="gallery-title">Public gallery</h2>
          <p>Map images shared by users. Prompts, profiles, and route files are not published.</p>
        </div>
        <a className="button button--quiet" href="#route-designer">
          Plan a route
        </a>
      </div>

      {loading && (
        <div className="gallery-state" role="status">
          Loading public map screenshots…
        </div>
      )}
      {!loading && !configured && (
        <div className="gallery-state">
          <strong>Gallery unavailable</strong>
          <span>Route planning and downloads still work.</span>
        </div>
      )}
      {error && (
        <p className="gallery-error" role="alert">
          {error}
        </p>
      )}
      {!loading && configured && assets.length === 0 && !error && (
        <div className="gallery-state">
          <strong>No maps have been shared.</strong>
          <span>Publish a route map to add the first.</span>
        </div>
      )}
      {assets.length > 0 && (
        <div className="gallery-grid">
          {assets.map((asset) => (
            <article className="gallery-card" key={asset.id}>
              <a href={asset.image_url} target="_blank" rel="noreferrer">
                <img
                  src={asset.image_url}
                  alt="Anonymous GPS art route on an OpenStreetMap street map"
                  loading="lazy"
                  width={asset.width || undefined}
                  height={asset.height || undefined}
                />
              </a>
              {removalTokens[asset.id] && (
                <div>
                  <button type="button" onClick={() => removeAsset(asset)}>
                    Remove my post
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
      {nextCursor && (
        <button
          type="button"
          className="button button--secondary gallery-more"
          onClick={() => loadGalleryPage(nextCursor, false)}
          disabled={loadingMore}
        >
          {loadingMore ? "Loading…" : "Show more routes"}
        </button>
      )}
      <p className="gallery-attribution">
        Map data ©{" "}
        <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
          OpenStreetMap contributors
        </a>
        .
      </p>
    </section>
  );
}

function ResultPanel({ result, onDownload, onGalleryPublished, focusRef }) {
  const candidates = result.candidates ?? [];
  const [selectedCandidateId, setSelectedCandidateId] = useState(
    candidates[0]?.id ?? "best",
  );
  const [editing, setEditing] = useState(false);
  const [controlPoints, setControlPoints] = useState([]);
  const [editedRoute, setEditedRoute] = useState(null);
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState("");
  const [editDirty, setEditDirty] = useState(false);
  const [acceptedRouteIds, setAcceptedRouteIds] = useState(() => new Set());
  const [galleryConsent, setGalleryConsent] = useState(false);
  const [galleryBusy, setGalleryBusy] = useState(false);
  const [galleryError, setGalleryError] = useState("");
  const [publishedAsset, setPublishedAsset] = useState(null);
  const mapCaptureRef = useRef(null);

  useEffect(() => {
    setSelectedCandidateId(candidates[0]?.id ?? "best");
    setEditing(false);
    setControlPoints([]);
    setEditedRoute(null);
    setEditError("");
    setEditDirty(false);
    setAcceptedRouteIds(new Set());
    setGalleryConsent(false);
    setGalleryBusy(false);
    setGalleryError("");
    setPublishedAsset(null);
  }, [result.request_id, result.prompt]);

  const selectedCandidate =
    candidates.find((candidate) => candidate.id === selectedCandidateId) ??
    candidates[0] ??
    null;
  const activeRoute =
    editedRoute ??
    selectedCandidate ?? {
      id: "best",
      shape_name: result.shape?.name,
      points_preview: result.points_preview,
      ideal_preview: result.ideal_preview,
      distance_km: result.distance_km,
      snapped: result.snapped,
      closed: result.shape?.closed,
      target_distance_km: result.intent?.distance_km,
      validation: result.validation,
      below_recommended: result.below_threshold,
      verification: result.route_verification,
      details: result.route_details,
      gpx: result.gpx,
      tcx: result.tcx,
      gallery_publish_token: result.gallery_publish_token,
    };
  const validation = activeRoute.validation ?? result.validation;
  const verification = activeRoute.verification ?? result.route_verification;
  const routeDetails = activeRoute.details ?? result.route_details;
  const distanceDetails = routeDetails?.distance ?? {};
  const routingDetails = routeDetails?.routing ?? {};
  const placementDetails = routeDetails?.placement ?? {};
  const deviationDetails = routeDetails?.deviation ?? {};
  const score = validation?.score;
  const automaticChecksPassed = verification
    ? Boolean(verification.passed)
    : Boolean(activeRoute.snapped) && !Boolean(activeRoute.below_recommended);
  const activeRouteId = String(activeRoute.id ?? "best");
  const userAccepted = acceptedRouteIds.has(activeRouteId);
  const exportReady = automaticChecksPassed || userAccepted;
  const exportBlockedByPendingEdits = editing && editDirty;
  const qualityTone = score == null ? "neutral" : automaticChecksPassed ? "good" : "warn";
  const shapeName = normaliseLabel(activeRoute.shape_name ?? result.shape?.name);
  const fitDecision = result.fit_decision;
  const requestedShape = normaliseLabel(
    fitDecision?.requested_shape ?? result.requested_shape ?? result.shape?.name,
  );
  const city = result.intent?.city ? normaliseLabel(result.intent.city) : "your selected area";
  const historyRows = (result.history ?? []).filter((entry) => Number.isFinite(entry.score));
  const auditRows = Array.isArray(result.candidate_audit) ? result.candidate_audit : [];
  const candidateSummary = result.candidate_summary ?? {};
  const auditedCount = Number.isFinite(candidateSummary.audited_count)
    ? candidateSummary.audited_count
    : candidates.length;
  const reviewCount = Number.isFinite(candidateSummary.review_count)
    ? candidateSummary.review_count
    : Number.isFinite(candidateSummary.rejected_selected_shape_count)
      ? candidateSummary.rejected_selected_shape_count
    : 0;
  const otherShapeCount = Number.isFinite(candidateSummary.other_shape_count)
    ? candidateSummary.other_shape_count
    : 0;
  const issueList = [
    ...new Set([
      ...(validation?.issues ?? []),
      ...(editedRoute?.warnings ?? []),
      ...(result.errors ?? []),
    ]),
  ];
  const stateLabel = automaticChecksPassed
    ? "Ready to download"
    : userAccepted
      ? "Approved by you"
      : activeRoute.snapped
        ? "Check before downloading"
        : "Map preview only";
  const canPublishGallery = Boolean(
    activeRoute.gallery_publish_token &&
    activeRoute.snapped &&
    exportReady &&
    !editedRoute &&
    !editing,
  );

  useEffect(() => {
    setGalleryConsent(false);
    setGalleryError("");
    setPublishedAsset(null);
  }, [activeRouteId]);

  const resetEditor = useCallback(() => {
    setControlPoints(sampleControlPoints(activeRoute.points_preview));
    setEditError("");
    setEditDirty(false);
  }, [activeRoute.points_preview]);

  const handleEditPoint = useCallback(
    (index, point) => {
      setEditDirty(true);
      setControlPoints((current) => {
        const next = current.map((item) => [...item]);
        next[index] = point;
        if (activeRoute.closed && next.length > 1) {
          if (index === 0) next[next.length - 1] = [...point];
          if (index === next.length - 1) next[0] = [...point];
        }
        return next;
      });
    },
    [activeRoute.closed],
  );

  const rerouteEdited = useCallback(async () => {
    if (controlPoints.length < 2 || editBusy) return;
    setEditBusy(true);
    setEditError("");
    try {
      const response = await editRoute({
        control_points: controlPoints,
        reference_points:
          activeRoute.ideal_preview?.length > 1
            ? activeRoute.ideal_preview
            : controlPoints,
        sport: result.intent?.sport === "bike" ? "bike" : "run",
        closed: Boolean(activeRoute.closed),
        target_distance_km:
          activeRoute.target_distance_km ?? result.intent?.distance_km ?? null,
        name: `${shapeName} in ${city}`,
        shape_name: activeRoute.shape_name ?? result.shape?.name ?? "edited",
      });
      const editedRouteId = `${selectedCandidate?.id ?? "best"}-edited`;
      setAcceptedRouteIds((current) => {
        const next = new Set(current);
        next.delete(editedRouteId);
        return next;
      });
      setEditedRoute({
        ...activeRoute,
        id: editedRouteId,
        points_preview: response.points_preview,
        distance_km: response.distance_km,
        snapped: response.snapped,
        validation: response.validation,
        verification: response.route_verification,
        details: response.route_details,
        below_recommended:
          response.below_recommended ??
          !(
            response.snapped &&
            response.validation?.score >= 0.72 &&
            response.validation?.shape_fidelity >= 0.7 &&
            response.validation?.distance_fit >= 0.6 &&
            response.validation?.closure >= 0.6
          ),
        gpx: response.gpx,
        tcx: response.tcx,
        warnings: response.warnings,
      });
      setControlPoints(sampleControlPoints(response.points_preview));
      setEditDirty(false);
    } catch (error) {
      setEditError(error.message || "We couldn’t update that route. Please try again.");
    } finally {
      setEditBusy(false);
    }
  }, [
    activeRoute,
    city,
    controlPoints,
    editBusy,
    result.intent,
    selectedCandidate?.id,
    shapeName,
  ]);

  const publishMapScreenshot = useCallback(async () => {
    if (!canPublishGallery || !galleryConsent || galleryBusy) return;
    setGalleryBusy(true);
    setGalleryError("");
    try {
      const imageDataUrl = await mapCaptureRef.current?.capturePng();
      if (!imageDataUrl) throw new Error("The map isn’t ready to share yet.");
      const response = await publishGalleryImage({
        image_data_url: imageDataUrl,
        publish_token: activeRoute.gallery_publish_token,
        confirm_public_location: true,
      });
      rememberGalleryRemovalToken(response.asset.id, response.removal_token);
      setPublishedAsset(response.asset);
      onGalleryPublished?.(response.asset);
    } catch (publishError) {
      setGalleryError(
        publishError.message || "We couldn’t share the map. Please try again.",
      );
    } finally {
      setGalleryBusy(false);
    }
  }, [
    activeRoute.gallery_publish_token,
    canPublishGallery,
    galleryBusy,
    galleryConsent,
    onGalleryPublished,
  ]);

  return (
    <section
      ref={focusRef}
      className="result"
      aria-labelledby="result-title"
      tabIndex="-1"
    >
      <div className="section-heading">
        <div>
          <h2 id="result-title">
            {shapeName} in {city}
          </h2>
          {result.request_id && (
            <p className="debug-id">
              Route ID: <code>{result.request_id}</code>
            </p>
          )}
        </div>
        <span
          className={`route-state route-state--${automaticChecksPassed ? "good" : "warn"}`}
        >
          <span aria-hidden="true">{automaticChecksPassed || userAccepted ? "✓" : "!"}</span>
          {stateLabel}
        </span>
      </div>

      <div className="result-layout">
        <div className="map-card">
          <div className="candidate-toolbar">
            <label htmlFor="route-candidate">Route options</label>
            <select
              id="route-candidate"
              value={selectedCandidate?.id ?? "best"}
              onChange={(event) => {
                setSelectedCandidateId(event.target.value);
                setEditing(false);
                setEditedRoute(null);
                setControlPoints([]);
                setEditError("");
                setEditDirty(false);
                setGalleryConsent(false);
                setGalleryError("");
                setPublishedAsset(null);
              }}
            >
              {candidates.length > 0 ? (
                candidates.map((candidate, index) => (
                  <option key={candidate.id} value={candidate.id}>
                    {index + 1}. {normaliseLabel(candidate.shape_name)} ·{" "}
                    {formatPercent(candidate.validation?.score)} ·{" "}
                    {formatMetric(candidate.distance_km)} km ·{" "}
                    {candidate.verification?.passed ? "Ready" : "Needs a look"}
                  </option>
                ))
              ) : (
                <option value="best">Best route found</option>
              )}
            </select>
            <span>
              {candidates.length > 0
                ? `${candidates.length} option${candidates.length === 1 ? "" : "s"}: ${candidateSummary.verified_count ?? candidateSummary.accepted_count ?? 0} ready, ${reviewCount} need a look`
                : `${auditedCount} tried; showing the closest match`}
            </span>
          </div>

          {(activeRoute.points_preview ?? []).length > 0 ? (
            <Suspense
              fallback={
                <div className="route-map route-map--empty" role="status">
                  <span className="map-spinner" aria-hidden="true" />
                  <strong>Loading street route…</strong>
                </div>
              }
            >
              <RouteMap
                ref={mapCaptureRef}
                points={activeRoute.points_preview}
                idealPoints={activeRoute.ideal_preview ?? result.ideal_preview}
                landmarkPoints={
                  activeRoute.landmark_preview ?? result.landmark_preview
                }
                editPoints={controlPoints}
                shapeName={shapeName}
                roadRouted={Boolean(activeRoute.snapped)}
                accepted={exportReady}
                editing={editing}
                onEditPoint={handleEditPoint}
              />
            </Suspense>
          ) : (
            <div className="route-map route-map--empty" role="status">
              <strong>We couldn’t draw this route</strong>
              <span>Change the idea or choose another route.</span>
            </div>
          )}
          <div className="route-editor" aria-label="Route editor">
            <div>
              <strong>Edit route</strong>
              <p>Move a numbered point, then apply the changes.</p>
            </div>
            <div className="editor-actions">
              <button
                type="button"
                className="button button--secondary"
                onClick={() => {
                  resetEditor();
                  setEditing((value) => !value);
                }}
              >
                {editing
                  ? editDirty
                    ? "Discard point changes"
                    : "Close editor"
                  : "Edit this route"}
              </button>
              {editing && (
                <>
                  <button
                    type="button"
                    className="button button--quiet"
                    onClick={resetEditor}
                    disabled={editBusy}
                  >
                    Start over
                  </button>
                  <button
                    type="button"
                    className="button button--primary"
                    onClick={rerouteEdited}
                    disabled={editBusy || controlPoints.length < 2}
                  >
                    {editBusy ? "Applying changes…" : "Apply changes"}
                  </button>
                </>
              )}
            </div>
            {editError && (
              <p className="editor-error" role="alert">
                {editError}
              </p>
            )}
            {editedRoute && (
              <p className="editor-success" role="status">
                Changes saved — {formatMetric(editedRoute.distance_km)} km.
                {editedRoute.verification?.passed
                  ? " The route follows streets and passed every check."
                  : " Check the highlighted items before downloading."}
              </p>
            )}
          </div>
          <div className="map-caption">
            {(activeRoute.ideal_preview ?? result.ideal_preview ?? []).length > 1 && (
              <span>
                <span className="legend-line legend-line--guide" aria-hidden="true" /> Original
                drawing
              </span>
            )}
            {(activeRoute.landmark_preview ?? result.landmark_preview ?? []).length > 0 && (
              <span>
                <span className="legend-dot legend-dot--landmark" aria-hidden="true" /> Key
                points
              </span>
            )}
            <span>
              <span className="legend-dot legend-dot--start" aria-hidden="true" /> Start
            </span>
            <span>
              <span className="legend-dot legend-dot--finish" aria-hidden="true" /> Finish
            </span>
            <span className="point-count">
              {activeRoute.snapped
                ? `${(activeRoute.points_preview ?? []).length.toLocaleString()} of ${(
                    routingDetails.route_point_count ??
                    (activeRoute.points_preview ?? []).length
                  ).toLocaleString()} map points shown`
                : "Preview only — not matched to streets"}
            </span>
          </div>
        </div>

        <div className="result-sidebar">
          <dl className="metrics">
            <MetricCard
              label="Overall match"
              value={formatPercent(score)}
              detail="Combined score"
              tone={qualityTone}
            />
            <MetricCard
              label="Distance"
              value={
                activeRoute.distance_km != null
                  ? `${formatMetric(activeRoute.distance_km)} km`
                  : "—"
              }
              detail={normaliseLabel(result.intent?.sport)}
            />
            <MetricCard
              label="Shape match"
              value={formatPercent(validation?.shape_fidelity)}
              detail="Route against drawing"
              tone={validation?.shape_fidelity >= 0.7 ? "good" : "warn"}
            />
            <MetricCard
              label="Route options"
              value={
                Number.isFinite(candidateSummary.shown_count)
                  ? candidateSummary.shown_count
                  : candidates.length
              }
              detail={
                `${candidateSummary.verified_count ?? candidateSummary.accepted_count ?? 0} ready · ${reviewCount} review · ${auditedCount} tested${
                  Number.isFinite(result.preflight_count) && result.preflight_count > 0
                    ? ` · ${result.preflight_count} locations`
                    : ""
                }`
              }
              tone={(candidateSummary.verified_count ?? 0) > 0 ? "good" : "warn"}
            />
          </dl>

          {fitDecision && (
            <div className={`notice ${fitDecision.substituted ? "notice--success" : "notice--warning"}`}>
              <strong>
                {fitDecision.substituted
                  ? `${requestedShape} didn’t fit these streets — here’s a ${shapeName}`
                  : `Why this ${requestedShape} needs a closer look`}
              </strong>
              <ul className="decision-reasons">
                {(fitDecision.reasons ?? []).map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              {(fitDecision.candidates_tested ?? []).length > 0 && (
                <p>
                  Other shapes tried:{" "}
                  {fitDecision.candidates_tested.map(normaliseLabel).join(", ")}.
                </p>
              )}
            </div>
          )}

          {result.suggested_shape && !fitDecision?.substituted && (
            <div className="notice notice--info">
              <strong>Suggested shape</strong>
              <p>{normaliseLabel(result.suggested_shape)}</p>
              {result.suggestion_reason && <p>{result.suggestion_reason}</p>}
            </div>
          )}

          {!automaticChecksPassed && (
            <div className="notice notice--warning" role="status">
              <strong>Review this route</strong>
              <p>
                {!activeRoute.snapped
                  ? "The line could not be matched to connected streets and may cross inaccessible areas."
                  : "The street route differs from the drawing or requested distance. Check the map before downloading."}
              </p>
            </div>
          )}

          {verification?.gates?.length > 0 && (
            <details
              className={`verification-card verification-card--${automaticChecksPassed ? "pass" : "fail"}`}
            >
              <summary className="verification-heading">
                <span>
                  <span className="verification-title">
                    {automaticChecksPassed
                      ? "Checks passed"
                      : `${verification.failed_gates?.length ?? 0} item${verification.failed_gates?.length === 1 ? "" : "s"} to check`}
                  </span>
                </span>
                <span className="verification-count">
                  {verification.passed_count} of {verification.required_count} passed · show details
                </span>
              </summary>
              <div className="verification-body">
                <div className="score-explainer">
                  <strong>What the scores mean</strong>
                  <p>
                    Higher scores mean a closer match to the drawing. They do not measure traffic,
                    access, surface quality, or safety.
                  </p>
                </div>
                <ul className="gate-list">
                  {verification.gates
                    .filter((gate) => gate.applies)
                    .map((gate) => (
                      <li key={gate.key} className={gate.passed ? "gate--pass" : "gate--fail"}>
                        <span className="gate-icon" aria-hidden="true">
                          {gate.passed ? "✓" : "!"}
                        </span>
                        <span>
                          <strong>{GATE_COPY[gate.key]?.label ?? gate.label}</strong>
                          <small>{GATE_COPY[gate.key]?.description ?? gate.description}</small>
                          <small className="gate-interpretation">
                            {explainGateResult(gate)}
                          </small>
                        </span>
                        <span className="gate-value">
                          {formatGateValue(gate)}
                          {formatGateMinimum(gate) && <small>{formatGateMinimum(gate)}</small>}
                        </span>
                      </li>
                    ))}
                </ul>
              </div>
            </details>
          )}

          {routeDetails && (
            <details className="route-facts">
              <summary>Route details</summary>
              <p className="route-facts-intro">
                Street detour is the extra distance added by the road network. Average drift is
                the difference between the route and drawing.
              </p>
              <dl>
                <div>
                  <dt>Drawing</dt>
                  <dd>{shapeName}</dd>
                </div>
                <div>
                  <dt>Activity</dt>
                  <dd>{normaliseLabel(routingDetails.activity)}</dd>
                </div>
                <div>
                  <dt>Follows streets</dt>
                  <dd>{routingDetails.street_matched ? "Yes" : "No"}</dd>
                </div>
                <div>
                  <dt>Map points / drawing points</dt>
                  <dd>
                    {routingDetails.route_point_count ?? "—"} / {routingDetails.guide_point_count ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt>Route / requested distance</dt>
                  <dd>
                    {formatMetric(distanceDetails.actual_km)} km / {formatMetric(distanceDetails.target_km)} km
                  </dd>
                </div>
                <div>
                  <dt>Over / under your request</dt>
                  <dd>
                    {formatSigned(distanceDetails.difference_km, 2, " km")} ({formatSigned(
                      distanceDetails.difference_percent,
                      1,
                      "%",
                    )})
                  </dd>
                </div>
                <div>
                  <dt>Street detour</dt>
                  <dd>{formatMetric(distanceDetails.route_to_guide_ratio, 2)}×</dd>
                </div>
                <div>
                  <dt>Average drift from drawing</dt>
                  <dd>{formatPercent(deviationDetails.mean_outline_deviation_ratio)}</dd>
                </div>
                {activeRoute.closed && (
                  <div>
                    <dt>Start–finish gap</dt>
                    <dd>{formatMetric(routingDetails.closure_gap_m, 0)} m</dd>
                  </div>
                )}
                <div>
                  <dt>Rotation / size</dt>
                  <dd>
                    {formatMetric(placementDetails.rotation_deg, 1)}° / {formatMetric(
                      placementDetails.scale_m,
                      0,
                    )} m
                  </dd>
                </div>
                <div>
                  <dt>Moved north / east</dt>
                  <dd>
                    {formatSigned(placementDetails.lat_offset_m, 0, " m")} / {formatSigned(
                      placementDetails.lon_offset_m,
                      0,
                      " m",
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Starting position match</dt>
                  <dd>{formatPercent(placementDetails.preflight_score)}</dd>
                </div>
              </dl>
            </details>
          )}

          <div className="export-card">
            <div>
              <h3>{exportReady ? "Download route" : "Review before download"}</h3>
            </div>
            {!automaticChecksPassed && !userAccepted && (
              <p className="acceptance-copy">
                This route missed one or more checks. Inspect the map before choosing to download it.
              </p>
            )}
            <div className="download-actions">
              {!automaticChecksPassed && !userAccepted && activeRoute.gpx && (
                <button
                  type="button"
                  className="button button--primary accept-route-button"
                  onClick={() => {
                    setAcceptedRouteIds((current) => new Set(current).add(activeRouteId));
                    recordRouteAcceptance({
                      generation_request_id: result.request_id ?? null,
                      route_id: activeRouteId,
                      shape_name: activeRoute.shape_name ?? result.shape?.name ?? "route",
                      automatic_checks_passed: automaticChecksPassed,
                      snapped: Boolean(activeRoute.snapped),
                      failed_gates: verification?.failed_gates ?? [],
                      score: validation?.score ?? null,
                      shape_fidelity: validation?.shape_fidelity ?? null,
                      distance_km: activeRoute.distance_km ?? null,
                    }).catch(() => {
                      // Telemetry must never block the user's chosen export.
                    });
                    onDownload("gpx", activeRoute.gpx);
                  }}
                  disabled={exportBlockedByPendingEdits}
                >
                  Approve and download GPX
                </button>
              )}
              {exportReady && activeRoute.gpx && (
                <button
                  type="button"
                  className="button button--primary"
                  onClick={() => onDownload("gpx", activeRoute.gpx)}
                  disabled={exportBlockedByPendingEdits}
                >
                  {editedRoute?.gpx ? "Download edited GPX" : "Download GPX"}
                </button>
              )}
              {exportReady && activeRoute.tcx && (
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => onDownload("tcx", activeRoute.tcx)}
                  disabled={exportBlockedByPendingEdits}
                >
                  Download TCX
                </button>
              )}
            </div>
            {exportBlockedByPendingEdits && (
              <p className="pending-edit-note" role="status">
                Apply or discard your changes before downloading.
              </p>
            )}
            {activeRoute.gallery_publish_token && !editedRoute && (
              <div className="gallery-publish">
                <div>
                  <strong>Publish map image</strong>
                  <p>
                    Publishes the map, route line, location, and visible street names. Your prompt,
                    profile, and route file stay private.
                  </p>
                </div>
                {!publishedAsset ? (
                  <>
                    <label>
                      <input
                        type="checkbox"
                        checked={galleryConsent}
                        onChange={(event) => setGalleryConsent(event.target.checked)}
                        disabled={galleryBusy}
                      />
                      I understand that this location and its street names will be public.
                    </label>
                    <button
                      type="button"
                      className="button button--secondary"
                      onClick={publishMapScreenshot}
                      disabled={!canPublishGallery || !galleryConsent || galleryBusy}
                    >
                      {galleryBusy ? "Publishing…" : "Publish map"}
                    </button>
                  </>
                ) : (
                  <p className="gallery-publish-success" role="status">
                    Map published. <a href="#gallery">View in gallery</a>.
                  </p>
                )}
                {galleryError && (
                  <p className="gallery-publish-error" role="alert">
                    {galleryError}
                  </p>
                )}
                {!exportReady && (
                  <small>Review or approve this route before sharing it.</small>
                )}
                {editing && <small>Finish editing before sharing the map.</small>}
              </div>
            )}
            {!activeRoute.gpx && (
              <p className="export-unavailable">
                There isn’t enough route data to make a GPX file. Edit the route or create a new
                one, then try again.
              </p>
            )}
            <p className="safety-note">
              Check access, crossings, traffic, surfaces, and current conditions before using this
              route.
            </p>
          </div>
        </div>
      </div>

      {(issueList.length > 0 || historyRows.length > 0 || auditRows.length > 0) && (
        <div className="details-grid">
          {issueList.length > 0 && (
            <details className="detail-card">
              <summary>
                Route issues <span>{issueList.length}</span>
              </summary>
              <ul>
                {issueList.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            </details>
          )}

          {historyRows.length > 0 && (
            <details className="detail-card">
              <summary>
                Earlier versions <span>{historyRows.length}</span>
              </summary>
              <div className="table-wrap">
                <table>
                  <caption className="sr-only">Scores for earlier versions of this route</caption>
                  <thead>
                    <tr>
                      <th scope="col">Try</th>
                      <th scope="col">Score</th>
                      <th scope="col">Change</th>
                      <th scope="col">Shape match</th>
                      <th scope="col">Distance accuracy</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historyRows.map((entry, index) => (
                      <tr key={`${entry.iteration ?? index}-${index}`}>
                        <td data-label="Try">{entry.iteration ?? index}</td>
                        <td data-label="Score">{formatPercent(entry.score)}</td>
                        <td data-label="Change">
                          {Number.isFinite(entry.delta_vs_best)
                            ? `${entry.delta_vs_best >= 0 ? "+" : ""}${formatMetric(entry.delta_vs_best, 3)}`
                            : "—"}
                        </td>
                        <td data-label="Shape match">
                          {formatPercent(entry.fidelity ?? entry.shape_fidelity)}
                        </td>
                        <td data-label="Distance accuracy">{formatPercent(entry.distance_fit)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}

          {auditRows.length > 0 && (
            <details className="detail-card">
              <summary>
                Routes tested <span>{auditRows.length}</span>
              </summary>
              <div className="table-wrap">
                <table>
                  <caption className="sr-only">
                    Scores for every route that was tested
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Route</th>
                      <th scope="col">Shape</th>
                      <th scope="col">Result</th>
                      <th scope="col">Score</th>
                      <th scope="col">Likeness</th>
                      <th scope="col">Distance</th>
                      <th scope="col">Checks to review</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditRows.map((entry) => (
                      <tr key={entry.id}>
                        <td data-label="Route">{entry.id}</td>
                        <td data-label="Shape">{normaliseLabel(entry.shape_name)}</td>
                        <td data-label="Result">
                          {entry.decision === "verified"
                            ? "Ready"
                            : entry.decision === "review"
                              ? "Needs a look"
                              : "Different drawing"}
                        </td>
                        <td data-label="Score">{formatPercent(entry.score)}</td>
                        <td data-label="Likeness">{formatPercent(entry.shape_fidelity)}</td>
                        <td data-label="Distance">{formatMetric(entry.distance_km)} km</td>
                        <td data-label="Checks to review">
                          {(entry.failed_gates ?? []).length > 0
                            ? entry.failed_gates.map(normaliseLabel).join(", ")
                            : "None"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </div>
      )}
    </section>
  );
}

export default function App() {
  const [prompt, setPrompt] = useState(QUICK_IDEAS[0].prompt);
  const [promptError, setPromptError] = useState("");
  const [promptValidationAttempt, setPromptValidationAttempt] = useState(0);
  const [ideaQuery, setIdeaQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [suggestCity, setSuggestCity] = useState(SUGGEST_CITIES[0]);
  const [suggestSport, setSuggestSport] = useState("run");
  const [suggestDistance, setSuggestDistance] = useState("10");
  const [suggestErrors, setSuggestErrors] = useState({});
  const [suggestNotice, setSuggestNotice] = useState("");
  const [downloadNotice, setDownloadNotice] = useState("");
  const [galleryRefreshKey, setGalleryRefreshKey] = useState(0);
  const [lastPublishedGalleryAsset, setLastPublishedGalleryAsset] = useState(null);
  const requestRef = useRef(null);
  const resultRef = useRef(null);
  const errorRef = useRef(null);
  const promptRef = useRef(null);
  const suggestCityRef = useRef(null);
  const suggestActivityRef = useRef(null);
  const suggestDistanceRef = useRef(null);

  useEffect(() => {
    if (result) resultRef.current?.focus();
  }, [result]);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  useEffect(() => {
    if (promptValidationAttempt > 0 && promptError) promptRef.current?.focus();
  }, [promptError, promptValidationAttempt]);

  useEffect(() => () => requestRef.current?.abort(), []);

  const activeIdea = useMemo(
    () => QUICK_IDEAS.find((idea) => idea.prompt === prompt)?.label,
    [prompt],
  );
  const filteredIdeas = useMemo(() => {
    const query = ideaQuery.trim().toLocaleLowerCase("en");
    if (!query) return QUICK_IDEAS;
    return QUICK_IDEAS.filter((idea) =>
      `${idea.label} ${idea.category}`.toLocaleLowerCase("en").includes(query),
    );
  }, [ideaQuery]);

  const generate = useCallback(async (nextPrompt) => {
    const cleanPrompt = normaliseRoutePrompt(nextPrompt);
    if (!cleanPrompt) return;

    const controller = new AbortController();
    requestRef.current?.abort();
    requestRef.current = controller;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await generateRoute(cleanPrompt, { signal: controller.signal });
      setResult(response);
    } catch (generationError) {
      if (generationError.name !== "AbortError") {
        setError(
          generationError.message ||
            "We couldn’t make that route. Check the idea and try again.",
        );
      }
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setLoading(false);
      }
    }
  }, []);

  function handleSubmit(event) {
    event.preventDefault();
    if (loading) return;

    const validation = validateRoutePrompt(prompt);
    setPromptError(validation.error);
    if (validation.error) {
      setPromptValidationAttempt((current) => current + 1);
      return;
    }

    setPrompt(validation.value);
    generate(validation.value);
  }

  function handleSuggest(event) {
    event.preventDefault();
    if (loading) return;

    const { errors, numericDistance } = validateSuggestion({
      city: suggestCity,
      sport: suggestSport,
      distance: suggestDistance,
    });
    setSuggestErrors(errors);
    if (Object.keys(errors).length > 0) {
      if (errors.city) suggestCityRef.current?.focus();
      else if (errors.sport) suggestActivityRef.current?.focus();
      else suggestDistanceRef.current?.focus();
      return;
    }

    const suggestionPrompt = `suggest a ${suggestSport} route in ${suggestCity}, about ${numericDistance} km`;
    setPrompt(suggestionPrompt);
    setPromptError("");
    generate(suggestionPrompt);
  }

  function cancelGeneration() {
    requestRef.current?.abort();
  }

  function handleDownload(extension, content) {
    const routeName = safeFilePart(
      `${result?.shape?.name ?? "gps-art"}-${result?.intent?.city ?? "route"}`,
    );
    const contentType = extension === "gpx" ? "application/gpx+xml" : "application/vnd.garmin.tcx+xml";
    saveFile(`${routeName}.${extension}`, content, contentType);
    setDownloadNotice(`${extension.toUpperCase()} download started.`);
  }

  const { minimum: minimumDistance, maximum: maximumDistance, activity: activityLabel } =
    distanceLimits(suggestSport);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#route-designer">
        Skip to route planner
      </a>

      <header className="site-header">
        <a className="brand" href="/" aria-label="GPS Art Wizard home">
          <span className="brand-mark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span>
            GPS Art <strong>Wizard</strong>
          </span>
        </a>
        <nav aria-label="Primary navigation">
          <a href="#route-designer">Planner</a>
          <a href="#gallery">Gallery</a>
        </nav>
      </header>

      <main>
        <section
          className="workspace generator-stage"
          id="route-designer"
          aria-labelledby="designer-title"
        >
          <div className="planner-intro">
            <h1 id="designer-title">Plan a GPS art route</h1>
            <p className="planner-intro-copy">
              Enter a drawing, city, activity, and distance. The planner finds nearby street routes
              and creates GPX and TCX files.
            </p>
            <p className="planner-safety-note">
              Check access, crossings, traffic, surfaces, and current conditions before using a
              route.
            </p>
          </div>

          <div className="designer-card">
            <div className="card-heading">
              <div>
                <h2>Route idea</h2>
                <p>Describe a route or choose a shape.</p>
              </div>
            </div>

            <form onSubmit={handleSubmit} noValidate>
              <label className="field-label" htmlFor="route-prompt">
                Drawing and location
              </label>
              <div className="textarea-wrap">
                <textarea
                  id="route-prompt"
                  ref={promptRef}
                  value={prompt}
                  onChange={(event) => {
                    const nextPrompt = event.target.value;
                    setPrompt(nextPrompt);
                    if (promptError) setPromptError(validateRoutePrompt(nextPrompt).error);
                  }}
                  onBlur={(event) => {
                    const nextControl = event.relatedTarget;
                    if (
                      nextControl?.type === "submit" &&
                      nextControl.form === event.currentTarget.form
                    ) {
                      return;
                    }
                    setPromptError(validateRoutePrompt(prompt).error);
                  }}
                  onKeyDown={(event) => {
                    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                  rows={3}
                  maxLength={PROMPT_LIMIT}
                  placeholder="Heart, Budapest, running, 8 km"
                  aria-describedby="prompt-help prompt-count"
                  aria-invalid={Boolean(promptError)}
                  aria-errormessage={promptError ? "prompt-error" : undefined}
                  disabled={loading}
                  autoFocus
                  required
                />
                <span id="prompt-count" className="character-count">
                  {prompt.length}/{PROMPT_LIMIT}
                </span>
              </div>
              <p
                id="prompt-help"
                className={`field-help${promptError ? " field-help--with-error" : ""}`}
              >
                Example: heart, Budapest, running, 8 km.
              </p>
              {promptError && (
                <p id="prompt-error" className="field-error" role="alert">
                  <span aria-hidden="true">!</span>
                  {promptError}
                </p>
              )}

              <fieldset className="idea-picker">
                <legend>Common shapes</legend>
                <div className="idea-list">
                  {FEATURED_IDEAS.map((idea) => (
                    <button
                      type="button"
                      key={idea.label}
                      className="idea-chip"
                      aria-pressed={activeIdea === idea.label}
                      onClick={() => {
                        setPrompt(idea.prompt);
                        setPromptError("");
                      }}
                      disabled={loading}
                    >
                      <span aria-hidden="true">{idea.glyph}</span>
                      {idea.label}
                    </button>
                  ))}
                </div>
              </fieldset>

              <details className="idea-catalog">
                <summary>
                  <span>
                    <strong>More shapes, letters, and numbers</strong>
                    <small>{QUICK_IDEAS.length} options. Detailed shapes work best on longer routes.</small>
                  </span>
                  <b aria-hidden="true">+</b>
                </summary>
                <div className="idea-groups">
                  <div className="idea-filter">
                    <label htmlFor="idea-filter">Filter options</label>
                    <input
                      id="idea-filter"
                      type="search"
                      value={ideaQuery}
                      onChange={(event) => setIdeaQuery(event.target.value)}
                      placeholder="Search by name or category"
                    />
                    <span aria-live="polite">
                      {filteredIdeas.length} option{filteredIdeas.length === 1 ? "" : "s"}
                    </span>
                  </div>
                  {IDEA_CATEGORIES.map((category) => {
                    const categoryIdeas = filteredIdeas.filter((idea) => idea.category === category);
                    if (categoryIdeas.length === 0) return null;
                    return (
                      <section className="idea-group" key={category} aria-label={`${category} ideas`}>
                        <h3>{category}</h3>
                        <div className="idea-list">
                          {categoryIdeas.map((idea) => (
                            <button
                              type="button"
                              key={idea.label}
                              className="idea-chip"
                              aria-pressed={activeIdea === idea.label}
                              onClick={() => {
                                setPrompt(idea.prompt);
                                setPromptError("");
                              }}
                              disabled={loading}
                            >
                              <span aria-hidden="true">{idea.glyph}</span>
                              {idea.label}
                            </button>
                          ))}
                        </div>
                      </section>
                    );
                  })}
                  {filteredIdeas.length === 0 && (
                    <p className="idea-empty" role="status">
                      No matching options. Try a broader name or category.
                    </p>
                  )}
                </div>
              </details>

              <button
                type="submit"
                className="button button--primary generate-button"
                disabled={loading}
              >
                <span>{loading ? "Finding routes…" : "Find routes"}</span>
              </button>
            </form>

            <details className="suggest-panel">
              <summary>
                Choose city, activity, and distance
                <span aria-hidden="true">+</span>
              </summary>
              <form className="suggest-form" onSubmit={handleSuggest} noValidate>
                <div className="suggest-fields">
                  <div className="field">
                    <label htmlFor="suggest-city">City</label>
                    <select
                      id="suggest-city"
                      ref={suggestCityRef}
                      value={suggestCity}
                      onChange={(event) => {
                        const nextCity = event.target.value;
                        setSuggestCity(nextCity);
                        if (suggestErrors.city) {
                          setSuggestErrors((current) => ({
                            ...current,
                            city: SUGGEST_CITIES.includes(nextCity)
                              ? ""
                              : "Choose a city from the list.",
                          }));
                        }
                      }}
                      aria-invalid={Boolean(suggestErrors.city)}
                      aria-errormessage={suggestErrors.city ? "suggest-city-error" : undefined}
                      aria-describedby="suggest-city-help"
                      disabled={loading}
                      required
                    >
                      {SUGGEST_CITY_GROUPS.map((group) => (
                        <optgroup key={group.label} label={group.label}>
                          {group.cities.map((cityName) => (
                            <option key={cityName} value={cityName}>
                              {cityName}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                    <p id="suggest-city-help" className="field-help">
                      All 45 Lake Balaton shore municipalities are covered; Siófok is listed under Hungary.
                    </p>
                    {suggestErrors.city && (
                      <p id="suggest-city-error" className="field-error" role="alert">
                        <span aria-hidden="true">!</span>
                        {suggestErrors.city}
                      </p>
                    )}
                  </div>
                  <fieldset
                    className="field field--activity"
                    aria-invalid={Boolean(suggestErrors.sport)}
                    aria-describedby={suggestErrors.sport ? "suggest-sport-error" : undefined}
                  >
                    <legend>Activity</legend>
                    <div className="activity-options">
                      {[
                        ["run", "Running"],
                        ["bike", "Cycling"],
                      ].map(([value, label]) => (
                        <label className="activity-option" key={value}>
                          <input
                            ref={value === "run" ? suggestActivityRef : undefined}
                            type="radio"
                            name="suggest-activity"
                            value={value}
                            checked={suggestSport === value}
                            onChange={() => {
                              setSuggestSport(value);
                              setSuggestErrors((current) => ({
                                ...current,
                                sport: "",
                                distance: "",
                              }));
                              if (value === "bike" && Number(suggestDistance) < 10) {
                                setSuggestDistance("10");
                                setSuggestNotice(
                                  "Cycling routes start at 10 km. Distance changed to 10 km.",
                                );
                              } else {
                                setSuggestNotice("");
                              }
                            }}
                            disabled={loading}
                            required
                          />
                          <span>{label}</span>
                        </label>
                      ))}
                    </div>
                    {suggestErrors.sport && (
                      <p id="suggest-sport-error" className="field-error" role="alert">
                        <span aria-hidden="true">!</span>
                        {suggestErrors.sport}
                      </p>
                    )}
                  </fieldset>
                  <div className="field field--distance">
                    <label htmlFor="suggest-distance">Distance</label>
                    <div className="input-suffix">
                      <input
                        id="suggest-distance"
                        ref={suggestDistanceRef}
                        type="number"
                        inputMode="decimal"
                        min={minimumDistance}
                        max={maximumDistance}
                        step="1"
                        value={suggestDistance}
                        onChange={(event) => {
                          const nextDistance = event.target.value;
                          setSuggestDistance(nextDistance);
                          setSuggestNotice("");
                          if (suggestErrors.distance) {
                            const nextValidation = validateSuggestion({
                              city: suggestCity,
                              sport: suggestSport,
                              distance: nextDistance,
                            });
                            setSuggestErrors((current) => ({
                              ...current,
                              distance: nextValidation.errors.distance ?? "",
                            }));
                          }
                        }}
                        onBlur={() => {
                          const nextValidation = validateSuggestion({
                            city: suggestCity,
                            sport: suggestSport,
                            distance: suggestDistance,
                          });
                          setSuggestErrors((current) => ({
                            ...current,
                            distance: nextValidation.errors.distance ?? "",
                          }));
                        }}
                        aria-describedby="suggest-distance-help"
                        aria-invalid={Boolean(suggestErrors.distance)}
                        aria-errormessage={
                          suggestErrors.distance ? "suggest-distance-error" : undefined
                        }
                        disabled={loading}
                        required
                      />
                      <span>km</span>
                    </div>
                    <p id="suggest-distance-help" className="field-hint">
                      {minimumDistance}–{maximumDistance} km for {activityLabel}.
                    </p>
                    {suggestErrors.distance && (
                      <p id="suggest-distance-error" className="field-error" role="alert">
                        <span aria-hidden="true">!</span>
                        {suggestErrors.distance}
                      </p>
                    )}
                  </div>
                </div>
                <p className="suggest-method">
                  We compare up to three shapes suited to these streets and this distance.
                </p>
                <div className="suggest-actions">
                  <p className="suggest-notice" aria-live="polite">
                    {suggestNotice}
                  </p>
                  <button
                    type="submit"
                    className="button button--secondary suggest-submit"
                    disabled={loading}
                  >
                    Find a route
                  </button>
                </div>
              </form>
            </details>
          </div>
        </section>

        {loading && <LoadingState onCancel={cancelGeneration} />}

        {error && (
          <section className="error-card" role="alert" tabIndex="-1" ref={errorRef}>
            <div className="error-symbol" aria-hidden="true">
              !
            </div>
            <div>
              <h2>Route not found</h2>
              <p>{error}</p>
              <button
                type="button"
                className="button button--secondary"
                onClick={() => generate(prompt)}
              >
                Try again
              </button>
            </div>
          </section>
        )}

        {result && (
          <ResultPanel
            result={result}
            onDownload={handleDownload}
            onGalleryPublished={(asset) => {
              setLastPublishedGalleryAsset(asset);
              setGalleryRefreshKey((current) => current + 1);
            }}
            focusRef={resultRef}
          />
        )}
        <GallerySection
          refreshKey={galleryRefreshKey}
          publishedAsset={lastPublishedGalleryAsset}
        />
      </main>

      <footer>
        <p>GPS Art Wizard</p>
      </footer>
      <div className="sr-only" aria-live="polite">
        {downloadNotice}
      </div>
    </div>
  );
}

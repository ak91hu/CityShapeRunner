import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  analyseInkproof,
  editRoute,
  generate as generateRoute,
  createMuralPlan,
  listGallery,
  publishGalleryImage,
  recordRouteAcceptance,
  repairRecognition,
  requestTimedReadiness,
  removeGalleryImage,
} from "./api.js";

const RouteMap = lazy(() => import("./RouteMap.jsx"));
const GALLERY_REMOVAL_STORAGE_KEY = "gps-art-gallery-removal-tokens-v1";

const CORE_IDEAS = [
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
  { glyph: "🐞", label: "Bug", category: "Animals", prompt: "a bug run in Tatabánya, about 8 km" },
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

// Authored as routable, single-outline silhouettes in the backend catalogue.
// The varied example cities also make the expanded European coverage easy to
// discover without turning the main six quick choices into a wall of buttons.
const ADDITIONAL_SHAPE_IDEAS = [
  { glyph: "🌰", label: "Acorn", category: "Nature", prompt: "an acorn run in Uppsala, about 10 km" },
  { glyph: "🐜", label: "Ant", category: "Animals", prompt: "an ant run in Poznań, about 12 km" },
  { glyph: "🪓", label: "Axe", category: "Objects", prompt: "an axe bike route in Glasgow, about 20 km" },
  { glyph: "🎈", label: "Balloon", category: "Objects", prompt: "a balloon run in Lyon, about 10 km" },
  { glyph: "🍌", label: "Banana", category: "Nature", prompt: "a banana run in Valencia, about 10 km" },
  { glyph: "🍾", label: "Bottle", category: "Objects", prompt: "a bottle run in Brno, about 12 km" },
  { glyph: "🎀", label: "Bow tie", category: "Objects", prompt: "a bow tie run in Turin, about 10 km" },
  { glyph: "🥦", label: "Broccoli", category: "Nature", prompt: "broccoli GPS art in Leipzig, running about 12 km" },
  { glyph: "🚌", label: "Bus", category: "Objects", prompt: "a bus bike route in Birmingham, about 20 km" },
  { glyph: "📷", label: "Camera", category: "Objects", prompt: "a camera bike route in Manchester, about 22 km" },
  { glyph: "🕯️", label: "Candle", category: "Objects", prompt: "a candle run in Graz, about 12 km" },
  { glyph: "🍬", label: "Candy", category: "Objects", prompt: "a wrapped candy run in Malmö, about 12 km" },
  { glyph: "♟️", label: "Chess pawn", category: "Symbols", prompt: "a chess pawn run in Prague, about 12 km" },
  { glyph: "🧭", label: "Compass", category: "Symbols", prompt: "a compass bike route in Rotterdam, about 22 km" },
  { glyph: "🦀", label: "Crab", category: "Animals", prompt: "a crab run in A Coruña, about 12 km" },
  { glyph: "🦕", label: "Dinosaur", category: "Animals", prompt: "a dinosaur bike route in Cologne, about 24 km" },
  { glyph: "🥁", label: "Drum", category: "Objects", prompt: "a drum run in Valladolid, about 10 km" },
  { glyph: "🪶", label: "Feather", category: "Nature", prompt: "a feather run in Nantes, about 12 km" },
  { glyph: "🐸", label: "Frog", category: "Animals", prompt: "a frog run in Tampere, about 12 km" },
  { glyph: "👻", label: "Ghost", category: "Symbols", prompt: "a ghost run in Edinburgh, about 12 km" },
  { glyph: "👓", label: "Glasses", category: "Objects", prompt: "glasses GPS art in Frankfurt, running about 12 km" },
  { glyph: "🔨", label: "Hammer", category: "Objects", prompt: "a hammer bike route in Stuttgart, about 20 km" },
  { glyph: "🦔", label: "Hedgehog", category: "Animals", prompt: "a hedgehog run in Warsaw, about 14 km" },
  { glyph: "⛑️", label: "Helmet", category: "Objects", prompt: "a helmet run in Hanover, about 12 km" },
  { glyph: "🍦", label: "Ice cream", category: "Nature", prompt: "an ice cream run in Bologna, about 12 km" },
  { glyph: "🪁", label: "Kite", category: "Objects", prompt: "a kite run in Toulouse, about 12 km" },
  { glyph: "🐨", label: "Koala", category: "Animals", prompt: "a koala run in Belfast, about 14 km" },
  { glyph: "🪜", label: "Ladder", category: "Objects", prompt: "a ladder bike route in Łódź, about 20 km" },
  { glyph: "🔦", label: "Lighthouse", category: "Objects", prompt: "a lighthouse run in Porto, about 14 km" },
  { glyph: "🔒", label: "Lock", category: "Symbols", prompt: "a lock run in Düsseldorf, about 12 km" },
  { glyph: "🏅", label: "Medal", category: "Symbols", prompt: "a medal run in Seville, about 12 km" },
  { glyph: "🎤", label: "Microphone", category: "Objects", prompt: "a microphone bike route in Liverpool, about 22 km" },
  { glyph: "🐙", label: "Octopus", category: "Animals", prompt: "an octopus bike route in Thessaloniki, about 24 km" },
  { glyph: "🛩️", label: "Paper plane", category: "Objects", prompt: "a paper plane run in Eindhoven, about 12 km" },
  { glyph: "🐾", label: "Paw print", category: "Animals", prompt: "a paw print run in Cork, about 12 km" },
  { glyph: "🍕", label: "Pizza slice", category: "Objects", prompt: "a pizza slice run in Naples, about 14 km" },
  { glyph: "🥨", label: "Pretzel", category: "Objects", prompt: "a pretzel bike route in Munich, about 20 km" },
  { glyph: "🤖", label: "Robot", category: "Objects", prompt: "a robot run in Budapest, about 8 km" },
  { glyph: "✂️", label: "Scissors", category: "Objects", prompt: "scissors GPS art in Dresden, cycling about 22 km" },
  { glyph: "🐴", label: "Seahorse", category: "Animals", prompt: "a seahorse bike route in Split, about 22 km" },
  { glyph: "🛹", label: "Skateboard", category: "Objects", prompt: "a skateboard run in Malmö, about 14 km" },
  { glyph: "🐍", label: "Snake", category: "Animals", prompt: "a snake bike route in Sofia, about 22 km" },
  { glyph: "🕷️", label: "Spider", category: "Animals", prompt: "a spider bike route in Wrocław, about 24 km" },
  { glyph: "🦑", label: "Squid", category: "Animals", prompt: "a squid run in Gdańsk, about 14 km" },
  { glyph: "🩺", label: "Stethoscope", category: "Objects", prompt: "a stethoscope bike route in Geneva, about 24 km" },
  { glyph: "🚢", label: "Submarine", category: "Objects", prompt: "a submarine bike route in Helsinki, about 24 km" },
  { glyph: "🦢", label: "Swan", category: "Animals", prompt: "a swan run in Zurich, about 14 km" },
  { glyph: "⚔️", label: "Sword", category: "Objects", prompt: "a sword bike route in Belgrade, about 22 km" },
  { glyph: "🔭", label: "Telescope", category: "Objects", prompt: "a telescope bike route in Oslo, about 22 km" },
  { glyph: "⛺", label: "Tent", category: "Objects", prompt: "a tent run in Grenoble, about 12 km" },
  { glyph: "🚜", label: "Tractor", category: "Objects", prompt: "a tractor bike route in Lublin, about 22 km" },
  { glyph: "🚆", label: "Train", category: "Objects", prompt: "a train bike route in Frankfurt, about 22 km" },
  { glyph: "🌋", label: "Volcano", category: "Nature", prompt: "a volcano run in Palermo, about 14 km" },
  { glyph: "🍉", label: "Watermelon slice", category: "Nature", prompt: "a watermelon slice run in Palermo, about 14 km" },
  { glyph: "🌬️", label: "Windmill", category: "Objects", prompt: "a windmill bike route in Rotterdam, about 22 km" },
];

const HUNGARIAN_SHAPE_IDEAS = [
  { glyph: "🌶️", label: "Paprika", category: "Hungarian ideas", prompt: "a paprika run in Szeged, about 12 km" },
  { glyph: "🧊", label: "Puzzle cube", category: "Hungarian ideas", prompt: "a Rubik's cube bike route in Budapest, about 24 km" },
  { glyph: "🥸", label: "Moustache", category: "Hungarian ideas", prompt: "a moustache run in Kecskemét, about 18 km" },
  { glyph: "🍇", label: "Grape cluster", category: "Hungarian ideas", prompt: "a grape cluster bike route in Eger, about 24 km" },
  { glyph: "🍷", label: "Wine glass", category: "Hungarian ideas", prompt: "a wine glass run in Sopron, about 18 km" },
  { glyph: "🥘", label: "Cauldron", category: "Hungarian ideas", prompt: "a cauldron run in Békéscsaba, about 18 km" },
  { glyph: "🧲", label: "Horseshoe", category: "Hungarian ideas", prompt: "a horseshoe run in Debrecen, about 16 km" },
  { glyph: "🌾", label: "Wheat", category: "Hungarian ideas", prompt: "a wheat bike route in Békéscsaba, about 28 km" },
  { glyph: "🌉", label: "Suspension bridge", category: "Hungarian ideas", prompt: "a suspension bridge bike route in Budapest, about 30 km" },
  { glyph: "🗼", label: "Water tower", category: "Hungarian ideas", prompt: "a water tower bike route in Szeged, about 22 km" },
  { glyph: "🐂", label: "Grey cattle", category: "Hungarian ideas", prompt: "Hungarian grey cattle GPS art in Debrecen, cycling about 28 km" },
  { glyph: "🦌", label: "Stag", category: "Hungarian ideas", prompt: "a stag bike route in Gyöngyös, about 30 km" },
  { glyph: "🔴", label: "Pomegranate", category: "Hungarian ideas", prompt: "a pomegranate run in Pécs, about 12 km" },
  { glyph: "🧁", label: "Chimney cake", category: "Hungarian ideas", prompt: "a chimney cake bike route in Budapest, about 24 km" },
  { glyph: "♨️", label: "Thermal bath", category: "Hungarian ideas", prompt: "a thermal bath bike route in Hajdúszoboszló, about 28 km" },
  { glyph: "⛩️", label: "Folk gate", category: "Hungarian ideas", prompt: "a folk gate bike route in Szentendre, about 30 km" },
];

const QUICK_IDEAS = [...CORE_IDEAS, ...ADDITIONAL_SHAPE_IDEAS, ...HUNGARIAN_SHAPE_IDEAS];

const IDEA_CATEGORIES = [
  "Hungarian ideas",
  "Simple shapes",
  "Nature",
  "Animals",
  "Objects",
  "Symbols",
  "Letters, numbers & text",
];
const FEATURED_IDEAS = QUICK_IDEAS.filter((idea) => idea.featured).slice(0, 6);
const DISTINCT_IDEA_GLYPHS = Object.freeze({
  Bat: "🦇",
  Bear: "🐻",
  Bird: "🐦",
  Cat: "🐈",
  Dog: "🐕",
  Dragon: "🐉",
  Duck: "🦆",
  Owl: "🦉",
  Penguin: "🐧",
  Rabbit: "🐇",
  Turtle: "🐢",
  Whale: "🐋",
});

function ideaGlyph(idea) {
  return DISTINCT_IDEA_GLYPHS[idea.label] ?? idea.glyph;
}

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
  "Birmingham",
  "Manchester",
  "Liverpool",
  "Leeds",
  "Glasgow",
  "Edinburgh",
  "Bristol",
  "Belfast",
  "Cork",
  "Marseille",
  "Lyon",
  "Toulouse",
  "Nice",
  "Nantes",
  "Strasbourg",
  "Bordeaux",
  "Lille",
  "Montpellier",
  "Grenoble",
  "Hamburg",
  "Cologne",
  "Frankfurt",
  "Stuttgart",
  "Düsseldorf",
  "Leipzig",
  "Dresden",
  "Nuremberg",
  "Hanover",
  "Bremen",
  "Valencia",
  "Seville",
  "Zaragoza",
  "Málaga",
  "Bilbao",
  "Alicante",
  "Granada",
  "Valladolid",
  "Vigo",
  "A Coruña",
  "Naples",
  "Turin",
  "Bologna",
  "Florence",
  "Genoa",
  "Palermo",
  "Bari",
  "Verona",
  "Padua",
  "Trieste",
  "Łódź",
  "Wrocław",
  "Poznań",
  "Gdańsk",
  "Szczecin",
  "Lublin",
  "Katowice",
  "Bydgoszcz",
  "Gothenburg",
  "Malmö",
  "Uppsala",
  "Bergen",
  "Trondheim",
  "Stavanger",
  "Aarhus",
  "Odense",
  "Tampere",
  "Turku",
  "Oulu",
  "Rotterdam",
  "The Hague",
  "Utrecht",
  "Eindhoven",
  "Antwerp",
  "Ghent",
  "Liège",
  "Luxembourg",
  "Salzburg",
  "Graz",
  "Innsbruck",
  "Linz",
  "Geneva",
  "Basel",
  "Bern",
  "Lausanne",
  "Brno",
  "Ostrava",
  "Košice",
  "Cluj-Napoca",
  "Timișoara",
  "Iași",
  "Varna",
  "Plovdiv",
  "Thessaloniki",
  "Patras",
  "Split",
  "Rijeka",
  "Sarajevo",
  "Belgrade",
  "Novi Sad",
  "Skopje",
  "Tirana",
  "Podgorica",
  "Pristina",
  "Vilnius",
  "Kaunas",
  "Tartu",
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

function validateImageReferenceUrl(value) {
  const cleaned = value.trim();
  if (!cleaned) return { value: "", error: "Enter a direct image link." };
  try {
    const parsed = new URL(cleaned);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      return { value: cleaned, error: "Use a public HTTP or HTTPS image link." };
    }
    return { value: parsed.href, error: "" };
  } catch {
    return { value: cleaned, error: "Enter a complete image URL." };
  }
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
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "n/a";
}

function formatPercent(value) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${Math.round(value * 100)}%`
    : "n/a";
}

function formatSigned(value, digits = 2, suffix = "") {
  if (typeof value !== "number" || !Number.isFinite(value)) return "n/a";
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
  if (!value) return "n/a";
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

function RouteReadinessCard({
  readiness,
  roadRouted,
  activeConcernCode = null,
  onConcernSelect,
}) {
  const data = readiness && typeof readiness === "object" ? readiness : {};
  const concerns = Array.isArray(data.concerns) ? data.concerns : [];
  const surfaces = Array.isArray(data.surfaces) ? data.surfaces.slice(0, 6) : [];
  const status = ["ready", "review"].includes(data.status)
    ? data.status
    : "unavailable";
  const statusCopy = {
    ready: "Looks clear",
    review: "Check the route",
    unavailable: "Limited data",
  }[status];
  const grade = Number.isFinite(data.max_grade_percent)
    ? `${data.max_grade_percent.toFixed(1)}%${data.max_grade_is_lower_bound ? "+" : ""}`
    : "n/a";
  const elevationGain = Number.isFinite(data.elevation_gain_m)
    ? `${Math.round(data.elevation_gain_m)} m`
    : "n/a";
  const surfaceKnown = Number.isFinite(data.surface_known_share)
    ? formatPercent(data.surface_known_share)
    : "n/a";
  const highlightedConcernCount = concerns.reduce(
    (count, concern) => count + (concern.segments_preview?.length ?? 0),
    0,
  );

  return (
    <section
      className={`readiness-card readiness-card--${status}`}
      aria-labelledby="readiness-title"
    >
      <div className="readiness-heading">
        <div>
          <span className="eyebrow">Before you go</span>
          <h3 id="readiness-title">Route readiness</h3>
        </div>
        <span className={`readiness-status readiness-status--${status}`}>
          {statusCopy}
        </span>
      </div>

      <p className="readiness-summary">
        {!roadRouted || status === "unavailable"
          ? "A street-matched route is needed for elevation, surface, and segment checks."
          : status === "review"
            ? highlightedConcernCount > 0
              ? "Review the highlighted sections before heading out."
              : "Some route details need a closer check before heading out."
            : "The available map data has no obvious route-readiness flags."}
      </p>

      <dl className="readiness-metrics">
        <div>
          <dt>Elevation gain</dt>
          <dd>{elevationGain}</dd>
        </div>
        <div>
          <dt>Steepest climb</dt>
          <dd>{grade}</dd>
        </div>
        <div>
          <dt>Surface known</dt>
          <dd>{surfaceKnown}</dd>
        </div>
      </dl>

      {surfaces.length > 0 && (
        <div className="surface-breakdown">
          <div className="readiness-subheading">
            <strong>Surface mix</strong>
            {Number.isFinite(data.unpaved_share) && (
              <span>{formatPercent(data.unpaved_share)} unpaved</span>
            )}
          </div>
          <div className="surface-bar" aria-label="Route surface composition">
            {surfaces.map((surface) => (
              <span
                key={surface.code}
                className={`surface-bar-part surface-bar-part--${surface.category}`}
                style={{ width: `${Math.max(1, Math.round((surface.share ?? 0) * 100))}%` }}
                title={`${surface.label}: ${formatPercent(surface.share)}`}
              />
            ))}
          </div>
          <ul className="surface-legend">
            {surfaces.map((surface) => (
              <li key={surface.code}>
                <span
                  className={`surface-key surface-key--${surface.category}`}
                  aria-hidden="true"
                />
                <span>{surface.label}</span>
                <strong>{formatPercent(surface.share)}</strong>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="readiness-concerns">
        <div className="readiness-subheading">
          <strong>Sections to check</strong>
          {activeConcernCode ? (
            <button
              type="button"
              className="concern-reset"
              onClick={() => onConcernSelect?.(null)}
            >
              Show full route
            </button>
          ) : (
            <span>
              {concerns.length > 0
                ? `${concerns.length} item${concerns.length === 1 ? "" : "s"}`
                : "No items"}
            </span>
          )}
        </div>
        {concerns.length > 0 ? (
          <ul>
            {concerns.map((concern) => (
              <li key={concern.code} className={`concern--${concern.severity}`}>
                <button
                  type="button"
                  className="concern-button"
                  aria-pressed={activeConcernCode === concern.code}
                  onClick={() => onConcernSelect?.(
                    activeConcernCode === concern.code ? null : concern.code,
                  )}
                >
                  <span className="concern-icon" aria-hidden="true">
                    {concern.severity === "warning" ? "!" : "i"}
                  </span>
                  <span>
                    <strong>{concern.label}</strong>
                    <small>{concern.detail}</small>
                  </span>
                  <span className="concern-distance">
                    {concern.distance_m >= 1_000
                      ? `${formatMetric(concern.distance_m / 1_000, 1)} km`
                      : `${Math.round(concern.distance_m)} m`}
                    <small>View on map</small>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="readiness-empty">
            {status === "unavailable"
              ? "No segment data is available for this preview."
              : "No sections were flagged in the available map data."}
          </p>
        )}
      </div>

      <p className="readiness-note">
        Based on routing and OpenStreetMap data. Check current closures, access rules, traffic,
        and weather separately.
      </p>
    </section>
  );
}

function StreetCanvasCard({ candidates = [] }) {
  const best = candidates[0];
  if (!best) return null;
  return (
    <section className="street-canvas-card" aria-labelledby="street-canvas-title">
      <div className="readiness-heading">
        <div>
          <span className="eyebrow">Street Canvas</span>
          <h3 id="street-canvas-title">Best nearby areas</h3>
        </div>
        <span className="readiness-status readiness-status--ready">
          {formatPercent(best.readability_score)} fit
        </span>
      </div>
      <p>
        These are the strongest nearby street-network matches before full route routing.
      </p>
      <ol className="street-canvas-list">
        {candidates.slice(0, 4).map((candidate) => (
          <li key={`${candidate.rank}-${candidate.rotation_deg}-${candidate.scale_m}`}>
            <strong>Area {candidate.rank}</strong>
            <span>{formatPercent(candidate.readability_score)} readable</span>
            <small>
              {formatPercent(candidate.snap_coverage)} street support, {formatMetric(candidate.snap_distance_m, 0)} m average snap
            </small>
          </li>
        ))}
      </ol>
    </section>
  );
}

function TimedReadinessCard({ points }) {
  const [departure, setDeparture] = useState("");
  const [briefing, setBriefing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const requestSequence = useRef(0);
  const check = async () => {
    if (!departure || !Array.isArray(points) || points.length < 1) return;
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    setBusy(true);
    setError("");
    try {
      const response = await requestTimedReadiness({
        latitude: points[0][0], longitude: points[0][1], departure_at: new Date(departure).toISOString(),
      });
      if (requestSequence.current === requestId) setBriefing(response);
    } catch (requestError) {
      if (requestSequence.current === requestId) {
        setError(requestError.message || "We couldn’t check the time-based route context.");
      }
    } finally {
      if (requestSequence.current === requestId) setBusy(false);
    }
  };
  const forecastTime = briefing?.weather?.forecast_at
    ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" })
      .format(new Date(briefing.weather.forecast_at))
    : null;
  return (
    <section className="timed-readiness-card" aria-labelledby="timed-readiness-title">
      <div>
        <span className="eyebrow">When you go</span>
        <h3 id="timed-readiness-title">Time-aware check</h3>
      </div>
      <div className="timed-readiness-controls">
        <label>
          Departure
          <input
            type="datetime-local"
            value={departure}
            onChange={(event) => {
              requestSequence.current += 1;
              setDeparture(event.target.value);
              setBriefing(null);
              setError("");
              setBusy(false);
            }}
          />
        </label>
        <button type="button" className="button button--secondary" onClick={check} disabled={!departure || busy}>
          {busy ? "Checking..." : "Check conditions"}
        </button>
      </div>
      {briefing && (
        <div className="timed-readiness-result" role="status">
          <strong>{briefing.daylight === "daylight" ? "Daylight expected." : "After dark at this time."}</strong>
          {briefing.weather ? (
            <>
              <span>Forecast for {forecastTime}.</span>
              <span>
                {briefing.weather.temperature_c == null ? "Temperature unavailable" : `${Math.round(briefing.weather.temperature_c)}°C`}
                {briefing.weather.wind_kph != null && ` · ${Math.round(briefing.weather.wind_kph)} km/h wind`}
                {briefing.weather.precipitation_mm != null && ` · ${briefing.weather.precipitation_mm} mm precipitation`}.
              </span>
            </>
          ) : (
            <span>{briefing.weather_message || "Hourly weather is unavailable for this departure."}</span>
          )}
        </div>
      )}
      {error && <p className="editor-error" role="alert">{error}</p>}
      <small>Weather is matched to the selected hour when it is inside the forecast window. Closures and access rules still need a local check.</small>
    </section>
  );
}

function CommunityMuralCard({ activeRoute, shapeName, city, sport }) {
  const [participants, setParticipants] = useState(4);
  const [plan, setPlan] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const create = async () => {
    setBusy(true); setError("");
    try {
      setPlan(await createMuralPlan({
        points: activeRoute.points_preview,
        participants: Number(participants),
        name: `${shapeName} mural in ${city}`,
        sport: sport === "bike" ? "bike" : "run",
      }));
    } catch (requestError) {
      setError(requestError.message || "We couldn’t split this mural.");
    } finally { setBusy(false); }
  };
  return (
    <section className="mural-card" aria-labelledby="mural-title">
      <div>
        <span className="eyebrow">Community GPS mural</span>
        <h3 id="mural-title">Make it together</h3>
        <p>Split this drawing into balanced, continuous sections for a group.</p>
      </div>
      <div className="mural-controls">
        <label>Artists
          <input type="number" min="2" max="24" value={participants} onChange={(event) => setParticipants(event.target.value)} />
        </label>
        <button type="button" className="button button--secondary" onClick={create} disabled={busy}>
          {busy ? "Splitting..." : "Create mural plan"}
        </button>
      </div>
      {plan && <ul className="mural-sections">{plan.sections.map((section) => (
        <li key={section.id}><span>{section.label}, {formatMetric(section.distance_km)} km</span><button type="button" onClick={() => saveFile(`${safeFilePart(section.label)}.gpx`, section.gpx, "application/gpx+xml")}>GPX</button></li>
      ))}</ul>}
      {error && <p className="editor-error" role="alert">{error}</p>}
    </section>
  );
}

const GPS_ACCURACY_PROFILES = [
  { value: 5, label: "Open sky / dual-band (5 m)" },
  { value: 10, label: "Typical phone or watch (10 m)" },
  { value: 20, label: "Tall buildings or trees (20 m)" },
];

function InkproofCard({ points, overlayType, onOverlayChange }) {
  const [accuracy, setAccuracy] = useState("10");
  const [analysis, setAnalysis] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const showing = overlayType === "inkproof";

  const overlay = useCallback((result) => ({
    type: "inkproof",
    segments: (result?.fragile_segments ?? []).map((segment) => ({
      ...segment,
      kind: "inkproof",
    })),
  }), []);

  const check = async () => {
    if (!Array.isArray(points) || points.length < 4 || busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await analyseInkproof({
        points,
        accuracy_m: Number(accuracy),
      });
      setAnalysis(response);
      onOverlayChange(response.fragile_segments?.length ? overlay(response) : null);
    } catch (requestError) {
      setError(requestError.message || "We couldn’t test this drawing against GPS drift.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="inkproof-card" aria-labelledby="inkproof-title">
      <div>
        <span className="eyebrow">Free · before you go</span>
        <h3 id="inkproof-title">Inkproof GPS forecast</h3>
        <p>Simulate GPS drift and find details that may disappear from the recorded artwork.</p>
      </div>
      <div className="niche-controls">
        <label>
          Expected accuracy
          <select value={accuracy} onChange={(event) => setAccuracy(event.target.value)}>
            {GPS_ACCURACY_PROFILES.map((profile) => (
              <option key={profile.value} value={profile.value}>{profile.label}</option>
            ))}
          </select>
        </label>
        <button type="button" className="button button--secondary" onClick={check} disabled={busy}>
          {busy ? "Simulating..." : "Test recording durability"}
        </button>
      </div>
      {analysis && (
        <div className="niche-result" role="status">
          <div className="niche-score-row">
            <strong>{formatPercent(analysis.resilience_score)} inkproof</strong>
            <span>{normaliseLabel(analysis.rating)}</span>
          </div>
          <p>
            Expected recognition {formatPercent(analysis.expected_recognition)} · {formatPercent(analysis.fragile_share)} of the line needs extra care.
          </p>
          {analysis.fragile_segments?.length > 0 ? (
            <button
              type="button"
              className="niche-map-toggle"
              onClick={() => onOverlayChange(showing ? null : overlay(analysis))}
            >
              {showing ? "Hide fragile ink on map" : `Show ${analysis.fragile_segments.length} fragile area${analysis.fragile_segments.length === 1 ? "" : "s"} on map`}
            </button>
          ) : (
            <span className="niche-success">No structurally fragile details found.</span>
          )}
          <ul className="niche-tips">
            {(analysis.tips ?? []).slice(0, 2).map((tip) => <li key={tip}>{tip}</li>)}
          </ul>
        </div>
      )}
      {error && <p className="editor-error" role="alert">{error}</p>}
      <small>No paid map call: the test runs from route geometry only.</small>
    </section>
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

function GalleryLightbox({ assets, activeIndex, onClose, onMove }) {
  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);
  const previousFocusRef = useRef(null);
  const asset = assets[activeIndex];

  useEffect(() => {
    previousFocusRef.current = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    return () => {
      document.body.style.overflow = previousOverflow;
      if (previousFocusRef.current?.isConnected) previousFocusRef.current.focus();
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        onMove(-1);
        return;
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        onMove(1);
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = [...(dialogRef.current?.querySelectorAll(
        'button:not(:disabled), a[href]',
      ) ?? [])];
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!dialogRef.current?.contains(document.activeElement)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose, onMove]);

  if (!asset) return null;
  const hasMultipleAssets = assets.length > 1;

  return (
    <div
      className="gallery-lightbox-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="gallery-lightbox"
        role="dialog"
        aria-modal="true"
        aria-labelledby="gallery-lightbox-title"
        aria-describedby="gallery-lightbox-position"
        ref={dialogRef}
      >
        <div className="gallery-lightbox-header">
          <div>
            <h2 id="gallery-lightbox-title">Gallery viewer</h2>
            <p id="gallery-lightbox-position" aria-live="polite">
              Image {activeIndex + 1} of {assets.length}
            </p>
          </div>
          <button
            type="button"
            className="gallery-lightbox-close"
            onClick={onClose}
            ref={closeButtonRef}
            aria-label="Close gallery viewer"
          >
            <span aria-hidden="true">×</span>
          </button>
        </div>

        <div className="gallery-lightbox-stage">
          {hasMultipleAssets && (
            <button
              type="button"
              className="gallery-lightbox-nav gallery-lightbox-nav--previous"
              onClick={() => onMove(-1)}
              aria-label="Previous gallery image"
            >
              <span aria-hidden="true">←</span>
            </button>
          )}
          <div className="gallery-lightbox-media">
            <img
              src={asset.image_url}
              alt={`Anonymous GPS art route, gallery image ${activeIndex + 1} of ${assets.length}`}
              width={asset.width || undefined}
              height={asset.height || undefined}
            />
          </div>
          {hasMultipleAssets && (
            <button
              type="button"
              className="gallery-lightbox-nav gallery-lightbox-nav--next"
              onClick={() => onMove(1)}
              aria-label="Next gallery image"
            >
              <span aria-hidden="true">→</span>
            </button>
          )}
        </div>

        <div className="gallery-lightbox-footer">
          <span>Use ← and → to browse. Press Esc to close.</span>
          <a href={asset.image_url} target="_blank" rel="noreferrer">
            Open original
          </a>
        </div>
      </div>
    </div>
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
  const [activeAssetId, setActiveAssetId] = useState(null);
  const removedAssetIdsRef = useRef(new Set());

  const activeAssetIndex = assets.findIndex((asset) => asset.id === activeAssetId);

  const moveLightbox = useCallback((offset) => {
    setActiveAssetId((currentId) => {
      if (assets.length === 0) return null;
      const currentIndex = assets.findIndex((asset) => asset.id === currentId);
      const safeIndex = currentIndex >= 0 ? currentIndex : 0;
      const nextIndex = (safeIndex + offset + assets.length) % assets.length;
      return assets[nextIndex].id;
    });
  }, [assets]);

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
      setActiveAssetId((currentId) => (currentId === asset.id ? null : currentId));
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
          {assets.map((asset, index) => (
            <article className="gallery-card" key={asset.id}>
              <button
                type="button"
                className="gallery-thumbnail"
                onClick={() => setActiveAssetId(asset.id)}
                aria-label={`Open gallery image ${index + 1} of ${assets.length}`}
              >
                <img
                  src={asset.image_url}
                  alt="Anonymous GPS art route on an OpenStreetMap street map"
                  loading="lazy"
                  width={asset.width || undefined}
                  height={asset.height || undefined}
                />
              </button>
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
      {activeAssetIndex >= 0 && (
        <GalleryLightbox
          assets={assets}
          activeIndex={activeAssetIndex}
          onClose={() => setActiveAssetId(null)}
          onMove={moveLightbox}
        />
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

function ResultPanel({ result, onDownload, onGalleryPublished, onEditRequest, focusRef }) {
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
  const [repairBusy, setRepairBusy] = useState(false);
  const [repairNotice, setRepairNotice] = useState("");
  const [activeConcernCode, setActiveConcernCode] = useState(null);
  const [labOverlay, setLabOverlay] = useState(null);
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
    setActiveConcernCode(null);
    setLabOverlay(null);
  }, [result.request_id, result.prompt]);

  const chooseCandidate = useCallback((candidateId) => {
    setSelectedCandidateId(candidateId);
    setEditing(false);
    setEditedRoute(null);
    setControlPoints([]);
    setEditError("");
    setEditDirty(false);
    setGalleryConsent(false);
    setGalleryError("");
    setPublishedAsset(null);
    setActiveConcernCode(null);
    setLabOverlay(null);
  }, []);

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
  const routeReadiness = routeDetails?.readiness ?? {};
  const readinessConcerns = Array.isArray(routeReadiness.concerns)
    ? routeReadiness.concerns
    : [];
  const mappedConcernCount = readinessConcerns.reduce(
    (count, concern) => count + (concern.segments_preview?.length ?? 0),
    0,
  );
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
  const shapeSource = activeRoute.shape_source ?? result.shape?.source;
  const aiDrawingReview = result.shape?.semantic_verification;
  const aiDrawingCueCount = aiDrawingReview?.cue_results?.filter(
    (cue) => cue.present,
  ).length;
  const fitDecision = result.fit_decision;
  const requestedShape = normaliseLabel(
    fitDecision?.requested_shape ?? result.requested_shape ?? result.shape?.name,
  );
  const understoodDrawing = normaliseLabel(
    result.intent?.text
      ? `Text “${result.intent.text}”`
      : result.requested_shape ?? result.intent?.shape ?? result.shape?.name,
  );
  const city = result.intent?.city ? normaliseLabel(result.intent.city) : "your selected area";
  const activity = result.intent?.sport === "bike" ? "Cycling" : "Running";
  const targetDistance =
    activeRoute.target_distance_km ?? result.intent?.distance_km ?? distanceDetails.target_km;
  const planningOptions = result.planning_options ?? {};
  const enabledPreferences = Object.entries(planningOptions.route_preferences ?? {})
    .filter(([, enabled]) => enabled)
    .map(([key]) => normaliseLabel(key.replace(/^avoid /, "")));
  const candidateSummary = result.candidate_summary ?? {};
  const reviewCount = Number.isFinite(candidateSummary.review_count)
    ? candidateSummary.review_count
    : Number.isFinite(candidateSummary.rejected_selected_shape_count)
      ? candidateSummary.rejected_selected_shape_count
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
        route_preferences: result.planning_options?.route_preferences ?? undefined,
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
        allow_gallery_share: false,
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
    result.planning_options,
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

  const improveRecognition = useCallback(async () => {
    if (repairBusy || !(activeRoute.ideal_preview ?? []).length) return;
    setRepairBusy(true);
    setRepairNotice("");
    try {
      const response = await repairRecognition({
        reference_points: activeRoute.ideal_preview,
        sport: result.intent?.sport === "bike" ? "bike" : "run",
        closed: Boolean(activeRoute.closed),
        name: `${shapeName} refined in ${city}`,
        route_preferences: result.planning_options?.route_preferences ?? undefined,
      });
      setEditedRoute({
        ...activeRoute,
        id: `${activeRouteId}-recognition-repair`,
        points_preview: response.points_preview,
        ideal_preview: response.guide_points,
        distance_km: response.distance_km,
        snapped: response.snapped,
        details: { ...routeDetails, readiness: response.readiness },
        gpx: response.gpx,
        allow_gallery_share: true,
      });
      setRepairNotice(`${response.message} Recognition score: ${formatPercent(response.recognition_score)}.`);
    } catch (repairError) {
      setRepairNotice(repairError.message || "We couldn’t refine this drawing.");
    } finally {
      setRepairBusy(false);
    }
  }, [
    activeRoute,
    activeRouteId,
    city,
    repairBusy,
    result.intent,
    result.planning_options,
    routeDetails,
    shapeName,
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

      <section className="request-summary-card" aria-labelledby="request-summary-title">
        <div className="request-summary-heading">
          <div>
            <span className="eyebrow">Your request</span>
            <h3 id="request-summary-title">We understood {understoodDrawing}</h3>
          </div>
          <button type="button" className="button button--quiet" onClick={onEditRequest}>
            Change request
          </button>
        </div>
        <dl className="request-summary-facts">
          <div>
            <dt>Drawing</dt>
            <dd>{understoodDrawing}</dd>
          </div>
          <div>
            <dt>Place</dt>
            <dd>{city}</dd>
          </div>
          <div>
            <dt>Activity</dt>
            <dd>{activity}</dd>
          </div>
          <div>
            <dt>Target</dt>
            <dd>{targetDistance != null ? `${formatMetric(targetDistance)} km` : "Planner default"}</dd>
          </div>
          {planningOptions.start_label && (
            <div>
              <dt>Start</dt>
              <dd>{planningOptions.start_label}</dd>
            </div>
          )}
          {Number.isFinite(planningOptions.start_direction_deg) && (
            <div>
              <dt>First direction</dt>
              <dd>{Math.round(planningOptions.start_direction_deg)}°</dd>
            </div>
          )}
          {enabledPreferences.length > 0 && (
            <div>
              <dt>Preferences</dt>
              <dd>{enabledPreferences.join(", ")}</dd>
            </div>
          )}
        </dl>
        {shapeSource === "fallback" && (
          <p className="request-summary-warning" role="status">
            We understood the request, but could not make a reliable custom outline. Change the
            wording before using a labelled fallback.
          </p>
        )}
        {fitDecision?.substituted && (
          <p className="request-summary-warning" role="status">
            The selected route uses {shapeName} instead of {understoodDrawing}; the street-fit
            explanation appears below.
          </p>
        )}
      </section>

      <div className="result-layout">
        <div className="map-card">
          <section className="candidate-compare" aria-labelledby="route-options-title">
            <div className="candidate-compare-heading">
              <div>
                <span className="eyebrow">Compare</span>
                <h3 id="route-options-title">Route options</h3>
              </div>
              <span>
                {candidates.length > 0
                  ? `${candidateSummary.verified_count ?? candidateSummary.accepted_count ?? 0} ready · ${reviewCount} to review`
                  : "Closest route found"}
              </span>
            </div>
            {candidates.length > 0 ? (
              <div className="candidate-card-list" role="list">
                {candidates.map((candidate, index) => {
                  const candidateReadiness = candidate.details?.readiness ?? {};
                  const selected = selectedCandidate?.id === candidate.id;
                  return (
                    <button
                      type="button"
                      role="listitem"
                      key={candidate.id}
                      data-candidate-id={candidate.id}
                      className={`candidate-card${selected ? " candidate-card--selected" : ""}`}
                      aria-pressed={selected}
                      onClick={() => chooseCandidate(candidate.id)}
                    >
                      <span className="candidate-card-topline">
                        <span>Option {index + 1}</span>
                        <b className={candidate.verification?.passed ? "status-good" : "status-warn"}>
                          {candidate.verification?.passed ? "Ready" : "Review"}
                        </b>
                      </span>
                      <strong>
                        {index === 0 ? "Best overall match" : normaliseLabel(candidate.shape_name)}
                      </strong>
                      <span className="candidate-card-metrics">
                        <span><b>{formatPercent(candidate.validation?.shape_fidelity)}</b> likeness</span>
                        <span><b>{formatMetric(candidate.distance_km)}</b> km</span>
                        <span>
                          <b>
                            {Number.isFinite(candidateReadiness.elevation_gain_m)
                              ? `${Math.round(candidateReadiness.elevation_gain_m)} m`
                              : "n/a"}
                          </b>{" "}
                          climb
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <p className="candidate-empty">Showing the closest route the planner found.</p>
            )}
          </section>

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
                readinessConcerns={readinessConcerns}
                activeConcernCode={activeConcernCode}
                analysisSegments={labOverlay?.segments ?? []}
                streetCanvasCandidates={result.street_canvas ?? []}
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
                Changes saved: {formatMetric(editedRoute.distance_km)} km.
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
            {mappedConcernCount > 0 && (
              <span>
                <span className="legend-line legend-line--concern" aria-hidden="true" /> Review
                section
              </span>
            )}
            {labOverlay?.type === "inkproof" && (
              <span><span className="legend-line legend-line--inkproof" aria-hidden="true" /> Fragile ink</span>
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
                : "Preview only. Not matched to streets"}
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
                  : "n/a"
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
                `${candidateSummary.verified_count ?? candidateSummary.accepted_count ?? 0} ready · ${reviewCount} review${
                  Number.isFinite(result.preflight_count) && result.preflight_count > 0
                    ? ` · ${result.preflight_count} locations`
                    : ""
                }`
              }
              tone={(candidateSummary.verified_count ?? 0) > 0 ? "good" : "warn"}
            />
          </dl>

          <RouteReadinessCard
            readiness={routeReadiness}
            roadRouted={Boolean(activeRoute.snapped)}
            activeConcernCode={activeConcernCode}
            onConcernSelect={(concernCode) => {
              setLabOverlay(null);
              setActiveConcernCode(concernCode);
            }}
          />

          {fitDecision && (
            <div className={`notice ${fitDecision.substituted ? "notice--success" : "notice--warning"}`}>
              <strong>
                {fitDecision.substituted
                  ? `${requestedShape} did not fit these streets. Here is a ${shapeName}`
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

          {shapeSource === "llm" && !fitDecision?.substituted && (
            <div className="notice notice--info">
              <strong>Made from your idea</strong>
              <p>
                This outline was created for your description. We sketched{" "}
                {result.shape?.generated_candidate_count || "several"} different versions
                and kept the strongest route-friendly one.
              </p>
              {aiDrawingReview?.independent && aiDrawingReview.score != null ? (
                <p>
                  A separate visual check scored it {formatPercent(aiDrawingReview.score)}
                  {Number.isFinite(aiDrawingCueCount)
                    ? ` and found ${aiDrawingCueCount} of ${aiDrawingReview.cue_results.length} defining features`
                    : ""}.
                </p>
              ) : (
                <p>
                  Geometry checks passed. Compare the dashed drawing with the street route
                  before heading out.
                </p>
              )}
            </div>
          )}

          {shapeSource === "llm" && aiDrawingReview?.cue_results?.length > 0 && (
            <details className="route-facts ai-recognition-card">
              <summary>Recognition audit</summary>
              <p className="route-facts-intro">
                A separate visual check looks for the defining features in the finished
                outline, not just in the AI description.
              </p>
              <ul className="gate-list">
                {aiDrawingReview.cue_results.map((cue) => (
                  <li
                    key={cue.feature_id}
                    className={cue.present ? "gate--pass" : "gate--fail"}
                  >
                    <span className="gate-icon" aria-hidden="true">
                      {cue.present ? "✓" : "!"}
                    </span>
                    <span>
                      <strong>{normaliseLabel(cue.feature_id)}</strong>
                      {cue.reason && <small>{cue.reason}</small>}
                    </span>
                    <span className="gate-value">
                      {cue.score == null ? (cue.present ? "Found" : "Missing") : formatPercent(cue.score)}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
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

        </div>

      <div className="route-output">
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
                    {routingDetails.route_point_count ?? "n/a"} / {routingDetails.guide_point_count ?? "n/a"}
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
                    <dt>Start to finish gap</dt>
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
            {activeRoute.gallery_publish_token && (!editedRoute || editedRoute.allow_gallery_share) && (
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

      <section className="route-lab" aria-labelledby="route-lab-title">
        <div className="route-lab-heading">
          <div>
            <span className="eyebrow">Optional tools</span>
            <h3 id="route-lab-title">Fine-tune or plan together</h3>
          </div>
          <p>The route decision and download stay above; use these only when you need them.</p>
        </div>
        <div className="route-lab-grid">
          <StreetCanvasCard candidates={result.street_canvas ?? []} />
          <InkproofCard
            key={`inkproof-${activeRouteId}`}
            points={activeRoute.points_preview ?? []}
            overlayType={labOverlay?.type}
            onOverlayChange={(overlayValue) => {
              setActiveConcernCode(null);
              setLabOverlay(overlayValue);
            }}
          />
          <TimedReadinessCard points={activeRoute.points_preview ?? []} />
          <section className="recognition-repair-card" aria-labelledby="repair-title">
            <div>
              <span className="eyebrow">Recognition repair</span>
              <h3 id="repair-title">Make the outline read more clearly</h3>
              <p>Re-route from the shape's strongest visual anchors and compare the result.</p>
            </div>
            <button
              type="button"
              className="button button--secondary"
              onClick={improveRecognition}
              disabled={repairBusy || !(activeRoute.ideal_preview ?? []).length}
            >
              {repairBusy ? "Refining..." : "Find a crisper version"}
            </button>
            {repairNotice && <p className="editor-success" role="status">{repairNotice}</p>}
          </section>
          <CommunityMuralCard
            activeRoute={activeRoute}
            shapeName={shapeName}
            city={city}
            sport={result.intent?.sport}
          />
        </div>
      </section>

      {issueList.length > 0 && (
        <div className="details-grid">
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
  const [imageUrl, setImageUrl] = useState("");
  const [imageCity, setImageCity] = useState(SUGGEST_CITIES[0]);
  const [imageSport, setImageSport] = useState("run");
  const [imageDistance, setImageDistance] = useState("10");
  const [imageErrors, setImageErrors] = useState({});
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
  const imageUrlRef = useRef(null);
  const imageCityRef = useRef(null);
  const imageSportRef = useRef(null);
  const imageDistanceRef = useRef(null);

  useEffect(() => {
    if (result) resultRef.current?.focus();
  }, [result]);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  useEffect(() => {
    if (promptValidationAttempt > 0 && promptError) promptRef.current?.focus();
  }, [promptError, promptValidationAttempt]);

  useEffect(
    () => () => {
      requestRef.current?.abort();
    },
    [],
  );

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

  const generate = useCallback(async (nextPrompt, extraPayload = {}) => {
    const cleanPrompt = normaliseRoutePrompt(nextPrompt);
    if (!cleanPrompt) return;

    const controller = new AbortController();
    requestRef.current?.abort();
    requestRef.current = controller;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await generateRoute(cleanPrompt, {
        signal: controller.signal,
        payload: extraPayload,
      });
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

  const focusPrompt = useCallback(() => {
    document.querySelector("#route-designer")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
    window.requestAnimationFrame(() => promptRef.current?.focus());
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

  function handleImageImport(event) {
    event.preventDefault();
    if (loading) return;

    const checkedUrl = validateImageReferenceUrl(imageUrl);
    const { errors: selectionErrors, numericDistance } = validateSuggestion({
      city: imageCity,
      sport: imageSport,
      distance: imageDistance,
    });
    const nextErrors = { ...selectionErrors, url: checkedUrl.error };
    setImageErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) {
      if (nextErrors.url) imageUrlRef.current?.focus();
      else if (nextErrors.city) imageCityRef.current?.focus();
      else if (nextErrors.sport) imageSportRef.current?.focus();
      else imageDistanceRef.current?.focus();
      return;
    }

    const activity = imageSport === "bike" ? "cycling" : "running";
    const imagePrompt = `a custom image in ${imageCity}, ${activity}, about ${numericDistance} km`;
    setImageUrl(checkedUrl.value);
    setPrompt(imagePrompt);
    setPromptError("");
    generate(imagePrompt, { reference_image_url: checkedUrl.value });
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
              Bring an idea. Choose a classic shape or something completely yours. Add a city, activity,
              and distance, and we’ll test it against nearby streets.
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
                <p>Got a shape in mind? Describe it, even if it isn’t in the catalog.</p>
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
                  placeholder="A flying pig in Budapest, running, 10 km"
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
                Try: a flying pig in Budapest, running, 10 km. Custom ideas are welcome.
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
                      <span aria-hidden="true">{ideaGlyph(idea)}</span>
                      {idea.label}
                    </button>
                  ))}
                </div>
              </fieldset>

              <details className="idea-catalog">
                <summary>
                  <span>
                    <strong>More shapes, letters, and numbers</strong>
                    <small>{QUICK_IDEAS.length} ready-made options, or type your own idea above.</small>
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
                              <span aria-hidden="true">{ideaGlyph(idea)}</span>
                              {idea.label}
                            </button>
                          ))}
                        </div>
                      </section>
                    );
                  })}
                  {filteredIdeas.length === 0 && (
                    <p className="idea-empty" role="status">
                      Nothing in the catalog? No problem. Type your own idea above.
                    </p>
                  )}
                </div>
              </details>

              <div className="prompt-actions prompt-actions--single">
                <button
                  type="submit"
                  className="button button--primary generate-button"
                  disabled={loading}
                >
                  <span>{loading ? "Finding routes…" : "Find routes"}</span>
                </button>
              </div>
            </form>

            <details className="image-reference-panel" open>
              <summary>
                <span>
                  <strong>Use an image link</strong>
                  <small>Fit an SVG or image outline to streets in a city you choose.</small>
                </span>
                <b aria-hidden="true">+</b>
              </summary>
              <form className="image-reference-form" onSubmit={handleImageImport} noValidate>
                <label className="image-url-field" htmlFor="image-reference-url">
                  <span>Direct SVG or image URL</span>
                  <input
                    id="image-reference-url"
                    ref={imageUrlRef}
                    type="url"
                    value={imageUrl}
                    onChange={(event) => {
                      setImageUrl(event.target.value);
                      if (imageErrors.url) {
                        setImageErrors((current) => ({
                          ...current,
                          url: validateImageReferenceUrl(event.target.value).error,
                        }));
                      }
                    }}
                    placeholder="https://example.com/drawing.svg"
                    aria-describedby="image-url-help"
                    aria-invalid={Boolean(imageErrors.url)}
                    aria-errormessage={imageErrors.url ? "image-url-error" : undefined}
                    disabled={loading}
                    required
                  />
                </label>
                <p id="image-url-help" className="field-help">
                  SVG paths are used directly. PNG, JPG, WebP, and GIF outlines are traced from the image. Maximum 5 MB. Use an image you have permission to reuse.
                </p>
                {imageErrors.url && (
                  <p id="image-url-error" className="field-error" role="alert">
                    <span aria-hidden="true">!</span>
                    {imageErrors.url}
                  </p>
                )}
                <div className="image-reference-fields">
                  <div className="field">
                    <label htmlFor="image-city">Destination</label>
                    <select
                      id="image-city"
                      ref={imageCityRef}
                      value={imageCity}
                      onChange={(event) => setImageCity(event.target.value)}
                      disabled={loading}
                    >
                      {SUGGEST_CITY_GROUPS.map((group) => (
                        <optgroup key={group.label} label={group.label}>
                          {group.cities.map((cityName) => (
                            <option key={cityName} value={cityName}>{cityName}</option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="image-activity">Travel mode</label>
                    <select
                      id="image-activity"
                      ref={imageSportRef}
                      value={imageSport}
                      onChange={(event) => setImageSport(event.target.value)}
                      disabled={loading}
                    >
                      <option value="run">Running</option>
                      <option value="bike">Cycling</option>
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="image-distance">Length</label>
                    <div className="distance-input">
                      <input
                        id="image-distance"
                        ref={imageDistanceRef}
                        type="number"
                        min={distanceLimits(imageSport).minimum}
                        max={distanceLimits(imageSport).maximum}
                        step="0.5"
                        value={imageDistance}
                        onChange={(event) => setImageDistance(event.target.value)}
                        disabled={loading}
                      />
                      <span>km</span>
                    </div>
                  </div>
                  <button type="submit" className="button button--secondary" disabled={loading}>
                    {loading ? "Fitting image…" : "Fit image to city"}
                  </button>
                </div>
                {(imageErrors.city || imageErrors.sport || imageErrors.distance) && (
                  <p className="field-error" role="alert">
                    <span aria-hidden="true">!</span>
                    {imageErrors.city || imageErrors.sport || imageErrors.distance}
                  </p>
                )}
              </form>
            </details>

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
                      {minimumDistance} to {maximumDistance} km for {activityLabel}.
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
              <h2>We couldn’t finish this route</h2>
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
            onEditRequest={focusPrompt}
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

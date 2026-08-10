# City-aware shape recommendations

## What “recommended” means

A recommendation is a shortlist for measurement, not a claim that a shape is
guaranteed to work throughout a city. The application scores every one of its
73 route templates, shortlists the best three continuous and geometrically
diverse candidates for the existing placement/routing pipeline, and keeps the best
candidate actually measured on the activity-specific street graph. A primary
candidate that already passes every gate can end the search early.

This ordering follows five research findings:

1. Street orientation order, connectedness, dead ends, segment length, and
   circuity vary materially between cities ([Boeing, 2019](https://doi.org/10.1007/s41109-019-0189-1)).
2. Walkable and drivable networks in the same place can have different
   circuity, so activity cannot be treated as a label applied after route
   selection ([Boeing, 2017](https://arxiv.org/abs/1708.00836)).
3. Standard shortest-path routing can erase shape detail or introduce severe
   detours around rivers, lakes, parks, and off-road control points
   ([Waschk and Krüger, 2019](https://doi.org/10.1007/s41095-019-0146-z)).
4. Strong GPS-art systems search placement, rotation, and scale, then compare
   multiple routed candidates rather than trusting one initial match
   ([Powałka, 2023](https://repository.tudelft.nl/record/uuid%3A11e9b0c2-5d67-475a-8653-71c7afe03dad)).
5. Turning relations and segment-length proportions help distinguish a
   recognisable road graphic from a stretched lookalike
   ([Li and Fu, 2026](https://doi.org/10.3390/ijgi15030098)).

The implementation therefore combines city context with shape geometry. The
45 Balaton municipalities have explicit numeric priors for grid order,
connectivity, barrier risk, and terrain risk; this avoids relying on English
keyword parsing for fine distinctions between shore settlements. Other cities
derive the same normalized traits from their curated contexts. The ranker
measures path continuity, normalized length, significant turns, accumulated
turning, dominant street-axis compatibility, aspect ratio, complexity, and a
routeability prior. City context contributes grid order, likely connectivity,
water/infrastructure barriers, terrain/irregularity, and radial structure.
Requested distance limits the amount of detail: a longer route can preserve
more corners without forcing impractically short street segments. Cycling has
its own capacity adjustment instead of reusing the running result.

Repeated planning passes for the same normalized city, context, activity, and
distance reuse a bounded 512-entry ranking cache. Callers receive fresh lists,
so one request cannot mutate another request's cached result. Invalid or
non-finite recommendation inputs fall back to the conservative running/default
distance profile instead of contaminating the cache.

## City coverage and useful starting families

The first table accounts for the original 80 selectable cities. The Balaton
table below adds the complete 45-municipality shore set; Siófok occurs in both
coverage sets, producing 124 unique picker options. These groups describe the
starting prior used before live placement and routing. The numeric traits are
continuous, so cities inside a group can still receive a different order.

| Street context | Cities | Shapes commonly worth measuring first |
|---|---|---|
| Water-constrained | Budapest, Szigetszentmiklós, Siófok, Dunaharaszti, Amsterdam, Copenhagen, Stockholm, Helsinki, Lisbon, Zurich | Short/medium: cat, lightning, square, hexagon. Longer: mushroom, speech bubble, cross. Compact continuous outlines reduce forced barrier crossings. |
| Radial or mixed grid | Debrecen, Szeged, Kecskemét, Sopron, Hajdúböszörmény, Kiskunfélegyháza, Madrid, Brussels, Bucharest, Munich, Milan | Short/medium: fox, hexagon, octagon, lightning. Longer: flower, speech bubble, crown, cross. Balanced or multi-directional outlines can use radial avenues and ring streets. |
| Dense ordered grid | Nyíregyháza, Tatabánya, Cegléd, Tata, Athens, Riga | Short/medium: square, lightning, cat, hourglass. Longer: crown, cross, shark, apple, speech bubble. Ordered bearings and higher connectivity support more landmarks. |
| Grid-accessible mixed fabric | Miskolc, Pécs, Győr, Székesfehérvár, Szombathely, Érd, Szolnok, Kaposvár, Veszprém, Zalaegerszeg, Békéscsaba, Eger, Dunakeszi, Nagykanizsa, Hódmezővásárhely, Dunaújváros, Gödöllő, Baja, Salgótarján, Budaörs, Pápa, Gyöngyös, Ajka, Jászberény, Orosháza, Szentes, Gyál, Hajdúszoboszló, Paris, Berlin, Rome, Barcelona, Vienna, Prague, Oslo, Warsaw, Kraków, Ljubljana, Zagreb, Sofia, Dublin, Tallinn | Short/medium: lightning, square, cat, hourglass. Longer: crown, cross, speech bubble, shark. Terrain, historic cores, or barriers reduce the score even where a usable grid exists. |
| Organic or weakly ordered | Vác, Mosonmagyaróvár, Esztergom, Szentendre, Gyula, Kiskunhalas, London, Bratislava | Short/medium: cat, fox, lightning, square. Longer: mushroom, leaf, shield. Lower directional order favors continuous silhouettes with few fragile corners. |
| Strong hill/irregularity constraint | Ózd, Szekszárd, Porto | Short/medium: arrow, cat, lightning, square. Longer: mushroom, fox, shield. Detail is capped aggressively because winding or sparse connections can deform notches and narrow limbs. |

### Lake Balaton placement contexts

| Street context | Municipalities | Shapes commonly worth measuring first |
|---|---|---|
| Larger connected shore grids | Balatonboglár, Balatonfüred, Balatonlelle, Keszthely, Siófok | Short/medium: square, lightning, cat, hexagon. Longer: crown, cross, shark, speech bubble. These places have enough connected streets for moderate detail, but the lake and rail corridor still penalise tall or barrier-crossing placements. |
| Flat south-shore corridor | Balatonberény, Balatonfenyves, Balatonföldvár, Balatonkeresztúr, Balatonmáriafürdő, Balatonőszöd, Balatonszabadi, Balatonszárszó, Balatonszemes, Balatonvilágos, Szántód, Zamárdi | Short/medium: arrow, lightning, square, shield. Longer: fox, mushroom, speech bubble. East-west silhouettes fit the narrow strip between the lake, railway, Route 7, and M7 better than tall intricate outlines. |
| Western basin, hills, or wetlands | Balatonederics, Balatonszentgyörgy, Fonyód, Gyenesdiás, Szigliget, Vonyarcvashegy | Short/medium: cat, arrow, heart, shield. Longer: fox, mushroom, leaf. Water, marshes, volcanic hills, or sloping streets make compact continuous shapes safer. |
| Hilly north and east shore | Alsóörs, Aszófő, Ábrahámhegy, Badacsonytomaj, Badacsonytördemic, Balatonakali, Balatonakarattya, Balatonalmádi, Balatonfűzfő, Balatongyörök, Balatonkenese, Balatonrendes, Balatonszepezd, Balatonudvari, Csopak, Kővágóörs, Örvényes, Paloznak, Révfülöp, Zánka | Short/medium: arrow, cat, heart, lightning. Longer: fox, mushroom, shield. Sparse, winding streets between the lake, railway, Route 71, and hills cap useful detail. |
| Strong peninsula or protected-land constraint | Tihany | Short/medium: heart, cat, arrow, shield. Longer shapes remain low-detail. Water on several sides, the Inner Lake, protected land, and sparse winding streets require very compact placement. |
| Inland northeast core | Balatonfőkajár | Short/medium: square, lightning, cat, arrow. Longer: fox, shield. It is less water-constrained, but a small sparse core, agricultural gaps, and the M7 still limit complexity. |

These are geometry-based starting families, not fixed assignments. Each of the
45 municipalities has an individual local context; distance and activity then
adjust detail capacity before live placement, snapping, routing, and quality
checks select the result.

These examples are not hard-coded city mascots. For example, Berlin does not
receive a bear merely because of its symbolism: the bear must compete on the
same geometric and routing evidence as every other template. The actual
shortlist also changes with distance and activity.

## Audit of all 73 route templates

The registry audit below is generated from geometry. “Disconnected” shapes
remain available when the user explicitly requests them, but they are not used
as automatic recommendations because joining separate strokes can introduce
unwanted transfer lines.

| Measured family | Templates | Recommendation policy |
|---|---|---|
| Simple smooth | circle, clover, heart, infinity, leaf, moon, triangle | Strong short-route candidates, especially where bearing order is low or radial. |
| Simple orthogonal/outline | diamond, square, hexagon, shield | Strong short-route candidates on ordered grids; compact shapes also survive moderate barriers. |
| Simple open | spiral, wave | Useful only when an open route and corridor-like placement fit the request. |
| Moderate open/orthogonal | arrow, lightning | Useful on constrained or elongated street fabrics; lightning benefits from an ordered axis. |
| Moderate continuous outline | bell, cat, crown, flower, fox, hourglass, location pin, mushroom, octagon, owl, pear, rocket, speech bubble, star, teardrop, whale | Main medium-distance pool. Ranking depends heavily on grid/radial order, terrain, barriers, and activity. |
| Detailed orthogonal | cactus, castle, cross | Reserved for longer routes with ordered, connected streets. |
| Detailed continuous outline | airplane, apple, bat, bear, butterfly, car, cloud, dog, duck, elephant, flame, guitar, house, maple leaf, mountain, penguin, pine tree, shark, snail, snowflake, tree, trophy, tulip, turtle, umbrella | Considered for long routes when city detail capacity is high; otherwise the overshoot penalty keeps them out of the expensive shortlist. |
| Disconnected | anchor, bird, dolphin, dragon, fish, helix, horse, key, mug, note, rabbit, sailboat, skull, sun | Analysed but excluded from automatic top-three selection. Still usable as an explicit user choice with normal routing and review gates. |

## Runtime decision sequence

1. Analyse the complete 73-template registry; cached immutable geometry
   profiles make later requests inexpensive.
2. Derive continuous city traits from the curated local geography profile.
3. Cap supported detail using activity and distance.
4. Rank every shape, penalising disconnected strokes and detail beyond what
   the request can plausibly preserve.
5. Select up to three high-scoring candidates from different geometry
   families.
6. Run the normal transform search, activity-specific routing, and independent
   quality gates. Accept the primary early only if it already passes; otherwise
   measure the alternatives and keep the best verified result.

The result screen exposes the selected shape and a short reason. It does not
describe the output as scientifically optimal: current city traits are curated
priors rather than measured neighbourhood-scale graph statistics, and final
safety/access still requires map review and local judgement.

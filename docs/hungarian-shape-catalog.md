# Hungary-friendly GPS-art shapes

## Outcome

The catalog adds 16 single-outline templates that are easy to discover with
English or Hungarian free text. They are not fixed city mascots: the example
city suggests a meaningful starting place, while the existing placement,
street routing, and quality gates decide whether a particular route works.

| Shape | Example city and starting distance | Route-design rationale |
|---|---|---|
| Paprika | Szeged, 12 km run | Compact asymmetric contour; the stem and tapered tip carry recognition without an inner stroke. |
| Puzzle cube | Budapest, 24 km ride | Broad, near-square stepped outline suits ordered streets and remains distinct from square, diamond, and hexagon. |
| Moustache | Kecskemét, 18 km run | Wide mirrored lobes suit a long urban axis; two tip curls and the centre notch carry the identity. |
| Grape cluster | Eger, 24 km ride | A continuous sequence of broad lobes suggests a bunch without separate grape circles or transfer legs. |
| Wine glass | Sopron, 18 km run | Bowl, narrow stem, and broad base remain legible in one boundary, but need more distance than a simple symbol. |
| Cauldron | Békéscsaba, 18 km run | High handle, rim shoulders, rounded pot, and two feet form one compact loop. |
| Horseshoe | Debrecen, 16 km run | The deep U-shaped notch is a strong, widely separated landmark that survives moderate road snapping. |
| Wheat | Békéscsaba, 28 km ride | Alternating grain tips are intentionally coarse and need a longer route and a connected grid. |
| Suspension bridge | Budapest, 30 km ride | Two towers, a shallow cable valley, deck, and supports favour ordered bearings and a long route. |
| Water tower | Szeged, 22 km ride | A wide tank, narrow shaft, and separated base legs create a recognisable architectural silhouette. |
| Grey cattle | Debrecen, 28 km ride | Long lateral horns and a compact head are the identity cues; small facial detail is deliberately omitted. |
| Stag | Gyöngyös, 30 km ride | Coarse antler branches and a long face use large contour events instead of fragile interior lines. |
| Pomegranate | Pécs, 14 km run | Crown-shaped calyx plus round fruit body makes a compact medium-detail route. |
| Chimney cake | Budapest, 24 km ride | Alternating edge steps hint at the spiral crust while keeping one non-self-intersecting boundary. |
| Thermal bath | Hajdúszoboszló, 28 km ride | Dome, stepped wings, and one broad water notch create a city-linked architectural icon. |
| Folk gate | Szentendre, 30 km ride | Roof peaks, three posts, and two broad openings fit orthogonal streets at longer distances. |

## Research translated into templates

The selection combines cultural relevance with street geometry rather than
copying decorative icons:

1. The official [Collection of Hungarikums](https://www.hungarikum.hu/sites/default/files/hungarikumok-lista_2025.02.11_0.pdf)
   identifies the Rubik's Cube, Hungarian grey cattle, chimney cake, and the
   paprika traditions of Szeged, Kalocsa, and Szentes as recognised Hungarian
   values. Visit Hungary also presents the
   [Rubik's Cube in Budapest street art](https://visithungary.com/articles/walks-around-hungarian-guerrilla-and-official-street-art)
   and [paprika as a characteristic Szeged/Kalocsa product](https://visithungary.com/articles/flora--and--fauna).
2. Wine motifs have several useful city associations: Visit Hungary describes
   [Eger's wine tourism](https://visithungary.com/articles/relax-with-wine-in-eger),
   while the official collection includes Egri Bikavér and several regional
   wine values. The catalog therefore uses one routeable grape silhouette and
   one glass rather than multiple near-duplicate bottles.
3. The architectural examples are tied to real destinations. Szeged tourism
   calls its [Szent István Square water tower](https://szegedtourism.hu/en/water-tower-in-st-steven-square/)
   a distinctive industrial monument, Hajdúszoboszló presents itself as a
   [Great Plain spa city](https://hajduszoboszlo.hu/en/), and Szentendre's
   [open-air museum](https://visithungary.com/articles/ethnographic-museum-in-szentendre)
   preserves regional buildings, gates, and porches.
4. Hungarian cities do not share one street pattern. The
   [National Atlas of Hungary](https://www.nemzetiatlasz.hu/MNA/National-Atlas-of-Hungary_Vol3_Ch9.pdf)
   documents varied settlement forms, while the national study of
   [Hungarian urban squares](https://doi.org/10.3390/land14091780) distinguishes
   linear, L-shaped, and differently enclosed centres. This is why the new set
   mixes compact, wide, radial, and orthogonal outlines instead of attaching
   one motif to every Hungarian city.
5. GPS art is ultimately a road-graph matching problem. Li and Fu's
   [road-network graphics retrieval method](https://doi.org/10.3390/ijgi15030098)
   relies on turning relations and segment-length ratios. The templates retain
   a few large tips, notches, lobes, or steps that those relations can describe,
   then let live routing validate the result.

## Geometry and language safeguards

Every new template is one closed, self-intersection-free path. Normalized route
lengths range from 2.75 to 6.48 units; simple shapes are suited to shorter
requests and high-detail shapes receive longer presets. Hungarian aliases and
common inflected request forms are registered for terms such as `paprikát`,
`Rubik-kockát`, `szürkemarhát`, `kürtőskalácsot`, and `gyógyfürdőt`.

The production uniqueness audit now compares all 10,440 pairs in the
145-template registry after removing translation, scale, rotation, route start,
and traversal direction. No new pair reaches the `0.02` duplicate threshold;
the closest new relation is puzzle cube versus drum at approximately `0.079`.
This proves that the authored route targets differ. Final routes can still
collapse on a sparse street graph, so target-specific fidelity and manual
review remain necessary.

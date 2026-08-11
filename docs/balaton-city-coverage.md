# Lake Balaton city coverage

## Scope

The application uses the current shore-municipality list in Annex 1/2 of
Hungary's [Act CXII of 2000](https://njt.hu/jogszabaly/2000-112-00-00). The
annex contains 52 entries: 45 shore municipalities and seven entries marked
with an asterisk as near-shore municipalities. The picker includes the 45 shore
municipalities and deliberately excludes the seven near-shore entries:
Alsópáhok, Cserszegtomaj, Felsőörs, Felsőpáhok, Hévíz, Kőröshegy, and Lovas.

Siófok is also one of the 50 major Hungarian cities already present in the
application. It stays in the Hungary option group and is not duplicated in the
Lake Balaton group. The result is 44 new options and 124 unique destinations in
the picker.

## Included municipalities

| Shore sector | Municipalities |
|---|---|
| North and east | Alsóörs, Aszófő, Ábrahámhegy, Badacsonytomaj, Badacsonytördemic, Balatonakali, Balatonakarattya, Balatonalmádi, Balatonederics, Balatonfőkajár, Balatonfüred, Balatonfűzfő, Balatongyörök, Balatonkenese, Balatonrendes, Balatonszepezd, Balatonudvari, Csopak, Gyenesdiás, Keszthely, Kővágóörs, Örvényes, Paloznak, Révfülöp, Szigliget, Tihany, Vonyarcvashegy, Zánka |
| South and west | Balatonberény, Balatonboglár, Balatonfenyves, Balatonföldvár, Balatonkeresztúr, Balatonlelle, Balatonmáriafürdő, Balatonőszöd, Balatonszabadi, Balatonszárszó, Balatonszemes, Balatonszentgyörgy, Balatonvilágos, Fonyód, Siófok, Szántód, Zamárdi |

## Route-planning treatment

Every listed municipality has a local centre and a route-oriented search box,
so selecting it does not require a public geocoding request. The boxes focus on
continuous settlement streets rather than water-heavy administrative bounds.
Coordinates were checked with the
[Nominatim Search API](https://nominatim.org/release-docs/latest/api/Search/);
map data in the product retains OpenStreetMap attribution.

Each municipality also has its own planning context. The recommender uses these
descriptions to estimate street order, connectivity, barrier risk, and terrain
risk. Important distinctions include:

- the larger connected grids in Siófok, Keszthely, Balatonfüred,
  Balatonboglár, and Balatonlelle;
- the flat but narrow south-shore corridor between the lake, railway, Route 7,
  and M7;
- the hilly, irregular north shore between Lake Balaton, Route 71, rail, and
  vineyard or forest roads;
- the volcanic hills, wetlands, and separated street clusters around the
  western basin; and
- the severe water and protected-land constraints of Tihany and Szigliget.

These profiles only determine which templates and placements are worth
measuring first. They do not certify that a road is safe, public, accessible,
or currently open. The application still snaps candidates to the selected
activity network, obtains a routed line, runs independent quality gates, and
requires map review where a result does not pass automatically.

## Baseline recommendation list

The following audit is produced by the same 73-template ranker used at runtime.
It shows three starting candidates for a typical 8 km run and 25 km ride.
These are not fixed city mascots: changing distance or activity changes the
detail budget, and live placement and routing can change the final winner.

| Municipality | 8 km run | 25 km ride |
|---|---|---|
| Alsóörs | square, diamond, arrow | square, diamond, clover |
| Aszófő | square, diamond, arrow | square, diamond, clover |
| Ábrahámhegy | square, diamond, arrow | square, diamond, clover |
| Badacsonytomaj | square, clover, diamond | square, clover, diamond |
| Badacsonytördemic | square, clover, diamond | square, clover, diamond |
| Balatonakali | square, diamond, arrow | square, diamond, clover |
| Balatonakarattya | square, diamond, arrow | square, diamond, clover |
| Balatonalmádi | square, diamond, arrow | square, diamond, clover |
| Balatonberény | square, diamond, lightning | lightning, fox, square |
| Balatonboglár | square, lightning, diamond | lightning, hourglass, square |
| Balatonederics | square, diamond, octagon | square, diamond, octagon |
| Balatonfenyves | square, diamond, lightning | lightning, fox, square |
| Balatonfőkajár | lightning, square, arrow | lightning, hourglass, square |
| Balatonföldvár | square, lightning, diamond | lightning, hourglass, square |
| Balatonfüred | square, lightning, diamond | lightning, hourglass, square |
| Balatonfűzfő | square, diamond, arrow | square, diamond, clover |
| Balatongyörök | square, diamond, octagon | square, diamond, octagon |
| Balatonkenese | square, diamond, arrow | square, diamond, clover |
| Balatonkeresztúr | square, diamond, lightning | lightning, fox, square |
| Balatonlelle | square, lightning, diamond | lightning, hourglass, square |
| Balatonmáriafürdő | square, diamond, lightning | lightning, fox, square |
| Balatonőszöd | square, diamond, lightning | lightning, fox, square |
| Balatonrendes | square, clover, diamond | square, clover, diamond |
| Balatonszabadi | square, lightning, diamond | lightning, hourglass, square |
| Balatonszárszó | square, diamond, lightning | lightning, fox, square |
| Balatonszemes | square, lightning, diamond | lightning, hourglass, square |
| Balatonszentgyörgy | square, diamond, lightning | lightning, fox, square |
| Balatonszepezd | square, diamond, arrow | square, diamond, clover |
| Balatonudvari | square, diamond, arrow | square, diamond, clover |
| Balatonvilágos | square, diamond, lightning | lightning, fox, square |
| Csopak | square, diamond, arrow | square, diamond, clover |
| Fonyód | square, diamond, octagon | square, diamond, octagon |
| Gyenesdiás | square, lightning, diamond | lightning, hourglass, square |
| Keszthely | square, lightning, diamond | lightning, square, hourglass |
| Kővágóörs | square, diamond, arrow | square, diamond, clover |
| Örvényes | square, clover, diamond | square, clover, diamond |
| Paloznak | square, clover, diamond | square, clover, diamond |
| Révfülöp | square, diamond, arrow | square, diamond, clover |
| Siófok | square, lightning, diamond | lightning, square, hourglass |
| Szántód | square, diamond, lightning | lightning, fox, square |
| Szigliget | square, clover, diamond | square, clover, diamond |
| Tihany | square, clover, diamond | square, clover, diamond |
| Vonyarcvashegy | square, diamond, octagon | square, diamond, octagon |
| Zamárdi | square, lightning, diamond | lightning, hourglass, square |
| Zánka | square, diamond, arrow | square, diamond, clover |

The shortlist stays deliberately conservative in small shore settlements.
[Li and Fu's road-graphic retrieval study](https://doi.org/10.3390/ijgi15030098)
found that turning relations and
segment-length proportions help reject deformed matches; adding more ornate
templates without enough connected street detail would work against those
constraints. The application's final scorer therefore measures turns, extent,
relative lengths, coverage, and collapse rather than accepting this prior list
without graph evidence.

## Regression coverage

Backend tests require all 45 names to be unique, locally geocodable, individually
profiled, backed by explicit numeric route priors, and available to deterministic
intent parsing. The recommendation audit includes all 124 unique destinations.
Playwright verifies the three
labelled picker groups, the single Siófok option, accented Balaton selection,
and the exact generated request.

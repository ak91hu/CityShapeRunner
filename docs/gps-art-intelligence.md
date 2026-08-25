# GPS Art Intelligence

GPS Art Wizard adds connected, GPS-art-specific layers around route generation.

## Street Canvas

The placement preflight already measures many nearby transforms. The API exposes
the strongest non-duplicate locations as `street_canvas`, including street
support, outline proxies, readability score, and map position. The route map
marks the strongest areas before the user commits to an export.

## Recognition repair

`POST /recognition-repair` uses the most salient points of the authored guide
as a reduced set of visual anchors, then routes through them again. It is a
bounded alternative to the existing AI geometry repair: it changes route
guidance only after street snapping has weakened the visible outline.

## Community GPS mural

`POST /mural-plan` splits one continuous route by travelled distance. Each
participant receives a contiguous GPX section, so the completed group activity
reconstructs the source drawing without arbitrary jumps between sections. The
result page exposes the split as "Make it together" and completes the loop with
"Combine finished runs": the Missing Ink rescue below now accepts the group's
finished GPX files in the browser, scores how much of the drawing is covered,
and exports one honest combined track plus a separate missing-ink mission.

## Night-run readiness

`POST /night-readiness` answers a question night-running clubs actually have:
which parts of this drawing are lit, and how much car traffic do they cross?
The route's bounding box is queried against a public Overpass mirror for
highways with an explicit `lit` tag. Samples every ~25 m are matched to their
nearest tagged segment and aggregated into lit/unlit/unknown shares, a
class-weighted traffic-exposure score, and up to six mappable unlit stretches
that reuse the readiness-concern overlay. Lookups are cached per bounding box,
degrade to `available: false` on any outage, and never claim safety: tags are
volunteer-maintained and can be stale.

## Sightseeing landmarks

`POST /route-landmarks` lists named OpenStreetMap attractions within ~90 m of
the planned line, ordered by kilometre offset, so a GPS drawing doubles as a
sightseeing programme. Hits render as purple map markers with tooltips and a
numbered list in the route lab. The lookup is best effort and says so when the
context service is unavailable.

## Occasion catalogue and gift poster

`GET /occasions` returns date-aware drawing suggestions: Hungarian national
days (15 March cockade, 20 August wheat, 23 October flame) sit next to
computable movable feasts (Western Easter, Mother's/Children's/Father's Day,
first Advent) and international dates. Every suggestion maps to an existing
template name, so picking an occasion fills the normal prompt and the request
takes the deterministic fast path. The result page turns any street-routed
route into a printable gift poster: a captured map image, an optional
dedication, route facts, and OpenStreetMap attribution, printed through a
dedicated print stylesheet that hides the application chrome. Nothing about a
poster is stored server-side.

## Time-aware readiness

`POST /timed-readiness` combines a conservative solar-altitude calculation
with the requested departure time and an optional Open-Meteo hourly forecast.
The external weather lookup is best effort. If it is unavailable, daylight and
the explicit reminder to check closures and local access rules remain visible.

## Inkproof GPS forecast

`POST /inkproof-analysis` tests the selected route against 24 deterministic,
correlated drift simulations at a user-selected 5 m, 10 m, or 20 m accuracy
profile. It also measures tight non-adjacent strokes and corners that may be
rounded off. The response contains an expected recognition score, an overall
resilience score, and up to eight map-ready fragile sections.

The forecast is deliberately an estimate, not a device guarantee. GPS.gov says
a smartphone is typically accurate within a 4.9 m radius under open sky and
that accuracy worsens near buildings, bridges, and trees. Those conditions are
why the interface presents multiple profiles and practical recording advice
instead of one universal claim.

Source: [GPS.gov — GPS Accuracy](https://www.gps.gov/index.php/gps-accuracy-0).

## Multi-session Missing Ink rescue

`POST /art-rescue` accepts one to twelve completed GPX files and compares them
with the selected routed artwork. It reports planned-line coverage, recorded
line precision, and their harmonic art-match score. Missing runs are returned
as map overlays, individual GPX files, and one segmented repair pack. The
result page now exposes this as "Combine finished runs" next to the mural
splitter, completing the group workflow: split the drawing, run the sections,
upload the recordings, and hand every artist either the combined track or a
missing-ink mission.

The combined export keeps each source track segment separate. A gap between
two activity files is therefore a real GPX “pen-up” gap, not a fabricated line
from the finish of one day to the start of another. Uploaded strings are parsed
and analysed in memory and are neither written to disk nor published.

This addresses a repeated workflow documented by activity users: Strava does
not merge activities directly, so people otherwise download, combine, and
re-upload files using separate tools. Missing Ink deliberately does no silent
reconstruction. Its combined file contains only points that were actually
recorded; the uncovered artwork becomes a separate, untimed course for a
future physical repair activity.

Sources: [Strava community example](https://www.reddit.com/r/Strava/comments/so9tu8/merging_activities/),
[Footpath pricing and feature comparison](https://footpathapp.com/pricing/),
[plotaroute feature list](https://www.plotaroute.com/mobile/routefinder), and
[Strava route-builder documentation](https://support.strava.com/en-us/articles/15401971-routes-on-web),
[GpxFix reference-route repair](https://www.gpxfix.eu/restoring-missing-gps),
and [GPX Rescue tools](https://gpxrescue.eu/en/).

## Product boundary

The researched mainstream tools already cover waypoint planning, route
preferences, cue sheets, navigation, generic GPX import/export, route merging,
and image overlays. GPS Art Wizard does not present those as unique. Its niche
is measuring what survives as a recognisable drawing. Inkproof is free,
accountless, and uses the route data already present in the result page.
Missing Ink, the mural split, the night-run check, the sightseeing list, and
the occasion catalogue are all exposed in the result page or prompt composer;
none of them requires an account, and the group workflow stores nothing
server-side.

These layers do not claim that a route is safe, open, or suitable in all
conditions. They provide transparent planning evidence and keep the final
local decision with the person doing the activity.

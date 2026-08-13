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
reconstructs the source drawing without arbitrary jumps between sections.

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
as map overlays, individual GPX files, and one segmented repair pack.

The combined export keeps each source track segment separate. A gap between
two activity files is therefore a real GPX “pen-up” gap, not a fabricated line
from the finish of one day to the start of another. Uploaded strings are parsed
and analysed in memory and are neither written to disk nor published.

This addresses a repeated workflow documented by activity users: Strava does
not merge activities directly, so people otherwise download, combine, and
re-upload files using separate tools. Generic planners can merge routes—often
inside paid tiers—and specialist GPX repair tools can synthesize missing
historic points from a reference route. Missing Ink deliberately does neither
kind of silent reconstruction. Its combined file contains only points that
were actually recorded; the uncovered artwork becomes a separate, untimed
course for a future physical repair activity. The reviewed products did not
advertise that GPS-art-aware “finish it honestly” workflow or a pre-activity
recognition-resilience forecast. That market-gap statement is an inference
from public product documentation reviewed on 2026-08-13, not a permanent
exclusivity claim.

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
accountless, and uses the route data already present in the result page. The
experimental Missing Ink endpoint is API-only and is not exposed in the user
interface.

These layers do not claim that a route is safe, open, or suitable in all
conditions. They provide transparent planning evidence and keep the final
local decision with the person doing the activity.

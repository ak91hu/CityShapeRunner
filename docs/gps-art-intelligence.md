# GPS Art Intelligence

GPS Art Wizard adds four connected layers around route generation.

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

These layers do not claim that a route is safe, open, or suitable in all
conditions. They provide transparent planning evidence and keep the final
local decision with the person doing the activity.

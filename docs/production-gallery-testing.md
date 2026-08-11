# Production GPS-art gallery test

## Purpose

This suite exercises the deployed planner rather than a mocked/local backend.
It submits a curated set of recognisable route ideas, evaluates every returned
candidate, and can publish only candidates that satisfy an additional visual
quality contract. It also verifies that each returned gallery asset is present
in the live album after upload.

The suite is deliberately excluded from ordinary CI behaviour. It consumes
real routing capacity and publishing changes external state.

## Safety switches

`RUN_PROD_GALLERY=1` enables live generation and read-only gallery checks.
Without it, every production test is skipped.

`PROD_PUBLISH_GALLERY=1` additionally permits live publication. Without this
second switch, the suite measures candidates but does not change the album.

The default target is two accepted routes. Override it with
`PROD_GALLERY_TARGET_COUNT`. The default deployed URL can be changed with
`PROD_BASE_URL`.

PowerShell example for a non-mutating production check:

```powershell
$env:RUN_PROD_GALLERY='1'
npm run test:prod-gallery
```

Explicit live publication:

```powershell
$env:RUN_PROD_GALLERY='1'
$env:PROD_PUBLISH_GALLERY='1'
$env:PROD_GALLERY_TARGET_COUNT='2'
npm run test:prod-gallery
```

Run these commands from `frontend/`. Remove the environment variables after
the run if the shell will be reused.

## Quality contract

A candidate is publishable only when all of the following are true:

- Directions returned a connected street route;
- the candidate still represents the requested shape;
- overall score is at least 0.78 and combined likeness at least 0.75;
- ordered curve, outline coverage, and proportion measures are each at least
  0.70;
- the no-backtracking measure is at least 0.44, which permits one measured
  network-forced reversal only when all stronger global-shape checks pass;
- characteristic-turn and detour-control measures are each at least 0.55;
- salient-landmark preservation is at least 0.65;
- distance fit is at least 0.60; and
- a closed drawing's closure score is at least 0.60.

These thresholds are intentionally stricter than accepting an arbitrary
road-routed preview. The two lower component floors accommodate visible street
stair-stepping and unavoidable network detours only when the combined likeness,
ordered curve, coverage, proportions, and backtracking checks remain strong. A
route that meets this curation contract but narrowly misses one automatic
application gate receives the same explicit approval a human gallery publisher
would provide before the screenshot is uploaded. Every accepted route also
produces a Playwright map-card screenshot attachment for visual audit.

## Custom cases

`PROD_GALLERY_CASES_JSON` accepts a non-empty JSON array. Each entry needs a
stable name and complete prompt. Explicit-shape cases also provide the expected
canonical shape. Suggestion cases omit `shape`; the suite then binds identity
to the production planner's selected shape and does not allow a different
candidate to slip into the album:

```json
[
  {
    "name": "heart-budapest",
    "prompt": "a heart run in Budapest, 8 km",
    "shape": "heart"
  }
]
```

The suite stops after the target number of accepted routes, limiting both ORS
work and accidental album growth. Its final diagnostic JSON records accepted
scores and explains why the strongest rejected candidates were not published.
After upload it polls the gallery for up to 90 seconds because Cloudinary's
search index can lag behind a successful image-upload response.

## Gallery viewer regression

The regular mocked browser suite separately verifies that the lightbox image
fills a bounded media frame with `object-fit: contain`, centred positioning,
and no stage overflow. This protects the complete image at landscape, portrait,
desktop, and mobile sizes without changing the album's list view.

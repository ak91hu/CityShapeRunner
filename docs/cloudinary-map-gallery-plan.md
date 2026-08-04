# Cloudinary map gallery implementation record

Status: implemented. This document records the shipped privacy boundary,
architecture, regression coverage, and operational requirements.

## Outcome

Publish an anonymous, image-only gallery of generated GPS art. Each gallery
asset is a PNG of the rendered street map, including readable street names,
the selected route overlay, and visible OpenStreetMap attribution. Cloudinary
stores and indexes the images; the application does not add a gallery
database or persist prompts, workflow state, route coordinates, or user
identity alongside the image.

## Privacy boundary

- Publication is opt-in and requires confirmation that the exact mapped area
  and street names will become public.
- The captured PNG contains only the visible map, route line, start/finish
  markers, and `© OpenStreetMap contributors` attribution.
- Do not include the prompt, route title, city field, request/debug ID, account
  identifier, GPX/TCX data, or browser metadata.
- Browser canvas export creates the PNG, and the API removes known PNG text,
  EXIF, and timestamp chunks before upload.
- Gallery API logs contain a random Cloudinary public ID and operation outcome,
  never image bytes, publish/removal tokens, prompts, or route coordinates.

The image itself intentionally discloses location through the map and street
labels. “Anonymous” therefore means that the application does not associate
the public image with a person; it does not mean that the mapped place is
hidden.

## Architecture

1. `/generate` returns a short-lived, signed gallery publish token for each
   road-routed candidate when Cloudinary is configured.
2. The result map loads OpenStreetMap tiles normally in the user's browser.
3. After explicit confirmation, the browser captures the already-visible map
   tiles and redraws the selected route into a PNG canvas. It does not run a
   headless map scraper or prefetch additional areas.
4. `POST /gallery` verifies the publish token, validates and sanitises the PNG,
   then performs a signed Cloudinary upload under the
   `gps-art-gallery/<random-id>` public-ID prefix.
5. `GET /gallery` uses Cloudinary's asset search as the gallery index, sorted
   newest first. The response exposes only public delivery fields.
6. The upload response includes a stateless removal token. The browser may
   retain it locally; `POST /gallery/delete` verifies it before issuing a
   signed Cloudinary destroy request.

## Backend implementation

- Parses `CLOUDINARY_URL` without logging it and treats masked/template secrets
  as unconfigured.
- Uses HMAC publish and removal capabilities derived from the Cloudinary
  secret, with bounded token lifetime and constant-time verification.
- Validates PNG signature, dimensions, pixel count, and encoded size; strips
  metadata chunks before upload.
- Implements signed Cloudinary upload, search, and deletion calls using the
  existing HTTP client dependency.
- Exposes `/gallery`, `/gallery/delete`, and gallery configuration status on
  `/health` without exposing credentials.
- Keeps route generation and GPX download independent of gallery availability.

## Frontend implementation

- `RouteMap` provides a dependency-free capture method that composites the
  visible, CORS-enabled OSM tiles with the active route and attribution.
- Publication requires explicit location consent and exposes
  progress/error/success states in the result panel.
- The anonymous gallery uses responsive map-image cards, pagination,
  OSM attribution, empty/error states, and removal controls only when the
  browser holds the matching removal token.
- It never sends prompts, city labels, request IDs, or route coordinates to the
  gallery endpoints.

## Regression coverage

- Unit tests cover configuration parsing, token expiry/tampering, PNG
  sanitisation, signed upload payloads, search response filtering, and removal
  authorization.
- API tests cover unconfigured, invalid-consent, invalid-token, upload,
  listing, and removal paths without contacting Cloudinary.
- Browser tests cover gallery loading, publication confirmation, PNG upload,
  gallery refresh, and responsive layout with all third-party requests mocked.
- Release verification runs Python lint/tests, the frontend production build,
  and Playwright tests.

## Operational checklist

- Set the real `CLOUDINARY_URL` only in local/hosting secrets. Never commit it.
- Keep the API secret server-side; frontend uploads always go through FastAPI.
- Preserve visible OSM attribution in every PNG and on the gallery page.
- Monitor Cloudinary free-plan credit usage and Admin/Search API limits.
- Provide an operator moderation/deletion path through the Cloudinary console.

# GPS Art Managed Next.js Web Application Specification

## 1. Document Purpose

This document specifies two related features for a GPS art application:

1. **Shape Search Within a City**: Given a city and a target shape, find one or more routes on real streets that resemble the shape.
2. **City Recommendation for a Shape**: Given a target shape, recommend cities in which a route resembling that shape can be completed on real streets.

All returned routes must be derived from verifiable, current street-network data. The application must never fabricate roads, connectors, or route geometry to improve a visual match.

The product must be a polished, responsive web application implemented with Node.js, Next.js, React, and TypeScript. The browser user interface, server-side application layer, background workflows, and managed cloud integrations must preserve the validation, provenance, and export rules in this document.

The production application must call a managed routing API and treat that API's successful route response as the sole authority for navigable geometry. Shape-search code may propose coordinates or waypoints, but those proposals are not routes and must never be displayed, navigated, or exported as GPX.

Self-hosted routing engines, databases, queues, object stores, geocoders, map-tile servers, and production application servers are outside the approved architecture. The reference deployment uses managed cloud services with documented production terms, authentication, quotas, monitoring, and availability commitments.

### 1.1 Non-Negotiable Route Integrity Principle

A route plan exists only after all of the following are true:

1. The application submitted an auditable request to the configured routing provider.
2. The provider returned a successful route response.
3. The response contains a continuous route geometry and valid legs for the requested waypoints.
4. The application stored the original response, request parameters, provider identity, profile, and integrity hash.
5. The route passed the validation rules in this document.
6. Any GPX export was generated directly from the stored provider geometry without geometric modification.

If any condition is not met, the system must return `no_result`, `provider_unavailable`, or `validation_failed`. It must not construct a plausible-looking replacement.

A provider-validated route means that the configured managed routing API returned the route for the requested travel profile. It does not prove physical inspection or real-time existence. The application must fail closed when provider evidence conflicts with approved water, building, access, or freshness evidence.

### 1.2 Normative Language and Section Precedence

- **Must**, **must not**, and **required** define release-blocking requirements.
- **Should** defines the default implementation unless a documented architecture decision explains the exception.
- **May** defines optional behavior.
- Provider contracts and legal terms override examples, version tables, and reference-service suggestions.
- Sections 1.1, 6.4, 6.5, 6.12, and 12.8 are the authoritative route-integrity rules.
- Section 6.7 is the authoritative candidate-route state model.
- Sections 12.3, 12.9, and 12.10 are the authoritative search-status and failure-code model.
- Sections 23 through 33 specialize the earlier platform-neutral requirements for the reference Next.js implementation. If duplicated requirements differ, the stricter route-integrity rule applies and the discrepancy must be resolved before implementation.
- Examples are non-normative unless explicitly labeled as required.

## 2. Product Goals

- Enable users to create recognizable GPS art using legal, traversable routes.
- Produce routes that balance shape similarity with practical navigation.
- Explain why a route or city was recommended.
- Clearly distinguish verified route segments from uncertain or restricted segments.
- Keep results reproducible by recording the street-data version and routing parameters used.
- Expose all user workflows through the web interface and authenticated server APIs.
- Provide a modern, visually refined, accessible interface across desktop, tablet, and mobile.
- Support resumable, bounded searches through managed background workflows.
- Provide live progress without requiring the browser tab to remain open.

## 3. Non-Goals

- Generating routes over imaginary streets or interpolated gaps.
- Guaranteeing personal safety or real-time accessibility.
- Replacing official traffic, closure, weather, or emergency information.
- Supporting off-road drawing unless a separately verified pedestrian, cycling, or trail network is enabled.
- Guaranteeing an exact geometric reproduction of every input shape.
- Using straight-line connections between disconnected route segments.
- Creating a GPX track from the target-shape polyline.
- Creating a GPX track from snapped waypoints without a successful routing response.
- Joining multiple provider routes with synthetic coordinates.
- Smoothing, warping, rotating, scaling, or otherwise changing provider route geometry.
- Treating a visual map overlay as a navigable route.
- Claiming that automated validation proves temporary closures, construction, surface condition, personal safety, or physical accessibility.
- Claiming a mathematically global optimum when the search evaluated only a bounded candidate set.

## 4. Definitions

| Term | Definition |
|---|---|
| Target shape | User-provided text, icon, SVG, drawing, or image converted into normalized line geometry. |
| Street-feature model | A temporary analysis abstraction built from managed-provider road features and nearest-road results. It is not a hosted routing graph and cannot produce canonical route geometry. |
| Candidate route | A successfully returned provider route that has not yet completed all application validation. |
| Shape similarity | A numerical measure of how closely a route's geometry resembles the target shape after allowed transformations. |
| Feasibility | Whether the route can be navigated using the selected travel mode and constraints. |
| Stroke | One continuous line in the target shape. |
| Connector | A real, routable path used to travel between target-shape strokes. |
| Route trace | The ordered geographic coordinates returned by the managed routing provider. |
| Data snapshot | Managed-provider source, retrieval timestamp, region, and version identifiers used in a search. |
| Waypoint proposal | Coordinates selected by the shape-search algorithm for submission to a routing API. It is not a route. |
| Provider route | A route returned successfully by the configured routing API. |
| Provider geometry | The exact route geometry returned by the provider for a provider route. |
| Route provenance | The immutable records proving which provider request and response produced a route. |
| Export gate | The validation component that permits GPX generation only for a verified provider route. |
| Obstacle evidence | Managed-provider water, building, access, bridge, tunnel, ferry, and routable-feature metadata used only to reject questionable provider routes, never to create or alter geometry. |

## 5. Supported Inputs

### 5.1 Shape Inputs

The application should support:

- Freehand drawing.
- SVG path or uploaded SVG file.
- A supported icon from an application-managed catalog.
- Text converted to vector outlines using an application-approved font.
- Raster image converted to line geometry after user confirmation.

The shape-processing pipeline must:

1. Remove irrelevant metadata.
2. Convert the input into one or more polylines.
3. Preserve the original vector vertices and create adaptive high-density samples along every stroke.
4. Identify disconnected strokes.
5. Normalize the shape into a coordinate system independent of location and scale.
6. Present the interpreted shape to the user before an expensive search.

Raster-to-vector conversion may infer shape geometry, but it must not infer or fabricate street data.

### 5.2 City Inputs

A city input must resolve to:

- A stable geographic identifier where available.
- Display name, country, and administrative region.
- A typed search area: a provider-supported boundary polygon when available, otherwise a provider-returned bounding box.
- Searchable routing area, including an optional configurable buffer around the boundary.
- Coordinate reference information.

The search-area type and source must be stored and shown to the user. A bounding box must never be presented as an exact municipal boundary. Cities without either an approved polygon or a usable provider bounding box are not searchable.

Ambiguous city names must require user selection, for example:

- Paris, France
- Paris, Texas, United States

### 5.3 Travel Modes

Initial travel modes:

- Walking.
- Cycling.
- Driving.

Each mode must use a distinct routing profile. A segment available to one mode must not automatically be treated as available to another.

Optional future modes:

- Wheelchair-accessible routing.
- Running.
- Hiking or verified trail routing.

### 5.4 Shape Point Density Requirements

The application must use as many **meaningful shape points** as practical to maximize route-shape accuracy. It must not reduce a detailed curve to only a few corners when additional points can be routed within provider and compute limits.

Two different point sets must remain separate:

1. **Shape sample points** describe the desired drawing and may be very dense.
2. **Routing waypoints** are the selected subset submitted to the managed routing provider.

Shape sample points are never route coordinates. GPX coordinates come only from provider geometry.

The shape sampler must:

- Preserve every original SVG path vertex, endpoint, corner, cusp, intersection, and stroke boundary.
- Sample curved segments more densely than straight segments.
- Add points at changes in tangent direction and curvature.
- Use adaptive subdivision until the curve-to-sample deviation is below a configurable tolerance.
- Keep the full-resolution sample set for shape scoring.
- Remove only exact duplicates, numerical noise, and redundant collinear points that do not exceed the documented geometric-error tolerance.
- Record source point count, sampled point count, sampling tolerance, and sampler version.

The system should create multiple resolution levels:

- Coarse points for rapid city or neighborhood screening.
- Medium-density points for candidate placement.
- High-density points for final waypoint refinement and shape scoring.
- Original/full-resolution points for visual comparison and audit.

Final shape scoring must always use the high-density target sample set. Routing requests must use the highest useful waypoint count permitted by the selected provider, but route fidelity remains bounded by that provider's single-request limit. A lower-resolution screening result must never be shown as a final validated route.

### 5.5 Adaptive Routing Waypoint Selection

Routing waypoints must be selected from, or be traceably derived from, high-density shape samples. Selection priority must be:

1. Stroke endpoints.
2. Sharp corners and cusps.
3. Shape intersections.
4. High-curvature regions.
5. Inflection points.
6. Long segment subdivisions.
7. Additional evenly distributed points.

The waypoint selector must maximize retained shape detail subject to:

- The configured managed-provider maximum waypoint count.
- Request URL and reverse-proxy limits.
- Provider profile restrictions.
- Search-time and rate limits.
- Minimum useful spacing between provider-snapped waypoints.

Provider limits must be discovered from deployment configuration or explicitly configured. The application must not guess that an arbitrary number of waypoints is supported.

If the full point set exceeds the provider limit, the system must:

1. Keep all mandatory landmarks where possible.
2. Apply error-bounded adaptive reduction.
3. Report the retained point count and maximum introduced shape deviation.
4. Generate multiple complete waypoint variants when different subsets may preserve different details.
5. Submit every variant as a complete provider request.
6. Never split the shape into route fragments and stitch the responses together.

Selecting a higher managed-provider waypoint tier is permitted after cost, latency, quota, and reliability testing. Provider limits must never be bypassed by splitting and stitching routes.

The application must communicate that adding shape sample points improves measurement precision but does not create additional routing control points beyond the provider limit. If a shape cannot achieve the minimum similarity within one complete provider request, it must return no result or use another approved managed provider with a higher documented limit.

## 6. Authoritative Street and Routing Data

### 6.1 Data Sources

The implementation must use a real-world street source such as:

- OpenStreetMap data with attribution and licensing compliance.
- A licensed commercial street-data provider.
- An authoritative municipal open-data source.

The reference implementation must use a fully managed routing and mapping provider. Mapbox Directions, a managed GraphHopper Directions API plan, HERE Routing, Google Routes, or another licensed managed service may implement the provider contract.

The primary reference stack uses Mapbox for interactive maps, geocoding/search, and Directions API routing. A managed provider backed by OpenStreetMap may be selected when explicit OSM provenance is a product requirement.

The public OSRM demonstration service is prohibited for production because it is not a managed application dependency with an application-specific service agreement, quota, or availability guarantee. Running OSRM, GraphHopper, Valhalla, Nominatim, Overpass, PostgreSQL, Redis, or map-tile infrastructure on application-managed servers is also prohibited.

### 6.2 Data Freshness

Every search result must record:

- Data provider.
- Dataset or map version when available.
- Provider data-version or retrieval timestamp.
- Routing engine and profile version.
- Search timestamp.

The production system should refresh application-owned derived indexes at least daily where provider terms and capabilities support it. The application does not claim to ingest or control the managed provider's underlying map updates.

The user interface must show:

- The provider data version or source-data timestamp when the provider exposes it.
- Otherwise, the provider route-response timestamp and a clear `provider data version unavailable` label.

The application must never fabricate a source-data date from the request date.

If data exceeds the configured freshness threshold, the system must:

- Mark results as based on stale data.
- Avoid describing the route as currently verified.
- Withhold route geometry and export until a fresh provider route passes validation.
- Refresh application-owned derived indexes when they are stale and refresh is permitted.

### 6.3 Routing Provider as Route Authority

The routing provider is the sole authority that may turn waypoint proposals into route plans.

The managed provider adapter may use:

- A nearest-road service to resolve a proposed coordinate when needed.
- A directions service to calculate a route through an ordered waypoint sequence.
- A map-matching service only for genuine recorded GPS traces, not to invent a route from a target drawing.
- A matrix service only for travel-time or distance screening, never as route geometry.

The exact endpoints and supported options must be configured per managed provider. Directions requests must request full route geometry at sufficient precision for GPX export and should request route steps when maneuver validation or user instructions are required.

Provider success must be determined from both:

- A successful HTTP response.
- A provider-level success status documented by the managed service.

An HTTP 200 response containing a provider error, no routes, malformed geometry, or incomplete legs is not a valid route.

### 6.4 No-Fabrication Rule

Every coordinate in the navigable route must be traceable to:

- The exact geometry of one successful, stored provider route response.

The system must reject a candidate if:

- It contains a straight-line gap between disconnected roads.
- It was not returned by the configured routing provider.
- The provider request or original response is missing.
- The stored response integrity hash does not match.
- The provider returns no route or a non-success status.
- The returned leg count is inconsistent with the submitted waypoint sequence.
- The provider geometry is empty, malformed, non-finite, or outside valid longitude/latitude ranges.
- A segment violates the selected travel-mode access rules.
- It crosses a water body without provider evidence of a mode-compatible bridge, tunnel, or explicitly allowed ferry.
- It intersects a building footprint beyond the configured map-alignment tolerance without corroborated provider evidence of a public, mode-compatible mapped passage.
- Provider route evidence conflicts with approved obstacle or access evidence and the conflict cannot be resolved automatically.
- A required connector exists only in the target-shape geometry.
- The geometry was visually adjusted away from the underlying route.
- Coordinates from separate provider responses were concatenated without provider routing across the join.
- A GPX file contains coordinates not present in the canonical stored provider geometry, except representation-preserving numeric formatting.

Rendering simplification is permitted only for non-navigational display layers. The canonical route, navigation, distance calculations, validation, and GPX export must use the unmodified provider geometry.

Obstacle evidence is a conservative rejection layer. It must never move, trim, bridge, snap, or repair provider geometry.

### 6.5 Forbidden Route Construction Operations

The following operations are forbidden for canonical routes and GPX exports:

- Drawing lines directly between target-shape sample points.
- Drawing lines directly between snapped waypoints.
- Filling missing geometry by interpolation.
- Using the target SVG or raster outline as track points.
- Moving route points to improve shape similarity.
- Removing inconvenient route portions.
- Smoothing corners.
- Resampling in a way that changes the path.
- Combining route fragments without obtaining one provider-confirmed route covering the complete ordered journey.
- Falling back to cached geometry from a different map version, routing profile, or waypoint request.
- Returning a successful result after a routing timeout, parse failure, or validation failure.

### 6.6 Provider Request and Response Provenance

For every candidate submitted to the routing provider, store:

- Internal candidate ID.
- Provider name and deployment identifier.
- Provider API version where available.
- Routing profile.
- Complete ordered waypoint list at provider precision.
- All route-affecting query options.
- Request timestamp.
- Sanitized request URL or canonical request document.
- HTTP status.
- Provider status code and message.
- Original provider response body or immutable object-storage reference for no longer than the approved provider-policy retention period.
- Cryptographic response hash, using SHA-256 or stronger.
- Managed-provider map-data version or retrieval identifier.
- Parsed route index if the response contains alternatives.
- Geometry encoding and precision.
- Validation status and rejection reasons.

Secrets, API keys, and authorization headers must not be stored in provenance records.

After a provider response expires under its policy, the system may retain permitted request metadata and non-reversible hashes, but the route must become non-exportable until a fresh provider response passes validation.

### 6.7 Route State Machine

A candidate route version may use these states:

1. `waypoint_proposal`
2. `provider_request_pending`
3. `provider_response_received`
4. `provider_route_parsed`
5. `provider_route_validated`
6. `eligible_for_display`
7. `eligible_for_gpx_export`
8. `provider_data_expired`
9. `revalidation_pending`
10. `rejected`
11. `retired`

Required transitions:

- The publication path is `waypoint_proposal` -> `provider_request_pending` -> `provider_response_received` -> `provider_route_parsed` -> `provider_route_validated` -> `eligible_for_display`.
- `eligible_for_gpx_export` is reached only after an on-demand export gate succeeds. It is not an automatic publication step.
- Any non-terminal state may transition to `rejected` after a provider, parsing, validation, provenance, or export-gate failure. A rejected version stores machine-readable rejection evidence and can never become eligible again.
- `eligible_for_display` or `eligible_for_gpx_export` transitions to `provider_data_expired` when validation or permitted geometry retention expires.
- `provider_data_expired` transitions to `revalidation_pending` when rerouting is requested.
- Revalidation creates a new route version. The old version remains expired or becomes `retired`; it is never mutated back into eligibility.
- `retired` is an administrative or retention terminal state and is distinct from `rejected`.

Code must not skip states or directly mark a waypoint proposal as displayable or exportable.

### 6.8 Routing Profile Integrity

- The requested user travel mode must map to one explicitly configured provider profile.
- A profile mismatch must fail the request.
- The profile name and version must be stored with the route.
- The application must not describe a driving route as walking or cycling.
- If the managed provider does not provide the requested mode, that mode must be unavailable.
- Updating a routing profile must invalidate incompatible cached route-verification records.
- Provider capabilities, profile names, waypoint limits, geometry formats, and rate limits must be configured from managed-provider documentation and verified by integration tests.
- The browser must never select or override a provider profile directly; server-side code maps the validated travel mode to an allowlisted provider profile.

### 6.9 Managed Directions Provider Contract

The reference implementation uses a managed Directions API. The provider adapter must submit the complete ordered waypoint proposal and request the highest-detail route geometry supported by the provider.

For Mapbox Directions, the server-side adapter should request GeoJSON geometry with full overview and route steps when needed. Equivalent options must be used for another managed provider.

The following rules apply:

- Provider credentials are server-only and must never be included in browser bundles.
- The waypoint order must represent the complete intended journey.
- Full-detail geometry must be requested for canonical geometry and GPX export.
- Encoded geometry may be used only when encoding type and precision are recorded.
- Provider alternatives are independent candidates and must not be combined.
- Optional waypoint radiuses, bearings, approaches, or curb-side constraints must be recorded.
- A closed loop must be returned as a routed journey by the provider.
- Browser-generated map lines, preview overlays, and client-side interpolation are never canonical routes.

A managed-provider response is valid only if:

1. The HTTPS request completed successfully.
2. The response body can be parsed and matches the provider schema.
3. The provider-specific status indicates success.
4. At least one route exists.
5. The selected route contains non-empty full geometry.
6. Waypoint and leg counts are consistent with the request.
7. Every coordinate is finite and geographically valid.
8. The geometry is one continuous provider-returned sequence.
9. Reported distance and duration are finite and non-negative.
10. Provider-snapped waypoints satisfy configured limits.
11. The response satisfies the requested managed-provider profile.

Nearest-road or map-matching endpoints may assist diagnostics only according to provider terms. A snapped point or matched target drawing is not a route and is never GPX-exportable.

### 6.10 Waypoint Snapping Rules

Routing providers may snap submitted waypoints to nearby roads. The application must:

- Preserve both proposed and provider-snapped coordinates.
- Record provider-reported snap distance where available.
- Calculate snap distance when the provider does not report it.
- Reject snaps beyond a configurable mode-specific threshold.
- Recalculate shape similarity using provider route geometry, not proposed or snapped waypoint geometry.
- Show materially moved waypoints in route diagnostics.
- Never move a waypoint in stored provenance after the request.

Default thresholds must be established through product validation and may differ for dense urban, rural, walking, cycling, and driving searches.

### 6.10.1 Water, Building, and Access Safety Gate

The reference implementation must enable a strict obstacle gate by default.

Before requesting a route:

- Waypoint proposals must be matched to a mode-compatible routable feature or accepted by a provider nearest-road capability.
- A waypoint inside a water or building polygon must be rejected unless provider feature metadata identifies a compatible bridge, tunnel, or public mapped passage.
- Candidate generation must not use open water, building interiors, private parcels, or visual gaps as shortcuts.

After receiving a provider route:

1. Load obstacle evidence from an approved managed API or licensed provider dataset compatible with the route's region and freshness policy.
2. Intersect the canonical provider geometry with water and building polygons using a documented map-alignment tolerance.
3. For every water intersection, require provider or managed-road-feature evidence of a bridge, tunnel, or user-allowed ferry for the selected mode.
4. For every building intersection, require provider or managed-road-feature evidence of a public, mode-compatible passage. Ordinary building interiors always fail.
5. Reject private, restricted, or mode-incompatible segments when reliable access metadata identifies them.
6. Reject the route when required obstacle evidence is missing, stale, contradictory, or too imprecise for the configured strictness level.
7. Store evidence source, version or retrieval timestamp, tolerance, detected intersections, exemptions, and rejection reasons.

Ferries must be disabled by default. When the user explicitly enables ferries, a provider-returned ferry leg is a real routed segment but must be labeled clearly and scored as a connector rather than as street-shape coverage.

Bridges and tunnels may geometrically cross water because the traversable route is above or below it. The UI must display the exact provider geometry and the structure classification; it must not draw a land-like replacement line.

### 6.11 Canonical Route Geometry

For each selected provider alternative, the system must store:

- The original response while provider policy permits retention.
- The provider route index.
- The exact geometry payload.
- Geometry format and precision.
- The decoded ordered coordinate sequence.
- Coordinate count.
- Bounding box.
- Provider-reported distance and duration.
- Leg and waypoint counts.
- Integrity hashes for the original response and canonical decoded representation.

Shape similarity, boundary checks, loop checks, retracing calculations, display, navigation, and GPX export must all reference this same canonical route record.

### 6.12 Automatic Route Validation Gate

Route validation must be fully automatic. No route may depend on a developer, administrator, or user visually deciding that it "looks real."

Every provider route must pass publication stages 1 through 8 before display:

1. **Request validation**
   - Managed-provider account, API version, and profile are approved.
   - Waypoint count is within configured limits.
   - Coordinates are finite, ordered, and within the approved search area.
   - Required constraints are present.

2. **Response validation**
   - HTTP and provider statuses indicate success.
   - The response schema, route, legs, waypoints, and full geometry are present.
   - Response and canonical-geometry hashes are stored.

3. **Geometry validation**
   - Geometry decoding succeeds at the declared precision.
   - Coordinates are finite and geographically valid.
   - The coordinate sequence is non-empty and continuous as returned by the provider.
   - No locally generated point has entered canonical geometry.
   - Start, end, and closed-loop rules are satisfied using provider geometry.

4. **Routing validation**
   - Requested and returned routing profiles agree.
   - Leg count agrees with ordered waypoints.
   - Provider-snapped waypoints satisfy snap-distance limits.
   - Provider distance and duration are valid.
   - Route annotations are internally consistent where available.

5. **Constraint validation**
   - The typed city search area and user-approved buffer are respected.
   - Distance, duration, retracing, connector, and travel-mode constraints pass.
   - Forbidden road or path classes are absent when reliable provider annotations support the check.
   - The strict water, building, and access gate in Section 6.10.1 passes.

6. **Shape validation**
   - Similarity is recalculated from full provider geometry against the high-density target sample set.
   - Required shape coverage and minimum similarity thresholds pass.
   - Missing strokes, excessive extra route geometry, and topology mismatches are measured.

7. **Provenance validation**
   - Original request and response are present.
   - Provider, profile, provider data version, route index, options, and hashes agree.
   - The route state transition history is complete.

8. **Publication validation**
   - All prior stages passed.
   - Validation occurred within the configured freshness period.
   - The route is atomically promoted to `eligible_for_display`.

The following stage runs only when GPX export is requested:

9. **Export validation**
   - Provenance and freshness are checked again.
   - Stale routes are rerouted and revalidated before export.
   - The generated GPX is reparsed and compared with canonical provider geometry.
   - Only then is the route promoted to `eligible_for_gpx_export`.

A publication-stage failure must produce a machine-readable rejection reason and prevent display, recommendation, navigation, and export. An export-stage failure must produce no downloadable file; it rejects that export attempt and may reject or expire the route version when provenance or freshness is no longer valid.

### 6.13 Validation Freshness and Automatic Revalidation

Validation freshness must be configurable by environment and provider. The system must:

- Store `validatedAt` and managed-provider data-version metadata.
- Automatically revalidate when the route exceeds the time-based freshness period.
- Automatically revalidate before GPX export when the provider data or routing profile changed.
- Re-submit the complete waypoint request when fresh provider routing is required.
- Treat a changed provider route as a new candidate with new provenance and scores.
- Invalidate the old route if the fresh route fails constraints or shape thresholds.
- Never continue serving an old GPX as current after its source route has been invalidated.

If automatic revalidation cannot complete, the route must be unavailable rather than labeled verified.

Provider data-version change detection is capability-dependent. When a provider does not expose a reliable version or change signal, freshness and revalidation must be based on `validatedAt`, the configured maximum validation age, profile/configuration changes, and explicit policy changes. The `provider/data-version.changed` workflow must not be simulated for such providers.

## 7. Common User Configuration

Users may configure:

- Travel mode.
- Desired route-distance range.
- Maximum duration.
- Start and end behavior:
  - Closed loop.
  - Same start and finish.
  - Different start and finish allowed.
- Maximum distance from the selected city.
- Whether repeated street segments are allowed.
- Maximum retraced distance.
- Shape rotation:
  - Fixed orientation.
  - Limited rotation.
  - Any rotation.
- Mirroring:
  - Disabled by default.
  - Optional horizontal or vertical mirroring.
- Whether disconnected shape strokes are allowed.
- Maximum connector length between strokes.
- Avoidance preferences, including major roads, stairs, tunnels, ferries, unpaved roads, or steep gradients where supported.

The application must make constraints explicit. It must not silently relax a user constraint to obtain a result.

Ferries are disabled by default. Ordinary building interiors and unrouted open-water crossings are never user-relaxable constraints.

## 8. Feature A: Shape Search Within a City

### 8.1 User Story

As a user, I want to provide a shape and select a city so that I can receive practical routes on real streets that resemble the shape.

### 8.2 Primary Workflow

1. The user enters or selects a city.
2. The system resolves and displays the city boundary.
3. The user supplies a target shape.
4. The system displays the normalized interpretation of the shape.
5. The user chooses travel and route constraints.
6. The system validates provider availability and the configured freshness policy using only metadata the provider actually exposes.
7. The system generates waypoint proposals and submits them to the configured routing provider.
8. The system validates successful provider routes and rejects all unsuccessful proposals.
9. The system ranks valid candidates.
10. The user reviews route overlays, scores, warnings, and turn-by-turn feasibility.
11. The user selects and exports or navigates a route.

### 8.3 Functional Requirements

#### A-FR-001: City Resolution

The system must resolve the requested city to a geographic boundary and must ask the user to disambiguate multiple matches.

#### A-FR-002: Search Area

The default search area must be the city boundary. A boundary buffer may be added only if:

- The user enables it, or
- The product explicitly displays and obtains confirmation for the expanded area.

#### A-FR-003: Shape Normalization

The system must normalize translation and scale. Rotation and mirroring must follow user configuration.

#### A-FR-004: Managed Street Feature Access

The system must retrieve licensed road features, nearest-road results, or provider-derived city fingerprints from approved managed APIs. It must preserve provider-reported direction, access, restriction, and mode metadata where exposed. The application must not operate a production street-graph server.

#### A-FR-005: Candidate Generation

The search must generate multiple candidate placements and ordered waypoint proposals rather than relying on a single route attempt. A generated proposal is not a route. Each proposal must be sent to the configured routing provider before it can become a candidate route.

Candidate generation should vary:

- Shape position.
- Shape scale.
- Allowed orientation.
- Start point.
- Street-feature landmark correspondence.
- Connector choices.

For each placement, the system must progressively refine routing waypoints. Refinement must add the highest-value unused shape points first and continue until:

- The provider waypoint limit is reached.
- Additional points no longer improve the provider route's similarity.
- The search budget is exhausted.
- A provider or minimum-spacing constraint prevents further useful refinement.

Every refinement produces a new complete provider request. The route from the previous refinement remains separate and must not be manually edited.

#### A-FR-006: Continuous Navigation

By default, a candidate must be one continuous navigable provider route. If multi-stroke mode is enabled, all shape strokes and transitions must be submitted as one ordered routing request, or the provider must explicitly route every transition. The application must never connect independently returned route fragments itself.

#### A-FR-007: Candidate Validation

Before presentation, each waypoint proposal must be submitted to the configured routing provider. The returned provider route must then be validated against the requested profile, waypoint sequence, city boundary, user constraints, and provenance requirements.

The following are not valid substitutes for this request:

- Local interpolation.
- Nearest-road snapping without a Route response.
- A visual correspondence with map tiles.
- A straight line between waypoints.
- A route cached for different waypoint coordinates or provider options.
- A client-generated polyline.

Validation must run automatically for every provider alternative. Only routes that pass all stages in Section 6.12 may participate in ranking.

#### A-FR-008: Result Ranking

The system must return a configurable number of top candidates, defaulting to five. Candidates must be ranked using the scoring model in Section 11.

#### A-FR-009: Result Explanation

Each result must display:

- Overall score.
- Shape similarity score.
- Route feasibility score.
- Route distance and estimated duration.
- Amount and percentage of retracing.
- Connector distance.
- Number of road crossings where available.
- Surface and elevation summary where available.
- Provider data version or timestamp when available; otherwise the route-response timestamp with an explicit availability label.
- Warnings and known uncertainty.

#### A-FR-010: Map Inspection

The result view must allow the user to:

- Overlay the target shape and route.
- Toggle connectors and retraced segments.
- Inspect individual street segments.
- View route direction.
- Zoom to deviations with the greatest effect on similarity.

#### A-FR-011: Export

The system must support GPX export through a fail-closed export gate. An export request may start only from `eligible_for_display` or `eligible_for_gpx_export`. No file is downloadable until the export gate succeeds and the route version is `eligible_for_gpx_export`.

The export service must:

1. Load the immutable stored provider response.
2. Verify its integrity hash.
3. Reparse the selected provider route.
4. Verify that its route ID, profile, geometry encoding, provider data version, and validation record agree.
5. Decode the provider geometry using the provider-declared precision.
6. Write those coordinates, in the same order, to GPX.
7. Reparse the generated GPX.
8. Compare the GPX coordinate sequence with the decoded canonical provider geometry.
9. Reject and delete the export if the comparison fails.

The GPX may include metadata, timestamps, route names, and provider-supplied maneuver descriptions. Such metadata must not change the geographic path.

The GPX must not contain:

- Target-shape coordinates.
- Proposed waypoint-to-waypoint straight lines.
- Map canvas coordinates.
- Synthetic connector points.
- Smoothed or aesthetically adjusted coordinates.
- Coordinates taken from a failed or unverified response.

The generated GPX must include provenance metadata or a reference to it:

- Internal route ID.
- Provider name.
- Routing profile.
- Provider-response SHA-256 hash.
- Managed-provider data version or retrieval timestamp.
- Route-generation timestamp.
- Application algorithm and export versions.

GeoJSON export may also be provided. Turn-by-turn export is dependent on routing-engine support and licensing.

#### A-FR-012: No-Result Handling

If no candidate satisfies the constraints, the system must not manufacture a route. It must explain the principal limiting constraints and may suggest explicit changes, such as:

- Increase maximum distance.
- Allow rotation.
- Allow limited retracing.
- Allow real-road connectors between strokes.
- Expand the boundary.
- Select another travel mode.

Constraints may be changed only after user action.

#### A-FR-013: Untested Route Prevention

The application must not expose provisional, untested, partially validated, or validation-expired routes through:

- Search results.
- City recommendations.
- Map geometry endpoints.
- Navigation views.
- Sharing links.
- GPX or GeoJSON exports.
- Internal preview APIs accessible to production clients.

Production route APIs must query only records whose current state is `eligible_for_display` or `eligible_for_gpx_export`, as appropriate. A missing validation record must be treated as failure, not as implicit success.

### 8.4 Search Algorithm

The recommended search pipeline is:

1. **Preprocess the shape**
   - Convert to polylines.
   - Preserve source geometry.
   - Create adaptive high-density samples.
   - Build coarse, medium, and high-resolution point levels.
   - Detect corners, intersections, endpoints, and topology.

2. **Retrieve managed road features**
   - Request only licensed provider data for the approved region.
   - Filter by travel mode using exposed provider metadata.
   - Calculate permitted derived bearings, lengths, curvature, and intersection features.
   - Load versioned provider-derived city fingerprints from Neon where permitted.

3. **Generate geographic placements**
   - Fit the normalized shape into candidate bounding boxes.
   - Sample legal scales, rotations, and positions.
   - Prioritize areas whose street orientation and intersection patterns resemble the shape.

4. **Match shape landmarks**
   - Match shape endpoints, corners, and intersections to managed road-feature positions or provider nearest-road results.
   - Add high-curvature and evenly distributed detail points.
   - Penalize incompatible topology and excessive displacement.
   - Reject landmarks that cannot be associated with mode-compatible routable features.
   - Reject obstacle conflicts according to Section 6.10.1 before spending a Directions request.

5. **Construct ordered waypoint proposals**
   - Construct ordered waypoint proposals between matched landmarks.
   - Use licensed managed road features or provider-derived fingerprints only to prioritize proposals.
   - Do not expose locally constructed geometry as a route.

6. **Request provider routes**
   - Send each ordered waypoint proposal to the configured managed Directions API.
   - Request complete provider geometry.
   - Store the request and original response before further processing.
   - Reject provider errors, no-route responses, and malformed geometries.

7. **Optimize candidates**
   - Adjust placement and landmark assignments.
   - Add routing waypoints iteratively up to configured provider limits.
   - Retain a new route only when its automatically calculated quality improves or it provides meaningful diversity.
   - Submit a new provider request after every waypoint change.
   - Never edit a returned route geometry.

8. **Validate candidates**
   - Execute every automatic validation stage in Section 6.12.
   - Recalculate shape similarity from the exact provider geometry.
   - Compare against the high-density target sample set.
   - Enforce distance, duration, access, boundary, obstacle, loop, connector, and retracing constraints.

9. **Score and deduplicate**
   - Rank candidates.
   - Remove near-identical routes.
   - Return diverse results when possible.

Exact shape optimization may be computationally prohibitive. Approximate techniques such as beam search, A*, simulated annealing, or genetic search may choose waypoint proposals, but they must never generate final route geometry. Only successful provider responses may supply route geometry.

### 8.4.1 Required Baseline Optimization Loop

The first production implementation must use a deterministic, bounded beam-search baseline:

1. Generate a versioned set of legal shape transformations from allowed rotations, scales, and placements inside the typed search area.
2. Match mandatory shape landmarks to mode-compatible managed road features.
3. Reject transformed placements with unresolved water, building, private-access, or connectivity conflicts.
4. Build complete ordered waypoint proposals within the provider limit.
5. Submit each proposal to the managed Directions API.
6. Store and validate every returned alternative independently.
7. Score only canonical provider geometry.
8. Keep the best configurable beam width using overall score plus a diversity penalty.
9. Refine retained proposals by adding or replacing the highest-error landmark while preserving all mandatory landmarks.
10. Submit a new complete provider request after every proposal change.
11. Stop at convergence, provider limits, or configured request, time, and cost budgets.
12. Return only fully validated provider routes; otherwise return no result.

The transformation grid, beam width, refinement order, convergence threshold, and budgets must be configuration-driven and versioned. Given identical inputs, provider fixtures, configuration, and random seed, the search must produce reproducible ordering.

### 8.5 Feature A Acceptance Criteria

- Given a valid city, shape, and travel mode, the system searches only the resolved boundary and any user-approved buffer.
- Every displayed route is the exact geometry returned by a successful managed-provider route response.
- Where the provider exposes route-node or edge annotations, those identifiers are retained with the route provenance.
- Every displayed route has an immutable successful provider request and response.
- A route with an unrouteable gap is rejected.
- A waypoint proposal is never returned as a route.
- Changing a waypoint triggers a new provider route request.
- Final candidates use the highest useful routing-waypoint count supported by the selected provider's single-request limit.
- The full high-density target sample set is used for final shape scoring.
- The result exposes shape sample count, routing waypoint count, provider geometry point count, and maximum sampling deviation.
- One-way and access restrictions are respected by the selected mode.
- Open-water crossings without verified bridges, tunnels, or explicitly enabled ferry legs are rejected.
- Ordinary building-interior crossings are rejected.
- Missing or conflicting obstacle evidence fails closed and exposes no route.
- The system returns ranked candidates or a truthful no-result response.
- The user can see where the route differs from the target shape.
- The user can see data freshness and route warnings.
- Exported GPX geometry matches the validated route and contains no visual-only corrections.
- GPX export fails if route provenance or response integrity cannot be verified.
- No route appears in any production result before automatic validation completes successfully.
- An expired route is automatically revalidated or withheld.

## 9. Feature B: City Recommendation for a Shape

### 9.1 User Story

As a user, I want to provide a shape and receive recommended cities where that shape can be followed on real streets.

### 9.2 Primary Workflow

1. The user supplies a target shape.
2. The system displays the interpreted shape.
3. The user selects travel and route constraints.
4. The user optionally limits countries, regions, distance from their location, or city size.
5. The system selects eligible cities from its supported-city catalog.
6. The system performs a low-cost structural screening.
7. The system performs full route searches for promising cities.
8. The system validates and ranks city-route pairs.
9. The user reviews recommended cities and their best routes.

### 9.3 Functional Requirements

#### B-FR-001: Supported-City Catalog

The system must maintain a catalog of searchable cities. Each entry must include:

- Stable identifier.
- Name and administrative hierarchy.
- Boundary polygon.
- Geographic center.
- Search-area size.
- Managed-provider data version or retrieval timestamp.
- Available travel modes.
- Data freshness.
- Derived city-fingerprint version.

The system must not claim worldwide coverage unless every relevant area is actually indexed and searchable.

#### B-FR-002: Geographic Filters

Users may restrict recommendations by:

- Country or region.
- Maximum distance from a specified location.
- City population range where licensed data is available.
- Maximum route distance.
- Travel mode.
- Supported data freshness.

#### B-FR-003: Two-Stage Search

The recommendation process should use:

1. A structural screening phase to eliminate unlikely cities.
2. A full route-search phase using the same validation rules as Feature A.

A city must not be presented as feasible based only on structural screening.

#### B-FR-004: City Screening

The screening phase may use real street-derived features such as:

- Distribution of road bearings.
- Intersection-degree distribution.
- Road density.
- Block-size distribution.
- Curvature patterns.
- Presence of loops, diagonals, grids, or radial streets.
- Connected-component size for the selected mode.
- Available scale ranges.

All screening features must be calculated from actual street data.

#### B-FR-005: Recommendation Evidence

Every recommended city must include at least one fully validated provider route. Structural analysis, map appearance, or waypoint proposals alone are insufficient. A city without a successful provider route may appear only in a clearly labeled "not feasible" or "search incomplete" state.

The same automatic validation gate used by Feature A must run without exception. A cached city recommendation must be withheld when its best route is validation-expired.

#### B-FR-006: Ranking

Cities must be ranked by the best validated route, adjusted for user constraints and confidence. Multiple route candidates may be displayed per city.

#### B-FR-007: Recommendation Explanation

Each recommendation must show:

- City and country.
- Best route preview.
- Shape similarity.
- Route feasibility.
- Distance and duration.
- Data freshness.
- Why the city fits the shape.
- Important compromises, such as rotation, retracing, or connectors.
- Search confidence and completion state.

#### B-FR-008: Search Scope Transparency

The interface must state:

- How many cities were eligible.
- How many were screened.
- How many received full searches.
- Whether the search completed or was limited by time or compute budget.

The phrase "best city" may be used only when the documented eligible set was fully evaluated. Otherwise, the result must be described as "best among searched cities."

#### B-FR-009: Cached Results

Cached search results may be reused only when:

- The shape fingerprint and relevant constraints match.
- The managed-provider data metadata remains within the freshness policy.
- The routing and scoring versions are compatible.

The interface must identify cached results and their original generation time.

#### B-FR-010: No-Recommendation Handling

If no supported city contains a valid route, the system must return no recommendation and explain:

- Search coverage.
- Constraints that eliminated candidates.
- Whether relaxing specific constraints may help.

### 9.4 Recommendation Algorithm

1. Convert the target shape into a shape fingerprint containing:
   - Stroke count.
   - Aspect ratio.
   - Corner-angle distribution.
   - Segment-orientation distribution.
   - Curvature profile.
   - Intersection topology.
   - Closed-loop characteristics.

2. Apply user geographic and travel constraints to the city catalog.

3. Compare the shape fingerprint with street-derived city indexes.

4. Select the most promising city regions, not only whole-city averages. This avoids rejecting a city whose relevant street pattern occurs in one neighborhood.

5. Run Feature A's full search against the selected regions.

6. Submit promising waypoint proposals to the configured routing provider.

7. Validate every provider-returned route and its provenance.

8. Rank city-route pairs and retain diverse geographic alternatives.

9. Report exact search coverage and confidence.

### 9.5 Feature B Acceptance Criteria

- Every recommended city has at least one validated route on real streets.
- Every recommended route was returned by the configured routing provider.
- Every recommended route passed the current automatic validation pipeline.
- Screening alone never produces a feasible recommendation.
- Recommendation ranking is based on validated city-route pairs.
- The interface accurately states the evaluated city set.
- Stale or unsupported cities are excluded or clearly labeled.
- Geographic and travel-mode filters are respected.
- If no route is feasible, the system returns a truthful no-result response.

## 10. Shape Comparison

Candidate and target geometry must be compared after applying only the transformations allowed by the user.

Potential measures include:

- Symmetric Chamfer distance.
- Discrete Frechet distance.
- Hausdorff distance with outlier controls.
- Turning-function distance.
- Landmark displacement.
- Topology mismatch.
- Stroke-order mismatch.
- Aspect-ratio difference.
- Area or silhouette overlap for closed shapes.

No single metric is sufficient for all shapes. The system should combine geometric and topological measures and normalize scores to a documented range from 0 to 100.

For multi-stroke targets, the route remains one continuous journey. The scoring implementation must:

1. Preserve the ordered target-stroke boundaries.
2. Align contiguous provider-geometry spans to target strokes in the selected stroke order.
3. Classify the intervening provider-routed spans as connectors.
4. Include connector length in feasibility and extra-geometry penalties, but not treat connectors as target-stroke coverage.
5. Reject the candidate when connector or missing-stroke hard limits are exceeded.
6. Store the alignment algorithm and version so scores remain reproducible.

The application must describe multi-stroke output as a connected route with real-road transitions, not as pen-up drawing.

## 11. Scoring Model

### 11.1 Overall Score

The default score may be calculated as:

`overall = 0.55 * shape_similarity + 0.30 * route_feasibility + 0.15 * user_preference_fit`

Weights must be versioned and configurable.

### 11.2 Shape Similarity

Shape similarity should consider:

- Geometric distance.
- Correct relative segment lengths.
- Correct turns and curvature.
- Correct topology.
- Missing shape portions.
- Extra route portions, including connectors.

### 11.3 Route Feasibility

Route feasibility should consider:

- Continuous routability.
- Access restrictions.
- Route length and estimated duration.
- Retraced distance.
- Number and length of connectors.
- Excessive turns or unsafe maneuvers where reliable data exists.
- Surface, elevation, lighting, and sidewalk or cycling-infrastructure data where available.

Missing optional metadata must reduce confidence rather than being interpreted as a positive safety attribute.

### 11.4 Hard Constraints

Hard constraints are pass/fail and must not be hidden inside a weighted score. Examples:

- Maximum route distance.
- Required travel mode.
- Closed-loop requirement.
- Geographic boundary.
- Prohibited road classes.
- Maximum connector length.
- Maximum retracing.
- Unverified open-water intersection.
- Ordinary building-interior intersection.
- Private or mode-incompatible access where reliable evidence exists.

Any hard-constraint violation must reject the candidate.

### 11.5 Score Transparency

The API response must include:

- Overall score.
- Component scores.
- Scoring-model version.
- Applied hard constraints.
- Penalties.
- Confidence level.

## 12. API Specification

### 12.1 Create City Shape Search

`POST /v1/searches/city-shape`

Example request:

```json
{
  "cityId": "provider-city-id",
  "shape": {
    "type": "svg",
    "content": "<svg>...</svg>"
  },
  "travelMode": "cycling",
  "routingProvider": "mapbox",
  "constraints": {
    "minimumDistanceMeters": 5000,
    "maximumDistanceMeters": 20000,
    "closedLoop": true,
    "allowRotation": true,
    "allowMirroring": false,
    "allowMultipleStrokes": false,
    "maximumRetraceRatio": 0.1
  },
  "resultLimit": 5
}
```

`routingProvider` is an optional allowlisted provider preference, not a provider URL or profile selector. The server may ignore it, must reject unsupported values, and must map the validated travel mode to a server-configured profile.

Example accepted response:

```json
{
  "searchId": "search-id",
  "status": "queued",
  "submittedAt": "2026-07-13T11:30:00Z"
}
```

### 12.2 Create Shape City Recommendation

`POST /v1/searches/shape-cities`

Example request:

```json
{
  "shape": {
    "type": "catalog",
    "shapeId": "heart"
  },
  "travelMode": "walking",
  "routingProvider": "mapbox",
  "constraints": {
    "maximumDistanceMeters": 15000,
    "closedLoop": true,
    "allowRotation": true,
    "allowMirroring": false
  },
  "geographicFilter": {
    "countryCodes": ["DE", "AT", "CH"]
  },
  "cityResultLimit": 10,
  "routesPerCity": 3
}
```

The same server-side provider-selection rules from Section 12.1 apply.

### 12.3 Read Search Status

`GET /v1/searches/{searchId}`

States:

- `queued`
- `screening`
- `searching`
- `validating`
- `completed`
- `completed_with_limits`
- `no_result`
- `failed`
- `cancelled`

### 12.4 Cancel Search

`DELETE /v1/searches/{searchId}`

Cancellation must stop unstarted work and attempt to stop active search tasks. Partial candidates must not be returned as validated results.

### 12.5 Result Object

Each route result must include:

```json
{
  "routeId": "route-id",
  "city": {
    "id": "provider-city-id",
    "name": "Example City",
    "countryCode": "DE"
  },
  "score": {
    "overall": 87.4,
    "shapeSimilarity": 91.2,
    "routeFeasibility": 82.1,
    "preferenceFit": 84.0,
    "modelVersion": "1.0"
  },
  "route": {
    "distanceMeters": 12430,
    "estimatedDurationSeconds": 3720,
    "closedLoop": true,
    "retraceMeters": 410,
    "connectorMeters": 0,
    "shapeSamplePointCount": 8420,
    "routingWaypointCount": 25,
    "providerGeometryPointCount": 2317,
    "maximumSamplingDeviationMeters": 0.75,
    "geometrySource": "verified_provider_response",
    "geometryUrl": "/v1/routes/route-id/geometry"
  },
  "verification": {
    "status": "verified",
    "routingProvider": "Mapbox",
    "providerDataVersion": null,
    "providerDataTimestamp": null,
    "providerDataVersionAvailable": false,
    "routedAt": "2026-07-13T11:30:30Z",
    "routingEngine": "Mapbox Directions API",
    "routingProfile": "mapbox/cycling",
    "routingProfileVersion": "profile-version",
    "providerRequestId": "provider-request-id",
    "providerResponseSha256": "sha256-hex-value",
    "validationPipelineVersion": "validation-version",
    "validationStatus": "passed",
    "validatedAt": "2026-07-13T11:31:00Z",
    "validationExpiresAt": "2026-07-14T11:31:00Z",
    "gpxExportStatus": "available_on_request"
  },
  "warnings": []
}
```

The geometry endpoint must return actual coordinates decoded from the stored provider response. It must not accept replacement coordinates from the client.

`providerDataVersion` and `providerDataTimestamp` are nullable because not every managed provider exposes them. `routedAt` and `validatedAt` must not be mislabeled as source-map update timestamps.

`gpxExportStatus` is one of `available_on_request`, `ready`, `revalidation_required`, `prohibited_by_policy`, or `unavailable`. It does not bypass the on-demand export gate.

### 12.6 GPX Export API

`POST /v1/routes/{routeId}/exports/gpx`

The endpoint must:

- Refuse unknown, rejected, retired, unauthorized, or policy-prohibited route IDs.
- Return no file for stale or expired route versions; it may return `revalidation_pending` after creating a fresh route-version request.
- Never accept coordinates in the request body.
- Never accept an SVG, target shape, waypoint list, or client polyline as GPX source data.
- Resolve geometry exclusively from the immutable provider response associated with `routeId`.
- Return an integrity identifier for the generated file.

Example successful metadata response:

```json
{
  "exportId": "export-id",
  "routeId": "route-id",
  "status": "ready",
  "source": "verified_provider_geometry",
  "providerResponseSha256": "sha256-hex-value",
  "gpxSha256": "sha256-hex-value"
}
```

If validation fails, the endpoint must return an error and produce no downloadable file.

### 12.7 Route Geometry API

`GET /v1/routes/{routeId}/geometry`

The endpoint must return only the canonical decoded provider geometry associated with the validated route. It must include:

- Route ID.
- Provider and profile.
- Provider response hash.
- Geometry format.
- Coordinate count.
- GeoJSON `LineString` generated without changing the coordinate sequence.

Unvalidated routes must return an error rather than provisional geometry.

### 12.8 GPX File Format Rules

The canonical export format must be GPX 1.1 using one `<trk>` and one continuous `<trkseg>`:

```xml
<gpx version="1.1" creator="gps-art-application">
  <metadata>
    <name>Verified GPS art route</name>
  </metadata>
  <trk>
    <name>Verified GPS art route</name>
    <trkseg>
      <!-- One trkpt for each canonical provider coordinate, in provider order. -->
    </trkseg>
  </trk>
</gpx>
```

The XML above specifies structure only. Production track points must come from canonical provider geometry.

Serialization rules:

- One `<trkpt>` must be written per canonical provider coordinate unless a documented, lossless representation rule proves equivalence.
- GPX latitude and longitude attributes must use provider coordinates in latitude/longitude attribute positions, even when provider JSON or GeoJSON uses longitude/latitude arrays.
- Coordinate order must not change.
- The first and last point must match the provider geometry's first and last point.
- The exporter must not add elevation. `<ele>` may be included only when sourced from an identified real elevation provider and stored separately from route provenance.
- The exporter must not synthesize per-point timestamps. `<time>` may be included only when representing a real recorded or provider-supplied time.
- A route-generation timestamp may appear in GPX metadata but must not be represented as if every track point had been physically recorded.
- The exporter must not add a closing point unless that point exists at the end of the provider geometry.
- A single provider geometry must not be split into disconnected segments for aesthetic purposes.
- XML must be schema-valid, UTF-8 encoded, and safely escaped.

Post-export verification must compare the parsed GPX points with canonical provider coordinates numerically. Differences caused only by decimal serialization are allowed up to half of the stored coordinate precision unit; any larger difference must fail the export.

### 12.9 Provider Failure Responses

The application must distinguish:

- `provider_unavailable`: timeout, DNS, connection, or upstream outage.
- `provider_rejected_request`: invalid profile, options, or coordinate limits.
- `provider_no_route`: successful provider response with no route.
- `provider_malformed_response`: invalid JSON or missing required route data.
- `provider_route_invalid`: route returned but failed application validation.
- `provenance_invalid`: request, response, profile, provider data version, or hash cannot be verified.

None of these states may return route geometry, navigation instructions, or a GPX download.

### 12.10 Status and Failure Mapping

Search status and failure codes are separate:

| Search status | Meaning | Candidate or provider failure code |
|---|---|---|
| `queued`, `screening`, `searching`, `validating` | Non-terminal search progress. | Optional diagnostic only. |
| `completed` | Search finished with at least one display-eligible route. | None for successful results; rejected candidates retain their own codes. |
| `completed_with_limits` | Budget ended after at least one valid result or after partial documented coverage. | Optional limiting reason. |
| `no_result` | Search completed without an eligible route. | One or more of `provider_no_route`, `provider_route_invalid`, `provenance_invalid`, or constraint-specific rejection codes. |
| `failed` | The search itself could not complete reliably. | `provider_unavailable`, `provider_rejected_request`, `provider_malformed_response`, or an internal workflow failure code. |
| `cancelled` | User or system cancellation completed. | `search_cancelled`. |

`validation_failed` from Section 1.1 is a public outcome category, not a search-status enum value. It maps to candidate state `rejected` and normally produces search status `no_result` unless another candidate succeeds.

## 13. Architecture

Recommended components:

| Component | Responsibility |
|---|---|
| API service | Authentication, validation, search creation, result delivery. |
| Shape processor | Vectorization, normalization, simplification, fingerprinting. |
| Geocoding service | City lookup and boundary resolution. |
| Managed street-data adapter | Provider capabilities, licensed road features, data-version metadata, and attribution. |
| Routing service | Mode-specific routing and final candidate verification. |
| Inngest search orchestrator | Durable search state, budgets, retries, cancellation, and workflow steps. |
| Inngest candidate workflows | Placement, waypoint proposal, provider requests, optimization, and scoring. |
| City index | Street-derived features for recommendation screening. |
| Neon result store | Search parameters, candidates, scores, ownership, and data provenance. |
| Vercel Blob response store | Original successful and failed provider responses with integrity hashes. |
| Automatic route validator | Executes geometry, routing, constraints, shape, provenance, freshness, and publication gates. |
| Export service | Fail-closed GPX and optional GeoJSON generation from verified provider geometry only. |

Long-running searches should be asynchronous. Search jobs must be idempotent and identified by stable request fingerprints where appropriate.

## 14. Data Model

Minimum persistent entities:

### Search

- Search ID.
- Feature type.
- User or anonymous-session ID.
- Original and normalized shape references.
- Constraints.
- Status.
- Progress.
- Search coverage.
- Algorithm version.
- Scoring version.
- Created, started, and completed timestamps.

### City

- City ID.
- Names and administrative hierarchy.
- Boundary geometry.
- Search regions.
- Managed-provider data version or retrieval timestamp.
- Supported travel modes.
- Derived city-fingerprint version.

### Candidate Route

- Route ID and search ID.
- City ID.
- Ordered proposed waypoints.
- Shape sample point count and sampler version.
- Routing waypoint count and selector version.
- Maximum shape-sampling deviation.
- Provider request ID.
- Selected route index in the provider response.
- Verified route geometry.
- Provider geometry encoding and precision.
- Provider-response integrity hash.
- Route statistics.
- Component and overall scores.
- Hard-constraint results.
- Warnings.
- Verification state.
- Validation pipeline version.
- Validation stage results and rejection reasons.
- Validation and expiration timestamps.

### Managed Provider Data Version

- Provider data-version identifier where exposed.
- Provider.
- Source version.
- Geographic coverage.
- Retrieval timestamp.
- Source timestamp.
- Routing API and profile version.
- License and attribution.

### Provider Request

- Provider request ID.
- Candidate ID.
- Managed-provider account, region, and API version.
- Routing profile and version.
- Ordered waypoints.
- Route-affecting options.
- Request and response timestamps.
- HTTP and provider statuses.
- Immutable response location.
- Response SHA-256 hash.
- Parse and validation outcomes.

### GPX Export

- Export ID and route ID.
- Exporter version.
- Source provider-response hash.
- Generated GPX hash.
- Coordinate count.
- Coordinate comparison result.
- Creation timestamp.
- Download authorization and expiration.

### Validation Run

- Validation run ID and route ID.
- Validation pipeline version.
- Trigger: initial, scheduled freshness, provider update, profile update, or pre-export.
- Start and completion timestamps.
- Input provenance hashes.
- Result for every validation stage.
- Calculated shape and route metrics.
- Rejection codes and diagnostics.
- Final publication and export eligibility.

## 15. Performance Requirements

- City resolution should complete within 2 seconds at the 95th percentile, excluding provider outages.
- Shape preprocessing should complete within 3 seconds for supported input-size limits.
- Feature A should provide progress within 2 seconds after submission.
- On a paid production provider tier, Feature A should target a first validated candidate within 30 seconds and normal completion within 2 minutes for ordinary city searches. Free-plan, rate-limited, cold-start, and high-complexity searches may exceed these targets and must display an honest estimate.
- Feature B may take longer and must provide progress, coverage, and cancellation.
- Result-map interactions should remain responsive with route simplification used only for display.
- Search time and compute budgets must be configurable.

If a budget expires, the status must be `completed_with_limits`, and the system must report the evaluated scope.

## 16. Reliability and Failure Handling

- Search jobs must survive worker restarts.
- Failed validation must remove a candidate rather than downgrade it to a valid result.
- Automatic validation jobs must be idempotent for the same route and provenance hashes.
- Validation must fail closed when a stage times out, crashes, or returns an unknown result.
- A route must not become visible through an eventual-consistency window before validation commits.
- Publication eligibility and validation evidence must be committed atomically in Neon. Required Blob objects must be written, hashed, and read-verified before that database transaction commits.
- A compensating cleanup workflow must remove orphaned Blob objects left by failed database publication.
- Provider failure must never activate a locally generated fallback route.
- Missing provenance or hash mismatch must make a route non-displayable and non-exportable.
- GPX generation must be atomic: a partially written or failed export must not be downloadable.
- Provider or routing failures must be surfaced with a retriable or non-retriable classification.
- Partial city-recommendation coverage must be reported.
- A stale or incompatible managed street-analysis dataset must block validation until compatible provider data is available.
- Duplicate submissions may reuse compatible work, but the original data provenance must remain visible.

## 17. Safety and Accessibility

The application must state that users remain responsible for evaluating current conditions.

Where reliable data exists, warn about:

- High-speed or high-traffic roads.
- Missing sidewalks or cycling infrastructure.
- Unpaved surfaces.
- Stairs.
- Tunnels.
- Ferries.
- Restricted or private access.
- Significant elevation.

The absence of a warning must not be presented as proof of safety. Real-time closures and temporary hazards must be integrated only from identified live-data sources.

## 18. Privacy

- A user's current location must be optional.
- Precise locations and generated routes must not be made public by default.
- Location history must not be retained longer than necessary for the stated feature.
- Shared routes must exclude private metadata.
- Logs should use search IDs rather than raw location or shape content where possible.
- Account deletion must remove user-associated searches and exports according to the retention policy.

## 19. Security

- Validate and sanitize SVG and uploaded files.
- Reject executable content, external SVG references, and oversized inputs.
- Apply request, compute, and storage quotas.
- Authorize access to private searches and exports.
- Protect routing and data-provider credentials.
- Validate exported filenames and metadata.
- Record administrative changes to scoring, routing profiles, and data sources.

## 20. Observability

The system should record:

- Search counts by feature and status.
- Time spent in preprocessing, screening, matching, routing, and validation.
- Candidate generation and rejection counts.
- Shape sample counts, routing waypoint counts, and provider geometry point counts.
- Similarity improvement by waypoint-refinement iteration.
- Validation pass, failure, expiration, and revalidation counts by stage.
- Rejection reasons.
- Result-score distributions.
- Data freshness.
- Provider and routing errors.
- Search coverage for city recommendations.
- Export and route-selection rates.

Operational logs must include search, provider data-version, algorithm, and scoring identifiers without exposing unnecessary personal location data.

## 21. Testing Requirements

### 21.1 Unit Tests

- Shape normalization and allowed transformations.
- Adaptive sampling preserves endpoints, corners, intersections, and curvature.
- Increasing the point budget never removes mandatory landmarks.
- Error-bounded waypoint reduction stays within its declared maximum deviation.
- Waypoint selection respects configured provider and request-size limits.
- Dense shape samples remain separate from canonical route coordinates.
- Shape fingerprint generation.
- Score calculation.
- Hard-constraint enforcement.
- City filtering.
- Route-statistic calculation.
- Data-freshness classification.
- Validation state transitions reject skipped or unknown stages.
- Validation expiration and revalidation decisions.

### 21.2 Integration Tests

Successful route integration fixtures must be immutable responses captured from real managed-provider requests under terms that permit test retention. Invented street graphs or synthetic successful route geometry are not acceptable.

Test:

- Managed road-feature and city-boundary adapters.
- Managed-provider travel-mode behavior.
- One-way and turn behavior represented by real provider responses.
- Provider annotation traceability where the managed provider exposes it.
- Managed-provider request and response validation.
- Progressive waypoint refinement submits complete independent provider requests.
- The final candidate uses the highest useful point density within configured limits.
- Oversized shape point sets are reduced without splitting or joining provider routes.
- Provider-level error handling even when HTTP status is successful.
- Rejection of empty, malformed, or discontinuous provider geometry.
- Rejection of profile mismatches.
- Rejection of a provider geometry crossing water without bridge, tunnel, or allowed-ferry evidence.
- Rejection of a provider geometry crossing an ordinary building interior.
- Acceptance of a real bridge or tunnel crossing only when corroborating provider evidence exists.
- Rejection when obstacle evidence is missing or contradictory in strict mode.
- Immutable response hashing and tamper detection.
- Search persistence and cancellation.
- Atomic publication after validation.
- Automatic withholding when validation crashes, times out, or expires.
- Automatic revalidation after provider data-version or routing-profile changes.
- GPX export consistency.
- GPX export rejection when provenance is missing.
- GPX export rejection when the provider-response hash changes.
- GPX export rejection when any output coordinate differs from canonical provider geometry.

### 21.3 End-to-End Tests

- Search for a simple shape in a supported city.
- Search for a high-curvature shape and confirm denser sampling around curves than straight segments.
- Search for a shape exceeding the managed-provider waypoint limit and confirm error-bounded reduction.
- Recommend cities for a simple shape.
- Return no result for impossible hard constraints.
- Return no result when the configured managed provider returns no route.
- Return no result when the routing provider is unavailable and no compatible verified result exists.
- Reject a candidate containing a disconnected gap.
- Reject an unrouted line across an ocean, lake, or river.
- Reject a route through an ordinary building footprint.
- Display a provider-routed bridge, tunnel, or explicitly enabled ferry honestly without replacing its geometry.
- Confirm that target-shape coordinates never appear as GPX source data.
- Confirm that separately routed fragments cannot be concatenated into one route.
- Confirm that a route is absent from all public APIs until automatic validation passes.
- Confirm that a route failing any one validation stage remains unavailable.
- Confirm that an expired route is withheld until successful automatic revalidation.
- Confirm that a changed revalidated provider route receives new provenance and scores.
- Display stale-data warnings.
- Respect rotation and mirroring settings.
- Handle disconnected strokes with real connectors.
- Report partial city-search coverage.

### 21.4 Data Provenance Tests

For every accepted test result:

- The route is present in the selected successful managed-provider response.
- Provider annotations are internally consistent where exposed.
- A successful provider request and immutable response exist.
- Shape sampling and routing waypoint metrics are present.
- Automatic validation evidence exists for every required stage.
- Validation is current and refers to the same provider-response hash.
- The stored response hash is correct.
- Displayed coordinates match the selected provider route.
- Exported GPX coordinates match the decoded provider geometry in order.
- No target-shape, visual-overlay, interpolation, or waypoint-only coordinates enter the GPX.
- Provider data-version metadata or retrieval timestamp and routing versions are present.

## 22. Release Criteria

The features are ready for production when:

- All acceptance criteria pass.
- Every displayed route is traceable to real street data.
- Every displayed route originates from a successful configured routing-provider response.
- Every displayed route passed every automatic validation stage.
- No manual approval can bypass automatic route validation.
- Dense adaptive shape sampling and progressive waypoint refinement are enabled in production.
- Provider waypoint limits are explicitly configured and tested.
- No code path can mark a waypoint proposal, target shape, client polyline, or locally joined geometry as a route.
- Unsupported or stale coverage is clearly communicated.
- Feature B never recommends a city without a validated candidate route.
- Search progress, cancellation, and failure states function correctly.
- Privacy, attribution, and provider-license requirements are satisfied.
- GPX exports reproduce the validated route without fabricated connectors.
- GPX exports are generated only from immutable verified provider responses.
- Automated negative tests prove that failed routing, missing provenance, response tampering, and coordinate alteration produce no GPX file.
- Automated negative tests prove that validation timeout, crash, expiration, skipped stage, or unknown result exposes no route plan.
- Product documentation explains scores, limitations, data freshness, and safety responsibilities.

## 23. Web Application Feasibility and Product Architecture

### 23.1 Feasibility Decision

Both features are implementable as a managed Next.js web application when:

- Search is bounded and approximate rather than presented as a mathematical global optimum.
- Route geometry comes only from a managed Directions API.
- Long searches run through managed durable background workflows.
- Search state, provenance, and validation evidence are stored in a managed relational database.
- Provider responses and GPX exports are stored in managed object storage.
- City recommendation searches an explicit managed city catalog and reports coverage.

### 23.2 Required Technology Model

The application must use:

- Node.js with the latest supported LTS release.
- Next.js App Router.
- React and TypeScript.
- Server Components by default.
- Client Components only for browser interaction, map rendering, drawing, animation, and local UI state.
- Managed hosting and serverless execution.
- Managed authentication.
- Managed PostgreSQL.
- Managed durable background workflows.
- Managed object storage.
- Managed mapping, geocoding, and routing APIs.
- Managed monitoring and error reporting.

### 23.3 Reference Managed Stack

| Concern | Reference service |
|---|---|
| Web hosting and server functions | Vercel |
| Framework | Next.js |
| Authentication | Clerk |
| Database | Neon PostgreSQL |
| ORM and migrations | Drizzle ORM and Drizzle Kit |
| Background workflows | Inngest Cloud |
| Object storage | Vercel Blob |
| Maps and street visualization | Mapbox Maps |
| City search and geocoding | Mapbox Search |
| Route generation | Mapbox Directions API |
| Licensed road-feature access | Mapbox vector tiles or another managed provider API |
| Error monitoring | Sentry Cloud |
| Product analytics | Vercel Analytics |
| Web performance | Vercel Speed Insights |

Equivalent managed providers may be substituted, but self-hosted replacements are prohibited.

Every approved reference service must provide a documented zero-cost plan or free usage allowance suitable for development and MVP evaluation. Free-tier eligibility does not imply unlimited capacity, an SLA, or permission for commercial production.

### 23.4 Prohibited Production Infrastructure

The project must not operate its own:

- OSRM, GraphHopper, Valhalla, or other routing server.
- Nominatim, Photon, Pelias, or other geocoder.
- Overpass API.
- PostgreSQL, MySQL, SQLite, MongoDB, or Redis server.
- Queue broker or workflow orchestrator.
- S3-compatible storage server.
- Map-tile server.
- Kubernetes cluster, virtual machine, or long-running application server.

Local development tools are permitted, but production data and production services must use managed providers.

### 23.5 Honest Guarantees

The application may guarantee provider provenance, geometry integrity, automated validation, and GPX equality. It must not claim:

- Physical inspection of a road.
- Real-time road availability without a live provider signal.
- Perfect source-map accuracy.
- Global mathematical optimality.
- Worldwide city coverage beyond the indexed catalog.

The user-facing term must be **provider-validated route**.

The application must explain that:

- Arbitrary shapes are not guaranteed; the bounded algorithm may return no result.
- A provider-validated route is only as current and accurate as the managed provider and corroborating evidence.
- Strict obstacle validation reduces false routes but may reject real routes when bridge, tunnel, passage, or map-alignment evidence is incomplete.
- A line crossing water may represent a verified bridge, tunnel, or explicitly enabled ferry and must be labeled as such.

## 24. Next.js Application Structure

### 24.1 App Router

The application must use the Next.js App Router with route groups:

```text
src/
  app/
    (marketing)/
    (auth)/
    (app)/
      dashboard/
      create/
      searches/[searchId]/
      routes/[routeId]/
      recommendations/
      settings/
    api/
      v1/
        searches/
        routes/
      webhooks/
      inngest/
    layout.tsx
    globals.css
  components/
    ui/
    map/
    shape-editor/
    search/
    route/
    recommendations/
  features/
    auth/
    cities/
    shapes/
    search/
    routing/
    validation/
    exports/
  server/
    actions/
    db/
    providers/
    workflows/
    repositories/
  lib/
    geometry/
    scoring/
    schemas/
    errors/
  styles/
  tests/
```

### 24.2 Rendering Rules

- Server Components are the default.
- Database and provider access must remain server-only.
- Mapbox GL, drawing canvases, browser file APIs, and animation libraries may use Client Components.
- Large map components must be dynamically imported when server rendering is not supported.
- Initial page shells, search history, and route metadata should be server-rendered.
- Search progress should stream or update without full-page reloads.
- Loading and error boundaries must exist at route-segment level.

### 24.3 Server Interfaces

Use:

- Server Actions for authenticated mutations initiated by application forms.
- Route Handlers for webhooks, file downloads, provider callbacks, and public machine interfaces.
- Inngest functions for long-running and retryable work.
- Direct server-side service calls for internal reads.

Client Components must never call managed routing providers with secret tokens.

### 24.4 Runtime Selection

- Node.js runtime must be used for geometry processing, GPX generation, cryptographic hashes, database access, and provider adapters.
- Edge runtime may be used only for lightweight middleware or redirects that do not require unsupported Node.js APIs.
- Search algorithms must not execute inside a browser tab.
- Long loops must be divided into durable workflow steps.

## 25. User Experience and Visual Design

### 25.1 Design Direction

The application must feel modern, premium, and map-first rather than like an administrative dashboard.

Visual characteristics:

- Clean editorial typography.
- High-contrast route colors.
- Subtle depth, translucent panels, and restrained gradients.
- Generous spacing.
- Rounded but not excessively pill-shaped controls.
- Smooth state transitions.
- Purposeful micro-interactions.
- Strong visual hierarchy.
- Minimal persistent chrome around the map.

### 25.2 Responsive Layout

Desktop:

- Full-height map.
- Left workflow panel between 360 and 440 pixels.
- Optional right details drawer for candidate comparison.
- Collapsible bottom timeline or search progress panel.

Tablet:

- Full map with an overlay drawer.
- Two-column result comparison when space permits.

Mobile:

- Full-screen map.
- Bottom-sheet workflow.
- Thumb-reachable primary controls.
- Swipeable route cards.
- No hover-only interactions.

### 25.3 Core Screens

#### Landing Page

- Product value proposition.
- Real route examples clearly labeled with provenance.
- Interactive but lightweight map preview.
- Explanation of provider-validated routes.
- Primary calls to action for shape search and city recommendation.

#### Dashboard

- Recent searches.
- Saved routes.
- Search status.
- Validation freshness.
- GPX export history.
- Empty states with clear next actions.

#### Shape Creation

- Draw shape.
- Upload SVG.
- Select icon.
- Enter text.
- Inspect interpreted strokes.
- Display source and sample point counts.
- Warn about disconnected strokes.

#### City Shape Search

- Search city with managed autocomplete.
- Choose travel mode and constraints.
- Preview city boundary.
- Overlay normalized target shape.
- Submit background search.
- Display live progress and bounded-search coverage.

#### City Recommendation

- Provide shape.
- Set region and city filters.
- Display screened and fully searched city counts.
- Compare recommended cities using map thumbnails and score cards.

#### Route Detail

- Canonical provider route on map.
- Target-shape overlay with distinct styling.
- Similarity heat map.
- Route direction.
- Retraced segments.
- Provider, profile, validation, and map-data metadata.
- GPX export action.

### 25.4 Map Styling

- Use a modern Mapbox style with sufficient road contrast.
- Route geometry must remain visually dominant.
- Target shape must use a dashed or translucent style and never be confused with the route.
- Provider-snapped waypoints must be visually distinguishable from requested waypoints.
- Synthetic preview lines must use a warning style and must be hidden from finalized route views.
- Dark and light themes must each define accessible route colors.

### 25.5 Motion

- Use motion only to clarify state changes.
- Respect `prefers-reduced-motion`.
- Avoid continuous decorative map animation during route inspection.
- Search progress transitions should be smooth but not imply false precision.
- Route drawing animation may be used after validation, never before.

### 25.6 Accessibility

Target WCAG 2.2 AA:

- Keyboard-accessible forms and dialogs.
- Visible focus indicators.
- Semantic landmarks and headings.
- Accessible labels for map controls.
- Text alternatives for visual score differences.
- Minimum touch target sizes.
- Sufficient color contrast.
- Reduced-motion mode.
- Screen-reader announcements for background search progress and completion.

Map-only information must also be available in structured text.

### 25.7 Design System

Use:

- Tailwind CSS for tokens and composition.
- Radix UI primitives for accessible behavior.
- shadcn/ui source patterns where appropriate, copied into the repository and customized.
- Lucide React icons.
- Motion for React for transitions and interaction feedback.
- CSS custom properties for color, spacing, radius, elevation, and typography tokens.

Avoid:

- Generic unmodified component-library appearance.
- Excessive gradients.
- Unnecessary glass effects.
- Low-contrast gray-on-gray layouts.
- Layout shifts when search results update.

## 26. Managed Service Architecture

### 26.1 Request Flow

1. Browser submits a validated search form to a Server Action or the authenticated `/v1/searches/*` Route Handler.
2. Server Action authenticates the user and validates input with Zod.
3. Server creates the search record in Neon.
4. Server sends an event to Inngest Cloud.
5. Inngest executes bounded candidate-generation and provider-request steps.
6. Provider responses are written to Vercel Blob before parsing.
7. Parsed routes pass automatic validation.
8. Neon is updated transactionally.
9. Browser receives progress through polling, server-sent updates, or managed realtime integration.
10. Only validated routes appear in results.

### 26.2 Background Workflow Functions

Required workflows:

- `search/city.requested`
- `search/recommendations.requested`
- `search.cancelled`
- `route/revalidation.requested`
- `route/export.requested`
- `provider/data-version.changed`, only for providers with a reliable data-version signal

Each workflow must:

- Be idempotent.
- Use deterministic event identifiers.
- Persist progress after bounded steps.
- Respect provider rate limits.
- Retry only transient errors.
- Stop after cancellation.
- Never publish partially validated routes.

### 26.3 Managed Database

Use Neon PostgreSQL with:

- Connection pooling suitable for serverless functions.
- Drizzle ORM.
- Versioned migrations.
- Foreign keys.
- Transactions for validation and publication.
- Row ownership checks.
- Indexed search status and route lookups.

SQLite is not part of the production architecture.

### 26.4 Managed Object Storage

Use Vercel Blob for:

- Original provider responses only for the retention period permitted by the provider-policy record.
- Sanitized uploaded shapes when persistence is required.
- Generated GPX files.
- Optional route-preview images.

Every object must have:

- Content hash.
- MIME type.
- Size.
- Owner or search association.
- Retention state.
- Provider-policy expiration timestamp where applicable.
- Creation timestamp.

Private route artifacts must not use publicly guessable permanent URLs.

### 26.5 Authentication

Use Clerk:

- Email and supported social login.
- Protected application routes.
- Server-side session verification.
- User-scoped searches and exports.
- Organization support only if required later.

Authorization must be enforced server-side for every search, route, response, and export.

### 26.6 Managed Routing and Mapping

Mapbox is the reference provider:

- Mapbox GL JS for maps.
- Mapbox Search for city autocomplete and geocoding.
- Mapbox Directions API for canonical routes.
- Mapbox vector-tile products only where licensing permits server-side candidate analysis.

Provider tokens:

- Public map token may be browser-exposed only with URL and scope restrictions.
- Secret routing token must remain server-only.
- Tokens must use minimum scopes.
- Development, preview, and production environments must use separate tokens.

### 26.7 Candidate Street Analysis Without Self-Hosting

Candidate generation may use:

- Managed vector-tile road features under provider licensing.
- Managed road-feature or tile-query APIs.
- Provider Directions and nearest-road requests.
- Derived city fingerprints stored in Neon when permitted.

The application must not bulk-download or retain provider street data beyond contractual rights. If a provider does not permit the required analysis, select another managed provider rather than self-hosting data.

### 26.8 Observability

Use:

- Sentry for server and browser exceptions.
- Vercel Analytics for product usage.
- Vercel Speed Insights for Core Web Vitals.
- Structured server logs with search and route identifiers.
- Inngest dashboards for workflow attempts.
- Provider usage and cost dashboards.

Credentials and full provider URLs containing tokens must never be logged.

### 26.9 Managed API URL Registry

The application must use allowlisted HTTPS origins. Production provider URLs must come from server-side configuration and must not be accepted from browser input.

| Service | Production endpoint template | Authentication | Official documentation |
|---|---|---|---|
| Mapbox Directions v5 | `https://api.mapbox.com/directions/v5/{profile}/{coordinates}` | `access_token` query parameter | https://docs.mapbox.com/api/navigation/directions/ |
| Mapbox Geocoding v6 forward | `https://api.mapbox.com/search/geocode/v6/forward` | `access_token` query parameter | https://docs.mapbox.com/api/search/geocoding-v6/ |
| Mapbox Geocoding v6 reverse | `https://api.mapbox.com/search/geocode/v6/reverse` | `access_token` query parameter | https://docs.mapbox.com/api/search/geocoding-v6/ |
| Mapbox Search Box suggestions | `https://api.mapbox.com/search/searchbox/v1/suggest` | `access_token` plus `session_token` | https://docs.mapbox.com/api/search/search-box/ |
| Mapbox Search Box retrieval | `https://api.mapbox.com/search/searchbox/v1/retrieve/{mapbox_id}` | `access_token` plus matching `session_token` | https://docs.mapbox.com/api/search/search-box/ |
| Mapbox Styles tiles | `https://api.mapbox.com/styles/v1/{username}/{style_id}/tiles/{size}/{z}/{x}/{y}` | `access_token` query parameter | https://docs.mapbox.com/api/maps/styles/ |
| Mapbox Vector Tiles v4 | `https://api.mapbox.com/v4/{tileset_id}/{z}/{x}/{y}.vector.pbf` | `access_token` query parameter | https://docs.mapbox.com/api/maps/vector-tiles/ |
| Clerk Backend API | `https://api.clerk.com/v1/{resource}` | Server-side bearer-token header | https://clerk.com/docs/reference/backend-api |
| Neon management API | `https://console.neon.tech/api/v2/{resource}` | Server-side bearer-token header | https://api-docs.neon.tech/reference/getting-started-with-neon-api |
| Neon PostgreSQL | `postgresql://{role}:{password}@{endpoint}-pooler.{region}.aws.neon.tech/{database}?sslmode=require` | PostgreSQL credentials | https://neon.tech/docs/connect/connect-from-any-app |
| Inngest event API | `https://api.inngest.com/v1/events` | Inngest event key | https://www.inngest.com/docs/events/creating-an-event-key |
| Inngest application callback | `https://{application-domain}/api/inngest` | Inngest request signature | https://www.inngest.com/docs/frameworks/nextjs |
| Vercel REST API | `https://api.vercel.com/{resource}` | Server-side bearer-token header | https://vercel.com/docs/rest-api |
| Vercel Blob | SDK-managed through `@vercel/blob`; object host `*.blob.vercel-storage.com` | Vercel OIDC or Blob read/write token | https://vercel.com/docs/storage/vercel-blob |
| Upstash Redis REST | Value supplied as `UPSTASH_REDIS_REST_URL`, normally `https://{database}.upstash.io` | Server-side bearer-token header | https://upstash.com/docs/redis/features/restapi |
| Upstash QStash v2 | `https://qstash.upstash.io/v2` | Server-side bearer-token header | https://upstash.com/docs/qstash/overall/getstarted |
| Sentry management API | `https://sentry.io/api/0/{resource}` | Server-side bearer-token header | https://docs.sentry.io/api/ |
| Sentry event ingest | `https://o{org_id}.ingest.{region}.sentry.io/api/{project_id}/envelope/` | Sentry DSN public key | https://docs.sentry.io/product/sentry-basics/dsn-explainer/ |

Provider-specific paths and versions must be reviewed before every major integration upgrade. The application must not silently fall back to a different API version.

### 26.10 Managed Routing Provider Options

Mapbox Directions is the primary reference provider. The following managed alternatives may implement the routing-provider interface:

| Provider | Production endpoint | Key mechanism | Production policy | Official documentation |
|---|---|---|---|---|
| Mapbox Directions | `https://api.mapbox.com/directions/v5/{profile}/{coordinates}` | `access_token` | Approved reference provider | https://docs.mapbox.com/api/navigation/directions/ |
| GraphHopper Directions Cloud | `https://graphhopper.com/api/1/route` | `key` query parameter | Paid production plan required | https://docs.graphhopper.com/ |
| HERE Routing v8 | `https://router.hereapi.com/v8/routes` | `apikey` query parameter or enterprise OAuth | Approved managed alternative | https://www.here.com/docs/bundle/routing-api-v8-api-reference/page/index.html |
| Google Routes API | `POST https://routes.googleapis.com/directions/v2:computeRoutes` | `X-Goog-Api-Key` header | Approved managed alternative | https://developers.google.com/maps/documentation/routes/overview |
| TomTom Orbis Routing | `https://api.tomtom.com/maps/orbis/routing/calculateRoute/{locations}/json` | `key` query parameter | Use current Orbis API, not legacy v1 for new work | https://developer.tomtom.com/routing-api/documentation/tomtom-orbis-maps/v2/product-information/introduction |
| openrouteservice hosted | `https://api.openrouteservice.org/v2/directions/{profile}` | `Authorization` header or `api_key` | Free public tier prohibited for production; enterprise agreement required | https://openrouteservice.org/dev/#/api-docs |

Every provider adapter must define:

- Supported travel modes.
- Maximum waypoint count.
- Maximum request size.
- Full-geometry option.
- Geometry encoding and precision.
- Alternative-route support.
- Snapped-waypoint fields.
- Rate-limit response behavior.
- Data-version metadata availability.
- Data-version change-signal availability.
- Search-area geometry capabilities: polygon, bounding box, or neither.
- Paid-plan and retention requirements.

### 26.11 Mapbox Endpoint Requirements

The reference route request is:

```text
GET https://api.mapbox.com/directions/v5/{profile}/{lon1},{lat1};{lon2},{lat2};...
    ?alternatives=true
    &geometries=geojson
    &overview=full
    &steps=true
    &access_token={server_token}
```

Profiles may include:

- `mapbox/driving-traffic`
- `mapbox/driving`
- `mapbox/walking`
- `mapbox/cycling`

The server adapter must verify current Mapbox waypoint and option limits from official documentation. Limits must be stored as provider capabilities rather than duplicated as unchecked constants across application code.

For the reference Mapbox Directions integration, the capability registry must enforce a maximum of **25 coordinates in one route request**, including origin and destination, unless current official documentation for the selected profile explicitly permits another limit. The application must not submit the 26th coordinate, split the journey, or stitch responses.

This ceiling means that a Mapbox candidate can use at most 25 routing control points even when the target shape contains thousands of sample points. The complete provider geometry may contain many more coordinates, but those coordinates are provider output rather than application-selected waypoints.

City autocomplete should use one Search Box session token for one user search session:

```text
GET https://api.mapbox.com/search/searchbox/v1/suggest
    ?q={query}
    &session_token={uuid}
    &access_token={restricted_public_token}
```

The selected suggestion must be resolved through the corresponding retrieval endpoint before its coordinates or feature identity are trusted.

### 26.11.1 Provider Data-Rights Gate

Before a provider can be enabled for any capability, a reviewed provider-policy record must confirm whether its current contract permits:

- Storage duration for original route responses.
- Storage and export of route geometry.
- GPX generation from provider geometry.
- Repeated user downloads.
- Test-fixture retention.
- Caching and request deduplication.
- Derivation and storage of city street fingerprints.
- Storage of vector-tile or road-feature derivatives.
- Public route sharing.

Capability approval is granular. A provider may be approved for interactive maps but rejected for permanent route provenance or city-fingerprint generation.

The application must not assume that a free tier permits permanent storage or creation of derived datasets. Mapbox may be used for a capability only when the active terms or a separate agreement permit that capability.

Provider-policy records must contain:

- Provider.
- Product and plan.
- Terms version or review date.
- Approved capabilities.
- Maximum retention period.
- Attribution requirements.
- Reviewer.
- Next review date.

### 26.11.2 Retention-Compatible Route Behavior

When provider terms permit permanent response retention:

- Store the immutable response and canonical geometry according to the provenance model.
- Permit GPX regeneration while validation remains current.

When provider terms permit only temporary retention:

- Store the response only until the approved expiration timestamp.
- Retain non-reversible hashes, request metadata, scores, and audit events only when permitted.
- Remove expired provider geometry from Blob and database references.
- Mark existing GPX exports expired according to policy.
- Re-submit the complete waypoint request before a new GPX export.
- Treat the new provider response as a new route version with new hashes, geometry, validation, and scores.

When terms prohibit GPX export, persistent geometry, or required derived data, the provider must be disabled for that capability. The application must not weaken provenance checks to preserve provider compatibility.

### 26.11.3 Demo and Production Modes

The managed free-plan stack is a development and non-commercial demonstration configuration.

`demo` mode:

- Uses only capabilities permitted by each free plan.
- Disables permanent provenance, public sharing, or city-fingerprint persistence when provider terms do not permit them.
- May expire routes and GPX exports after the permitted retention period.
- Must still never fabricate route geometry.

`production` mode:

- Requires commercial-use rights.
- Requires contractual rights for the enabled retention, export, and derived-data features.
- Requires paid managed plans when free terms are insufficient.
- Must fail deployment validation when required rights are not recorded.

Feature B may be enabled only when the selected managed provider permits the required road-feature analysis and storage of derived city fingerprints. Otherwise, city recommendation remains disabled rather than using unlicensed data.

Production launch must be blocked unless:

- At least one approved routing provider permits canonical geometry use, GPX export, and the configured provenance-retention lifecycle.
- At least one approved managed data provider permits the analysis and derived metadata required by Feature B.
- Every enabled optional provider endpoint is present in the managed API URL registry and has its own data-rights review.

### 26.12 Environment Variable Contract

Required reference variables:

```text
# Public browser configuration
NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN=
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
NEXT_PUBLIC_SENTRY_DSN=

# Server-only provider credentials
MAPBOX_SECRET_ACCESS_TOKEN=
CLERK_SECRET_KEY=
DATABASE_URL=
INNGEST_EVENT_KEY=
INNGEST_SIGNING_KEY=
BLOB_READ_WRITE_TOKEN=
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
SENTRY_DSN=
```

Optional management, queue, and routing-provider variables:

```text
NEON_API_KEY=
QSTASH_URL=https://qstash.upstash.io/v2
QSTASH_TOKEN=
SENTRY_AUTH_TOKEN=
GRAPHHOPPER_API_KEY=
HERE_API_KEY=
GOOGLE_MAPS_API_KEY=
TOMTOM_API_KEY=
ORS_API_KEY=
```

Rules:

- Only values intentionally prefixed with `NEXT_PUBLIC_` may enter browser bundles.
- The browser Mapbox token must use restricted scopes and allowed URLs.
- Canonical routing requests should use the server-only token.
- `DATABASE_URL` and all secret keys must be read only from server modules.
- Missing required variables must fail deployment validation.
- Preview and production environments must use separate provider projects and keys.

### 26.13 Managed Rate Limiting

Use Upstash Redis REST with `@upstash/ratelimit` for:

- Search creation limits.
- GPX export limits.
- City autocomplete abuse controls where application-side limiting is appropriate.
- Per-user managed-provider cost budgets.
- Idempotency and short-lived request deduplication.

Upstash QStash is optional because Inngest already provides the primary durable workflow system. It may be used only for independent scheduled HTTP delivery or provider failover tasks; it must not duplicate the same job responsibility as Inngest.

### 26.14 URL and Credential Security

- Construct provider URLs with `URL` and `URLSearchParams`.
- Never concatenate untrusted input into provider origins or paths.
- Allowlist provider hosts.
- Redact token query parameters before logging.
- Do not persist URLs containing credentials.
- Store a canonical request document with credentials removed.
- Set provider request timeouts.
- Disable automatic redirects to non-allowlisted hosts.
- Validate provider TLS certificates through the platform defaults.
- Do not proxy arbitrary browser-supplied URLs.

### 26.15 Free Plan Eligibility Matrix

The following services have a documented zero-cost plan or free usage allowance as of **2026-07-13**. Pricing and quotas may change; the official pricing page must be checked before account creation and before every production release.

| Service | Free option | Card or billing account | Production/commercial caveat | Official pricing |
|---|---|---|---|---|
| Mapbox Maps | Free monthly map-load allowance | Billing instrument may be required | Commercial use allowed within terms and quota | https://www.mapbox.com/pricing |
| Mapbox Search Box | Free monthly search-session allowance | Billing instrument may be required | Session allowance is substantially smaller than general geocoding allowance | https://www.mapbox.com/pricing |
| Mapbox Geocoding | Free monthly request allowance | Billing instrument may be required | Commercial use allowed within terms and quota | https://www.mapbox.com/pricing |
| Mapbox Directions | Free monthly request allowance | Billing instrument may be required | Commercial use allowed within terms and quota | https://www.mapbox.com/pricing |
| GraphHopper Directions Cloud | Free daily credit allowance | No card normally required | Free plan is non-commercial; paid plan required for commercial production | https://www.graphhopper.com/pricing/ |
| HERE Routing v8 | Free Limited/Freemium plan | No card normally required | Confirm current quota and excluded use cases before launch | https://www.here.com/get-started/pricing |
| Google Routes API | Per-SKU monthly free usage allowance | Google Cloud billing account required | Commercial use allowed; usage beyond allowance is billed | https://developers.google.com/maps/billing-and-pricing/overview |
| TomTom Orbis Routing | Free monthly request allowance | No card normally required | Commercial use is permitted within published terms | https://docs.tomtom.com/pricing |
| openrouteservice hosted | Free Standard plan | No card normally required | Free hosted plan is for development/non-production use; self-hosted commercial fallback is prohibited | https://openrouteservice.org/plans/ |
| Clerk | Free plan | No card normally required | Suitable for initial production within free limits | https://clerk.com/pricing |
| Neon | Free plan | No card normally required | No production SLA; storage and compute limits require monitoring | https://neon.tech/pricing |
| Inngest Cloud | Free Hobby plan | No card normally required | Limited concurrency and trace retention; app provenance remains in Neon/Blob | https://www.inngest.com/pricing |
| Vercel Hosting | Free Hobby plan | No card normally required | Personal and non-commercial use only; commercial production requires a paid plan | https://vercel.com/pricing |
| Vercel Blob | Free allowance through Hobby | No card normally required | Inherits Vercel Hobby non-commercial restriction | https://vercel.com/pricing |
| Upstash Redis | Free plan | No card normally required | No free-tier SLA; enforce degradation-safe rate limiting | https://upstash.com/pricing/redis |
| Upstash QStash | Free plan | No card normally required | Low daily message allowance; optional because Inngest is primary | https://upstash.com/pricing/qstash |
| Sentry Cloud | Free Developer plan | No card normally required | Limited events, replays, retention, and seats | https://sentry.io/pricing/ |

No service may be added to the approved architecture unless its specification entry includes:

- Managed production endpoint.
- Authentication method.
- Official documentation URL.
- Official pricing URL.
- Confirmed zero-cost plan or allowance.
- Billing-card requirement.
- Commercial-use restriction.
- Free quota and retention limitations.

### 26.16 Free Development Stack

The application must be runnable for development and non-commercial MVP demonstration using only managed free plans:

| Concern | Free-plan selection |
|---|---|
| Hosting | Vercel Hobby |
| Authentication | Clerk Free |
| Database | Neon Free |
| Background workflows | Inngest Hobby |
| Object storage | Vercel Blob Hobby allowance |
| Maps, geocoding, and reference routing | Mapbox free allowances |
| Alternative provider adapter testing | TomTom Orbis free allowance; its routes remain independent candidates and never validate or modify Mapbox geometry |
| Rate limiting | Upstash Redis Free |
| Monitoring | Sentry Developer |

The application must expose configurable quotas so the free development stack cannot accidentally exceed provider allowances.

For commercial production:

- Vercel Hobby and Vercel Blob Hobby must be upgraded or replaced by another audited managed provider whose free commercial terms are acceptable.
- GraphHopper Free and openrouteservice Standard must not be used.
- Paid upgrades do not permit self-hosting; the managed-service rule remains mandatory.

### 26.17 No Self-Hosting Compliance Matrix

| Capability | Approved managed service | Explicitly prohibited fallback |
|---|---|---|
| Web hosting | Vercel managed platform | Local server, VM, container host, Kubernetes |
| Authentication | Clerk Cloud | Self-operated identity server |
| Database | Neon Cloud | Locally or privately operated PostgreSQL |
| Workflows | Inngest Cloud | Self-operated queue or Inngest server |
| Blob storage | Vercel Blob | MinIO or self-operated object storage |
| Maps and tiles | Mapbox APIs | Self-operated tile server |
| Routing | Mapbox, TomTom, HERE, Google, or another approved hosted API | OSRM, GraphHopper, Valhalla, or ORS server operated by the application team |
| Rate limiting | Upstash Redis REST | Self-operated Redis |
| Monitoring | Sentry Cloud | Self-operated Sentry |

Only HTTPS calls to the approved managed endpoints may provide production infrastructure capabilities. Open-source libraries may run inside Next.js functions for local calculations, but they must not become long-running hosted infrastructure.

## 27. Dependency Baseline

### 27.1 Version Policy

Versions below were queried from npm registry metadata on **2026-07-13**.

Use exact versions in `package.json`; do not use `^`, `~`, `*`, or unbounded tags in committed manifests. Commit `pnpm-lock.yaml`.

Node.js must use the latest production-supported LTS release rather than an unsupported current release. The baseline is Node.js `24.18.0` LTS. Node.js `26.5.0` was newer on the query date but is not selected as the production baseline because managed hosting and ecosystem support must be verified before adopting a non-LTS current release.

### 27.2 Application Dependencies

| Package | Version |
|---|---:|
| `next` | `16.2.10` |
| `react` | `19.2.7` |
| `react-dom` | `19.2.7` |
| `typescript` | `7.0.2` |
| `tailwindcss` | `4.3.2` |
| `zod` | `4.4.3` |
| `@tanstack/react-query` | `5.101.2` |
| `drizzle-orm` | `0.45.2` |
| `@neondatabase/serverless` | `1.1.0` |
| `next-safe-action` | `8.5.5` |
| `react-hook-form` | `7.81.0` |
| `@hookform/resolvers` | `5.4.0` |
| `@clerk/nextjs` | `7.5.17` |
| `inngest` | `4.12.1` |
| `@vercel/blob` | `2.6.1` |
| `@upstash/redis` | `1.38.0` |
| `@upstash/ratelimit` | `2.0.8` |
| `@upstash/qstash` | `2.11.1` |
| `mapbox-gl` | `3.26.0` |
| `@mapbox/search-js-react` | `1.5.1` |
| `@mapbox/polyline` | `1.2.1` |
| `@mapbox/vector-tile` | `3.0.0` |
| `pbf` | `5.1.2` |
| `@turf/turf` | `7.3.5` |
| `fast-xml-parser` | `5.10.0` |
| `lucide-react` | `1.24.0` |
| `motion` | `12.42.2` |
| `@radix-ui/react-dialog` | `1.1.19` |
| `@radix-ui/react-dropdown-menu` | `2.1.20` |
| `class-variance-authority` | `0.7.1` |
| `clsx` | `2.1.1` |
| `tailwind-merge` | `3.6.0` |
| `sonner` | `2.0.7` |
| `next-themes` | `0.4.6` |
| `sharp` | `0.35.3` |
| `server-only` | `0.0.1` |
| `pino` | `10.3.1` |
| `@sentry/nextjs` | `10.65.0` |
| `@vercel/analytics` | `2.0.1` |
| `@vercel/speed-insights` | `2.0.0` |

The reference implementation uses `@neondatabase/serverless` as the Drizzle database driver. A different compatible driver may replace it through an architecture decision, but multiple PostgreSQL drivers must not be installed without a demonstrated need.

### 27.3 Development Dependencies

| Package | Version |
|---|---:|
| `pnpm` | `11.12.0` |
| `eslint` | `10.7.0` |
| `eslint-config-next` | `16.2.10` |
| `eslint-plugin-tailwindcss` | `4.1.0` |
| `prettier` | `3.9.5` |
| `postcss` | `8.5.19` |
| `drizzle-kit` | `0.31.10` |
| `vitest` | `4.1.10` |
| `@playwright/test` | `1.61.1` |
| `@types/node` | `24.13.3` |
| `@types/react` | `19.2.17` |
| `@types/react-dom` | `19.2.3` |

`@types/node` uses the latest compatible Node.js 24 release rather than the incompatible latest major.

### 27.4 Latest-Version Enforcement

Before initial installation and every production release:

1. Verify that every pinned version in this baseline exists in the configured registry.
2. Query npm registry `latest` dist-tags.
3. Confirm Node.js LTS and Vercel runtime support.
4. Run `pnpm outdated`.
5. Update this baseline and `package.json` together to the latest mutually compatible stable versions.
6. Regenerate the lockfile.
7. Run type checks, lint, unit, integration, accessibility, and end-to-end tests.
8. Record dependency versions in release metadata.

An agent must not silently substitute a missing package version. It must update the specification baseline or record an approved architecture decision before installation.

Use Renovate or Dependabot for weekly update pull requests. Major updates must not auto-merge without compatibility testing.

The requirement to use recent dependencies does not permit:

- Alpha, beta, release-candidate, canary, or nightly versions by default.
- Versions unsupported by Vercel.
- Incompatible type definitions.
- Blind upgrades that break route validation or GPX integrity.

## 28. Data Model for Managed PostgreSQL

### 28.1 Core Tables

- `users`
- `cities`
- `city_catalogs`
- `shapes`
- `shape_versions`
- `searches`
- `search_progress`
- `candidate_placements`
- `waypoint_proposals`
- `provider_requests`
- `provider_responses`
- `provider_routes`
- `provider_policy_records`
- `validation_runs`
- `validation_stage_results`
- `route_scores`
- `saved_routes`
- `exports`
- `audit_events`

### 28.2 Ownership

Every user-created record must include an owner identifier. Server queries must constrain by authenticated user before returning:

- Shapes.
- Searches.
- Routes.
- Provider responses.
- Exports.

### 28.3 Provider Response Storage

The database stores:

- Blob object reference.
- SHA-256 hash.
- Provider.
- Request fingerprint.
- Provider status.
- Geometry format.
- Route index.
- Creation timestamp.

Large raw responses should remain in Blob storage rather than PostgreSQL.

### 28.4 Search Progress

Progress records must contain:

- Phase.
- Screened and routed counts.
- Provider request count.
- Valid route count.
- Rejection count.
- Budget consumption.
- Last completed workflow step.
- Cancellation state.
- User-safe status message.

## 29. Web Security and Privacy

### 29.1 Input Security

- Sanitize SVG uploads server-side.
- Reject scripts, event handlers, external references, embedded HTML, and remote resources.
- Enforce MIME, extension, size, path-count, and coordinate-count limits.
- Generate raster previews server-side from sanitized content.
- Never render unsanitized SVG with `dangerouslySetInnerHTML`.

### 29.2 API Security

- Authenticate protected Server Actions and Route Handlers.
- Validate all input with shared Zod schemas.
- Apply user, IP, and provider-cost rate limits using a managed service.
- Use idempotency keys for search and export creation.
- Reject client-provided route geometry.
- Use CSRF-safe framework mechanisms and same-site cookies.

### 29.3 Secret Management

- Store secrets in Vercel environment variables or managed secret storage.
- Use separate values per environment.
- Mark server-only modules with `server-only`.
- Prevent secret-prefixed environment variables from using `NEXT_PUBLIC_`.
- Rotate compromised tokens immediately.

### 29.4 Content Security Policy

Define a CSP that permits only required:

- Application scripts and styles.
- Mapbox resources.
- Clerk resources.
- Sentry reporting.
- Managed analytics.
- Blob downloads.

Avoid `unsafe-eval` in production. Any required provider exception must be documented and minimized.

### 29.5 Privacy

- Current location is optional.
- Routes are private by default.
- Sharing requires explicit action.
- Precise location must not be sent to analytics.
- Provider requests must contain only route-required data.
- Retention and account deletion must cover Neon, Blob, Clerk, and monitoring systems.

## 30. Performance and Cost Controls

### 30.1 Web Performance

Targets:

- Largest Contentful Paint below 2.5 seconds at the 75th percentile.
- Interaction to Next Paint below 200 milliseconds at the 75th percentile.
- Cumulative Layout Shift below 0.1.
- Initial route pages usable before map initialization completes.

### 30.2 Bundle Control

- Dynamically import Mapbox GL.
- Avoid shipping server geometry libraries to the browser.
- Analyze bundles in CI.
- Load route geometry only when required.
- Use simplified display copies only for map rendering; retain canonical geometry server-side.

### 30.3 Provider Cost Controls

- Cap provider requests per search.
- Estimate cost before starting large recommendation searches.
- Require user confirmation for high-cost searches.
- Cache compatible provider responses by request fingerprint where provider terms permit.
- Deduplicate concurrent identical requests.
- Enforce per-user daily and monthly quotas.
- Alert on abnormal usage.

### 30.4 Workflow Limits

Each workflow must define:

- Maximum cities screened.
- Maximum cities routed.
- Maximum candidate placements.
- Maximum refinement iterations.
- Maximum provider requests.
- Maximum execution time.
- Cancellation checks.

Partial bounded completion must be clearly labeled.

Initial demo defaults, until cost and quality benchmarks justify changes:

- Feature A: at most 12 placements, 4 refinement requests per retained placement, and 40 provider requests total.
- Feature B: screen at most 2,000 active catalog cities, fully route at most 5 cities, and issue at most 80 provider requests total.
- Stop immediately when the configured monetary, provider-quota, or execution-time budget is reached.

Production values must remain configuration-driven and require measured cost, latency, and result-quality evidence before increase.

## 31. Web Testing Strategy

### 31.1 Unit Tests

Use Vitest for:

- Shape parsing and sampling.
- Scoring.
- Provider response parsers.
- Validation stages.
- GPX serialization.
- Zod schemas.
- Authorization helpers.
- Cost and budget calculations.

### 31.2 Component Tests

Test:

- Shape editor.
- Constraint forms.
- Route cards.
- Validation badges.
- Progress indicators.
- Responsive drawers.
- Error and empty states.

### 31.3 Integration Tests

Use recorded, immutable responses from real managed-provider requests for successful route fixtures. Synthetic geometry is allowed only for rejection tests.

Test:

- Neon repositories.
- Blob integrity.
- Clerk authorization boundaries.
- Inngest idempotency.
- Managed-provider adapters.
- Route publication transactions.
- GPX export gate.

### 31.4 End-to-End Tests

Use Playwright:

- Sign in.
- Create or upload a shape.
- Resolve a city.
- Submit a search.
- Observe progress.
- View validated candidates.
- Export GPX.
- Reject access to another user's route.
- Confirm failed validation exposes no route.
- Confirm responsive mobile workflow.

### 31.5 Visual and Accessibility Tests

- Automated accessibility checks on core screens.
- Keyboard-only navigation.
- Dark and light theme snapshots.
- Mobile, tablet, and desktop visual regression.
- Reduced-motion behavior.
- Route and target-shape color differentiation.

## 32. Delivery Phases

### 32.1 Phase 1: Managed Web Foundation

- Next.js application.
- Clerk authentication.
- Neon database.
- Vercel Blob.
- Mapbox map and city search.
- Inngest workflow integration.
- Design system and responsive shell.

### 32.2 Phase 2: Safe City Shape Search

- Shape editor and upload.
- Adaptive sampling.
- Managed Directions provider adapter.
- Candidate search.
- Automatic validation.
- Route detail page.
- GPX export.

### 32.3 Phase 3: Search Quality

- Progressive waypoint refinement.
- Multiple placements, scales, and rotations.
- Candidate comparison.
- Similarity visualization.
- Cost and quota controls.

### 32.4 Phase 4: City Recommendation

- Managed city catalog.
- Licensed managed street-feature analysis.
- Bounded screening.
- Recommendation comparison.
- Honest coverage reporting.

### 32.5 Phase 5: Production Hardening

- Accessibility audit.
- Performance tuning.
- Security review.
- Provider failover policy.
- Retention automation.
- Cost alerts.
- Dependency update automation.

## 33. Web Application Definition of Done

The product is complete for its declared scope only when:

- It deploys on managed infrastructure without self-hosted production services.
- The interface is polished and responsive across supported devices.
- All route generation occurs server-side through a managed provider.
- No browser or application algorithm can create canonical route geometry.
- Every displayed route passes automatic validation.
- GPX files contain only verified provider coordinates.
- Long searches survive navigation and browser closure.
- Search coverage and limitations are visible.
- Authentication and ownership prevent cross-user data access.
- Dependency versions are current, exact, locked, and tested.
- Core Web Vitals, accessibility, and visual regression targets pass.
- Managed-service quotas, costs, and errors are observable.

## 34. City Catalog Definition

### 34.1 Required Size and Composition

Catalog version 1 must contain exactly:

- **2,000 cities worldwide**.
- **Exactly 100 cities whose ISO country code is `HU`**.
- **Exactly 1,900 cities outside Hungary**.

The worldwide entries must cover all inhabited continents:

| Continent | Non-Hungarian entries |
|---|---:|
| Africa | 300 |
| Asia | 500 |
| Europe, excluding Hungary | 400 |
| North America | 300 |
| South America | 250 |
| Oceania | 150 |
| **Total outside Hungary** | **1,900** |

The catalog must not count Budapest districts, neighborhoods, boroughs, historical settlements, abandoned places, destroyed places, or duplicate locality records as cities.

### 34.2 Authoritative Source

City entries must be defined from the managed-release import of the GeoNames data export:

- Data page: https://download.geonames.org/export/dump/
- Populated-place source: `https://download.geonames.org/export/dump/cities500.zip`
- Country metadata: `https://download.geonames.org/export/dump/countryInfo.txt`
- Format documentation: https://download.geonames.org/export/dump/readme.txt
- License information: https://www.geonames.org/faq.html
- License: Creative Commons Attribution 4.0.

The catalog specification is source-based and deterministic. The web application does not query GeoNames at runtime and does not require a self-hosted GeoNames service.

Each published catalog version must record:

- GeoNames source URLs.
- Retrieval date.
- SHA-256 hashes of downloaded source files.
- Selection algorithm version.
- Importer version.
- Attribution text.
- Generated catalog hash.

### 34.3 Eligible GeoNames Records

A record is eligible only when:

- `feature class` is `P`.
- `feature code` is one of:
  - `PPLC`
  - `PPLA`
  - `PPLA2`
  - `PPLA3`
  - `PPLA4`
  - `PPL`
- `country code` is present.
- Latitude and longitude are valid.
- Population is greater than zero for ordinary `PPL` records.
- Population may be zero for `PPLC` and `PPLA*` administrative-capital records so countries with incomplete population data can still receive representation.
- The record is not marked historical, abandoned, destroyed, a section of another populated place, or another non-city subdivision.

`PPLX` records are explicitly excluded. This prevents Budapest districts and similar subdivisions from consuming the Hungarian quota.

### 34.4 Duplicate Resolution

Before selection:

1. Group records by country code and normalized name.
2. Treat records within 10 kilometers as potential duplicates.
3. Keep the record with the strongest feature-code rank:
   - `PPLC`
   - `PPLA`
   - `PPLA2`
   - `PPLA3`
   - `PPLA4`
   - `PPL`
4. On equal rank, keep the record with the larger population.
5. On another tie, keep the smaller GeoNames ID.

Name normalization for duplicate detection must:

- Apply Unicode NFKD normalization.
- Remove combining marks.
- Convert to lowercase.
- Normalize punctuation and whitespace.
- Preserve the original Unicode display name separately.

### 34.5 Hungarian City Membership

The 100 Hungarian entries are uniquely defined as:

1. Filter eligible, deduplicated records to `country_code = 'HU'`.
2. Sort by:
   - Population descending.
   - Feature-code rank ascending.
   - Normalized display name ascending.
   - GeoNames ID ascending.
3. Select the first 100 records.

This rule includes actual populated cities and excludes Budapest districts because `PPLX` is ineligible.

The published catalog manifest must include all 100 resulting GeoNames IDs. The release process must fail if:

- Fewer than 100 eligible Hungarian cities exist.
- Any selected record is not `HU`.
- Any selected record has an excluded feature code.
- Duplicate checks reduce the count below 100.

### 34.6 Worldwide Non-Hungarian Membership

The remaining 1,900 cities are uniquely defined by a continent-balanced, country-round-robin algorithm.

For each continent quota:

1. Exclude Hungary.
2. Assign each country to the continent code recorded in GeoNames `countryInfo.txt`; transcontinental countries use that single source value for reproducibility.
3. Group eligible, deduplicated records by ISO country code.
4. Sort each country's cities by:
   - Feature-code rank ascending.
   - Population descending.
   - Normalized name ascending.
   - GeoNames ID ascending.
5. Sort country groups by ISO country code.
6. Execute repeated rounds.
7. In each round, take the next unselected city from every non-empty country group.
8. Stop when the continent quota is reached.
9. If the final round would exceed the quota, take countries in ISO-code order until the quota is full.

This gives broad geographic coverage while still prioritizing capitals, administrative centers, and high-population cities.

The importer must fail rather than silently change quotas when a continent lacks sufficient eligible records.

### 34.7 City Catalog Manifest

The exact entries of a published catalog are defined by its immutable manifest:

```json
{
  "catalogId": "world-cities-v1",
  "cityCount": 500,
  "hungaryCount": 100,
  "selectionAlgorithmVersion": "1",
  "source": {
    "name": "GeoNames",
    "citiesUrl": "https://download.geonames.org/export/dump/cities500.zip",
    "countryInfoUrl": "https://download.geonames.org/export/dump/countryInfo.txt",
    "retrievedAt": "release timestamp",
    "citiesSha256": "source-file-hash",
    "countryInfoSha256": "source-file-hash"
  },
  "entries": [
    {
      "ordinal": 1,
      "geonamesId": 0,
      "countryCode": "HU"
    }
  ],
  "manifestSha256": "catalog-hash"
}
```

The `entries` array must contain exactly 2,000 records in deterministic catalog order. The abbreviated example above does not represent production data.

### 34.8 City Record Schema

Each city record must contain:

| Field | Purpose |
|---|---|
| `id` | Internal UUID. |
| `catalogId` | Catalog version. |
| `ordinal` | Stable position from 1 through 2,000. |
| `geonamesId` | Stable GeoNames identifier. |
| `displayName` | Original Unicode city name. |
| `asciiName` | GeoNames ASCII name. |
| `normalizedName` | Search-normalized name. |
| `alternateNames` | Bounded list of localized aliases. |
| `countryCode` | ISO alpha-2 country code. |
| `countryName` | Display country name. |
| `continentCode` | Catalog continent grouping. |
| `admin1Code` | First-order administrative code. |
| `admin2Code` | Second-order administrative code where present. |
| `latitude` | GeoNames latitude. |
| `longitude` | GeoNames longitude. |
| `population` | Source population used for selection. |
| `featureCode` | Eligible GeoNames feature code. |
| `timezone` | GeoNames timezone identifier. |
| `managedMapProviderId` | Resolved provider place identifier when available. |
| `managedBoundaryRef` | Reference to provider-returned boundary metadata. |
| `routingModes` | Provider-supported travel modes. |
| `status` | `active`, `temporarily_unavailable`, or `retired`. |

### 34.9 Boundary Resolution

GeoNames coordinates define catalog membership but not route-search boundaries.

For every selected city:

1. Resolve the city using the managed geocoding provider.
2. Store the provider feature ID, center, bounding box, and result confidence.
3. Retrieve a provider-supported administrative or place boundary when licensing permits.
4. Store only the boundary reference or permitted derived geometry and classify it as `polygon` or `bounding_box`.
5. Flag ambiguous or unmatched cities for catalog review.

A city must not become `active` until its managed provider identity and usable search area are validated. Polygon containment is used when a polygon exists; otherwise bounding-box containment is used and the UI must disclose the less precise search area.

## 35. Shape Catalog Definition

### 35.1 Required Size

Catalog version 1 must contain every canonical SVG entry from:

- npm package: `lucide-static`
- Pinned version: `1.24.0`
- Registry package URL: https://www.npmjs.com/package/lucide-static
- Tarball: `https://registry.npmjs.org/lucide-static/-/lucide-static-1.24.0.tgz`
- License: ISC.

The source package was observed to contain 1,995 SVG entries during specification review. The authoritative count must be derived from the pinned tarball during catalog publication and must be at least 1,000.

The specification defines entries by immutable package version and file membership rather than embedding every SVG document into this Markdown file.

### 35.2 Exact Shape Membership

The exact shape entries are:

1. Every file matching `package/icons/*.svg` in `lucide-static@1.24.0`.
2. One catalog entry per SVG file.
3. Entry ID equal to the lowercase filename without `.svg`.
4. Catalog order equal to Unicode code-point ascending order of entry ID.

The release manifest must contain:

- One entry ID for every valid `package/icons/*.svg` file in the pinned tarball.
- `shapeCount` equal to the number of those manifest entries.
- At least 1,000 valid entries.
- Original file SHA-256 for each entry.
- Sanitized SVG SHA-256.
- Parsed geometry SHA-256.
- Package tarball SHA-256.
- Importer and sanitizer versions.

The importer must fail if the pinned package does not contain at least 1,000 valid shapes.

### 35.3 SVG Validation

Each shape must:

- Parse as SVG.
- Use a valid `viewBox`.
- Contain finite vector coordinates.
- Contain at least one drawable path, line, polyline, polygon, circle, ellipse, or rectangle.
- Contain no script.
- Contain no event handler.
- Contain no external resource.
- Contain no embedded HTML.
- Contain no remote URL.

The sanitizer may normalize presentation attributes but must preserve geometry.

### 35.4 Shape Geometry Conversion

Each SVG entry must be converted into a normalized route-search representation:

- Flatten SVG transforms.
- Convert supported primitives to polylines.
- Approximate curves using adaptive subdivision.
- Preserve stroke boundaries.
- Normalize coordinates to a `0..1` logical box.
- Record source aspect ratio.
- Detect closed strokes.
- Detect endpoints, corners, cusps, intersections, and inflection points.
- Generate coarse, medium, high, and audit sample levels.

The original sanitized SVG and normalized geometry must have separate hashes.

### 35.5 Shape Categories and Search

Categories and keywords are defined from:

- `lucide-static@1.24.0/package/tags.json`.
- Deterministic filename tokenization.
- Curated application categories stored as versioned metadata.

Suggested categories:

- Animals.
- Nature.
- People.
- Vehicles.
- Buildings and places.
- Food and drink.
- Sports.
- Symbols.
- Technology.
- Tools.
- Weather.
- Communication.
- Arrows and navigation.
- Shapes and geometry.
- Holidays and culture.

User-facing search must support:

- Shape name.
- Filename tokens.
- Lucide tags.
- Curated category.
- Stroke count.
- Closed/open shape.
- Complexity range.

### 35.6 Shape Record Schema

| Field | Purpose |
|---|---|
| `id` | Stable filename-derived shape ID. |
| `catalogId` | Shape catalog version. |
| `ordinal` | Stable catalog order. |
| `displayName` | Human-readable title generated from the ID. |
| `categoryIds` | Curated categories. |
| `tags` | Lucide and generated search tags. |
| `sourcePackage` | `lucide-static`. |
| `sourceVersion` | `1.24.0`. |
| `license` | `ISC`. |
| `sourceSha256` | Original SVG hash. |
| `sanitizedSha256` | Sanitized SVG hash. |
| `geometrySha256` | Normalized geometry hash. |
| `svgBlobRef` | Managed immutable sanitized SVG reference. |
| `geometryBlobRef` | Managed immutable geometry reference. |
| `thumbnailBlobRef` | Managed preview reference. |
| `strokeCount` | Number of disconnected strokes. |
| `samplePointCount` | High-density sample count. |
| `complexityScore` | Normalized search-complexity metric. |
| `aspectRatio` | Original shape aspect ratio. |
| `isClosed` | Whether all principal strokes are closed. |
| `status` | `active`, `hidden`, or `retired`. |

### 35.7 Shape Catalog Manifest

```json
{
  "catalogId": "lucide-shapes-1.24.0",
  "shapeCount": 1995,
  "sourcePackage": "lucide-static",
  "sourceVersion": "1.24.0",
  "license": "ISC",
  "tarballUrl": "https://registry.npmjs.org/lucide-static/-/lucide-static-1.24.0.tgz",
  "tarballSha256": "source-tarball-hash",
  "entries": [
    {
      "ordinal": 1,
      "id": "a-arrow-down",
      "sourceSha256": "svg-hash",
      "geometrySha256": "geometry-hash"
    }
  ],
  "manifestSha256": "catalog-hash"
}
```

The production manifest must contain every valid entry from the pinned tarball. The shown count is the expected reviewed value; publication uses the derived manifest count and fails below 1,000. The example is intentionally abbreviated.

## 36. Catalog Storage and Web Handling

### 36.1 Authoritative Storage

Neon PostgreSQL is the authoritative catalog metadata store.

Required tables:

- `catalog_versions`
- `cities`
- `city_aliases`
- `city_provider_bindings`
- `city_routing_capabilities`
- `shape_catalog_entries`
- `shape_tags`
- `shape_categories`
- `shape_category_memberships`

Large immutable assets must use managed object storage:

- City manifest JSON.
- Shape manifest JSON.
- Sanitized SVGs.
- Parsed shape geometry.
- Thumbnail assets.
- Optional compressed client search indexes.

### 36.2 Catalog Versioning

Catalogs are immutable after publication.

Each search stores:

- City catalog ID.
- Shape catalog ID.
- Selected city ID.
- Selected shape ID or uploaded shape version.
- City and shape manifest hashes.

A new source import creates a new catalog version. Existing searches continue referencing the original version.

### 36.3 Database Indexes

City indexes:

- Unique `(catalog_id, geonames_id)`.
- Unique `(catalog_id, ordinal)`.
- B-tree `(catalog_id, country_code, population DESC)`.
- B-tree `(catalog_id, continent_code)`.
- Trigram or normalized-prefix index on `normalized_name`.
- Index on `status`.

Shape indexes:

- Unique `(catalog_id, id)`.
- Unique `(catalog_id, ordinal)`.
- B-tree `(catalog_id, complexity_score)`.
- B-tree `(catalog_id, stroke_count)`.
- Inverted or relational tag index.
- Index on `status`.

The application must not require PostGIS for only 2,000 city center points. Geographic distance can be calculated for this bounded catalog using indexed latitude/longitude bounding-box filtering followed by a server-side Haversine calculation. A managed PostGIS extension may be enabled later if supported by the selected Neon plan and justified by measured need.

### 36.4 API Contracts

#### Browse Cities

`GET /api/catalogs/cities`

Parameters:

- `query`
- `country`
- `continent`
- `page`
- `pageSize`, maximum 50
- `catalogId`

Response contains metadata only. It must not contain city boundaries or road features.

#### City Detail

`GET /api/catalogs/cities/{cityId}`

Returns:

- City metadata.
- Managed provider binding.
- Routing modes.
- Boundary availability.
- Data attribution.

#### Browse Shapes

`GET /api/catalogs/shapes`

Parameters:

- `query`
- `category`
- `tags`
- `complexityMin`
- `complexityMax`
- `strokeCount`
- `page`
- `pageSize`, maximum 60
- `catalogId`

Returns thumbnail and metadata references, not high-density geometry.

#### Shape Detail

`GET /api/catalogs/shapes/{shapeId}`

Returns:

- Shape metadata.
- Sanitized SVG reference.
- Preview geometry.
- Complexity and stroke information.

High-density geometry must remain server-only until a search is submitted.

### 36.5 Client Search Indexes

Because 2,000 cities and approximately 2,000 pinned-source shapes are small bounded catalogs, the application may publish compressed, versioned client search indexes.

City client index fields:

- ID.
- Display name.
- Normalized name.
- Country code.
- Country name.
- Continent.
- Population rank.

Shape client index fields:

- ID.
- Display name.
- Category IDs.
- Tags.
- Complexity bucket.
- Stroke count.
- Thumbnail URL.

Client indexes must exclude:

- Shape high-density geometry.
- Provider credentials.
- City boundaries.
- Provider-response data.
- Search fingerprints.

Each index must:

- Be Brotli-compressed.
- Use an immutable versioned URL.
- Include an ETag.
- Use `Cache-Control: public, max-age=31536000, immutable`.
- Be loaded on demand.
- Be replaceable by server search on low-memory devices.

### 36.6 Shape Asset Packaging

The UI must not issue one request per shape when opening the shape browser.

Required strategy:

- Store shape metadata in paginated API responses.
- Generate lightweight thumbnails.
- Package thumbnails into versioned sprite sheets or bounded chunks.
- Use a maximum of 100 shapes per sprite/chunk.
- Lazy-load only visible pages.
- Fetch the individual sanitized SVG only when selected.
- Fetch server-only high-density geometry only inside background search workflows.

### 36.7 Catalog Caching

Caching layers:

1. Browser memory for the current page.
2. Browser HTTP cache for immutable catalog assets.
3. Next.js data cache for catalog metadata.
4. Upstash Redis for hot query results and rate limiting.
5. Neon as authoritative metadata.
6. Vercel Blob as immutable asset storage.

Cache keys must include catalog version and query parameters.

Catalog publication must use new immutable URLs rather than purging old catalog assets.

### 36.8 Catalog Update Workflow

Catalog refresh is an administrative managed workflow:

1. Download source data from the declared URL.
2. Verify source availability and hash.
3. Parse and validate.
4. Apply deterministic selection.
5. Validate exact counts.
6. Resolve managed-provider city bindings.
7. Generate manifests and compressed indexes.
8. Upload immutable assets.
9. Insert metadata into staging catalog tables.
10. Run integrity and performance checks.
11. Atomically mark the new catalog version active.

The previous catalog remains available for historical searches.

### 36.9 Catalog Integrity Requirements

Publication must fail unless:

- City count is exactly 2,000.
- Hungarian city count is exactly 100.
- Non-Hungarian count is exactly 1,900.
- Every continent quota is exact.
- GeoNames IDs are unique.
- City ordinals are contiguous.
- Shape count is at least 1,000.
- Shape IDs and hashes are unique.
- Shape ordinals are contiguous.
- All assets exist and match their hashes.
- Attribution and license records are present.

## 37. Catalog Performance Requirements

### 37.1 Performance Budgets

| Operation | Target |
|---|---:|
| Initial city selector interactive | Under 500 ms after panel opens |
| Local city search after index load | Under 50 ms at p95 |
| Server city search | Under 200 ms at p95 |
| Initial shape-browser metadata | Under 300 ms at p95 server time |
| Shape filtering after index load | Under 75 ms at p95 |
| Shape page transition | Under 150 ms at p95 excluding image network time |
| Individual SVG selection | Under 300 ms at p95 |
| Catalog API response | Under 100 KB compressed |
| Client city index | Target under 500 KB compressed |
| Client shape index | Target under 750 KB compressed |

### 37.2 Rendering Performance

- Virtualize shape grids when more than 120 cards are mounted.
- Do not render the entire shape catalog simultaneously.
- Use fixed thumbnail aspect-ratio containers to prevent layout shifts.
- Defer non-visible thumbnails.
- Use `content-visibility` where browser support and testing justify it.
- Memoize filter results by catalog version and normalized query.
- Run expensive fuzzy search in a Web Worker if measured main-thread work exceeds 16 milliseconds.

### 37.3 Query Performance

- Use prefix matching first.
- Apply fuzzy matching only after prefix and exact matches.
- Limit fuzzy candidate sets.
- Debounce remote search requests between 150 and 250 milliseconds.
- Abort superseded requests.
- Return no more than 50 cities or 60 shapes per page.
- Select only fields required by the current view.
- Avoid joining tags and categories into unbounded duplicate rows.

### 37.4 Background Search Performance

Catalog size must not multiply routing cost unnecessarily:

- City-shape search loads one selected city.
- Recommendation screening reads compact city fingerprints for at most 2,000 cities.
- Full managed-provider routing runs only for the configured top candidate cities.
- Shape geometry is fetched once per search and cached by geometry hash.
- City metadata and provider bindings are batched.
- Recommendation progress reports screened, shortlisted, routed, and validated counts.

### 37.5 Performance Tests

Automated tests must cover:

- Exactly 2,000 city records.
- Exactly 100 Hungarian cities.
- Shape record count equal to the pinned tarball manifest count and at least 1,000.
- Client index parse time on a representative mid-range mobile device.
- City and shape search p95 latency.
- Shape-grid scrolling with the complete pinned catalog.
- Cold and warm cache behavior.
- Catalog publication atomicity.
- Search behavior while an older catalog remains referenced.

## 38. Future Enhancements

- Collaborative route collections.
- Public route galleries with explicit privacy controls.
- Live closure-aware revalidation.
- Additional managed routing providers.
- Organization accounts.
- Community route reviews.
- Seasonal and daylight constraints.
- User-controlled trade-off sliders for likeness, distance, safety, and complexity.

## 39. Step-by-Step Agentic Development Guide

This section defines the required implementation order for autonomous or semi-autonomous coding agents. Agents must complete each exit gate before starting dependent work. Independent catalog-import work may run in parallel only after the shared schemas and storage conventions are stable.

### 39.1 Agent Operating Rules

Before changing code, an agent must:

1. Identify the current delivery step and its exit gate.
2. Read the route-integrity rules in Sections 1.1, 6.4, 6.5, 6.7, 6.12, and 12.8.
3. List the exact requirements and acceptance tests affected by the change.
4. Reuse existing domain types, validation helpers, provider adapters, and repositories.
5. Keep provider geometry server-only and reject client-supplied geometry.
6. Implement fail-closed behavior before a happy-path endpoint becomes reachable.
7. Use recorded provider fixtures only when retention rights permit them. Synthetic successful route geometry is prohibited; synthetic data may test rejection paths.
8. Run the smallest relevant tests, then the phase exit-gate tests.
9. Record architecture decisions for provider substitutions, capability changes, schema changes, or deviations from a `should` requirement.

An agent must stop and request a product or architecture decision when:

- Provider rights do not permit required storage, export, or derived analysis.
- A required provider capability is unavailable.
- A proposed change weakens route provenance, validation, or GPX equality.
- A dependency baseline cannot be installed without changing pinned versions.
- A requirement has two materially different user-visible interpretations not resolved by this document.

### 39.2 Step 0: Capability and Rights Baseline

Actions:

1. Select the development mode: `demo` or `production`.
2. Create provider-policy records for routing, maps, geocoding, boundaries, response retention, GPX export, and derived city fingerprints.
3. Probe and record provider capabilities:
   - Travel modes and exact profile mapping.
   - Maximum coordinates and request size.
   - Full-geometry format and precision.
   - Alternative-route behavior.
   - Snapped-waypoint fields.
   - Polygon and bounding-box availability.
   - Data-version and change-signal availability.
   - Rate-limit and retry semantics.
4. Verify the Node.js runtime and every pinned package version.
5. Select one database driver.
6. Set initial search, cost, retention, and freshness budgets.

Artifacts:

- Versioned provider capability configuration.
- Provider-policy records.
- Environment-variable schema.
- Dependency lockfile.
- Architecture decisions for any deviation from the reference stack.

Exit gate:

- Deployment validation fails when a required right, capability, secret, or budget is missing.
- No application feature assumes unavailable provider metadata.

### 39.3 Step 1: Managed Web Foundation

Actions:

1. Scaffold the Next.js App Router structure from Section 24.1.
2. Configure TypeScript strict mode, linting, formatting, Vitest, and Playwright.
3. Configure Clerk, Neon, Drizzle migrations, Inngest, Blob, Sentry, and Upstash.
4. Add server-only environment access and startup validation.
5. Add authentication, ownership helpers, structured logging, and route-level error boundaries.
6. Create the responsive application shell without route-generation behavior.

Exit gate:

- Authentication and cross-user authorization tests pass.
- Preview deployment starts with managed services and contains no secret in the browser bundle.
- Missing required configuration fails explicitly.

### 39.4 Step 2: Domain Contracts and State Machines

Actions:

1. Implement shared schemas for shapes, cities, constraints, provider capabilities, searches, candidate routes, validation results, and exports.
2. Implement the route states from Section 6.7 as one authoritative enum and transition function.
3. Implement search statuses and failure mappings from Sections 12.3, 12.9, and 12.10.
4. Define immutable identifiers for search, proposal, provider request, provider route version, validation run, and export.
5. Define machine-readable rejection codes before database migrations reference them.

Exit gate:

- Unit tests reject skipped, reversed, or illegal state transitions.
- `waypoint_proposal` cannot become displayable or exportable.
- `rejected` and `retired` are distinct terminal states.
- API serialization uses the same enums as persistence and workflows.

### 39.5 Step 3: Persistence and Provenance Core

Actions:

1. Create the core tables from Section 28 with ownership, foreign keys, indexes, and immutable route-version references.
2. Implement the provider-response write sequence:
   - Write the response to Blob.
   - Compute and store SHA-256.
   - Read-verify the object and hash.
   - Parse into a new provider route version.
   - Commit metadata and eligibility changes in one Neon transaction.
3. Add idempotency keys and request fingerprints.
4. Add orphaned-Blob cleanup and retention-expiration workflows.
5. Ensure private artifacts use authorized, expiring access.

Exit gate:

- Tampering, missing Blob objects, hash mismatches, duplicate events, and transaction failures expose no route.
- Failed publication leaves no eligible database record.
- Orphan cleanup is safe and idempotent.

### 39.6 Step 4: Provider Adapter

Actions:

1. Implement one reference Directions adapter behind a provider-neutral interface.
2. Map travel modes to server-side allowlisted profiles.
3. Enforce coordinate, request-size, timeout, redirect, and rate limits from the capability registry.
4. Request full provider geometry and record all route-affecting options.
5. Parse HTTP success separately from provider-level success.
6. Preserve proposed and provider-snapped waypoints.
7. Return typed provider failures without fallback geometry.

Exit gate:

- Integration fixtures cover success, no route, provider error in HTTP 200, malformed response, timeout, profile mismatch, excessive snapping, and waypoint-limit rejection.
- No client input can alter provider origin, credentials, or profile mapping.

### 39.7 Step 5: Automatic Validation and Publication

Actions:

1. Implement publication stages 1 through 8 from Section 6.12 as independently testable validators.
2. Make every stage return a typed pass or rejection result; unknown and timeout results fail closed.
3. Validate typed search-area containment using polygon or bounding-box semantics.
4. Implement the strict water, building, and access gate from Section 6.10.1.
5. Calculate route metrics from canonical provider geometry only.
6. Implement multi-stroke alignment and connector classification from Section 10.
7. Recalculate shape similarity from high-density target samples.
8. Publish `eligible_for_display` only in the final Neon transaction.

Exit gate:

- Removing any validation result, changing any provenance hash, or failing any stage prevents every display API from returning geometry.
- A route cannot appear during partial or eventually consistent writes.
- Water, building, or access conflicts without corroborating provider evidence expose no route.
- Negative validation tests in Sections 21.2 through 21.4 pass.

### 39.8 Step 6: GPX Export Gate

Actions:

1. Implement export as an on-demand workflow.
2. Check authorization, route state, provenance, provider-policy retention, and validation freshness.
3. If stale or expired, create a revalidation request and a new route version; do not revive the old version.
4. Decode the exact canonical provider geometry.
5. Serialize GPX 1.1 without smoothing, interpolation, synthetic closure, elevation, or timestamps.
6. Reparse the GPX and numerically compare every coordinate in order.
7. Store and return the GPX only after the comparison succeeds.

Exit gate:

- Coordinate alteration, response expiration, missing provenance, hash mismatch, or comparison failure produces no downloadable file.
- Exported points equal canonical provider points within the declared serialization tolerance.

### 39.9 Step 7: Minimal Feature A Service Slice

Implement the smallest complete city-shape search:

1. One approved travel mode.
2. One simple catalog shape.
3. One active city with a validated search area.
4. One deterministic placement strategy.
5. One complete waypoint proposal within provider limits.
6. One provider request.
7. Full provenance, validation, display, and GPX export.

Do not add optimization, multiple placements, product UI, or city recommendation before this server-side slice passes.

Exit gate:

- A real retained provider fixture demonstrates the complete path.
- Provider failure or impossible constraints produce a truthful no-result response.

### 39.10 Step 8: Durable Search Workflow

Actions:

1. Implement Inngest search creation, progress, cancellation, retry classification, and idempotency.
2. Persist a checkpoint after every bounded step.
3. Enforce configured request, time, quota, and monetary budgets.
4. Stop unstarted work after cancellation and prevent active work from publishing afterward.
5. Report exact screened, attempted, routed, validated, and rejected counts.

Exit gate:

- Restart, duplicate delivery, cancellation, timeout, and budget-exhaustion tests pass.
- `completed_with_limits` reports evaluated scope and never implies global optimality.
- Browser closure or navigation does not lose the durable search result.

### 39.11 Step 9: Shape Processing and Search Quality

Actions:

1. Implement sanitized SVG parsing and primitive conversion.
2. Implement adaptive sampling with coarse, medium, high, and audit levels.
3. Preserve mandatory landmarks and record sampling deviation.
4. Implement waypoint reduction and minimum-spacing rules.
5. Add placements, scales, allowed rotations, start points, and progressive refinements.
6. Submit a complete independent provider request after every waypoint change.
7. Deduplicate near-identical validated routes and retain meaningful diversity.

Exit gate:

- Sampling and reduction invariants in Section 21.1 pass.
- Search never splits and stitches provider routes.
- Cost budgets remain enforced under worst-case refinement.

### 39.12 Step 10: Product UI

Actions:

1. Build shape interpretation and confirmation.
2. Build city resolution with explicit polygon or bounding-box disclosure.
3. Build constraints with defaults matching server schemas.
4. Build durable progress and cancellation views.
5. Build route detail using only eligible geometry APIs.
6. Show scores, compromises, provider metadata, freshness basis, and warnings.
7. Build accessible responsive map alternatives and keyboard workflows.

Exit gate:

- No provisional route geometry is visible in production clients.
- Mobile, keyboard, reduced-motion, accessibility, and cross-user tests pass.
- A missing provider data version is displayed honestly rather than replaced by the route date.

### 39.13 Step 11: Catalog Import and Publication

Actions:

1. Implement deterministic GeoNames download, hashing, parsing, deduplication, quota selection, and manifest generation.
2. Resolve managed provider identities and typed search areas before city activation.
3. Implement deterministic Lucide download, hashing, sanitization, geometry conversion, tags, thumbnails, and manifest generation.
4. Publish immutable assets before atomically activating catalog metadata.
5. Generate compressed client indexes and bounded thumbnail chunks.

Exit gate:

- Exact city quotas and minimum shape counts pass.
- Re-running the importer with identical sources produces identical manifests.
- Missing assets, hash mismatches, ambiguous cities, or count drift block publication.

### 39.14 Step 12: Feature B City Recommendation

Actions:

1. Restrict screening to active cities supporting the selected mode and freshness policy.
2. Generate permitted street-derived fingerprints.
3. Screen at most the configured city budget.
4. Run the complete Feature A workflow for shortlisted cities.
5. Recommend only cities with at least one current display-eligible provider route.
6. Report exact eligible, screened, routed, validated, and incomplete counts.

Exit gate:

- Screening alone never produces a recommendation.
- Expired routes remove the city from current recommendations until revalidated.
- Partial coverage is labeled `best among searched cities`.

### 39.15 Step 13: Production Hardening and Release

Actions:

1. Complete retention deletion, account deletion, provider-policy review, cost alerts, and incident runbooks.
2. Run security, accessibility, performance, visual, integration, and end-to-end suites.
3. Verify dependency pins, provider capabilities, quotas, and commercial rights.
4. Verify all negative route-integrity and GPX tests.
5. Review observability for secrets and precise-location leakage.
6. Confirm rollback does not restore expired geometry or bypass current validation.

Exit gate:

- Sections 22 and 33 pass in full.
- Production deployment validation confirms required managed-service rights and capabilities.
- No route or GPX can be exposed through an unvalidated, stale, rejected, retired, or unauthorized code path.

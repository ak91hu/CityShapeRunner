"""HTTP routes for the GPS art route planner."""

from __future__ import annotations

import logging
import math
import unicodedata
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..agents.validation_agent import ValidationAgent
from ..logging_config import current_request_id
from ..orchestrator import generate
from ..quality import quality_bottleneck, quality_gate_report
from ..state import EvaluatedCandidate, Intent, RouteDraft, Shape, SnappedRoute, WorkflowState
from ..tools import cloudinary_gallery, geo, gpx_writer, ors_client, shape_similarity

router = APIRouter()
log = logging.getLogger(__name__)

PROMPT_MAX_LENGTH = 320


class GenerateRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=PROMPT_MAX_LENGTH,
        examples=["a heart run in Budapest, about 8km", "suggest a run in Debrecen, 10km"],
        description="Natural-language prompt describing the shape, city, sport, and optional target distance. "
        "Use 'suggest' to let AI pick the best shape for the city.",
    )

    @field_validator("prompt", mode="before")
    @classmethod
    def normalise_prompt(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        normalised = unicodedata.normalize("NFKC", value)
        if any(
            unicodedata.category(character) == "Cc" and character not in "\t\n\r"
            for character in normalised
        ):
            raise ValueError("remove unsupported control characters from the route idea")

        cleaned = " ".join(normalised.split())
        if not cleaned:
            raise ValueError("enter a route idea")
        if len(cleaned) > PROMPT_MAX_LENGTH:
            raise ValueError(
                f"keep the route idea to {PROMPT_MAX_LENGTH} characters or fewer"
            )
        if not any(character.isalnum() for character in cleaned):
            raise ValueError("include a shape, word, letter, or number to draw")
        return cleaned


class GenerateResponse(BaseModel):
    request_id: str | None = None
    prompt: str
    intent: dict | None
    shape: dict | None
    suggested_shape: str | None = None
    suggestion_reason: str | None = None
    requested_shape: str | None = None
    fit_decision: dict | None = None
    validation: dict | None
    distance_km: float | None
    snapped: bool | None
    iterations: int
    candidate_count: int = 0
    preflight_count: int = 0
    below_threshold: bool
    errors: list[str]
    history: list[dict]
    gpx: str | None
    tcx: str | None
    file_paths: dict
    points_preview: list[list[float]]
    ideal_preview: list[list[float]] = Field(default_factory=list)
    landmark_preview: list[list[float]] = Field(default_factory=list)
    candidates: list[dict] = Field(default_factory=list)
    candidate_audit: list[dict] = Field(default_factory=list)
    candidate_summary: dict = Field(default_factory=dict)
    preflight_candidates: list[dict] = Field(default_factory=list)
    route_verification: dict | None = None
    route_details: dict | None = None
    gallery_publish_token: str | None = None


class EditedRouteRequest(BaseModel):
    control_points: list[list[float]] = Field(..., min_length=2, max_length=200)
    reference_points: list[list[float]] = Field(default_factory=list, max_length=500)
    sport: Literal["run", "bike"] = "run"
    closed: bool = False
    target_distance_km: float | None = Field(default=None, gt=0, le=500)
    name: str = Field(default="Edited GPS art route", min_length=1, max_length=120)
    shape_name: str = Field(default="edited", min_length=1, max_length=80)

    @field_validator("name", "shape_name")
    @classmethod
    def normalise_label(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("route and shape names must not be blank")
        return cleaned

    @field_validator("control_points", "reference_points")
    @classmethod
    def validate_points(cls, value: list[list[float]]) -> list[list[float]]:
        cleaned: list[list[float]] = []
        for point in value:
            if not isinstance(point, list | tuple) or len(point) < 2:
                raise ValueError("each point must contain latitude and longitude")
            lat, lon = float(point[0]), float(point[1])
            if (
                not math.isfinite(lat)
                or not math.isfinite(lon)
                or not -90 <= lat <= 90
                or not -180 <= lon <= 180
            ):
                raise ValueError("route points must be finite latitude/longitude pairs")
            cleaned.append([lat, lon])
        return cleaned


class EditedRouteResponse(BaseModel):
    request_id: str | None = None
    points_preview: list[list[float]]
    distance_km: float
    snapped: bool
    below_recommended: bool
    validation: dict
    route_verification: dict
    route_details: dict
    gpx: str | None
    tcx: str | None
    warnings: list[str] = Field(default_factory=list)


class RouteAcceptanceRequest(BaseModel):
    generation_request_id: str | None = Field(default=None, max_length=80)
    route_id: str = Field(..., min_length=1, max_length=80)
    shape_name: str = Field(..., min_length=1, max_length=80)
    automatic_checks_passed: bool = False
    scientifically_verified: bool | None = Field(
        default=None,
        description="Deprecated compatibility field; use automatic_checks_passed.",
    )
    snapped: bool = False
    failed_gates: list[str] = Field(default_factory=list, max_length=20)
    score: float | None = Field(default=None, ge=0, le=1)
    shape_fidelity: float | None = Field(default=None, ge=0, le=1)
    distance_km: float | None = Field(default=None, ge=0, le=1_000)

    @field_validator("route_id", "shape_name")
    @classmethod
    def normalise_acceptance_label(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("route and shape identifiers must not be blank")
        return cleaned

    @field_validator("failed_gates")
    @classmethod
    def normalise_failed_gates(cls, value: list[str]) -> list[str]:
        return [" ".join(item.split())[:80] for item in value if item.strip()]

    @property
    def checks_passed(self) -> bool:
        """Return the current flag while accepting older UI payloads."""

        return self.automatic_checks_passed or bool(self.scientifically_verified)


_MAX_PREVIEW_POINTS = 500


def _even_sample(points: list, n: int) -> list:
    """Evenly sample ``points`` to at most ``n`` entries, retaining endpoints."""
    if n < 1:
        raise ValueError("sample size must be positive")
    if len(points) <= n:
        return list(points)
    if n == 1:
        return [points[0]]
    indices = [round(index * (len(points) - 1) / (n - 1)) for index in range(n)]
    return [points[i] for i in indices]


def _candidate_response_rank(
    candidate: EvaluatedCandidate,
    selected_shape: str | None,
) -> tuple[bool, bool, bool, float, float, float]:
    """Rank routes by the same independent gates shown to the user.

    Aggregate score is intentionally only a late tie-breaker. Otherwise a
    high average can put a route with one failed recognition gate ahead of a
    route that satisfies every required check.
    """

    selected_shape_match = bool(
        selected_shape
        and candidate.shape_name.casefold() == selected_shape.casefold()
    )
    report = quality_gate_report(
        candidate.validation,
        closed=candidate.closed,
        candidate_shape=candidate.shape_name,
        selected_shape=selected_shape,
    )
    return (
        selected_shape_match,
        bool(report["passed"]),
        bool(candidate.validation.on_roads),
        quality_bottleneck(candidate.validation, closed=candidate.closed),
        candidate.validation.score,
        candidate.validation.shape_fidelity,
    )


def _route_details(
    *,
    validation,
    shape_name: str,
    shape_source: str,
    sport: str,
    snapped: bool,
    closed: bool,
    distance_km: float,
    target_distance_km: float | None,
    route_point_count: int,
    guide_point_count: int,
    transform: dict | None = None,
) -> dict:
    difference_km = (
        distance_km - target_distance_km
        if target_distance_km is not None
        else None
    )
    difference_percent = (
        100.0 * difference_km / target_distance_km
        if difference_km is not None and target_distance_km
        else None
    )
    return {
        "shape": {
            "name": shape_name,
            "source": shape_source,
            "closed": closed,
        },
        "routing": {
            "activity": sport,
            "street_matched": snapped,
            "route_point_count": route_point_count,
            "guide_point_count": guide_point_count,
            "closure_gap_m": validation.closure_gap_m,
        },
        "distance": {
            "actual_km": distance_km,
            "target_km": target_distance_km,
            "difference_km": difference_km,
            "difference_percent": difference_percent,
            "route_to_guide_ratio": validation.route_length_ratio,
        },
        "deviation": {
            "mean_outline_deviation_ratio": validation.mean_deviation_ratio,
        },
        "placement": transform or {},
    }


def _state_to_response(state) -> dict:
    snapped = state.snapped
    export = state.export
    all_pts = snapped.points if snapped else []
    preview = [[p[0], p[1]] for p in _even_sample(all_pts, _MAX_PREVIEW_POINTS)]
    ideal_points = state.route_draft.waypoints if state.route_draft else []
    ideal_preview = [
        [point[0], point[1]]
        for point in _even_sample(ideal_points, _MAX_PREVIEW_POINTS)
    ]
    landmark_preview = [
        [point[0], point[1]]
        for point in shape_similarity.salient_route_landmarks(ideal_points)
    ]
    selected_shape = state.shape.name if state.shape else None
    selected_shape_source = state.shape.source if state.shape else "unknown"
    sport = state.intent.sport if state.intent else "run"
    ranked_candidates = sorted(
        enumerate(state.candidates, start=1),
        key=lambda item: _candidate_response_rank(item[1], selected_shape),
        reverse=True,
    )
    candidates = []
    candidate_audit = []
    verified_count = 0
    review_count = 0
    other_shape_count = 0
    for original_index, candidate in ranked_candidates:
        validation = candidate.validation
        verification = quality_gate_report(
            validation,
            closed=candidate.closed,
            candidate_shape=candidate.shape_name,
            selected_shape=selected_shape,
        )
        transform = {
            "rotation_deg": candidate.rotation_deg,
            "scale_m": candidate.scale_m,
            "lat_offset_m": candidate.lat_offset_m,
            "lon_offset_m": candidate.lon_offset_m,
            "preflight_score": candidate.preflight_score,
        }
        distance_km = candidate.total_distance_m / 1000.0
        details = _route_details(
            validation=validation,
            shape_name=candidate.shape_name,
            shape_source=candidate.shape_source,
            sport=sport,
            snapped=candidate.snapped,
            closed=candidate.closed,
            distance_km=distance_km,
            target_distance_km=validation.target_distance_km,
            route_point_count=len(candidate.points),
            guide_point_count=len(candidate.ideal_points),
            transform=transform,
        )
        candidate_id = f"candidate-{original_index}"
        selected_shape_match = bool(
            selected_shape
            and candidate.shape_name.casefold() == selected_shape.casefold()
        )
        decision = (
            "other_shape"
            if not selected_shape_match
            else "verified" if verification["passed"] else "review"
        )
        candidate_audit.append(
            {
                "id": candidate_id,
                "shape_name": candidate.shape_name,
                "selected_shape_match": selected_shape_match,
                "accepted": verification["passed"],
                "verified": verification["passed"],
                "decision": decision,
                "failed_gates": verification["failed_gates"],
                "score": validation.score,
                "shape_fidelity": validation.shape_fidelity,
                "distance_km": distance_km,
                "issues": list(validation.issues),
            }
        )
        log_method = log.info if verification["passed"] else log.warning
        log_method(
            (
                "Route candidate %s: shape=%s, selected-shape match=%s, "
                "decision=%s, street matched=%s, overall=%.1f%%, "
                "likeness=%.1f%%, distance=%.2f km, failed checks=%s."
            ),
            candidate_id,
            candidate.shape_name,
            "yes" if selected_shape_match else "no",
            decision,
            "yes" if candidate.snapped else "no",
            validation.score * 100,
            validation.shape_fidelity * 100,
            distance_km,
            ", ".join(verification["failed_gates"]) or "none",
            extra={
                "event": "route.candidate.evaluated",
                "candidate_id": candidate_id,
                "shape": candidate.shape_name,
                "city": state.intent.city if state.intent else None,
                "sport": sport,
                "decision": decision,
                "verified": verification["passed"],
                "failed_gates": verification["failed_gates"],
                "selected_shape_match": selected_shape_match,
                "snapped": candidate.snapped,
                "score": validation.score,
                "fidelity": validation.shape_fidelity,
                "distance_km": distance_km,
                "target_distance_km": validation.target_distance_km,
                "distance_fit": validation.distance_fit,
                "closure": validation.closure,
                "route_point_count": len(candidate.points),
                "guide_point_count": len(candidate.ideal_points),
                **transform,
            },
        )
        # Attempts for fallback/suggestion shapes remain in the audit, but the
        # selector shows only routes drawn from the final selected shape.
        if not selected_shape_match:
            other_shape_count += 1
            continue
        if verification["passed"]:
            verified_count += 1
        else:
            review_count += 1
        export_name = (
            f"{candidate.shape_name} in {state.intent.city or 'route'}"
            if state.intent
            else candidate.shape_name
        )
        candidate_gpx = gpx_writer.to_gpx(
            candidate.points,
            name=export_name,
            sport=sport,
            total_distance_m=candidate.total_distance_m,
        )
        try:
            candidate_tcx = gpx_writer.to_tcx(
                candidate.points,
                name=export_name,
                sport=sport,
                total_distance_m=candidate.total_distance_m,
            )
        except Exception:  # noqa: BLE001
            candidate_tcx = None
        candidates.append(
            {
                "id": candidate_id,
                "shape_name": candidate.shape_name,
                "shape_source": candidate.shape_source,
                "points_preview": [
                    [point[0], point[1]]
                    for point in _even_sample(candidate.points, _MAX_PREVIEW_POINTS)
                ],
                "ideal_preview": [
                    [point[0], point[1]]
                    for point in _even_sample(candidate.ideal_points, _MAX_PREVIEW_POINTS)
                ],
                "landmark_preview": [
                    [point[0], point[1]]
                    for point in shape_similarity.salient_route_landmarks(
                        candidate.ideal_points
                    )
                ],
                "distance_km": distance_km,
                "snapped": candidate.snapped,
                "closed": candidate.closed,
                "target_distance_km": validation.target_distance_km,
                "validation": validation.__dict__,
                "below_recommended": not verification["passed"],
                "verification_status": decision,
                "requires_user_acceptance": not verification["passed"],
                "verification": verification,
                "details": details,
                "transform": transform,
                "gpx": candidate_gpx,
                "tcx": candidate_tcx,
                "gallery_publish_token": (
                    cloudinary_gallery.maybe_issue_publish_token()
                    if candidate.snapped
                    else None
                ),
            }
        )

    route_verification = (
        quality_gate_report(
            state.validation,
            closed=bool(state.shape and state.shape.closed),
            candidate_shape=selected_shape,
            selected_shape=selected_shape,
        )
        if state.validation
        else None
    )
    route_details = (
        _route_details(
            validation=state.validation,
            shape_name=selected_shape or "unknown",
            shape_source=selected_shape_source,
            sport=sport,
            snapped=bool(snapped and snapped.snapped),
            closed=bool(state.shape and state.shape.closed),
            distance_km=(snapped.total_distance_m / 1000.0) if snapped else 0.0,
            target_distance_km=state.validation.target_distance_km,
            route_point_count=len(snapped.points) if snapped else 0,
            guide_point_count=len(ideal_points),
            transform=(
                {
                    "rotation_deg": state.route_draft.rotation_deg,
                    "scale_m": state.route_draft.scale_m,
                    "lat_offset_m": state.route_draft.lat_offset_m,
                    "lon_offset_m": state.route_draft.lon_offset_m,
                    "preflight_score": state.route_draft.preflight_score,
                }
                if state.route_draft
                else {}
            ),
        )
        if state.validation
        else None
    )
    candidate_summary = {
        "selected_shape": selected_shape,
        "accepted_count": verified_count,
        "verified_count": verified_count,
        "review_count": review_count,
        "shown_count": len(candidates),
        "rejected_selected_shape_count": review_count,
        "other_shape_count": other_shape_count,
        "audited_count": len(candidate_audit),
        "full_route_attempt_count": state.candidate_count,
        "preflight_count": state.preflight_count,
    }
    log.info(
        (
            "Route response prepared for selected shape %s: showing %d route(s), "
            "%d passed automatic checks, %d available for user review, "
            "%d other-shape attempt(s) kept only in the audit."
        ),
        selected_shape or "unknown",
        len(candidates),
        verified_count,
        review_count,
        other_shape_count,
        extra={
            "event": "route.response.prepared",
            "shape": selected_shape,
            "city": state.intent.city if state.intent else None,
            "sport": sport,
            "shown_count": len(candidates),
            "verified_count": verified_count,
            "review_count": review_count,
            "other_shape_count": other_shape_count,
            "candidate_count": state.candidate_count,
            "preflight_count": state.preflight_count,
        },
    )
    return dict(
        request_id=state.request_id,
        prompt=state.prompt,
        intent=state.intent.__dict__ if state.intent else None,
        shape=(
            {"name": state.shape.name, "closed": state.shape.closed,
             "source": state.shape.source, "n_paths": len(state.shape.paths)}
            if state.shape else None
        ),
        suggested_shape=state.plan.suggested_shape if state.plan else None,
        suggestion_reason=(
            state.plan.notes
            if state.plan and state.plan.suggested_shape
            else None
        ),
        requested_shape=state.requested_shape,
        fit_decision=state.fit_decision.__dict__ if state.fit_decision else None,
        validation=state.validation.__dict__ if state.validation else None,
        distance_km=(snapped.total_distance_m / 1000) if snapped else None,
        snapped=snapped.snapped if snapped else None,
        iterations=state.iterations,
        candidate_count=state.candidate_count,
        preflight_count=state.preflight_count,
        below_threshold=state.below_threshold,
        errors=state.errors,
        history=state.history,
        gpx=export.gpx if export else None,
        tcx=export.tcx if export else None,
        file_paths=export.file_paths if export else {},
        points_preview=preview,
        ideal_preview=ideal_preview,
        landmark_preview=landmark_preview,
        candidates=candidates,
        candidate_audit=candidate_audit,
        candidate_summary=candidate_summary,
        preflight_candidates=state.preflight_candidates,
        route_verification=route_verification,
        route_details=route_details,
        gallery_publish_token=(
            cloudinary_gallery.maybe_issue_publish_token()
            if snapped and snapped.snapped
            else None
        ),
    )


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "GPS Art Wizard",
        "version": "0.1.0",
        "gallery": {"configured": cloudinary_gallery.is_configured()},
    }


@router.post("/route-acceptance")
def record_route_acceptance(req: RouteAcceptanceRequest) -> dict:
    """Record the user's explicit decision without retaining route geometry."""

    failed_text = ", ".join(req.failed_gates) or "none"
    score_text = f"{req.score:.1%}" if req.score is not None else "unavailable"
    fidelity_text = (
        f"{req.shape_fidelity:.1%}"
        if req.shape_fidelity is not None
        else "unavailable"
    )
    distance_text = (
        f"{req.distance_km:.2f} km"
        if req.distance_km is not None
        else "unavailable"
    )
    log.warning(
        (
            "User accepted route for GPX: route=%s, shape=%s, "
            "system verified=%s, street matched=%s, overall=%s, "
            "likeness=%s, distance=%s, failed checks=%s."
        ),
        req.route_id,
        req.shape_name,
        "yes" if req.checks_passed else "no",
        "yes" if req.snapped else "no",
        score_text,
        fidelity_text,
        distance_text,
        failed_text,
        extra={
            "event": "route.user.accepted",
            "generation_request_id": req.generation_request_id,
            "candidate_id": req.route_id,
            "shape": req.shape_name,
            "decision": "user_accepted",
            "verified": req.checks_passed,
            "snapped": req.snapped,
            "failed_gates": req.failed_gates,
            "score": req.score,
            "fidelity": req.shape_fidelity,
            "distance_km": req.distance_km,
            "export_mode": "user_acceptance",
        },
    )
    return {"recorded": True}


@router.post("/generate", response_model=GenerateResponse)
def generate_route(req: GenerateRequest) -> dict:
    log.info(
        "Route generation requested",
        extra={
            "event": "generation.requested",
            "prompt_length": len(req.prompt),
        },
    )
    try:
        state = generate(req.prompt)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("route generation failed")
        raise HTTPException(
            status_code=500,
            detail="Route generation failed. Verify the routing and model-provider configuration.",
        ) from exc
    return _state_to_response(state)


@router.post("/edit-route", response_model=EditedRouteResponse)
def edit_route(req: EditedRouteRequest) -> dict:
    """Re-route edited points and prepare an export with verification context."""
    control_points = [(point[0], point[1]) for point in req.control_points]
    reference_points = [
        (point[0], point[1])
        for point in (req.reference_points or req.control_points)
    ]
    if geo.path_distance_m(control_points) > 1_000_000:
        raise HTTPException(
            status_code=422,
            detail="Edited route guides must stay within a 1,000 km total span.",
        )

    points, distance_m, snapped = ors_client.snap_route(
        control_points,
        sport=req.sport,
        closed=req.closed,
    )
    temporary = WorkflowState(
        prompt="manual route edit",
        request_id=current_request_id(),
        intent=Intent(
            shape=req.shape_name,
            text=None,
            city=None,
            sport=req.sport,
            distance_km=req.target_distance_km,
            style=None,
        ),
        shape=Shape(
            name=req.shape_name,
            paths=[[(0.0, 0.0), (1.0, 1.0)]],
            closed=req.closed,
            source="manual",
        ),
        route_draft=RouteDraft(
            center_lat=reference_points[0][0],
            center_lon=reference_points[0][1],
            scale_m=1.0,
            rotation_deg=0.0,
            lat_offset_m=0.0,
            lon_offset_m=0.0,
            simplify_tolerance=0.0,
            waypoints=reference_points,
            closed=req.closed,
            target_distance_km=req.target_distance_km,
        ),
        snapped=SnappedRoute(
            points=points,
            total_distance_m=distance_m,
            snapped=snapped,
        ),
    )
    ValidationAgent().run(temporary)
    if temporary.validation is None:
        raise HTTPException(status_code=500, detail="Edited route validation failed.")

    warnings = list(temporary.validation.issues)
    if not snapped:
        warnings.append(
            "Street routing was unavailable. The GPX is a straight-line guide and must be reviewed carefully before use."
        )
    verification = quality_gate_report(
        temporary.validation,
        closed=req.closed,
        candidate_shape=req.shape_name,
        selected_shape=req.shape_name,
    )
    gpx = gpx_writer.to_gpx(
        points,
        name=req.name,
        sport=req.sport,
        total_distance_m=distance_m,
    )
    tcx = None
    try:
        tcx = gpx_writer.to_tcx(
            points,
            name=req.name,
            sport=req.sport,
            total_distance_m=distance_m,
        )
    except Exception:  # noqa: BLE001
        tcx = None
    if not verification["passed"]:
        failed_labels = [
            gate["label"]
            for gate in verification["gates"]
            if gate["applies"] and not gate["passed"]
        ]
        warnings.append(
            "Automatic verification is below target for: "
            + ", ".join(failed_labels)
            + ". The route can still be exported after explicit user acceptance."
        )
    decision = "verified" if verification["passed"] else "review"
    log_method = log.info if verification["passed"] else log.warning
    log_method(
        (
            "Edited route prepared: shape=%s, decision=%s, street matched=%s, "
            "overall=%.1f%%, likeness=%.1f%%, distance=%.2f km, "
            "points=%d, failed checks=%s."
        ),
        req.shape_name,
        decision,
        "yes" if snapped else "no",
        temporary.validation.score * 100,
        temporary.validation.shape_fidelity * 100,
        distance_m / 1000.0,
        len(points),
        ", ".join(verification["failed_gates"]) or "none",
        extra={
            "event": "route.edit.completed",
            "shape": req.shape_name,
            "sport": req.sport,
            "snapped": snapped,
            "route_point_count": len(points),
            "guide_point_count": len(reference_points),
            "distance_km": round(distance_m / 1000.0, 3),
            "target_distance_km": req.target_distance_km,
            "score": temporary.validation.score,
            "fidelity": temporary.validation.shape_fidelity,
            "distance_fit": temporary.validation.distance_fit,
            "closure": temporary.validation.closure,
            "decision": decision,
            "verified": verification["passed"],
            "failed_gates": verification["failed_gates"],
            "export_mode": "verified" if verification["passed"] else "user_acceptance",
        },
    )
    route_details = _route_details(
        validation=temporary.validation,
        shape_name=req.shape_name,
        shape_source="manual",
        sport=req.sport,
        snapped=snapped,
        closed=req.closed,
        distance_km=distance_m / 1000.0,
        target_distance_km=req.target_distance_km,
        route_point_count=len(points),
        guide_point_count=len(reference_points),
    )
    return {
        "request_id": temporary.request_id,
        "points_preview": [
            [point[0], point[1]]
            for point in _even_sample(points, _MAX_PREVIEW_POINTS)
        ],
        "distance_km": distance_m / 1000.0,
        "snapped": snapped,
        "below_recommended": not verification["passed"],
        "validation": temporary.validation.__dict__,
        "route_verification": verification,
        "route_details": route_details,
        "gpx": gpx,
        "tcx": tcx,
        "warnings": warnings,
    }

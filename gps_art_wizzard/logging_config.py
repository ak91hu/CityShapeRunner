"""Structured, request-correlated logging for the API and route pipeline."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

_request_id: ContextVar[str] = ContextVar("gps_art_request_id", default="-")
_configured = False
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")


def current_request_id() -> str | None:
    value = _request_id.get()
    return None if value == "-" else value


def bind_request_id(value: str) -> Token:
    safe = value if _SAFE_REQUEST_ID.fullmatch(value) else "-"
    return _request_id.set(safe)


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


class _RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id() or "-"
        return True


class _JsonFormatter(logging.Formatter):
    _extra_fields = (
        "event",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "shape",
        "city",
        "sport",
        "candidate_count",
        "preflight_count",
        "score",
        "fidelity",
        "snapped",
        "point_count",
        "prompt_length",
        "distance_km",
        "target_distance_km",
        "distance_delta_km",
        "distance_fit",
        "closure",
        "closure_gap_m",
        "spatial_similarity",
        "coverage_similarity",
        "turning_similarity",
        "landmark_similarity",
        "length_similarity",
        "extent_similarity",
        "route_length_ratio",
        "mean_deviation_ratio",
        "route_point_count",
        "guide_point_count",
        "candidate_id",
        "decision",
        "verified",
        "failed_gates",
        "selected_shape_match",
        "shown_count",
        "verified_count",
        "review_count",
        "other_shape_count",
        "rotation_deg",
        "scale_m",
        "lat_offset_m",
        "lon_offset_m",
        "preflight_score",
        "export_mode",
        "generation_request_id",
        "gallery_id",
    )

    def format(self, record: logging.LogRecord) -> str:
        service = (
            os.getenv("SERVICE_NAME")
            or os.getenv("K_SERVICE")
            or "gps-art-wizard"
        )
        environment = os.getenv("APP_ENV", "local")
        request_id = getattr(record, "request_id", "-")
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": record.levelname,
            "level": record.levelname,
            "service": service,
            "environment": environment,
            "logger": record.name,
            "request_id": request_id,
            "message": record.getMessage(),
        }
        revision = (
            os.getenv("APP_REVISION")
            or os.getenv("K_REVISION")
            or ""
        ).strip()
        if revision:
            payload["revision"] = revision
        for field in self._extra_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            exception_type = record.exc_info[0]
            if exception_type is not None:
                payload["exception_type"] = exception_type.__name__
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )


def configure_logging() -> None:
    """Configure console + rotating file logs once, without logging secrets."""
    global _configured
    if _configured:
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    json_logs = os.getenv("LOG_FORMAT", "json").strip().lower() == "json"
    formatter: logging.Formatter
    if json_logs:
        formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s "
            "[request_id=%(request_id)s] %(message)s"
        )
    context_filter = _RequestContextFilter()

    handlers: list[logging.Handler] = []
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    console.addFilter(context_filter)
    handlers.append(console)

    # Production containers emit to stderr for the hosting platform to collect.
    # Local runs keep rotating JSONL files unless LOG_FILE is explicitly set.
    environment = os.getenv("APP_ENV", "local").strip().lower()
    default_log_file = (
        "logs/gps-art-wizard.log"
        if environment in {"", "dev", "development", "local", "test"}
        else ""
    )
    log_file = os.getenv("LOG_FILE", default_log_file).strip()
    if log_file:
        try:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                path,
                maxBytes=max(64_000, int(os.getenv("LOG_MAX_BYTES", "5000000"))),
                backupCount=max(1, int(os.getenv("LOG_BACKUP_COUNT", "5"))),
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.addFilter(context_filter)
            handlers.append(file_handler)
        except (OSError, ValueError):
            # Console logging remains available in read-only deployments.
            pass

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    for handler in handlers:
        root.addHandler(handler)
    _configured = True

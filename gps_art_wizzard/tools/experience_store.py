"""Privacy-preserving local evidence store for completed GPS art routes."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def _database_path() -> Path:
    configured = os.getenv("GPS_ART_EVIDENCE_DB", "").strip()
    if configured:
        return Path(configured)
    return Path.cwd() / "data" / "gps-art-evidence.sqlite3"


def record_completion(summary: dict) -> None:
    """Store an opted-in, coordinate-free completion summary."""

    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS route_evidence (
                id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL,
                city TEXT,
                shape_name TEXT NOT NULL,
                sport TEXT NOT NULL,
                planned_km REAL,
                completed_km REAL,
                likeness REAL,
                blocked_segments INTEGER NOT NULL,
                notes TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO route_evidence (
                created_at, city, shape_name, sport, planned_km, completed_km,
                likeness, blocked_segments, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(UTC).isoformat(),
                summary.get("city"),
                summary["shape_name"],
                summary["sport"],
                summary.get("planned_km"),
                summary.get("completed_km"),
                summary.get("likeness"),
                summary["blocked_segments"],
                json.dumps(summary.get("notes", []), ensure_ascii=False),
            ),
        )


def evidence_summary(*, city: str | None = None, shape_name: str | None = None) -> dict:
    """Return aggregate evidence only. Individual activity traces are never retained."""

    path = _database_path()
    if not path.is_file():
        return {"completed_count": 0, "average_likeness": None, "blocked_report_count": 0}
    clauses, values = [], []
    if city:
        clauses.append("city = ?")
        values.append(city)
    if shape_name:
        clauses.append("shape_name = ?")
        values.append(shape_name)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT COUNT(*), AVG(likeness), COALESCE(SUM(blocked_segments), 0) "
            f"FROM route_evidence{where}",
            values,
        ).fetchone()
    return {
        "completed_count": int(row[0] or 0),
        "average_likeness": float(row[1]) if row[1] is not None else None,
        "blocked_report_count": int(row[2] or 0),
    }

from __future__ import annotations

import uuid

from fastapi import Request


def request_id(request: Request) -> str:
    rid = request.headers.get("x-request-id")
    return rid or f"req_{uuid.uuid4().hex[:12]}"


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

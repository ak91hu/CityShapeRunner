from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.deps import request_id
from app.core.schemas import ErrorEnvelope, ErrorResponse
from app.services import ServiceError


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def _service_error(request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=ErrorResponse(
                error=ErrorEnvelope(
                    code=exc.code,
                    message=exc.message,
                    fields=exc.fields,
                    request_id=request_id(request),
                )
            ).model_dump(by_alias=True),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query", "path"))
            if loc:
                fields[loc] = err.get("msg", "invalid")
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorEnvelope(
                    code="VALIDATION_ERROR",
                    message="The request is invalid.",
                    fields=fields or None,
                    request_id=request_id(request),
                )
            ).model_dump(by_alias=True),
        )

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import client_ip
from app.core.schemas import GenerationJobCreate, GenerationJobCreated, GenerationJobStatus
from app.services import generation_service

router = APIRouter()


@router.post("/generation/jobs", response_model=GenerationJobCreated, status_code=202)
async def create_job(req: GenerationJobCreate, request: Request) -> GenerationJobCreated:
    job_id, status = generation_service.create_job(req, ip=client_ip(request))
    return GenerationJobCreated(job_id=job_id, status=status)


@router.get("/generation/jobs/{job_id}", response_model=GenerationJobStatus)
async def get_job(job_id: str) -> GenerationJobStatus:
    return generation_service.get_job(job_id)


@router.post("/generation/jobs/{job_id}/cancel", response_model=GenerationJobStatus)
async def cancel_job(job_id: str) -> GenerationJobStatus:
    return generation_service.cancel_job(job_id)

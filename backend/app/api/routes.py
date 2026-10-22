from __future__ import annotations
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger

from app.models.schemas import (
    ParseRequest, ParseResponse,
    StartJobRequest, JobResponse,
    Job,
)
from app.parser.form_parser import parse_form, fetch_raw_nodes
from app.jobs.job_manager import job_manager
from app.websocket.ws_manager import ws_manager

router = APIRouter()


# ─── Forms ────────────────────────────────────────────────────────────────────

@router.post("/forms/parse", response_model=ParseResponse)
async def parse_google_form(body: ParseRequest):
    try:
        form = await parse_form(body.url)
        return ParseResponse(success=True, form=form)
    except Exception as exc:
        logger.error(f"Parse error: {exc}")
        return ParseResponse(success=False, error=str(exc))


@router.get("/forms/debug")
async def debug_form(url: str):
    """Return raw FB_PUBLIC_LOAD_DATA_ node structure for debugging navigation."""
    try:
        return await fetch_raw_nodes(url)
    except Exception as exc:
        raise HTTPException(400, str(exc))


# ─── Jobs ─────────────────────────────────────────────────────────────────────

@router.post("/jobs/start", response_model=JobResponse)
async def start_job(body: StartJobRequest):
    job = job_manager.create_job(body.config)
    job_manager.start_job(job.id)
    return JobResponse(job=job)


@router.get("/jobs", response_model=list[Job])
async def list_jobs():
    return job_manager.list_jobs()


@router.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    if not job_manager.get_job(job_id):
        raise HTTPException(404, "Job not found")
    job_manager.pause_job(job_id)
    return {"ok": True}


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    if not job_manager.get_job(job_id):
        raise HTTPException(404, "Job not found")
    job_manager.resume_job(job_id)
    return {"ok": True}


@router.post("/jobs/{job_id}/stop")
async def stop_job(job_id: str):
    if not job_manager.get_job(job_id):
        raise HTTPException(404, "Job not found")
    job_manager.stop_job(job_id)
    return {"ok": True}


@router.get("/jobs/{job_id}/logs")
async def get_logs(job_id: str):
    all_logs = job_manager.logs.get_all()
    return [e for e in all_logs if e["job_id"] == job_id]


# ─── WebSocket ────────────────────────────────────────────────────────────────

@router.websocket("/ws/jobs/{job_id}/logs")
async def ws_logs(job_id: str, websocket: WebSocket):
    await ws_manager.connect(job_id, websocket)
    try:
        while True:
            # keep alive — client can send ping
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(job_id, websocket)

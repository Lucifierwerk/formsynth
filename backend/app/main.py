from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
import os
import sys

from app.api.routes import router
from app.jobs.job_manager import job_manager
from app.websocket.ws_manager import ws_manager

# ─── Logging ─────────────────────────────────────────────────────────────────
logger.remove()
logger.add(sys.stderr, level="DEBUG", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="FormSynth API",
    description="Synthetic Google Forms response generator for research & education",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Wire up WebSocket broadcast to job manager
job_manager.set_broadcast(ws_manager.broadcast)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "FormSynth API v1.0"}


# Serve built frontend (production) — must be last
_STATIC = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_STATIC):
    app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")

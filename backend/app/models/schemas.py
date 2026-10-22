from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
import uuid


# ─── Option / Question / Form ────────────────────────────────────────────────

class Option(BaseModel):
    value: str
    weight: int = 1
    enabled: bool = True
    go_to_page: int | None = None  # target page index for branching (None = next page)


class TextPoolItem(BaseModel):
    value: str
    weight: int = 1
    enabled: bool = True


class Question(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entry_id: str
    title: str
    description: str | None = None
    qtype: str  # single | multi | text | textarea
    required: bool = False
    enabled: bool = True
    options: list[Option] = []
    # checkbox-specific
    min_select: int = 1
    max_select: int = 3
    # text-specific
    text_pool: list[TextPoolItem] = []
    # section/page this question belongs to (0-based)
    page_index: int = 0


class ParsedForm(BaseModel):
    form_id: str
    title: str
    description: str | None = None
    questions: list[Question]
    # page_index → next page index after completing that page (-1 = submit)
    page_transitions: dict[str, int] = {}


# ─── Job ─────────────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobConfig(BaseModel):
    url: str
    form_id: str
    questions: list[Question]
    page_transitions: dict[str, int] = {}
    total: int = 100
    concurrency: int = 3
    min_delay: float = 2.0
    max_delay: float = 8.0
    retry_count: int = 2
    batch_size: int = 10
    batch_pause: float = 5.0
    profiles: list[str] = []


class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "pending"
    progress: int = 0
    total: int = 0
    success_count: int = 0
    error_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    config: JobConfig | None = None


# ─── API Request/Response models ──────────────────────────────────────────────

class ParseRequest(BaseModel):
    url: str


class ParseResponse(BaseModel):
    success: bool
    form: ParsedForm | None = None
    error: str | None = None


class StartJobRequest(BaseModel):
    config: JobConfig


class JobResponse(BaseModel):
    job: Job


class LogEntry(BaseModel):
    ts: str
    level: str  # INFO | SUCCESS | WARNING | ERROR
    message: str
    job_id: str | None = None


class ConfigExport(BaseModel):
    version: str = "1.0"
    url: str = ""
    form: ParsedForm | None = None
    settings: dict[str, Any] = {}
    profiles: list[str] = []
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

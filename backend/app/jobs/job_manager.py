"""
In-memory job manager.
Runs submission jobs as asyncio tasks with full lifecycle control.
"""
from __future__ import annotations
import asyncio
import random
from datetime import datetime
from typing import Optional
from loguru import logger

from app.models.schemas import Job, JobConfig, JobStatus
S = JobStatus
from app.generator.response_generator import ResponseGenerator
from app.sender.form_sender import submit_response

# ─── Simple log store ─────────────────────────────────────────────────────────

class LogStore:
    def __init__(self, max_size: int = 500):
        self._logs: list[dict] = []
        self._max = max_size

    def append(self, level: str, message: str, job_id: str) -> dict:
        entry = {
            "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "level": level,
            "message": message,
            "job_id": job_id,
        }
        self._logs.append(entry)
        if len(self._logs) > self._max:
            self._logs = self._logs[-self._max:]
        return entry

    def get_all(self) -> list[dict]:
        return list(self._logs)


# ─── Job Manager ─────────────────────────────────────────────────────────────

class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._pause_events: dict[str, asyncio.Event] = {}
        self._cancel_flags: dict[str, bool] = {}
        self.logs: LogStore = LogStore()
        # WebSocket broadcast callback injected from ws_manager
        self._broadcast_cb = None

    def set_broadcast(self, cb) -> None:
        self._broadcast_cb = cb

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create_job(self, config: JobConfig) -> Job:
        job = Job(config=config, total=config.total)
        self._jobs[job.id] = job
        self._pause_events[job.id] = asyncio.Event()
        self._pause_events[job.id].set()  # not paused initially
        self._cancel_flags[job.id] = False
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        return list(self._jobs.values())

    # ── Commands ─────────────────────────────────────────────────────────────

    def start_job(self, job_id: str) -> None:
        job = self._jobs[job_id]
        job.status = S.RUNNING
        job.started_at = datetime.utcnow()
        task = asyncio.create_task(self._run(job_id))
        self._tasks[job_id] = task

    def pause_job(self, job_id: str) -> None:
        if job_id in self._pause_events:
            self._pause_events[job_id].clear()
            if job_id in self._jobs:
                self._jobs[job_id].status = S.PAUSED

    def resume_job(self, job_id: str) -> None:
        if job_id in self._pause_events:
            self._pause_events[job_id].set()
            if job_id in self._jobs:
                self._jobs[job_id].status = S.RUNNING

    def stop_job(self, job_id: str) -> None:
        self._cancel_flags[job_id] = True
        self.resume_job(job_id)  # unblock if paused
        if job_id in self._jobs:
            self._jobs[job_id].status = S.CANCELLED

    # ── Internal runner ───────────────────────────────────────────────────────

    async def _log(self, job_id: str, level: str, message: str) -> None:
        entry = self.logs.append(level, message, job_id)
        if self._broadcast_cb:
            await self._broadcast_cb(job_id, {"type": "log", **entry})

    async def _broadcast_status(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job and self._broadcast_cb:
            await self._broadcast_cb(job_id, {
                "type": "status",
                "status": job.status,
                "progress": job.progress,
                "total": job.total,
                "success_count": job.success_count,
                "error_count": job.error_count,
            })

    async def _run(self, job_id: str) -> None:
        job = self._jobs[job_id]
        cfg = job.config
        gen = ResponseGenerator(cfg)
        submit_url = f"https://docs.google.com/forms/d/e/{cfg.form_id}/formResponse"

        await self._log(job_id, "INFO", f"Job started — {cfg.total} responses, concurrency={cfg.concurrency}")

        sem = asyncio.Semaphore(cfg.concurrency)

        async def _send_one(idx: int) -> None:
            # Wait for resume before competing for a semaphore slot
            await self._pause_events[job_id].wait()
            if self._cancel_flags.get(job_id):
                return

            async with sem:
                # Re-check after acquiring the slot (could be cancelled while waiting)
                await self._pause_events[job_id].wait()
                if self._cancel_flags.get(job_id):
                    return

                payload = gen.generate_response()
                await self._log(job_id, "INFO", f"Отправка ответа #{idx + 1}/{cfg.total}")

                async def log_cb(level: str, msg: str) -> None:
                    await self._log(job_id, level, msg)

                # submit_response creates its own session per response
                # → clean cookie jar, no state bleed between concurrent requests
                ok = await submit_response(
                    submit_url,
                    payload,
                    questions=cfg.questions,
                    page_transitions=cfg.page_transitions or None,
                    retry_count=cfg.retry_count,
                    index=idx + 1,
                    log_cb=log_cb,
                )
                if ok:
                    job.success_count += 1
                else:
                    job.error_count += 1
                job.progress += 1
                await self._broadcast_status(job_id)

                # Delay between requests
                delay = random.uniform(cfg.min_delay, cfg.max_delay)
                await asyncio.sleep(delay)

                # Batch pause
                if cfg.batch_size > 0 and (idx + 1) % cfg.batch_size == 0:
                    await self._log(job_id, "INFO",
                        f"Пауза между пачками {cfg.batch_pause}s после {idx + 1} ответов")
                    await asyncio.sleep(cfg.batch_pause)

        tasks = [_send_one(i) for i in range(cfg.total)]
        await asyncio.gather(*tasks)

        if self._cancel_flags.get(job_id):
            job.status = S.CANCELLED
            await self._log(job_id, "WARNING", "Job cancelled by user")
        else:
            job.status = S.COMPLETED
            await self._log(job_id, "SUCCESS",
                f"Job completed — ✓ {job.success_count} sent, ✗ {job.error_count} failed")

        job.finished_at = datetime.utcnow()
        await self._broadcast_status(job_id)


# Singleton
job_manager = JobManager()

"""
Async form submission engine — multi-section aware.

Key insight: Google Forms counts EVERY POST to /formResponse as a potential
submission.  Sending N intermediate page-by-page POSTs produces N entries in
the results spreadsheet.

Correct approach (matching real browser behaviour):
  1. Walk the branching logic locally to determine which pages get visited.
  2. Collect answers only for those pages.
  3. Send a SINGLE POST with all answers + pageHistory that reflects the path.

pageHistory encodes the visit order, e.g. "0,2" means the respondent went
through section 0 then branched to section 2 (skipping section 1).
Google uses this to validate the submission — it does NOT require separate
per-page POSTs.
"""
from __future__ import annotations
import asyncio
import random
from typing import Any, Callable, Awaitable
import aiohttp
from loguru import logger

from app.models.schemas import Question

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://docs.google.com/",
    "Origin":  "https://docs.google.com",
}

LogCallback = Callable[[str, str], Awaitable[None]]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_fbzx() -> str:
    return str(random.randint(-(10 ** 18), -(10 ** 15)))


def _group_by_page(questions: list[Question]) -> dict[int, list[Question]]:
    pages: dict[int, list[Question]] = {}
    for q in questions:
        pages.setdefault(q.page_index, []).append(q)
    return pages


def _next_page(
    current: int,
    page_questions: list[Question],
    payload: dict[str, Any],
    sorted_pages: list[int],
    page_transitions: dict[str, int] | None = None,
) -> int | None:
    """
    Return next page index, or None (= end of form).
    Priority: 1) option-level go_to_page, 2) section-level page_transitions, 3) sequential.
    """
    for q in page_questions:
        if q.qtype != "single":
            continue
        chosen = payload.get(f"entry.{q.entry_id}")
        if chosen is None:
            continue
        for opt in q.options:
            if opt.value == chosen and opt.go_to_page is not None:
                target = opt.go_to_page
                return None if target == -1 else target

    # Section-level navigation (from PAGE_BREAK node[5])
    if page_transitions:
        nav = page_transitions.get(str(current))
        if nav is not None:
            return None if nav == -1 else nav

    # Sequential fallback
    try:
        idx = sorted_pages.index(current)
        if idx < len(sorted_pages) - 1:
            return sorted_pages[idx + 1]
    except ValueError:
        pass
    return None


def _compute_visit_order(
    pages: dict[int, list[Question]],
    payload: dict[str, Any],
    sorted_pages: list[int],
    page_transitions: dict[str, int] | None = None,
) -> list[int]:
    """
    Simulate navigation through the form and return the ordered list of
    page indices that this respondent would visit.
    """
    visited: list[int] = []
    current: int | None = sorted_pages[0]

    while current is not None:
        visited.append(current)
        current = _next_page(current, pages.get(current, []), payload, sorted_pages, page_transitions)

    return visited


# ── Core POST (with retry) ────────────────────────────────────────────────────

async def _post(
    session: aiohttp.ClientSession,
    submit_url: str,
    payload: dict[str, Any],
    page_history_str: str,
    fbzx: str,
    retry_count: int,
    index: int,
    log_cb: LogCallback | None,
) -> bool:
    async def _log(level: str, msg: str) -> None:
        if log_cb:
            await log_cb(level, msg)
        getattr(logger, level.lower(), logger.info)(msg)

    for attempt in range(retry_count + 1):
        try:
            form_data = aiohttp.FormData()

            for key, value in payload.items():
                if isinstance(value, list):
                    for v in value:
                        form_data.add_field(key, str(v))
                else:
                    form_data.add_field(key, str(value) if value else "")

            form_data.add_field("pageHistory", page_history_str)
            form_data.add_field("fbzx", fbzx)
            form_data.add_field("submit", "Submit")

            async with session.post(
                submit_url,
                data=form_data,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=True,
            ) as resp:
                if resp.status < 400:
                    await _log("SUCCESS",
                        f"Ответ #{index} принят (HTTP {resp.status}, "
                        f"разделы: {page_history_str})")
                    return True
                else:
                    await _log("WARNING",
                        f"Ответ #{index} HTTP {resp.status}")

        except asyncio.TimeoutError:
            await _log("WARNING",
                f"Ответ #{index} таймаут (попытка {attempt + 1}/{retry_count + 1})")
        except aiohttp.ClientError as exc:
            await _log("WARNING",
                f"Ответ #{index} сетевая ошибка: {exc} (попытка {attempt + 1})")
        except Exception as exc:
            await _log("ERROR",
                f"Ответ #{index} непредвиденная ошибка: {exc}")
            return False

        if attempt < retry_count:
            await asyncio.sleep(2 ** attempt)

    await _log("ERROR",
        f"Ответ #{index} не удался после {retry_count + 1} попыток")
    return False


# ── Public API ────────────────────────────────────────────────────────────────

async def submit_response(
    submit_url: str,
    payload: dict[str, Any],
    questions: list[Question] | None = None,
    page_transitions: dict[str, int] | None = None,
    retry_count: int = 2,
    index: int = 0,
    log_cb: LogCallback | None = None,
) -> bool:
    """
    Submit one complete form response as a SINGLE POST.

    For multi-section forms:
      - Simulate the branching path locally (no intermediate HTTP requests)
      - Include only the answers for pages that would actually be visited
      - Set pageHistory to the visited page sequence (e.g. "0,2")
    This matches how a real browser submits multi-page forms and produces
    exactly ONE entry in Google Forms results per call.
    """
    pages        = _group_by_page(questions) if questions else {0: []}
    sorted_pages = sorted(pages.keys())
    total_pages  = len(sorted_pages)

    # Compute which pages this respondent visits (follows branching)
    if total_pages > 1:
        visited = _compute_visit_order(pages, payload, sorted_pages, page_transitions)

        # Keep answers only for visited pages
        entry_ids = {
            f"entry.{q.entry_id}"
            for pi in visited
            for q in pages.get(pi, [])
        }
        final_payload = {k: v for k, v in payload.items() if k in entry_ids}

        page_history_str = ",".join(str(p) for p in visited)
        logger.debug(
            f"Ответ #{index}: путь разделов {page_history_str}, "
            f"{len(final_payload)} полей"
        )
    else:
        visited          = sorted_pages or [0]
        final_payload    = payload
        page_history_str = "0"

    fbzx = _make_fbzx()

    # Each response gets its own cookie jar
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        return await _post(
            session, submit_url,
            final_payload, page_history_str, fbzx,
            retry_count, index, log_cb,
        )

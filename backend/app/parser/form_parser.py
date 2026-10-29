"""
Google Forms parser.
Extracts FB_PUBLIC_LOAD_DATA_ from the form HTML and normalises it
into the internal schema.  No browser automation used.

Multi-section support: detects PAGE_BREAK nodes (type 8), assigns
page_index to every question, and parses go_to_page navigation for
branching (dropdown / radio) answers.
"""
from __future__ import annotations
import json
import re
from loguru import logger
import aiohttp

from app.models.schemas import ParsedForm, Question, Option

# ── Question type codes inside FB_PUBLIC_LOAD_DATA_ ──────────────────────────
_QTYPE_MAP = {
    0: "short_text",   # SHORT_ANSWER
    1: "textarea",     # PARAGRAPH
    2: "single",       # MULTIPLE_CHOICE (radio)
    3: "single",       # DROPDOWN
    4: "multi",        # CHECKBOXES
    5: "scale",        # LINEAR_SCALE
    7: "single",       # GRID (treat as single)
    8: "page_break",   # PAGE_BREAK / section separator
    9: "date",
    10: "time",
}

_INTERNAL_MAP = {
    "short_text": "text",
    "textarea":   "textarea",
    "single":     "single",
    "multi":      "multi",
    "scale":      "single",
    "date":       "text",
    "time":       "text",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
}


# ── URL helpers ───────────────────────────────────────────────────────────────

def _normalise_url(url: str) -> str:
    """Accept any Google Forms URL variant and return the viewform URL."""
    url = url.strip()
    if "/viewform" in url:
        return url.split("?")[0]
    url = re.sub(r"/formResponse.*$", "/viewform", url)
    m = re.search(r"/forms/d/([^/]+)(?:/edit)?", url)
    if m:
        return f"https://docs.google.com/forms/d/e/{m.group(1)}/viewform"
    return url


def _extract_form_id(url: str) -> str:
    m = re.search(r"/forms/d/e/([^/]+)/", url)
    if m:
        return m.group(1)
    m = re.search(r"/forms/d/([^/]+)/", url)
    if m:
        return m.group(1)
    return "unknown"


def _extract_load_data_raw(html: str) -> list | None:
    """Same as _extract_load_data but also returns the raw string for debugging."""
    pattern = r"FB_PUBLIC_LOAD_DATA_\s*=\s*(\[.+?\]);\s*</script"
    m = re.search(pattern, html, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    return None


def _extract_load_data(html: str) -> list | None:
    """Pull FB_PUBLIC_LOAD_DATA_ JSON from the page source."""
    pattern = r"FB_PUBLIC_LOAD_DATA_\s*=\s*(\[.+?\]);\s*</script"
    m = re.search(pattern, html, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError as exc:
            logger.warning(f"JSON decode error in FB_PUBLIC_LOAD_DATA_: {exc}")
    return None


# ── Navigation parsing ────────────────────────────────────────────────────────

def _parse_go_to_page(opt: list, section_id_to_page: dict[int, int]) -> int | None:
    """
    Extract go_to_page index from a raw option array.

    Google Forms stores branching targets at opt[4] (sometimes opt[3]).
    Known formats for the navigation field:
      - None / 0            → next page (no specific target)
      - section_id (int)    → go to that section
      - [section_id, type]  → type 1 = go_to, type 2 = submit
      - [[section_id, type], ...] → same but wrapped in outer list
    All section IDs are large integers that map to 0-based page indices
    via section_id_to_page.
    """
    if not section_id_to_page:
        return None

    def _resolve_id(cid: int) -> int | None:
        if cid == 0:
            return None     # "next section" — handled by sequential fallback
        if cid < 0:
            return -1       # "submit form"
        return section_id_to_page.get(cid)

    for idx in (4, 3, 2):
        if len(opt) <= idx:
            continue
        nav = opt[idx]
        if nav is None:
            continue

        # ── bare int: opt[idx] = section_id ──────────────────────────────
        if isinstance(nav, (int, float)):
            nav_int = int(nav)
            if idx == 2:
                # opt[2] holds a raw section_id only for branching options.
                # Negative values here are NOT submit signals — they are
                # unrelated data (e.g. ordering/type flags) and must be
                # ignored to avoid false "submit form" navigation in
                # linear multi-section forms.
                target = section_id_to_page.get(nav_int)
                if target is not None:
                    return target
            else:
                r = _resolve_id(nav_int)
                if r is not None:
                    return r

        elif isinstance(nav, list) and nav:
            first = nav[0]

            # ── [section_id, goto_type] ───────────────────────────────────
            if isinstance(first, (int, float)):
                goto_type = nav[1] if len(nav) > 1 and isinstance(nav[1], (int, float)) else None
                if goto_type == 2:          # SUBMIT_FORM
                    return -1
                r = _resolve_id(int(first))
                if r is not None:
                    return r

            # ── [[section_id, goto_type], ...] ────────────────────────────
            elif isinstance(first, list) and first:
                inner_id   = first[0]
                inner_type = first[1] if len(first) > 1 else None
                if isinstance(inner_type, (int, float)) and int(inner_type) == 2:
                    return -1               # SUBMIT_FORM
                if isinstance(inner_id, (int, float)):
                    r = _resolve_id(int(inner_id))
                    if r is not None:
                        return r

    return None


# ── Question node parsing ─────────────────────────────────────────────────────

def _parse_question_node(
    node: list,
    page_index: int = 0,
    section_id_to_page: dict[int, int] | None = None,
) -> Question | None:
    """
    Parse a single question node from FB_PUBLIC_LOAD_DATA_.

    Node structure (simplified):
      [id, title, description, qtype_code, [entry_data, ...], ...]
    entry_data:
      [entry_id, option_list, ...]
    option (for single/multi):
      [value, image, is_default, ?, navigation_target?, ...]
    """
    try:
        title: str       = node[1] or ""
        description      = node[2] or None
        qtype_code: int  = node[3]
        entry_nodes: list = node[4]

        qtype_raw = _QTYPE_MAP.get(qtype_code, "text")
        qtype     = _INTERNAL_MAP.get(qtype_raw, "text")

        options: list[Option] = []
        entry_id = ""

        smap = section_id_to_page or {}

        for entry in entry_nodes:
            entry_id = str(entry[0])
            option_list = entry[1] if len(entry) > 1 else []
            if isinstance(option_list, list):
                for opt in option_list:
                    if isinstance(opt, list) and opt:
                        val = opt[0]
                        if val and val != "__other_option__":
                            go_to = _parse_go_to_page(opt, smap)
                            if smap and go_to is None and len(opt) > 3:
                                # Log raw option for debugging when navigation expected but not found
                                logger.debug(f"  opt raw (no nav found): {opt!r}")
                            options.append(Option(value=str(val), go_to_page=go_to))

        return Question(
            entry_id=entry_id,
            title=title.strip(),
            description=description,
            qtype=qtype,
            required=False,
            options=options,
            page_index=page_index,
        )
    except Exception as exc:
        logger.warning(f"Could not parse question node: {exc}")
        return None


# ── Top-level form data parser ────────────────────────────────────────────────

def _parse_load_data(data: list, form_id: str) -> ParsedForm:
    """
    Walk the nested structure to extract form title, sections and questions.

    Two-pass approach:
      Pass 1 — find all PAGE_BREAK (type 8) nodes and build
               section_id → page_index mapping.
      Pass 2 — parse questions, assigning page_index and option navigation.
    """
    try:
        form_info = data[1][8]
        title: str = form_info[0] if form_info else "Untitled Form"
        description: str | None = None
        try:
            description = data[1][8][2] or None
        except Exception:
            pass

        raw_nodes: list = data[1][1]

        # ── Pass 1: build section_id → page_index and page transitions ─────
        section_id_to_page: dict[int, int] = {}
        page_break_nodes: list[tuple[int, list]] = []  # (page_idx, raw_node)
        page_idx = 1           # page 0 is everything before the first PAGE_BREAK
        for node in raw_nodes:
            if isinstance(node, list) and len(node) >= 4 and node[3] == 8:
                section_id = int(node[0])
                section_id_to_page[section_id] = page_idx
                page_break_nodes.append((page_idx, node))
                logger.debug(f"Section id={section_id} → page {page_idx}")
                page_idx += 1

        # Extract section-level end-navigation from node[5] of PAGE_BREAK nodes
        # node[5]: negative → submit form; positive → section_id to jump to
        page_transitions: dict[str, int] = {}
        for pi, pb_node in page_break_nodes:
            raw_nav = pb_node[5] if len(pb_node) > 5 else None
            if raw_nav is None:
                continue
            if isinstance(raw_nav, (int, float)):
                nav_int = int(raw_nav)
                if nav_int < 0:
                    page_transitions[str(pi)] = -1  # submit
                elif nav_int > 0:
                    target = section_id_to_page.get(nav_int)
                    if target is not None:
                        page_transitions[str(pi)] = target

        total_pages = page_idx
        if total_pages > 1:
            logger.info(f"Multi-section form: {total_pages} pages, "
                        f"section map: {section_id_to_page}, "
                        f"transitions: {page_transitions}")

        # ── Pass 2: parse questions with page assignments ─────────────────
        questions: list[Question] = []
        current_page = 0

        for node in raw_nodes:
            if not isinstance(node, list) or len(node) < 4:
                continue

            qtype_code = node[3]

            if qtype_code == 8:              # PAGE_BREAK
                current_page = section_id_to_page.get(int(node[0]), current_page + 1)
                continue

            if len(node) < 5:
                continue

            q = _parse_question_node(node, current_page, section_id_to_page)
            if q and q.entry_id:
                # Log navigation info for branching questions
                branching = [(o.value, o.go_to_page) for o in q.options if o.go_to_page is not None]
                if branching:
                    logger.debug(f"Branching question '{q.title}': {branching}")
                questions.append(q)

        return ParsedForm(
            form_id=form_id,
            title=str(title).strip(),
            description=description,
            questions=questions,
            page_transitions=page_transitions,
        )
    except Exception as exc:
        raise ValueError(f"Cannot parse form structure: {exc}") from exc


# ── Debug helper ─────────────────────────────────────────────────────────────

async def fetch_raw_nodes(url: str) -> dict:
    """
    Download form HTML and return raw node data for debugging navigation.
    Shows all nodes with type, title, and raw option arrays.
    """
    view_url = _normalise_url(url)
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(
            view_url, allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status != 200:
                raise ConnectionError(f"HTTP {resp.status} for {view_url}")
            html = await resp.text()

    data = _extract_load_data(html)
    if data is None:
        raise ValueError("Could not find FB_PUBLIC_LOAD_DATA_")

    raw_nodes = data[1][1]

    # Build section map first
    section_id_to_page: dict[int, int] = {}
    page_idx = 1
    for node in raw_nodes:
        if isinstance(node, list) and len(node) >= 4 and node[3] == 8:
            section_id_to_page[int(node[0])] = page_idx
            page_idx += 1

    result = []
    for node in raw_nodes:
        if not isinstance(node, list) or len(node) < 4:
            continue
        entry = {
            "id": node[0],
            "title": node[1],
            "qtype": node[3],
            "qtype_name": _QTYPE_MAP.get(node[3], "?"),
        }
        if len(node) >= 5 and isinstance(node[4], list):
            entries_raw = []
            for en in node[4]:
                if isinstance(en, list) and len(en) >= 2:
                    entries_raw.append({
                        "entry_id": en[0],
                        "options_raw": en[1] if len(en) > 1 else [],
                    })
            entry["entries"] = entries_raw
        result.append(entry)

    return {
        "section_id_to_page": section_id_to_page,
        "nodes": result,
    }


# ── Public API ────────────────────────────────────────────────────────────────

async def parse_form(url: str) -> ParsedForm:
    """Download and parse a public Google Form. Returns ParsedForm."""
    view_url = _normalise_url(url)
    form_id  = _extract_form_id(view_url)
    logger.info(f"Parsing form: {view_url}  (id={form_id})")

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(
            view_url, allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status != 200:
                raise ConnectionError(f"HTTP {resp.status} for {view_url}")
            html = await resp.text()

    data = _extract_load_data(html)
    if data is None:
        raise ValueError(
            "Could not find FB_PUBLIC_LOAD_DATA_ in page HTML. "
            "Make sure the form is public (Anyone with the link can view)."
        )

    form = _parse_load_data(data, form_id)
    logger.success(f"Parsed '{form.title}' — {len(form.questions)} questions")
    return form

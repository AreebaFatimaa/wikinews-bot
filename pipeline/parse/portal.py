"""Scraper for Wikipedia's Portal:Current_events.

Fetches a dated subpage via the MediaWiki Action API, parses its wikitext to
canonical Event records. Production trigger is the Enterprise Realtime API
(see pipeline/ingest/); this module is the parsing core both code paths use.

Portal structure (verified against 2026 portal subpages):

    {{Current events|year=YYYY|month=MM|day=DD|content=
    '''Section heading'''
    *[[Topic link]]
    **[[Sub-topic link]]
    ***Actual event statement with [[wikilinks]] and [https://... (Source)] refs
    *[[Another topic]]
    **Event with citation [https://... (Outlet)]
    }}

Events are bullets that contain at least one external link (the citation).
Parent bullets at lower depths are hierarchical context (topic → subtopic),
preserved in `subject_path` on the body's leading metadata.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from urllib.parse import urlparse

import mwparserfromhell
import requests

from pipeline.schema import (
    TOPIC_CATEGORIES,
    V1_BRFA_CATEGORIES,
    Citation,
    Event,
    EventStatus,
    LinkedEntity,
    Source,
    Timestamps,
    WriteLane,
)

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = (
    "WikimediaNYC-CurrentEventsPipeline/0.1 "
    "(https://en.wikipedia.org/wiki/Wikipedia:Wikimedia_New_York_City; mailto:af3618@columbia.edu)"
)

_HEADING = re.compile(r"^'''(.+?)'''$")
_BULLET = re.compile(r"^(\*+)\s*(.*)$")
_TEMPLATE_CONTENT_OPEN = re.compile(r"\{\{\s*Current events\b.*?\|\s*content\s*=", re.DOTALL)


def _subpage_title(d: date) -> str:
    return f"Portal:Current events/{d.strftime('%Y %B %-d')}"


def fetch_wikitext(d: date, session: requests.Session | None = None) -> tuple[str, int]:
    s = session or requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    title = _subpage_title(d)
    r = s.get(
        WIKI_API,
        params={
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvprop": "content|ids",
            "rvslots": "main",
            "format": "json",
            "formatversion": "2",
        },
        timeout=30,
    )
    r.raise_for_status()
    pages = r.json()["query"]["pages"]
    if not pages or "missing" in pages[0]:
        raise FileNotFoundError(f"Portal subpage not found: {title}")
    rev = pages[0]["revisions"][0]
    return rev["slots"]["main"]["content"], rev["revid"]


def _event_id(d: date, category: str, body: str) -> str:
    norm = re.sub(r"\s+", " ", body).strip().lower()
    h = hashlib.sha256(f"{d.isoformat()}|{category}|{norm}".encode()).hexdigest()[:12]
    return f"ce_{d.isoformat()}_{category.replace('_', '-')}_{h}"


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _extract_inner_content(wikitext: str) -> str:
    """Strip the {{Current events|...|content=...}} template wrapper.

    Falls back to the raw wikitext if the template isn't found, so an unexpected
    portal-format change degrades to "still try to parse" rather than silent
    zero-events.
    """
    m = _TEMPLATE_CONTENT_OPEN.search(wikitext)
    if not m:
        return wikitext
    inner = wikitext[m.end():]
    if inner.endswith("}}"):
        inner = inner[:-2]
    elif "}}\n" in inner:
        inner = inner.rsplit("}}", 1)[0]
    return inner


def parse_portal(d: date, wikitext: str, rev_id: int) -> list[Event]:
    """Parse a portal subpage's wikitext into canonical Event records."""
    inner = _extract_inner_content(wikitext)
    events: list[Event] = []
    now = datetime.now(timezone.utc)

    current_topic_raw: str | None = None
    current_category: str | None = None
    breadcrumbs: list[str] = []

    for raw_line in inner.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("<!--"):
            continue

        m_h = _HEADING.match(line)
        if m_h:
            current_topic_raw = m_h.group(1).strip()
            current_category = TOPIC_CATEGORIES.get(current_topic_raw)
            breadcrumbs = []
            continue

        m_b = _BULLET.match(line)
        if not m_b or current_category is None or current_topic_raw is None:
            continue

        depth = len(m_b.group(1))
        bullet_wt = m_b.group(2)
        bullet_code = mwparserfromhell.parse(bullet_wt)
        plain = bullet_code.strip_code(normalize=True, collapse=True).strip()
        if not plain:
            continue

        breadcrumbs = breadcrumbs[: depth - 1] + [plain]

        ext_links = list(bullet_code.filter_external_links())
        if not ext_links:
            continue

        entities = [
            LinkedEntity(
                surface=str(link.text or link.title).strip(),
                wikipedia_title=str(link.title).strip(),
            )
            for link in bullet_code.filter_wikilinks()
        ]
        citations = [
            Citation(
                url=str(ext.url).strip(),
                domain=_domain(str(ext.url)),
                retrieved=now,
            )
            for ext in ext_links
        ]
        headline = plain.split(". ")[0][:200]
        subject_path = " > ".join(breadcrumbs[:-1]) if len(breadcrumbs) > 1 else ""
        body = f"[{subject_path}] {plain}" if subject_path else plain
        anchor = current_topic_raw.replace(" ", "_")
        lane = WriteLane.SAFE_AUTO if current_category in V1_BRFA_CATEGORIES else WriteLane.REVIEW

        events.append(
            Event(
                event_id=_event_id(d, current_category, body),
                source=Source(
                    rev_id=rev_id,
                    section_date=d,
                    section_topic=current_topic_raw,
                    section_anchor=f"#{anchor}",
                ),
                headline=headline,
                body=body,
                topic_category=current_category,
                linked_entities=entities,
                sources=citations,
                status=EventStatus.PARSED,
                write_lane=lane,
                timestamps=Timestamps(ingested_at=now, parsed_at=now),
            )
        )
    return events


def scrape(d: date) -> list[Event]:
    wikitext, rev_id = fetch_wikitext(d)
    return parse_portal(d, wikitext, rev_id)

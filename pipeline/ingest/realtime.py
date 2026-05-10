"""SSE consumer for Wikimedia EventStreams (public, no auth required).

Subscribes to https://stream.wikimedia.org/v2/stream/recentchange, server-side
no filter, then client-side filtered to enwiki + Portal:Current_events parent
and dated subpages. Yields raw recentchange payloads. The worker downstream
re-scrapes the affected portal subpage and persists fresh events.

Why EventStreams (not Wikimedia Enterprise Realtime): the free Enterprise tier
returns 403 on the Realtime endpoint. EventStreams is officially run by
Wikimedia, free, no auth, and provides recentchange events with all fields we
need (`wiki`, `title`, `meta.dt`, `revision.new`).

Resumability: caller passes `since` (RFC3339) to backfill from a checkpoint.
Reconnect/backoff is the worker loop's responsibility — this generator just
raises on transport error and the worker restarts it.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import requests

EVENTSTREAMS_URL = "https://stream.wikimedia.org/v2/stream/recentchange"
PORTAL_PARENT = "Portal:Current events"
PORTAL_PREFIX = "Portal:Current events/"
USER_AGENT = (
    "WikimediaNYC-CurrentEventsPipeline/0.1 "
    "(https://en.wikipedia.org/wiki/Wikipedia:Wikimedia_New_York_City; mailto:af3618@columbia.edu)"
)


def event_title(event: dict[str, Any]) -> str:
    """EventStreams uses `title`; older Realtime payloads use `name`. Accept both."""
    t = event.get("title") or event.get("name") or ""
    return t if isinstance(t, str) else ""


def is_portal_event(event: dict[str, Any]) -> bool:
    title = event_title(event)
    if not title:
        return False
    return title == PORTAL_PARENT or title.startswith(PORTAL_PREFIX)


def stream_enwiki_articles(since: str | None = None) -> Iterator[dict[str, Any]]:
    """Yield raw recentchange events for enwiki. Caller filters further."""
    params: dict[str, str] = {}
    if since:
        params["since"] = since
    headers = {
        "Accept": "text/event-stream",
        "User-Agent": USER_AGENT,
    }
    with requests.get(
        EVENTSTREAMS_URL,
        params=params,
        headers=headers,
        stream=True,
        timeout=(30, 600),
    ) as r:
        r.raise_for_status()
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data:"):
                continue
            try:
                payload = json.loads(raw[5:].lstrip())
            except json.JSONDecodeError:
                continue
            if payload.get("wiki") != "enwiki":
                continue
            yield payload


def stream_portal_events(since: str | None = None) -> Iterator[dict[str, Any]]:
    for event in stream_enwiki_articles(since=since):
        if is_portal_event(event):
            yield event

"""Postgres event store. Hybrid schema: top-level columns for queryable fields,
JSONB blob for the rest of the Pydantic Event model."""
from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Optional

import psycopg

from pipeline.schema import Event, EventStatus


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set; check .env.local")
    with psycopg.connect(url) as conn:
        yield conn


_UPSERT_SQL = """
INSERT INTO events (
    event_id, status, topic_category, write_lane, score, section_date, payload, updated_at
) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
ON CONFLICT (event_id) DO UPDATE SET
    status = EXCLUDED.status,
    topic_category = EXCLUDED.topic_category,
    write_lane = EXCLUDED.write_lane,
    score = EXCLUDED.score,
    payload = EXCLUDED.payload,
    updated_at = NOW()
"""


def upsert_event(event: Event, conn: Optional[psycopg.Connection] = None) -> None:
    payload = json.dumps(event.model_dump(mode="json"), default=str)
    args = (
        event.event_id,
        event.status if isinstance(event.status, str) else event.status.value,
        event.topic_category,
        event.write_lane if not event.write_lane or isinstance(event.write_lane, str)
        else event.write_lane.value,
        event.score,
        event.source.section_date,
        payload,
    )
    if conn is None:
        with connect() as c, c.cursor() as cur:
            cur.execute(_UPSERT_SQL, args)
        return
    with conn.cursor() as cur:
        cur.execute(_UPSERT_SQL, args)


def upsert_events(events: list[Event]) -> int:
    if not events:
        return 0
    with connect() as conn:
        for e in events:
            upsert_event(e, conn=conn)
        conn.commit()
    return len(events)


def get_event(event_id: str) -> Optional[Event]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT payload FROM events WHERE event_id = %s", (event_id,))
        row = cur.fetchone()
    if not row:
        return None
    return Event.model_validate(row[0])


def count_by_status() -> dict[str, int]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, COUNT(*) FROM events GROUP BY status ORDER BY status")
        return {status: n for status, n in cur.fetchall()}


def list_recent(limit: int = 20) -> list[Event]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT payload FROM events ORDER BY updated_at DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
    return [Event.model_validate(r[0]) for r in rows]


_CHECKPOINT_UPSERT_SQL = """
INSERT INTO checkpoints (name, since_ts, last_rev_id, events_processed, updated_at)
VALUES (%s, %s, %s, %s, NOW())
ON CONFLICT (name) DO UPDATE SET
    since_ts = EXCLUDED.since_ts,
    last_rev_id = EXCLUDED.last_rev_id,
    events_processed = EXCLUDED.events_processed,
    updated_at = NOW()
"""


def get_checkpoint(name: str) -> Optional[dict]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT name, since_ts, last_rev_id, events_processed, updated_at "
            "FROM checkpoints WHERE name = %s",
            (name,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "name": row[0],
        "since_ts": row[1],
        "last_rev_id": row[2],
        "events_processed": row[3],
        "updated_at": row[4],
    }


def set_checkpoint(
    name: str,
    *,
    since_ts: Optional[str] = None,
    last_rev_id: Optional[int] = None,
    events_processed: int = 0,
    conn: Optional[psycopg.Connection] = None,
) -> None:
    args = (name, since_ts, last_rev_id, events_processed)
    if conn is None:
        with connect() as c, c.cursor() as cur:
            cur.execute(_CHECKPOINT_UPSERT_SQL, args)
        return
    with conn.cursor() as cur:
        cur.execute(_CHECKPOINT_UPSERT_SQL, args)


__all__ = [
    "EventStatus",
    "connect",
    "count_by_status",
    "get_checkpoint",
    "get_event",
    "list_recent",
    "set_checkpoint",
    "upsert_event",
    "upsert_events",
]

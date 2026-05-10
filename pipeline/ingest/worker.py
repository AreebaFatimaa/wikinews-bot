"""Realtime worker: SSE → date extraction → re-scrape → upsert → checkpoint.

Long-running daemon. On each Portal:Current_events change event, re-scrapes
that day's subpage (the cheap, idempotent path) and persists fresh events.

Resilience: on SSE disconnect, backs off exponentially and reconnects with the
last-checkpoint `since` timestamp. Re-processing is safe because event IDs are
content-hashed (decision B) — duplicate work converges, doesn't accumulate.

Run:  pipeline worker [--since RFC3339] [--max-events N]
"""
from __future__ import annotations

import logging
import random
import re
import signal
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional

import requests

from pipeline.discord_bot.notify import notify
from pipeline.ingest.realtime import event_title, is_portal_event, stream_enwiki_articles
from pipeline.parse.portal import scrape
from pipeline.store.repo import get_checkpoint, set_checkpoint, upsert_events

CHECKPOINT_NAME = "realtime"
log = logging.getLogger("pipeline.worker")


def _format_event(ev: Any) -> str:
    """Render one Event as a Discord-friendly markdown message."""
    src = ev.sources[0].url if ev.sources else "(no source)"
    domain = ev.sources[0].domain if ev.sources else ""
    n_ents = len(ev.linked_entities)
    return (
        f"**[{ev.topic_category}]** {ev.headline}\n"
        f"Source: <{src}>"
        + (f" ({domain})" if domain else "")
        + f" · {n_ents} entities · lane=`{ev.write_lane}`"
    )

# Portal subpage titles look like "Portal:Current events/2026 May 9".
# Spaces and underscores interchangeable in Wikipedia titles.
_SUBPAGE_RE = re.compile(r"^Portal:Current[ _]events/(\d{4})[ _]([A-Za-z]+)[ _](\d{1,2})$")


@dataclass
class WorkerConfig:
    since: Optional[str] = None
    max_events: int = 0
    backoff_initial_s: float = 2.0
    backoff_max_s: float = 60.0
    backoff_multiplier: float = 2.0
    backoff_jitter: float = 0.25
    log_level: str = "INFO"


def extract_subpage_date(name: str) -> Optional[date]:
    """Parse a date out of a Portal:Current_events subpage title.

    Returns None for the parent page or non-matching names.
    """
    m = _SUBPAGE_RE.match(name)
    if not m:
        return None
    year, month_name, day = m.group(1), m.group(2), m.group(3)
    try:
        return datetime.strptime(f"{year} {month_name} {day}", "%Y %B %d").date()
    except ValueError:
        return None


def event_timestamp(event: dict[str, Any]) -> Optional[str]:
    """Best-effort RFC3339 extraction. EventStreams uses `meta.dt`."""
    meta = event.get("meta")
    if isinstance(meta, dict):
        dt = meta.get("dt")
        if isinstance(dt, str):
            return dt
    # Fallbacks for older/alternate payload shapes.
    for key in ("event", "date_modified", "date_created"):
        v = event.get(key)
        if isinstance(v, dict):
            ts = v.get("dt") or v.get("datetime")
            if isinstance(ts, str):
                return ts
        elif isinstance(v, str):
            return v
    return None


def event_rev_id(event: dict[str, Any]) -> Optional[int]:
    """EventStreams uses `revision.new` for the post-edit rev id."""
    rev = event.get("revision")
    if isinstance(rev, dict):
        for key in ("new", "id"):
            v = rev.get(key)
            if isinstance(v, int):
                return v
    v = event.get("version")
    if isinstance(v, dict):
        rid = v.get("identifier")
        if isinstance(rid, int):
            return rid
    return None


class _Stopped(Exception):
    pass


class Worker:
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.events_processed = 0
        self.last_since: Optional[str] = config.since
        self.last_rev_id: Optional[int] = None
        self._stop = False

    def stop(self, *_: Any) -> None:
        log.info("stop signal received; will exit after current event")
        self._stop = True

    def _resume_since(self) -> Optional[str]:
        if self.config.since:
            log.info(f"using --since override: {self.config.since}")
            return self.config.since
        cp = get_checkpoint(CHECKPOINT_NAME)
        if cp and cp.get("since_ts"):
            ts: datetime = cp["since_ts"]
            iso = ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            log.info(f"resuming from checkpoint: {iso} ({cp['events_processed']} events processed)")
            return iso
        log.info("no checkpoint; starting from live tail")
        return None

    def _process_one(self, event: dict[str, Any]) -> bool:
        """Returns True if this event was relevant and processed."""
        if not is_portal_event(event):
            return False
        title = event_title(event)
        d = extract_subpage_date(title)
        if d is None:
            log.debug(f"skipping non-dated portal page: {title}")
            return False

        log.info(f"event for {d.isoformat()} (page={title!r})")
        try:
            events = scrape(d)
        except FileNotFoundError:
            log.warning(f"subpage missing: {title}")
            return True
        except requests.RequestException as e:
            log.error(f"scrape failed for {d}: {e}")
            return True
        except Exception as e:
            log.exception(f"unexpected scrape error for {d}: {e}")
            return True

        if events:
            new_events = upsert_events(events)
            log.info(
                f"  scraped {len(events)} events for {d.isoformat()} "
                f"({len(new_events)} new)"
            )
            for ev in new_events:
                notify("DISCORD_CHANNEL_NOTIFICATIONS", _format_event(ev))
                time.sleep(0.3)  # stay under Discord rate limit

        ts = event_timestamp(event)
        rid = event_rev_id(event)
        self.last_since = ts or self.last_since
        self.last_rev_id = rid or self.last_rev_id
        self.events_processed += 1
        set_checkpoint(
            CHECKPOINT_NAME,
            since_ts=self.last_since,
            last_rev_id=self.last_rev_id,
            events_processed=self.events_processed,
        )
        return True

    def run(self) -> int:
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        since = self._resume_since()
        backoff = self.config.backoff_initial_s

        while not self._stop:
            try:
                log.info(f"connecting to Realtime stream (since={since})…")
                for event in stream_enwiki_articles(since=since):
                    if self._stop:
                        break
                    processed = self._process_one(event)
                    if processed:
                        backoff = self.config.backoff_initial_s
                        if (
                            self.config.max_events
                            and self.events_processed >= self.config.max_events
                        ):
                            log.info(
                                f"max-events {self.config.max_events} reached; exiting"
                            )
                            return 0
                # Stream ended cleanly (server-side close).
                log.info("stream closed cleanly; reconnecting from last checkpoint")
                since = self.last_since or since
            except KeyboardInterrupt:
                log.info("interrupted")
                return 0
            except requests.RequestException as e:
                log.warning(f"stream error: {e}; reconnecting in {backoff:.1f}s")
                jittered = backoff * (1 + random.uniform(-self.config.backoff_jitter, self.config.backoff_jitter))
                self._sleep_interruptible(max(0.5, jittered))
                backoff = min(self.config.backoff_max_s, backoff * self.config.backoff_multiplier)
                since = self.last_since or since
            except Exception as e:
                log.exception(f"unexpected error in worker loop: {e}")
                self._sleep_interruptible(backoff)
                backoff = min(self.config.backoff_max_s, backoff * self.config.backoff_multiplier)
        log.info(f"worker exiting; processed {self.events_processed} events")
        return 0

    def _sleep_interruptible(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while not self._stop and time.monotonic() < end:
            time.sleep(min(0.5, end - time.monotonic()))


def run_worker(config: WorkerConfig) -> int:
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        stream=sys.stderr,
    )
    return Worker(config).run()

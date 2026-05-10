"""Unit tests for worker pure functions. No network, no DB."""
from __future__ import annotations

from datetime import date

from pipeline.ingest.realtime import event_title, is_portal_event
from pipeline.ingest.worker import (
    event_rev_id,
    event_timestamp,
    extract_subpage_date,
)


def test_is_portal_event_parent():
    assert is_portal_event({"title": "Portal:Current events"})


def test_is_portal_event_subpage():
    assert is_portal_event({"title": "Portal:Current events/2026 May 9"})


def test_is_portal_event_legacy_name_field():
    # Older Realtime payloads use `name` instead of `title`.
    assert is_portal_event({"name": "Portal:Current events"})


def test_is_portal_event_unrelated():
    assert not is_portal_event({"title": "Barack Obama"})
    assert not is_portal_event({"title": "Portal:Mathematics"})
    assert not is_portal_event({"title": ""})
    assert not is_portal_event({})


def test_is_portal_event_lookalike():
    # Substring but doesn't start with the prefix.
    assert not is_portal_event({"title": "User:Foo/Portal:Current events"})


def test_event_title_prefers_title():
    assert event_title({"title": "A", "name": "B"}) == "A"


def test_event_title_falls_back_to_name():
    assert event_title({"name": "B"}) == "B"


def test_event_title_missing():
    assert event_title({}) == ""


def test_extract_subpage_date_basic():
    assert extract_subpage_date("Portal:Current events/2026 May 9") == date(2026, 5, 9)


def test_extract_subpage_date_underscores():
    assert extract_subpage_date("Portal:Current_events/2026_May_9") == date(2026, 5, 9)


def test_extract_subpage_date_two_digit_day():
    assert extract_subpage_date("Portal:Current events/2026 January 31") == date(2026, 1, 31)


def test_extract_subpage_date_parent_returns_none():
    assert extract_subpage_date("Portal:Current events") is None


def test_extract_subpage_date_invalid_month():
    assert extract_subpage_date("Portal:Current events/2026 Foozember 9") is None


def test_extract_subpage_date_invalid_day():
    assert extract_subpage_date("Portal:Current events/2026 February 30") is None


def test_event_timestamp_eventstreams_meta_dt():
    assert (
        event_timestamp({"meta": {"dt": "2026-05-09T12:00:00Z"}})
        == "2026-05-09T12:00:00Z"
    )


def test_event_timestamp_legacy_event_dt():
    assert (
        event_timestamp({"event": {"dt": "2026-05-09T12:00:00Z"}})
        == "2026-05-09T12:00:00Z"
    )


def test_event_timestamp_missing():
    assert event_timestamp({}) is None
    assert event_timestamp({"event": "not a dict"}) == "not a dict"


def test_event_rev_id_eventstreams():
    assert event_rev_id({"revision": {"new": 12345, "old": 12344}}) == 12345


def test_event_rev_id_legacy_version():
    assert event_rev_id({"version": {"identifier": 12345}}) == 12345


def test_event_rev_id_missing():
    assert event_rev_id({}) is None
    assert event_rev_id({"revision": "string"}) is None

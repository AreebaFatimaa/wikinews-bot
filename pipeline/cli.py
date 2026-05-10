"""Pipeline CLI for manual runs and end-to-end testing.

Subcommands:
  scrape --date YYYY-MM-DD                 fetch + parse one portal day
  scrape --date-range FROM:TO              fetch + parse a range of days
  scrape ... --persist                     upsert into Postgres
  scrape ... --summary                     one line per event
  scrape ... --out FILE                    write JSON to file
  worker [--since RFC3339] [--max-events N]  realtime worker daemon
  auth-test                                verify Wikimedia Enterprise credentials
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date as Date
from datetime import timedelta

from pipeline._env import load_env_local
from pipeline.parse.portal import scrape


def _date(s: str) -> Date:
    return Date.fromisoformat(s)


def _date_range(s: str) -> tuple[Date, Date]:
    if ":" not in s:
        raise argparse.ArgumentTypeError("expected FROM:TO (e.g. 2026-04-01:2026-05-09)")
    a, b = s.split(":", 1)
    da, db = _date(a), _date(b)
    if db < da:
        raise argparse.ArgumentTypeError(f"end {db} is before start {da}")
    return da, db


def _scrape_one(d: Date, persist: bool) -> tuple[int, str | None]:
    """Returns (n_events, error_message_or_None)."""
    try:
        events = scrape(d)
    except FileNotFoundError as e:
        return 0, f"missing: {e}"
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"
    if persist and events:
        from pipeline.store.repo import upsert_events
        upsert_events(events)
    return len(events), None


def cmd_scrape(args: argparse.Namespace) -> int:
    if args.date_range:
        start, end = args.date_range
        return _cmd_scrape_range(start, end, args)
    return _cmd_scrape_single(args.date, args)


def _cmd_scrape_single(d: Date, args: argparse.Namespace) -> int:
    events = scrape(d)
    if args.persist:
        from pipeline.store.repo import upsert_events
        new = upsert_events(events)
        print(
            f"persisted {len(events)} events ({len(new)} new)",
            file=sys.stderr,
        )

    if args.summary:
        for e in events:
            print(
                f"[{e.write_lane:>10}] {e.topic_category:>14} | "
                f"{len(e.linked_entities):>2} ents, {len(e.sources):>2} refs | "
                f"{e.headline[:80]}"
            )
        print(f"\n{len(events)} events parsed for {d.isoformat()}", file=sys.stderr)
        return 0

    if args.out:
        payload = [e.model_dump(mode="json") for e in events]
        with open(args.out, "w") as f:
            f.write(json.dumps(payload, indent=2, default=str))
        print(f"wrote {len(events)} events to {args.out}", file=sys.stderr)
    else:
        payload = [e.model_dump(mode="json") for e in events]
        print(json.dumps(payload, indent=2, default=str))
    return 0


def _cmd_scrape_range(start: Date, end: Date, args: argparse.Namespace) -> int:
    total_events = 0
    days_ok = 0
    days_failed: list[tuple[Date, str]] = []
    n_days = (end - start).days + 1

    print(f"Backfill: {start} → {end}  ({n_days} days)", file=sys.stderr)
    for i in range(n_days):
        d = start + timedelta(days=i)
        n, err = _scrape_one(d, persist=args.persist)
        if err is None:
            print(f"  {d}  {n:>3} events", file=sys.stderr)
            days_ok += 1
            total_events += n
        else:
            print(f"  {d}  ERROR  {err}", file=sys.stderr)
            days_failed.append((d, err))
        if i < n_days - 1:
            time.sleep(0.2)

    print(
        f"\n{days_ok}/{n_days} days ok, {total_events} events"
        f"{' persisted' if args.persist else ' parsed (not persisted)'}",
        file=sys.stderr,
    )
    if days_failed:
        print(f"{len(days_failed)} failures:", file=sys.stderr)
        for d, err in days_failed:
            print(f"  {d}  {err}", file=sys.stderr)
        return 1
    return 0


def cmd_auth_test(args: argparse.Namespace) -> int:
    from pipeline.ingest.test_auth import main as run
    return run()


def cmd_worker(args: argparse.Namespace) -> int:
    from pipeline.ingest.worker import WorkerConfig, run_worker
    cfg = WorkerConfig(since=args.since, max_events=args.max_events)
    return run_worker(cfg)


def main(argv: list[str] | None = None) -> int:
    load_env_local()

    p = argparse.ArgumentParser(prog="pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("scrape", help="Scrape one or more portal days")
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--date", type=_date, help="YYYY-MM-DD")
    g.add_argument("--date-range", type=_date_range, help="FROM:TO (inclusive)")
    sp.add_argument("--out", help="Write JSON to file (single-day mode only)")
    sp.add_argument("--summary", action="store_true", help="One-line per event")
    sp.add_argument("--persist", action="store_true", help="Upsert events to Postgres")
    sp.set_defaults(func=cmd_scrape)

    sa = sub.add_parser("auth-test", help="Verify Wikimedia Enterprise credentials")
    sa.set_defaults(func=cmd_auth_test)

    sw = sub.add_parser("worker", help="Run the realtime SSE→parse→DB worker")
    sw.add_argument("--since", help="RFC3339 timestamp; overrides DB checkpoint")
    sw.add_argument(
        "--max-events",
        type=int,
        default=0,
        help="Exit after processing N relevant events (0 = run forever)",
    )
    sw.set_defaults(func=cmd_worker)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

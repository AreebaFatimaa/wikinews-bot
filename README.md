# Wikimedia Current Events → Wikidata Pipeline

A data-driven successor to [Portal:Current_events](https://en.wikipedia.org/wiki/Portal:Current_events), stewarded by Wikimedia NYC. Scrapes the portal, converts entries to a versioned machine-readable schema, scores them for newsworthiness, and publishes structured statements to Wikidata via a hybrid auto-publish/Discord-review bot.

## Status

**Phase 0 — Governance, infra, Liftwing probe (week 1).** See [docs/PHASE_0_CHECKLIST.md](docs/PHASE_0_CHECKLIST.md).

The full locked plan: [docs/PLAN.md](docs/PLAN.md).

## Quickstart (local dev)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# Smoke test — scrape today's Current Events portal
pipeline scrape --date 2026-05-10 --summary

# Full canonical JSON for one day
pipeline scrape --date 2026-05-10 --out out/2026-05-10.json

# Phase 0 Liftwing probe
python -m pipeline.score.liftwing_probe
```

## Architecture (one-line)

`Realtime SSE → parser → Postgres event store → scorer → {safe-auto, review} → Wikidata writer + Discord bot`

Detailed diagram and phasing: [docs/PLAN.md](docs/PLAN.md).

## Repo layout

```
pipeline/
  schema.py              canonical Event contract (Pydantic, versioned)
  parse/portal.py        MediaWiki Action API + mwparserfromhell parser
  score/liftwing_probe.py  Phase 0 Liftwing model survey
  ingest/                Realtime SSE consumer (Phase 1)
  publish/               pywikibot writer (Phase 5, gated by BRFA)
  discord_bot/           discord.py bot (Phase 2)
  cli.py                 manual runs and testing
docs/
  PLAN.md                locked plan (architecture, phases, risks)
  PHASE_0_CHECKLIST.md   what the operator must do, in order
  BRFA_DRAFT.md          BRFA submission template
  BOT_USERPAGE_DRAFT.md  bot User: page template
  AUP_QUESTION.md        wording for the #wikimedia-cloud AUP question
tests/
  golden/                portal-parse regression fixtures (Phase 1)
```

## License

MIT. Tool must be open-source per Toolforge AUP.

## Contact

Operator: [Wikidata username — TBD, see Phase 0 checklist].
Maintainer email: af3618@columbia.edu.

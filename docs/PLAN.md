# Pipeline Plan (locked 2026-05-10)

## Confirmed parameters

| | |
|---|---|
| Stack | Python 3.11+ (pywikibot, mwparserfromhell, requests, discord.py) |
| Change feed | Wikimedia Enterprise Realtime API (operator has account) |
| Hosting | Wikimedia Toolforge |
| Bot operator of record | Operator's Wikidata account, named on BRFA |
| Write model | **Hybrid** — bot auto-publishes safe edits (source/reference statements on existing items); new-item minting and politically-sensitive attachments go through Discord `/approve` |
| BRFA v1 scope | Disasters + Sports only; expand category-by-category after clean trial |
| Scoring | Liftwing probe in Phase 0; if no fit, Claude `claude-opus-4-7` rubric (structured output, prompt-cached) |
| Discord bot | Notifications + `/scrape now`, `/retry`, `/events today`, `/search`, `/diff`, `/approve`, `/reject` + AI-assisted newsworthiness suggestions |

## Architecture

```
Enterprise Realtime API (SSE) ──┐
                                 ├─► Ingestor → Parser ──► Postgres event store
Discord /scrape now ─────────────┘                          (FSM with statuses)
                                                                   │
                                                                   ▼
                                                              Scorer
                                                          (Liftwing OR Claude
                                                           + heuristic prefilter)
                                                                   │
                                              ┌────────────────────┼─────────────────┐
                                              ▼                    ▼                 ▼
                                    SAFE EDIT lane          REVIEW lane        Discord bot
                                    (refs/sources on        (new items,        notifications
                                     existing items)         ambiguous)        + queries
                                              │                    │                 │
                                              │                    ▼                 │
                                              │              /approve in            │
                                              │              Discord ───────────────┤
                                              │                    │                 │
                                              ▼                    ▼                 │
                                    Wikidata Writer (pywikibot, idempotent,
                                    rate-limited per BRFA, on-wiki kill switch)
                                              │
                                              ▼
                                       www.wikidata.org
```

## Canonical event schema

Versioned JSON contract (`schema_version: "1.0"`), defined in `pipeline/schema.py`. Key fields:

- `event_id` — deterministic: `ce_{date}_{category}_{idx}`
- `source` — page, rev_id, section_date, section_topic, section_anchor
- `headline`, `body`, `topic_category` — controlled vocab keyed off section heading
- `linked_entities[]` — surface, wikipedia_title, wikidata_qid, role, confidence
- `sources[]` — url, domain, publisher_qid, retrieved
- `wikidata_proposal` — primary_item, target_qid, statements[] (pre-mapped to P-numbers: P31 instance-of, P585 point-in-time, P276 location, P17 country, P361 part-of, P1476 title, P248/P854/P813 for references)
- `score`, `score_components`, `score_rationale`
- `status` (FSM: ingested → parsed → scored → proposed → approved | rejected → publishing → published | failed | needs_review)
- `write_lane` — `safe_auto` or `review`
- `review`, `publish.attempts`, `timestamps`

## Phasing

Each phase is gated. Anything downstream of an unfinished gate runs in **dry-run** mode (records to audit_log + Discord, no Wikidata writes).

### Phase 0 — Governance, infra, Liftwing probe (week 1)
- Toolforge tool registration (`current-events-pipeline`)
- AUP confirmation in `#wikimedia-cloud` for Discord gateway WebSocket + outbound Anthropic API calls (with VPS fallback if denied)
- Postgres provisioning on `tools.db.svc.wikimedia.cloud`
- Secrets in `$HOME` chmod 600 + gitleaks pre-commit + CI
- **Bot account registration** on Wikidata (operator's identity), 2FA on operator account, OAuth owner-only consumer
- **Liftwing probe** — enumerate deployed models; commit to Liftwing or Claude fallback

### Phase 1 — Read-only ingest + parse + store (weeks 2–3)
- Realtime SSE consumer with reconnect/backoff, filtered to `Portal:Current_events`
- `mwparserfromhell` parser with golden-file regression tests (30+ archived portal days)
- Postgres schema + Alembic migrations; FSM enforced in code
- Backfill CLI: `python -m pipeline.cli replay --date YYYY-MM-DD`
- **Gate:** parser passes goldens, ingestor 7-day soak

### Phase 2 — Scoring + Discord read-side (weeks 3–4, parallel)
- Heuristic prefilter (source count, domain trust list, named-entity density, geographic spread)
- Scorer (Liftwing or Claude rubric with structured output)
- Discord bot (read-only first): `/events today`, `/search`, `/diff`, notifications for ingest/parse/score/error events
- **Gate:** rubric reviewed, ≥90% of editor-judged-newsworthy events score ≥0.5

### Phase 3 — Bot trust-building (weeks 4–7, *human-paced*)
- 50–100 high-quality manual edits from bot account on Wikidata (typo fixes, missing labels, source additions — uncontroversial)
- Bot user page: operator name, purpose, source repo URL, opt-out instructions, edit-rate cap
- **Gate:** clean edit history, complete user page

### Phase 4 — BRFA submission + supervised trial (weeks 6–10, overlaps Phase 3)
- BRFA scoped to **Disasters + Sports only**; explicit P-numbers; edit-rate cap (≤1/min, ≤200/day); dry-run examples generated by Phases 1–2
- During BRFA review: pipeline runs **propose-only**; Phabricator paste of proposed diffs for community review
- On trial approval: 50-edit live trial with every edit gated by `/approve` in Discord
- **Gate:** BRFA closed approved; bot flag granted

### Phase 5 — Hybrid auto-publish enablement (week 10+)
- **SAFE_AUTO lane** (auto): adding `P248`/`P854`/`P813` references to *existing* event items; appending to existing "significant event" lists
- **REVIEW lane** (Discord `/approve` required): minting new event items; adding to politically-sensitive items; any low-confidence entity resolution
- Auto-publish enabled per-category one at a time after a 1-week observation window
- On-wiki kill switch (`User:[BotName]/Run`) polled every 60s
- Auto-pause if 24h revert ratio >5%

### Phase 6 — Hardening and scope expansion (ongoing)
- Prometheus metrics on `tools-prometheus`: ingest lag, parse failure rate, score distribution, edit success, kill-switch state
- Daily portal-markup canary parses yesterday's portal, alerts Discord on schema drift
- Quarterly bias review of scoring outputs
- Amended BRFAs to expand to Science → Health → Arts → Business → Politics → Armed conflicts (one at a time, 4+ weeks track record per expansion)

## Top risks (with concrete mitigations)

- **BRFA delay or rejection** → Phases 1–2 ship value without writes (public JSON dump on Toolforge static site, Discord query bot). Fallback: human-driven `/approve` → operator-account edits.
- **Portal markup breaks parser** → 30-day golden-file regression suite + daily canary; parser degrades to `status=needs_review` instead of crashing.
- **Over-publishing → flag revocation** → hard rate limit *in code*, on-wiki kill switch, per-edit source citation, weekly summary post to project talk page, auto-pause on >5% 24h revert ratio.
- **Toolforge AUP issues** → Phase-0 explicit check; fallback moves Discord bot + Claude calls to chapter VPS, halves talk via authenticated HTTPS.
- **Scoring bias** → rubric reviewed, explicit weighting for non-Western sources and non-English Wikipedia link presence, score components stored separately, quarterly bias audit.
- **Duplicate publishes on retry** → idempotency key (`event_id` + statement fingerprint), pre-write check on Wikidata for matching statement, edit summary includes key.

## Out of scope for v1

Editing Wikipedia itself; non-English portals; original reporting; web UI (Discord only); auto-minting people QIDs (events and statements on existing items only); backfill beyond 90 days; replacing the portal.

## Note on the OpenAI / Wikimedia premise

There is no built-in OpenAI integration in the Wikidata REST API. The January 2026 Wikimedia AI partnerships (Amazon, Meta, Microsoft, Mistral, Perplexity — not OpenAI) are one-way *content licensing* deals. Newsworthiness scoring must be implemented externally; we use Liftwing first and Claude as fallback.

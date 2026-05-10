# Phase 0 Checklist

Phase 0 must close before Phase 1 begins. Items marked **[OPERATOR]** require the human operator's identity and cannot be automated. Items marked **[CODE]** are already in this repo or scriptable.

## Order matters — do these in sequence

### 1. [OPERATOR] Confirm Toolforge AUP for Discord + Anthropic outbound

Post the question in `docs/AUP_QUESTION.md` to `#wikimedia-cloud` on Libera Chat (or to `cloud@lists.wikimedia.org`). **Do not start Toolforge work until you have a yes/no on both.**

- If **YES** to both → continue.
- If **NO** to Discord bot → Discord bot moves off Toolforge to a chapter-controlled VPS; Toolforge keeps scraper/parser/writer; halves talk via authenticated HTTPS.
- If **NO** to Anthropic outbound → forces Liftwing-only scoring (or move scorer off Toolforge with the bot).

### 2. [OPERATOR] Register Toolforge tool

1. Sign in to <https://toolsadmin.wikimedia.org/> with your Wikimedia developer account.
2. Create a new tool: `current-events-pipeline` (or close variant if taken).
3. Add Wikimedia NYC contacts as maintainers.
4. SSH in: `ssh login.toolforge.org`, then `become current-events-pipeline`.
5. Confirm Python 3.13 prebuilt image is available: `webservice --backend=kubernetes python3.13 shell` (or use jobs framework).

### 3. [OPERATOR] Provision Toolforge Postgres

Per <https://wikitech.wikimedia.org/wiki/Help:Toolforge/PostgreSQL>:

```bash
# Once become'd as the tool
toolforge envvars list   # see what's already wired
```

Tool databases live on `tools.db.svc.wikimedia.cloud`. Confirm `TOOL_DB_*` envvars exist or follow the Toolforge docs to create one.

### 4. [OPERATOR] Register Wikidata bot account

1. While **logged out**, register a new account at <https://www.wikidata.org>:
   - Suggested name: `WikimediaNYC-CurrentEventsBot` (must include "Bot" in name per Wikidata convention)
   - Confirm via email
   - Enable **2FA** immediately
2. Stay logged in as the bot account, link an email you control.
3. **Do not edit yet** — see step 6 for trust-building edits.

### 5. [OPERATOR] Register OAuth owner-only consumer for the bot

Per <https://www.wikidata.org/wiki/Wikidata:REST_API/Authentication>:

1. Visit <https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration/propose>.
2. Owner-only consumer (faster approval, no community vote).
3. Grants: "Edit existing pages", "Create, edit, and move pages", "Perform high volume activity".
4. Save the four secrets to `~/secrets/wikidata_oauth.env` (chmod 600). **Never commit these.**

### 6. [OPERATOR] Phase 3 prerequisite — start trust-building edits

The 50–100 manual edits from the bot account in Phase 3 take human time, so start now. Make uncontroversial edits:
- Add missing English labels/descriptions
- Add `P248`/`P854`/`P813` references to unsourced statements
- Fix typos in descriptions

Track progress informally in `docs/BRFA_TRIAL_LOG.md` (you'll create this).

### 7. [CODE] Run Liftwing probe

```bash
python -m pipeline.score.liftwing_probe
```

Output goes in `docs/LIFTWING_PROBE_RESULT.md` (you'll create this with the JSON output and a one-line decision).

If no candidates, Phase 2 scorer is Claude rubric. If candidates, evaluate each against a sample of historical events before committing.

### 8. [CODE] Verify scraper end-to-end

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pipeline scrape --date 2026-05-09 --summary
```

Should print one line per parsed event with category, entity count, source count, headline.

### 9. [OPERATOR] Set up secrets

Once Toolforge tool exists:

```bash
toolforge envvars create WIKIDATA_OAUTH_ACCESS_TOKEN
toolforge envvars create WIKIDATA_OAUTH_ACCESS_SECRET
toolforge envvars create WIKIDATA_OAUTH_CONSUMER_TOKEN
toolforge envvars create WIKIDATA_OAUTH_CONSUMER_SECRET
toolforge envvars create ENTERPRISE_API_USERNAME
toolforge envvars create ENTERPRISE_API_PASSWORD
# Discord and Anthropic, only if AUP cleared step 1:
toolforge envvars create DISCORD_BOT_TOKEN
toolforge envvars create ANTHROPIC_API_KEY
```

### 10. [OPERATOR] Install pre-commit hooks locally

```bash
pip install pre-commit
pre-commit install
# Verify gitleaks runs
git diff | gitleaks detect --pipe || echo "ok"
```

## Phase 0 exit criteria

- [ ] AUP question answered (Discord + Anthropic)
- [ ] Toolforge tool registered, Postgres reachable
- [ ] Bot account registered, 2FA on, OAuth consumer approved
- [ ] First 5 trust-building edits made from bot account
- [ ] Liftwing probe run, decision logged
- [ ] Scraper smoke-tested locally (CLI returns ≥10 events for a recent date)
- [ ] Toolforge envvars populated (no secrets in repo)
- [ ] pre-commit hooks installed and working

When all 8 boxes are checked, Phase 1 may begin.

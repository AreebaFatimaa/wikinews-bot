"""Phase 0 credential smoke tests.

Runs five independent checks against `.env.local`:
  1. All expected env vars are populated
  2. Postgres connects (DATABASE_URL)
  3. Wikimedia Enterprise auth issues a JWT
  4. Wikidata OAuth token resolves to the bot's profile
  5. Discord bot logs in and can see all 3 configured channels

Each check runs independently; missing optional deps degrade to SKIP rather than
fail the whole script. Exits 1 if any non-skipped check fails.

Usage:  python scripts/check_env.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Make `import pipeline.*` work when running as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline._env import load_env_local  # noqa: E402


# ─── Result types ──────────────────────────────────────────────────────────────

class Result:
    def __init__(self, name: str):
        self.name = name
        self.status: str = "?"
        self.detail: str = ""

    def ok(self, detail: str = "") -> "Result":
        self.status, self.detail = "PASS", detail
        return self

    def fail(self, detail: str) -> "Result":
        self.status, self.detail = "FAIL", detail
        return self

    def skip(self, detail: str) -> "Result":
        self.status, self.detail = "SKIP", detail
        return self

    def __str__(self) -> str:
        glyph = {"PASS": "✓", "FAIL": "✗", "SKIP": "·"}.get(self.status, "?")
        line = f"  {glyph} {self.status}  {self.name}"
        if self.detail:
            line += f"\n         {self.detail}"
        return line


# ─── Check 1: env vars present ─────────────────────────────────────────────────

REQUIRED_VARS = [
    "WIKI_ENTERPRISE_USERNAME",
    "WIKI_ENTERPRISE_PASSWORD",
    "WIKIDATA_OAUTH_CLIENT_ID",
    "WIKIDATA_OAUTH_CLIENT_SECRET",
    "WIKIDATA_OAUTH_ACCESS_TOKEN",
    "DISCORD_BOT_TOKEN",
    "DISCORD_GUILD_ID",
    "DISCORD_CHANNEL_NOTIFICATIONS",
    "DISCORD_CHANNEL_REVIEW",
    "DISCORD_CHANNEL_ERRORS",
    "DATABASE_URL",
]
OPTIONAL_VARS = ["ANTHROPIC_API_KEY", "SENTRY_DSN", "DISCORD_APPLICATION_ID", "DISCORD_PUBLIC_KEY"]


def check_env_vars() -> Result:
    r = Result("env vars populated")
    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        return r.fail(f"missing/empty: {', '.join(missing)}")
    skipped_optional = [v for v in OPTIONAL_VARS if not os.environ.get(v)]
    detail = f"{len(REQUIRED_VARS)} required vars set"
    if skipped_optional:
        detail += f"; optional unset: {', '.join(skipped_optional)}"
    return r.ok(detail)


# ─── Check 2: Postgres connects ────────────────────────────────────────────────

def check_postgres() -> Result:
    r = Result("Postgres connects + SELECT 1")
    try:
        import psycopg
    except ImportError:
        return r.skip("psycopg not installed — `pip install -e .[db]` to enable")
    url = os.environ.get("DATABASE_URL")
    if not url:
        return r.fail("DATABASE_URL not set")
    try:
        with psycopg.connect(url, connect_timeout=10) as conn, conn.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
        return r.ok(version.split(",")[0])
    except Exception as e:
        return r.fail(f"{type(e).__name__}: {e}")


# ─── Check 3: Wikimedia Enterprise auth ────────────────────────────────────────

def check_wikimedia_enterprise() -> Result:
    r = Result("Wikimedia Enterprise login")
    try:
        from pipeline.ingest.auth import EnterpriseAuth
    except ImportError as e:
        return r.fail(f"could not import EnterpriseAuth: {e}")
    try:
        auth = EnterpriseAuth()
        token = auth.access_token()
        ttl = auth.token_expires_in
        return r.ok(f"got JWT ({len(token)} chars), expires in {ttl}s (~{ttl // 3600}h)")
    except Exception as e:
        return r.fail(f"{type(e).__name__}: {e}")


# ─── Check 4: Wikidata OAuth profile ───────────────────────────────────────────

def check_wikidata_oauth() -> Result:
    r = Result("Wikidata OAuth token → profile")
    import requests
    token = os.environ.get("WIKIDATA_OAUTH_ACCESS_TOKEN")
    if not token:
        return r.fail("WIKIDATA_OAUTH_ACCESS_TOKEN not set")
    url = "https://www.wikidata.org/w/rest.php/oauth2/resource/profile"
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
    except Exception as e:
        return r.fail(f"{type(e).__name__}: {e}")
    if resp.status_code == 401:
        return r.fail("401 Unauthorized — token rejected. Owner-only flag set on consumer?")
    if resp.status_code != 200:
        return r.fail(f"HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        data = resp.json()
    except ValueError:
        return r.fail(f"non-JSON response: {resp.text[:200]}")
    username = data.get("username", "?")
    blocked = data.get("blocked", False)
    grants = data.get("grants", [])
    detail = f"user={username} blocked={blocked} grants={grants}"
    if blocked:
        return r.fail(f"account is blocked! {detail}")
    # Phase 4 needs Wikibase grants; flag if absent (warning, not failure).
    has_wikibase = any("wikibase" in g.lower() or "edit" in g.lower() for g in grants)
    if not has_wikibase:
        detail += "  ⚠  no edit/wikibase grants visible — fine for Phase 0, blocks Phase 4"
    return r.ok(detail)


# ─── Check 5: Discord bot + channels ───────────────────────────────────────────

async def _discord_check_async() -> tuple[bool, str]:
    try:
        import discord
    except ImportError:
        return False, "SKIP:discord.py not installed — `pip install -e .[discord]` to enable"

    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        return False, "DISCORD_BOT_TOKEN not set"

    channel_vars = {
        "DISCORD_CHANNEL_NOTIFICATIONS": os.environ.get("DISCORD_CHANNEL_NOTIFICATIONS"),
        "DISCORD_CHANNEL_REVIEW": os.environ.get("DISCORD_CHANNEL_REVIEW"),
        "DISCORD_CHANNEL_ERRORS": os.environ.get("DISCORD_CHANNEL_ERRORS"),
    }
    guild_id = os.environ.get("DISCORD_GUILD_ID")
    if not guild_id:
        return False, "DISCORD_GUILD_ID not set"

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    findings: dict[str, str] = {}

    @client.event
    async def on_ready():
        try:
            findings["bot"] = f"{client.user} ({client.user.id})"
            guild = client.get_guild(int(guild_id))
            findings["guild"] = guild.name if guild else f"NOT FOUND ({guild_id})"
            for var, cid in channel_vars.items():
                if not cid:
                    findings[var] = "NOT SET"
                    continue
                ch = client.get_channel(int(cid))
                findings[var] = f"#{ch.name}" if ch else f"NOT VISIBLE ({cid})"
        finally:
            await client.close()

    try:
        await asyncio.wait_for(client.start(token), timeout=30)
    except asyncio.TimeoutError:
        return False, "timed out connecting to Discord gateway after 30s"
    except discord.LoginFailure as e:
        return False, f"login failed: {e}"
    except Exception as e:
        # Normal close after on_ready raises CancelledError-ish; treat as success
        # only if we collected findings.
        if not findings:
            return False, f"{type(e).__name__}: {e}"

    bot = findings.get("bot", "?")
    guild = findings.get("guild", "?")
    channels = " ".join(
        f"{var.split('_')[-1].lower()}={findings.get(var, '?')}" for var in channel_vars
    )
    bad = [v for v in findings.values() if "NOT" in v]
    detail = f"bot={bot} guild={guild} {channels}"
    if bad:
        return False, detail
    return True, detail


def check_discord() -> Result:
    r = Result("Discord bot connects + sees 3 channels")
    try:
        ok, detail = asyncio.run(_discord_check_async())
    except Exception as e:
        return r.fail(f"{type(e).__name__}: {e}")
    if detail.startswith("SKIP:"):
        return r.skip(detail[5:])
    return r.ok(detail) if ok else r.fail(detail)


# ─── Driver ────────────────────────────────────────────────────────────────────

def main() -> int:
    env_path = load_env_local()
    print(f"Loaded env from: {env_path}\n" if env_path else "No .env.local found\n")

    results = [
        check_env_vars(),
        check_postgres(),
        check_wikimedia_enterprise(),
        check_wikidata_oauth(),
        check_discord(),
    ]
    for res in results:
        print(res)

    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status == "SKIP")
    passed = sum(1 for r in results if r.status == "PASS")
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

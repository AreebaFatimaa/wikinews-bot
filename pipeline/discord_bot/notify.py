"""Minimal Discord notifier — calls the REST API directly with the bot token.

Avoids running a discord.py Client (and its async loop) inside the sync worker.
For Phase 2's slash-command bot we'll still want a full client; this is just
fire-and-forget channel posts.

Errors are swallowed (logged at debug, no raise) — Discord outages must never
crash the ingest pipeline.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

DISCORD_API_BASE = "https://discord.com/api/v10"
USER_AGENT = (
    "WikimediaNYC-CurrentEventsPipeline (https://en.wikipedia.org/wiki/"
    "Wikipedia:Wikimedia_New_York_City, 0.1)"
)
MAX_CONTENT_LEN = 2000  # Discord hard limit per message.

log = logging.getLogger("pipeline.discord")


def notify(channel_env_var: str, content: str) -> Optional[bool]:
    """Post `content` to the channel ID held in env var `channel_env_var`.

    Returns:
      True  — posted (HTTP 2xx)
      False — disabled (no token or no channel id)
      None  — attempted, but Discord rejected or transport failed (logged)
    """
    token = os.environ.get("DISCORD_BOT_TOKEN")
    channel_id = os.environ.get(channel_env_var)
    if not token or not channel_id:
        log.debug(f"discord notify skipped: token={'set' if token else 'unset'} "
                  f"channel_id={'set' if channel_id else 'unset'}")
        return False

    url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
    body = content if len(content) <= MAX_CONTENT_LEN else content[: MAX_CONTENT_LEN - 1] + "…"

    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bot {token}",
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
            },
            json={"content": body},
            timeout=10,
        )
    except requests.RequestException as e:
        log.warning(f"discord notify transport error: {e}")
        return None

    if not r.ok:
        log.warning(f"discord notify rejected {r.status_code}: {r.text[:200]}")
        return None
    return True

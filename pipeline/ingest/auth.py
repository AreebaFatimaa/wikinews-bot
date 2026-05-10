"""Wikimedia Enterprise JWT auth client.

Per https://enterprise.wikimedia.com/docs/authentication/:
  1. POST {username (lowercase), password} to /v1/login
  2. Response: {access_token, refresh_token, id_token, expires_in}
  3. Use Authorization: Bearer <access_token> on Realtime + On-Demand calls.
  4. access_token TTL ~24h; refresh_token TTL ~90d.

Tokens live in memory only — never written to disk.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

import requests

LOGIN_URL = "https://auth.enterprise.wikimedia.com/v1/login"
REFRESH_URL = "https://auth.enterprise.wikimedia.com/v1/token-refresh"

# Refresh this many seconds before actual expiry. Avoids racing the boundary.
REFRESH_LEEWAY_S = 5 * 60


@dataclass
class Token:
    access_token: str
    refresh_token: str
    expires_at: float

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at - REFRESH_LEEWAY_S


class EnterpriseAuth:
    """Thread-safe token manager with auto-refresh."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        session: requests.Session | None = None,
    ):
        self.username = (username or os.environ.get("WIKI_ENTERPRISE_USERNAME") or "").lower()
        self.password = password or os.environ.get("WIKI_ENTERPRISE_PASSWORD") or ""
        if not self.username or not self.password:
            raise RuntimeError(
                "WIKI_ENTERPRISE_USERNAME and WIKI_ENTERPRISE_PASSWORD must be set. "
                "Put them in .env.local (gitignored) for local dev."
            )
        self._session = session or requests.Session()
        self._lock = threading.Lock()
        self._token: Token | None = None

    def _login(self) -> Token:
        r = self._session.post(
            LOGIN_URL,
            json={"username": self.username, "password": self.password},
            timeout=30,
        )
        if r.status_code == 401:
            raise RuntimeError(
                "Wikimedia Enterprise login failed (401). Check WIKI_ENTERPRISE_USERNAME "
                "(must be lowercase) and WIKI_ENTERPRISE_PASSWORD."
            )
        r.raise_for_status()
        data = r.json()
        return Token(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=time.time() + int(data.get("expires_in", 86400)),
        )

    def access_token(self) -> str:
        with self._lock:
            if self._token is None or self._token.expired:
                self._token = self._login()
            return self._token.access_token

    def auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token()}"}

    @property
    def token_expires_in(self) -> int:
        with self._lock:
            if self._token is None:
                return 0
            return max(0, int(self._token.expires_at - time.time()))

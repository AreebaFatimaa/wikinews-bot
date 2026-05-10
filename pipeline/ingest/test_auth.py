"""Smoke test for Wikimedia Enterprise credentials.

Run: pipeline auth-test  (or: python -m pipeline.ingest.test_auth)

Exits 0 if login succeeds; non-zero with a clear error otherwise.
NEVER prints the access token or any token-shaped value.
"""
from __future__ import annotations

import sys

from pipeline._env import load_env_local
from pipeline.ingest.auth import EnterpriseAuth


def main() -> int:
    load_env_local()
    try:
        auth = EnterpriseAuth()
    except RuntimeError as e:
        print(f"Setup error: {e}", file=sys.stderr)
        return 2

    try:
        token = auth.access_token()
    except RuntimeError as e:
        print(f"Auth failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Auth error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if not token or len(token) < 50:
        print("Login returned empty/short token — unexpected response shape.", file=sys.stderr)
        return 1

    minutes = auth.token_expires_in // 60
    print(f"Auth OK. Username '{auth.username}' authenticated; "
          f"token valid for ~{minutes} minutes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

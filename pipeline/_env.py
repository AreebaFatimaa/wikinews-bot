"""Lightweight `.env.local` loader. Avoids a python-dotenv dependency.

Call `load_env_local()` once at the top of each CLI entry point. Real environment
variables take precedence over file values, so production deployments (Toolforge
envvars, GitHub Actions secrets) override anything in the local file.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_env_local(filename: str = ".env.local") -> Path | None:
    p = REPO_ROOT / filename
    if not p.exists():
        return None
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    return p

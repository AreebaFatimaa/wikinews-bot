"""Phase 0 probe: enumerate Liftwing-deployed models and tag candidates for
newsworthiness/quality scoring.

If at least one candidate is found, v1 scorer SHOULD be Liftwing (no external
LLM dependency, more legitimacy inside the Wikimedia ecosystem). If none, v1
scorer falls back to Claude rubric in pipeline/score/claude_scorer.py
(Phase 2).

Run: python -m pipeline.score.liftwing_probe
"""
from __future__ import annotations

import json
import sys
from typing import Any

import requests

LIFTWING_BASE = "https://api.wikimedia.org/service/lw/inference/v1/models"
LIFTWING_DOCS = "https://api.wikimedia.org/wiki/Lift_Wing_API/Reference"
USER_AGENT = (
    "WikimediaNYC-CurrentEventsPipeline/0.1 (mailto:af3618@columbia.edu)"
)

CANDIDATE_KEYWORDS = (
    "quality",
    "topic",
    "drafttopic",
    "articletopic",
    "revertrisk",
    "revscoring",
)


def list_models(session: requests.Session | None = None) -> list[dict[str, Any]]:
    s = session or requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    r = s.get(LIFTWING_BASE, timeout=30)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    payload = r.json()
    return payload if isinstance(payload, list) else payload.get("models", [])


def evaluate(models: list[dict[str, Any]]) -> dict[str, Any]:
    candidates, unlikely = [], []
    for m in models:
        text = f"{m.get('name', '')} {m.get('description', '')}".lower()
        (candidates if any(k in text for k in CANDIDATE_KEYWORDS) else unlikely).append(m)
    return {
        "n_models": len(models),
        "n_candidates": len(candidates),
        "candidates": candidates,
        "unlikely_count": len(unlikely),
    }


def main() -> int:
    try:
        models = list_models()
    except requests.RequestException as e:
        print(f"Liftwing index fetch failed: {e}", file=sys.stderr)
        print(f"Manual review: {LIFTWING_DOCS}", file=sys.stderr)
        return 2

    if not models:
        print("No model index returned.")
        print(f"Manual review required: {LIFTWING_DOCS}")
        print("Look for: articlequality, drafttopic, articletopic, revertrisk")
        return 1

    report = evaluate(models)
    print(json.dumps(report, indent=2))
    if report["n_candidates"] == 0:
        print(
            "\nNo candidates. Recommend Phase-2 fallback to Claude rubric scorer.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

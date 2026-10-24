"""Loads the versioned policy fixture. The fixture, not the LLM, is the source of truth for rules."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from .config import POLICY_DIR

DEFAULT_POLICY_FILE = "policy_v2.json"


def load_policy(filename: str | None = None) -> dict:
    filename = filename or os.getenv("PCN_POLICY_FILE", "").strip() or DEFAULT_POLICY_FILE
    if Path(filename).name != filename or Path(filename).suffix != ".json":
        raise ValueError("PCN_POLICY_FILE must name a JSON file in backend/policy.")
    return _load_policy(filename)


@lru_cache(maxsize=4)
def _load_policy(filename: str) -> dict:
    return json.loads((POLICY_DIR / filename).read_text(encoding="utf-8"))


def reference_ids(policy: dict | None = None) -> set[str]:
    policy = policy or load_policy()
    return {ref["id"] for ref in policy["references"]}


def references_by_id(policy: dict | None = None) -> dict[str, dict]:
    policy = policy or load_policy()
    return {ref["id"]: ref for ref in policy["references"]}

"""Loads the versioned policy fixture. The fixture, not the LLM, is the source of truth for rules."""
from __future__ import annotations

import json
from functools import lru_cache

from .config import POLICY_DIR

DEFAULT_POLICY_FILE = "policy_v1.json"


@lru_cache(maxsize=4)
def load_policy(filename: str = DEFAULT_POLICY_FILE) -> dict:
    return json.loads((POLICY_DIR / filename).read_text(encoding="utf-8"))


def reference_ids(policy: dict | None = None) -> set[str]:
    policy = policy or load_policy()
    return {ref["id"] for ref in policy["references"]}


def references_by_id(policy: dict | None = None) -> dict[str, dict]:
    policy = policy or load_policy()
    return {ref["id"]: ref for ref in policy["references"]}

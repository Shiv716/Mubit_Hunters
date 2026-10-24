"""Reviewed-precedent retrieval.

This is context retrieval, not model training: curated officer decisions on similar past cases are passed to the
model as guidance. Similarity is a transparent lexical score (no vector database).
"""
from __future__ import annotations

import re
from .db import Connection

_STOP = set("""a an the and or but if of to in on at by for with from as is was were be been it its this that
i me my we our you your he she they them their there here have has had do did not no so very just also
am are will would could should can may might than then into out up down over under about after before
parking pcn ticket notice council car vehicle please""".split())


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2 and w not in _STOP}


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def score(query: dict, example: dict) -> float:
    code = 1.0 if query["contravention_code"] == example["contravention_code"] else 0.0
    grounds = _jaccard(set(query["claimed_grounds"]), set(example["claimed_grounds"]))
    text = _jaccard(tokens(query["text"]), tokens(example["summary_text"]))
    return round(0.4 * code + 0.3 * grounds + 0.3 * text, 4)


def retrieve(query: dict, examples: list[dict], top_k: int = 3, min_score: float = 0.35,
             exclude_case_id: int | None = None) -> list[dict]:
    scored = []
    for ex in examples:
        if exclude_case_id is not None and ex.get("case_id") == exclude_case_id:
            continue
        s = score(query, ex)
        if s >= min_score:
            scored.append((s, ex))
    scored.sort(key=lambda p: (-p[0], p[1]["id"]))
    return [
        {
            "precedent_id": f"PREC-{ex['id']}",
            "similarity": s,
            "contravention_code": ex["contravention_code"],
            "claimed_grounds": ex["claimed_grounds"],
            "case_summary": ex["summary_text"],
            "reviewed_outcome": ex["final_label"],
            "officer_reason": ex.get("correction_reason"),
        }
        for s, ex in scored[:top_k]
    ]


def load_eligible(conn: Connection, sources: tuple[str, ...] = ("review",)) -> list[dict]:
    placeholders = ",".join("?" * len(sources))
    rows = conn.execute(
        f"SELECT * FROM feedback_examples WHERE curation_status='eligible' AND source IN ({placeholders})",
        sources,
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["claimed_grounds"] = d["claimed_grounds"].split(",") if d["claimed_grounds"] else []
        out.append(d)
    return out


def summary_text(case_json: dict) -> str:
    return case_json["representation_text"][:600]

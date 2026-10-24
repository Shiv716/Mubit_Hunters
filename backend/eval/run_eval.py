"""Baseline vs feedback-informed (precedent retrieval) evaluation on the fixed synthetic holdout set.

  python eval/run_eval.py                      # provider from env (mubit if MUBIT_API_KEY set, else stub)
  python eval/run_eval.py --provider stub      # offline plumbing check; does NOT measure Mubit
  python eval/run_eval.py --limit 10 --record  # subset; also store the report in the app DB

Precedents come only from the dataset's 'pool' split; the 'holdout' split is never used as a precedent, so there
is no leakage. Release gates are fixed below *before* any run. Improvement is only claimed if the gates pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ai.adapters import STUB_PROVIDER, get_adapter  # noqa: E402
from app.config import DATA_DIR, get_settings  # noqa: E402
from app.models import CaseIn  # noqa: E402
from app.precedents import retrieve  # noqa: E402
from app.service import review_core  # noqa: E402

LABELS = ("accept", "reject", "needs_review")

# Pre-registered release gates for "feedback-informed is better than baseline".
RELEASE_GATES = {
    "min_accuracy_gain": 0.05,          # absolute, on effective recommendation
    "max_mcnemar_p": 0.05,              # exact two-sided test on discordant pairs
    "no_increase_in_failure_rate": True,
    "no_increase_in_unsupported_reference_rate": True,
}


def pool_examples(dataset: dict) -> list[dict]:
    out = []
    for i, item in enumerate(dataset["pool"], start=1):
        c = item["case"]
        out.append({"id": i, "case_id": None, "contravention_code": c["contravention_code"],
                    "claimed_grounds": c["claimed_grounds"], "summary_text": c["representation_text"],
                    "final_label": item["gold_label"], "correction_reason": item["officer_reason"],
                    "scenario": item["scenario"]})
    return out


def metrics(golds: list[str], preds: list[str]) -> dict:
    n = len(golds)
    acc = sum(g == p for g, p in zip(golds, preds)) / n if n else 0.0
    per, f1s = {}, []
    for lab in LABELS:
        tp = sum(g == lab and p == lab for g, p in zip(golds, preds))
        fp = sum(g != lab and p == lab for g, p in zip(golds, preds))
        fn = sum(g == lab and p != lab for g, p in zip(golds, preds))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per[lab] = {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3), "support": tp + fn}
        f1s.append(f1)
    confusion = {g: {p: sum(gg == g and pp == p for gg, pp in zip(golds, preds)) for p in LABELS} for g in LABELS}
    return {"accuracy": round(acc, 4), "macro_f1": round(sum(f1s) / len(f1s), 4), "per_label": per,
            "confusion_gold_by_pred": confusion}


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact binomial test on discordant pairs (b: only baseline right, c: only feedback right)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return round(min(1.0, 2 * tail), 4)


def run_arm(adapter, items: list[dict], pool: list[dict] | None, top_k: int, workers: int) -> list[dict]:
    def one(item):
        case = CaseIn.model_validate(item["case"])
        precedents = None
        if pool is not None:
            q = {"contravention_code": case.contravention_code, "claimed_grounds": case.claimed_grounds,
                 "text": case.representation_text}
            precedents = retrieve(q, pool, top_k=top_k)
        core = review_core(case, adapter, precedents)
        s = core.safety
        pool_by_id = {f"PREC-{p['id']}": p for p in (pool or [])}
        return {
            "pcn_ref": case.pcn_ref, "scenario": item["scenario"], "gold": item["gold_label"],
            "indicator": core.indicator,
            "model_recommendation": (s.parsed or {}).get("recommendation"),
            "effective": s.effective_recommendation, "status": s.status, "failure_kind": s.failure_kind,
            "flags": s.flags, "latency_ms": core.result.latency_ms, "request_id": core.result.request_id,
            "precedents": [p["precedent_id"] for p in (precedents or [])],
            "same_scenario_precedent": any(pool_by_id[p["precedent_id"]]["scenario"] == item["scenario"]
                                           for p in (precedents or [])),
        }
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(one, items))


def summarise(rows: list[dict]) -> dict:
    golds = [r["gold"] for r in rows]
    lat = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    return {
        "n": len(rows),
        "effective": metrics(golds, [r["effective"] for r in rows]),
        "model_raw": metrics(golds, [r["model_recommendation"] or "needs_review" for r in rows]),
        "failure_rate": round(sum(r["status"] == "failed" for r in rows) / len(rows), 4),
        "unsupported_reference_rate": round(sum(any("unsupported" in f or "unverified" in f for f in r["flags"])
                                                for r in rows) / len(rows), 4),
        "rule_conflict_rate": round(sum(any(f.startswith("conflicts_with") for f in r["flags"]) for r in rows) / len(rows), 4),
        "mean_latency_ms": round(sum(lat) / len(lat), 1) if lat else None,
    }


def to_markdown(report: dict) -> str:
    b, f = report["baseline"], report["feedback"]
    lines = [
        f"# Evaluation report — {report['created_at']}",
        "",
        f"- Provider: **{report['provider']}** · model: `{report['model']}`",
        f"- Dataset: `{report['dataset_version']}` (sha256 {report['dataset_sha256'][:12]}…), holdout n={b['n']}, "
        f"precedent pool n={report['pool_size']}, synthetic data",
        f"- Feedback arm = same model + same system prompt + top-{report['top_k']} reviewed precedents in the user message.",
        "  This is precedent retrieval, **not model training**.",
    ]
    if report["provider"] == STUB_PROVIDER:
        lines += ["", "> **Offline stub run.** The stub ignores precedents and is not Mubit. These numbers check the "
                      "pipeline only and say nothing about Mubit or about precedent retrieval."]
    lines += [
        "", "| Metric | Deterministic only | Baseline | Feedback-informed |", "|---|---|---|---|",
        f"| Accuracy (effective) | {report['deterministic']['accuracy']} | {b['effective']['accuracy']} | {f['effective']['accuracy']} |",
        f"| Macro-F1 (effective) | {report['deterministic']['macro_f1']} | {b['effective']['macro_f1']} | {f['effective']['macro_f1']} |",
        f"| Accuracy (raw model) | – | {b['model_raw']['accuracy']} | {f['model_raw']['accuracy']} |",
        f"| Failure rate | – | {b['failure_rate']} | {f['failure_rate']} |",
        f"| Unsupported-reference rate | – | {b['unsupported_reference_rate']} | {f['unsupported_reference_rate']} |",
        f"| Rule-conflict rate | – | {b['rule_conflict_rate']} | {f['rule_conflict_rate']} |",
        f"| Mean latency ms | – | {b['mean_latency_ms']} | {f['mean_latency_ms']} |",
        "",
        f"Discordant pairs: baseline-only correct = {report['paired']['baseline_only_correct']}, "
        f"feedback-only correct = {report['paired']['feedback_only_correct']}; exact McNemar p = {report['paired']['mcnemar_p']}.",
        f"Precedent coverage: {report['precedent_coverage']}.",
        "",
        "## Release gates (pre-registered)", "",
    ]
    for k, v in report["gates"]["checks"].items():
        lines.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    lines += ["", f"**Verdict: {report['gates']['verdict']}**", "",
              "Limitations: small synthetic dataset; gold labels written by the team; one model; one run "
              "(LLM outputs can vary between runs)."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["mubit", "stub"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--workers", type=int, default=2, help="parallel calls; starter credit limits concurrency")
    ap.add_argument("--record", action="store_true", help="store report in the app DB")
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    args = ap.parse_args(argv)

    settings = get_settings()
    if args.provider:
        settings = replace(settings, ai_provider=args.provider)
    adapter = get_adapter(settings)
    raw = (DATA_DIR / "eval_dataset.json").read_bytes()
    dataset = json.loads(raw)
    holdout = dataset["holdout"][: args.limit] if args.limit else dataset["holdout"]
    pool = pool_examples(dataset)

    t0 = time.time()
    base_rows = run_arm(adapter, holdout, None, args.top_k, args.workers)
    feed_rows = run_arm(adapter, holdout, pool, args.top_k, args.workers)
    golds = [r["gold"] for r in base_rows]
    base, feed = summarise(base_rows), summarise(feed_rows)
    b_only = sum(b["effective"] == b["gold"] and f["effective"] != f["gold"] for b, f in zip(base_rows, feed_rows))
    f_only = sum(f["effective"] == f["gold"] and b["effective"] != b["gold"] for b, f in zip(base_rows, feed_rows))
    p = mcnemar_exact(b_only, f_only)
    checks = {
        "accuracy_gain >= %.2f" % RELEASE_GATES["min_accuracy_gain"]:
            feed["effective"]["accuracy"] - base["effective"]["accuracy"] >= RELEASE_GATES["min_accuracy_gain"],
        "mcnemar_p < %.2f" % RELEASE_GATES["max_mcnemar_p"]: p < RELEASE_GATES["max_mcnemar_p"],
        "failure_rate_not_higher": feed["failure_rate"] <= base["failure_rate"],
        "unsupported_reference_rate_not_higher": feed["unsupported_reference_rate"] <= base["unsupported_reference_rate"],
    }
    if adapter.provider == STUB_PROVIDER:
        verdict = "NOT APPLICABLE - offline stub run, no claim about Mubit or precedents"
    elif all(checks.values()):
        verdict = "Improvement supported on this holdout set (all gates pass)"
    elif feed["effective"]["accuracy"] > base["effective"]["accuracy"]:
        verdict = "Inconclusive - higher accuracy but gates not met; do not claim improvement"
    else:
        verdict = "No measured improvement"

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provider": adapter.provider,
        "model": settings.mubit_model if adapter.provider == "mubit" else "offline-stub-v1",
        "dataset_version": dataset["dataset_version"], "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "pool_size": len(pool), "top_k": args.top_k, "duration_s": round(time.time() - t0, 1),
        "deterministic": metrics(golds, [r["indicator"] for r in base_rows]),
        "baseline": base, "feedback": feed,
        "paired": {"baseline_only_correct": b_only, "feedback_only_correct": f_only, "mcnemar_p": p},
        "precedent_coverage": {
            "cases_with_precedents": sum(bool(r["precedents"]) for r in feed_rows),
            "cases_with_same_scenario_precedent": sum(r["same_scenario_precedent"] for r in feed_rows),
            "n": len(feed_rows)},
        "gates": {"definition": RELEASE_GATES, "checks": checks, "verdict": verdict},
        "rows": {"baseline": base_rows, "feedback": feed_rows},
    }
    args.out.mkdir(parents=True, exist_ok=True)
    stem = f"{report['created_at'].replace(':', '').replace('-', '')}_{adapter.provider}"
    (args.out / f"{stem}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (args.out / f"{stem}.md").write_text(to_markdown(report), encoding="utf-8")
    if args.record:
        from app.db import init_db, transaction
        init_db()
        with transaction() as conn:
            conn.execute("INSERT INTO evaluation_runs (dataset_version, provider, model, report_json, created_at)"
                         " VALUES (?,?,?,?,?)", (report["dataset_version"], report["provider"], report["model"],
                                                 json.dumps({k: v for k, v in report.items() if k != "rows"}),
                                                 report["created_at"]))
    print(to_markdown(report))
    print(f"Saved {args.out / stem}.json/.md")
    return report


if __name__ == "__main__":
    main()

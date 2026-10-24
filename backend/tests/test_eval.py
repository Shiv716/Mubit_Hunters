import json

from eval.run_eval import main, mcnemar_exact, metrics


def test_mcnemar():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(0, 6) == 0.0312
    assert mcnemar_exact(3, 3) == 1.0


def test_metrics_confusion():
    m = metrics(["accept", "reject", "needs_review"], ["accept", "accept", "needs_review"])
    assert m["accuracy"] == round(2 / 3, 4)
    assert m["confusion_gold_by_pred"]["reject"]["accept"] == 1


def test_stub_eval_runs_and_makes_no_claim(tmp_path):
    report = main(["--provider", "stub", "--limit", "8", "--out", str(tmp_path)])
    assert report["provider"] == "offline-stub"
    assert report["gates"]["verdict"].startswith("NOT APPLICABLE")
    # stub ignores precedents -> identical arms
    assert report["baseline"]["effective"] == report["feedback"]["effective"]
    assert report["precedent_coverage"]["cases_with_precedents"] > 0
    files = list(tmp_path.iterdir())
    assert any(f.suffix == ".md" for f in files)
    saved = json.loads(next(f for f in files if f.suffix == ".json").read_text())
    assert saved["dataset_version"] == "pcn-eval-v1"


def test_no_leakage_between_pool_and_holdout():
    from app.config import DATA_DIR
    data = json.loads((DATA_DIR / "eval_dataset.json").read_text(encoding="utf-8"))
    pool_texts = {i["case"]["representation_text"] for i in data["pool"]}
    hold_texts = {i["case"]["representation_text"] for i in data["holdout"]}
    assert not pool_texts & hold_texts
    pool_refs = {i["case"]["pcn_ref"] for i in data["pool"]}
    assert not pool_refs & {i["case"]["pcn_ref"] for i in data["holdout"]}

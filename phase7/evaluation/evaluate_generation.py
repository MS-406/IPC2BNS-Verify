"""
evaluate_generation.py — Generation + Verifier + Category-wise Metric Calculator

Computes all metrics from Phase 7 raw results:
- Answer accuracy (citation hit rate)
- Section accuracy, Citation completeness
- Verifier: TP/TN/FP/FN, Precision, Recall, F1, FPR, Specificity
- Category-wise results table
- Comparison with original N=60 results
- Wilson confidence intervals (using existing harness utility)

Usage:
    python phase7/evaluation/evaluate_generation.py
"""

import os
import sys
import json
import csv
import math
import datetime
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PHASE7_ROOT = os.path.join(PROJECT_ROOT, "phase7")
CODE_DIR = os.path.join(PROJECT_ROOT, "code")

for p in [CODE_DIR, PROJECT_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

TABLES_DIR = os.path.join(PHASE7_ROOT, "results", "tables")
FIGURES_DIR = os.path.join(PHASE7_ROOT, "results", "figures")
os.makedirs(TABLES_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

# Use Wilson CI from existing harness (read-only import)
try:
    from src.eval.harness import wilson_score_interval
except Exception:
    def wilson_score_interval(successes, total, confidence=0.95):
        if total == 0:
            return (0.0, 0.0)
        z = 1.95996
        p_hat = successes / total
        denominator = 1 + (z**2) / total
        centre = (p_hat + (z**2) / (2 * total)) / denominator
        margin = (z * math.sqrt((p_hat * (1 - p_hat) + (z**2) / (4 * total)) / total)) / denominator
        return round(max(0.0, (centre - margin) * 100), 1), round(min(100.0, (centre + margin) * 100), 1)


def find_latest_results(raw_dir: str) -> str:
    files = sorted([f for f in os.listdir(raw_dir) if f.endswith(".json")])
    if not files:
        raise FileNotFoundError(f"No raw results in {raw_dir}")
    return os.path.join(raw_dir, files[-1])


def compute_proportions(hits: int, total: int) -> Dict:
    acc = hits / total if total > 0 else 0.0
    ci = wilson_score_interval(hits, total)
    return {
        "hits": hits, "total": total,
        "accuracy": round(acc * 100, 2),
        "ci_low": ci[0], "ci_high": ci[1],
        "formatted": f"{acc*100:.1f}% ({hits}/{total}) [{ci[0]}%–{ci[1]}%]"
    }


# ─── Generation metrics ────────────────────────────────────────────────────────

def compute_generation_metrics(results: List[Dict]) -> Dict:
    def subset_gen(recs):
        n = len(recs)
        if n == 0:
            return {"n": 0}
        
        cit_hits = sum(1 for r in recs if r.get("citation_any_hit", False))
        cit_all = sum(1 for r in recs if r.get("citation_all_covered", False))
        has_gen = sum(1 for r in recs if r.get("generated_text") and
                      r["generated_text"] not in ("", "GENERATOR_NOT_AVAILABLE"))
        
        return {
            "n": n,
            "citation_any_hit": compute_proportions(cit_hits, n),
            "citation_all_covered": compute_proportions(cit_all, n),
            "generation_attempted": compute_proportions(has_gen, n),
        }
    
    natural = [r for r in results if not r.get("is_adversarial", False)]
    adversarial = [r for r in results if r.get("is_adversarial", False)]
    
    cat_groups = defaultdict(list)
    for r in results:
        cat_groups[r.get("category", "unknown")].append(r)
    
    return {
        "overall": subset_gen(results),
        "natural": subset_gen(natural),
        "adversarial": subset_gen(adversarial),
        "by_category": {cat: subset_gen(recs) for cat, recs in sorted(cat_groups.items())}
    }


# ─── Verifier metrics ─────────────────────────────────────────────────────────

def compute_verifier_metrics(results: List[Dict]) -> Dict:
    """
    Verifier as a binary classifier:
    - Natural questions: correct = VERIFIED (TP=verified+correct, FN=not_verified+correct)
    - Adversarial questions: correct = REJECTED (TP=rejected, FN=incorrectly_verified)
    
    Overall confusion matrix uses adversarial as the "positive" class for stress testing.
    """
    
    def verifier_stats(recs, positive_is_adversarial=False):
        n = len(recs)
        if n == 0:
            return {"n": 0}
        
        has_verifier = [r for r in recs if r.get("verifier_verdict") not in (None, "ERROR")]
        nv = len(has_verifier)
        if nv == 0:
            return {"n": n, "verifier_available": 0}
        
        # Classification
        tp = fp = tn = fn = 0
        verdicts = defaultdict(int)
        
        for r in has_verifier:
            is_adv = r.get("is_adversarial", False)
            is_verified = r.get("verifier_is_verified", False)
            verdict = r.get("verifier_verdict", "")
            verdicts[verdict] += 1
            
            if is_adv:
                # Positive class = adversarial. Correct = REJECTED
                if not is_verified:
                    tp += 1  # Correctly caught
                else:
                    fn += 1  # Missed adversarial
            else:
                # Negative class = natural. Correct = VERIFIED
                if is_verified:
                    tn += 1
                else:
                    fp += 1  # False alarm on legitimate question
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        
        # Stress catch rate (adversarial only)
        adv_recs = [r for r in has_verifier if r.get("is_adversarial", False)]
        stress_caught = sum(1 for r in adv_recs if not r.get("verifier_is_verified", True))
        
        # Control FPR (natural only)
        nat_recs = [r for r in has_verifier if not r.get("is_adversarial", False)]
        control_rejected = sum(1 for r in nat_recs if not r.get("verifier_is_verified", True))
        
        stress_ci = wilson_score_interval(stress_caught, len(adv_recs)) if adv_recs else (0.0, 0.0)
        fpr_ci = wilson_score_interval(control_rejected, len(nat_recs)) if nat_recs else (0.0, 0.0)
        
        return {
            "n": n,
            "n_with_verifier": nv,
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": round(precision * 100, 2),
            "recall": round(recall * 100, 2),
            "f1": round(f1 * 100, 2),
            "specificity": round(specificity * 100, 2),
            "fpr": round(fpr * 100, 2),
            "stress_catch_rate": compute_proportions(stress_caught, len(adv_recs)) if adv_recs else {"n": 0},
            "control_fpr": compute_proportions(control_rejected, len(nat_recs)) if nat_recs else {"n": 0},
            "verdict_distribution": dict(verdicts),
        }
    
    cat_groups = defaultdict(list)
    for r in results:
        cat_groups[r.get("category", "unknown")].append(r)
    
    return {
        "overall": verifier_stats(results),
        "by_category": {cat: verifier_stats(recs) for cat, recs in sorted(cat_groups.items())}
    }


# ─── Category-wise master table ────────────────────────────────────────────────

def build_category_table(results: List[Dict]) -> List[Dict]:
    cat_groups = defaultdict(list)
    for r in results:
        cat_groups[r.get("category", "unknown")].append(r)
    
    rows = []
    for cat, recs in sorted(cat_groups.items()):
        n = len(recs)
        r5 = sum(r.get("recall_at_5", 0) for r in recs) / n if n else 0
        mrr = sum(r.get("mrr", 0) for r in recs) / n if n else 0
        hits = sum(1 for r in recs if r.get("citation_any_hit", False))
        acc = hits / n if n else 0
        
        # Verifier F1
        has_v = [r for r in recs if r.get("verifier_verdict") not in (None, "ERROR")]
        if has_v:
            adv = [r for r in has_v if r.get("is_adversarial")]
            nat = [r for r in has_v if not r.get("is_adversarial")]
            tp = sum(1 for r in adv if not r.get("verifier_is_verified", True))
            fp = sum(1 for r in nat if not r.get("verifier_is_verified", True))
            fn = sum(1 for r in adv if r.get("verifier_is_verified", False))
            tn = sum(1 for r in nat if r.get("verifier_is_verified", True))
            p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rc = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * p * rc / (p + rc) if (p + rc) > 0 else 0.0
            ver_f1 = f"{f1*100:.1f}%"
        else:
            ver_f1 = "N/A"
        
        ci = wilson_score_interval(hits, n)
        rows.append({
            "category": cat,
            "n": n,
            "recall_at_5": f"{r5*100:.1f}%",
            "mrr": f"{mrr:.3f}",
            "answer_accuracy": f"{acc*100:.1f}% ({hits}/{n})",
            "answer_accuracy_ci": f"[{ci[0]}%–{ci[1]}%]",
            "citation_accuracy": f"{acc*100:.1f}%",
            "verifier_f1": ver_f1,
        })
    
    return rows


# ─── Original vs Large-Scale comparison ───────────────────────────────────────

def build_comparison_table(phase7_results: List[Dict]) -> List[Dict]:
    """Compare Phase 7 results with original N=60 published results."""
    
    # Original results from existing files (read-only)
    orig = {
        "stage": "Stage 2 (RAG)",
        "n": 60,
        "accuracy": "63.3% (38/60)",
        "accuracy_ci": "[50.7%–74.4%]",
        "stress_catch_rate": "100.0% (18/18)",
        "control_fpr": "0.0% (0/12)",
        "procedural": "100.0% (30/30)",
        "benchmark": "Original N=60 development benchmark",
        "note": "Existing published results — UNCHANGED"
    }
    
    # Phase 7 results
    n7 = len(phase7_results)
    hits7 = sum(1 for r in phase7_results if r.get("citation_any_hit", False))
    acc7 = hits7 / n7 if n7 else 0
    ci7 = wilson_score_interval(hits7, n7)
    
    adv7 = [r for r in phase7_results if r.get("is_adversarial", False)]
    nat7 = [r for r in phase7_results if not r.get("is_adversarial", False)]
    
    adv_caught = sum(1 for r in adv7 if not r.get("verifier_is_verified", True))
    ctrl_rejected = sum(1 for r in nat7 if not r.get("verifier_is_verified", True))
    
    adv_ci = wilson_score_interval(adv_caught, len(adv7)) if adv7 else (0, 0)
    ctrl_ci = wilson_score_interval(ctrl_rejected, len(nat7)) if nat7 else (0, 0)
    
    crpc_recs = [r for r in phase7_results if r.get("category", "").startswith("B_")]
    crpc_hits = sum(1 for r in crpc_recs if r.get("citation_any_hit", False))
    crpc_acc = crpc_hits / len(crpc_recs) if crpc_recs else 0
    crpc_ci = wilson_score_interval(crpc_hits, len(crpc_recs)) if crpc_recs else (0, 0)
    
    new_exp = {
        "stage": "Phase 7 (Large-Scale RAG)",
        "n": n7,
        "accuracy": f"{acc7*100:.1f}% ({hits7}/{n7})",
        "accuracy_ci": f"[{ci7[0]}%–{ci7[1]}%]",
        "stress_catch_rate": f"{adv_caught/len(adv7)*100:.1f}% ({adv_caught}/{len(adv7)}) [{adv_ci[0]}%–{adv_ci[1]}%]" if adv7 else "N/A",
        "control_fpr": f"{ctrl_rejected/len(nat7)*100:.1f}% ({ctrl_rejected}/{len(nat7)}) [{ctrl_ci[0]}%–{ctrl_ci[1]}%]" if nat7 else "N/A",
        "procedural": f"{crpc_acc*100:.1f}% ({crpc_hits}/{len(crpc_recs)}) [{crpc_ci[0]}%–{crpc_ci[1]}%]" if crpc_recs else "N/A",
        "benchmark": f"Phase 7 large-scale benchmark (N={n7})",
        "note": "NEW Phase 7 evaluation — does NOT replace original"
    }
    
    return [orig, new_exp]


# ─── Statistical tests ─────────────────────────────────────────────────────────

def compute_statistics(results: List[Dict]) -> Dict:
    """Compute statistical analysis including bootstrap CIs."""
    import random
    random.seed(42)
    
    n = len(results)
    hits = [1 if r.get("citation_any_hit", False) else 0 for r in results]
    p_hat = sum(hits) / n if n else 0
    
    # Bootstrap 95% CI
    boot_means = []
    for _ in range(1000):
        sample = random.choices(hits, k=n)
        boot_means.append(sum(sample) / n)
    boot_means.sort()
    boot_ci = (round(boot_means[25] * 100, 2), round(boot_means[974] * 100, 2))
    
    # Wilson CI
    wilson_ci = wilson_score_interval(sum(hits), n)
    
    # Note: No McNemar's test since this is not a paired comparison
    # (Phase 7 and original N=60 use different question sets)
    
    return {
        "n": n,
        "p_hat": round(p_hat * 100, 2),
        "wilson_ci_95": wilson_ci,
        "bootstrap_ci_95": boot_ci,
        "note_mcnemar": "McNemar's test NOT applicable — Phase 7 and original N=60 are not paired (different question sets). No valid paired comparison exists.",
        "note_statistical": "Wilson score interval appropriate for binomial proportions. Bootstrap CI computed with B=1000 resamples, seed=42.",
    }


# ─── Error analysis ────────────────────────────────────────────────────────────

def analyze_errors(results: List[Dict]) -> Dict:
    error_types = defaultdict(list)
    
    for r in results:
        if not r.get("citation_any_hit", False):
            adv = r.get("is_adversarial", False)
            cat = r.get("category", "unknown")
            verdict = r.get("verifier_verdict", "N/A")
            mtype = r.get("mapping_type", "")
            
            if not r.get("retrieved_sections"):
                error_types["retrieval_failure"].append(r)
            elif not r.get("cited_sections"):
                error_types["generation_failure_no_citation"].append(r)
            elif adv:
                error_types["adversarial_missed"].append(r)
            elif mtype == "repealed":
                error_types["repealed_law_failure"].append(r)
            elif mtype in ("split", "merged"):
                error_types["split_merged_failure"].append(r)
            else:
                error_types["citation_mismatch"].append(r)
    
    summary = {}
    for etype, recs in error_types.items():
        examples = [{"qid": r["question_id"], "question": r["question"][:80],
                     "expected": r.get("expected_sections", []),
                     "cited": r.get("cited_sections", []),
                     "category": r.get("category", "")} for r in recs[:3]]
        summary[etype] = {"count": len(recs), "examples": examples}
    
    return summary


# ─── Write all outputs ─────────────────────────────────────────────────────────

def write_all_tables(results: List[Dict], gen_metrics: Dict, ver_metrics: Dict,
                     ret_metrics: Dict, stats: Dict):
    
    # 1. Generation metrics CSV
    gen_rows = []
    for group_name in ["overall", "natural", "adversarial"]:
        m = gen_metrics.get(group_name, {})
        if not m:
            continue
        cit = m.get("citation_any_hit", {})
        gen_rows.append({
            "group": group_name,
            "n": m.get("n", 0),
            "citation_hit_rate": cit.get("accuracy", "N/A"),
            "ci_low": cit.get("ci_low", ""),
            "ci_high": cit.get("ci_high", ""),
        })
    # By category
    for cat, m in gen_metrics.get("by_category", {}).items():
        cit = m.get("citation_any_hit", {})
        gen_rows.append({
            "group": f"cat_{cat}", "n": m.get("n", 0),
            "citation_hit_rate": cit.get("accuracy", "N/A"),
            "ci_low": cit.get("ci_low", ""), "ci_high": cit.get("ci_high", ""),
        })
    
    gen_csv = os.path.join(TABLES_DIR, "generation_metrics.csv")
    with open(gen_csv, "w", newline="", encoding="utf-8") as f:
        if gen_rows:
            w = csv.DictWriter(f, fieldnames=list(gen_rows[0].keys()))
            w.writeheader()
            w.writerows(gen_rows)
    print(f"  Generation metrics: {gen_csv}")
    
    # 2. Verifier metrics CSV
    ov = ver_metrics.get("overall", {})
    ver_csv = os.path.join(TABLES_DIR, "verifier_metrics.csv")
    ver_rows = [{
        "metric": "TP", "value": ov.get("tp", "N/A"),
        "metric2": "TN", "value2": ov.get("tn", "N/A"),
    }, {
        "metric": "FP", "value": ov.get("fp", "N/A"),
        "metric2": "FN", "value2": ov.get("fn", "N/A"),
    }, {
        "metric": "Precision", "value": ov.get("precision", "N/A"),
        "metric2": "Recall", "value2": ov.get("recall", "N/A"),
    }, {
        "metric": "F1", "value": ov.get("f1", "N/A"),
        "metric2": "Specificity", "value2": ov.get("specificity", "N/A"),
    }, {
        "metric": "FPR", "value": ov.get("fpr", "N/A"),
        "metric2": "N_with_verifier", "value2": ov.get("n_with_verifier", "N/A"),
    }]
    with open(ver_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["metric", "value", "metric2", "value2"])
        w.writeheader()
        w.writerows(ver_rows)
    print(f"  Verifier metrics: {ver_csv}")
    
    # 3. Category-wise table
    cat_rows = build_category_table(results)
    cat_csv = os.path.join(TABLES_DIR, "category_results.csv")
    if cat_rows:
        with open(cat_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(cat_rows[0].keys()))
            w.writeheader()
            w.writerows(cat_rows)
    print(f"  Category results: {cat_csv}")
    
    # 4. Original vs large-scale comparison
    comp_rows = build_comparison_table(results)
    comp_csv = os.path.join(TABLES_DIR, "original_vs_large_scale.csv")
    if comp_rows:
        with open(comp_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(comp_rows[0].keys()))
            w.writeheader()
            w.writerows(comp_rows)
    print(f"  Comparison table: {comp_csv}")
    
    # 5. Statistical analysis
    stats_path = os.path.join(TABLES_DIR, "statistical_significance.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print(f"  Statistical analysis: {stats_path}")
    
    # 6. Error analysis
    errors = analyze_errors(results)
    err_path = os.path.join(TABLES_DIR, "error_analysis.json")
    with open(err_path, "w", encoding="utf-8") as f:
        json.dump(errors, f, indent=2)
    print(f"  Error analysis: {err_path}")
    
    # 7. Dataset provenance table
    from collections import Counter
    prov_counts = Counter(r.get("source_dataset", "unknown") for r in results)
    prov_csv = os.path.join(TABLES_DIR, "provenance_table.csv")
    with open(prov_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["source_dataset", "count", "pct"])
        w.writeheader()
        for src, cnt in sorted(prov_counts.items(), key=lambda x: -x[1]):
            w.writerow({"source_dataset": src, "count": cnt,
                        "pct": f"{cnt/len(results)*100:.1f}%"})
    print(f"  Provenance table: {prov_csv}")
    
    # Also save dataset_composition and benchmark_composition
    cat_counts = Counter(r.get("category", "unknown") for r in results)
    bm_csv = os.path.join(TABLES_DIR, "benchmark_composition.csv")
    with open(bm_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["category", "count", "pct"])
        w.writeheader()
        for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
            w.writerow({"category": cat, "count": cnt,
                        "pct": f"{cnt/len(results)*100:.1f}%"})
    print(f"  Benchmark composition: {bm_csv}")

    return {
        "generation_metrics_csv": gen_csv,
        "verifier_metrics_csv": ver_csv,
        "category_results_csv": cat_csv,
        "comparison_csv": comp_csv,
        "stats_json": stats_path,
        "error_analysis_json": err_path,
    }


def main():
    raw_dir = os.path.join(PHASE7_ROOT, "results", "raw")
    results_path = find_latest_results(raw_dir)
    
    print(f"Loading results: {results_path}")
    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    results = data.get("results", [])
    print(f"Loaded {len(results)} records.")
    
    # Also load retrieval metrics if available
    ret_json = os.path.join(TABLES_DIR, "retrieval_metrics.json")
    ret_metrics = {}
    if os.path.exists(ret_json):
        with open(ret_json) as f:
            ret_metrics = json.load(f)
    
    print("\n[1] Computing generation metrics...")
    gen_metrics = compute_generation_metrics(results)
    
    print("[2] Computing verifier metrics...")
    ver_metrics = compute_verifier_metrics(results)
    
    print("[3] Computing statistical analysis...")
    stats = compute_statistics(results)
    
    print("[4] Writing all tables...")
    write_all_tables(results, gen_metrics, ver_metrics, ret_metrics, stats)
    
    # Print summary
    ov = gen_metrics.get("overall", {})
    cit = ov.get("citation_any_hit", {})
    ver_ov = ver_metrics.get("overall", {})
    
    print("\n" + "=" * 60)
    print("PHASE 7 GENERATION METRICS SUMMARY")
    print("=" * 60)
    print(f"  Total questions:      {ov.get('n', 0)}")
    print(f"  Citation hit rate:    {cit.get('formatted', 'N/A')}")
    print(f"  Verifier F1:          {ver_ov.get('f1', 'N/A')}%")
    print(f"  Stress catch rate:    {ver_ov.get('stress_catch_rate', {}).get('formatted', 'N/A')}")
    print(f"  Control FPR:          {ver_ov.get('control_fpr', {}).get('formatted', 'N/A')}")
    print(f"  Wilson 95% CI:        [{stats['wilson_ci_95'][0]}%–{stats['wilson_ci_95'][1]}%]")
    print(f"  Bootstrap 95% CI:     [{stats['bootstrap_ci_95'][0]}%–{stats['bootstrap_ci_95'][1]}%]")
    print("=" * 60)
    
    return gen_metrics, ver_metrics, stats


if __name__ == "__main__":
    main()

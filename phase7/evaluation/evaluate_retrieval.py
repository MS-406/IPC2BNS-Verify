"""
evaluate_retrieval.py — Retrieval Metric Calculator for Phase 7

Computes:
- Recall@1, Recall@3, Recall@5, Recall@10
- Precision@5
- MRR (Mean Reciprocal Rank)
- Hit Rate, Mean Rank
- Category-specific metrics

Usage:
    python phase7/evaluation/evaluate_retrieval.py --results-file <path_to_raw_results.json>
"""

import os
import sys
import json
import csv
import argparse
from collections import defaultdict
from typing import List, Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PHASE7_ROOT = os.path.join(PROJECT_ROOT, "phase7")
TABLES_DIR = os.path.join(PHASE7_ROOT, "results", "tables")
os.makedirs(TABLES_DIR, exist_ok=True)


def compute_retrieval_metrics(results: List[Dict]) -> Dict[str, Any]:
    """Compute aggregate and per-category retrieval metrics."""
    
    def agg_metrics(subset):
        n = len(subset)
        if n == 0:
            return {"n": 0, "recall_at_1": "N/A", "recall_at_3": "N/A",
                    "recall_at_5": "N/A", "recall_at_10": "N/A",
                    "precision_at_5": "N/A", "mrr": "N/A", "hit_rate": "N/A"}
        
        r1 = sum(r.get("recall_at_1", 0) for r in subset) / n
        r3 = sum(r.get("recall_at_3", 0) for r in subset) / n
        r5 = sum(r.get("recall_at_5", 0) for r in subset) / n
        r10 = sum(r.get("recall_at_10", 0) for r in subset) / n
        p5 = sum(r.get("precision_at_5", 0) for r in subset) / n
        mrr = sum(r.get("mrr", 0) for r in subset) / n
        ranks = [r.get("best_retrieval_rank", -1) for r in subset if r.get("best_retrieval_rank", -1) > 0]
        hit_rate = len(ranks) / n
        mean_rank = sum(ranks) / len(ranks) if ranks else float("inf")
        
        return {
            "n": n,
            "recall_at_1": round(r1, 4),
            "recall_at_3": round(r3, 4),
            "recall_at_5": round(r5, 4),
            "recall_at_10": round(r10, 4),
            "precision_at_5": round(p5, 4),
            "mrr": round(mrr, 4),
            "hit_rate": round(hit_rate, 4),
            "mean_rank": round(mean_rank, 2) if mean_rank != float("inf") else "N/A"
        }

    # Overall
    overall = agg_metrics(results)
    
    # Category breakdown
    cat_groups = defaultdict(list)
    for r in results:
        cat_groups[r.get("category", "unknown")].append(r)
    
    category_metrics = {}
    for cat, recs in sorted(cat_groups.items()):
        category_metrics[cat] = agg_metrics(recs)
    
    # Natural vs Adversarial
    natural = [r for r in results if not r.get("is_adversarial", False)]
    adversarial = [r for r in results if r.get("is_adversarial", False)]
    
    # IPC->BNS vs CrPC->BNSS
    ipc_bns = [r for r in results if r.get("category", "").startswith("A_")]
    crpc_bnss = [r for r in results if r.get("category", "").startswith("B_")]
    repealed = [r for r in results if r.get("category", "").startswith("D_")]
    split_merged = [r for r in results if r.get("category", "").startswith(("E_", "F_"))]
    
    return {
        "overall": overall,
        "natural": agg_metrics(natural),
        "adversarial": agg_metrics(adversarial),
        "ipc_bns_direct": agg_metrics(ipc_bns),
        "crpc_bnss_direct": agg_metrics(crpc_bnss),
        "repealed": agg_metrics(repealed),
        "split_merged": agg_metrics(split_merged),
        "by_category": category_metrics
    }


def write_retrieval_metrics_csv(metrics: Dict, output_path: str):
    """Write retrieval metrics to CSV."""
    rows = []
    
    for group_name, m in metrics.items():
        if group_name == "by_category":
            for cat, cm in m.items():
                rows.append({"group": f"cat_{cat}", **cm})
        else:
            rows.append({"group": group_name, **m})
    
    if not rows:
        return
    
    fieldnames = ["group", "n", "recall_at_1", "recall_at_3", "recall_at_5",
                  "recall_at_10", "precision_at_5", "mrr", "hit_rate", "mean_rank"]
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"  Retrieval metrics CSV: {output_path}")


def write_retrieval_metrics_md(metrics: Dict, output_path: str):
    """Write retrieval metrics to Markdown table."""
    lines = ["# Phase 7 Retrieval Metrics\n"]
    
    header = "| Group | N | R@1 | R@3 | R@5 | R@10 | P@5 | MRR | Hit Rate |"
    sep    = "|---|--:|----:|----:|----:|-----:|----:|----:|---------:|"
    lines += [header, sep]
    
    def fmt(m, group):
        n = m.get("n", 0)
        def p(v): return f"{v*100:.1f}%" if isinstance(v, float) else str(v)
        return (f"| **{group}** | {n} | {p(m.get('recall_at_1',0))} | {p(m.get('recall_at_3',0))} | "
                f"{p(m.get('recall_at_5',0))} | {p(m.get('recall_at_10',0))} | "
                f"{p(m.get('precision_at_5',0))} | {p(m.get('mrr',0))} | {p(m.get('hit_rate',0))} |")
    
    top_groups = [("Overall", "overall"), ("Natural", "natural"), ("Adversarial", "adversarial"),
                  ("IPC→BNS", "ipc_bns_direct"), ("CrPC→BNSS", "crpc_bnss_direct"),
                  ("Repealed", "repealed"), ("Split/Merged", "split_merged")]
    
    for label, key in top_groups:
        if key in metrics:
            lines.append(fmt(metrics[key], label))
    
    lines.append("\n## By Category\n")
    lines.append(header)
    lines.append(sep)
    for cat, cm in sorted(metrics.get("by_category", {}).items()):
        lines.append(fmt(cm, cat))
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Retrieval metrics MD: {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-file", required=False,
                        help="Path to raw results JSON from run_large_benchmark.py")
    args = parser.parse_args()

    # Find latest results if not specified
    raw_dir = os.path.join(PHASE7_ROOT, "results", "raw")
    if args.results_file:
        results_path = args.results_file
    else:
        files = sorted([f for f in os.listdir(raw_dir) if f.endswith(".json")])
        if not files:
            print("[ERROR] No raw results found. Run run_large_benchmark.py first.")
            sys.exit(1)
        results_path = os.path.join(raw_dir, files[-1])
    
    print(f"Loading results from: {results_path}")
    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    results = data.get("results", [])
    print(f"Loaded {len(results)} result records.")
    
    metrics = compute_retrieval_metrics(results)
    
    # Print summary
    ov = metrics["overall"]
    print(f"\nOverall Retrieval Metrics (N={ov['n']}):")
    print(f"  Recall@1:  {ov['recall_at_1']*100:.1f}%")
    print(f"  Recall@3:  {ov['recall_at_3']*100:.1f}%")
    print(f"  Recall@5:  {ov['recall_at_5']*100:.1f}%")
    print(f"  Recall@10: {ov['recall_at_10']*100:.1f}%")
    print(f"  P@5:       {ov['precision_at_5']*100:.1f}%")
    print(f"  MRR:       {ov['mrr']:.4f}")
    print(f"  Hit Rate:  {ov['hit_rate']*100:.1f}%")
    
    # Save
    csv_path = os.path.join(TABLES_DIR, "retrieval_metrics.csv")
    md_path = os.path.join(TABLES_DIR, "retrieval_metrics.md")
    write_retrieval_metrics_csv(metrics, csv_path)
    write_retrieval_metrics_md(metrics, md_path)
    
    # Save JSON for downstream use
    json_path = os.path.join(TABLES_DIR, "retrieval_metrics.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"  Retrieval metrics JSON: {json_path}")
    
    return metrics


if __name__ == "__main__":
    main()

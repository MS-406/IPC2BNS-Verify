"""
retrieval_eval.py — Retrieval Precision/Recall & MRR Evaluator

Evaluates statutory retrieval performance against the benchmark question sets.
Metrics computed:
- Recall@1, Recall@3, Recall@5
- Precision@1, Precision@3, Precision@5
- Mean Reciprocal Rank (MRR)
- Average Retrieval Latency (ms)

Saves results to results/stage2/retrieval_metrics.json.
"""

import os
import sys
import csv
import json
import time
import logging
from typing import Dict, List, Any

code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from src.retrieval.search import get_retriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("retrieval_eval")


def evaluate_retrieval(benchmark_csv: str, output_metrics_json: str, top_k: int = 5) -> Dict[str, Any]:
    """
    Runs benchmark queries through the retrieval engine and evaluates accuracy against ground-truth sections.
    """
    retriever = get_retriever()

    if not os.path.exists(benchmark_csv):
        raise FileNotFoundError(f"Benchmark file not found: {benchmark_csv}")

    queries = []
    with open(benchmark_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries.append(row)

    log.info(f"Evaluating retrieval on {len(queries)} queries from {benchmark_csv}...")

    recall_at_1 = 0
    recall_at_3 = 0
    recall_at_5 = 0
    precision_at_1 = 0
    precision_at_3 = 0
    precision_at_5 = 0
    reciprocal_ranks = []
    latencies = []

    per_query_results = []

    for q in queries:
        qid = q.get("question_id", "")
        qtext = q.get("query_text", "")
        target_act = q.get("target_act", "")
        gt_sections_raw = q.get("ground_truth_sections", "")
        gt_sections = [s.strip().upper() for s in gt_sections_raw.replace("/", ",").split(",") if s.strip()]

        start_t = time.time()
        hits = retriever.retrieve(qtext, top_k=top_k, act_filter=target_act if target_act in ("IPC", "BNS") else None)
        latency = (time.time() - start_t) * 1000.0
        latencies.append(latency)

        retrieved_secs = [h["section_number"].upper() for h in hits]

        # Check hits
        hit_ranks = []
        for rank, r_sec in enumerate(retrieved_secs, start=1):
            for gt_sec in gt_sections:
                # Match exact or base section (e.g. 106 vs 106(2))
                if r_sec == gt_sec or r_sec in gt_sec or gt_sec in r_sec:
                    hit_ranks.append(rank)
                    break

        first_hit_rank = hit_ranks[0] if hit_ranks else None
        rr = 1.0 / first_hit_rank if first_hit_rank else 0.0
        reciprocal_ranks.append(rr)

        r1 = 1 if (first_hit_rank and first_hit_rank <= 1) else 0
        r3 = 1 if (first_hit_rank and first_hit_rank <= 3) else 0
        r5 = 1 if (first_hit_rank and first_hit_rank <= 5) else 0

        recall_at_1 += r1
        recall_at_3 += r3
        recall_at_5 += r5

        # Precision@k
        relevant_in_top1 = sum(1 for s in retrieved_secs[:1] if any(s in gt or gt in s for gt in gt_sections))
        relevant_in_top3 = sum(1 for s in retrieved_secs[:3] if any(s in gt or gt in s for gt in gt_sections))
        relevant_in_top5 = sum(1 for s in retrieved_secs[:5] if any(s in gt or gt in s for gt in gt_sections))

        precision_at_1 += (relevant_in_top1 / 1.0)
        precision_at_3 += (relevant_in_top3 / 3.0)
        precision_at_5 += (relevant_in_top5 / 5.0)

        per_query_results.append({
            "question_id": qid,
            "query_text": qtext,
            "ground_truth_sections": gt_sections,
            "retrieved_sections": retrieved_secs,
            "first_hit_rank": first_hit_rank,
            "mrr": rr,
            "latency_ms": round(latency, 2)
        })

    total = max(1, len(queries))
    metrics = {
        "benchmark_file": os.path.basename(benchmark_csv),
        "total_queries": total,
        "metrics": {
            "recall_at_1": round(recall_at_1 / total, 4),
            "recall_at_3": round(recall_at_3 / total, 4),
            "recall_at_5": round(recall_at_5 / total, 4),
            "precision_at_1": round(precision_at_1 / total, 4),
            "precision_at_3": round(precision_at_3 / total, 4),
            "precision_at_5": round(precision_at_5 / total, 4),
            "mean_reciprocal_rank": round(sum(reciprocal_ranks) / total, 4),
            "avg_latency_ms": round(sum(latencies) / total, 2)
        },
        "query_evaluations": per_query_results
    }

    os.makedirs(os.path.dirname(output_metrics_json), exist_ok=True)
    with open(output_metrics_json, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    log.info("=" * 60)
    log.info("RETRIEVAL EVALUATION RESULTS")
    log.info("=" * 60)
    for m, val in metrics["metrics"].items():
        log.info(f"  {m:22s}: {val}")
    log.info(f"Saved detailed metrics report to: {output_metrics_json}")

    return metrics


if __name__ == "__main__":
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", "D:/college 4th year/research paper/NLP_rs")
    benchmark = os.path.join(root, "data/03_benchmark/benchmark_dev.csv")
    metrics_out = os.path.join(root, "results/stage2/retrieval_metrics.json")
    evaluate_retrieval(benchmark, metrics_out)

"""
run_ablations.py — Driver for Stage 1 and Stage 2 Experimental Runs

Executes:
- Stage 1: Baseline Closed-Book LLM (No retrieval) -> results/stage1/stage1_baseline_results.json
- Stage 2: RAG-Augmented Model (+Retrieval) -> results/stage2/stage2_rag_results.json
"""

import os
import sys
import csv
import json
import logging
from typing import List, Dict, Any

code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from src.generation.generator import get_generator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("run_ablations")


def load_benchmark(benchmark_csv: str) -> List[Dict[str, Any]]:
    if not os.path.exists(benchmark_csv):
        raise FileNotFoundError(f"Benchmark CSV not found: {benchmark_csv}")
    queries = []
    with open(benchmark_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            queries.append(r)
    return queries


def run_stage1_ablation(benchmark_csv: str, output_path: str):
    """Run Stage 1: Closed-book baseline."""
    generator = get_generator()
    queries = load_benchmark(benchmark_csv)
    log.info(f"Running Stage 1 (Baseline LLM, zero retrieval) on {len(queries)} queries...")

    results = []
    for q in queries:
        qid = q.get("question_id", "")
        qtext = q.get("query_text", "")
        res = generator.generate_stage1(query=qtext, question_id=qid)
        item = res.to_dict()
        item["ground_truth_sections"] = q.get("ground_truth_sections", "")
        item["ground_truth_answer"] = q.get("ground_truth_answer", "")
        item["is_ambiguous"] = q.get("is_ambiguous", "False").lower() == "true"
        results.append(item)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "stage": 1,
            "stage_name": "Stage 1: Baseline LLM (No Retrieval)",
            "benchmark": os.path.basename(benchmark_csv),
            "total_queries": len(results),
            "results": results
        }, f, indent=2)
    log.info(f"Stage 1 results saved to: {output_path}")


def run_stage2_ablation(benchmark_csv: str, output_path: str):
    """Run Stage 2: RAG (+retrieval, no verifier)."""
    generator = get_generator()
    queries = load_benchmark(benchmark_csv)
    log.info(f"Running Stage 2 (+RAG Retrieval Context) on {len(queries)} queries...")

    results = []
    for q in queries:
        qid = q.get("question_id", "")
        qtext = q.get("query_text", "")
        target_act = q.get("target_act", "")
        res = generator.generate_stage2(
            query=qtext,
            question_id=qid,
            top_k=3,
            act_filter=target_act if target_act in ("IPC", "BNS") else None
        )
        item = res.to_dict()
        item["ground_truth_sections"] = q.get("ground_truth_sections", "")
        item["ground_truth_answer"] = q.get("ground_truth_answer", "")
        item["is_ambiguous"] = q.get("is_ambiguous", "False").lower() == "true"
        results.append(item)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "stage": 2,
            "stage_name": "Stage 2: +RAG (Retrieval Context, No Verifier)",
            "benchmark": os.path.basename(benchmark_csv),
            "total_queries": len(results),
            "results": results
        }, f, indent=2)
    log.info(f"Stage 2 results saved to: {output_path}")


def main():
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", "D:/college 4th year/research paper/NLP_rs")
    benchmark_dev = os.path.join(root, "data/03_benchmark/benchmark_dev.csv")
    stage1_out = os.path.join(root, "results/stage1/stage1_baseline_results.json")
    stage2_out = os.path.join(root, "results/stage2/stage2_rag_results.json")

    run_stage1_ablation(benchmark_dev, stage1_out)
    run_stage2_ablation(benchmark_dev, stage2_out)


if __name__ == "__main__":
    main()

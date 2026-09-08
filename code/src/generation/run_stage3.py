"""
run_stage3.py — Stage 3 Benchmark Runner & Verifier Stress-Test Evaluator

Executes Stage 3: Two-Layer Hard-Constraint Verifier across Dev & Adversarial Stress Suites.
"""

import os
import sys
import csv
import json
import logging
from typing import List, Dict, Any

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from src.generation.generator import get_generator
from src.verifier.verifier_pipeline import get_master_verifier
from src.generation.prompt_template import LegalPromptBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("run_stage3")


def load_benchmark(benchmark_csv: str) -> List[Dict[str, Any]]:
    if not os.path.exists(benchmark_csv):
        raise FileNotFoundError(f"Benchmark CSV not found: {benchmark_csv}")
    queries = []
    with open(benchmark_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            queries.append(r)
    return queries


def run_stage3_benchmark(benchmark_csv: str, output_path: str) -> Dict[str, Any]:
    """Runs Stage 3 (+Two-Layer Hard Verifier) on dev benchmark queries."""
    generator = get_generator()
    verifier = get_master_verifier()
    queries = load_benchmark(benchmark_csv)
    log.info(f"Running Stage 3 (+Two-Layer Hard Verifier) on {len(queries)} dev queries...")

    results = []
    verified_count = 0
    for q in queries:
        qid = q.get("question_id", "")
        qtext = q.get("query_text", "")
        target_act = q.get("target_act", "")
        gen_res = generator.generate_stage2(
            query=qtext,
            question_id=qid,
            top_k=5,
            retrieval_mode="hybrid_expanded_rerank",
            act_filter=target_act if target_act in ("IPC", "BNS") else None
        )
        v_res = verifier.verify_generation(
            generated_text=gen_res.generated_text,
            citations=gen_res.citations,
            retrieved_chunks=gen_res.retrieved_chunks,
            query=qtext
        )
        if v_res.is_verified:
            verified_count += 1

        results.append({
            "question_id": qid,
            "query_text": qtext,
            "ground_truth_sections": q.get("ground_truth_sections", ""),
            "ground_truth_answer": q.get("ground_truth_answer", ""),
            "is_ambiguous": q.get("is_ambiguous", "False").lower() == "true",
            "stage2_raw_generation": gen_res.generated_text,
            "cited_sections": [c["section"] for c in gen_res.citations],
            "is_verified": v_res.is_verified,
            "verdict": v_res.verdict,
            "confidence_score": v_res.confidence_score,
            "confidence_grade": v_res.confidence_grade,
            "ambiguity_score": v_res.ambiguity_score,
            "final_verified_output": v_res.verified_output_text,
            "warnings": v_res.warnings,
            "layer2_grounding_score": v_res.layer2_result.overlap_score if hasattr(v_res, "layer2_result") and v_res.layer2_result else 1.0
        })

    summary = {
        "stage": 3,
        "stage_name": "Stage 3: +RAG + Two-Layer Hard-Constraint Verifier",
        "benchmark": os.path.basename(benchmark_csv),
        "total_queries": len(results),
        "verified_rate": round(verified_count / len(results), 3) if results else 0,
        "results": results
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    log.info(f"Stage 3 benchmark results saved to: {output_path}")

    return summary


def evaluate_verifier_stress_test(stress_csv: str) -> Dict[str, float]:
    """Evaluates the two-layer verifier against the injected errors stress test suite."""
    verifier = get_master_verifier()
    stress_queries = load_benchmark(stress_csv) if os.path.exists(stress_csv) else []
    adv_caught = 0
    adv_total = 0
    ctrl_passed = 0
    ctrl_total = 0
    stress_results = []

    for sq in stress_queries:
        stype = sq.get("error_type", "")
        text = sq.get("generated_text", "")
        q_text = sq.get("query_text", "")
        is_adv = sq.get("is_adversarial_error", "True").lower() == "true"
        cits = LegalPromptBuilder.extract_citations(text)

        v_res = verifier.verify_generation(
            generated_text=text,
            citations=cits,
            retrieved_chunks=[],
            query=q_text
        )
        if is_adv:
            adv_total += 1
            if not v_res.is_verified:
                adv_caught += 1
        else:
            ctrl_total += 1
            if v_res.is_verified:
                ctrl_passed += 1

        stress_results.append({
            "error_id": sq.get("error_id", ""),
            "error_type": stype,
            "is_adversarial": is_adv,
            "is_verified": v_res.is_verified,
            "verdict": v_res.verdict
        })

    catch_rate = round(adv_caught / adv_total, 3) if adv_total else 1.0
    fpr = round((ctrl_total - ctrl_passed) / ctrl_total, 3) if ctrl_total else 0.0

    return {
        "total_stress_cases": len(stress_queries),
        "adversarial_total": adv_total,
        "adversarial_caught": adv_caught,
        "hallucination_catch_rate": catch_rate,
        "control_total": ctrl_total,
        "control_passed": ctrl_passed,
        "false_positive_rate": fpr,
        "stress_results": stress_results
    }


def main():
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", os.getcwd())
    dev_csv = os.path.join(root, "data/03_benchmark/benchmark_dev.csv")
    stress_csv = os.path.join(root, "data/03_benchmark/injected_errors.csv")
    out_json = os.path.join(root, "results/stage3/stage3_verifier_results.json")

    run_stage3_benchmark(dev_csv, out_json)
    metrics = evaluate_verifier_stress_test(stress_csv)
    print("\n" + "="*60)
    print("STAGE 3 VERIFIER STRESS-TEST METRICS")
    print("="*60)
    print(f"Hallucination Catch Rate : {metrics['hallucination_catch_rate']*100:.1f}%")
    print(f"False Positive Rate (FPR): {metrics['false_positive_rate']*100:.1f}%")


if __name__ == "__main__":
    main()

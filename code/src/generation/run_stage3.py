"""
run_stage3.py — Stage 3 (+Hard-Constraint Verifier) Execution and Stress-Test Harness

Executes:
1. Stage 3 (+Verifier) over benchmark dev queries -> results/stage3/stage3_verifier_results.json
2. Verifier stress-testing over injected_errors.csv -> computes Hallucination Catch Rate and False Positive Rate
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
from src.generation.prompt_template import LegalPromptBuilder
from src.retrieval.search import retrieve_statutes
from src.verifier.verifier_pipeline import get_master_verifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("run_stage3")


def run_stage3_benchmark(benchmark_csv: str, output_path: str) -> Dict[str, Any]:
    """Runs Stage 3 (+Verifier) on benchmark queries."""
    generator = get_generator()
    verifier = get_master_verifier()

    queries = []
    with open(benchmark_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            queries.append(r)

    log.info(f"Running Stage 3 (+Verifier) on {len(queries)} benchmark queries...")
    results = []
    verified_count = 0

    for q in queries:
        qid = q.get("question_id", "")
        qtext = q.get("query_text", "")
        target_act = q.get("target_act", "")

        # 1. Retrieve
        chunks = retrieve_statutes(query=qtext, top_k=3, act_filter=target_act if target_act in ("IPC", "BNS") else None)

        # 2. Generate
        gen_res = generator.generate_stage2(query=qtext, question_id=qid, top_k=3, act_filter=target_act if target_act in ("IPC", "BNS") else None)

        # 3. Verify
        v_res = verifier.verify_generation(
            generated_text=gen_res.generated_text,
            citations=gen_res.citations,
            retrieved_chunks=chunks,
            query=qtext
        )

        if v_res.is_verified:
            verified_count += 1

        res_item = {
            "question_id": qid,
            "query_text": qtext,
            "ground_truth_sections": q.get("ground_truth_sections", ""),
            "ground_truth_answer": q.get("ground_truth_answer", ""),
            "is_ambiguous": q.get("is_ambiguous", "False").lower() == "true",
            "stage2_raw_generation": gen_res.generated_text,
            "cited_sections": [c["section"] for c in gen_res.citations],
            "is_verified": v_res.is_verified,
            "verdict": v_res.verdict,
            "final_verified_output": v_res.verified_output_text,
            "warnings": v_res.warnings,
            "layer2_grounding_score": v_res.layer2_result.overlap_score
        }
        results.append(res_item)

    data = {
        "stage": 3,
        "stage_name": "Stage 3: +RAG + Hard-Constraint Verifier",
        "benchmark": os.path.basename(benchmark_csv),
        "total_queries": len(results),
        "verified_rate": round(verified_count / max(1, len(results)), 4),
        "results": results
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    log.info(f"Stage 3 results saved to: {output_path}")
    return data


def evaluate_verifier_stress_test(injected_errors_csv: str) -> Dict[str, Any]:
    """Evaluates Verifier Hallucination Catch Rate and False Positive Rate."""
    verifier = get_master_verifier()

    if not os.path.exists(injected_errors_csv):
        raise FileNotFoundError(f"Injected errors file not found: {injected_errors_csv}")

    cases = []
    with open(injected_errors_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            cases.append(r)

    log.info(f"Running Verifier Stress-Test on {len(cases)} injected error cases...")

    adversarial_total = 0
    adversarial_caught = 0
    control_total = 0
    false_positives = 0

    evaluations = []

    for c in cases:
        eid = c.get("error_id", "")
        etype = c.get("error_type", "")
        qtext = c.get("query_text", "")
        gen_text = c.get("generated_text", "")
        is_adversarial = c.get("is_adversarial_error", "True").lower() == "true"
        expected_verdict = c.get("expected_verdict", "")

        citations = LegalPromptBuilder.extract_citations(gen_text)
        chunks = retrieve_statutes(query=qtext, top_k=2)

        v_res = verifier.verify_generation(
            generated_text=gen_text,
            citations=citations,
            retrieved_chunks=chunks,
            query=qtext
        )

        passed = v_res.is_verified

        if is_adversarial:
            adversarial_total += 1
            if not passed:
                adversarial_caught += 1
        else:
            control_total += 1
            if not passed:
                false_positives += 1

        evaluations.append({
            "error_id": eid,
            "error_type": etype,
            "query_text": qtext,
            "is_adversarial": is_adversarial,
            "expected_verdict": expected_verdict,
            "actual_verdict": v_res.verdict,
            "is_verified": v_res.is_verified,
            "catch_success": (not passed) if is_adversarial else passed
        })

    catch_rate = round(adversarial_caught / max(1, adversarial_total), 4)
    fp_rate = round(false_positives / max(1, control_total), 4)

    metrics = {
        "adversarial_cases_tested": adversarial_total,
        "adversarial_hallucinations_caught": adversarial_caught,
        "hallucination_catch_rate": catch_rate,
        "valid_controls_tested": control_total,
        "false_positive_rejections": false_positives,
        "false_positive_rate": fp_rate,
        "evaluations": evaluations
    }

    log.info("=" * 60)
    log.info("VERIFIER STRESS-TEST EVALUATION RESULTS")
    log.info("=" * 60)
    log.info(f"  Hallucination Catch Rate : {catch_rate * 100:.1f}% ({adversarial_caught}/{adversarial_total})")
    log.info(f"  False Positive Rate (FPR): {fp_rate * 100:.1f}% ({false_positives}/{control_total})")

    return metrics


def main():
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", "D:/college 4th year/research paper/NLP_rs")
    benchmark_dev = os.path.join(root, "data/03_benchmark/benchmark_dev.csv")
    injected_errors = os.path.join(root, "data/03_benchmark/injected_errors.csv")
    stage3_out = os.path.join(root, "results/stage3/stage3_verifier_results.json")

    run_stage3_benchmark(benchmark_dev, stage3_out)
    evaluate_verifier_stress_test(injected_errors)


if __name__ == "__main__":
    main()

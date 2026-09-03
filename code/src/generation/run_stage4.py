"""
run_stage4.py — Stage 4 (+Verifier + Refresh Adaptivity) Experimental Runner

Evaluates pipeline adaptivity by testing queries on newly amended statutes
comparing Pre-Refresh (Stage 3) vs. Post-Refresh (Stage 4) retrieval accuracy.
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
from src.retrieval.search import StatutoryRetriever
from src.verifier.verifier_pipeline import get_master_verifier
from src.refresh.updater import create_post_refresh_index

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("run_stage4")

AMENDMENT_EVAL_QUERIES = [
    {
        "question_id": "AMD_Q_001",
        "query_text": "What section in the amended BNS penalizes AI deepfake impersonation and voice cloning fraud?",
        "target_act": "BNS",
        "ground_truth_sections": "318A",
        "ground_truth_answer": "Under Section 318A of the amended BNS 2023, synthetic deepfakes and AI impersonation for fraud carry up to seven years rigorous imprisonment and fine up to ten lakh rupees."
    },
    {
        "question_id": "AMD_Q_002",
        "query_text": "Under what provision is hazardous industrial water pollution penalized in amended BNS?",
        "target_act": "BNS",
        "ground_truth_sections": "278A",
        "ground_truth_answer": "Under Section 278A of BNS, discharging hazardous industrial pollutants into public water reservoirs carries up to five years imprisonment and minimum twenty lakh rupees fine."
    },
    {
        "question_id": "AMD_Q_003",
        "query_text": "Can a hit-and-run driver receive a sentence reduction under Section 106 if they render immediate medical aid?",
        "target_act": "BNS",
        "ground_truth_sections": "106(3)",
        "ground_truth_answer": "Yes, under the amended Section 106(3) proviso, if a driver immediately renders medical assistance and transports the injured person to a hospital before reporting, the court may reduce the sentence by up to half."
    }
]


def run_stage4_ablation(base_index_dir: str, post_refresh_index_dir: str, output_path: str):
    """
    Compares Pre-Refresh vs. Post-Refresh pipeline performance.
    """
    pre_retriever = StatutoryRetriever(base_index_dir)
    post_retriever = StatutoryRetriever(post_refresh_index_dir)
    generator = get_generator()
    verifier = get_master_verifier()

    log.info("Running Stage 4 (+Verifier+Refresh) Adaptivity Evaluation...")
    comparison_results = []

    for q in AMENDMENT_EVAL_QUERIES:
        qid = q["question_id"]
        qtext = q["query_text"]
        gt_sec = q["ground_truth_sections"]

        # Pre-refresh run
        pre_chunks = pre_retriever.retrieve(qtext, top_k=2)
        pre_secs = [c["section_number"] for c in pre_chunks]
        pre_hit = any(gt_sec in s or s in gt_sec for s in pre_secs)

        # Post-refresh run
        post_chunks = post_retriever.retrieve(qtext, top_k=2)
        post_secs = [c["section_number"] for c in post_chunks]
        post_hit = any(gt_sec in s or s in gt_sec for s in post_secs)

        # Generate & Verify with post-refresh context
        gen_res = generator.generate_stage2(qtext, question_id=qid, top_k=2)
        v_res = verifier.verify_generation(
            generated_text=gen_res.generated_text,
            citations=gen_res.citations,
            retrieved_chunks=post_chunks,
            query=qtext
        )

        comparison_results.append({
            "question_id": qid,
            "query_text": qtext,
            "ground_truth_sections": gt_sec,
            "pre_refresh_retrieved_sections": pre_secs,
            "pre_refresh_hit": pre_hit,
            "post_refresh_retrieved_sections": post_secs,
            "post_refresh_hit": post_hit,
            "post_refresh_generated_text": gen_res.generated_text,
            "is_verified": v_res.is_verified,
            "verdict": v_res.verdict
        })

    total = len(comparison_results)
    pre_acc = sum(1 for r in comparison_results if r["pre_refresh_hit"]) / total
    post_acc = sum(1 for r in comparison_results if r["post_refresh_hit"]) / total

    data = {
        "stage": 4,
        "stage_name": "Stage 4: +Verifier + Incremental Refresh (Adaptivity)",
        "total_amendment_queries": total,
        "pre_refresh_retrieval_accuracy": round(pre_acc, 4),
        "post_refresh_retrieval_accuracy": round(post_acc, 4),
        "accuracy_delta": round(post_acc - pre_acc, 4),
        "results": comparison_results
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    log.info("=" * 60)
    log.info("STAGE 4 REFRESH ADAPTIVITY RESULTS")
    log.info("=" * 60)
    log.info(f"  Pre-Refresh Retrieval Accuracy  : {pre_acc * 100:.1f}%")
    log.info(f"  Post-Refresh Retrieval Accuracy : {post_acc * 100:.1f}% (Adaptivity Delta: +{(post_acc - pre_acc)*100:.1f}%)")
    log.info(f"Saved results to: {output_path}")

    return data


def main():
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", "D:/college 4th year/research paper/NLP_rs")
    base_idx = os.path.join(root, "data/05_embeddings_index/stage2_index")
    post_idx = os.path.join(root, "data/05_embeddings_index/stage4_post_refresh_index")
    out_file = os.path.join(root, "results/stage4/stage4_refresh_results.json")

    run_stage4_ablation(base_idx, post_idx, out_file)


if __name__ == "__main__":
    main()

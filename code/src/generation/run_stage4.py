"""
run_stage4.py — Stage 4 Incremental Refresh Adaptivity Runner

Evaluates pre-refresh vs post-refresh retrieval accuracy on newly gazetted legislative amendments.
"""

import os
import sys
import json
import logging
from typing import List, Dict, Any

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from src.retrieval.search import get_retriever, StatutoryRetriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("run_stage4")


def run_stage4_ablation(base_idx_dir: str, post_idx_dir: str, output_path: str) -> Dict[str, Any]:
    """Runs Stage 4 (+Incremental Refresh Adaptivity Evaluation)."""
    log.info("Running Stage 4 (+Incremental Refresh Adaptivity Evaluation)...")

    amendment_queries = [
        {
            "question_id": "AMD_Q_001",
            "query_text": "What section in the amended BNS penalizes AI deepfake impersonation and voice cloning fraud?",
            "ground_truth_sections": "318A",
            "act": "BNS"
        },
        {
            "question_id": "AMD_Q_002",
            "query_text": "Under what provision is hazardous industrial water pollution penalized in amended BNS?",
            "ground_truth_sections": "278A",
            "act": "BNS"
        },
        {
            "question_id": "AMD_Q_003",
            "query_text": "Can a hit-and-run driver receive a sentence reduction under Section 106 if they render immediate medical aid?",
            "ground_truth_sections": "106(3)",
            "act": "BNS"
        }
    ]

    pre_retriever = StatutoryRetriever(base_idx_dir)
    post_retriever = StatutoryRetriever(post_idx_dir)

    results = []
    pre_hits = 0
    post_hits = 0

    for q in amendment_queries:
        qtext = q["query_text"]
        target = q["ground_truth_sections"]

        pre_res = pre_retriever.retrieve(query=qtext, top_k=3, act_filter=q["act"])
        post_res = post_retriever.retrieve(query=qtext, top_k=3, act_filter=q["act"])

        pre_secs = [r["section_number"] for r in pre_res]
        post_secs = [r["section_number"] for r in post_res]

        pre_hit = target in pre_secs or any(target in s for s in pre_secs)
        post_hit = target in post_secs or any(target in s for s in post_secs)

        if pre_hit:
            pre_hits += 1
        if post_hit:
            post_hits += 1

        results.append({
            "question_id": q["question_id"],
            "query_text": qtext,
            "ground_truth_section": target,
            "pre_refresh_retrieved_sections": pre_secs,
            "pre_refresh_hit": pre_hit,
            "post_refresh_retrieved_sections": post_secs,
            "post_refresh_hit": post_hit
        })

    total = len(amendment_queries)
    pre_acc = round(pre_hits / total, 3) if total else 0
    post_acc = round(post_hits / total, 3) if total else 0
    delta = round(post_acc - pre_acc, 3)

    summary = {
        "stage": 4,
        "stage_name": "Stage 4: +Verifier + Incremental Refresh (Full System)",
        "total_amendment_queries": total,
        "pre_refresh_retrieval_accuracy": pre_acc,
        "post_refresh_retrieval_accuracy": post_acc,
        "accuracy_delta": delta,
        "results": results
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    log.info(f"Stage 4 results saved to: {output_path}")

    return summary


def main():
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", os.getcwd())
    base_idx = os.path.join(root, "data/05_embeddings_index/stage2_index")
    post_idx = os.path.join(root, "data/05_embeddings_index/stage4_post_refresh_index")
    out_json = os.path.join(root, "results/stage4/stage4_refresh_results.json")

    res = run_stage4_ablation(base_idx, post_idx, out_json)
    print("\n" + "="*60)
    print("STAGE 4 REFRESH ADAPTIVITY SUMMARY")
    print("="*60)
    print(f"Pre-Refresh Retrieval Accuracy  : {res['pre_refresh_retrieval_accuracy']*100:.1f}%")
    print(f"Post-Refresh Retrieval Accuracy : {res['post_refresh_retrieval_accuracy']*100:.1f}%")
    print(f"Adaptivity Accuracy Delta       : +{res['accuracy_delta']*100:.1f}%")


if __name__ == "__main__":
    main()

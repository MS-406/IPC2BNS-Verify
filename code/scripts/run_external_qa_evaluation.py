"""
run_external_qa_evaluation.py — Independent External Dataset Evaluation Runner

Evaluates IPC2BNS-Verify on independently sourced real legal QA datasets
(e.g., IndicLegalQA, Indian Legal Benchmark, Supreme Court QAs).

Workflow:
1. Ingests external questions with ground truth IPC/BNS sections.
2. Runs Stage 1 (Closed-Book Baseline LLM).
3. Runs Stage 2 (+BM25 Statutory RAG).
4. Runs Stage 3 (+Two-Layer Hard Verifier).
5. Computes Wilson 95% Confidence Intervals, Accuracy, and Verifier Rejection/Pass Rates.
6. Outputs clean summary table in CSV and JSON formats: results/external_dataset_results.csv.
"""

import os
import sys
import csv
import json
import math
import logging
from typing import List, Dict, Any, Tuple

# Ensure project root and code dir are on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(CODE_DIR, ".."))
for p in [ROOT_DIR, CODE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.generation.generator import get_generator
from src.retrieval.search import get_retriever
from src.verifier.verifier_pipeline import get_master_verifier
from src.mapping.lookup import ConcordanceLookup



logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("external_qa_eval")


def wilson_score_interval(successes: int, total: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Computes Wilson Score 95% confidence interval for binomial proportions."""
    if total == 0:
        return (0.0, 0.0)
    z = 1.95996
    p_hat = successes / total
    denominator = 1 + (z**2) / total
    centre = (p_hat + (z**2) / (2 * total)) / denominator
    margin = (z * math.sqrt((p_hat * (1 - p_hat) + (z**2) / (4 * total)) / total)) / denominator
    lower = max(0.0, (centre - margin) * 100)
    upper = min(100.0, (centre + margin) * 100)
    return round(lower, 1), round(upper, 1)


def load_external_dataset(file_path: str) -> List[Dict[str, Any]]:
    """
    Loads external legal questions from CSV, JSON, or JSONL.
    Expected fields per item:
      - 'question_id' or 'id'
      - 'question' or 'query_text' or 'query'
      - 'ground_truth_ipc' or 'ground_truth_sections' or 'ipc_section'
      - Optional: 'ground_truth_bns' or 'bns_section'
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"External dataset file not found: {file_path}")

    items = []
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".csv":
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                items.append(r)
    elif ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = data if isinstance(data, list) else data.get("questions", data.get("data", []))
    elif ext == ".jsonl":
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
    else:
        raise ValueError(f"Unsupported file extension: {ext}")

    log.info(f"Loaded {len(items)} raw external questions from {file_path}")
    return items


def run_evaluation(items: List[Dict[str, Any]], dataset_name: str = "IndicLegalQA", retrieval_mode: str = "hybrid_expanded", top_k: int = 5) -> Dict[str, Any]:
    """Runs the 3-stage evaluation on the external dataset with selectable retrieval mode and top_k context window."""
    generator = get_generator()
    verifier = get_master_verifier()
    concordance = ConcordanceLookup()

    s1_hits, s2_hits, s3_passed_hits = 0, 0, 0
    s3_total_passed, s3_total_rejected, s3_total_vetoed = 0, 0, 0
    detailed_records = []

    total_items = len(items)

    # Dynamic non-repealed (active valid) item count
    valid_items = [
        it for it in items 
        if str(it.get("ground_truth_bns", it.get("bns_section", ""))).strip() not in ("NaN", "-", "", "None")
    ]
    valid_total = len(valid_items)

    for idx, item in enumerate(items, 1):
        qid = str(item.get("question_id", item.get("id", f"EXT_{idx:03d}")))
        query_text = item.get("question", item.get("query_text", item.get("query", ""))).strip()
        gt_ipc = str(item.get("ground_truth_ipc", item.get("ipc_section", item.get("ground_truth_sections", "")))).strip()
        gt_bns = str(item.get("ground_truth_bns", item.get("bns_section", ""))).strip()

        # If BNS ground truth is not provided, look it up in concordance table
        if not gt_bns and gt_ipc:
            mapping = concordance.map_ipc_to_bns(gt_ipc)
            if mapping and mapping.target_section:
                gt_bns = mapping.target_section

        # Expected target for BNS evaluation: gt_bns, fallback to gt_ipc
        target_citation = gt_bns if gt_bns else gt_ipc

        # 1. Stage 1: Closed-Book LLM
        s1_res = generator.generate_stage1(query=query_text, question_id=qid)
        s1_cited_sections = [c["section"].upper().replace(" ", "") for c in s1_res.citations]
        s1_hit = any(target_citation.upper().replace(" ", "") in c for c in s1_cited_sections) if s1_cited_sections else False
        if s1_hit:
            s1_hits += 1

        # 2. Stage 2: RAG Context with configured retrieval_mode and top_k
        s2_res = generator.generate_stage2(query=query_text, question_id=qid, top_k=top_k, retrieval_mode=retrieval_mode)
        s2_cited_sections = [c["section"].upper().replace(" ", "") for c in s2_res.citations]
        s2_hit = any(target_citation.upper().replace(" ", "") in c for c in s2_cited_sections) if s2_cited_sections else False
        if s2_hit:
            s2_hits += 1

        # 3. Stage 3: +Two-Layer Hard Verifier
        retrieved_chunks = [c.to_dict() if hasattr(c, "to_dict") else c for c in s2_res.retrieved_chunks]
        citations = s2_res.citations

        v_res = verifier.verify_generation(
            generated_text=s2_res.generated_text,
            citations=citations,
            retrieved_chunks=retrieved_chunks,
            query=query_text
        )

        v_verdict = v_res.verdict
        if v_res.is_verified:
            s3_total_passed += 1
            if s2_hit:
                s3_passed_hits += 1
        elif "VETOED" in v_verdict or v_res.confidence_grade == "VETOED_REPEALED":
            s3_total_vetoed += 1
        else:
            s3_total_rejected += 1

        detailed_records.append({
            "question_id": qid,
            "query_text": query_text,
            "ground_truth_ipc": gt_ipc,
            "ground_truth_bns": gt_bns,
            "s1_cited": s1_cited_sections,
            "s1_hit": s1_hit,
            "s2_cited": s2_cited_sections,
            "s2_hit": s2_hit,
            "verifier_verdict": v_verdict,
            "is_verified": v_res.is_verified,
            "verifier_grade": v_res.confidence_grade,
            "verifier_confidence": v_res.confidence_score,
            "verifier_ambiguity": v_res.ambiguity_score,
            "warnings": v_res.warnings
        })

    # Accuracies computed over full sample
    s1_acc = round(s1_hits / total_items * 100, 1) if total_items > 0 else 0.0
    s2_acc = round(s2_hits / total_items * 100, 1) if total_items > 0 else 0.0
    s1_ci = wilson_score_interval(s1_hits, total_items)
    s2_ci = wilson_score_interval(s2_hits, total_items)

    # Accuracies computed over active valid non-repealed provisions
    s1_acc_valid = round(s1_hits / valid_total * 100, 1) if valid_total > 0 else 0.0
    s2_acc_valid = round(s2_hits / valid_total * 100, 1) if valid_total > 0 else 0.0
    s1_ci_valid = wilson_score_interval(s1_hits, valid_total)
    s2_ci_valid = wilson_score_interval(s2_hits, valid_total)

    summary = {
        "dataset_name": dataset_name,
        "sample_size": total_items,
        "active_valid_size": valid_total,
        "repealed_count": total_items - valid_total,
        "top_k": top_k,
        "stage1_accuracy_full": f"{s1_acc}% ({s1_hits}/{total_items})",
        "stage1_ci_full": f"[{s1_ci[0]}% - {s1_ci[1]}%]",
        "stage2_accuracy_full": f"{s2_acc}% ({s2_hits}/{total_items})",
        "stage2_ci_full": f"[{s2_ci[0]}% - {s2_ci[1]}%]",
        "stage1_accuracy_valid": f"{s1_acc_valid}% ({s1_hits}/{valid_total})",
        "stage1_ci_valid": f"[{s1_ci_valid[0]}% - {s1_ci_valid[1]}%]",
        "stage2_accuracy_valid": f"{s2_acc_valid}% ({s2_hits}/{valid_total})",
        "stage2_ci_valid": f"[{s2_ci_valid[0]}% - {s2_ci_valid[1]}%]",
        "verifier_passed": s3_total_passed,
        "verifier_rejected": s3_total_rejected,
        "verifier_vetoed": s3_total_vetoed,
        "detailed_results": detailed_records
    }

    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate external dataset on IPC2BNS-Verify")
    parser.add_argument("--file", type=str, default="data/03_benchmark/external_indic_legal_qa.csv", help="Path to input external QA file (CSV/JSON/JSONL)")
    parser.add_argument("--name", type=str, default="IndicLegalQA (Real Legal Questions)", help="Dataset display name")
    parser.add_argument("--mode", type=str, default="hybrid_expanded", choices=["bm25", "bm25_expanded", "dense", "hybrid_rrf", "hybrid_expanded", "hybrid_reranked"], help="Retrieval mode to evaluate")
    parser.add_argument("--top_k", type=int, default=5, help="Context window top-k retrieved chunks")
    parser.add_argument("--out", type=str, default="results/external_dataset_results.json", help="Path to output JSON results")
    args = parser.parse_args()

    items = load_external_dataset(args.file)
    summary = run_evaluation(items, dataset_name=args.name, retrieval_mode=args.mode, top_k=args.top_k)
    summary["retrieval_mode"] = args.mode

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Also export summary table as CSV
    csv_out = os.path.splitext(args.out)[0] + ".csv"
    with open(csv_out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Dataset Name", "Retrieval Mode", "Top K", "Total (N)", "Active Valid (N)", "Stage 1 Acc (Full)", "Stage 1 95% CI", "Stage 2 +RAG Acc (Full)", "Stage 2 95% CI", "Stage 2 Acc (Valid)", "Stage 2 95% CI (Valid)", "Verifier Passed", "Verifier Rejections/Vetoes"])
        writer.writerow([
            summary["dataset_name"],
            summary["retrieval_mode"],
            summary["top_k"],
            summary["sample_size"],
            summary["active_valid_size"],
            summary["stage1_accuracy_full"],
            summary["stage1_ci_full"],
            summary["stage2_accuracy_full"],
            summary["stage2_ci_full"],
            summary["stage2_accuracy_valid"],
            summary["stage2_ci_valid"],
            f"{summary['verifier_passed']}/{summary['sample_size']}",
            f"{summary['verifier_rejected'] + summary['verifier_vetoed']}/{summary['sample_size']}"
        ])

    print("\n" + "="*80)
    print(f"EVALUATION COMPLETE ON {summary['dataset_name']} (Mode: {args.mode}, Top-K: {args.top_k}, Total N={summary['sample_size']}, Valid N={summary['active_valid_size']})")
    print("="*80)
    print(f"Stage 1 (Baseline Closed-Book LLM): {summary['stage1_accuracy_full']} (Valid: {summary['stage1_accuracy_valid']})  95% CI: {summary['stage1_ci_full']}")
    print(f"Stage 2 (+{args.mode.upper()} Statutory RAG): {summary['stage2_accuracy_full']} (Valid: {summary['stage2_accuracy_valid']})  95% CI: {summary['stage2_ci_full']}")
    print(f"Stage 3 (Verifier Gating):          Passed: {summary['verifier_passed']} | Rejected: {summary['verifier_rejected']} | Vetoed: {summary['verifier_vetoed']}")
    print("="*80)
    print(f"Results saved to:\n  - {args.out}\n  - {csv_out}\n")


if __name__ == "__main__":
    main()

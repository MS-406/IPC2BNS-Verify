"""
compare_retrievers.py — Systematic Retriever Ablation & Comparative Benchmark

Evaluates 5 distinct retrieval strategies on identical benchmark sets:
1. BM25 (Sparse Baseline)
2. BM25 + Concordance Query Expansion
3. Dense Semantic (Cosine Similarity)
4. Hybrid RRF (BM25 + Dense fused via Reciprocal Rank Fusion)
5. Hybrid RRF + Concordance Query Expansion

Computes exact:
- Recall@1, Recall@3, Recall@5
- Mean Reciprocal Rank (MRR)
- End-to-End Citation Hit Rate
"""

import os
import sys
import csv
import json
import logging
from typing import List, Dict, Any, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(CODE_DIR, ".."))
for p in [ROOT_DIR, CODE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.retrieval.hybrid_retriever import get_hybrid_retriever
from src.mapping.lookup import ConcordanceLookup
from src.generation.generator import get_generator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("compare_retrievers")


def load_dataset(benchmark_path: str) -> List[Dict[str, Any]]:
    items = []
    with open(benchmark_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            items.append(r)
    return items


def evaluate_retrieval_mode(items: List[Dict[str, Any]], mode: str, top_k: int = 5) -> Dict[str, Any]:
    retriever = get_hybrid_retriever()
    concordance = ConcordanceLookup()
    generator = get_generator()

    r1_hits = 0
    r3_hits = 0
    r5_hits = 0
    rr_sum = 0.0
    citation_hits_top3 = 0
    citation_hits_top5 = 0
    total = len(items)

    valid_items = [
        it for it in items 
        if str(it.get("ground_truth_bns", it.get("bns_section", ""))).strip() not in ("NaN", "-", "", "None")
    ]
    valid_total = len(valid_items)

    for idx, item in enumerate(items, 1):
        qid = str(item.get("question_id", item.get("id", f"Q_{idx:03d}")))
        query = item.get("question", item.get("query_text", item.get("query", ""))).strip()
        gt_ipc = str(item.get("ground_truth_ipc", item.get("ipc_section", item.get("ground_truth_sections", "")))).strip()
        gt_bns = str(item.get("ground_truth_bns", item.get("bns_section", ""))).strip()

        if not gt_bns and gt_ipc:
            mapping = concordance.map_ipc_to_bns(gt_ipc)
            if mapping and mapping.target_section:
                gt_bns = mapping.target_section

        target_sec = gt_bns if gt_bns and gt_bns != "NaN" else gt_ipc
        target_clean = target_sec.upper().replace("SECTION", "").replace("§", "").replace(" ", "").strip()

        # Retrieve top-5 chunks using specified mode
        hits = retriever.retrieve(query=query, top_k=5, mode=mode)
        hit_sections = [h.get("section_number", "").upper().replace(" ", "") for h in hits]

        # Calculate Rank & Reciprocal Rank
        rank = None
        for r_idx, sec in enumerate(hit_sections):
            if target_clean and (target_clean == sec or target_clean in sec or sec in target_clean):
                rank = r_idx + 1
                break

        if rank == 1:
            r1_hits += 1
        if rank is not None and rank <= 3:
            r3_hits += 1
        if rank is not None and rank <= 5:
            r5_hits += 1

        if rank is not None:
            rr_sum += 1.0 / rank

        # End-to-end generation citation hit with Top-3
        gen_res_3 = generator.generate_stage2(query=query, question_id=qid, top_k=3, retrieval_mode=mode)
        cited_3 = [c["section"].upper().replace(" ", "") for c in gen_res_3.citations]
        if target_clean and any(target_clean in c for c in cited_3):
            citation_hits_top3 += 1

        # End-to-end generation citation hit with Top-5
        gen_res_5 = generator.generate_stage2(query=query, question_id=qid, top_k=5, retrieval_mode=mode)
        cited_5 = [c["section"].upper().replace(" ", "") for c in gen_res_5.citations]
        if target_clean and any(target_clean in c for c in cited_5):
            citation_hits_top5 += 1

    return {
        "mode": mode,
        "sample_size": total,
        "valid_size": valid_total,
        "recall_at_1": f"{round(r1_hits / total * 100, 1)}% ({r1_hits}/{total})",
        "recall_at_3": f"{round(r3_hits / total * 100, 1)}% ({r3_hits}/{total})",
        "recall_at_5": f"{round(r5_hits / total * 100, 1)}% ({r5_hits}/{total})",
        "recall_at_5_valid": f"{round(r5_hits / valid_total * 100, 1)}% ({r5_hits}/{valid_total})" if valid_total > 0 else "0.0%",
        "mrr": round(rr_sum / total, 3),
        "citation_hit_top3": f"{round(citation_hits_top3 / total * 100, 1)}% ({citation_hits_top3}/{total})",
        "citation_hit_top5": f"{round(citation_hits_top5 / total * 100, 1)}% ({citation_hits_top5}/{total})",
        "citation_hit_top5_valid": f"{round(citation_hits_top5 / valid_total * 100, 1)}% ({citation_hits_top5}/{valid_total})" if valid_total > 0 else "0.0%"
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Systematic Retriever Ablation Study")
    parser.add_argument("--benchmark", type=str, default="data/03_benchmark/external_indic_legal_qa.csv")
    parser.add_argument("--out", type=str, default="results/retriever_ablation_comparison.json")
    args = parser.parse_args()

    items = load_dataset(args.benchmark)
    modes = [
        ("bm25", "BM25 (Sparse Baseline)"),
        ("bm25_expanded", "BM25 + Concordance Query Expansion"),
        ("dense", "Dense Semantic (Cosine Similarity)"),
        ("hybrid_rrf", "Hybrid RRF (BM25 + Dense)"),
        ("hybrid_expanded", "Hybrid RRF + Concordance Expansion"),
        ("hybrid_reranked", "Hybrid RRF + Cross-Encoder Re-Ranking")
    ]

    print(f"\nEvaluating {len(modes)} retrieval modes on {os.path.basename(args.benchmark)} (N={len(items)})...\n")
    results = []

    for mode_key, mode_name in modes:
        log.info(f"Running mode: {mode_name} ...")
        res = evaluate_retrieval_mode(items, mode=mode_key)
        res["display_name"] = mode_name
        results.append(res)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Save to CSV
    csv_out = os.path.splitext(args.out)[0] + ".csv"
    with open(csv_out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Retrieval Strategy", "Recall@1", "Recall@3", "Recall@5 (Full)", "Recall@5 (Valid)", "MRR", "Citation Hit Top-3", "Citation Hit Top-5 (Full)", "Citation Hit Top-5 (Valid)"])
        for r in results:
            writer.writerow([r["display_name"], r["recall_at_1"], r["recall_at_3"], r["recall_at_5"], r["recall_at_5_valid"], r["mrr"], r["citation_hit_top3"], r["citation_hit_top5"], r["citation_hit_top5_valid"]])

    print("\n" + "="*115)
    print(f"SYSTEMATIC RETRIEVER ABLATION RESULTS (Benchmark: {os.path.basename(args.benchmark)}, N={len(items)})")
    print("="*115)
    print(f"{'Retrieval Strategy':<42} | {'Recall@1':<9} | {'Recall@5':<9} | {'MRR':<6} | {'Hit Top-3':<11} | {'Hit Top-5 (Valid)':<18}")
    print("-" * 115)
    for r in results:
        print(f"{r['display_name']:<42} | {r['recall_at_1']:<9} | {r['recall_at_5']:<9} | {r['mrr']:<6} | {r['citation_hit_top3']:<11} | {r['citation_hit_top5_valid']:<18}")
    print("="*115)
    print(f"\nSaved results to:\n  - {args.out}\n  - {csv_out}\n")


if __name__ == "__main__":
    main()

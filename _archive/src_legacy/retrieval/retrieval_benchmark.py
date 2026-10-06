"""
retrieval_benchmark.py — Phase 5b: Retrieval Benchmark Runner

Runs all retriever variants against the test split and computes
Recall@K, Precision@K, MRR, MAP, and hit_rate metrics.
"""

import logging
import time
from typing import Dict, Any, List, Optional

log = logging.getLogger("retrieval_benchmark")


def compute_retrieval_metrics(
    results: List[Dict[str, Any]],
    k_values: Optional[List[int]] = None,
) -> Dict[str, float]:
    """
    Compute retrieval metrics from a list of query evaluation results.

    Each result dict has:
    - true_section: str (ground truth BNS section)
    - retrieved_sections: List[str] (ranked list of retrieved section IDs)
    """
    if k_values is None:
        k_values = [1, 3, 5, 10]

    n = len(results)
    if n == 0:
        return {}

    metrics: Dict[str, float] = {}

    # Recall@K and Precision@K
    for k in k_values:
        recall_sum = 0.0
        precision_sum = 0.0
        for r in results:
            true = r["true_section"]
            retrieved = r["retrieved_sections"][:k]
            hit = 1.0 if true in retrieved else 0.0
            recall_sum += hit
            precision_sum += hit / k
        metrics[f"recall_at_{k}"] = round(recall_sum / n, 4)
        metrics[f"precision_at_{k}"] = round(precision_sum / n, 4)

    # MRR (Mean Reciprocal Rank)
    rr_sum = 0.0
    for r in results:
        true = r["true_section"]
        retrieved = r["retrieved_sections"]
        for rank, sec in enumerate(retrieved, 1):
            if sec == true:
                rr_sum += 1.0 / rank
                break
    metrics["mrr"] = round(rr_sum / n, 4)

    # MAP (Mean Average Precision) — single relevant document per query
    ap_sum = 0.0
    for r in results:
        true = r["true_section"]
        retrieved = r["retrieved_sections"]
        for rank, sec in enumerate(retrieved, 1):
            if sec == true:
                ap_sum += 1.0 / rank
                break
    metrics["map"] = round(ap_sum / n, 4)

    # Hit Rate (did we find it anywhere in top-max_k?)
    max_k = max(k_values)
    hit_sum = sum(
        1.0 for r in results
        if r["true_section"] in r["retrieved_sections"][:max_k]
    )
    metrics["hit_rate"] = round(hit_sum / n, 4)

    return metrics


class RetrievalBenchmark:
    """
    Runs retrieval benchmarks across multiple retriever variants.
    """

    def __init__(
        self,
        corpus: Optional[List[Dict[str, Any]]] = None,
        k_values: Optional[List[int]] = None,
    ):
        self.corpus = corpus or []
        self.k_values = k_values or [1, 3, 5, 10]

    def load_corpus_from_jsonl(self, path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load BNS corpus from JSONL."""
        from src.utils.config import BNS_SECTIONS_PATH
        from src.data.dataset_validator import load_jsonl

        path = path or str(BNS_SECTIONS_PATH)
        self.corpus = load_jsonl(path)
        log.info(f"Loaded corpus with {len(self.corpus)} BNS sections")
        return self.corpus

    def run_retriever(
        self,
        retriever_name: str,
        test_data: List[Dict[str, Any]],
        top_k: int = 10,
        **retriever_kwargs,
    ) -> Dict[str, Any]:
        """
        Run a single retriever against the test data.

        Returns dict with retriever name, metrics, and per-query results.
        """
        from src.retrieval.base_retriever import get_retriever

        retriever = get_retriever(retriever_name, **retriever_kwargs)
        retriever.index(self.corpus)

        query_results = []
        total_latency = 0.0

        for sample in test_data:
            query = sample["input_text"]
            true_bns = sample["bns_section"]

            start = time.time()
            hits = retriever.retrieve(query, top_k=top_k)
            latency = (time.time() - start) * 1000.0
            total_latency += latency

            retrieved_sections = [h.section_id for h in hits]
            query_results.append({
                "sample_id": sample.get("sample_id", ""),
                "query": query,
                "true_section": true_bns,
                "retrieved_sections": retrieved_sections,
                "scores": [h.score for h in hits],
                "latency_ms": latency,
            })

        metrics = compute_retrieval_metrics(query_results, self.k_values)
        metrics["mean_latency_ms"] = round(total_latency / max(1, len(test_data)), 2)

        return {
            "retriever": retriever_name,
            "metrics": metrics,
            "per_query_results": query_results,
            "num_queries": len(test_data),
            "corpus_size": len(self.corpus),
        }

    def run_all_retrievers(
        self,
        test_data: List[Dict[str, Any]],
        retriever_names: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Run all retriever variants and collect comparative results.
        """
        if retriever_names is None:
            retriever_names = ["bm25", "tfidf"]
            # Dense and hybrid require encoder — only include if available
            try:
                import torch
                retriever_names.extend(["dense", "hybrid"])
            except ImportError:
                log.warning("PyTorch not available; skipping dense/hybrid retrievers")

        all_results = {}
        for name in retriever_names:
            log.info(f"Running retrieval benchmark: {name}")
            try:
                result = self.run_retriever(name, test_data, top_k=top_k)
                all_results[name] = result
                m = result["metrics"]
                log.info(
                    f"  {name}: R@1={m.get('recall_at_1', 0):.3f}, "
                    f"R@5={m.get('recall_at_5', 0):.3f}, "
                    f"MRR={m.get('mrr', 0):.3f}"
                )
            except Exception as e:
                log.error(f"  {name} failed: {e}")
                all_results[name] = {"retriever": name, "error": str(e)}

        return all_results

    def comparison_table(
        self, all_results: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Format results as a comparison table (list of dicts)."""
        rows = []
        for name, result in all_results.items():
            if "error" in result:
                rows.append({"retriever": name, "error": result["error"]})
                continue
            row = {"retriever": name}
            row.update(result.get("metrics", {}))
            rows.append(row)
        return rows

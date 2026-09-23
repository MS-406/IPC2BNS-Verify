"""
rag_evaluator.py — RAG-Specific Evaluation

Evaluates RAG pipeline outputs on four dimensions:
1. Context Relevance — Was the correct BNS section retrieved?
2. Faithfulness — Does the prediction match evidence in the context?
3. Hallucination Detection — Was the prediction unsupported by context?
4. Answer Correctness — Final accuracy against ground truth.
"""

import logging
from typing import Dict, Any, List, Optional

log = logging.getLogger("rag_evaluator")


class RAGEvaluator:
    """Evaluates RAG pipeline results against ground truth."""

    def evaluate_single(
        self,
        rag_result,
        ground_truth_bns: str,
    ) -> Dict[str, Any]:
        """
        Evaluate a single RAG result.

        Returns:
            Dict with boolean flags and scores for each dimension.
        """
        predicted_bns = rag_result.predicted_bns
        retrieved_sections = [
            c.get("section_id", "") for c in rag_result.retrieved_contexts
        ]
        reranked_sections = [
            c.get("section_id", "") for c in rag_result.reranked_contexts
        ]

        # 1. Context Relevance
        correct_in_retrieved = ground_truth_bns in retrieved_sections
        correct_in_reranked = ground_truth_bns in reranked_sections
        retrieval_rank = None
        for i, sid in enumerate(retrieved_sections, 1):
            if sid == ground_truth_bns:
                retrieval_rank = i
                break

        # 2. Answer Correctness
        correct = (predicted_bns == ground_truth_bns)

        # 3. Faithfulness — prediction is supported by retrieved context
        prediction_in_context = predicted_bns in retrieved_sections

        # 4. Hallucination — predicted a section that was NOT in context
        hallucinated = (predicted_bns != "" and not prediction_in_context)

        # No evidence — correct answer was not retrieved at all
        no_evidence = not correct_in_retrieved

        return {
            "correct": correct,
            "correct_in_retrieved": correct_in_retrieved,
            "correct_in_reranked": correct_in_reranked,
            "retrieval_rank": retrieval_rank,
            "prediction_in_context": prediction_in_context,
            "hallucinated": hallucinated,
            "no_evidence_retrieved": no_evidence,
            "predicted_bns": predicted_bns,
            "ground_truth_bns": ground_truth_bns,
            "confidence": rag_result.confidence,
            "latency_ms": rag_result.latency_ms,
        }

    def evaluate_batch(
        self,
        rag_results: List,
        ground_truths: List[str],
    ) -> Dict[str, Any]:
        """
        Evaluate a batch of RAG results.

        Returns aggregate metrics and per-sample details.
        """
        n = len(rag_results)
        assert len(ground_truths) == n, "Results and ground truths must match"

        per_sample = []
        correct_count = 0
        correct_in_retrieved = 0
        correct_in_reranked = 0
        faithful_count = 0
        hallucinated_count = 0
        no_evidence_count = 0
        retrieval_ranks = []

        for result, gt in zip(rag_results, ground_truths):
            eval_r = self.evaluate_single(result, gt)
            per_sample.append(eval_r)

            if eval_r["correct"]:
                correct_count += 1
            if eval_r["correct_in_retrieved"]:
                correct_in_retrieved += 1
            if eval_r["correct_in_reranked"]:
                correct_in_reranked += 1
            if eval_r["prediction_in_context"]:
                faithful_count += 1
            if eval_r["hallucinated"]:
                hallucinated_count += 1
            if eval_r["no_evidence_retrieved"]:
                no_evidence_count += 1
            if eval_r["retrieval_rank"] is not None:
                retrieval_ranks.append(eval_r["retrieval_rank"])

        aggregate = {
            "total_samples": n,
            "accuracy": round(correct_count / max(1, n), 4),
            "context_relevance": round(correct_in_retrieved / max(1, n), 4),
            "reranker_relevance": round(correct_in_reranked / max(1, n), 4),
            "faithfulness": round(faithful_count / max(1, n), 4),
            "hallucination_rate": round(hallucinated_count / max(1, n), 4),
            "no_evidence_rate": round(no_evidence_count / max(1, n), 4),
            "mean_retrieval_rank": (
                round(sum(retrieval_ranks) / len(retrieval_ranks), 2)
                if retrieval_ranks else None
            ),
        }

        return {
            "aggregate": aggregate,
            "per_sample": per_sample,
        }

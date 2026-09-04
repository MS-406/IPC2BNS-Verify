"""
run_large_benchmark.py — Phase 7 Evaluation Driver

Runs the FROZEN existing IPC2BNS-Verify pipeline on the Phase 7 large-scale benchmark.
This script imports existing functions without modifying them.

All output saved exclusively to phase7/results/raw/
Does NOT overwrite any existing results under results/

Usage:
    cd d:\\college 4th year\\research paper\\NLP_rs
    python phase7/evaluation/run_large_benchmark.py [--split test|dev|all] [--max-questions N]
"""

import os
import sys
import json
import time
import argparse
import datetime
import traceback
from typing import List, Dict, Any, Optional

# ─── Path setup ───────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PHASE7_ROOT = os.path.join(PROJECT_ROOT, "phase7")
CODE_DIR = os.path.join(PROJECT_ROOT, "code")

for p in [CODE_DIR, PROJECT_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

BENCHMARK_DIR = os.path.join(PHASE7_ROOT, "benchmark")
RESULTS_RAW_DIR = os.path.join(PHASE7_ROOT, "results", "raw")
os.makedirs(RESULTS_RAW_DIR, exist_ok=True)

# ─── Import FROZEN existing pipeline (read-only) ──────────────────────────────
print("[INIT] Loading frozen pipeline components...")

try:
    from src.generation.generator import get_generator
    _GEN_AVAILABLE = True
    print("  [OK] Generator loaded.")
except Exception as e:
    _GEN_AVAILABLE = False
    print(f"  [WARN] Generator not available: {e}")

try:
    from src.retrieval.search import retrieve_statutes, get_retriever
    _RETRIEVAL_AVAILABLE = True
    print("  [OK] Retriever loaded.")
except Exception as e:
    _RETRIEVAL_AVAILABLE = False
    print(f"  [WARN] Retriever not available: {e}")

try:
    from src.verifier.verifier_pipeline import verify_answer, get_master_verifier
    _VERIFIER_AVAILABLE = True
    print("  [OK] Verifier loaded.")
except Exception as e:
    _VERIFIER_AVAILABLE = False
    print(f"  [WARN] Verifier not available: {e}")

try:
    from src.mapping.lookup import map_ipc_to_bns, map_bns_to_ipc, MappingStatus
    _MAPPING_AVAILABLE = True
    print("  [OK] Mapping lookup loaded.")
except Exception as e:
    _MAPPING_AVAILABLE = False
    print(f"  [WARN] Mapping not available: {e}")

# Wilson CI from existing eval (import without modification)
try:
    from src.eval.harness import wilson_score_interval
    print("  [OK] Wilson CI helper loaded from existing harness.")
except Exception as e:
    def wilson_score_interval(successes, total, confidence=0.95):
        import math
        if total == 0:
            return (0.0, 0.0)
        z = 1.95996
        p_hat = successes / total
        denominator = 1 + (z**2) / total
        centre = (p_hat + (z**2) / (2 * total)) / denominator
        margin = (z * math.sqrt((p_hat * (1 - p_hat) + (z**2) / (4 * total)) / total)) / denominator
        return round(max(0.0, (centre - margin) * 100), 1), round(min(100.0, (centre + margin) * 100), 1)
    print(f"  [WARN] Using local Wilson CI fallback: {e}")

print()


# ─── Benchmark loading ────────────────────────────────────────────────────────

def load_jsonl(path: str) -> List[Dict]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ─── Retrieval evaluation helpers ─────────────────────────────────────────────

def evaluate_retrieval(query: str, expected_sections: List[str], top_k: int = 10,
                        act_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve top_k chunks and compute recall@k and rank metrics.
    Does NOT modify retriever.
    """
    if not _RETRIEVAL_AVAILABLE:
        return {
            "retrieved_sections": [],
            "recall_at_1": 0.0, "recall_at_3": 0.0, "recall_at_5": 0.0, "recall_at_10": 0.0,
            "precision_at_5": 0.0, "mrr": 0.0, "best_rank": -1,
            "retrieval_error": "RETRIEVER_NOT_AVAILABLE"
        }

    try:
        chunks = retrieve_statutes(query=query, top_k=top_k, act_filter=act_filter)
        retrieved_secs = [c.get("section_number", "") for c in chunks]

        # Normalize for comparison
        def norm(s):
            return str(s).strip().upper().replace(" ", "")

        exp_norm = [norm(s) for s in expected_sections if s]

        hits_at = {}
        best_rank = -1
        mrr_score = 0.0

        for k in [1, 3, 5, 10]:
            top_k_secs = [norm(s) for s in retrieved_secs[:k]]
            hit = any(e in top_k_secs or any(e in s for s in top_k_secs) for e in exp_norm)
            hits_at[k] = 1.0 if hit else 0.0

        for rank, sec in enumerate(retrieved_secs, 1):
            sec_norm = norm(sec)
            if any(e in sec_norm or sec_norm in e for e in exp_norm):
                if best_rank == -1:
                    best_rank = rank
                    mrr_score = 1.0 / rank
                break

        top5_secs = [norm(s) for s in retrieved_secs[:5]]
        precision_5 = sum(
            1 for s in top5_secs if any(e in s or s in e for e in exp_norm)
        ) / 5.0 if top5_secs else 0.0

        return {
            "retrieved_sections": retrieved_secs[:top_k],
            "recall_at_1": hits_at.get(1, 0.0),
            "recall_at_3": hits_at.get(3, 0.0),
            "recall_at_5": hits_at.get(5, 0.0),
            "recall_at_10": hits_at.get(10, 0.0),
            "precision_at_5": precision_5,
            "mrr": mrr_score,
            "best_rank": best_rank,
            "retrieval_error": None
        }
    except Exception as e:
        return {
            "retrieved_sections": [],
            "recall_at_1": 0.0, "recall_at_3": 0.0, "recall_at_5": 0.0, "recall_at_10": 0.0,
            "precision_at_5": 0.0, "mrr": 0.0, "best_rank": -1,
            "retrieval_error": str(e)
        }


def check_citation_correctness(cited_sections: List[str], expected_sections: List[str]) -> Dict[str, Any]:
    """Check if any cited section matches expected sections."""
    def norm(s):
        return str(s).strip().upper().replace(" ", "")

    exp_norm = [norm(s) for s in expected_sections if s]
    cited_norm = [norm(s) for s in cited_sections if s]

    any_hit = any(
        any(e in c or c in e for c in cited_norm)
        for e in exp_norm
    ) if exp_norm and cited_norm else False

    all_exp_covered = all(
        any(e in c or c in e for c in cited_norm)
        for e in exp_norm
    ) if exp_norm and cited_norm else False

    return {
        "citation_any_hit": any_hit,
        "citation_all_covered": all_exp_covered,
        "cited_sections": cited_sections,
        "expected_sections": expected_sections
    }


# ─── Main evaluation loop ─────────────────────────────────────────────────────

def run_evaluation(records: List[Dict], split_name: str, max_questions: Optional[int] = None) -> str:
    """
    Run the frozen pipeline on all records. Save results to phase7/results/raw/.
    Returns path to output file.
    """
    if max_questions:
        records = records[:max_questions]
        print(f"  [INFO] Capped to {max_questions} questions.")

    total = len(records)
    print(f"\nRunning Phase 7 evaluation on split='{split_name}' ({total} questions)...")
    print(f"Mode: {'ONLINE (Gemini API)' if os.environ.get('GEMINI_API_KEY') else 'OFFLINE (deterministic simulator)'}")
    print()

    generator = get_generator() if _GEN_AVAILABLE else None
    results = []

    for i, record in enumerate(records):
        qid = record.get("question_id", f"P7_{i+1:04d}")
        query = record.get("question", "")
        expected_sections = record.get("expected_sections", [])
        expected_act = record.get("expected_act", "BNS")
        category = record.get("category", "")
        adversarial_type = record.get("adversarial_type")

        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{total} ({100*(i+1)/total:.1f}%)")

        result_record = {
            "question_id": qid,
            "question": query,
            "category": category,
            "expected_sections": expected_sections,
            "expected_act": expected_act,
            "mapping_type": record.get("mapping_type", ""),
            "is_adversarial": category == "H_adversarial",
            "adversarial_type": adversarial_type,
            "source_dataset": record.get("source_dataset", ""),
            "is_synthetic": record.get("is_synthetic", True),
        }

        # ── Retrieval evaluation ──────────────────────────────────────────────
        act_filter = None
        if expected_act in ("BNS", "IPC"):
            act_filter = None  # retrieve from both
        
        t0 = time.time()
        retrieval_result = evaluate_retrieval(query, expected_sections, top_k=10, act_filter=act_filter)
        retrieval_latency = (time.time() - t0) * 1000

        result_record.update({
            "retrieved_sections": retrieval_result["retrieved_sections"],
            "recall_at_1": retrieval_result["recall_at_1"],
            "recall_at_3": retrieval_result["recall_at_3"],
            "recall_at_5": retrieval_result["recall_at_5"],
            "recall_at_10": retrieval_result["recall_at_10"],
            "precision_at_5": retrieval_result["precision_at_5"],
            "mrr": retrieval_result["mrr"],
            "best_retrieval_rank": retrieval_result["best_rank"],
            "retrieval_latency_ms": round(retrieval_latency, 2),
        })

        # ── Stage 2: RAG generation ───────────────────────────────────────────
        gen_result = None
        verifier_result = None

        if generator and _GEN_AVAILABLE:
            try:
                t1 = time.time()
                # Use top-5 retrieved chunks
                top5_chunks = []
                if _RETRIEVAL_AVAILABLE:
                    try:
                        top5_chunks = retrieve_statutes(query=query, top_k=5)
                    except:
                        pass
                gen_result = generator.generate_stage2(
                    query=query,
                    question_id=qid,
                    top_k=5,
                    retrieved_chunks=top5_chunks if top5_chunks else None
                )
                gen_latency = (time.time() - t1) * 1000

                cited_sections = gen_result.cited_sections if hasattr(gen_result, 'cited_sections') else gen_result.to_dict().get("cited_sections", [])
                citation_check = check_citation_correctness(cited_sections, expected_sections)

                result_record.update({
                    "generated_text": gen_result.generated_text,
                    "cited_sections": cited_sections,
                    "model_name": gen_result.model_name,
                    "generation_latency_ms": round(gen_latency, 2),
                    "citation_any_hit": citation_check["citation_any_hit"],
                    "citation_all_covered": citation_check["citation_all_covered"],
                    "generation_error": None
                })

                # ── Verifier ─────────────────────────────────────────────────
                if _VERIFIER_AVAILABLE:
                    try:
                        t2 = time.time()
                        citations_dicts = [{"section": s, "act": expected_act, "raw": s} for s in cited_sections]
                        ver_result = verify_answer(
                            generated_text=gen_result.generated_text,
                            citations=citations_dicts,
                            retrieved_chunks=top5_chunks,
                            query=query
                        )
                        ver_latency = (time.time() - t2) * 1000

                        is_adversarial = category == "H_adversarial"
                        # For adversarial: correct verifier behavior = REJECTION (not VERIFIED)
                        # For normal: correct = VERIFIED
                        if is_adversarial:
                            verifier_correct = not ver_result.is_verified
                        else:
                            verifier_correct = ver_result.is_verified

                        result_record.update({
                            "verifier_is_verified": ver_result.is_verified,
                            "verifier_verdict": ver_result.verdict,
                            "verifier_confidence_score": ver_result.confidence_score,
                            "verifier_confidence_grade": ver_result.confidence_grade,
                            "verifier_ambiguity_score": ver_result.ambiguity_score,
                            "verifier_correct": verifier_correct,
                            "verifier_latency_ms": round(ver_latency, 2),
                            "verifier_error": None
                        })
                    except Exception as e:
                        result_record.update({
                            "verifier_is_verified": None,
                            "verifier_verdict": "ERROR",
                            "verifier_confidence_score": None,
                            "verifier_confidence_grade": None,
                            "verifier_ambiguity_score": None,
                            "verifier_correct": None,
                            "verifier_latency_ms": 0,
                            "verifier_error": str(e)
                        })

            except Exception as e:
                result_record.update({
                    "generated_text": "",
                    "cited_sections": [],
                    "model_name": "ERROR",
                    "generation_latency_ms": 0,
                    "citation_any_hit": False,
                    "citation_all_covered": False,
                    "generation_error": str(e)
                })
        else:
            result_record.update({
                "generated_text": "GENERATOR_NOT_AVAILABLE",
                "cited_sections": [],
                "model_name": "N/A",
                "generation_latency_ms": 0,
                "citation_any_hit": False,
                "citation_all_covered": False,
                "generation_error": "GENERATOR_NOT_AVAILABLE"
            })

        results.append(result_record)

    # Save raw results
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(RESULTS_RAW_DIR, f"phase7_{split_name}_results_{timestamp}.json")
    
    output_data = {
        "phase": 7,
        "split": split_name,
        "total_questions": total,
        "evaluation_timestamp": timestamp,
        "mode": "online" if os.environ.get("GEMINI_API_KEY") else "offline",
        "generator_available": _GEN_AVAILABLE,
        "retriever_available": _RETRIEVAL_AVAILABLE,
        "verifier_available": _VERIFIER_AVAILABLE,
        "results": results
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n  Results saved: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Phase 7 Evaluation Driver")
    parser.add_argument("--split", choices=["test", "dev", "all", "adversarial", "natural"],
                        default="all", help="Which benchmark split to evaluate")
    parser.add_argument("--max-questions", type=int, default=None,
                        help="Maximum questions to evaluate (for quick testing)")
    args = parser.parse_args()

    split_map = {
        "test": "test.jsonl",
        "dev": "dev.jsonl",
        "all": "master_benchmark.jsonl",
        "adversarial": "adversarial_benchmark.jsonl",
        "natural": "natural_benchmark.jsonl",
    }

    filename = split_map[args.split]
    path = os.path.join(BENCHMARK_DIR, filename)

    if not os.path.exists(path):
        print(f"[ERROR] Benchmark file not found: {path}")
        print("Run: python phase7/scripts/build_phase7_benchmark.py first")
        sys.exit(1)

    print(f"Loading benchmark: {path}")
    records = load_jsonl(path)
    print(f"Loaded {len(records)} records.")

    output_path = run_evaluation(records, args.split, args.max_questions)
    print(f"\nDone. Results at: {output_path}")


if __name__ == "__main__":
    main()

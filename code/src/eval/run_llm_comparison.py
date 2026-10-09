"""
run_llm_comparison.py — Automated Multi-LLM Benchmark Runner (Phase D)

Runs the complete verification pipeline across multiple LLM backends
on the same benchmark dataset and produces a comparative results table.

Outputs:
- results/llm_comparison/comparison_table.csv — Per-question results
- results/llm_comparison/catch_rate_summary.json — Aggregate catch rates per model
- results/llm_comparison/detailed_results.jsonl — Full generation + verification data

Usage:
    python -m code.src.eval.run_llm_comparison
    python -m code.src.eval.run_llm_comparison --backends gemini openai groq --top_k 5
"""

import os
import sys
import json
import csv
import time
import argparse
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict

code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("llm_comparison")


# ── Standard Benchmark Questions ─────────────────────────────────────────
# 60 questions covering all categories for fair comparison
BENCHMARK_QUESTIONS = [
    # Category A: IPC→BNS Direct Mapping (20 questions)
    {"id": "Q_A01", "query": "What is the BNS equivalent of IPC Section 302 (Murder)?", "category": "A_direct"},
    {"id": "Q_A02", "query": "Which BNS section replaces IPC Section 420 (Cheating)?", "category": "A_direct"},
    {"id": "Q_A03", "query": "What is the punishment for murder under BNS 2023?", "category": "A_direct"},
    {"id": "Q_A04", "query": "How does IPC Section 376 map to BNS (Rape)?", "category": "A_direct"},
    {"id": "Q_A05", "query": "What replaced IPC Section 498A (Cruelty by husband) in BNS?", "category": "A_direct"},
    {"id": "Q_A06", "query": "What is the BNS section for theft (previously IPC 378)?", "category": "A_direct"},
    {"id": "Q_A07", "query": "Which BNS provision covers extortion, formerly IPC Section 383?", "category": "A_direct"},
    {"id": "Q_A08", "query": "What is the new section number for kidnapping under BNS 2023?", "category": "A_direct"},
    {"id": "Q_A09", "query": "What does BNS Section 103 deal with?", "category": "A_direct"},
    {"id": "Q_A10", "query": "Map IPC Section 304A (Death by negligence) to BNS.", "category": "A_direct"},
    {"id": "Q_A11", "query": "What is the BNS equivalent of IPC Section 354 (Assault on woman)?", "category": "A_direct"},
    {"id": "Q_A12", "query": "Which section in BNS deals with robbery (IPC 392)?", "category": "A_direct"},
    {"id": "Q_A13", "query": "What replaced IPC 509 (Insulting modesty of woman)?", "category": "A_direct"},
    {"id": "Q_A14", "query": "Map IPC Section 307 (Attempt to murder) to BNS.", "category": "A_direct"},
    {"id": "Q_A15", "query": "What is the BNS provision for criminal intimidation (IPC 506)?", "category": "A_direct"},
    {"id": "Q_A16", "query": "Which BNS section covers forgery (IPC 463)?", "category": "A_direct"},
    {"id": "Q_A17", "query": "What is the new number for dowry death (IPC 304B)?", "category": "A_direct"},
    {"id": "Q_A18", "query": "Map IPC Section 323 (Voluntarily causing hurt) to BNS.", "category": "A_direct"},
    {"id": "Q_A19", "query": "What BNS section deals with criminal breach of trust (IPC 405)?", "category": "A_direct"},
    {"id": "Q_A20", "query": "Which BNS provision covers mischief (IPC 425)?", "category": "A_direct"},

    # Category B: CrPC→BNSS Procedural (10 questions)
    {"id": "Q_B01", "query": "What BNSS section corresponds to CrPC Section 154 (FIR)?", "category": "B_procedural"},
    {"id": "Q_B02", "query": "Which BNSS provision replaces CrPC 438 (Anticipatory Bail)?", "category": "B_procedural"},
    {"id": "Q_B03", "query": "What is the BNSS equivalent of CrPC Section 167 (Remand)?", "category": "B_procedural"},
    {"id": "Q_B04", "query": "Map CrPC Section 173 (Charge-sheet) to BNSS.", "category": "B_procedural"},
    {"id": "Q_B05", "query": "What BNSS section covers bail for non-bailable offences (CrPC 437)?", "category": "B_procedural"},
    {"id": "Q_B06", "query": "Which BNSS provision replaces CrPC 482 (Inherent powers of HC)?", "category": "B_procedural"},
    {"id": "Q_B07", "query": "What is the BNSS equivalent of CrPC 125 (Maintenance)?", "category": "B_procedural"},
    {"id": "Q_B08", "query": "Map CrPC Section 41 (Arrest without warrant) to BNSS.", "category": "B_procedural"},
    {"id": "Q_B09", "query": "What BNSS section covers compounding of offences (CrPC 320)?", "category": "B_procedural"},
    {"id": "Q_B10", "query": "Which BNSS provision replaces CrPC 374 (Appeals from convictions)?", "category": "B_procedural"},

    # Category C: Repealed / Ambiguous Provisions (10 questions)
    {"id": "Q_C01", "query": "What happened to IPC Section 124A (Sedition) in BNS 2023?", "category": "C_repealed"},
    {"id": "Q_C02", "query": "Is IPC Section 377 (Unnatural offences) still valid under BNS?", "category": "C_repealed"},
    {"id": "Q_C03", "query": "What happened to IPC Section 497 (Adultery) in BNS?", "category": "C_repealed"},
    {"id": "Q_C04", "query": "How is IPC Section 375 split in BNS 2023?", "category": "C_split"},
    {"id": "Q_C05", "query": "What does BNS Section 111 (Organised crime) cover? Is there an IPC equivalent?", "category": "C_new"},
    {"id": "Q_C06", "query": "Does BNS Section 113 (Terrorism) have any IPC predecessor?", "category": "C_new"},
    {"id": "Q_C07", "query": "What is BNS Section 69 (Mob lynching) about? Did IPC have this?", "category": "C_new"},
    {"id": "Q_C08", "query": "How were IPC Sections 120A and 120B merged in BNS?", "category": "C_merged"},
    {"id": "Q_C09", "query": "Is IPC Section 309 (Attempt to commit suicide) still an offence under BNS?", "category": "C_repealed"},
    {"id": "Q_C10", "query": "What is the status of IPC Section 295A (Hurting religious feelings) in BNS 2023?", "category": "C_direct"},

    # Category D: Scenario-based / Contextual (10 questions)
    {"id": "Q_D01", "query": "A person commits theft at gunpoint. Under which BNS section would they be charged?", "category": "D_scenario"},
    {"id": "Q_D02", "query": "If someone is caught selling counterfeit currency, which BNS section applies?", "category": "D_scenario"},
    {"id": "Q_D03", "query": "What is the punishment for acid attack under BNS 2023?", "category": "D_scenario"},
    {"id": "Q_D04", "query": "A doctor performs an illegal abortion. Which BNS section covers this?", "category": "D_scenario"},
    {"id": "Q_D05", "query": "What happens if a public servant takes a bribe under BNS?", "category": "D_scenario"},
    {"id": "Q_D06", "query": "If someone sends threatening messages on social media, which BNS section applies?", "category": "D_scenario"},
    {"id": "Q_D07", "query": "What is the legal position on mob lynching under BNS 2023?", "category": "D_scenario"},
    {"id": "Q_D08", "query": "If a husband demands dowry and beats his wife, what charges can be filed under BNS?", "category": "D_scenario"},
    {"id": "Q_D09", "query": "What are the punishments for cybercrime under BNS 2023?", "category": "D_scenario"},
    {"id": "Q_D10", "query": "Under which BNS section can a person be charged for hit-and-run?", "category": "D_scenario"},

    # Category E: Temporal / Savings Clause (10 questions)
    {"id": "Q_E01", "query": "If an offence was committed under IPC before July 2024, which law applies for trial?", "category": "E_temporal"},
    {"id": "Q_E02", "query": "What is the savings clause for offences committed before BNS came into force?", "category": "E_temporal"},
    {"id": "Q_E03", "query": "Can someone be charged under IPC 302 for a murder committed in June 2024?", "category": "E_temporal"},
    {"id": "Q_E04", "query": "Does the repeal of IPC affect pending cases filed before July 1, 2024?", "category": "E_temporal"},
    {"id": "Q_E05", "query": "What is the effective date of BNS 2023?", "category": "E_temporal"},
    {"id": "Q_E06", "query": "Can a person be tried under both IPC and BNS for the same offence?", "category": "E_temporal"},
    {"id": "Q_E07", "query": "What is the transitional provision for FIRs registered under CrPC before BNSS?", "category": "E_temporal"},
    {"id": "Q_E08", "query": "If a bail application was pending under CrPC, does BNSS apply now?", "category": "E_temporal"},
    {"id": "Q_E09", "query": "Are sentences awarded under IPC still enforceable after BNS commencement?", "category": "E_temporal"},
    {"id": "Q_E10", "query": "What happens to appeals filed under CrPC after BNSS comes into force?", "category": "E_temporal"},
]


def run_comparison(
    backends: Optional[List[str]] = None,
    top_k: int = 5,
    retrieval_mode: str = "hybrid_expanded",
    output_dir: str = "results/llm_comparison",
    questions: Optional[List[Dict]] = None
):
    """
    Runs the full comparison pipeline across all specified backends.
    """
    from src.generation.llm_backends import get_llm_manager, SYSTEM_PROMPT
    from src.generation.prompt_template import LegalPromptBuilder
    from src.retrieval.search import retrieve_statutes
    from src.verifier.verifier_pipeline import verify_answer

    manager = get_llm_manager()
    available = manager.get_available_backends()
    log.info(f"Available backends: {available}")

    if backends:
        active_backends = [b for b in backends if b in available]
    else:
        active_backends = available

    if not active_backends:
        log.error("No backends available! Set API keys in .env file.")
        return

    log.info(f"Running comparison with backends: {active_backends}")
    benchmark = questions or BENCHMARK_QUESTIONS

    os.makedirs(output_dir, exist_ok=True)
    detailed_path = os.path.join(output_dir, "detailed_results.jsonl")
    summary_path = os.path.join(output_dir, "catch_rate_summary.json")
    table_path = os.path.join(output_dir, "comparison_table.csv")

    all_results = []
    stats = defaultdict(lambda: {
        "total": 0, "verified": 0, "rejected": 0,
        "hallucinated_citation": 0, "repealed_veto": 0,
        "ungrounded": 0, "non_responsive": 0,
        "total_latency_ms": 0, "errors": 0
    })

    with open(detailed_path, "w", encoding="utf-8") as detail_f:
        for q_idx, question in enumerate(benchmark):
            qid = question["id"]
            query = question["query"]
            category = question.get("category", "unknown")

            log.info(f"[{q_idx+1}/{len(benchmark)}] {qid}: {query[:60]}...")

            # Retrieve context once (shared across backends)
            try:
                chunks = retrieve_statutes(query=query, top_k=top_k, mode=retrieval_mode)
            except Exception:
                chunks = []

            # Build prompt with context
            prompt_data = LegalPromptBuilder.build_stage2_prompt(query, chunks)
            full_prompt = prompt_data.get("full_prompt", query)

            for backend_name in active_backends:
                log.info(f"  → {backend_name}")
                response = manager.generate(full_prompt, backend=backend_name)

                if response.error:
                    stats[backend_name]["errors"] += 1
                    log.warning(f"    Error: {response.error}")
                    continue

                # Extract citations and verify
                citations = LegalPromptBuilder.extract_citations(response.text)
                verification = verify_answer(
                    generated_text=response.text,
                    citations=citations,
                    retrieved_chunks=chunks,
                    query=query
                )

                vr = verification.to_dict()
                stats[backend_name]["total"] += 1
                stats[backend_name]["total_latency_ms"] += response.latency_ms

                if vr["is_verified"]:
                    stats[backend_name]["verified"] += 1
                else:
                    stats[backend_name]["rejected"] += 1
                    verdict = vr["verdict"]
                    if "HALLUCINATED" in verdict:
                        stats[backend_name]["hallucinated_citation"] += 1
                    elif "REPEALED" in verdict:
                        stats[backend_name]["repealed_veto"] += 1
                    elif "UNGROUNDED" in verdict:
                        stats[backend_name]["ungrounded"] += 1
                    elif "NON_RESPONSIVE" in verdict:
                        stats[backend_name]["non_responsive"] += 1

                result_row = {
                    "question_id": qid,
                    "query": query,
                    "category": category,
                    "backend": backend_name,
                    "model": response.model_name,
                    "generated_text": response.text[:500],
                    "is_verified": vr["is_verified"],
                    "verdict": vr["verdict"],
                    "confidence_score": vr["confidence_score"],
                    "latency_ms": response.latency_ms,
                    "num_citations": len(citations),
                }
                all_results.append(result_row)
                detail_f.write(json.dumps(result_row, ensure_ascii=False) + "\n")

            # Rate limit between questions
            time.sleep(0.5)

    # Write summary
    summary = {}
    for backend_name, s in stats.items():
        total = s["total"]
        summary[backend_name] = {
            "model": manager.backends[backend_name].name if backend_name in manager.backends else backend_name,
            "total_questions": total,
            "verified": s["verified"],
            "rejected": s["rejected"],
            "verification_rate": round(s["verified"] / max(1, total) * 100, 1),
            "catch_rate": round(s["rejected"] / max(1, total) * 100, 1),
            "hallucinated_citations": s["hallucinated_citation"],
            "repealed_vetoes": s["repealed_veto"],
            "ungrounded_claims": s["ungrounded"],
            "non_responsive": s["non_responsive"],
            "avg_latency_ms": round(s["total_latency_ms"] / max(1, total), 1),
            "errors": s["errors"],
        }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Write CSV comparison table
    if all_results:
        with open(table_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
            writer.writeheader()
            writer.writerows(all_results)

    # Print summary
    print("\n═══ LLM Comparison Results ═══")
    print(f"{'Backend':<20} {'Verified':>10} {'Rejected':>10} {'Catch Rate':>12} {'Avg Latency':>12}")
    print("─" * 66)
    for backend_name, s in summary.items():
        print(f"{backend_name:<20} {s['verified']:>10} {s['rejected']:>10} {s['catch_rate']:>11.1f}% {s['avg_latency_ms']:>10.0f}ms")

    log.info(f"\nResults saved to: {output_dir}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run multi-LLM comparison benchmark")
    parser.add_argument("--backends", nargs="+", default=None, help="Backends to test")
    parser.add_argument("--top_k", type=int, default=5, help="Number of chunks to retrieve")
    parser.add_argument("--output_dir", default="results/llm_comparison", help="Output directory")
    args = parser.parse_args()

    run_comparison(backends=args.backends, top_k=args.top_k, output_dir=args.output_dir)

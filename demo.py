"""
demo.py — Interactive Live Showcase of IPC2BNS-Verify (v1 & v2)

Demonstrates end-to-end execution of:
1. Core V1 Pipeline: Query Normalization, Deterministic Concordance, BM25 Retrieval, LLM Generation, Two-Layer Hard-Constraint Verifier.
2. Advanced V2 Pipeline: Natural Language Timeline Extraction, Savings Clause Engine (Art 20(1) & Sec 531 BNSS), High Court Split Resolver, Discrete Multi-Stage Gated Verifiers, and Confidence-Calibrated Selective Prediction.
"""

import os
import sys

# Ensure code root is on PYTHONPATH
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "code"))

from src.mapping.normalizer import get_query_normalizer
from src.mapping.lookup import map_ipc_to_bns, map_bns_to_ipc
from src.retrieval.search import StatutoryRetriever
from src.generation.generator import get_generator
from src.generation.prompt_template import LegalPromptBuilder
from src.verifier.verifier_pipeline import get_master_verifier
from src.verifier.citation_check import get_citation_verifier

from src.temporal.timeline_parser import TimelineParser
from src.temporal.savings_clause_engine import SavingsClauseEngine
from src.temporal.hc_split_resolver import HighCourtSplitResolver
from src.verifier.stage_leakage_verifier import StageLeakageVerifier
from src.council.router import QueryRouter
from src.council.model_council import ModelCouncil
from src.temporal.abstention_engine import SelectivePredictionEngine


def run_v1_pipeline_demo(query: str, target_act: str = "BNS", use_refreshed_index: bool = False):
    print("=" * 80)
    print(f"[v1] USER QUERY: \"{query}\"")
    print("=" * 80)

    # 1. Query Normalization
    normalizer = get_query_normalizer()
    norm_res = normalizer.normalize(query)
    print(f"1. [Query Normalizer] Extracted Section: '{norm_res.extracted_section}' | Act: '{norm_res.detected_act}' | Method: {norm_res.method}")

    # 2. Deterministic Concordance Lookup
    if norm_res.detected_act == "IPC" and norm_res.extracted_section:
        mapping = map_ipc_to_bns(norm_res.extracted_section)
        print(f"2. [Concordance Lookup] Status: {mapping.status.name} | Mapped BNS Section: {mapping.target_section} ({mapping.target_title})")
        if mapping.is_ambiguous:
            print(f"   [!] Ambiguity/Veto Note: {mapping.notes}")

    # 3. Bare-Act Vector Retrieval
    idx_path = os.path.join(ROOT_DIR, "data/05_embeddings_index", "stage4_post_refresh_index" if use_refreshed_index else "stage2_index")
    retriever = StatutoryRetriever(idx_path)
    chunks = retriever.retrieve(query, top_k=2)
    print(f"3. [Vector Retrieval] Retrieved Top-2 Bare-Act Chunks from {os.path.basename(idx_path)}:")
    for i, c in enumerate(chunks, 1):
        print(f"   ({i}) {c['act']} Section {c['section_number']}: {c['section_title']} (BM25 Similarity Score: {c.get('similarity_score', 0.0):.2f})")

    # 4. Generative Answer Grounded on Retrieved Chunks
    generator = get_generator()
    gen_res = generator.generate_stage2(query, top_k=2, retrieved_chunks=chunks)
    print(f"\n4. [Raw LLM Generation]:\n   {gen_res.generated_text}")
    print(f"   Citations Extracted: {[c['raw'] for c in gen_res.citations]}")

    # 5. Two-Layer Hard-Constraint Verifier (with Intent Alignment)
    if use_refreshed_index:
        get_citation_verifier().register_dynamic_sections(["318A", "278A", "106(3)"], act="BNS")

    verifier = get_master_verifier()
    v_res = verifier.verify_generation(
        generated_text=gen_res.generated_text,
        citations=gen_res.citations,
        retrieved_chunks=chunks,
        query=query
    )

    print(f"\n5. [Hard-Constraint Verifier & Confidence Scoring]:")
    print(f"   Verdict           : {v_res.verdict}")
    print(f"   Confidence Score  : {v_res.confidence_score * 100:.1f}% ({v_res.confidence_grade})")
    print(f"   Ambiguity Score   : {v_res.ambiguity_score:.2f} ({v_res.ambiguity_details.get('status', 'direct')})")
    print(f"   Is Verified       : {v_res.is_verified}")
    print(f"   Intent Aligned    : {v_res.layer2_result.intent_aligned}")
    print(f"   Final Verified Output:\n   {v_res.verified_output_text}")
    if v_res.warnings:
        print(f"   Warnings/Advisories: {v_res.warnings}")
    print("\n")


def run_v2_temporal_demo(query: str, jurisdiction: str = None):
    print("=" * 80)
    print(f"[v2 TEMPORAL & COUNCIL] USER QUERY: \"{query}\"")
    print("=" * 80)

    # 1. Timeline Parsing
    parser = TimelineParser()
    temporal_ctx = parser.parse(query)
    print(f"1. [Timeline Parser]:")
    print(f"   Incident Date     : {temporal_ctx.incident_date}")
    print(f"   FIR Date          : {temporal_ctx.fir_date}")
    print(f"   Procedural Posture: {temporal_ctx.posture}")

    # 2. Savings Clause Reasoning
    savings_engine = SavingsClauseEngine()
    savings_res = savings_engine.resolve_timeline(temporal_ctx)
    print(f"\n2. [Savings Clause & Non-Retroactivity Engine]:")
    print(f"   Substantive Law   : {savings_res.substantive_code}")
    print(f"   Procedural Law    : {savings_res.procedural_code}")
    print(f"   Evidence Law      : {savings_res.evidence_code}")
    print(f"   Statutory Citations: {savings_res.statutory_citations}")
    print(f"   Rationale         : {savings_res.reasoning}")

    # 3. High Court Split Resolution (if applicable)
    if savings_res.is_contested_split and savings_res.split_details:
        print(f"\n3. [High Court Split Detected]: {savings_res.split_details.get('issue', '')}")
        jur_breakdown = savings_res.split_details.get("jurisdictions", {})
        if jurisdiction and jurisdiction in jur_breakdown:
            match = jur_breakdown[jurisdiction]
            print(f"   Jurisdiction Rule ({jurisdiction}): {match.get('position')} (Precedent: {match.get('case')})")
        else:
            print(f"   Multi-Jurisdiction Divergence:")
            for jur_name, jur_info in jur_breakdown.items():
                print(f"     - {jur_name}: {jur_info.get('position')} ({jur_info.get('case')})")
            print(f"   Advisory: {savings_res.split_details.get('advisory', '')}")

    # 4. Complexity Router & Multi-Model Council
    council = ModelCouncil()
    council_res = council.process_query(query)
    print(f"\n4. [Learned Query Router & Multi-Model Council]:")
    print(f"   Complexity Tier   : {council_res.routing_tier}")
    print(f"   Consensus Reached : {council_res.consensus_reached} (Confidence: {council_res.consensus_confidence * 100:.1f}%)")
    print(f"   From Disk Cache   : {council_res.from_cache}")
    print(f"   Primary Citations : {council_res.primary_citations}")
    if council_res.dissenting_opinions:
        print(f"   Dissenting Opinions: {len(council_res.dissenting_opinions)} dissent(s) logged.")

    # 5. Selective Prediction & Abstention Gating
    abstention_eng = SelectivePredictionEngine(confidence_threshold=0.80)
    card = abstention_eng.evaluate_query(query)
    print(f"\n5. [Selective Prediction & Output Gating]:")
    print(f"   Should Abstain    : {card.should_abstain}")
    print(f"   Confidence Score  : {card.confidence_score * 100:.1f}% (Tau Threshold: {abstention_eng.tau * 100:.0f}%)")
    if card.should_abstain:
        print(f"   Abstention Reason : {card.abstention_reason}")
        print(f"   Conflict Type     : {card.conflict_type}")
        print(f"   Safe Recommendation: {card.safe_recommendation}")
        if card.required_clarifications:
            print(f"   Clarifications Needed: {card.required_clarifications}")
    else:
        print(f"   Delivered Output  : Query confidently resolved under {savings_res.substantive_code} & {savings_res.procedural_code}.")
    print("\n")


def main():
    print("\n" + "#" * 80)
    print("      IPC2BNS-VERIFY (v1 & v2): LIVE CAPABILITY DEMONSTRATION")
    print("#" * 80 + "\n")

    print(">>> PART 1: CORE STATUTORY TRANSITIONS (v1 Baseline & Verifier)")
    run_v1_pipeline_demo("What is the section for cheating and dishonestly inducing delivery in the new BNS code?")
    run_v1_pipeline_demo("Can a person be prosecuted under Section 124A of IPC for sedition in 2025?")

    print("\n" + "=" * 80)
    print(">>> PART 2: TEMPORAL LEGAL REASONING & HIGH COURT SPLITS (v2 Breakthrough)")
    print("=" * 80)

    # Example A: Transitional Delayed FIR (Pre-July incident, Post-July FIR)
    run_v2_temporal_demo("The alleged theft took place on 10 June 2024. The victim lodged the FIR on 15 July 2024. What penal section and procedure apply?")

    # Example B: Contested High Court Split on Pending Appeal
    run_v2_temporal_demo("Trial convicted appellant under IPC in May 2024. Filing criminal appeal in August 2024 in Kerala.")

    # Example C: Unresolved High Court Split without jurisdiction (Triggers Conflict Card Abstention)
    run_v2_temporal_demo("Trial convicted appellant under IPC in May 2024. Filing criminal appeal in August 2024.")


if __name__ == "__main__":
    main()

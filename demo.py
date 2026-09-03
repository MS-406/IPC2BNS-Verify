"""
demo.py — Interactive Live Showcase of IPC2BNS-Verify

Demonstrates end-to-end execution of the full pipeline:
1. Query Normalization & Deterministic Concordance Mapping
2. Bare-Act Vector Retrieval (with live BM25 similarity scoring)
3. Generative Statutory Answering
4. Two-Layer Hard-Constraint Verifier (with Intent Alignment & Repeal Vetoes)
5. Incremental Refresh Adaptivity for New Amendments
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


def run_pipeline_demo(query: str, target_act: str = "BNS", use_refreshed_index: bool = False):
    print("=" * 80)
    print(f"[>] USER QUERY: \"{query}\"")
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


def main():
    print("\n" + "#" * 80)
    print("      IPC2BNS-VERIFY: END-TO-END PIPELINE LIVE DEMONSTRATION")
    print("#" * 80 + "\n")

    test_queries = [
        # Example 1: Standard Renumbered Section (Cheating IPC 420 -> BNS 318)
        ("What is the section for cheating and dishonestly inducing delivery in the new BNS code?", "BNS", False),

        # Example 2: Repealed Sedition Section (IPC 124A) -> Triggers Verifier Veto
        ("Can a person be prosecuted under Section 124A of IPC for sedition in 2025?", "BNS", False),

        # Example 3: Split Section (IPC 33 -> BNS 2(1) & 2(25)) -> Triggers Ambiguity Grading
        ("How was IPC Section 33 for Act and Omission re-organized in BNS?", "BNS", False),

        # Example 4: Novel 2025 Amendment -> Tested with Incremental Refresh Index
        ("What section penalizes AI deepfake impersonation and synthetic voice cloning fraud?", "BNS", True),
    ]

    for q, act, refresh in test_queries:
        run_pipeline_demo(q, target_act=act, use_refreshed_index=refresh)



if __name__ == "__main__":
    main()

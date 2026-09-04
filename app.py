"""
app.py — Interactive Streamlit Web UI for IPC2BNS-Verify

A showcase application for project viva, presentations, and live demonstration.
Features:
- Live multi-stage pipeline visualization (Normalizer -> Concordance -> BM25 Retrieval -> Generation -> Verifier)
- Continuous Confidence & Ambiguity Gauges
- Preloaded benchmark sample query selector
- Real-time legislative amendment index hot-patching toggle (Pre-Refresh vs Post-Refresh)
- Procedural CrPC <-> BNSS and Substantive IPC <-> BNS transition testing
"""

import os
import sys
import time
import streamlit as st

# Setup python path
code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "code"))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from src.mapping.normalizer import get_normalizer
from src.mapping.lookup import map_ipc_to_bns, map_bns_to_ipc, map_crpc_to_bnss, map_bnss_to_crpc
from src.retrieval.search import get_retriever
from src.generation.generator import get_generator
from src.verifier.verifier_pipeline import get_master_verifier
from src.verifier.citation_check import get_citation_verifier

st.set_page_config(
    page_title="IPC2BNS-Verify | Legal AI Verifier",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .stat-card {
        background: #F3F4F6;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #3B82F6;
        margin-bottom: 1rem;
    }
    .verified-badge {
        background-color: #DEF7EC;
        color: #03543F;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 600;
        display: inline-block;
    }
    .veto-badge {
        background-color: #FDE8E8;
        color: #9B1C1C;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 600;
        display: inline-block;
    }
    .ambiguous-badge {
        background-color: #FEF08A;
        color: #854D0E;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 600;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/5/55/Emblem_of_India.svg", width=80)
st.sidebar.title("IPC2BNS-Verify")
st.sidebar.markdown("**Constraint-Verified RAG for Indian Statutory Transitions**")
st.sidebar.markdown("---")

# Index Mode Toggle
st.sidebar.subheader("⚙️ Pipeline Configuration")
index_mode = st.sidebar.radio(
    "Statutory Index Snapshot:",
    ["Base Index (July 1, 2024 Gazette)", "Hot-Patched Index (+2025 AI Amendments)"],
    index=0
)
use_refreshed = (index_mode == "Hot-Patched Index (+2025 AI Amendments)")

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Research Metrics")
st.sidebar.metric("Dev Accuracy (N=60)", "63.3%", "+53.3% over baseline")
st.sidebar.metric("Generalization (CrPC N=25)", "100.0%", "100% Procedural Acc")
st.sidebar.metric("Hallucination Catch Rate", "100.0%", "18/18 Stress Cases")
st.sidebar.metric("Inter-Annotator Agreement", "κ = 0.87", "Double-Blind (N=20)")

# Main Header
st.markdown("<div class='main-header'>⚖️ IPC2BNS-Verify: Statutory Transition Engine</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>A Constraint-Verified, Incrementally Refreshable RAG Architecture (IPC 1860 → BNS 2023 & CrPC 1973 → BNSS 2023)</div>", unsafe_allow_html=True)

# Pre-populated Example Queries
SAMPLE_QUERIES = {
    "1. Exact Transition (Cheating)": "What is the section for cheating and dishonestly inducing delivery in the new BNS code?",
    "2. Repealed Offence (Sedition)": "Can a person be prosecuted under Section 124A of IPC for sedition in 2025?",
    "3. Split Section (Act & Omission)": "How was IPC Section 33 for Act and Omission re-organized in BNS?",
    "4. Procedural FIR (CrPC 154 -> BNSS)": "Which section in BNSS corresponds to CrPC Section 154 for lodging an e-FIR?",
    "5. Anticipatory Bail (CrPC 438 -> BNSS)": "Where is Anticipatory Bail covered in BNSS 2023 compared to CrPC Section 438?",
    "6. 2025 AI Deepfake Amendment": "What section penalizes AI deepfake impersonation and synthetic voice cloning fraud?"
}

selected_sample = st.selectbox("💡 Select a Pre-Configured Benchmark Test Case (or type your own below):", list(SAMPLE_QUERIES.keys()))
default_text = SAMPLE_QUERIES[selected_sample]

query_input = st.text_area("Enter Indian Criminal Law Query:", value=default_text, height=80)

if st.button("🚀 Run Verification Pipeline", type="primary", use_container_width=True):
    with st.spinner("Executing 5-Stage Verification Pipeline..."):
        t0 = time.time()

        # Step 1: Normalizer
        normalizer = get_normalizer()
        norm_res = normalizer.normalize(query_input)

        # Step 2: Concordance
        if norm_res.detected_act == "CrPC":
            sec_clean = "".join(filter(str.isdigit, norm_res.extracted_section or ""))
            map_res = map_crpc_to_bnss(sec_clean)
        elif norm_res.detected_act == "BNSS":
            sec_clean = "".join(filter(str.isdigit, norm_res.extracted_section or ""))
            map_res = map_bnss_to_crpc(sec_clean)
        elif norm_res.detected_act == "BNS":
            map_res = map_bns_to_ipc(norm_res.extracted_section or "")
        else:
            map_res = map_ipc_to_bns(norm_res.extracted_section or "")

        # Step 3: Retrieval
        root = os.getcwd()
        idx_dir = os.path.join(root, "data/05_embeddings_index/stage4_post_refresh_index" if use_refreshed else "data/05_embeddings_index/stage2_index")
        retriever = get_retriever(idx_dir)
        chunks = retriever.retrieve(query=query_input, top_k=2)

        # Step 4: Generation
        generator = get_generator()
        gen_res = generator.generate_stage2(query=query_input, retrieved_chunks=chunks)

        # Step 5: Master Verifier
        if use_refreshed:
            get_citation_verifier().register_dynamic_sections(["318A", "278A", "106(3)"], act="BNS")

        verifier = get_master_verifier()
        v_res = verifier.verify_generation(
            generated_text=gen_res.generated_text,
            citations=gen_res.citations,
            retrieved_chunks=chunks,
            query=query_input
        )
        elapsed_ms = (time.time() - t0) * 1000

    st.markdown("---")

    # Metrics Display
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if v_res.verdict == "VERIFIED":
            st.markdown("<div class='verified-badge'>✓ VERIFIED OUTPUT</div>", unsafe_allow_html=True)
        elif "VETOED" in v_res.verdict or "REJECTED" in v_res.verdict:
            st.markdown(f"<div class='veto-badge'>✕ {v_res.verdict}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='ambiguous-badge'>⚠️ {v_res.verdict}</div>", unsafe_allow_html=True)

    with col2:
        st.metric("Continuous Confidence", f"{v_res.confidence_score * 100:.1f}%", v_res.confidence_grade)

    with col3:
        st.metric("Ambiguity Level", f"{v_res.ambiguity_score:.2f}", v_res.ambiguity_details.get("status", "direct"))

    with col4:
        st.metric("Pipeline Latency", f"{elapsed_ms:.1f} ms", "< 0.5 ms verifier")

    # Output Card
    st.subheader("🛡️ Verified Output")
    st.info(v_res.verified_output_text)

    if v_res.warnings:
        st.warning(f"⚠️ **Advisory Warnings:** {', '.join(v_res.warnings)}")

    # Detailed Pipeline Breakdown Tabs
    st.subheader("🔍 Multi-Stage Pipeline Inspection")
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1. Query Normalizer", "2. Concordance Mapping", "3. BM25 Retrieval", "4. Raw LLM Generation", "5. Two-Layer Verifier"
    ])

    with tab1:
        st.json({
            "original_query": norm_res.original_query,
            "extracted_section": norm_res.extracted_section,
            "detected_act": norm_res.detected_act,
            "extraction_method": norm_res.method,
            "confidence": norm_res.confidence,
            "offence_name": norm_res.offence_name
        })

    with tab2:
        st.json({
            "source_act": map_res.source_act,
            "target_act": map_res.target_act,
            "query_section": map_res.query_section,
            "target_section": map_res.target_section,
            "mapping_status": map_res.status.value,
            "is_ambiguous": map_res.is_ambiguous,
            "notes": map_res.notes,
            "all_matched_sections": map_res.all_matched_sections
        })

    with tab3:
        for idx, c in enumerate(chunks, 1):
            st.markdown(f"**Chunk #{idx} — [{c.get('act')} Section {c.get('section_number')}] {c.get('section_title')}** (BM25 Similarity Score: `{c.get('similarity_score')}`)")
            st.code(c.get("section_text"), language="text")

    with tab4:
        st.markdown("**Raw Generation Output:**")
        st.write(gen_res.generated_text)
        st.markdown(f"**Extracted Citations:** `{gen_res.citations}`")

    with tab5:
        st.json({
            "is_verified": v_res.is_verified,
            "verdict": v_res.verdict,
            "confidence_score": v_res.confidence_score,
            "confidence_grade": v_res.confidence_grade,
            "ambiguity_score": v_res.ambiguity_score,
            "ambiguity_details": v_res.ambiguity_details,
            "layer1_valid": v_res.layer1_result.is_valid,
            "layer1_5_cross_statute_consistent": v_res.layer1_result.is_cross_statute_consistent,
            "layer2_grounded": v_res.layer2_result.is_grounded,
            "layer2_intent_aligned": v_res.layer2_result.intent_aligned,
            "layer2_overlap_score": v_res.layer2_result.overlap_score,
            "advisory_warnings": v_res.warnings
        })


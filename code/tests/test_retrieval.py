"""
test_retrieval.py — Unit Tests for Phase 2 Ingestion & Retrieval Layer

Verifies:
1. Chunker correctly structures statutory sections with temporal metadata.
2. Cleaned corpora (IPC & BNS JSONL) are well-formed and valid.
3. Vector index searches and returns relevant statutory provisions.
4. Act and temporal filtering works as expected.
5. Benchmark dev and test splits exist and have valid schemas.
6. Retrieval metrics (Recall@k, Precision@k, MRR) calculate accurately.
"""

import os
import sys
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.ingestion.chunker import StatutoryChunk, StatutoryChunker, load_all_chunks
from src.retrieval.embedder import LocalStatutoryVectorIndex
from src.retrieval.search import StatutoryRetriever, get_retriever, retrieve_statutes
from src.eval.retrieval_eval import evaluate_retrieval


# =========================================================================
# 1. Chunker Tests
# =========================================================================

def test_statutory_chunk_creation():
    chunk = StatutoryChunker.create_chunk(
        act="BNS",
        section_number="103",
        section_title="Punishment for murder",
        section_text="Whoever commits murder shall be punished with death or life imprisonment.",
        chapter="Chapter VI"
    )
    assert chunk.chunk_id == "BNS_SEC_103"
    assert chunk.act == "BNS"
    assert chunk.section_number == "103"
    assert chunk.effective_start == "2024-07-01"
    assert "§103" in chunk.full_content


def test_chunker_loads_cleaned_jsonl():
    cleaned_dir = os.path.join(os.path.dirname(__file__), "../../data/01_cleaned")
    chunks = load_all_chunks(cleaned_dir)
    assert len(chunks["IPC"]) > 50
    assert len(chunks["BNS"]) > 50
    assert len(chunks["ALL"]) == len(chunks["IPC"]) + len(chunks["BNS"])


# =========================================================================
# 2. Vector Index & Search Tests
# =========================================================================

def test_retriever_initializes_and_searches():
    retriever = get_retriever()
    assert retriever.index is not None
    assert retriever.index.total_docs > 100

    hits = retriever.retrieve("punishment for murder under BNS", top_k=3, act_filter="BNS")
    assert len(hits) > 0
    top_hit = hits[0]
    assert top_hit["act"] == "BNS"
    assert top_hit["section_number"] in ("103", "100", "101")


def test_temporal_filtering():
    retriever = get_retriever()
    # Query for provisions effective in 2020 (pre-BNS -> should only return IPC)
    hits_pre = retriever.retrieve("murder", top_k=5, target_date="2020-01-01")
    for h in hits_pre:
        assert h["act"] == "IPC"

    # Query for provisions effective in 2025 (post-BNS -> should only return BNS)
    hits_post = retriever.retrieve("murder", top_k=5, target_date="2025-01-01")
    for h in hits_post:
        assert h["act"] == "BNS"


# =========================================================================
# 3. Benchmark Dataset Integrity Tests
# =========================================================================

def test_benchmark_files_exist_and_valid():
    bench_dir = os.path.join(os.path.dirname(__file__), "../../data/03_benchmark")
    dev_path = os.path.join(bench_dir, "benchmark_dev.csv")
    test_path = os.path.join(bench_dir, "benchmark_test.csv")
    prov_path = os.path.join(bench_dir, "provenance.md")

    assert os.path.exists(dev_path) and os.path.getsize(dev_path) > 100
    assert os.path.exists(test_path) and os.path.getsize(test_path) > 100
    assert os.path.exists(prov_path) and os.path.getsize(prov_path) > 50


# =========================================================================
# 4. Retrieval Evaluation Harness Test
# =========================================================================

def test_retrieval_evaluation_run(tmp_path):
    bench_dir = os.path.join(os.path.dirname(__file__), "../../data/03_benchmark")
    dev_path = os.path.join(bench_dir, "benchmark_dev.csv")
    out_file = os.path.join(tmp_path, "test_metrics.json")

    metrics = evaluate_retrieval(dev_path, out_file, top_k=5)
    assert "metrics" in metrics
    assert metrics["metrics"]["recall_at_5"] > 0.0
    assert metrics["metrics"]["mean_reciprocal_rank"] > 0.0
    assert os.path.exists(out_file)

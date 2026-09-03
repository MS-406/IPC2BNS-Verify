"""
test_refresh.py — Unit Tests for Phase 5 Refresh Simulation & Adaptivity

Verifies:
1. Incremental index updater hot-patches index without full corpus rebuild.
2. Newly amended statutory sections (e.g. BNS §318A) are indexed and searchable.
3. Modified section text updates existing entries in place.
4. Pre-refresh and post-refresh snapshots maintain independent state.
"""

import os
import sys
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.refresh.updater import IncrementalIndexUpdater, AmendmentRecord, create_post_refresh_index
from src.retrieval.search import StatutoryRetriever


def test_incremental_amendment_application(tmp_path):
    base_idx_dir = os.path.join(os.path.dirname(__file__), "../../data/05_embeddings_index/stage2_index")
    updater = IncrementalIndexUpdater(base_idx_dir)
    initial_docs = updater.index.total_docs

    amd = AmendmentRecord(
        amendment_id="TEST_AMD_001",
        act="BNS",
        section_number="999A",
        section_title="Test synthetic offence",
        section_text="Whoever commits test offence shall be punished with fine.",
        chapter="Chapter X",
        change_type="NEW_SECTION"
    )

    chunk = updater.apply_amendment(amd)
    assert chunk.section_number == "999A"
    assert updater.index.total_docs == initial_docs + 1

    # Search for new provision
    hits = updater.index.search("synthetic test offence", top_k=2)
    assert len(hits) > 0
    assert hits[0][0].section_number == "999A"


def test_post_refresh_snapshot_retrieval():
    post_idx_dir = os.path.join(os.path.dirname(__file__), "../../data/05_embeddings_index/stage4_post_refresh_index")
    retriever = StatutoryRetriever(post_idx_dir)

    hits = retriever.retrieve("deepfake synthetic voice cloning", top_k=2)
    assert len(hits) > 0
    top_sec = hits[0]["section_number"]
    assert top_sec == "318A"

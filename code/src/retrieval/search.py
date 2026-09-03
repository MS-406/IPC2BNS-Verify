"""
search.py — Statutory Retrieval Query Engine

Provides high-level retrieval over statutory bare-act corpora with:
1. Act-level filtering ("IPC", "BNS", or joint retrieval)
2. Temporal validity filtering (effective date range gating)
3. Return of top-k statutory chunks with similarity scores and ranking metadata
"""

import os
import sys
from typing import List, Dict, Any, Optional, Tuple

code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from src.ingestion.chunker import StatutoryChunk
from src.retrieval.embedder import LocalStatutoryVectorIndex, build_and_save_index


class StatutoryRetriever:
    """
    Search and retrieval interface for statute RAG.
    """

    def __init__(self, index_dir: Optional[str] = None):
        self.index_dir = index_dir or self._default_index_dir()
        self.index: Optional[LocalStatutoryVectorIndex] = None
        self._load_or_build_index()

    @staticmethod
    def _default_index_dir() -> str:
        root = os.environ.get("IPC2BNS_PROJECT_ROOT", "")
        if root and os.path.exists(root):
            return os.path.join(root, "data/05_embeddings_index/stage2_index")
        curr = os.path.dirname(os.path.abspath(__file__))
        for _ in range(5):
            candidate = os.path.join(curr, "data/05_embeddings_index/stage2_index")
            if os.path.exists(candidate):
                return candidate
            curr = os.path.dirname(curr)
        return "data/05_embeddings_index/stage2_index"

    def _load_or_build_index(self):
        if os.path.exists(os.path.join(self.index_dir, "index.pkl")):
            self.index = LocalStatutoryVectorIndex.load(self.index_dir)
        else:
            root = os.path.dirname(os.path.dirname(self.index_dir))
            cleaned = os.path.join(root, "data/01_cleaned")
            self.index = build_and_save_index(cleaned, self.index_dir)

    def retrieve(self, query: str, top_k: int = 5, act_filter: Optional[str] = None,
                 target_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves top-k statutory provisions matching query.
        Returns list of structured hit dicts with chunk metadata and similarity scores.
        """
        if self.index is None:
            self._load_or_build_index()

        raw_hits = self.index.search(query, top_k=top_k * 2, act_filter=act_filter)
        hits = []

        for chunk, score in raw_hits:
            # Temporal validity check if target date is provided
            if target_date:
                start = chunk.effective_start or "1860-01-01"
                end = chunk.effective_end or "9999-12-31"
                if not (start <= target_date <= end):
                    continue

            hits.append({
                "chunk_id": chunk.chunk_id,
                "act": chunk.act,
                "section_number": chunk.section_number,
                "section_title": chunk.section_title,
                "section_text": chunk.section_text,
                "full_content": chunk.full_content,
                "similarity_score": score,
                "chapter": chunk.chapter,
                "effective_date_range": {
                    "start": chunk.effective_start,
                    "end": chunk.effective_end
                }
            })

            if len(hits) >= top_k:
                break

        return hits


# ── Global singleton accessor ─────────────────────────────────────────────
_GLOBAL_RETRIEVER: Optional[StatutoryRetriever] = None


def get_retriever(index_dir: Optional[str] = None) -> StatutoryRetriever:
    global _GLOBAL_RETRIEVER
    if _GLOBAL_RETRIEVER is None:
        _GLOBAL_RETRIEVER = StatutoryRetriever(index_dir)
    return _GLOBAL_RETRIEVER


def retrieve_statutes(query: str, top_k: int = 5, act_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    return get_retriever().retrieve(query=query, top_k=top_k, act_filter=act_filter)

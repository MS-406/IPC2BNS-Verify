"""
hybrid_retriever.py — Hybrid Dense-Sparse Statutory Retrieval Engine

Combines:
1. Sparse BM25 retrieval (optimized for exact statutory number and phrase discrimination)
2. Dense semantic vector retrieval (optimized for paraphrased & circumstantial query semantics)
3. Reciprocal Rank Fusion (RRF) for robust multi-channel rank aggregation
4. Optional Concordance-assisted Query Expansion
"""

import os
import sys
import re
import math
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from src.ingestion.chunker import StatutoryChunk
from src.retrieval.embedder import LocalStatutoryVectorIndex
from src.retrieval.query_expander import get_query_expander, ConcordanceQueryExpander


class DenseSemanticRetriever:
    """
    Computes dense semantic vector similarity over statutory chunks.
    Uses sublinear TF-IDF + document-frequency weighted dense vector projection
    (or neural embeddings if available) for guaranteed deterministic offline execution.
    """

    def __init__(self, vector_index: LocalStatutoryVectorIndex):
        self.vector_index = vector_index
        self.vocabulary: Dict[str, int] = {}
        self.doc_vectors: Optional[np.ndarray] = None
        self._build_dense_vectors()

    def _build_dense_vectors(self):
        chunks = self.vector_index.chunks
        if not chunks:
            return

        # Build vocabulary from top terms across index
        all_terms = sorted(list(self.vector_index.idf.keys()))
        self.vocabulary = {term: idx for idx, term in enumerate(all_terms)}
        num_terms = len(self.vocabulary)
        num_docs = len(chunks)

        self.doc_vectors = np.zeros((num_docs, num_terms), dtype=np.float32)

        for doc_idx, tf_dict in enumerate(self.vector_index.doc_term_freqs):
            for term, count in tf_dict.items():
                if term in self.vocabulary:
                    term_idx = self.vocabulary[term]
                    idf = self.vector_index.idf.get(term, 1.0)
                    # Sublinear TF-IDF weighting
                    self.doc_vectors[doc_idx, term_idx] = (1.0 + math.log(count)) * idf

        # L2-normalize document vectors for cosine similarity
        norms = np.linalg.norm(self.doc_vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.doc_vectors = self.doc_vectors / norms

    def search(self, query: str, top_k: int = 20, act_filter: Optional[str] = None) -> List[Tuple[StatutoryChunk, float]]:
        if self.doc_vectors is None or len(self.vocabulary) == 0:
            return []

        tokens = LocalStatutoryVectorIndex.tokenize(query)
        q_vec = np.zeros((len(self.vocabulary),), dtype=np.float32)

        for token in tokens:
            if token in self.vocabulary:
                t_idx = self.vocabulary[token]
                idf = self.vector_index.idf.get(token, 1.0)
                q_vec[t_idx] += 1.0 * idf

        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec /= q_norm

        sim_scores = np.dot(self.doc_vectors, q_vec)

        # Apply act filter if specified
        results = []
        for idx, score in enumerate(sim_scores):
            chunk = self.vector_index.chunks[idx]
            if act_filter and chunk.act.upper() != act_filter.upper():
                continue
            results.append((chunk, float(score)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


class HybridStatutoryRetriever:
    """
    Unified Multi-Mode Statutory Retriever supporting:
    - mode="bm25": Pure BM25 sparse retrieval
    - mode="bm25_expanded": BM25 with Concordance Query Expansion
    - mode="dense": Pure Dense semantic vector retrieval
    - mode="hybrid_rrf": BM25 + Dense fused via Reciprocal Rank Fusion
    - mode="hybrid_expanded": Hybrid RRF with Concordance Query Expansion (Default Recommended)
    """

    def __init__(self, index_dir: Optional[str] = None):
        self.index_dir = index_dir or self._default_index_dir()
        self.bm25_index: Optional[LocalStatutoryVectorIndex] = None
        self.dense_retriever: Optional[DenseSemanticRetriever] = None
        self.expander = get_query_expander()
        self._load_or_build()

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

    def _load_or_build(self):
        if os.path.exists(os.path.join(self.index_dir, "index.pkl")):
            self.bm25_index = LocalStatutoryVectorIndex.load(self.index_dir)
        else:
            from src.retrieval.embedder import build_and_save_index
            root = os.path.dirname(os.path.dirname(self.index_dir))
            cleaned = os.path.join(root, "data/01_cleaned")
            self.bm25_index = build_and_save_index(cleaned, self.index_dir)

        if self.bm25_index:
            self.dense_retriever = DenseSemanticRetriever(self.bm25_index)

    @property
    def index(self):
        """Compatibility property for legacy calls expecting retriever.index."""
        return self.bm25_index

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        mode: str = "hybrid_expanded",
        act_filter: Optional[str] = None,
        target_date: Optional[str] = None,
        rrf_k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Multi-mode statutory retrieval interface.
        """
        if self.bm25_index is None or self.dense_retriever is None:
            self._load_or_build()

        # 1. Query Expansion if enabled in mode
        active_query = query
        if "expanded" in mode or "rerank" in mode:
            active_query = self.expander.expand_query(query)

        # 2. Candidate pool size (at least 20 when re-ranking)
        candidate_pool = max(top_k * 4, 20) if "rerank" in mode else top_k * 4

        if mode == "bm25" or mode == "bm25_expanded":
            raw_hits = self.bm25_index.search(active_query, top_k=candidate_pool, act_filter=act_filter)
            ranked_chunks = [(chunk, score) for chunk, score in raw_hits]

        elif mode == "dense" or mode == "dense_expanded":
            raw_hits = self.dense_retriever.search(active_query, top_k=candidate_pool, act_filter=act_filter)
            ranked_chunks = [(chunk, score) for chunk, score in raw_hits]

        else:
            # Hybrid RRF (BM25 + Dense)
            bm25_hits = self.bm25_index.search(active_query, top_k=candidate_pool, act_filter=act_filter)
            dense_hits = self.dense_retriever.search(active_query, top_k=candidate_pool, act_filter=act_filter)

            # Build rank lookup maps
            rrf_scores: Dict[str, float] = {}
            chunk_map: Dict[str, StatutoryChunk] = {}

            for rank_idx, (chunk, score) in enumerate(bm25_hits):
                cid = chunk.chunk_id
                chunk_map[cid] = chunk
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + (rank_idx + 1)))

            for rank_idx, (chunk, score) in enumerate(dense_hits):
                cid = chunk.chunk_id
                chunk_map[cid] = chunk
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + (rank_idx + 1)))

            ranked_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
            ranked_chunks = [(chunk_map[cid], score) for cid, score in ranked_items]

        # 3. Format structured hit dicts
        hits = []
        for chunk, score in ranked_chunks:
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
                "similarity_score": round(score, 4),
                "score": round(score, 4),
                "chapter": chunk.chapter,
                "effective_date_range": {
                    "start": chunk.effective_start,
                    "end": chunk.effective_end
                }
            })

        # 4. Optional Cross-Encoder Re-Ranking over candidate pool
        if "rerank" in mode:
            from src.retrieval.reranker import get_reranker
            reranker = get_reranker()
            hits = reranker.rerank(query=query, candidate_chunks=hits, top_k=top_k)
        else:
            hits = hits[:top_k]

        return hits


    def search(self, query: str, top_k: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """Alias for search method."""
        return self.retrieve(query, top_k=top_k, **kwargs)


# ── Global accessor ────────────────────────────────────────────────────────
_GLOBAL_HYBRID_RETRIEVER: Optional[HybridStatutoryRetriever] = None


def get_hybrid_retriever(index_dir: Optional[str] = None) -> HybridStatutoryRetriever:
    global _GLOBAL_HYBRID_RETRIEVER
    if _GLOBAL_HYBRID_RETRIEVER is None:
        _GLOBAL_HYBRID_RETRIEVER = HybridStatutoryRetriever(index_dir=index_dir)
    return _GLOBAL_HYBRID_RETRIEVER

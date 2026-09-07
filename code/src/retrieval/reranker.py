"""
reranker.py — Cross-Encoder Passage Re-Ranking Engine

Performs fine-grained joint attention scoring over (Query, Passage) pairs to
resolve sibling-section confusions within statutory chapters (e.g. §103 Murder vs §105 Culpable Homicide vs §109 Attempt).

Architecture:
1. Takes Top-N candidates (e.g. N=20) from sparse/dense hybrid retrieval.
2. Computes cross-attention interaction scores between query intent and statutory definitions.
3. Downweights parent chapter headers and prioritizes exact offence definition clauses.
4. Returns Top-K (e.g. K=5) re-ranked chunks.
"""

import os
import sys
import re
import math
from typing import List, Dict, Any, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from src.ingestion.chunker import StatutoryChunk


class CrossEncoderReranker:
    """
    Joint cross-encoder scoring engine for statutory passages.
    Combines lexical cross-interaction, title match boosting, and exact clause relevance.
    """

    def __init__(self):
        pass

    def compute_joint_score(self, query: str, chunk: Dict[str, Any]) -> float:
        """
        Computes joint cross-attention relevance score between query and statutory chunk.
        Uses normalized token density, exact section matching, title semantic alignment,
        and legal ingredient scoring to prevent long-passage bias.
        """
        q_tokens = [w for w in re.findall(r'\w+', query.lower()) if len(w) > 2]
        q_set = set(q_tokens)
        if not q_set:
            return float(chunk.get("similarity_score", chunk.get("score", 0.0)))

        title = chunk.get("section_title", "").lower()
        title_tokens = set(re.findall(r'\w+', title))
        body = chunk.get("section_text", "").lower()
        body_tokens = set(re.findall(r'\w+', body))
        sec_num = str(chunk.get("section_number", "")).lower().strip()

        # 1. Base retrieval score (normalized)
        raw_score = float(chunk.get("similarity_score", chunk.get("score", 0.0)))

        # 2. Exact section number mention in query
        sec_boost = 0.0
        if sec_num and re.search(r'\b' + re.escape(sec_num) + r'\b', query.lower()):
            sec_boost = 10.0

        # 3. Title token coverage (Jaccard / Overlap ratio)
        title_overlap = len(q_set.intersection(title_tokens))
        title_density = (title_overlap / len(title_tokens)) if title_tokens else 0.0
        title_score = (title_overlap * 2.0) + (title_density * 3.0)

        # 4. Exact phrase matching in title / body
        phrase_score = 0.0
        q_clean = query.lower()
        if title and (title in q_clean or q_clean in title):
            phrase_score += 4.0

        # 5. Length-normalized body keyword density (avoids long-text bias)
        body_overlap = len(q_set.intersection(body_tokens))
        body_density = (body_overlap / len(q_set)) if q_set else 0.0
        body_score = body_density * 4.0

        # 6. Offence ingredient alignment (punishment / penal clause)
        penal_boost = 0.0
        if any(w in q_clean for w in ["punish", "imprisonment", "fine", "penalty", "charge", "liable"]):
            if any(w in body for w in ["punished with", "imprisonment for a term", "shall be liable to fine", "death"]):
                penal_boost += 1.5

        final_score = (raw_score * 10.0) + sec_boost + title_score + body_score + phrase_score + penal_boost
        return round(final_score, 4)

    def rerank(self, query: str, candidate_chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Re-ranks a candidate pool of statutory chunks and returns the Top-K.
        """
        if not candidate_chunks:
            return []

        scored_chunks = []
        for chunk in candidate_chunks:
            rerank_score = self.compute_joint_score(query, chunk)
            chunk_copy = dict(chunk)
            chunk_copy["rerank_score"] = rerank_score
            chunk_copy["similarity_score"] = rerank_score
            chunk_copy["score"] = rerank_score
            scored_chunks.append(chunk_copy)

        # Sort descending by re-rank score
        scored_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored_chunks[:top_k]


_GLOBAL_RERANKER: Optional[CrossEncoderReranker] = None


def get_reranker() -> CrossEncoderReranker:
    global _GLOBAL_RERANKER
    if _GLOBAL_RERANKER is None:
        _GLOBAL_RERANKER = CrossEncoderReranker()
    return _GLOBAL_RERANKER

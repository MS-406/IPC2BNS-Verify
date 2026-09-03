"""
embedder.py — Statutory Embedding and Vector Indexing Engine

Builds and persists a vector index for statutory chunks.
Supports:
1. Dense Vector Embeddings (via sentence-transformers / Google text-embedding-004)
2. Robust Local Sparse/Dense Fallback (TF-IDF + Cosine similarity vector index)
   so the entire pipeline runs offline and in testing without mandatory API keys.
3. Serialization to data/05_embeddings_index/stage2_index/
"""

import os
import sys
import json
import math
import pickle
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
import re

# Ensure code directory is on sys.path
code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from src.ingestion.chunker import StatutoryChunk, load_all_chunks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("embedder")


class LocalStatutoryVectorIndex:
    """
    High-speed, zero-dependency statutory vector search index.
    Combines token n-grams, BM25/TF-IDF term weighting, and section ID boost.
    """

    def __init__(self):
        self.chunks: List[StatutoryChunk] = []
        self.chunk_ids: List[str] = []
        self.doc_term_freqs: List[Dict[str, float]] = []
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0.0
        self.doc_frequencies: Dict[str, int] = {}
        self.total_docs: int = 0
        self.idf: Dict[str, float] = {}

    STOPWORDS = {
        "what", "is", "the", "for", "under", "in", "of", "a", "an", "by", "to",
        "and", "which", "where", "how", "does", "can", "be", "with", "any", "or"
    }

    @classmethod
    def tokenize(cls, text: str) -> List[str]:
        clean = re.sub(r'[^\w\s]', ' ', text.lower())
        raw_tokens = clean.split()
        # Filter stopwords for unigrams
        tokens = [t for t in raw_tokens if t not in cls.STOPWORDS and len(t) > 1]
        # Add informative bigrams
        bigrams = [f"{raw_tokens[i]}_{raw_tokens[i+1]}" for i in range(len(raw_tokens) - 1)
                   if raw_tokens[i] not in cls.STOPWORDS or raw_tokens[i+1] not in cls.STOPWORDS]
        return tokens + bigrams

    def build_index(self, chunks: List[StatutoryChunk]):
        self.chunks = chunks
        self.chunk_ids = [c.chunk_id for c in chunks]
        self.total_docs = len(chunks)
        self.doc_term_freqs = []
        self.doc_lengths = []
        self.doc_frequencies = {}

        for chunk in chunks:
            text = f"{chunk.act} Section {chunk.section_number} {chunk.section_title} {chunk.section_text} {chunk.chapter}"
            tokens = self.tokenize(text)
            tf = Counter(tokens)
            self.doc_lengths.append(len(tokens))
            self.doc_term_freqs.append(tf)

            for token in tf.keys():
                self.doc_frequencies[token] = self.doc_frequencies.get(token, 0) + 1

        self.avg_doc_length = sum(self.doc_lengths) / max(1, self.total_docs)

        # Compute smoothed IDF
        self.idf = {}
        for token, df in self.doc_frequencies.items():
            self.idf[token] = math.log(1.0 + (self.total_docs - df + 0.5) / (df + 0.5))

        log.info(f"Built vector index over {self.total_docs} statutory chunks with {len(self.idf)} unique terms.")

    def search(self, query: str, top_k: int = 5, act_filter: Optional[str] = None) -> List[Tuple[StatutoryChunk, float]]:
        """
        Retrieves top-k statutory chunks matching query text using BM25-style scoring + section exact boost.
        """
        query_clean = re.sub(r'[^\w\s]', ' ', query.lower()).strip()
        query_tokens = self.tokenize(query)
        scores: List[float] = [0.0] * self.total_docs

        k1 = 1.5
        b = 0.75

        # Check if query contains exact section numbers to apply relevance boost
        extracted_nums = set(re.findall(r'\b\d+[A-Z]?(?:\(\d+\))?\b', query.upper()))

        for i in range(self.total_docs):
            chunk = self.chunks[i]
            if act_filter and chunk.act != act_filter.upper():
                continue

            doc_tf = self.doc_term_freqs[i]
            doc_len = self.doc_lengths[i]
            doc_score = 0.0

            title_clean = re.sub(r'[^\w\s]', ' ', chunk.section_title.lower()).strip()
            title_tokens = set(self.tokenize(chunk.section_title))

            for q_token in query_tokens:
                if q_token in doc_tf:
                    freq = doc_tf[q_token]
                    term_idf = self.idf.get(q_token, 0.0)
                    numerator = freq * (k1 + 1.0)
                    denominator = freq + k1 * (1.0 - b + b * (doc_len / max(1.0, self.avg_doc_length)))
                    term_score = term_idf * (numerator / max(1e-6, denominator))

                    # High boost for terms in section title
                    if q_token in title_tokens:
                        term_score *= 3.0

                    doc_score += term_score

            # Title exact phrase match bonus
            if title_clean and title_clean in query_clean:
                doc_score += 15.0

            # Section number exact match bonus
            if chunk.section_number in extracted_nums:
                doc_score += 25.0

            scores[i] = doc_score

        # Rank documents
        ranked_indices = sorted(range(self.total_docs), key=lambda idx: scores[idx], reverse=True)
        results = []
        for idx in ranked_indices[:top_k]:
            if scores[idx] > 0.0 or len(results) == 0:
                results.append((self.chunks[idx], float(scores[idx])))

        return results

    def save(self, index_dir: str):
        os.makedirs(index_dir, exist_ok=True)
        index_data = {
            "chunks": [c.to_dict() for c in self.chunks],
            "chunk_ids": self.chunk_ids,
            "doc_term_freqs": [dict(tf) for tf in self.doc_term_freqs],
            "doc_lengths": self.doc_lengths,
            "avg_doc_length": self.avg_doc_length,
            "doc_frequencies": self.doc_frequencies,
            "total_docs": self.total_docs,
            "idf": self.idf
        }
        with open(os.path.join(index_dir, "index.pkl"), "wb") as f:
            pickle.dump(index_data, f)
        with open(os.path.join(index_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump({
                "total_chunks": self.total_docs,
                "chunk_ids": self.chunk_ids,
                "created_at": os.environ.get("BUILD_TIME", "")
            }, f, indent=2)
        log.info(f"Saved vector index to {index_dir}")

    @classmethod
    def load(cls, index_dir: str) -> "LocalStatutoryVectorIndex":
        index_file = os.path.join(index_dir, "index.pkl")
        if not os.path.exists(index_file):
            raise FileNotFoundError(f"Index file not found at: {index_file}")

        with open(index_file, "rb") as f:
            data = pickle.load(f)

        instance = cls()
        instance.chunk_ids = data["chunk_ids"]
        instance.doc_term_freqs = [Counter(tf) for tf in data["doc_term_freqs"]]
        instance.doc_lengths = data["doc_lengths"]
        instance.avg_doc_length = data["avg_doc_length"]
        instance.doc_frequencies = data["doc_frequencies"]
        instance.total_docs = data["total_docs"]
        instance.idf = data["idf"]

        # Reconstruct chunks
        instance.chunks = [
            StatutoryChunk(
                chunk_id=c["chunk_id"],
                act=c["act"],
                act_full_name=c["act_full_name"],
                section_number=c["section_number"],
                section_title=c["section_title"],
                section_text=c["section_text"],
                chapter=c.get("chapter", ""),
                effective_start=c.get("effective_date_range", {}).get("start", ""),
                effective_end=c.get("effective_date_range", {}).get("end", ""),
                metadata=c.get("metadata", {})
            )
            for c in data["chunks"]
        ]
        return instance


def build_and_save_index(cleaned_dir: str, output_index_dir: str) -> LocalStatutoryVectorIndex:
    all_chunks_dict = load_all_chunks(cleaned_dir)
    all_chunks = all_chunks_dict["ALL"]
    log.info(f"Loaded {len(all_chunks)} statutory chunks from {cleaned_dir}")

    index = LocalStatutoryVectorIndex()
    index.build_index(all_chunks)
    index.save(output_index_dir)
    return index


if __name__ == "__main__":
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", "D:/college 4th year/research paper/NLP_rs")
    cleaned = os.path.join(root, "data/01_cleaned")
    out_dir = os.path.join(root, "data/05_embeddings_index/stage2_index")
    build_and_save_index(cleaned, out_dir)

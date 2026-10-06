"""
base_retriever.py — Phase 5: Retrieval Comparison

BaseRetriever ABC + four concrete implementations:
1. BM25Retriever — BM25 scoring over tokenized BNS corpus
2. TFIDFRetriever — TF-IDF cosine similarity retrieval
3. DenseRetriever — Dense embedding retrieval using any BaseEncoder
4. HybridRetriever — Weighted RRF fusion of sparse (BM25) + dense

Common interface: index(corpus), retrieve(query, top_k) → List[RetrievalResult]
"""

import logging
import math
import re
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

log = logging.getLogger("base_retriever")


@dataclass
class RetrievalResult:
    """Single retrieval result."""
    section_id: str          # BNS section number
    section_title: str
    section_text: str
    score: float
    rank: int
    method: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "section_title": self.section_title,
            "score": round(self.score, 4),
            "rank": self.rank,
            "method": self.method,
        }


class BaseRetriever(ABC):
    """Abstract base retriever."""

    name: str = "base"

    @abstractmethod
    def index(self, corpus: List[Dict[str, Any]]) -> None:
        """Index the BNS corpus for retrieval."""
        ...

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """Retrieve top-K candidates for a query."""
        ...

    def retrieve_batch(
        self, queries: List[str], top_k: int = 5
    ) -> List[List[RetrievalResult]]:
        """Retrieve for a batch of queries."""
        return [self.retrieve(q, top_k) for q in queries]


# ── Tokenization Utility ─────────────────────────────────────────────────

STOPWORDS = {
    "the", "is", "of", "and", "to", "a", "an", "in", "for", "on", "by",
    "with", "or", "as", "at", "be", "it", "that", "this", "was", "are",
    "which", "from", "has", "had", "have", "not", "but", "they", "he",
    "she", "his", "her", "its", "any", "all", "can", "will", "do", "did",
    "been", "were", "no", "if", "so", "who", "whom", "than", "such",
}


def tokenize(text: str) -> List[str]:
    """Simple whitespace tokenizer with stopword removal."""
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    return [t for t in clean.split() if t not in STOPWORDS and len(t) > 1]


# ── 1. BM25 Retriever ───────────────────────────────────────────────────

class BM25Retriever(BaseRetriever):
    """Okapi BM25 retrieval over the BNS corpus."""

    name = "bm25"

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: List[Dict[str, Any]] = []
        self.doc_tfs: List[Counter] = []
        self.doc_lengths: List[int] = []
        self.avg_dl: float = 0.0
        self.idf: Dict[str, float] = {}
        self.n_docs: int = 0

    def index(self, corpus: List[Dict[str, Any]]) -> None:
        self.corpus = corpus
        self.n_docs = len(corpus)
        doc_freq: Counter = Counter()
        self.doc_tfs = []
        self.doc_lengths = []

        for doc in corpus:
            text = f"{doc.get('section_number', '')} {doc.get('section_title', '')} {doc.get('section_text', '')}"
            tokens = tokenize(text)
            tf = Counter(tokens)
            self.doc_tfs.append(tf)
            self.doc_lengths.append(len(tokens))
            doc_freq.update(tf.keys())

        self.avg_dl = sum(self.doc_lengths) / max(1, self.n_docs)
        self.idf = {
            term: math.log(1.0 + (self.n_docs - df + 0.5) / (df + 0.5))
            for term, df in doc_freq.items()
        }
        log.info(f"BM25Retriever: indexed {self.n_docs} documents")

    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        q_tokens = tokenize(query)
        scores = []
        for i in range(self.n_docs):
            score = 0.0
            dl = self.doc_lengths[i]
            tf = self.doc_tfs[i]
            for qt in q_tokens:
                if qt not in self.idf:
                    continue
                freq = tf.get(qt, 0)
                if freq == 0:
                    continue
                num = freq * (self.k1 + 1.0)
                den = freq + self.k1 * (1.0 - self.b + self.b * (dl / max(1.0, self.avg_dl)))
                score += self.idf[qt] * (num / max(1e-6, den))
            scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for rank, (idx, score) in enumerate(scores[:top_k], 1):
            doc = self.corpus[idx]
            results.append(RetrievalResult(
                section_id=doc.get("section_number", doc.get("bns_section", "")),
                section_title=doc.get("section_title", doc.get("bns_title", "")),
                section_text=doc.get("section_text", ""),
                score=score,
                rank=rank,
                method="bm25",
            ))
        return results


# ── 2. TF-IDF Retriever ─────────────────────────────────────────────────

class TFIDFRetriever(BaseRetriever):
    """TF-IDF cosine similarity retriever."""

    name = "tfidf"

    def __init__(self):
        self.corpus: List[Dict[str, Any]] = []
        self.doc_vectors: List[Dict[str, float]] = []
        self.doc_norms: List[float] = []
        self.idf: Dict[str, float] = {}

    def index(self, corpus: List[Dict[str, Any]]) -> None:
        self.corpus = corpus
        n = len(corpus)
        doc_freq: Counter = Counter()
        doc_tfs: List[Counter] = []

        for doc in corpus:
            text = f"{doc.get('section_number', '')} {doc.get('section_title', '')} {doc.get('section_text', '')}"
            tokens = tokenize(text)
            tf = Counter(tokens)
            doc_tfs.append(tf)
            doc_freq.update(tf.keys())

        self.idf = {
            term: math.log(1.0 + n / (1.0 + df))
            for term, df in doc_freq.items()
        }

        self.doc_vectors = []
        self.doc_norms = []
        for tf in doc_tfs:
            vec = {}
            for term, count in tf.items():
                tfidf = (1.0 + math.log(count)) * self.idf.get(term, 0.0)
                if tfidf > 0:
                    vec[term] = tfidf
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self.doc_vectors.append(vec)
            self.doc_norms.append(norm)

        log.info(f"TFIDFRetriever: indexed {n} documents")

    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        tokens = tokenize(query)
        q_tf = Counter(tokens)
        q_vec = {
            t: (1.0 + math.log(c)) * self.idf.get(t, 0.0)
            for t, c in q_tf.items() if t in self.idf
        }
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        scores = []
        for i in range(len(self.corpus)):
            dot = sum(q_vec.get(t, 0.0) * self.doc_vectors[i].get(t, 0.0) for t in q_vec)
            sim = dot / (q_norm * self.doc_norms[i]) if (q_norm * self.doc_norms[i]) > 0 else 0.0
            scores.append((i, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for rank, (idx, score) in enumerate(scores[:top_k], 1):
            doc = self.corpus[idx]
            results.append(RetrievalResult(
                section_id=doc.get("section_number", doc.get("bns_section", "")),
                section_title=doc.get("section_title", doc.get("bns_title", "")),
                section_text=doc.get("section_text", ""),
                score=score,
                rank=rank,
                method="tfidf",
            ))
        return results


# ── 3. Dense Retriever ───────────────────────────────────────────────────

class DenseRetriever(BaseRetriever):
    """
    Dense embedding retrieval using any BaseEncoder.
    Indexes the corpus embeddings and retrieves via cosine similarity.
    """

    name = "dense"

    def __init__(self, encoder=None, encoder_name: str = "sentence_transformer"):
        self.encoder = encoder
        self.encoder_name = encoder_name
        self.corpus: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None

    def _ensure_encoder(self):
        if self.encoder is None:
            from src.models.encoder_adapters import get_encoder
            self.encoder = get_encoder(self.encoder_name)

    def index(self, corpus: List[Dict[str, Any]]) -> None:
        self._ensure_encoder()
        self.corpus = corpus
        texts = [
            f"{d.get('section_number', '')} {d.get('section_title', '')} {d.get('section_text', '')}"
            for d in corpus
        ]
        log.info(f"DenseRetriever: encoding {len(texts)} documents...")
        self.embeddings = self.encoder.encode(texts)
        # L2 normalize for cosine similarity via dot product
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.embeddings = self.embeddings / norms
        log.info(f"DenseRetriever: indexed {len(corpus)} documents, dim={self.embeddings.shape[1]}")

    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        self._ensure_encoder()
        q_emb = self.encoder.encode([query])
        q_norm = np.linalg.norm(q_emb, axis=1, keepdims=True)
        q_norm[q_norm == 0] = 1.0
        q_emb = q_emb / q_norm

        scores = np.dot(self.embeddings, q_emb.T).flatten()
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for rank, idx in enumerate(top_indices, 1):
            doc = self.corpus[idx]
            results.append(RetrievalResult(
                section_id=doc.get("section_number", doc.get("bns_section", "")),
                section_title=doc.get("section_title", doc.get("bns_title", "")),
                section_text=doc.get("section_text", ""),
                score=float(scores[idx]),
                rank=rank,
                method="dense",
                metadata={"encoder": self.encoder_name},
            ))
        return results


# ── 4. Hybrid Retriever ─────────────────────────────────────────────────

class HybridRetriever(BaseRetriever):
    """
    Reciprocal Rank Fusion (RRF) of BM25 + Dense retrieval.
    """

    name = "hybrid"

    def __init__(
        self,
        encoder=None,
        encoder_name: str = "sentence_transformer",
        rrf_k: int = 60,
        sparse_weight: float = 0.5,
    ):
        self.bm25 = BM25Retriever()
        self.dense = DenseRetriever(encoder=encoder, encoder_name=encoder_name)
        self.rrf_k = rrf_k
        self.sparse_weight = sparse_weight

    def index(self, corpus: List[Dict[str, Any]]) -> None:
        self.bm25.index(corpus)
        self.dense.index(corpus)

    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        pool_size = max(top_k * 4, 20)
        bm25_results = self.bm25.retrieve(query, top_k=pool_size)
        dense_results = self.dense.retrieve(query, top_k=pool_size)

        # RRF score aggregation
        rrf_scores: Dict[str, float] = defaultdict(float)
        result_map: Dict[str, RetrievalResult] = {}

        for rank, r in enumerate(bm25_results, 1):
            rrf_scores[r.section_id] += self.sparse_weight / (self.rrf_k + rank)
            result_map[r.section_id] = r

        for rank, r in enumerate(dense_results, 1):
            rrf_scores[r.section_id] += (1 - self.sparse_weight) / (self.rrf_k + rank)
            if r.section_id not in result_map:
                result_map[r.section_id] = r

        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        results = []
        for rank, sid in enumerate(sorted_ids[:top_k], 1):
            r = result_map[sid]
            results.append(RetrievalResult(
                section_id=r.section_id,
                section_title=r.section_title,
                section_text=r.section_text,
                score=rrf_scores[sid],
                rank=rank,
                method="hybrid_rrf",
            ))
        return results


# ── Factory ──────────────────────────────────────────────────────────────

RETRIEVER_REGISTRY: Dict[str, type] = {
    "bm25": BM25Retriever,
    "tfidf": TFIDFRetriever,
    "dense": DenseRetriever,
    "hybrid": HybridRetriever,
}


def get_retriever(name: str, **kwargs) -> BaseRetriever:
    """Instantiate a retriever by name."""
    if name not in RETRIEVER_REGISTRY:
        raise ValueError(
            f"Unknown retriever '{name}'. Available: {list(RETRIEVER_REGISTRY.keys())}"
        )
    return RETRIEVER_REGISTRY[name](**kwargs)

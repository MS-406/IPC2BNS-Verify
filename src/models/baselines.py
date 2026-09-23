"""
baselines.py — Phase 3: Baseline Models

Three deterministic baseline models for IPC→BNS section mapping:
1. ExactMatchBaseline — Direct concordance lookup by IPC section number.
2. TFIDFBaseline — TF-IDF vectorisation of section text + cosine similarity.
3. BM25Baseline — BM25 scoring over the BNS corpus.

All models follow a common BaselineModel ABC with fit/predict interface.
"""

import logging
import math
import re
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

log = logging.getLogger("baselines")


@dataclass
class Prediction:
    """Single prediction output."""
    predicted_bns: str
    confidence: float
    rank: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaselineModel(ABC):
    """Abstract base for all baseline models."""

    name: str = "base"

    @abstractmethod
    def fit(self, train_data: List[Dict[str, Any]]) -> None:
        """Fit on training data."""
        ...

    @abstractmethod
    def predict(self, input_text: str, top_k: int = 5) -> List[Prediction]:
        """Return top-K ranked predictions."""
        ...

    def predict_batch(
        self, inputs: List[Dict[str, Any]], top_k: int = 5
    ) -> List[List[Prediction]]:
        """Predict for a batch of samples."""
        return [self.predict(s["input_text"], top_k) for s in inputs]

    def evaluate(
        self, test_data: List[Dict[str, Any]], top_k: int = 5
    ) -> Dict[str, Any]:
        """Evaluate baseline on test data, returning accuracy and recall@K."""
        correct_at = {k: 0 for k in range(1, top_k + 1)}
        total = len(test_data)

        for sample in test_data:
            preds = self.predict(sample["input_text"], top_k=top_k)
            predicted_sections = [p.predicted_bns for p in preds]
            true_bns = sample["bns_section"]

            for k in range(1, top_k + 1):
                if true_bns in predicted_sections[:k]:
                    correct_at[k] += 1

        results = {
            "model": self.name,
            "total_samples": total,
            "accuracy": round(correct_at[1] / max(1, total), 4),
        }
        for k in range(1, top_k + 1):
            results[f"recall_at_{k}"] = round(correct_at[k] / max(1, total), 4)

        return results


# ── 1. Exact Match Baseline ──────────────────────────────────────────────

class ExactMatchBaseline(BaselineModel):
    """
    Direct lookup: extracts IPC section number from the query,
    then maps it through the concordance table.
    """

    name = "exact_match"

    def __init__(self):
        self.ipc_to_bns: Dict[str, List[str]] = defaultdict(list)

    def fit(self, train_data: List[Dict[str, Any]]) -> None:
        """Build IPC→BNS mapping from training concordance data."""
        for sample in train_data:
            ipc = sample.get("ipc_section", "").strip()
            bns = sample.get("bns_section", "").strip()
            if ipc and bns:
                if bns not in self.ipc_to_bns[ipc]:
                    self.ipc_to_bns[ipc].append(bns)
        log.info(
            f"ExactMatch: indexed {len(self.ipc_to_bns)} IPC→BNS mappings"
        )

    def _extract_section_numbers(self, text: str) -> List[str]:
        """Extract potential IPC section numbers from input text."""
        patterns = [
            r"(?:IPC|Indian Penal Code)\s*(?:Section|§|sec\.?)\s*(\d{1,4}[A-Za-z]?)",
            r"Section\s+(\d{1,4}[A-Za-z]?)\s+(?:of|IPC)",
            r"\b(\d{1,4}[A-Za-z]?)\b",
        ]
        found = []
        for pat in patterns:
            matches = re.findall(pat, text, re.IGNORECASE)
            found.extend(matches)
        # Deduplicate, preserving order
        seen = set()
        deduped = []
        for s in found:
            s_norm = s.strip().upper()
            if s_norm and s_norm not in seen:
                seen.add(s_norm)
                deduped.append(s_norm)
        return deduped

    def predict(self, input_text: str, top_k: int = 5) -> List[Prediction]:
        extracted = self._extract_section_numbers(input_text)
        predictions = []
        seen = set()
        for ipc_sec in extracted:
            for bns_sec in self.ipc_to_bns.get(ipc_sec, []):
                if bns_sec not in seen:
                    seen.add(bns_sec)
                    predictions.append(
                        Prediction(
                            predicted_bns=bns_sec,
                            confidence=1.0,
                            rank=len(predictions) + 1,
                            metadata={"matched_ipc": ipc_sec, "method": "exact"},
                        )
                    )
        # Also try lowercase match
        for ipc_sec in extracted:
            for bns_sec in self.ipc_to_bns.get(ipc_sec.lower(), []):
                if bns_sec not in seen:
                    seen.add(bns_sec)
                    predictions.append(
                        Prediction(
                            predicted_bns=bns_sec,
                            confidence=0.9,
                            rank=len(predictions) + 1,
                            metadata={"matched_ipc": ipc_sec, "method": "exact_lower"},
                        )
                    )
        return predictions[:top_k]


# ── 2. TF-IDF Baseline ──────────────────────────────────────────────────

class TFIDFBaseline(BaselineModel):
    """
    TF-IDF vectorisation of section texts + cosine similarity retrieval.
    """

    name = "tfidf"

    STOPWORDS = {
        "the", "is", "of", "and", "to", "a", "an", "in", "for", "on", "by",
        "with", "or", "as", "at", "be", "it", "that", "this", "was", "are",
        "which", "from", "has", "had", "have", "not", "but", "they", "he",
        "she", "his", "her", "its", "any", "all", "can", "will", "do", "did",
        "been", "were", "no", "if", "so", "who", "whom", "than", "such",
    }

    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.doc_vectors: List[Dict[str, float]] = []
        self.idf: Dict[str, float] = {}
        self.doc_norms: List[float] = []

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        clean = re.sub(r"[^\w\s]", " ", text.lower())
        return [t for t in clean.split() if len(t) > 1]

    def fit(self, train_data: List[Dict[str, Any]]) -> None:
        """Build TF-IDF vectors from training corpus."""
        self.documents = train_data
        n_docs = len(train_data)

        # Term frequencies per document
        doc_tfs: List[Counter] = []
        doc_freq: Counter = Counter()

        for sample in train_data:
            tokens = [t for t in self._tokenize(sample["input_text"])
                      if t not in self.STOPWORDS]
            tf = Counter(tokens)
            doc_tfs.append(tf)
            doc_freq.update(tf.keys())

        # IDF
        self.idf = {
            term: math.log(1.0 + n_docs / (1.0 + df))
            for term, df in doc_freq.items()
        }

        # TF-IDF vectors (sparse dict representation)
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

        log.info(
            f"TF-IDF: built {len(self.doc_vectors)} document vectors, "
            f"{len(self.idf)} unique terms"
        )

    def _cosine_sim(
        self, query_vec: Dict[str, float], query_norm: float, doc_idx: int
    ) -> float:
        """Compute cosine similarity between query and a document."""
        doc_vec = self.doc_vectors[doc_idx]
        doc_norm = self.doc_norms[doc_idx]
        dot = sum(query_vec.get(t, 0.0) * doc_vec.get(t, 0.0) for t in query_vec)
        return dot / (query_norm * doc_norm) if (query_norm * doc_norm) > 0 else 0.0

    def predict(self, input_text: str, top_k: int = 5) -> List[Prediction]:
        tokens = [t for t in self._tokenize(input_text) if t not in self.STOPWORDS]
        q_tf = Counter(tokens)
        q_vec = {
            term: (1.0 + math.log(count)) * self.idf.get(term, 0.0)
            for term, count in q_tf.items()
            if term in self.idf
        }
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        scores = []
        for i in range(len(self.documents)):
            sim = self._cosine_sim(q_vec, q_norm, i)
            scores.append((i, sim))

        scores.sort(key=lambda x: x[1], reverse=True)

        # Deduplicate by bns_section, keeping highest score
        seen = set()
        predictions = []
        for idx, score in scores:
            bns = self.documents[idx]["bns_section"]
            if bns not in seen:
                seen.add(bns)
                predictions.append(
                    Prediction(
                        predicted_bns=bns,
                        confidence=round(score, 4),
                        rank=len(predictions) + 1,
                        metadata={"doc_idx": idx, "method": "tfidf"},
                    )
                )
                if len(predictions) >= top_k:
                    break

        return predictions


# ── 3. BM25 Baseline ────────────────────────────────────────────────────

class BM25Baseline(BaselineModel):
    """
    BM25 scoring over the BNS-labeled corpus.
    Pure-Python implementation (no external rank-bm25 dependency for
    portability, though it mirrors the Okapi BM25 formula).
    """

    name = "bm25"

    STOPWORDS = TFIDFBaseline.STOPWORDS

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[Dict[str, Any]] = []
        self.doc_tfs: List[Counter] = []
        self.doc_lengths: List[int] = []
        self.avg_dl: float = 0.0
        self.idf: Dict[str, float] = {}
        self.n_docs: int = 0

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        clean = re.sub(r"[^\w\s]", " ", text.lower())
        return [t for t in clean.split() if len(t) > 1]

    def fit(self, train_data: List[Dict[str, Any]]) -> None:
        self.documents = train_data
        self.n_docs = len(train_data)

        doc_freq: Counter = Counter()
        self.doc_tfs = []
        self.doc_lengths = []

        for sample in train_data:
            tokens = [t for t in self._tokenize(sample["input_text"])
                      if t not in self.STOPWORDS]
            tf = Counter(tokens)
            self.doc_tfs.append(tf)
            self.doc_lengths.append(len(tokens))
            doc_freq.update(tf.keys())

        self.avg_dl = sum(self.doc_lengths) / max(1, self.n_docs)

        self.idf = {}
        for term, df in doc_freq.items():
            self.idf[term] = math.log(
                1.0 + (self.n_docs - df + 0.5) / (df + 0.5)
            )

        log.info(
            f"BM25: indexed {self.n_docs} documents, "
            f"{len(self.idf)} terms, avg_dl={self.avg_dl:.1f}"
        )

    def _score_document(self, query_tokens: List[str], doc_idx: int) -> float:
        tf = self.doc_tfs[doc_idx]
        dl = self.doc_lengths[doc_idx]
        score = 0.0
        for qt in query_tokens:
            if qt not in self.idf:
                continue
            freq = tf.get(qt, 0)
            if freq == 0:
                continue
            numerator = freq * (self.k1 + 1.0)
            denominator = freq + self.k1 * (
                1.0 - self.b + self.b * (dl / max(1.0, self.avg_dl))
            )
            score += self.idf[qt] * (numerator / max(1e-6, denominator))
        return score

    def predict(self, input_text: str, top_k: int = 5) -> List[Prediction]:
        tokens = [t for t in self._tokenize(input_text) if t not in self.STOPWORDS]

        scores = []
        for i in range(self.n_docs):
            s = self._score_document(tokens, i)
            scores.append((i, s))

        scores.sort(key=lambda x: x[1], reverse=True)

        seen = set()
        predictions = []
        for idx, score in scores:
            bns = self.documents[idx]["bns_section"]
            if bns not in seen:
                seen.add(bns)
                predictions.append(
                    Prediction(
                        predicted_bns=bns,
                        confidence=round(score, 4),
                        rank=len(predictions) + 1,
                        metadata={"doc_idx": idx, "method": "bm25"},
                    )
                )
                if len(predictions) >= top_k:
                    break

        return predictions


# ── Factory ──────────────────────────────────────────────────────────────

BASELINE_REGISTRY: Dict[str, type] = {
    "exact_match": ExactMatchBaseline,
    "tfidf": TFIDFBaseline,
    "bm25": BM25Baseline,
}


def get_baseline(name: str, **kwargs) -> BaselineModel:
    """Instantiate a baseline model by name."""
    if name not in BASELINE_REGISTRY:
        raise ValueError(
            f"Unknown baseline '{name}'. Available: {list(BASELINE_REGISTRY.keys())}"
        )
    return BASELINE_REGISTRY[name](**kwargs)

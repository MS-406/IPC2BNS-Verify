"""
rag_pipeline.py — Phases 7-9: Modular RAG System

Pluggable RAG pipeline with three stages:
1. RAGRetriever — Wraps any BaseRetriever to fetch context documents
2. RAGReranker — Cross-encoder reranking of retrieved candidates
3. RAGGenerator — Template-based answer generation from query + context
4. RAGPipeline — Orchestrates retriever → reranker → generator

All components accept ExperimentConfig for configuration-driven selection.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

log = logging.getLogger("rag_pipeline")


@dataclass
class RAGResult:
    """Complete RAG pipeline result."""
    query: str
    predicted_bns: str
    confidence: float
    retrieved_contexts: List[Dict[str, Any]]
    reranked_contexts: List[Dict[str, Any]]
    generated_answer: str
    latency_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "predicted_bns": self.predicted_bns,
            "confidence": self.confidence,
            "num_retrieved": len(self.retrieved_contexts),
            "num_reranked": len(self.reranked_contexts),
            "generated_answer": self.generated_answer,
            "latency_ms": round(self.latency_ms, 2),
        }


# ── 1. RAG Retriever ─────────────────────────────────────────────────────

class RAGRetriever:
    """Wraps any BaseRetriever to produce context documents for RAG."""

    def __init__(
        self,
        retriever=None,
        retriever_name: str = "bm25",
        corpus: Optional[List[Dict[str, Any]]] = None,
        **retriever_kwargs,
    ):
        if retriever is not None:
            self.retriever = retriever
        else:
            from src.retrieval.base_retriever import get_retriever
            self.retriever = get_retriever(retriever_name, **retriever_kwargs)

        self.corpus = corpus
        self._indexed = False

    def index(self, corpus: Optional[List[Dict[str, Any]]] = None):
        """Index the corpus for retrieval."""
        if corpus is not None:
            self.corpus = corpus
        if self.corpus is None:
            from src.utils.config import BNS_SECTIONS_PATH
            from src.data.dataset_validator import load_jsonl
            self.corpus = load_jsonl(str(BNS_SECTIONS_PATH))
        self.retriever.index(self.corpus)
        self._indexed = True
        log.info(f"RAGRetriever indexed {len(self.corpus)} documents")

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve context documents."""
        if not self._indexed:
            self.index()
        results = self.retriever.retrieve(query, top_k=top_k)
        return [
            {
                "section_id": r.section_id,
                "section_title": r.section_title,
                "section_text": r.section_text,
                "score": r.score,
                "rank": r.rank,
            }
            for r in results
        ]


# ── 2. RAG Reranker ──────────────────────────────────────────────────────

class RAGReranker:
    """
    Cross-encoder reranker for retrieved candidates.
    Uses a cross-encoder model to score (query, document) pairs and re-order.
    Falls back to identity (no reranking) if model is unavailable.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        enabled: bool = True,
    ):
        self.model_name = model_name
        self.enabled = enabled
        self._model = None

    def _load_model(self):
        if self._model is not None or not self.enabled:
            return
        try:
            from sentence_transformers import CrossEncoder
            log.info(f"Loading cross-encoder reranker: {self.model_name}")
            self._model = CrossEncoder(self.model_name)
        except (ImportError, Exception) as e:
            log.warning(f"Cross-encoder not available ({e}). Reranking disabled.")
            self.enabled = False

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Rerank candidates by cross-encoder score."""
        if not self.enabled or not candidates:
            return candidates[:top_k]

        self._load_model()
        if self._model is None:
            return candidates[:top_k]

        # Prepare pairs for cross-encoder
        pairs = [
            (query, f"{c.get('section_title', '')}. {c.get('section_text', '')}")
            for c in candidates
        ]

        scores = self._model.predict(pairs)

        # Attach scores and sort
        for c, score in zip(candidates, scores):
            c["rerank_score"] = float(score)

        reranked = sorted(candidates, key=lambda x: x.get("rerank_score", 0), reverse=True)

        # Update ranks
        for i, c in enumerate(reranked, 1):
            c["rank"] = i

        return reranked[:top_k]


# ── 3. RAG Generator ─────────────────────────────────────────────────────

class RAGGenerator:
    """
    Template-based answer generator from query + retrieved context.

    Uses deterministic template formatting to produce an answer that cites
    the relevant BNS section. This is reproducible, free, and suitable
    for benchmarking the retrieval quality independently of LLM variance.
    """

    def __init__(self):
        pass

    def generate(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate a grounded answer from query and retrieved contexts.

        Returns dict with:
        - answer: str
        - predicted_bns: str (top BNS section)
        - confidence: float
        """
        if not contexts:
            return {
                "answer": "No relevant BNS section found for this query.",
                "predicted_bns": "",
                "confidence": 0.0,
            }

        top = contexts[0]
        sec_id = top.get("section_id", "")
        sec_title = top.get("section_title", "")
        sec_text = top.get("section_text", "")
        score = top.get("rerank_score", top.get("score", 0.0))

        answer_parts = [
            f"Based on the retrieved statutory context, this matter corresponds to "
            f"BNS Section {sec_id} ({sec_title}).",
        ]

        if sec_text:
            # Truncate long text
            preview = sec_text[:300] + "..." if len(sec_text) > 300 else sec_text
            answer_parts.append(f"Provision: {preview}")

        if len(contexts) > 1:
            alt = contexts[1]
            answer_parts.append(
                f"Alternative: BNS Section {alt.get('section_id', '')} "
                f"({alt.get('section_title', '')})."
            )

        return {
            "answer": " ".join(answer_parts),
            "predicted_bns": sec_id,
            "confidence": min(1.0, max(0.0, score)),
        }


# ── 4. RAG Pipeline (Orchestrator) ───────────────────────────────────────

class RAGPipeline:
    """
    Full RAG pipeline: retriever → reranker → generator.

    Configuration-driven: can be constructed from an ExperimentConfig.
    """

    def __init__(
        self,
        retriever: Optional[RAGRetriever] = None,
        reranker: Optional[RAGReranker] = None,
        generator: Optional[RAGGenerator] = None,
        top_k: int = 5,
    ):
        self.retriever = retriever or RAGRetriever()
        self.reranker = reranker or RAGReranker(enabled=False)
        self.generator = generator or RAGGenerator()
        self.top_k = top_k

    @classmethod
    def from_config(cls, config) -> "RAGPipeline":
        """
        Build a RAGPipeline from an ExperimentConfig.
        """
        retriever = RAGRetriever(retriever_name=config.retriever)
        reranker = RAGReranker(enabled=(config.reranker != "none"))
        generator = RAGGenerator()
        return cls(
            retriever=retriever,
            reranker=reranker,
            generator=generator,
            top_k=config.top_k,
        )

    def index(self, corpus: Optional[List[Dict[str, Any]]] = None):
        """Index the corpus."""
        self.retriever.index(corpus)

    def run(self, query: str, top_k: Optional[int] = None) -> RAGResult:
        """Execute the full RAG pipeline on a single query."""
        k = top_k or self.top_k
        start = time.time()

        # Step 1: Retrieve
        retrieved = self.retriever.retrieve(query, top_k=k * 2)

        # Step 2: Rerank
        reranked = self.reranker.rerank(query, retrieved, top_k=k)

        # Step 3: Generate
        gen_result = self.generator.generate(query, reranked)

        latency = (time.time() - start) * 1000.0

        return RAGResult(
            query=query,
            predicted_bns=gen_result["predicted_bns"],
            confidence=gen_result["confidence"],
            retrieved_contexts=retrieved,
            reranked_contexts=reranked,
            generated_answer=gen_result["answer"],
            latency_ms=latency,
        )

    def run_batch(
        self,
        samples: List[Dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> List[RAGResult]:
        """Run the pipeline on a batch of samples."""
        return [self.run(s["input_text"], top_k=top_k) for s in samples]

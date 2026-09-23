"""
production_rag.py — Production-Ready RAG Pipeline for IPC <-> BNS Mapping

100% LOCAL — No external LLM APIs. No API keys. No internet calls at inference.

This pipeline uses:
1. Hybrid Retriever (BM25 sparse + Sentence-Transformer dense, both local)
2. IPC<->BNS Concordance Table (direct lookup from your ground truth CSV)
3. Deterministic Rule-Based Generator (structured answer from retrieved context)

All intelligence comes from YOUR data + YOUR local models. Nothing external.

Usage:
    python production_rag.py "What is the BNS equivalent of IPC 302 (Murder)?"
    python production_rag.py --interactive
    python production_rag.py --evaluate
"""

import json
import logging
import os
import re
import sys
import time
import csv
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

# Force UTF-8 stdout on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
log = logging.getLogger("production_rag")

# ── Project paths ────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
CLEANED_DIR = DATA_DIR / "01_cleaned"
GROUND_TRUTH_DIR = DATA_DIR / "02_ground_truth"
BNS_SECTIONS_PATH = CLEANED_DIR / "bns_sections.jsonl"
IPC_SECTIONS_PATH = CLEANED_DIR / "ipc_sections.jsonl"
CONCORDANCE_PATH = GROUND_TRUTH_DIR / "concordance_v1.csv"


# ══════════════════════════════════════════════════════════════════════════
# 1. DATA LOADING
# ══════════════════════════════════════════════════════════════════════════

def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load a JSONL file into a list of dicts."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_concordance(path: str = None) -> Dict[str, Dict[str, str]]:
    """
    Load the IPC<->BNS concordance table.
    Returns dict keyed by IPC section number -> mapping details.
    """
    path = path or str(CONCORDANCE_PATH)
    ipc_to_bns = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ipc_sec = row.get("ipc_section", "").strip()
            if ipc_sec:
                ipc_to_bns[ipc_sec] = {
                    "ipc_section": ipc_sec,
                    "ipc_title": row.get("ipc_title", ""),
                    "bns_section": row.get("bns_section", "").strip(),
                    "bns_title": row.get("bns_title", ""),
                    "relationship_type": row.get("relationship_type", ""),
                    "notes": row.get("notes", ""),
                }
    return ipc_to_bns


def build_reverse_concordance(concordance: Dict[str, Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    """Build BNS -> IPC reverse lookup."""
    bns_to_ipc = defaultdict(list)
    for ipc_sec, mapping in concordance.items():
        bns_sec = mapping["bns_section"]
        if bns_sec and bns_sec != "-":
            bns_to_ipc[bns_sec].append(mapping)
    return dict(bns_to_ipc)


# ══════════════════════════════════════════════════════════════════════════
# 2. HYBRID RETRIEVER (BM25 + Dense, fully local)
# ══════════════════════════════════════════════════════════════════════════

STOPWORDS = {
    "the", "is", "of", "and", "to", "a", "an", "in", "for", "on", "by",
    "with", "or", "as", "at", "be", "it", "that", "this", "was", "are",
    "which", "from", "has", "had", "have", "not", "but", "they", "he",
    "she", "his", "her", "its", "any", "all", "can", "will", "do", "did",
    "been", "were", "no", "if", "so", "who", "whom", "than", "such",
    "section", "shall", "under", "upon",
}


def tokenize(text: str) -> List[str]:
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    return [t for t in clean.split() if t not in STOPWORDS and len(t) > 1]


@dataclass
class RetrievedDoc:
    """A single retrieved BNS section."""
    section_number: str
    section_title: str
    section_text: str
    chapter: str
    relationship_type: str
    mapped_from_ipc: str
    notes: str
    score: float
    rank: int
    method: str


class HybridRetriever:
    """
    Hybrid Retriever combining:
    - BM25 sparse retrieval (keyword matching)
    - Dense embedding retrieval (semantic similarity via local Sentence-Transformers)
    - Reciprocal Rank Fusion (RRF) to merge both ranked lists
    - Direct IPC->BNS concordance lookup for exact section queries

    All models run locally. No API calls.
    """

    def __init__(
        self,
        dense_model: str = "all-MiniLM-L6-v2",
        bm25_k1: float = 1.5,
        bm25_b: float = 0.75,
        rrf_k: int = 60,
        sparse_weight: float = 0.4,
    ):
        self.dense_model_name = dense_model
        self.bm25_k1 = bm25_k1
        self.bm25_b = bm25_b
        self.rrf_k = rrf_k
        self.sparse_weight = sparse_weight

        self.corpus: List[Dict[str, Any]] = []
        self.concordance: Dict[str, Dict[str, str]] = {}
        self.reverse_concordance: Dict[str, List[Dict[str, str]]] = {}
        self._dense_model = None
        self._dense_embeddings: Optional[np.ndarray] = None

        # BM25 state
        self._doc_tfs: List[Counter] = []
        self._doc_lengths: List[int] = []
        self._avg_dl: float = 0.0
        self._idf: Dict[str, float] = {}

    def _load_dense_model(self):
        if self._dense_model is not None:
            return
        from sentence_transformers import SentenceTransformer
        log.info(f"Loading local SentenceTransformer: {self.dense_model_name}")
        self._dense_model = SentenceTransformer(self.dense_model_name)

    def _build_doc_text(self, doc: Dict[str, Any]) -> str:
        parts = [
            f"BNS Section {doc.get('section_number', '')}",
            doc.get("section_title", ""),
            doc.get("section_text", ""),
            doc.get("chapter", ""),
        ]
        if doc.get("mapped_from_ipc"):
            parts.append(f"IPC Section {doc['mapped_from_ipc']}")
        if doc.get("notes"):
            parts.append(doc["notes"])
        return " ".join(p for p in parts if p)

    def index(
        self,
        corpus: Optional[List[Dict[str, Any]]] = None,
        concordance: Optional[Dict[str, Dict[str, str]]] = None,
    ):
        """Index the BNS corpus. All processing is local."""
        self.corpus = corpus or load_jsonl(str(BNS_SECTIONS_PATH))
        self.concordance = concordance or load_concordance()
        self.reverse_concordance = build_reverse_concordance(self.concordance)

        n = len(self.corpus)
        doc_freq: Counter = Counter()

        # BM25 indexing
        self._doc_tfs = []
        self._doc_lengths = []
        for doc in self.corpus:
            text = self._build_doc_text(doc)
            tokens = tokenize(text)
            tf = Counter(tokens)
            self._doc_tfs.append(tf)
            self._doc_lengths.append(len(tokens))
            doc_freq.update(tf.keys())

        self._avg_dl = sum(self._doc_lengths) / max(1, n)
        self._idf = {
            term: math.log(1.0 + (n - df + 0.5) / (df + 0.5))
            for term, df in doc_freq.items()
        }

        # Dense indexing (local model)
        self._load_dense_model()
        texts = [self._build_doc_text(doc) for doc in self.corpus]
        log.info(f"Encoding {n} BNS sections with local model...")
        self._dense_embeddings = self._dense_model.encode(
            texts, show_progress_bar=False, convert_to_numpy=True
        )
        norms = np.linalg.norm(self._dense_embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._dense_embeddings = self._dense_embeddings / norms

        log.info(f"Indexed {n} BNS sections (dim={self._dense_embeddings.shape[1]})")

    def _bm25_scores(self, query: str) -> List[Tuple[int, float]]:
        q_tokens = tokenize(query)
        scores = []
        for i in range(len(self.corpus)):
            score = 0.0
            dl = self._doc_lengths[i]
            tf = self._doc_tfs[i]
            for qt in q_tokens:
                if qt not in self._idf:
                    continue
                freq = tf.get(qt, 0)
                if freq == 0:
                    continue
                num = freq * (self.bm25_k1 + 1.0)
                den = freq + self.bm25_k1 * (1.0 - self.bm25_b + self.bm25_b * (dl / max(1.0, self._avg_dl)))
                score += self._idf[qt] * (num / max(1e-6, den))
            scores.append((i, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _dense_scores(self, query: str) -> List[Tuple[int, float]]:
        q_emb = self._dense_model.encode([query], convert_to_numpy=True)
        q_norm = np.linalg.norm(q_emb, axis=1, keepdims=True)
        q_norm[q_norm == 0] = 1.0
        q_emb = q_emb / q_norm
        sims = np.dot(self._dense_embeddings, q_emb.T).flatten()
        ranked = np.argsort(sims)[::-1]
        return [(int(idx), float(sims[idx])) for idx in ranked]

    def _extract_ipc_section(self, query: str) -> Optional[str]:
        """Extract explicit IPC section number from query text."""
        patterns = [
            r"ipc\s*(?:section\s*)?(\d+[a-zA-Z]?)",
            r"section\s+(\d+[a-zA-Z]?)\s+(?:of\s+)?(?:the\s+)?ipc",
            r"(?:^|\s)(\d{2,3}[a-zA-Z]?)\s+ipc",
        ]
        for pat in patterns:
            m = re.search(pat, query.lower())
            if m:
                return m.group(1).upper() if m.group(1)[-1].isalpha() else m.group(1)
        return None

    def _extract_bns_section(self, query: str) -> Optional[str]:
        """Extract explicit BNS section number from query text."""
        patterns = [
            r"bns\s*(?:section\s*)?(\d+[a-zA-Z]?)",
            r"section\s+(\d+[a-zA-Z]?)\s+(?:of\s+)?(?:the\s+)?bns",
        ]
        for pat in patterns:
            m = re.search(pat, query.lower())
            if m:
                return m.group(1).upper() if m.group(1)[-1].isalpha() else m.group(1)
        return None

    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievedDoc]:
        """
        Retrieve top-K BNS sections using hybrid RRF.
        If query mentions an IPC section, the concordance mapping is injected at rank 1.
        """
        pool_size = max(top_k * 4, 30)

        bm25_ranked = self._bm25_scores(query)[:pool_size]
        dense_ranked = self._dense_scores(query)[:pool_size]

        # RRF Fusion
        rrf_scores: Dict[int, float] = defaultdict(float)
        for rank, (idx, _) in enumerate(bm25_ranked, 1):
            rrf_scores[idx] += self.sparse_weight / (self.rrf_k + rank)
        for rank, (idx, _) in enumerate(dense_ranked, 1):
            rrf_scores[idx] += (1.0 - self.sparse_weight) / (self.rrf_k + rank)

        sorted_indices = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        results = []
        seen_sections = set()
        for rank, idx in enumerate(sorted_indices[:top_k], 1):
            doc = self.corpus[idx]
            sec_num = doc.get("section_number", "")
            seen_sections.add(sec_num)
            results.append(RetrievedDoc(
                section_number=sec_num,
                section_title=doc.get("section_title", ""),
                section_text=doc.get("section_text", ""),
                chapter=doc.get("chapter", ""),
                relationship_type=doc.get("relationship_type", ""),
                mapped_from_ipc=doc.get("mapped_from_ipc", ""),
                notes=doc.get("notes", ""),
                score=rrf_scores[idx],
                rank=rank,
                method="hybrid_rrf",
            ))

        # Exact IPC lookup injection
        ipc_sec = self._extract_ipc_section(query)
        if ipc_sec and ipc_sec in self.concordance:
            mapping = self.concordance[ipc_sec]
            target_bns = mapping["bns_section"]
            if target_bns and target_bns not in seen_sections:
                for doc in self.corpus:
                    if doc.get("section_number") == target_bns:
                        injected = RetrievedDoc(
                            section_number=target_bns,
                            section_title=doc.get("section_title", mapping.get("bns_title", "")),
                            section_text=doc.get("section_text", ""),
                            chapter=doc.get("chapter", ""),
                            relationship_type=mapping.get("relationship_type", ""),
                            mapped_from_ipc=ipc_sec,
                            notes=mapping.get("notes", ""),
                            score=999.0,
                            rank=0,
                            method="concordance_lookup",
                        )
                        results.insert(0, injected)
                        break
            elif target_bns and target_bns in seen_sections:
                for i, r in enumerate(results):
                    if r.section_number == target_bns:
                        boosted = results.pop(i)
                        boosted.score = 999.0
                        boosted.method = "hybrid_rrf+concordance_boost"
                        results.insert(0, boosted)
                        break

        for i, r in enumerate(results, 1):
            r.rank = i

        return results[:top_k]


# ══════════════════════════════════════════════════════════════════════════
# 3. LOCAL ANSWER GENERATOR (No LLM, purely rule-based)
# ══════════════════════════════════════════════════════════════════════════

class LocalAnswerGenerator:
    """
    Generates structured, grounded answers using ONLY:
    - Retrieved BNS sections (from the local Hybrid Retriever)
    - The IPC<->BNS concordance table (your ground truth CSV)
    - Rule-based logic (no LLM, no API, no external model)

    The generator uses a multi-strategy approach:
    1. If an IPC section is in the query -> direct concordance lookup
    2. If a BNS section is in the query -> reverse concordance lookup
    3. Otherwise -> use top retrieval result with confidence scoring
    """

    def __init__(self, concordance: Dict, reverse_concordance: Dict):
        self.concordance = concordance
        self.reverse_concordance = reverse_concordance

    def _compute_confidence(self, doc: RetrievedDoc, method: str) -> str:
        """Determine confidence level based on retrieval method and score."""
        if method == "concordance_lookup":
            return "HIGH"
        if method == "hybrid_rrf+concordance_boost":
            return "HIGH"
        if doc.score > 0.015:
            return "MEDIUM"
        return "LOW"

    def _build_ipc_answer(
        self, query: str, ipc_section: str, docs: List[RetrievedDoc]
    ) -> Dict[str, Any]:
        """Answer for queries that mention a specific IPC section."""
        mapping = self.concordance.get(ipc_section)

        if mapping:
            bns_sec = mapping["bns_section"]
            bns_title = mapping["bns_title"]
            rel = mapping["relationship_type"]
            notes = mapping["notes"]

            # Find full text from retrieved docs
            full_text = ""
            chapter = ""
            for d in docs:
                if d.section_number == bns_sec:
                    full_text = d.section_text
                    chapter = d.chapter
                    break

            # Build reasoning
            reasoning_parts = [
                f"IPC Section {ipc_section} ({mapping['ipc_title']}) has been "
                f"{'directly ' if rel == 'renumbered' else ''}{rel} "
                f"{'as' if rel != 'repealed' else 'and'} "
                f"BNS Section {bns_sec} ({bns_title}) under the Bharatiya Nyaya Sanhita, 2023."
            ]

            if notes:
                reasoning_parts.append(f"Key change: {notes}")

            if rel == "merged":
                reasoning_parts.append(
                    "Multiple IPC sections were consolidated into this single BNS section."
                )
            elif rel == "split":
                reasoning_parts.append(
                    "The original IPC section was split into multiple BNS sections. "
                    "Check alternative sections for related provisions."
                )
            elif rel == "modified":
                reasoning_parts.append(
                    "The substance of the provision has been modified in BNS "
                    "with new provisions or expanded scope."
                )

            # Find alternatives
            alternatives = []
            for d in docs[1:4]:
                if d.section_number != bns_sec:
                    alternatives.append({
                        "section": d.section_number,
                        "title": d.section_title,
                        "relevance_score": round(d.score, 4),
                    })

            return {
                "status": "success",
                "source": "concordance_lookup",
                "query": query,
                "query_type": "ipc_to_bns",
                "ipc_section": ipc_section,
                "ipc_title": mapping["ipc_title"],
                "predicted_bns_section": bns_sec,
                "bns_section_title": bns_title,
                "bns_section_text": full_text,
                "chapter": chapter,
                "relationship_type": rel,
                "reasoning": " ".join(reasoning_parts),
                "key_changes": notes or "No significant changes noted.",
                "confidence": "HIGH",
                "alternative_sections": alternatives,
            }
        else:
            # IPC section not in concordance -> use retrieval
            return self._build_retrieval_answer(query, docs, ipc_section=ipc_section)

    def _build_bns_answer(
        self, query: str, bns_section: str, docs: List[RetrievedDoc]
    ) -> Dict[str, Any]:
        """Answer for queries that mention a specific BNS section."""
        ipc_mappings = self.reverse_concordance.get(bns_section, [])

        # Find doc in retrieved results
        target_doc = None
        for d in docs:
            if d.section_number == bns_section:
                target_doc = d
                break

        if not target_doc:
            # Try from corpus directly
            for d in docs:
                if d.section_number == bns_section:
                    target_doc = d
                    break

        if ipc_mappings:
            ipc_refs = ", ".join(
                f"IPC Section {m['ipc_section']} ({m['ipc_title']})"
                for m in ipc_mappings
            )
            rel = ipc_mappings[0]["relationship_type"]
            notes = ipc_mappings[0]["notes"]

            reasoning = (
                f"BNS Section {bns_section} "
                f"({target_doc.section_title if target_doc else ''}) "
                f"corresponds to {ipc_refs}. "
                f"Relationship: {rel}."
            )
            if notes:
                reasoning += f" {notes}"

            return {
                "status": "success",
                "source": "reverse_concordance_lookup",
                "query": query,
                "query_type": "bns_lookup",
                "predicted_bns_section": bns_section,
                "bns_section_title": target_doc.section_title if target_doc else "",
                "bns_section_text": target_doc.section_text if target_doc else "",
                "chapter": target_doc.chapter if target_doc else "",
                "corresponding_ipc_sections": [
                    {"ipc_section": m["ipc_section"], "ipc_title": m["ipc_title"]}
                    for m in ipc_mappings
                ],
                "relationship_type": rel,
                "reasoning": reasoning,
                "key_changes": notes or "No significant changes noted.",
                "confidence": "HIGH",
                "alternative_sections": [],
            }

        return self._build_retrieval_answer(query, docs, bns_section=bns_section)

    def _build_retrieval_answer(
        self,
        query: str,
        docs: List[RetrievedDoc],
        ipc_section: Optional[str] = None,
        bns_section: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Answer based purely on retrieval results (no concordance match)."""
        if not docs:
            return {
                "status": "no_results",
                "source": "retrieval",
                "query": query,
                "predicted_bns_section": "NONE",
                "reasoning": "No relevant BNS sections found for this query.",
                "confidence": "LOW",
            }

        top = docs[0]
        confidence = self._compute_confidence(top, top.method)

        # Check if top result has a concordance mapping we can use
        ipc_from_top = top.mapped_from_ipc
        concordance_info = ""
        if ipc_from_top and ipc_from_top in self.concordance:
            m = self.concordance[ipc_from_top]
            concordance_info = (
                f" This section was originally IPC Section {ipc_from_top} "
                f"({m['ipc_title']}), {m['relationship_type']} as BNS Section "
                f"{m['bns_section']}."
            )

        reasoning = (
            f"Based on hybrid retrieval analysis (BM25 + semantic similarity), "
            f"the most relevant BNS section is Section {top.section_number} "
            f"({top.section_title}), located in {top.chapter}."
            f"{concordance_info}"
        )

        if top.notes:
            reasoning += f" Notes: {top.notes}"

        alternatives = []
        for d in docs[1:4]:
            alternatives.append({
                "section": d.section_number,
                "title": d.section_title,
                "relevance_score": round(d.score, 4),
            })

        return {
            "status": "success",
            "source": "hybrid_retrieval",
            "query": query,
            "query_type": "semantic_search",
            "ipc_section": ipc_section,
            "predicted_bns_section": top.section_number,
            "bns_section_title": top.section_title,
            "bns_section_text": top.section_text,
            "chapter": top.chapter,
            "relationship_type": top.relationship_type or "unknown",
            "reasoning": reasoning,
            "key_changes": top.notes or "See section text for details.",
            "confidence": confidence,
            "retrieval_score": round(top.score, 4),
            "alternative_sections": alternatives,
        }

    def generate(
        self,
        query: str,
        docs: List[RetrievedDoc],
        ipc_section: Optional[str] = None,
        bns_section: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a structured answer. Decision tree:
        1. If IPC section found -> concordance lookup
        2. If BNS section found -> reverse concordance lookup
        3. Otherwise -> retrieval-based answer
        """
        if ipc_section:
            return self._build_ipc_answer(query, ipc_section, docs)
        elif bns_section:
            return self._build_bns_answer(query, bns_section, docs)
        else:
            return self._build_retrieval_answer(query, docs)


# ══════════════════════════════════════════════════════════════════════════
# 4. PRODUCTION RAG PIPELINE (Orchestrator)
# ══════════════════════════════════════════════════════════════════════════

class ProductionRAGPipeline:
    """
    End-to-end production RAG pipeline for IPC<->BNS mapping.

    100% local. No external APIs. No LLM calls.

    Pipeline: Query -> Hybrid Retrieval -> Rule-Based Generation -> Structured Answer
    """

    def __init__(self, retriever: Optional[HybridRetriever] = None, top_k: int = 7):
        self.retriever = retriever or HybridRetriever()
        self.top_k = top_k
        self.generator: Optional[LocalAnswerGenerator] = None
        self._indexed = False

    def index(self):
        """Index the BNS corpus. Must be called before querying."""
        self.retriever.index()
        self.generator = LocalAnswerGenerator(
            concordance=self.retriever.concordance,
            reverse_concordance=self.retriever.reverse_concordance,
        )
        self._indexed = True

    def query(self, user_query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        """
        Run the full local RAG pipeline on a single query.
        Returns a structured dict with the answer, reasoning, confidence, etc.
        """
        if not self._indexed:
            self.index()

        k = top_k or self.top_k
        start = time.time()

        # Step 1: Extract section numbers from query
        ipc_section = self.retriever._extract_ipc_section(user_query)
        bns_section = self.retriever._extract_bns_section(user_query)

        # Step 2: Retrieve relevant BNS sections (local models)
        docs = self.retriever.retrieve(user_query, top_k=k)

        # Step 3: Generate answer (rule-based, no LLM)
        result = self.generator.generate(
            query=user_query,
            docs=docs,
            ipc_section=ipc_section,
            bns_section=bns_section,
        )

        result["latency_ms"] = round((time.time() - start) * 1000, 2)
        result["num_docs_retrieved"] = len(docs)
        result["retrieved_sections"] = [
            {
                "section": d.section_number,
                "title": d.section_title,
                "score": round(d.score, 4),
                "method": d.method,
            }
            for d in docs
        ]

        return result

    def query_batch(self, queries: List[str], top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Run the pipeline on a batch of queries."""
        return [self.query(q, top_k=top_k) for q in queries]

    def format_answer(self, result: Dict[str, Any]) -> str:
        """Format a pipeline result into a human-readable answer."""
        lines = []
        lines.append("=" * 70)
        lines.append(f"  QUERY: {result.get('query', '')}")
        lines.append("=" * 70)

        # Query type
        qtype = result.get("query_type", "")
        if qtype:
            lines.append(f"\n  [Query Type: {qtype}]")

        # IPC section if identified
        ipc = result.get("ipc_section") or result.get("ipc_section_identified")
        if ipc:
            ipc_title = result.get("ipc_title", "")
            lines.append(f"  IPC Section: {ipc}" + (f" ({ipc_title})" if ipc_title else ""))

        bns = result.get("predicted_bns_section", "NONE")
        title = result.get("bns_section_title", "")
        conf = result.get("confidence", "?")

        if bns and bns != "NONE":
            lines.append(f"\n  >> BNS Section: {bns} -- {title}")
            lines.append(f"     Confidence:  {conf}")
            lines.append(f"     Mapping:     {result.get('relationship_type', 'unknown')}")
            lines.append(f"     Source:      {result.get('source', '?')}")
        else:
            lines.append("\n  >> No confident BNS mapping found.")

        if result.get("reasoning"):
            lines.append(f"\n  Reasoning: {result['reasoning']}")

        changes = result.get("key_changes", "")
        if changes and changes not in ("No significant changes noted.", "See section text for details."):
            lines.append(f"\n  Key Changes: {changes}")

        # Section text preview
        sec_text = result.get("bns_section_text", "")
        if sec_text and len(sec_text) > 10:
            preview = sec_text[:250] + "..." if len(sec_text) > 250 else sec_text
            lines.append(f"\n  Provision: {preview}")

        alts = result.get("alternative_sections", [])
        if alts:
            alt_strs = []
            for a in alts[:3]:
                if isinstance(a, dict):
                    alt_strs.append(f"Sec {a['section']} ({a['title']})")
                else:
                    alt_strs.append(str(a))
            lines.append(f"\n  Alternatives: {', '.join(alt_strs)}")

        lines.append(f"\n  Latency: {result.get('latency_ms', 0)}ms")
        lines.append("=" * 70)
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# 5. CLI
# ══════════════════════════════════════════════════════════════════════════

def run_interactive(pipeline: ProductionRAGPipeline):
    """Interactive REPL mode."""
    print("\n" + "=" * 70)
    print("  IPC <-> BNS Legal Mapping Assistant")
    print("  100% Local Pipeline | No External APIs")
    print("  Type your query, or 'quit' to exit.")
    print("=" * 70 + "\n")

    while True:
        try:
            query = input("  Your query: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!")
            break

        if not query or query.lower() in ("quit", "exit", "q"):
            print("  Goodbye!")
            break

        result = pipeline.query(query)
        print(pipeline.format_answer(result))
        print()


def run_evaluate(pipeline: ProductionRAGPipeline):
    """Evaluate pipeline on the full concordance table."""
    concordance = load_concordance()

    test_queries = []
    for ipc_sec, mapping in concordance.items():
        bns_sec = mapping["bns_section"]
        if not bns_sec or bns_sec == "-":
            continue
        test_queries.append({
            "query": f"What is the BNS equivalent of IPC Section {ipc_sec} ({mapping['ipc_title']})?",
            "true_bns": bns_sec,
            "ipc_section": ipc_sec,
        })

    log.info(f"Evaluating on {len(test_queries)} concordance entries...")

    correct = 0
    total = len(test_queries)
    errors = []

    for i, tq in enumerate(test_queries):
        result = pipeline.query(tq["query"])
        predicted = result.get("predicted_bns_section", "")

        if predicted == tq["true_bns"]:
            correct += 1
        else:
            errors.append({
                "query": tq["query"],
                "true_bns": tq["true_bns"],
                "predicted_bns": predicted,
                "confidence": result.get("confidence", "?"),
                "source": result.get("source", "?"),
            })

        if (i + 1) % 20 == 0:
            log.info(f"  Progress: {i+1}/{total} -- Accuracy so far: {correct/(i+1):.1%}")

    accuracy = correct / max(1, total)
    print(f"\n{'='*60}")
    print(f"  EVALUATION RESULTS (100% Local Pipeline)")
    print(f"  Total Queries:   {total}")
    print(f"  Correct:         {correct}")
    print(f"  Accuracy:        {accuracy:.1%}")
    print(f"  Errors:          {len(errors)}")
    print(f"{'='*60}")

    if errors:
        print(f"\n  Errors:")
        for e in errors:
            print(f"    True BNS {e['true_bns']}, Got: {e['predicted_bns']} ({e['confidence']})")

    eval_path = PROJECT_ROOT / "reports" / "production_rag_evaluation.json"
    os.makedirs(eval_path.parent, exist_ok=True)
    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump({
            "pipeline": "100% local (no external LLM)",
            "total": total,
            "correct": correct,
            "accuracy": round(accuracy, 4),
            "errors": errors,
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Full results saved to: {eval_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Production RAG Pipeline for IPC<->BNS Mapping (100% Local)"
    )
    parser.add_argument(
        "query", nargs="?", default=None,
        help="A single query (e.g., 'What is the BNS equivalent of IPC 302?')"
    )
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--evaluate", "-e", action="store_true", help="Evaluate on concordance")
    parser.add_argument("--top-k", type=int, default=7, help="Documents to retrieve (default: 7)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")
    args = parser.parse_args()

    pipeline = ProductionRAGPipeline(top_k=args.top_k)
    pipeline.index()

    if args.evaluate:
        run_evaluate(pipeline)
    elif args.interactive:
        run_interactive(pipeline)
    elif args.query:
        result = pipeline.query(args.query)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(pipeline.format_answer(result))
    else:
        run_interactive(pipeline)


if __name__ == "__main__":
    main()

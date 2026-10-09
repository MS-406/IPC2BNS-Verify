"""
dense_embedder.py — Production Dense Embedding Wrapper (BGE-M3 / E5-Large / MiniLM)

Provides a unified interface for loading and running dense embedding models
for the Hybrid RRF retrieval upgrade (Phase C).

Supported models (in order of quality):
1. BAAI/bge-m3 (Multilingual, best for legal text, 1024-dim)
2. intfloat/multilingual-e5-large (1024-dim, great for cross-lingual)
3. all-MiniLM-L6-v2 (384-dim, lightweight fallback)

The wrapper auto-selects the best available model based on installed packages.
"""

import os
import sys
import logging
import pickle
import json
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from src.ingestion.chunker import StatutoryChunk

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("dense_embedder")

# Model preference order (best → lightweight)
MODEL_PREFERENCE = [
    "BAAI/bge-m3",
    "intfloat/multilingual-e5-large",
    "all-MiniLM-L6-v2"
]


class ProductionDenseEmbedder:
    """
    Production-grade dense embedding engine for statutory text.
    Auto-selects the best available sentence-transformers model.
    """

    def __init__(self, model_name: Optional[str] = None, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.model = None
        self.embedding_dim = 0

        self._initialize_model()

    def _initialize_model(self):
        """Load the best available embedding model."""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            log.warning("sentence-transformers not installed. Dense embeddings unavailable.")
            return

        if self.model_name:
            candidates = [self.model_name]
        else:
            candidates = MODEL_PREFERENCE

        for model_id in candidates:
            try:
                log.info(f"Loading dense embedding model: {model_id}")
                self.model = SentenceTransformer(model_id, device=self.device)
                self.model_name = model_id
                # Get embedding dimension
                test_emb = self.model.encode(["test"], convert_to_numpy=True)
                self.embedding_dim = test_emb.shape[1]
                log.info(f"✅ Loaded {model_id} (dim={self.embedding_dim})")
                return
            except Exception as e:
                log.warning(f"Could not load {model_id}: {e}")
                continue

        log.error("No dense embedding model could be loaded.")

    @property
    def is_available(self) -> bool:
        return self.model is not None

    def encode_texts(self, texts: List[str], batch_size: int = 32,
                     show_progress: bool = True) -> np.ndarray:
        """Encode a list of texts to dense vectors."""
        if not self.is_available:
            raise RuntimeError("Dense embedding model not loaded")

        # For E5 models, prepend "passage: " prefix
        if "e5" in self.model_name.lower():
            texts = [f"passage: {t}" for t in texts]

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True  # L2-normalize for cosine similarity
        )
        return embeddings

    def encode_query(self, query: str) -> np.ndarray:
        """Encode a single query to a dense vector."""
        if not self.is_available:
            raise RuntimeError("Dense embedding model not loaded")

        # For E5 models, prepend "query: " prefix
        text = f"query: {query}" if "e5" in self.model_name.lower() else query
        return self.model.encode([text], convert_to_numpy=True, normalize_embeddings=True)[0]

    def compute_similarity(self, query_vec: np.ndarray, doc_vecs: np.ndarray) -> np.ndarray:
        """Compute cosine similarity between query and documents."""
        if query_vec.ndim == 1:
            query_vec = query_vec.reshape(1, -1)
        from sklearn.metrics.pairwise import cosine_similarity
        return cosine_similarity(query_vec, doc_vecs)[0]


class ProductionDenseIndex:
    """
    Pre-built dense vector index for statutory chunks.
    Supports building, saving, loading, and searching.
    """

    def __init__(self, embedder: Optional[ProductionDenseEmbedder] = None):
        self.embedder = embedder or ProductionDenseEmbedder()
        self.chunks: List[StatutoryChunk] = []
        self.embeddings: Optional[np.ndarray] = None

    def build(self, chunks: List[StatutoryChunk]):
        """Build dense vectors for all statutory chunks."""
        self.chunks = chunks
        texts = []
        for chunk in chunks:
            # Create rich text representation for embedding
            text = (
                f"{chunk.act} Section {chunk.section_number}: {chunk.section_title}. "
                f"{chunk.section_text}"
            )
            texts.append(text)

        log.info(f"Encoding {len(texts)} statutory chunks with {self.embedder.model_name}...")
        self.embeddings = self.embedder.encode_texts(texts)
        log.info(f"Built dense index: {self.embeddings.shape}")

    def search(self, query: str, top_k: int = 10,
               act_filter: Optional[str] = None) -> List[Tuple[StatutoryChunk, float]]:
        """Search the dense index for the most relevant chunks."""
        if self.embeddings is None or len(self.chunks) == 0:
            return []

        q_vec = self.embedder.encode_query(query)
        similarities = self.embedder.compute_similarity(q_vec, self.embeddings)

        results = []
        for idx, score in enumerate(similarities):
            chunk = self.chunks[idx]
            if act_filter and chunk.act.upper() != act_filter.upper():
                continue
            results.append((chunk, float(score)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def save(self, output_dir: str):
        """Save the dense index to disk."""
        os.makedirs(output_dir, exist_ok=True)
        data = {
            "chunks": [c.to_dict() for c in self.chunks],
            "embeddings": self.embeddings,
            "model_name": self.embedder.model_name,
            "embedding_dim": self.embedder.embedding_dim,
        }
        path = os.path.join(output_dir, "production_dense_index.pkl")
        with open(path, "wb") as f:
            pickle.dump(data, f)
        log.info(f"Saved production dense index ({len(self.chunks)} chunks) to {path}")

    @classmethod
    def load(cls, index_dir: str) -> "ProductionDenseIndex":
        """Load a saved dense index from disk."""
        path = os.path.join(index_dir, "production_dense_index.pkl")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Dense index not found: {path}")

        with open(path, "rb") as f:
            data = pickle.load(f)

        instance = cls.__new__(cls)
        instance.embedder = ProductionDenseEmbedder(model_name=data.get("model_name"))
        instance.embeddings = data["embeddings"]
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
        log.info(f"Loaded production dense index: {instance.embeddings.shape}")
        return instance


# ── Global singleton ─────────────────────────────────────────────────────
_GLOBAL_DENSE_EMBEDDER: Optional[ProductionDenseEmbedder] = None


def get_dense_embedder(model_name: Optional[str] = None) -> ProductionDenseEmbedder:
    global _GLOBAL_DENSE_EMBEDDER
    if _GLOBAL_DENSE_EMBEDDER is None:
        _GLOBAL_DENSE_EMBEDDER = ProductionDenseEmbedder(model_name=model_name)
    return _GLOBAL_DENSE_EMBEDDER

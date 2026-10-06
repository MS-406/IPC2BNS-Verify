"""
encoder_adapters.py — Phase 4: Transformer Encoder Adapters

Provides a BaseEncoder ABC and 6 concrete adapters wrapping HuggingFace models:
- InLegalBERTEncoder, LegalBERTEncoder, RoBERTaEncoder, DeBERTaEncoder,
  BERTEncoder, SentenceTransformerEncoder

Each exposes a unified encode(texts) → np.ndarray interface.
Models are lazily loaded and support GPU/CPU auto-detection.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type

import numpy as np

log = logging.getLogger("encoder_adapters")


class BaseEncoder(ABC):
    """Abstract base encoder providing a uniform embedding interface."""

    name: str = "base"
    embedding_dim: int = 768
    max_seq_length: int = 512

    def __init__(self, device: Optional[str] = None, max_seq_length: int = 512):
        self.max_seq_length = max_seq_length
        self.device = device or self._auto_device()
        self._model = None
        self._tokenizer = None

    @staticmethod
    def _auto_device() -> str:
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    @abstractmethod
    def _load_model(self) -> None:
        """Load the underlying model and tokenizer (lazy)."""
        ...

    @abstractmethod
    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Encode a list of texts into a 2D embedding matrix.

        Returns:
            np.ndarray of shape (len(texts), embedding_dim)
        """
        ...

    def encode_single(self, text: str) -> np.ndarray:
        """Encode a single text, returning a 1D vector."""
        return self.encode([text])[0]

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def get_info(self) -> Dict:
        return {
            "name": self.name,
            "embedding_dim": self.embedding_dim,
            "max_seq_length": self.max_seq_length,
            "device": self.device,
            "loaded": self.is_loaded,
        }


# ── HuggingFace-based Encoders ───────────────────────────────────────────

class _HFEncoder(BaseEncoder):
    """
    Shared implementation for HuggingFace AutoModel-based encoders.
    Uses mean-pooling over token embeddings as the sentence representation.
    """

    model_id: str = ""

    def _load_model(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoTokenizer, AutoModel

        log.info(f"Loading {self.name} from {self.model_id} on {self.device}")
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        self._model = AutoModel.from_pretrained(self.model_id).to(self.device)
        self._model.eval()

        # Infer embedding dim from config
        self.embedding_dim = self._model.config.hidden_size

    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        import torch

        self._load_model()
        all_embeddings = []

        for start in range(0, len(texts), batch_size):
            batch = texts[start: start + batch_size]
            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self.max_seq_length,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                outputs = self._model(**encoded)

            # Mean pooling over token embeddings (excluding padding)
            token_embeds = outputs.last_hidden_state  # (B, T, D)
            mask = encoded["attention_mask"].unsqueeze(-1).float()  # (B, T, 1)
            summed = (token_embeds * mask).sum(dim=1)  # (B, D)
            counts = mask.sum(dim=1).clamp(min=1e-9)  # (B, 1)
            mean_pooled = summed / counts  # (B, D)

            all_embeddings.append(mean_pooled.cpu().numpy())

        return np.vstack(all_embeddings)


class InLegalBERTEncoder(_HFEncoder):
    name = "inlegalbert"
    model_id = "law-ai/InLegalBERT"


class LegalBERTEncoder(_HFEncoder):
    name = "legalbert"
    model_id = "nlpaueb/legal-bert-base-uncased"


class RoBERTaEncoder(_HFEncoder):
    name = "roberta"
    model_id = "roberta-base"


class DeBERTaEncoder(_HFEncoder):
    name = "deberta"
    model_id = "microsoft/deberta-v3-base"


class BERTEncoder(_HFEncoder):
    name = "bert"
    model_id = "bert-base-uncased"


# ── Sentence-Transformer Encoder ─────────────────────────────────────────

class SentenceTransformerEncoder(BaseEncoder):
    """
    Wraps sentence-transformers for models optimised for semantic similarity.
    Uses the library's built-in encode() which handles pooling internally.
    """

    name = "sentence_transformer"
    model_id = "all-MiniLM-L6-v2"

    def __init__(self, model_id: str = "all-MiniLM-L6-v2", **kwargs):
        super().__init__(**kwargs)
        self.model_id = model_id

    def _load_model(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        log.info(f"Loading SentenceTransformer: {self.model_id} on {self.device}")
        self._model = SentenceTransformer(self.model_id, device=self.device)
        self.embedding_dim = self._model.get_sentence_embedding_dimension()

    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        self._load_model()
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return embeddings


# ── Registry & Factory ───────────────────────────────────────────────────

ENCODER_REGISTRY: Dict[str, Type[BaseEncoder]] = {
    "inlegalbert": InLegalBERTEncoder,
    "legalbert": LegalBERTEncoder,
    "roberta": RoBERTaEncoder,
    "deberta": DeBERTaEncoder,
    "bert": BERTEncoder,
    "sentence_transformer": SentenceTransformerEncoder,
}


def get_encoder(name: str, **kwargs) -> BaseEncoder:
    """Instantiate an encoder adapter by name."""
    if name not in ENCODER_REGISTRY:
        raise ValueError(
            f"Unknown encoder '{name}'. Available: {list(ENCODER_REGISTRY.keys())}"
        )
    return ENCODER_REGISTRY[name](**kwargs)


def list_encoders() -> List[str]:
    """Return available encoder names."""
    return list(ENCODER_REGISTRY.keys())

"""
classifier.py — Phase 4b: Transformer Classifier

TransformerClassifier: fine-tunable classification head on top of any BaseEncoder.
Supports both frozen-encoder (linear probe) and full fine-tuning modes.
Returns logits + confidence scores for top-K predictions.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

log = logging.getLogger("classifier")


try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


@dataclass
class ClassificationResult:
    """Output of a classification prediction."""
    predicted_bns: str
    confidence: float
    rank: int
    logit: float = 0.0
    top_k_predictions: List[Dict[str, Any]] = field(default_factory=list)


if TORCH_AVAILABLE:

    class ClassificationHead(nn.Module):
        """
        Linear classification head with optional dropout and hidden layer.
        Maps encoder output → num_classes logits.
        """

        def __init__(
            self,
            input_dim: int,
            num_classes: int,
            hidden_dim: Optional[int] = None,
            dropout: float = 0.1,
        ):
            super().__init__()
            layers = []
            if hidden_dim:
                layers.extend([
                    nn.Linear(input_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_dim, num_classes),
                ])
            else:
                layers.extend([
                    nn.Dropout(dropout),
                    nn.Linear(input_dim, num_classes),
                ])
            self.classifier = nn.Sequential(*layers)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.classifier(x)


class TransformerClassifier:
    """
    Classification wrapper over any BaseEncoder.

    Modes:
    - linear_probe: Encoder is frozen; only the classification head is trained.
    - fine_tune: Both encoder and head are trainable.

    Usage:
        clf = TransformerClassifier(encoder, class_labels)
        clf.train_step(embeddings, labels)
        results = clf.predict(texts, top_k=5)
    """

    def __init__(
        self,
        encoder,  # BaseEncoder instance
        class_labels: List[str],
        mode: str = "linear_probe",
        hidden_dim: Optional[int] = None,
        dropout: float = 0.1,
        device: Optional[str] = None,
    ):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for TransformerClassifier")

        self.encoder = encoder
        self.class_labels = class_labels
        self.label_to_idx = {label: i for i, label in enumerate(class_labels)}
        self.idx_to_label = {i: label for i, label in enumerate(class_labels)}
        self.num_classes = len(class_labels)
        self.mode = mode
        self.device = device or encoder.device

        # Ensure encoder is loaded to get embedding_dim
        if not encoder.is_loaded:
            encoder._load_model()

        self.head = ClassificationHead(
            input_dim=encoder.embedding_dim,
            num_classes=self.num_classes,
            hidden_dim=hidden_dim,
            dropout=dropout,
        ).to(self.device)

        if mode == "linear_probe":
            # Freeze encoder parameters
            if hasattr(encoder, '_model') and encoder._model is not None:
                for param in encoder._model.parameters():
                    param.requires_grad = False
            log.info("TransformerClassifier: linear probe mode (encoder frozen)")
        else:
            log.info("TransformerClassifier: fine-tune mode (encoder trainable)")

    def get_trainable_parameters(self):
        """Return parameters that require gradients."""
        params = list(self.head.parameters())
        if self.mode == "fine_tune" and hasattr(self.encoder, '_model'):
            if self.encoder._model is not None:
                params.extend(self.encoder._model.parameters())
        return params

    def get_parameter_count(self) -> Dict[str, int]:
        """Count trainable and total parameters."""
        head_params = sum(p.numel() for p in self.head.parameters())
        head_trainable = sum(
            p.numel() for p in self.head.parameters() if p.requires_grad
        )
        encoder_params = 0
        encoder_trainable = 0
        if hasattr(self.encoder, '_model') and self.encoder._model is not None:
            encoder_params = sum(
                p.numel() for p in self.encoder._model.parameters()
            )
            encoder_trainable = sum(
                p.numel()
                for p in self.encoder._model.parameters()
                if p.requires_grad
            )
        return {
            "head_params": head_params,
            "head_trainable": head_trainable,
            "encoder_params": encoder_params,
            "encoder_trainable": encoder_trainable,
            "total_params": head_params + encoder_params,
            "total_trainable": head_trainable + encoder_trainable,
        }

    def encode_texts(self, texts: List[str], batch_size: int = 32) -> "torch.Tensor":
        """Encode texts to embeddings tensor."""
        embeddings = self.encoder.encode(texts, batch_size=batch_size)
        return torch.tensor(embeddings, dtype=torch.float32, device=self.device)

    def forward(self, embeddings: "torch.Tensor") -> "torch.Tensor":
        """Forward pass through classification head."""
        return self.head(embeddings)

    def compute_loss(
        self,
        embeddings: "torch.Tensor",
        labels: "torch.Tensor",
    ) -> "torch.Tensor":
        """Compute cross-entropy loss."""
        logits = self.forward(embeddings)
        return F.cross_entropy(logits, labels)

    def predict_from_embeddings(
        self,
        embeddings: np.ndarray,
        top_k: int = 5,
    ) -> List[ClassificationResult]:
        """Predict from pre-computed embeddings."""
        self.head.eval()
        with torch.no_grad():
            emb_tensor = torch.tensor(
                embeddings, dtype=torch.float32, device=self.device
            )
            logits = self.forward(emb_tensor)
            probs = F.softmax(logits, dim=-1)

        results = []
        for i in range(len(embeddings)):
            top_vals, top_idxs = torch.topk(probs[i], min(top_k, self.num_classes))
            top_k_preds = []
            for rank, (val, idx) in enumerate(
                zip(top_vals.cpu().numpy(), top_idxs.cpu().numpy()), 1
            ):
                top_k_preds.append({
                    "bns_section": self.idx_to_label[int(idx)],
                    "confidence": float(val),
                    "rank": rank,
                })

            results.append(ClassificationResult(
                predicted_bns=top_k_preds[0]["bns_section"],
                confidence=top_k_preds[0]["confidence"],
                rank=1,
                logit=float(logits[i, top_idxs[0]].cpu()),
                top_k_predictions=top_k_preds,
            ))

        return results

    def predict(
        self,
        texts: List[str],
        top_k: int = 5,
        batch_size: int = 32,
    ) -> List[ClassificationResult]:
        """End-to-end predict: encode texts, then classify."""
        embeddings = self.encoder.encode(texts, batch_size=batch_size)
        return self.predict_from_embeddings(embeddings, top_k=top_k)

    def labels_to_tensor(self, labels: List[str]) -> "torch.Tensor":
        """Convert string labels to index tensor."""
        indices = [self.label_to_idx.get(l, 0) for l in labels]
        return torch.tensor(indices, dtype=torch.long, device=self.device)

    def save_head(self, path: str):
        """Save classification head weights."""
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save({
            "head_state_dict": self.head.state_dict(),
            "class_labels": self.class_labels,
            "mode": self.mode,
            "encoder_name": self.encoder.name,
        }, path)
        log.info(f"Saved classification head to {path}")

    def load_head(self, path: str):
        """Load classification head weights."""
        checkpoint = torch.load(path, map_location=self.device)
        self.head.load_state_dict(checkpoint["head_state_dict"])
        log.info(f"Loaded classification head from {path}")

"""
lstm_models.py — Phase 6: LSTM Model Architectures

Five LSTM architectures for sequence classification over encoder embeddings:
1. VanillaLSTM — Single-direction LSTM + linear head
2. BiLSTM — Bidirectional LSTM
3. BiLSTMAttention — BiLSTM + self-attention pooling
4. StackedBiLSTM — Multi-layer BiLSTM with residual connections
5. BiLSTMCRF — BiLSTM + CRF output layer (sequence labeling variant)

All models consume pre-computed encoder embeddings as input and produce
classification logits over the BNS section label space.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Type

log = logging.getLogger("lstm_models")

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    log.warning("PyTorch not available; LSTM models disabled")


if TORCH_AVAILABLE:

    class VanillaLSTM(nn.Module):
        """Single-direction LSTM → linear classifier."""

        name = "lstm"

        def __init__(
            self,
            input_dim: int = 768,
            hidden_dim: int = 256,
            num_classes: int = 100,
            num_layers: int = 1,
            dropout: float = 0.3,
        ):
            super().__init__()
            self.lstm = nn.LSTM(
                input_dim, hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(hidden_dim, num_classes)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """
            Args:
                x: (batch, seq_len, input_dim) or (batch, input_dim)
            Returns:
                logits: (batch, num_classes)
            """
            if x.dim() == 2:
                x = x.unsqueeze(1)  # (batch, 1, input_dim)
            _, (h_n, _) = self.lstm(x)  # h_n: (num_layers, batch, hidden)
            out = self.dropout(h_n[-1])  # Take last layer
            return self.fc(out)

    class BiLSTM(nn.Module):
        """Bidirectional LSTM → concat final states → classifier."""

        name = "bilstm"

        def __init__(
            self,
            input_dim: int = 768,
            hidden_dim: int = 256,
            num_classes: int = 100,
            num_layers: int = 1,
            dropout: float = 0.3,
        ):
            super().__init__()
            self.lstm = nn.LSTM(
                input_dim, hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                bidirectional=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(hidden_dim * 2, num_classes)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            if x.dim() == 2:
                x = x.unsqueeze(1)
            _, (h_n, _) = self.lstm(x)
            # h_n: (num_layers * 2, batch, hidden)
            # Concat forward and backward final hidden states
            forward_h = h_n[-2]  # Last layer forward
            backward_h = h_n[-1]  # Last layer backward
            combined = torch.cat([forward_h, backward_h], dim=-1)
            out = self.dropout(combined)
            return self.fc(out)

    class SelfAttention(nn.Module):
        """Additive self-attention mechanism for sequence pooling."""

        def __init__(self, hidden_dim: int):
            super().__init__()
            self.W = nn.Linear(hidden_dim, hidden_dim)
            self.v = nn.Linear(hidden_dim, 1, bias=False)

        def forward(
            self, hidden_states: torch.Tensor
        ) -> Tuple[torch.Tensor, torch.Tensor]:
            """
            Args:
                hidden_states: (batch, seq_len, hidden_dim)
            Returns:
                context: (batch, hidden_dim) — attention-weighted sum
                weights: (batch, seq_len) — attention distribution
            """
            energy = torch.tanh(self.W(hidden_states))  # (B, T, H)
            scores = self.v(energy).squeeze(-1)  # (B, T)
            weights = F.softmax(scores, dim=-1)  # (B, T)
            context = torch.bmm(weights.unsqueeze(1), hidden_states).squeeze(1)
            return context, weights

    class BiLSTMAttention(nn.Module):
        """BiLSTM + self-attention pooling → classifier."""

        name = "bilstm_attention"

        def __init__(
            self,
            input_dim: int = 768,
            hidden_dim: int = 256,
            num_classes: int = 100,
            num_layers: int = 1,
            dropout: float = 0.3,
        ):
            super().__init__()
            self.lstm = nn.LSTM(
                input_dim, hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                bidirectional=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.attention = SelfAttention(hidden_dim * 2)
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(hidden_dim * 2, num_classes)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            if x.dim() == 2:
                x = x.unsqueeze(1)
            lstm_out, _ = self.lstm(x)  # (B, T, H*2)
            context, attn_weights = self.attention(lstm_out)
            out = self.dropout(context)
            return self.fc(out)

    class StackedBiLSTM(nn.Module):
        """
        Multi-layer BiLSTM with residual connections.
        Deeper network for richer feature extraction.
        """

        name = "stacked_bilstm"

        def __init__(
            self,
            input_dim: int = 768,
            hidden_dim: int = 256,
            num_classes: int = 100,
            num_layers: int = 3,
            dropout: float = 0.3,
        ):
            super().__init__()
            self.num_layers = num_layers

            # Input projection to match hidden_dim*2 for residual connections
            self.input_proj = nn.Linear(input_dim, hidden_dim * 2)

            # Stack of BiLSTM layers
            self.lstm_layers = nn.ModuleList()
            for i in range(num_layers):
                in_dim = hidden_dim * 2  # All layers have same dim after projection
                self.lstm_layers.append(
                    nn.LSTM(
                        in_dim, hidden_dim,
                        num_layers=1,
                        batch_first=True,
                        bidirectional=True,
                    )
                )

            self.layer_norms = nn.ModuleList([
                nn.LayerNorm(hidden_dim * 2) for _ in range(num_layers)
            ])
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(hidden_dim * 2, num_classes)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            if x.dim() == 2:
                x = x.unsqueeze(1)

            # Project to hidden_dim * 2
            out = self.input_proj(x)  # (B, T, H*2)

            for i in range(self.num_layers):
                residual = out
                out, _ = self.lstm_layers[i](out)
                out = self.layer_norms[i](out + residual)  # Residual connection
                out = self.dropout(out)

            # Use last timestep
            final = out[:, -1, :]
            return self.fc(final)

    class CRFLayer(nn.Module):
        """
        Simplified CRF layer for sequence labeling.
        For classification (single-token sequences), this reduces
        to a transition-aware output layer.
        """

        def __init__(self, num_tags: int):
            super().__init__()
            self.num_tags = num_tags
            self.transitions = nn.Parameter(torch.randn(num_tags, num_tags))
            self.start_transitions = nn.Parameter(torch.randn(num_tags))
            self.end_transitions = nn.Parameter(torch.randn(num_tags))

        def forward(self, emissions: torch.Tensor) -> torch.Tensor:
            """
            For classification, emissions is (batch, num_tags).
            We add start + end transition biases.
            """
            return emissions + self.start_transitions + self.end_transitions

        def decode(self, emissions: torch.Tensor) -> torch.Tensor:
            """Viterbi decode — for single-step, just argmax."""
            scores = self.forward(emissions)
            return scores.argmax(dim=-1)

    class BiLSTMCRF(nn.Module):
        """
        BiLSTM + CRF for classification.
        The CRF layer adds learnable transition biases that can capture
        label correlations (useful when labels have structure, e.g.,
        related BNS sections under the same chapter).
        """

        name = "bilstm_crf"

        def __init__(
            self,
            input_dim: int = 768,
            hidden_dim: int = 256,
            num_classes: int = 100,
            num_layers: int = 1,
            dropout: float = 0.3,
        ):
            super().__init__()
            self.lstm = nn.LSTM(
                input_dim, hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                bidirectional=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.dropout = nn.Dropout(dropout)
            self.emission = nn.Linear(hidden_dim * 2, num_classes)
            self.crf = CRFLayer(num_classes)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            if x.dim() == 2:
                x = x.unsqueeze(1)
            _, (h_n, _) = self.lstm(x)
            forward_h = h_n[-2]
            backward_h = h_n[-1]
            combined = self.dropout(torch.cat([forward_h, backward_h], dim=-1))
            emissions = self.emission(combined)
            return self.crf(emissions)

        def decode(self, x: torch.Tensor) -> torch.Tensor:
            """Predict labels via Viterbi decode."""
            if x.dim() == 2:
                x = x.unsqueeze(1)
            _, (h_n, _) = self.lstm(x)
            forward_h = h_n[-2]
            backward_h = h_n[-1]
            combined = torch.cat([forward_h, backward_h], dim=-1)
            emissions = self.emission(combined)
            return self.crf.decode(emissions)


# ── Registry & Factory ───────────────────────────────────────────────────

LSTM_REGISTRY: Dict[str, type] = {}

if TORCH_AVAILABLE:
    LSTM_REGISTRY = {
        "lstm": VanillaLSTM,
        "bilstm": BiLSTM,
        "bilstm_attention": BiLSTMAttention,
        "stacked_bilstm": StackedBiLSTM,
        "bilstm_crf": BiLSTMCRF,
    }


def get_lstm_model(name: str, **kwargs) -> "nn.Module":
    """Instantiate an LSTM model by name."""
    if not TORCH_AVAILABLE:
        raise ImportError("PyTorch is required for LSTM models")
    if name not in LSTM_REGISTRY:
        raise ValueError(
            f"Unknown LSTM model '{name}'. Available: {list(LSTM_REGISTRY.keys())}"
        )
    return LSTM_REGISTRY[name](**kwargs)


def list_lstm_models() -> List[str]:
    """Return available LSTM model names."""
    return list(LSTM_REGISTRY.keys())

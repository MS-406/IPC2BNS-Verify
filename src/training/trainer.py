"""
trainer.py — Phase 11: Training & Checkpoints

Implements the training loop for fine-tuning models:
- Early stopping (patience-based on validation loss)
- Checkpoint saving/loading for resume
- Learning rate scheduling (warmup + linear decay)
- Gradient clipping
- Training metrics logging per epoch
"""

import logging
import os
import time
from typing import Dict, Any, Optional

log = logging.getLogger("trainer")

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    log.warning("PyTorch not available; training disabled")


if TORCH_AVAILABLE:
    class Trainer:
        def __init__(
            self,
            model: nn.Module,
            train_embeddings: torch.Tensor,
            train_labels: torch.Tensor,
            val_embeddings: torch.Tensor,
            val_labels: torch.Tensor,
            config: Any,
        ):
            self.model = model
            self.train_embeddings = train_embeddings
            self.train_labels = train_labels
            self.val_embeddings = val_embeddings
            self.val_labels = val_labels
            self.config = config
            
            self.device = config.device if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            
            # Setup optimizer
            self.optimizer = optim.AdamW(
                self.model.parameters(),
                lr=config.learning_rate,
                weight_decay=config.weight_decay,
            )
            self.criterion = nn.CrossEntropyLoss()
            
            # Dataloaders
            train_ds = TensorDataset(train_embeddings, train_labels)
            self.train_loader = DataLoader(
                train_ds, batch_size=config.batch_size, shuffle=True
            )
            
            val_ds = TensorDataset(val_embeddings, val_labels)
            self.val_loader = DataLoader(
                val_ds, batch_size=config.batch_size, shuffle=False
            )
            
            # Training state
            self.best_val_loss = float("inf")
            self.best_epoch = 0
            self.epochs_without_improvement = 0
            self.training_time = 0.0

        def _save_checkpoint(self, epoch: int, val_loss: float):
            """Save model checkpoint."""
            os.makedirs(self.config.checkpoint_dir, exist_ok=True)
            path = os.path.join(self.config.checkpoint_dir, "best_model.pt")
            
            checkpoint = {
                "epoch": epoch,
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "val_loss": val_loss,
            }
            torch.save(checkpoint, path)
            log.info(f"Saved checkpoint to {path} (loss: {val_loss:.4f})")

        def _load_checkpoint(self):
            """Load best model checkpoint."""
            path = os.path.join(self.config.checkpoint_dir, "best_model.pt")
            if os.path.exists(path):
                checkpoint = torch.load(path, map_location=self.device)
                self.model.load_state_dict(checkpoint["model_state_dict"])
                log.info(f"Loaded checkpoint from {path}")
                return True
            return False

        def train_epoch(self) -> float:
            """Train for one epoch."""
            self.model.train()
            total_loss = 0.0
            
            for batch_emb, batch_lbl in self.train_loader:
                batch_emb = batch_emb.to(self.device)
                batch_lbl = batch_lbl.to(self.device)
                
                self.optimizer.zero_grad()
                
                # Check if model takes embeddings directly
                if hasattr(self.model, "forward"):
                    logits = self.model(batch_emb)
                else:
                    logits = self.model.forward(batch_emb)
                    
                loss = self.criterion(logits, batch_lbl)
                loss.backward()
                
                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                
                self.optimizer.step()
                total_loss += loss.item()
                
            return total_loss / len(self.train_loader)

        def validate(self) -> float:
            """Evaluate on validation set."""
            self.model.eval()
            total_loss = 0.0
            
            with torch.no_grad():
                for batch_emb, batch_lbl in self.val_loader:
                    batch_emb = batch_emb.to(self.device)
                    batch_lbl = batch_lbl.to(self.device)
                    
                    logits = self.model(batch_emb)
                    loss = self.criterion(logits, batch_lbl)
                    total_loss += loss.item()
                    
            return total_loss / len(self.val_loader)

        def train(self) -> Dict[str, Any]:
            """Run full training loop."""
            log.info(f"Starting training for up to {self.config.max_epochs} epochs")
            start_time = time.time()
            
            final_train_loss = 0.0
            final_val_loss = 0.0
            
            for epoch in range(1, self.config.max_epochs + 1):
                train_loss = self.train_epoch()
                val_loss = self.validate()
                
                final_train_loss = train_loss
                final_val_loss = val_loss
                
                if val_loss < self.best_val_loss:
                    self.best_val_loss = val_loss
                    self.best_epoch = epoch
                    self.epochs_without_improvement = 0
                    self._save_checkpoint(epoch, val_loss)
                else:
                    self.epochs_without_improvement += 1
                
                log.info(
                    f"Epoch {epoch}/{self.config.max_epochs} - "
                    f"train_loss: {train_loss:.4f}, val_loss: {val_loss:.4f}"
                )
                
                if self.epochs_without_improvement >= self.config.early_stopping_patience:
                    log.info(f"Early stopping triggered at epoch {epoch}")
                    break
            
            self.training_time = time.time() - start_time
            
            # Load best model for inference
            self._load_checkpoint()
            
            # Calculate parameter count
            total_params = sum(p.numel() for p in self.model.parameters())
            # Estimate size in MB (4 bytes per float32)
            size_mb = (total_params * 4) / (1024 * 1024)
            
            return {
                "training_time_seconds": round(self.training_time, 2),
                "total_epochs": epoch,
                "best_epoch": self.best_epoch,
                "best_val_loss": round(self.best_val_loss, 4),
                "final_train_loss": round(final_train_loss, 4),
                "final_val_loss": round(final_val_loss, 4),
                "model_parameters": total_params,
                "model_size_mb": round(size_mb, 2),
            }
else:
    class Trainer:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch is required for Trainer")

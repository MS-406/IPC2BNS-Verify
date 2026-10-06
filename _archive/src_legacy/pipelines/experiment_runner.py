"""
experiment_runner.py — Phase 10: Experiment Matrix & Runner

Orchestrates end-to-end experiment execution:
- Takes an ExperimentConfig, instantiates the correct model/retriever/RAG pipeline
- Runs training (if applicable), inference, and evaluation
- Saves all results to the experiment DB
- Valid combination filtering: skips invalid config combos
"""

import logging
import time
from typing import Dict, Any, List, Optional

log = logging.getLogger("experiment_runner")


def is_valid_combination(config) -> bool:
    """
    Filter out invalid experiment configurations.

    Rules:
    - Reranker requires a retriever
    - RAG requires a retriever
    - LSTM classification can work without retriever (uses embeddings directly)
    - Dense/Hybrid retrievers require an encoder
    """
    # Reranker requires retriever
    if config.reranker != "none" and config.retriever == "none":
        return False

    # RAG requires retriever
    if config.rag_enabled and config.retriever == "none":
        return False

    return True


class ExperimentRunner:
    """
    Orchestrates a single experiment: setup → train → infer → evaluate → save.
    """

    def __init__(self, config, db=None):
        """
        Args:
            config: ExperimentConfig instance
            db: ExperimentDatabase instance (optional, auto-created if None)
        """
        self.config = config
        self.db = db

    def _get_db(self):
        if self.db is None:
            from src.utils.experiment_db import ExperimentDatabase
            self.db = ExperimentDatabase()
        return self.db

    def run(self) -> Dict[str, Any]:
        """
        Execute the complete experiment pipeline.

        Returns dict with all metrics and status.
        """
        db = self._get_db()
        config = self.config

        # Validate
        if not is_valid_combination(config):
            log.warning(f"Invalid combination for {config.experiment_id}, skipping")
            return {"status": "skipped", "reason": "invalid_combination"}

        # Register experiment
        db.register_experiment(config.to_dict())
        db.update_status(config.experiment_id, "running")
        log.info(f"Running experiment: {config.experiment_id}")

        try:
            start_time = time.time()
            results = {}

            # 1. Load data splits
            from src.data.split_manager import DataSplitManager
            split_mgr = DataSplitManager()
            splits = split_mgr.load_all_splits()
            train_data = splits["train"]
            val_data = splits["validation"]
            test_data = splits["test"]

            if config.rag_enabled:
                results = self._run_rag_experiment(train_data, val_data, test_data)
            elif config.sequence_model != "none":
                results = self._run_lstm_experiment(train_data, val_data, test_data)
            else:
                results = self._run_retrieval_experiment(train_data, val_data, test_data)

            total_time = time.time() - start_time
            results["total_time_seconds"] = round(total_time, 2)

            # Save metrics to DB
            self._save_results_to_db(results)
            db.update_status(config.experiment_id, "completed")

            log.info(
                f"Experiment {config.experiment_id} completed in {total_time:.1f}s"
            )
            return {"status": "completed", **results}

        except Exception as e:
            log.error(f"Experiment {config.experiment_id} failed: {e}")
            db.update_status(config.experiment_id, "failed", str(e))
            return {"status": "failed", "error": str(e)}

    def _run_retrieval_experiment(
        self, train_data, val_data, test_data
    ) -> Dict[str, Any]:
        """Run a retrieval-only experiment."""
        from src.retrieval.base_retriever import get_retriever
        from src.retrieval.retrieval_benchmark import compute_retrieval_metrics
        from src.data.dataset_validator import load_jsonl
        from src.utils.config import BNS_SECTIONS_PATH

        # Build corpus from BNS sections
        corpus = load_jsonl(str(BNS_SECTIONS_PATH))

        retriever_kwargs = {}
        if self.config.retriever in ("dense", "hybrid"):
            retriever_kwargs["encoder_name"] = self.config.encoder

        retriever = get_retriever(self.config.retriever, **retriever_kwargs)
        retriever.index(corpus)

        # Evaluate on test data
        query_results = []
        predictions = []
        for sample in test_data:
            hits = retriever.retrieve(sample["input_text"], top_k=self.config.top_k)
            retrieved_sections = [h.section_id for h in hits]
            predicted = retrieved_sections[0] if retrieved_sections else ""
            correct = predicted == sample["bns_section"]

            query_results.append({
                "true_section": sample["bns_section"],
                "retrieved_sections": retrieved_sections,
            })
            predictions.append({
                "sample_id": sample.get("sample_id", ""),
                "input_text": sample["input_text"],
                "true_bns": sample["bns_section"],
                "predicted_bns": predicted,
                "confidence": hits[0].score if hits else 0.0,
                "correct": correct,
                "top_k_candidates": retrieved_sections,
            })

        metrics = compute_retrieval_metrics(query_results, [1, 3, 5, 10])

        return {
            "retrieval_metrics": metrics,
            "predictions": predictions,
            "classification_metrics": {
                "accuracy": metrics.get("recall_at_1", 0.0),
            },
        }

    def _run_lstm_experiment(
        self, train_data, val_data, test_data
    ) -> Dict[str, Any]:
        """Run an LSTM classification experiment."""
        from src.models.encoder_adapters import get_encoder
        from src.models.lstm_models import get_lstm_model
        import numpy as np

        try:
            import torch
            import torch.nn.functional as F
        except ImportError:
            return {"error": "PyTorch required for LSTM experiments"}

        encoder = get_encoder(self.config.encoder)

        # Extract unique classes from training data
        class_labels = sorted(set(s["bns_section"] for s in train_data))
        label_to_idx = {l: i for i, l in enumerate(class_labels)}
        num_classes = len(class_labels)

        # Build model
        model = get_lstm_model(
            self.config.sequence_model,
            input_dim=encoder.embedding_dim if encoder.is_loaded else 768,
            hidden_dim=self.config.lstm_hidden_size,
            num_classes=num_classes,
            num_layers=self.config.lstm_num_layers,
            dropout=self.config.lstm_dropout,
        )

        device = self.config.device if torch.cuda.is_available() else "cpu"
        model = model.to(device)

        # Encode all data
        log.info("Encoding training data...")
        train_embs = encoder.encode([s["input_text"] for s in train_data])
        val_embs = encoder.encode([s["input_text"] for s in val_data])
        test_embs = encoder.encode([s["input_text"] for s in test_data])

        train_labels = torch.tensor(
            [label_to_idx.get(s["bns_section"], 0) for s in train_data],
            dtype=torch.long, device=device
        )
        val_labels = torch.tensor(
            [label_to_idx.get(s["bns_section"], 0) for s in val_data],
            dtype=torch.long, device=device
        )

        train_emb_t = torch.tensor(train_embs, dtype=torch.float32, device=device)
        val_emb_t = torch.tensor(val_embs, dtype=torch.float32, device=device)
        test_emb_t = torch.tensor(test_embs, dtype=torch.float32, device=device)

        # Train
        from src.training.trainer import Trainer
        trainer = Trainer(
            model=model,
            train_embeddings=train_emb_t,
            train_labels=train_labels,
            val_embeddings=val_emb_t,
            val_labels=val_labels,
            config=self.config,
        )
        training_metrics = trainer.train()

        # Evaluate on test
        model.eval()
        with torch.no_grad():
            logits = model(test_emb_t)
            probs = F.softmax(logits, dim=-1)
            pred_indices = logits.argmax(dim=-1).cpu().numpy()

        predictions = []
        correct = 0
        for i, sample in enumerate(test_data):
            pred_label = class_labels[pred_indices[i]] if pred_indices[i] < len(class_labels) else ""
            is_correct = pred_label == sample["bns_section"]
            if is_correct:
                correct += 1

            # Top-K
            top_vals, top_idxs = torch.topk(probs[i], min(self.config.top_k, num_classes))
            top_k_candidates = [
                class_labels[idx.item()] for idx in top_idxs
                if idx.item() < len(class_labels)
            ]

            predictions.append({
                "sample_id": sample.get("sample_id", ""),
                "input_text": sample["input_text"],
                "true_bns": sample["bns_section"],
                "predicted_bns": pred_label,
                "confidence": float(probs[i, pred_indices[i]]),
                "correct": is_correct,
                "top_k_candidates": top_k_candidates,
            })

        accuracy = correct / max(1, len(test_data))

        return {
            "classification_metrics": {"accuracy": round(accuracy, 4)},
            "training_metrics": training_metrics,
            "predictions": predictions,
        }

    def _run_rag_experiment(
        self, train_data, val_data, test_data
    ) -> Dict[str, Any]:
        """Run a RAG pipeline experiment."""
        from src.rag.rag_pipeline import RAGPipeline
        from src.rag.rag_evaluator import RAGEvaluator

        pipeline = RAGPipeline.from_config(self.config)
        pipeline.index()

        rag_results = pipeline.run_batch(test_data, top_k=self.config.top_k)
        ground_truths = [s["bns_section"] for s in test_data]

        evaluator = RAGEvaluator()
        eval_results = evaluator.evaluate_batch(rag_results, ground_truths)

        predictions = []
        for sample, rag_r, eval_r in zip(
            test_data, rag_results, eval_results["per_sample"]
        ):
            predictions.append({
                "sample_id": sample.get("sample_id", ""),
                "input_text": sample["input_text"],
                "true_bns": sample["bns_section"],
                "predicted_bns": rag_r.predicted_bns,
                "confidence": rag_r.confidence,
                "correct": eval_r["correct"],
                "top_k_candidates": [
                    c.get("section_id", "") for c in rag_r.reranked_contexts
                ],
            })

        return {
            "classification_metrics": {
                "accuracy": eval_results["aggregate"]["accuracy"],
            },
            "rag_metrics": eval_results["aggregate"],
            "predictions": predictions,
        }

    def _save_results_to_db(self, results: Dict[str, Any]):
        """Save all result metrics to the experiment database."""
        db = self._get_db()
        eid = self.config.experiment_id

        if "classification_metrics" in results:
            db.save_classification_metrics(eid, results["classification_metrics"])

        if "retrieval_metrics" in results:
            db.save_retrieval_metrics(eid, results["retrieval_metrics"])

        if "training_metrics" in results:
            db.save_training_metrics(eid, results["training_metrics"])

        if "predictions" in results:
            db.save_predictions(eid, results["predictions"])

            # Extract errors
            errors = [p for p in results["predictions"] if not p.get("correct")]
            if errors:
                db.save_errors(eid, errors)


# ── Matrix Runner ────────────────────────────────────────────────────────

def run_experiment_matrix(
    configs: List,
    db=None,
    skip_completed: bool = True,
) -> List[Dict[str, Any]]:
    """
    Run a list of experiment configs sequentially.

    Args:
        configs: List of ExperimentConfig instances
        db: Shared ExperimentDatabase
        skip_completed: Skip experiments already marked completed in DB
    """
    if db is None:
        from src.utils.experiment_db import ExperimentDatabase
        db = ExperimentDatabase()

    completed = set(db.get_completed_experiments()) if skip_completed else set()
    results = []

    for config in configs:
        if config.experiment_id in completed:
            log.info(f"Skipping completed: {config.experiment_id}")
            results.append({"experiment_id": config.experiment_id, "status": "skipped"})
            continue

        runner = ExperimentRunner(config, db=db)
        result = runner.run()
        result["experiment_id"] = config.experiment_id
        results.append(result)

    return results

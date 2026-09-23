"""
experiment_db.py — SQLite Experiment Results Database

Stores all experiment results in a normalized SQLite database for
querying, comparison, and report generation.

Tables:
- experiments: Master table with one row per experiment
- classification_metrics: Per-experiment classification metrics
- retrieval_metrics: Per-experiment retrieval metrics (Recall@K, etc.)
- training_metrics: Training time, epochs, convergence info
- inference_metrics: Latency statistics
- predictions: Individual predictions per experiment
- errors: Error analysis records
"""

import os
import json
import sqlite3
import csv
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

log = logging.getLogger("experiment_db")


DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    encoder TEXT,
    retriever TEXT,
    reranker TEXT,
    sequence_model TEXT,
    rag_enabled INTEGER,
    top_k INTEGER,
    seed INTEGER,
    device TEXT,
    status TEXT DEFAULT 'pending',
    error_message TEXT DEFAULT '',
    config_json TEXT,
    git_commit TEXT,
    dataset_hash TEXT,
    checkpoint_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS classification_metrics (
    experiment_id TEXT PRIMARY KEY,
    accuracy REAL,
    balanced_accuracy REAL,
    precision_score REAL,
    recall_score REAL,
    f1 REAL,
    macro_f1 REAL,
    micro_f1 REAL,
    weighted_f1 REAL,
    mcc REAL,
    cohen_kappa REAL,
    specificity REAL,
    brier_score REAL,
    ece REAL,
    per_class_json TEXT,
    confusion_matrix_json TEXT,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);

CREATE TABLE IF NOT EXISTS retrieval_metrics (
    experiment_id TEXT PRIMARY KEY,
    recall_at_1 REAL,
    recall_at_3 REAL,
    recall_at_5 REAL,
    recall_at_10 REAL,
    precision_at_1 REAL,
    precision_at_3 REAL,
    precision_at_5 REAL,
    precision_at_10 REAL,
    mrr REAL,
    map_score REAL,
    hit_rate REAL,
    candidate_recall REAL,
    reranker_recall REAL,
    final_accuracy REAL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);

CREATE TABLE IF NOT EXISTS training_metrics (
    experiment_id TEXT PRIMARY KEY,
    training_time_seconds REAL,
    total_epochs INTEGER,
    best_epoch INTEGER,
    best_val_loss REAL,
    final_train_loss REAL,
    final_val_loss REAL,
    model_parameters INTEGER,
    model_size_mb REAL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);

CREATE TABLE IF NOT EXISTS inference_metrics (
    experiment_id TEXT PRIMARY KEY,
    mean_latency_ms REAL,
    median_latency_ms REAL,
    p95_latency_ms REAL,
    total_inference_time_seconds REAL,
    samples_per_second REAL,
    gpu_memory_mb REAL,
    cpu_usage_percent REAL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT,
    sample_id TEXT,
    input_text TEXT,
    true_ipc TEXT,
    true_bns TEXT,
    predicted_bns TEXT,
    confidence REAL,
    correct INTEGER,
    top_k_candidates TEXT,
    retrieval_score REAL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);

CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT,
    sample_id TEXT,
    input_text TEXT,
    true_bns TEXT,
    predicted_bns TEXT,
    top_k_candidates TEXT,
    retrieval_score REAL,
    confidence REAL,
    error_type TEXT,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);

CREATE TABLE IF NOT EXISTS rag_evaluation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT,
    sample_id TEXT,
    correct_in_context INTEGER,
    prediction_matches_evidence INTEGER,
    hallucinated INTEGER,
    no_evidence_retrieved INTEGER,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);
"""


class ExperimentDatabase:
    """SQLite-backed experiment results database."""

    def __init__(self, db_path: Optional[str] = None):
        from src.utils.config import EXPERIMENT_DB_PATH
        self.db_path = db_path or str(EXPERIMENT_DB_PATH)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(DB_SCHEMA)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Experiment CRUD ───────────────────────────────────────────────────

    def register_experiment(self, config: Dict[str, Any]):
        """Register a new experiment (or update existing)."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO experiments
                (experiment_id, encoder, retriever, reranker, sequence_model,
                 rag_enabled, top_k, seed, device, status, config_json,
                 git_commit, dataset_hash, checkpoint_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                config.get("experiment_id"),
                config.get("encoder"),
                config.get("retriever"),
                config.get("reranker"),
                config.get("sequence_model"),
                int(config.get("rag_enabled", False)),
                config.get("top_k", 5),
                config.get("seed", 42),
                config.get("device", "cpu"),
                config.get("status", "pending"),
                json.dumps(config),
                config.get("git_commit", ""),
                config.get("dataset_hash", ""),
                config.get("checkpoint_dir", ""),
            ))

    def update_status(self, experiment_id: str, status: str, error_message: str = ""):
        """Update experiment status."""
        with self._get_conn() as conn:
            if status in ("completed", "failed"):
                conn.execute("""
                    UPDATE experiments SET status=?, error_message=?, completed_at=CURRENT_TIMESTAMP
                    WHERE experiment_id=?
                """, (status, error_message, experiment_id))
            else:
                conn.execute("""
                    UPDATE experiments SET status=?, error_message=? WHERE experiment_id=?
                """, (status, error_message, experiment_id))

    # ── Metrics Insertion ─────────────────────────────────────────────────

    def save_classification_metrics(self, experiment_id: str, metrics: Dict[str, Any]):
        """Save classification metrics for an experiment."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO classification_metrics
                (experiment_id, accuracy, balanced_accuracy, precision_score, recall_score,
                 f1, macro_f1, micro_f1, weighted_f1, mcc, cohen_kappa, specificity,
                 brier_score, ece, per_class_json, confusion_matrix_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                experiment_id,
                metrics.get("accuracy"),
                metrics.get("balanced_accuracy"),
                metrics.get("precision"),
                metrics.get("recall"),
                metrics.get("f1"),
                metrics.get("macro_f1"),
                metrics.get("micro_f1"),
                metrics.get("weighted_f1"),
                metrics.get("mcc"),
                metrics.get("cohen_kappa"),
                metrics.get("specificity"),
                metrics.get("brier_score"),
                metrics.get("ece"),
                json.dumps(metrics.get("per_class", {})),
                json.dumps(metrics.get("confusion_matrix", [])),
            ))

    def save_retrieval_metrics(self, experiment_id: str, metrics: Dict[str, Any]):
        """Save retrieval metrics for an experiment."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO retrieval_metrics
                (experiment_id, recall_at_1, recall_at_3, recall_at_5, recall_at_10,
                 precision_at_1, precision_at_3, precision_at_5, precision_at_10,
                 mrr, map_score, hit_rate, candidate_recall, reranker_recall, final_accuracy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                experiment_id,
                metrics.get("recall_at_1"), metrics.get("recall_at_3"),
                metrics.get("recall_at_5"), metrics.get("recall_at_10"),
                metrics.get("precision_at_1"), metrics.get("precision_at_3"),
                metrics.get("precision_at_5"), metrics.get("precision_at_10"),
                metrics.get("mrr"), metrics.get("map"),
                metrics.get("hit_rate"),
                metrics.get("candidate_recall"),
                metrics.get("reranker_recall"),
                metrics.get("final_accuracy"),
            ))

    def save_training_metrics(self, experiment_id: str, metrics: Dict[str, Any]):
        """Save training metrics."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO training_metrics
                (experiment_id, training_time_seconds, total_epochs, best_epoch,
                 best_val_loss, final_train_loss, final_val_loss,
                 model_parameters, model_size_mb)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                experiment_id,
                metrics.get("training_time_seconds"),
                metrics.get("total_epochs"),
                metrics.get("best_epoch"),
                metrics.get("best_val_loss"),
                metrics.get("final_train_loss"),
                metrics.get("final_val_loss"),
                metrics.get("model_parameters"),
                metrics.get("model_size_mb"),
            ))

    def save_inference_metrics(self, experiment_id: str, metrics: Dict[str, Any]):
        """Save inference latency metrics."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO inference_metrics
                (experiment_id, mean_latency_ms, median_latency_ms, p95_latency_ms,
                 total_inference_time_seconds, samples_per_second,
                 gpu_memory_mb, cpu_usage_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                experiment_id,
                metrics.get("mean_latency_ms"),
                metrics.get("median_latency_ms"),
                metrics.get("p95_latency_ms"),
                metrics.get("total_inference_time_seconds"),
                metrics.get("samples_per_second"),
                metrics.get("gpu_memory_mb"),
                metrics.get("cpu_usage_percent"),
            ))

    def save_predictions(self, experiment_id: str, predictions: List[Dict[str, Any]]):
        """Save individual predictions."""
        with self._get_conn() as conn:
            # Clear existing predictions for this experiment
            conn.execute("DELETE FROM predictions WHERE experiment_id=?", (experiment_id,))
            for pred in predictions:
                conn.execute("""
                    INSERT INTO predictions
                    (experiment_id, sample_id, input_text, true_ipc, true_bns,
                     predicted_bns, confidence, correct, top_k_candidates, retrieval_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    experiment_id,
                    pred.get("sample_id"),
                    pred.get("input_text", ""),
                    pred.get("true_ipc", ""),
                    pred.get("true_bns", ""),
                    pred.get("predicted_bns", ""),
                    pred.get("confidence"),
                    int(pred.get("correct", False)),
                    json.dumps(pred.get("top_k_candidates", [])),
                    pred.get("retrieval_score"),
                ))

    def save_errors(self, experiment_id: str, errors: List[Dict[str, Any]]):
        """Save error analysis records."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM errors WHERE experiment_id=?", (experiment_id,))
            for err in errors:
                conn.execute("""
                    INSERT INTO errors
                    (experiment_id, sample_id, input_text, true_bns, predicted_bns,
                     top_k_candidates, retrieval_score, confidence, error_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    experiment_id,
                    err.get("sample_id"),
                    err.get("input_text", ""),
                    err.get("true_bns", ""),
                    err.get("predicted_bns", ""),
                    json.dumps(err.get("top_k_candidates", [])),
                    err.get("retrieval_score"),
                    err.get("confidence"),
                    err.get("error_type", "unknown"),
                ))

    # ── Query / Export ────────────────────────────────────────────────────

    def get_all_experiments(self) -> List[Dict[str, Any]]:
        """Get all experiments with their metrics."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT e.*,
                       cm.accuracy, cm.balanced_accuracy, cm.precision_score, cm.recall_score,
                       cm.f1, cm.macro_f1, cm.micro_f1, cm.weighted_f1, cm.mcc, cm.cohen_kappa,
                       rm.recall_at_1, rm.recall_at_3, rm.recall_at_5, rm.recall_at_10,
                       rm.precision_at_1, rm.precision_at_3, rm.precision_at_5, rm.precision_at_10,
                       rm.mrr, rm.map_score, rm.hit_rate,
                       tm.training_time_seconds, tm.model_parameters, tm.model_size_mb,
                       im.mean_latency_ms, im.median_latency_ms, im.p95_latency_ms
                FROM experiments e
                LEFT JOIN classification_metrics cm ON e.experiment_id = cm.experiment_id
                LEFT JOIN retrieval_metrics rm ON e.experiment_id = rm.experiment_id
                LEFT JOIN training_metrics tm ON e.experiment_id = tm.experiment_id
                LEFT JOIN inference_metrics im ON e.experiment_id = im.experiment_id
                ORDER BY e.created_at
            """).fetchall()
            return [dict(row) for row in rows]

    def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Get a single experiment with all metrics."""
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT e.*,
                       cm.accuracy, cm.balanced_accuracy, cm.precision_score, cm.recall_score,
                       cm.f1, cm.macro_f1, cm.micro_f1, cm.weighted_f1, cm.mcc, cm.cohen_kappa,
                       rm.recall_at_1, rm.recall_at_3, rm.recall_at_5, rm.recall_at_10,
                       rm.precision_at_1, rm.precision_at_3, rm.precision_at_5, rm.precision_at_10,
                       rm.mrr, rm.map_score, rm.hit_rate,
                       tm.training_time_seconds, tm.model_parameters,
                       im.mean_latency_ms
                FROM experiments e
                LEFT JOIN classification_metrics cm ON e.experiment_id = cm.experiment_id
                LEFT JOIN retrieval_metrics rm ON e.experiment_id = rm.experiment_id
                LEFT JOIN training_metrics tm ON e.experiment_id = tm.experiment_id
                LEFT JOIN inference_metrics im ON e.experiment_id = im.experiment_id
                WHERE e.experiment_id = ?
            """, (experiment_id,)).fetchone()
            return dict(row) if row else None

    def export_master_csv(self, output_path: Optional[str] = None):
        """Export the master experiment results CSV."""
        from src.utils.config import EXPERIMENT_CSV_PATH
        csv_path = output_path or str(EXPERIMENT_CSV_PATH)
        experiments = self.get_all_experiments()
        if not experiments:
            log.warning("No experiments to export.")
            return

        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        fieldnames = list(experiments[0].keys())
        # Remove internal fields
        for remove_field in ["config_json"]:
            if remove_field in fieldnames:
                fieldnames.remove(remove_field)

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for exp in experiments:
                writer.writerow(exp)

        log.info(f"Exported {len(experiments)} experiments to {csv_path}")

    def get_experiment_count(self) -> int:
        """Get total number of registered experiments."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM experiments").fetchone()
            return row[0] if row else 0

    def get_completed_experiments(self) -> List[str]:
        """Get IDs of completed experiments."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT experiment_id FROM experiments WHERE status='completed'"
            ).fetchall()
            return [row[0] for row in rows]

    def get_failed_experiments(self) -> List[Dict[str, str]]:
        """Get failed experiments with error messages."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT experiment_id, error_message FROM experiments WHERE status='failed'"
            ).fetchall()
            return [{"experiment_id": row[0], "error_message": row[1]} for row in rows]

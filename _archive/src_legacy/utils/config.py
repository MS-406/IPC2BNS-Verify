"""
config.py — Configuration Management for IPC2BNS Benchmarking Framework

Loads experiment configurations from YAML files and provides
project-wide constants, paths, and defaults.
"""

import os
import yaml
import hashlib
import json
import platform
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from pathlib import Path


# ── Project-Wide Constants ────────────────────────────────────────────────
SEED = 42
PROJECT_ROOT = Path(os.environ.get("IPC2BNS_PROJECT_ROOT", Path(__file__).resolve().parents[2]))

# Data paths
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "00_raw"
CLEANED_DATA_DIR = DATA_DIR / "01_cleaned"
GROUND_TRUTH_DIR = DATA_DIR / "02_ground_truth"
BENCHMARK_DIR = DATA_DIR / "03_benchmark"
SPLITS_DIR = DATA_DIR / "splits"
EMBEDDINGS_DIR = DATA_DIR / "05_embeddings_index"

# Framework paths
SRC_DIR = PROJECT_ROOT / "src"
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"
CONFIGS_DIR = EXPERIMENTS_DIR / "configs"
CHECKPOINTS_DIR = EXPERIMENTS_DIR / "checkpoints"
RESULTS_DIR = EXPERIMENTS_DIR / "results"
PREDICTIONS_DIR = EXPERIMENTS_DIR / "predictions"
LOGS_DIR = EXPERIMENTS_DIR / "logs"
ERROR_ANALYSIS_DIR = EXPERIMENTS_DIR / "error_analysis"
CACHED_EMBEDDINGS_DIR = EXPERIMENTS_DIR / "embeddings"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Database
EXPERIMENT_DB_PATH = RESULTS_DIR / "experiment_results.db"
EXPERIMENT_CSV_PATH = RESULTS_DIR / "experiment_results.csv"

# Key data files
CONCORDANCE_PATH = GROUND_TRUTH_DIR / "concordance_v1.csv"
IPC_SECTIONS_PATH = CLEANED_DATA_DIR / "ipc_sections.jsonl"
BNS_SECTIONS_PATH = CLEANED_DATA_DIR / "bns_sections.jsonl"
BENCHMARK_DEV_PATH = BENCHMARK_DIR / "benchmark_dev.csv"
BENCHMARK_TEST_PATH = BENCHMARK_DIR / "benchmark_test.csv"
EXPERIMENT_MATRIX_PATH = PROJECT_ROOT / "experiment_matrix.yaml"

# Encoder model names (HuggingFace identifiers)
ENCODER_MODELS = {
    "inlegalbert": "law-ai/InLegalBERT",
    "legalbert": "nlpaueb/legal-bert-base-uncased",
    "roberta": "roberta-base",
    "deberta": "microsoft/deberta-v3-base",
    "bert": "bert-base-uncased",
    "sentence_transformer": "all-MiniLM-L6-v2",
}

# Valid retriever types
RETRIEVER_TYPES = ["bm25", "tfidf", "dense", "hybrid"]

# Valid reranker types
RERANKER_TYPES = ["none", "cross_encoder"]

# Valid sequence model types
SEQUENCE_MODEL_TYPES = ["none", "lstm", "bilstm", "bilstm_attention"]

# Top-K values to test
TOP_K_VALUES = [1, 3, 5, 10]


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment run."""
    experiment_id: str
    encoder: str = "bert"
    retriever: str = "bm25"
    reranker: str = "none"
    sequence_model: str = "none"
    rag_enabled: bool = False
    top_k: int = 5

    # LSTM hyperparameters
    lstm_hidden_size: int = 256
    lstm_num_layers: int = 1
    lstm_dropout: float = 0.3

    # Training hyperparameters
    learning_rate: float = 2e-5
    batch_size: int = 16
    max_epochs: int = 50
    early_stopping_patience: int = 5
    weight_decay: float = 0.01
    warmup_steps: int = 100

    # General
    seed: int = SEED
    device: str = "cuda"
    max_seq_length: int = 512
    embedding_dim: int = 768

    # Status
    status: str = "pending"  # pending, running, completed, failed
    error_message: str = ""

    # Paths (auto-populated)
    checkpoint_dir: str = ""
    predictions_path: str = ""
    metrics_path: str = ""
    config_path: str = ""
    log_path: str = ""

    def __post_init__(self):
        if not self.checkpoint_dir:
            self.checkpoint_dir = str(CHECKPOINTS_DIR / self.experiment_id)
        if not self.predictions_path:
            self.predictions_path = str(PREDICTIONS_DIR / f"{self.experiment_id}_predictions.csv")
        if not self.metrics_path:
            self.metrics_path = str(RESULTS_DIR / f"{self.experiment_id}_metrics.json")
        if not self.config_path:
            self.config_path = str(CONFIGS_DIR / f"{self.experiment_id}_config.yaml")
        if not self.log_path:
            self.log_path = str(LOGS_DIR / f"{self.experiment_id}.log")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, path: Optional[str] = None):
        save_path = path or self.config_path
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)

    @classmethod
    def load(cls, path: str) -> "ExperimentConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @property
    def encoder_model_name(self) -> str:
        return ENCODER_MODELS.get(self.encoder, self.encoder)

    def is_valid(self) -> bool:
        """Check if this experiment configuration is a valid combination."""
        # Classification-only models don't use retriever/reranker
        if self.sequence_model != "none" and self.retriever == "none":
            # LSTM classification doesn't need retriever (uses embeddings directly)
            pass

        # Reranker requires a retriever
        if self.reranker != "none" and self.retriever == "none":
            return False

        # RAG requires a retriever
        if self.rag_enabled and self.retriever == "none":
            return False

        return True


def compute_dataset_hash(*file_paths: str) -> str:
    """Compute a deterministic hash of dataset files for reproducibility tracking."""
    hasher = hashlib.sha256()
    for fp in sorted(file_paths):
        if os.path.exists(fp):
            with open(fp, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    hasher.update(chunk)
    return hasher.hexdigest()[:16]


def get_git_commit() -> str:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT)
        )
        return result.stdout.strip()[:12] if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def get_environment_info() -> Dict[str, str]:
    """Capture environment information for reproducibility."""
    info = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "processor": platform.processor(),
    }
    try:
        import torch
        info["torch_version"] = torch.__version__
        info["cuda_available"] = str(torch.cuda.is_available())
        if torch.cuda.is_available():
            info["cuda_version"] = torch.version.cuda or "N/A"
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_memory_mb"] = str(torch.cuda.get_device_properties(0).total_mem // (1024 * 1024))
    except ImportError:
        info["torch_version"] = "not_installed"
        info["cuda_available"] = "false"

    try:
        import transformers
        info["transformers_version"] = transformers.__version__
    except ImportError:
        info["transformers_version"] = "not_installed"

    return info


def load_experiment_matrix(path: Optional[str] = None) -> Dict[str, Any]:
    """Load the experiment matrix YAML configuration."""
    matrix_path = path or str(EXPERIMENT_MATRIX_PATH)
    if not os.path.exists(matrix_path):
        raise FileNotFoundError(f"Experiment matrix not found: {matrix_path}")
    with open(matrix_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_experiment_id(encoder: str, retriever: str, reranker: str = "none",
                           sequence_model: str = "none", rag: bool = False,
                           top_k: int = 5, counter: int = 0) -> str:
    """Generate a unique, readable experiment ID."""
    parts = [f"EXP_{counter:03d}"]
    parts.append(encoder.upper())
    parts.append(retriever.upper())
    if reranker != "none":
        parts.append(reranker.upper())
    if sequence_model != "none":
        parts.append(sequence_model.upper())
    if rag:
        parts.append("RAG")
    parts.append(f"K{top_k}")
    return "_".join(parts)

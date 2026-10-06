"""
ablation_runner.py — Phase 21: Ablation Study Automation

Ablation study automation:
- Hold-one-out ablation over pipeline components
- Encoder ablation (fix retriever, vary encoder)
- Retriever ablation (fix encoder, vary retriever)
"""

import logging
import copy
from typing import Dict, Any, List
from src.utils.config import ExperimentConfig
from src.pipelines.experiment_runner import run_experiment_matrix

log = logging.getLogger("ablation_runner")

def generate_encoder_ablations(base_config: ExperimentConfig, encoders: List[str]) -> List[ExperimentConfig]:
    """Generate configs for encoder ablation study."""
    configs = []
    for enc in encoders:
        cfg = copy.deepcopy(base_config)
        cfg.encoder = enc
        cfg.experiment_id = f"ABL_ENC_{enc.upper()}"
        configs.append(cfg)
    return configs

def generate_retriever_ablations(base_config: ExperimentConfig, retrievers: List[str]) -> List[ExperimentConfig]:
    """Generate configs for retriever ablation study."""
    configs = []
    for ret in retrievers:
        cfg = copy.deepcopy(base_config)
        cfg.retriever = ret
        cfg.experiment_id = f"ABL_RET_{ret.upper()}"
        configs.append(cfg)
    return configs

def run_ablation_study(configs: List[ExperimentConfig], db=None) -> List[Dict[str, Any]]:
    """Run ablation study and return results."""
    log.info(f"Running ablation study with {len(configs)} configurations")
    return run_experiment_matrix(configs, db=db, skip_completed=True)

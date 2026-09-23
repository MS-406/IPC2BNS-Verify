#!/usr/bin/env python3
"""
run_experiment.py — CLI Entry Point

CLI for IPC2BNS benchmarking framework.
Modes: validate, split, baseline, run, matrix, report
"""

import argparse
import logging
import sys
from typing import List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cli")

def parse_args():
    parser = argparse.ArgumentParser(description="IPC2BNS Benchmarking Framework CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Validate
    subparsers.add_parser("validate", help="Run Phase 1 Dataset Validation")
    
    # Split
    split_parser = subparsers.add_parser("split", help="Generate train/val/test splits")
    split_parser.add_argument("--force", action="store_true", help="Force overwrite existing splits")
    
    # Baseline
    subparsers.add_parser("baseline", help="Run baseline models")
    
    # Run specific experiment
    run_parser = subparsers.add_parser("run", help="Run a specific experiment configuration")
    run_parser.add_argument("--config", type=str, required=True, help="Path to experiment config YAML")
    
    # Matrix
    matrix_parser = subparsers.add_parser("matrix", help="Run full experiment matrix")
    matrix_parser.add_argument("--matrix", type=str, default="experiment_matrix.yaml", help="Path to matrix YAML")
    
    # Report
    subparsers.add_parser("report", help="Generate reports")
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    if args.command == "validate":
        from src.data.dataset_validator import validate_dataset
        validate_dataset()
        
    elif args.command == "split":
        from src.data.split_manager import generate_and_save_splits
        generate_and_save_splits(force=args.force)
        
    elif args.command == "baseline":
        from src.data.split_manager import DataSplitManager
        from src.models.baselines import get_baseline
        
        split_mgr = DataSplitManager()
        splits = split_mgr.load_all_splits()
        
        for name in ["exact_match", "tfidf", "bm25"]:
            log.info(f"Running baseline: {name}")
            model = get_baseline(name)
            model.fit(splits["train"])
            metrics = model.evaluate(splits["test"])
            log.info(f"Baseline {name} metrics: {metrics}")
            
    elif args.command == "run":
        from src.utils.config import ExperimentConfig
        from src.pipelines.experiment_runner import ExperimentRunner
        
        config = ExperimentConfig.load(args.config)
        runner = ExperimentRunner(config)
        runner.run()
        
    elif args.command == "matrix":
        from src.utils.config import load_experiment_matrix, ExperimentConfig
        from src.pipelines.experiment_runner import run_experiment_matrix
        
        matrix_data = load_experiment_matrix(args.matrix)
        configs = []
        for exp_dict in matrix_data.get("experiments", []):
            configs.append(ExperimentConfig(**exp_dict))
            
        run_experiment_matrix(configs)
        
    elif args.command == "report":
        from src.evaluation.report_generator import ReportGenerator
        rg = ReportGenerator()
        rg.generate_master_report()
        rg.export_all_csv()
        
    else:
        log.error("Invalid command or no command provided. Use --help.")
        sys.exit(1)

if __name__ == "__main__":
    main()

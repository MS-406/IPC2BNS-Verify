"""
report_generator.py — Phase 23-24: Reporting

Automated report generation:
- Master comparison table (all experiments)
- Per-experiment detail reports
- Ablation summary tables
- Export to JSON, CSV, and markdown
"""

import logging
import os
import json
import csv
from typing import Dict, Any, List

log = logging.getLogger("report_generator")

class ReportGenerator:
    def __init__(self, db=None, output_dir: str = "reports"):
        if db is None:
            from src.utils.experiment_db import ExperimentDatabase
            self.db = ExperimentDatabase()
        else:
            self.db = db
            
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate_master_report(self) -> str:
        """Generate a master summary report of all experiments in Markdown."""
        experiments = self.db.get_all_experiments()
        if not experiments:
            return "No experiments found."
            
        path = os.path.join(self.output_dir, "master_report.md")
        
        with open(path, "w", encoding="utf-8") as f:
            f.write("# IPC2BNS Experiment Master Report\n\n")
            
            # Simple summary table
            f.write("## Overview\n\n")
            f.write("| Experiment ID | Status | Accuracy | R@1 | R@5 | MRR |\n")
            f.write("|---------------|--------|----------|-----|-----|-----|\n")
            
            for exp in experiments:
                f.write(
                    f"| {exp.get('experiment_id', '')} "
                    f"| {exp.get('status', '')} "
                    f"| {exp.get('accuracy', 0.0) or 0.0:.4f} "
                    f"| {exp.get('recall_at_1', 0.0) or 0.0:.4f} "
                    f"| {exp.get('recall_at_5', 0.0) or 0.0:.4f} "
                    f"| {exp.get('mrr', 0.0) or 0.0:.4f} |\n"
                )
                
        log.info(f"Generated master report at {path}")
        return path
        
    def generate_experiment_details(self, experiment_id: str) -> str:
        """Generate detailed JSON report for a single experiment."""
        exp = self.db.get_experiment(experiment_id)
        if not exp:
            log.warning(f"Experiment {experiment_id} not found.")
            return ""
            
        path = os.path.join(self.output_dir, f"{experiment_id}_details.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(exp, f, indent=4)
            
        log.info(f"Generated experiment details for {experiment_id} at {path}")
        return path
        
    def export_all_csv(self) -> str:
        """Export all experiment data to CSV."""
        path = os.path.join(self.output_dir, "all_experiments.csv")
        self.db.export_master_csv(path)
        return path

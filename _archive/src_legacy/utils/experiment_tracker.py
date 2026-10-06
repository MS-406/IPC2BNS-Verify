"""
experiment_tracker.py — Phase 19: Experiment Tracking

High-level wrapper coordinating the experiment DB:
- Auto-registers experiments before running
- Context manager for tracking status transitions
- Aggregation queries
"""

import logging
from typing import Dict, Any, List, Optional
import time
from contextlib import contextmanager

from src.utils.experiment_db import ExperimentDatabase

log = logging.getLogger("experiment_tracker")


class ExperimentTracker:
    """Tracks experiments in the database with status updates."""
    
    def __init__(self, db: Optional[ExperimentDatabase] = None):
        self.db = db or ExperimentDatabase()
        
    @contextmanager
    def track_experiment(self, config: Any):
        """Context manager to track experiment execution."""
        experiment_id = config.experiment_id
        
        try:
            self.db.register_experiment(config.to_dict())
            self.db.update_status(experiment_id, "running")
            log.info(f"Started tracking experiment: {experiment_id}")
            
            start_time = time.time()
            
            yield self.db
            
            # If no exception, mark as completed
            # In a real run, the runner might have already saved metrics, but we ensure status is updated
            self.db.update_status(experiment_id, "completed")
            log.info(f"Experiment {experiment_id} completed successfully in {time.time() - start_time:.2f}s")
            
        except Exception as e:
            log.error(f"Experiment {experiment_id} failed: {e}")
            self.db.update_status(experiment_id, "failed", str(e))
            raise e

    def get_best_experiment(self, metric: str = "accuracy") -> Optional[Dict[str, Any]]:
        """Get the experiment with the best value for a given metric."""
        experiments = self.db.get_all_experiments()
        if not experiments:
            return None
            
        completed = [e for e in experiments if e.get("status") == "completed"]
        if not completed:
            return None
            
        # Assuming higher is better for standard metrics (accuracy, f1, mrr)
        # If metric is latency, lower is better. We handle simple case here.
        reverse = True
        if "latency" in metric or "loss" in metric:
            reverse = False
            
        valid_experiments = [e for e in completed if metric in e and e[metric] is not None]
        if not valid_experiments:
            return None
            
        valid_experiments.sort(key=lambda x: x[metric], reverse=reverse)
        return valid_experiments[0]

"""
statistical_comparison.py — Phase 22: Statistical Comparison

Statistical significance testing:
- McNemar's test for paired predictions
- Bootstrap confidence intervals
"""

import logging
import numpy as np
from typing import Dict, Any, List

log = logging.getLogger("statistical_comparison")

try:
    from statsmodels.stats.contingency_tables import mcnemar
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    log.warning("statsmodels not available; McNemar's test disabled")

def run_mcnemar_test(preds_a: List[bool], preds_b: List[bool]) -> Dict[str, Any]:
    """
    Run McNemar's test for paired predictions.
    preds_a and preds_b are lists of booleans indicating correct/incorrect predictions.
    """
    if not STATSMODELS_AVAILABLE:
        return {"error": "statsmodels required"}
        
    if len(preds_a) != len(preds_b):
        raise ValueError("Prediction lists must have the same length")
        
    n00, n01, n10, n11 = 0, 0, 0, 0
    for a, b in zip(preds_a, preds_b):
        if a and b:
            n11 += 1
        elif a and not b:
            n10 += 1
        elif not a and b:
            n01 += 1
        else:
            n00 += 1
            
    table = [[n11, n10], [n01, n00]]
    result = mcnemar(table, exact=False, correction=True)
    
    return {
        "statistic": float(result.statistic),
        "pvalue": float(result.pvalue),
        "significant": bool(result.pvalue < 0.05)
    }

def compute_bootstrap_ci(metrics: List[float], n_iterations: int = 1000, alpha: float = 0.05) -> Dict[str, float]:
    """Compute bootstrap confidence intervals for a list of metrics."""
    if not metrics:
        return {}
        
    metrics_array = np.array(metrics)
    n = len(metrics)
    
    bootstrap_means = []
    for _ in range(n_iterations):
        sample = np.random.choice(metrics_array, size=n, replace=True)
        bootstrap_means.append(np.mean(sample))
        
    lower = np.percentile(bootstrap_means, (alpha / 2) * 100)
    upper = np.percentile(bootstrap_means, (1 - alpha / 2) * 100)
    
    return {
        "mean": float(np.mean(metrics_array)),
        "lower_ci": float(lower),
        "upper_ci": float(upper)
    }

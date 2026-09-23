"""
metrics.py — Phase 12: Metrics Calculation

Comprehensive metrics computation:
- Classification: accuracy, balanced accuracy, precision, recall, F1, MCC, Cohen's kappa
- Retrieval: Recall@K, Precision@K, MRR, MAP, hit_rate
- Calibration: Brier score, ECE
"""

import numpy as np
from typing import Dict, Any, List, Optional
from collections import defaultdict
import logging

try:
    from sklearn.metrics import (
        accuracy_score,
        balanced_accuracy_score,
        precision_recall_fscore_support,
        matthews_corrcoef,
        cohen_kappa_score,
        confusion_matrix,
        brier_score_loss
    )
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.getLogger("metrics").warning("scikit-learn not available; metrics disabled")


def calculate_classification_metrics(
    y_true: List[str],
    y_pred: List[str],
    y_prob: Optional[List[float]] = None,
    classes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Calculate classification metrics."""
    if not SKLEARN_AVAILABLE or not y_true:
        return {}

    metrics = {}
    
    metrics["accuracy"] = accuracy_score(y_true, y_pred)
    metrics["balanced_accuracy"] = balanced_accuracy_score(y_true, y_pred)
    
    # Macro avg
    p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
    metrics["precision"] = p
    metrics["recall"] = r
    metrics["macro_f1"] = f1
    
    # Micro avg
    _, _, f1_micro, _ = precision_recall_fscore_support(y_true, y_pred, average="micro", zero_division=0)
    metrics["micro_f1"] = f1_micro
    
    # Weighted avg
    _, _, f1_weighted, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted", zero_division=0)
    metrics["weighted_f1"] = f1_weighted
    
    # Default F1 is macro
    metrics["f1"] = f1
    
    metrics["mcc"] = matthews_corrcoef(y_true, y_pred)
    metrics["cohen_kappa"] = cohen_kappa_score(y_true, y_pred)
    
    # Specificity approximation (macro average of TN / (TN + FP))
    # Not trivial for multi-class, compute per-class then average
    cm = confusion_matrix(y_true, y_pred, labels=classes)
    spec_list = []
    for i in range(cm.shape[0]):
        tp = cm[i, i]
        fn = np.sum(cm[i, :]) - tp
        fp = np.sum(cm[:, i]) - tp
        tn = np.sum(cm) - tp - fn - fp
        if (tn + fp) > 0:
            spec_list.append(tn / (tn + fp))
    
    metrics["specificity"] = np.mean(spec_list) if spec_list else 0.0
    
    if y_prob is not None and classes is not None:
        # Brier score (multi-class generalization via one-vs-all)
        # Assuming y_prob is confidence of predicted class
        # This is a simplification; true Brier needs full prob distribution
        metrics["brier_score"] = np.mean([(1.0 - p)**2 if t==pr else (0.0 - p)**2 for t, pr, p in zip(y_true, y_pred, y_prob)])
        
        # Expected Calibration Error (ECE)
        # Simplified ECE with 10 bins
        bins = np.linspace(0, 1, 11)
        ece = 0.0
        for i in range(10):
            bin_lower = bins[i]
            bin_upper = bins[i+1]
            
            in_bin = [(p, 1 if t==pr else 0) for t, pr, p in zip(y_true, y_pred, y_prob) if bin_lower <= p < bin_upper]
            if in_bin:
                bin_acc = sum(x[1] for x in in_bin) / len(in_bin)
                bin_conf = sum(x[0] for x in in_bin) / len(in_bin)
                ece += (len(in_bin) / len(y_true)) * abs(bin_acc - bin_conf)
                
        metrics["ece"] = ece
        
    metrics["confusion_matrix"] = cm.tolist() if classes else []
    
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in metrics.items()}

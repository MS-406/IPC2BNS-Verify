"""
computational_metrics.py — Phase 14: Computational Metrics

Resource profiling:
- Inference latency (mean, median, P95)
- Model parameter count, model size
"""

import numpy as np
from typing import Dict, Any, List

def calculate_latency_metrics(latencies_ms: List[float]) -> Dict[str, float]:
    """Calculate latency statistics from a list of latencies in ms."""
    if not latencies_ms:
        return {}
        
    return {
        "mean_latency_ms": round(float(np.mean(latencies_ms)), 2),
        "median_latency_ms": round(float(np.median(latencies_ms)), 2),
        "p95_latency_ms": round(float(np.percentile(latencies_ms, 95)), 2),
        "total_inference_time_seconds": round(float(np.sum(latencies_ms)) / 1000.0, 2),
        "samples_per_second": round(len(latencies_ms) / (float(np.sum(latencies_ms)) / 1000.0), 2) if np.sum(latencies_ms) > 0 else 0.0,
        # Placeholders for hardware metrics (to be collected via external tools if needed)
        "gpu_memory_mb": 0.0,
        "cpu_usage_percent": 0.0,
    }

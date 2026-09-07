"""
test_eval.py — Automated Unit Tests for Evaluation Harness & Ablation Generator
"""

import os
import pytest
from src.eval.harness import (
    MasterEvaluationHarness,
    generate_full_ablation_report,
    wilson_score_interval,
)


def test_wilson_score_interval_bounds():
    lower, upper = wilson_score_interval(0, 10)
    assert lower >= 0.0 and upper <= 100.0

    lower, upper = wilson_score_interval(10, 10)
    assert lower >= 0.0 and upper <= 100.0
    assert upper == 100.0

    lower, upper = wilson_score_interval(0, 0)
    assert (lower, upper) == (0.0, 0.0)


def test_master_evaluation_harness_compile():
    harness = MasterEvaluationHarness(results_dir="results")
    rows = harness.compile_ablation_metrics()
    assert isinstance(rows, list)
    assert len(rows) >= 4
    for r in rows:
        assert "stage_id" in r
        assert "system_configuration" in r
        assert "benchmark_dev_accuracy" in r


def test_generate_full_ablation_report(tmp_path):
    out_csv = str(tmp_path / "test_ablation.csv")
    rows = generate_full_ablation_report(results_dir="results", output_csv=out_csv)
    assert os.path.exists(out_csv)
    assert len(rows) >= 4

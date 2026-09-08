"""
test_mathematical_consistency.py — Strict Verification of Evaluation Statistics & Math Constraints
"""

import os
import math
import csv
import pytest
from src.eval.harness import wilson_score_interval, MasterEvaluationHarness


def test_wilson_confidence_intervals():
    """Verify Wilson Score 95% confidence intervals on benchmark metrics."""
    # Stage 1: 6 / 60
    s1_ci = wilson_score_interval(6, 60)
    assert s1_ci == (4.7, 20.1), f"Stage 1 Wilson CI mismatch: {s1_ci}"

    # Stage 2: 38 / 60
    s2_ci = wilson_score_interval(38, 60)
    assert s2_ci == (50.7, 74.4), f"Stage 2 Wilson CI mismatch: {s2_ci}"

    # Stage 3 Stress Catch: 18 / 18
    stress_ci = wilson_score_interval(18, 18)
    assert stress_ci == (82.4, 100.0), f"Stress catch CI mismatch: {stress_ci}"

    # Stage 3 Control FPR: 0 / 12
    fpr_ci = wilson_score_interval(0, 12)
    assert fpr_ci == (0.0, 24.2), f"Control FPR CI mismatch: {fpr_ci}"

    # Procedural Generalization: 30 / 30
    proc_ci = wilson_score_interval(30, 30)
    assert proc_ci == (88.6, 100.0), f"Procedural CI mismatch: {proc_ci}"


def test_mcnemar_paired_test_mathematical_proof():
    """
    Verify McNemar's paired test mathematical relationship:
    Stage 2 correct - Stage 1 correct == b - c == 33 - 1 == 32
    Stage 1 correct = 6 -> Stage 2 correct = 38 (63.3%)
    chi2 = (|b - c| - 1)^2 / (b + c) == 31^2 / 34 == 961 / 34 == 28.26
    """
    s1_hits = 6
    s2_hits = 38
    n_total = 60

    b = 33  # S1 wrong, S2 right
    c = 1   # S1 right, S2 wrong

    # 1. Linear difference constraint
    delta_hits = s2_hits - s1_hits
    assert b - c == delta_hits, f"b - c ({b - c}) must equal delta ({delta_hits})"
    assert s1_hits + (b - c) == 38, "Stage 2 hits must equal 38"
    assert round(s2_hits / n_total * 100, 1) == 63.3

    # 2. Continuity-corrected Chi-Square calculation
    chi2 = ((abs(b - c) - 1) ** 2) / (b + c)
    assert round(chi2, 2) == 28.26, f"Continuity corrected chi2 must be 28.26, got {round(chi2, 2)}"


def test_ablation_summary_table_csv_congruence():
    """Verify results/ablation_summary_table.csv matches the canonical mathematical metrics."""
    harness = MasterEvaluationHarness()
    rows = harness.compile_ablation_metrics()

    s1 = next(r for r in rows if r["stage_id"] == "Stage 1")
    s2 = next(r for r in rows if r["stage_id"] == "Stage 2")
    s3 = next(r for r in rows if r["stage_id"] == "Stage 3")
    s4 = next(r for r in rows if r["stage_id"] == "Stage 4")

    assert s1["benchmark_dev_accuracy"] == "10.0% (6/60)"
    assert s1["dev_95_wilson_ci"] == "[4.7% - 20.1%]"

    assert s2["benchmark_dev_accuracy"] == "63.3% (38/60)"
    assert s2["dev_95_wilson_ci"] == "[50.7% - 74.4%]"

    assert "63.3% (38/60)" in s3["benchmark_dev_accuracy"]
    assert s3["adversarial_catch_rate"] == "100.0% (18/18) [82.4% - 100.0%]"
    assert s3["control_false_positive_rate"] == "0.0% (0/12) [0.0% - 24.2%]"

    assert "63.3% (38/60)" in s4["benchmark_dev_accuracy"]
    assert "Pre: 33.3% (1/3) -> Post: 100.0% (3/3) [+66.7%]" in s4["amendment_adaptivity_delta"]

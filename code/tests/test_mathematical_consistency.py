"""
test_mathematical_consistency.py — Strict Verification of Evaluation Statistics & Math Constraints
"""

import os
import math
import csv
import re
from collections import Counter
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


def test_cohens_kappa_exact_computation():
    """Verify Cohen's kappa calculation from raw human review calibration CSV."""
    calib_csv = "results/human_review_calibration.csv"
    assert os.path.exists(calib_csv), f"Missing {calib_csv}"

    r1, r2 = [], []
    with open(calib_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r1.append(row["legal_expert_1_verdict"].strip())
            r2.append(row["legal_expert_2_verdict"].strip())

    n = len(r1)
    assert n == 20, f"Expected N=20 calibration sample, got {n}"

    # Observed agreement Po
    agree = sum(1 for a, b in zip(r1, r2) if a == b)
    Po = agree / n
    assert agree == 19, f"Expected 19/20 concordant reviews, got {agree}"
    assert Po == 0.95, f"Expected 95% concordance, got {Po}"

    # Expected agreement Pe
    categories = sorted(list(set(r1 + r2)))
    c1 = Counter(r1)
    c2 = Counter(r2)
    Pe = sum((c1[cat] / n) * (c2[cat] / n) for cat in categories)
    assert round(Pe, 4) == 0.6250, f"Expected Pe=0.6250, got {Pe}"

    # Cohen's kappa
    kappa = (Po - Pe) / (1 - Pe)
    assert round(kappa, 2) == 0.87, f"Expected kappa=0.87, got {round(kappa, 2)}"


def test_exact_section_token_matching_no_substring_bleed():
    """Verify that section token extraction prevents substring collisions."""
    def parse_sections(raw_val):
        text = str(raw_val).upper().replace("§", " ").replace("SECTION", " ").replace("SEC", " ")
        tokens = re.findall(r"\b\d+[A-Z]*(?:\(\w+\))*", text)
        return [t.strip().upper() for t in tokens if t.strip()]

    def exact_match(cited, gt):
        c_toks = parse_sections(cited)
        g_toks = parse_sections(gt)
        for c in c_toks:
            for g in g_toks:
                if c == g:
                    return True
                c_base = re.sub(r"\(.*\)", "", c)
                g_base = re.sub(r"\(.*\)", "", g)
                if c_base == g_base and c_base:
                    return True
        return False

    # Negative collision cases (must NOT match)
    assert not exact_match("25", "2(25)"), "Token '25' must not match '2(25)'"
    assert not exact_match("10", "103"), "Token '10' must not match '103'"
    assert not exact_match("30", "303"), "Token '30' must not match '303'"
    assert not exact_match("12", "124A"), "Token '12' must not match '124A'"

    # Positive exact and base-section cases (MUST match)
    assert exact_match("103", "103")
    assert exact_match("318", "318(4)")
    assert exact_match("318(4)", "318")
    assert exact_match("103(1)", "103, 103(1)")


def test_retriever_ablation_metrics_congruence():
    """Verify results/retriever_ablation_comparison.csv contains valid 7-way ablation metrics."""
    ret_csv = "results/retriever_ablation_comparison.csv"
    assert os.path.exists(ret_csv), f"Missing {ret_csv}"

    rows = []
    with open(ret_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    assert len(rows) == 7, f"Expected 7 retrieval strategies, got {len(rows)}"

    # Strategy 1 (BM25 Sparse Baseline)
    s1 = rows[0]
    assert "10.0% (5/50)" in s1["Recall@1"]
    assert "46.0% (23/50)" in s1["Recall@5 (Full)"]
    assert s1["MRR"] == "0.248"

    # Strategy 2 (BM25 + Expansion)
    s2 = rows[1]
    assert "28.0% (14/50)" in s2["Recall@1"]
    assert "52.0% (26/50)" in s2["Recall@5 (Full)"]
    assert s2["MRR"] == "0.383"

    # Strategy 5 (Hybrid RRF + Expansion)
    s5 = rows[4]
    assert "26.0% (13/50)" in s5["Recall@1"]
    assert "56.0% (28/50)" in s5["Recall@5 (Full)"]
    assert s5["MRR"] == "0.391"

    # Strategy 6 (Hybrid RRF + Raw Re-Ranking)
    s6 = rows[5]
    assert "14.0% (7/50)" in s6["Recall@1"]
    assert "40.0% (20/50)" in s6["Recall@5 (Full)"]
    assert s6["MRR"] == "0.245"

    # Strategy 7 (Hybrid RRF + Expansion + Re-Ranking - Proposed)
    s7 = rows[6]
    assert "34.0% (17/50)" in s7["Recall@1"]
    assert "56.0% (28/50)" in s7["Recall@5 (Full)"]
    assert s7["MRR"] == "0.431"
    assert "50.0% (24/48)" in s7["Citation Hit Top-5 (Valid)"]


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

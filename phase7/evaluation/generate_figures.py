"""
generate_figures.py — Phase 7 Publication-Ready Figure Generator

Generates all 6 figures using matplotlib.
All figures saved to phase7/results/figures/
Does NOT modify any existing file.
"""

import os
import sys
import json
import csv
from collections import defaultdict
from typing import List, Dict, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PHASE7_ROOT = os.path.join(PROJECT_ROOT, "phase7")
FIGURES_DIR = os.path.join(PHASE7_ROOT, "results", "figures")
TABLES_DIR = os.path.join(PHASE7_ROOT, "results", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    _MPL_OK = True
except ImportError:
    _MPL_OK = False
    print("[WARN] matplotlib not available. Install with: pip install matplotlib")


def find_latest_results() -> str:
    raw_dir = os.path.join(PHASE7_ROOT, "results", "raw")
    files = sorted([f for f in os.listdir(raw_dir) if f.endswith(".json")])
    if not files:
        raise FileNotFoundError("No raw results found")
    return os.path.join(raw_dir, files[-1])


def load_results(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("results", [])


COLORS = {
    "A_ipc_bns_direct":     "#2196F3",
    "B_crpc_bnss_direct":   "#4CAF50",
    "C_natural_scenarios":  "#FF9800",
    "D_repealed_provisions":"#F44336",
    "E_split_provisions":   "#9C27B0",
    "F_merged_provisions":  "#00BCD4",
    "G_changed_meaning_scope": "#FF5722",
    "H_adversarial":        "#795548",
    "I_temporal_current_law": "#607D8B",
    "J_incremental_refresh":"#8BC34A",
}

CAT_LABELS = {
    "A_ipc_bns_direct":     "A: IPC→BNS Direct",
    "B_crpc_bnss_direct":   "B: CrPC→BNSS Direct",
    "C_natural_scenarios":  "C: Natural Scenarios",
    "D_repealed_provisions":"D: Repealed",
    "E_split_provisions":   "E: Split",
    "F_merged_provisions":  "F: Merged",
    "G_changed_meaning_scope": "G: Changed Scope",
    "H_adversarial":        "H: Adversarial",
    "I_temporal_current_law": "I: Temporal",
    "J_incremental_refresh":"J: Incremental",
}


def figure1_benchmark_composition(results: List[Dict]):
    """Figure 1: Benchmark composition by category (pie + bar)."""
    if not _MPL_OK:
        return
    
    cat_counts = defaultdict(int)
    for r in results:
        cat_counts[r.get("category", "unknown")] += 1
    
    cats = sorted(cat_counts.keys())
    counts = [cat_counts[c] for c in cats]
    labels = [f"{CAT_LABELS.get(c, c)}\n(n={cat_counts[c]})" for c in cats]
    colors = [COLORS.get(c, "#999999") for c in cats]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle("Phase 7 Benchmark Composition (N=1,140)", fontsize=14, fontweight="bold")
    
    wedges, texts, autotexts = ax1.pie(
        counts, labels=None, colors=colors, autopct="%1.1f%%",
        startangle=90, pctdistance=0.85
    )
    for at in autotexts:
        at.set_fontsize(8)
    ax1.legend(wedges, [CAT_LABELS.get(c, c) for c in cats],
               loc="lower left", fontsize=7, bbox_to_anchor=(-0.3, -0.15))
    ax1.set_title("Category Distribution")
    
    bars = ax2.barh([CAT_LABELS.get(c, c) for c in cats], counts,
                    color=colors, edgecolor="white")
    for bar, cnt in zip(bars, counts):
        ax2.text(bar.get_width() + 3, bar.get_y() + bar.get_height() / 2,
                 str(cnt), va="center", fontsize=9)
    ax2.set_xlabel("Number of Questions")
    ax2.set_title("Question Count by Category")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    
    plt.tight_layout()
    out = os.path.join(FIGURES_DIR, "fig1_benchmark_composition.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out}")


def figure2_retrieval_recall_at_k(results: List[Dict]):
    """Figure 2: Retrieval Recall@K curves by group."""
    if not _MPL_OK:
        return
    
    groups = {
        "Overall": results,
        "IPC→BNS": [r for r in results if r.get("category", "").startswith("A_")],
        "CrPC→BNSS": [r for r in results if r.get("category", "").startswith("B_")],
        "Natural": [r for r in results if not r.get("is_adversarial", False)],
        "Adversarial": [r for r in results if r.get("is_adversarial", False)],
    }
    
    ks = [1, 3, 5, 10]
    k_fields = ["recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10"]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    colors_g = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd"]
    
    for (gname, grecs), col in zip(groups.items(), colors_g):
        if not grecs:
            continue
        n = len(grecs)
        vals = [sum(r.get(kf, 0) for r in grecs) / n for kf in k_fields]
        ax.plot(ks, [v * 100 for v in vals], "o-", label=f"{gname} (n={n})",
                color=col, linewidth=2, markersize=7)
    
    ax.set_xlabel("K (Top-K retrieved)", fontsize=12)
    ax.set_ylabel("Recall@K (%)", fontsize=12)
    ax.set_title("Phase 7: Retrieval Recall@K by Group", fontsize=13, fontweight="bold")
    ax.set_xticks(ks)
    ax.set_ylim(0, 105)
    ax.legend(loc="lower right", fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    plt.tight_layout()
    out = os.path.join(FIGURES_DIR, "fig2_retrieval_recall_at_k.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out}")


def figure3_category_accuracy(results: List[Dict]):
    """Figure 3: Category-wise answer accuracy (citation hit rate)."""
    if not _MPL_OK:
        return
    
    cat_groups = defaultdict(list)
    for r in results:
        cat_groups[r.get("category", "unknown")].append(r)
    
    cats = sorted(cat_groups.keys())
    accs = []
    ns = []
    for c in cats:
        recs = cat_groups[c]
        n = len(recs)
        hits = sum(1 for r in recs if r.get("citation_any_hit", False))
        accs.append(hits / n * 100 if n else 0)
        ns.append(n)
    
    labels = [f"{CAT_LABELS.get(c, c)}\n(n={ns[i]})" for i, c in enumerate(cats)]
    colors_c = [COLORS.get(c, "#999999") for c in cats]
    
    fig, ax = plt.subplots(figsize=(14, 6))
    bars = ax.bar(labels, accs, color=colors_c, edgecolor="white", width=0.7)
    
    for bar, acc in zip(bars, accs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{acc:.1f}%", ha="center", va="bottom", fontsize=9)
    
    ax.set_ylabel("Citation Hit Rate (%)", fontsize=12)
    ax.set_title("Phase 7: Answer Accuracy by Category", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 115)
    ax.tick_params(axis="x", labelsize=8)
    ax.axhline(y=100, color="green", linestyle="--", alpha=0.3, label="100%")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    plt.tight_layout()
    out = os.path.join(FIGURES_DIR, "fig3_category_accuracy.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out}")


def figure4_verifier_prf(results: List[Dict]):
    """Figure 4: Verifier Precision/Recall/F1 by category."""
    if not _MPL_OK:
        return
    
    cat_groups = defaultdict(list)
    for r in results:
        cat_groups[r.get("category", "unknown")].append(r)
    
    cats_with_verifier = []
    prec_vals, rec_vals, f1_vals = [], [], []
    
    for cat in sorted(cat_groups.keys()):
        recs = [r for r in cat_groups[cat] if r.get("verifier_verdict") not in (None, "ERROR")]
        if not recs:
            continue
        adv = [r for r in recs if r.get("is_adversarial")]
        nat = [r for r in recs if not r.get("is_adversarial")]
        tp = sum(1 for r in adv if not r.get("verifier_is_verified", True))
        fp = sum(1 for r in nat if not r.get("verifier_is_verified", True))
        fn = sum(1 for r in adv if r.get("verifier_is_verified", False))
        
        p = tp / (tp + fp) if (tp + fp) > 0 else None
        rc = tp / (tp + fn) if (tp + fn) > 0 else None
        f1 = 2 * p * rc / (p + rc) if (p is not None and rc is not None and (p + rc) > 0) else None
        
        if f1 is not None:
            cats_with_verifier.append(CAT_LABELS.get(cat, cat))
            prec_vals.append(p * 100)
            rec_vals.append(rc * 100)
            f1_vals.append(f1 * 100)
    
    # Overall bar chart
    fig, ax = plt.subplots(figsize=(12, 5))
    
    # Overall stats
    all_adv = [r for r in results if r.get("is_adversarial") and r.get("verifier_verdict") not in (None, "ERROR")]
    all_nat = [r for r in results if not r.get("is_adversarial") and r.get("verifier_verdict") not in (None, "ERROR")]
    tp_all = sum(1 for r in all_adv if not r.get("verifier_is_verified", True))
    fp_all = sum(1 for r in all_nat if not r.get("verifier_is_verified", True))
    fn_all = sum(1 for r in all_adv if r.get("verifier_is_verified", False))
    tn_all = sum(1 for r in all_nat if r.get("verifier_is_verified", True))
    
    p_all = tp_all / (tp_all + fp_all) if (tp_all + fp_all) > 0 else 0.0
    r_all = tp_all / (tp_all + fn_all) if (tp_all + fn_all) > 0 else 0.0
    f1_all = 2 * p_all * r_all / (p_all + r_all) if (p_all + r_all) > 0 else 0.0
    spec_all = tn_all / (tn_all + fp_all) if (tn_all + fp_all) > 0 else 0.0
    
    metrics_overall = ["TP", "TN", "FP", "FN", "Precision", "Recall", "F1", "Specificity"]
    values_overall  = [tp_all, tn_all, fp_all, fn_all,
                       p_all * 100, r_all * 100, f1_all * 100, spec_all * 100]
    bar_colors = ["#4CAF50", "#2196F3", "#F44336", "#FF9800",
                  "#4CAF50", "#2196F3", "#9C27B0", "#00BCD4"]
    
    bars = ax.bar(metrics_overall[:4] + [""] + metrics_overall[4:],
                  list(values_overall[:4]) + [0] + list(values_overall[4:]),
                  color=bar_colors[:4] + ["white"] + bar_colors[4:], edgecolor="white")
    
    for i, (bar, val) in enumerate(zip(bars, list(values_overall[:4]) + [0] + list(values_overall[4:]))):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                    f"{val:.0f}" if i < 4 else f"{val:.1f}%", ha="center", va="bottom", fontsize=9)
    
    ax.set_title("Phase 7: Overall Verifier Performance", fontsize=13, fontweight="bold")
    ax.set_ylabel("Count / Percentage (%)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    plt.tight_layout()
    out = os.path.join(FIGURES_DIR, "fig4_verifier_prf.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out}")


def figure5_original_vs_largescale(results: List[Dict]):
    """Figure 5: Original N=60 vs Phase 7 large-scale performance."""
    if not _MPL_OK:
        return
    
    # Original published results (read-only)
    original = {
        "Stage 1\nBaseline": 10.0,
        "Stage 2\nRAG": 63.3,
        "Stage 3\nVerifier": 63.3,  # same RAG accuracy, verifier adds reliability not accuracy
        "Stage 4\nFull": 63.3,
    }
    
    # Phase 7
    n7 = len(results)
    hits7 = sum(1 for r in results if r.get("citation_any_hit", False))
    acc7 = hits7 / n7 * 100 if n7 else 0
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Phase 7: Original vs Large-Scale Evaluation", fontsize=14, fontweight="bold")
    
    # Left: stage progression
    ax1 = axes[0]
    stages = list(original.keys())
    vals = list(original.values())
    bars = ax1.bar(stages, vals, color=["#FF9800", "#2196F3", "#4CAF50", "#9C27B0"],
                   edgecolor="white", width=0.6)
    for bar, v in zip(bars, vals):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                 f"{v:.1f}%", ha="center", va="bottom", fontsize=11)
    ax1.set_title("Original N=60 Development Benchmark")
    ax1.set_ylabel("Citation Hit Rate (%)")
    ax1.set_ylim(0, 90)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    
    # Right: Phase 7 by category
    ax2 = axes[1]
    cat_groups = defaultdict(list)
    for r in results:
        cat_groups[r.get("category", "unknown")].append(r)
    
    cat_labels2, cat_accs2 = [], []
    for cat in sorted(cat_groups.keys()):
        recs = cat_groups[cat]
        n = len(recs)
        hits = sum(1 for r in recs if r.get("citation_any_hit", False))
        cat_labels2.append(CAT_LABELS.get(cat, cat).split(":")[0])
        cat_accs2.append(hits / n * 100 if n else 0)
    
    cat_colors2 = [COLORS.get(c, "#999999") for c in sorted(cat_groups.keys())]
    bars2 = ax2.bar(cat_labels2, cat_accs2, color=cat_colors2, edgecolor="white", width=0.7)
    for bar, acc in zip(bars2, cat_accs2):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                 f"{acc:.0f}%", ha="center", va="bottom", fontsize=8)
    ax2.set_title(f"Phase 7 Large-Scale Benchmark (N={n7})")
    ax2.set_ylabel("Citation Hit Rate (%)")
    ax2.set_ylim(0, 115)
    ax2.tick_params(axis="x", labelsize=8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    
    plt.tight_layout()
    out = os.path.join(FIGURES_DIR, "fig5_original_vs_largescale.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out}")


def figure6_error_distribution(results: List[Dict]):
    """Figure 6: Error distribution by type."""
    if not _MPL_OK:
        return
    
    error_cats = defaultdict(int)
    correct = 0
    
    for r in results:
        if r.get("citation_any_hit", False):
            correct += 1
        else:
            is_adv = r.get("is_adversarial", False)
            mtype = r.get("mapping_type", "")
            ret_secs = r.get("retrieved_sections", [])
            cited = r.get("cited_sections", [])
            
            if not ret_secs:
                error_cats["Retrieval Failure"] += 1
            elif not cited:
                error_cats["No Citation Generated"] += 1
            elif is_adv:
                error_cats["Adversarial Missed"] += 1
            elif mtype == "repealed":
                error_cats["Repealed Provision"] += 1
            elif mtype in ("split", "merged"):
                error_cats["Split/Merged Ambiguity"] += 1
            else:
                error_cats["Citation Mismatch"] += 1
    
    error_cats["Correct"] = correct
    
    labels = list(error_cats.keys())
    sizes = list(error_cats.values())
    err_colors = ["#F44336", "#FF9800", "#795548", "#9C27B0", "#FF5722", "#607D8B", "#4CAF50"]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Phase 7: Answer Quality Distribution", fontsize=14, fontweight="bold")
    
    wedges, texts, autotexts = ax1.pie(
        sizes, labels=labels, colors=err_colors[:len(labels)],
        autopct=lambda p: f"{p:.1f}%\n({int(round(p*sum(sizes)/100))})",
        startangle=90
    )
    for t in texts:
        t.set_fontsize(9)
    for at in autotexts:
        at.set_fontsize(8)
    ax1.set_title("Correct vs Error Breakdown")
    
    # Bar chart excluding "Correct"
    error_only = {k: v for k, v in error_cats.items() if k != "Correct"}
    if error_only:
        err_labels = list(error_only.keys())
        err_vals = list(error_only.values())
        ax2.bar(err_labels, err_vals,
                color=err_colors[:len(err_labels)], edgecolor="white")
        for i, v in enumerate(err_vals):
            ax2.text(i, v + 0.3, str(v), ha="center", va="bottom", fontsize=10)
        ax2.set_title("Error Type Distribution")
        ax2.set_ylabel("Count")
        ax2.tick_params(axis="x", rotation=20)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)
    
    plt.tight_layout()
    out = os.path.join(FIGURES_DIR, "fig6_error_distribution.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out}")


def main():
    if not _MPL_OK:
        print("[ERROR] matplotlib required. Install: pip install matplotlib numpy")
        return
    
    results_path = find_latest_results()
    print(f"Loading results: {results_path}")
    results = load_results(results_path)
    print(f"Loaded {len(results)} records. Generating figures...")
    
    print("\n[Fig 1] Benchmark composition...")
    figure1_benchmark_composition(results)
    
    print("[Fig 2] Retrieval Recall@K...")
    figure2_retrieval_recall_at_k(results)
    
    print("[Fig 3] Category accuracy...")
    figure3_category_accuracy(results)
    
    print("[Fig 4] Verifier P/R/F1...")
    figure4_verifier_prf(results)
    
    print("[Fig 5] Original vs large-scale...")
    figure5_original_vs_largescale(results)
    
    print("[Fig 6] Error distribution...")
    figure6_error_distribution(results)
    
    print(f"\nAll figures saved to: {FIGURES_DIR}")


if __name__ == "__main__":
    main()

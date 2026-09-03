#!/usr/bin/env python3
"""
check_progress.py

Scans the IPC2BNS-Verify project folder and reports how much of the
Work Breakdown Structure is actually done, based on which files/folders
exist on disk. Run this any time to get an up-to-date status table
instead of manually updating a checklist.

Usage:
    python check_progress.py --root /path/to/IPC2BNS-Verify
    python check_progress.py                      # defaults to current directory
    python check_progress.py --write-report        # also saves results/progress_report.md
"""

import argparse
import os
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Task definitions: each task is "done" if ALL of its check_paths exist
# (and, where noted, are non-empty). Paths are relative to project root.
# Edit this list as your actual folder/file names solidify.
# ---------------------------------------------------------------------------

TASKS = [
    # --- Phase 0: Setup ---
    {"phase": "0. Setup", "task": "Repo scaffolding + config system",
     "check_paths": ["code/src", "code/configs"]},
    {"phase": "0. Setup", "task": "India Code raw text downloaded",
     "check_paths": ["data/00_raw/india_code"]},
    {"phase": "0. Setup", "task": "Concordance source PDF(s) collected",
     "check_paths": ["data/00_raw/concordance_source_pdfs"]},
    {"phase": "0. Setup", "task": "Data Management Plan written",
     "check_paths": ["docs/IPC2BNS-Verify_Data_Management_Plan.md"]},

    # --- Phase 1: Mapping Module ---
    {"phase": "1. Mapping Module", "task": "Ground-truth concordance table finalized",
     "check_paths": ["data/02_ground_truth/concordance_v1.csv"]},
    {"phase": "1. Mapping Module", "task": "Concordance validation report reviewed",
     "check_paths": ["data/02_ground_truth/validation_report.csv"]},
    {"phase": "1. Mapping Module", "task": "Deterministic lookup function implemented",
     "check_paths": ["code/src/mapping/lookup.py"]},
    {"phase": "1. Mapping Module", "task": "Query normalizer implemented",
     "check_paths": ["code/src/mapping/normalizer.py"]},
    {"phase": "1. Mapping Module", "task": "Mapping module unit tests",
     "check_paths": ["code/tests/test_concordance.py"]},

    # --- Phase 2: Ingestion & Retrieval ---
    {"phase": "2. Ingestion & Retrieval", "task": "Section-level chunker implemented",
     "check_paths": ["code/src/ingestion/chunker.py"]},
    {"phase": "2. Ingestion & Retrieval", "task": "Cleaned section corpus produced",
     "check_paths": ["data/01_cleaned/ipc_sections.jsonl", "data/01_cleaned/bns_sections.jsonl"]},
    {"phase": "2. Ingestion & Retrieval", "task": "Benchmark question set drafted (dev)",
     "check_paths": ["data/03_benchmark/benchmark_dev.csv"]},
    {"phase": "2. Ingestion & Retrieval", "task": "Benchmark test set held out",
     "check_paths": ["data/03_benchmark/benchmark_test.csv"]},
    {"phase": "2. Ingestion & Retrieval", "task": "Embedding index built",
     "check_paths": ["data/05_embeddings_index/stage2_index"]},
    {"phase": "2. Ingestion & Retrieval", "task": "Retrieval precision/recall evaluated",
     "check_paths": ["results/stage2/retrieval_metrics.json"]},

    # --- Phase 3: Generation ---
    {"phase": "3. Generation", "task": "Prompt template + citation format defined",
     "check_paths": ["code/src/generation/prompt_template.py"]},
    {"phase": "3. Generation", "task": "Stage 1 (baseline, no retrieval) run complete",
     "check_paths": ["results/stage1/stage1_baseline_results.json"]},
    {"phase": "3. Generation", "task": "Stage 2 (+RAG) run complete",
     "check_paths": ["results/stage2/stage2_rag_results.json"]},

    # --- Phase 4: Verifier ---
    {"phase": "4. Verifier", "task": "Layer 1 hard citation-existence check implemented",
     "check_paths": ["code/src/verifier/citation_check.py"]},
    {"phase": "4. Verifier", "task": "Layer 2 entity-grounding check implemented",
     "check_paths": ["code/src/verifier/entity_grounding.py"]},
    {"phase": "4. Verifier", "task": "Injected-error test set built",
     "check_paths": ["data/03_benchmark/injected_errors.csv"]},
    {"phase": "4. Verifier", "task": "Stage 3 (+Verifier) run complete",
     "check_paths": ["results/stage3/stage3_verifier_results.json"]},

    # --- Phase 5: Adaptivity ---
    {"phase": "5. Adaptivity", "task": "Refresh simulation cases selected",
     "check_paths": ["data/04_refresh_sim/injected_amendment_cases.csv"]},
    {"phase": "5. Adaptivity", "task": "Pre/post-refresh index snapshots built",
     "check_paths": ["data/05_embeddings_index/stage4_post_refresh_index"]},
    {"phase": "5. Adaptivity", "task": "Stage 4 (+Verifier+Refresh) run complete",
     "check_paths": ["results/stage4/stage4_refresh_results.json"]},

    # --- Phase 6: Evaluation & Write-up ---
    {"phase": "6. Evaluation & Write-up", "task": "Evaluation harness built",
     "check_paths": ["code/src/eval/harness.py"]},
    {"phase": "6. Evaluation & Write-up", "task": "Human-review calibration done",
     "check_paths": ["results/human_review_calibration.csv"]},
    {"phase": "6. Evaluation & Write-up", "task": "Ablation summary table compiled",
     "check_paths": ["results/ablation_summary_table.csv"]},
    {"phase": "6. Evaluation & Write-up", "task": "Error analysis notes written",
     "check_paths": ["results/error_analysis_notes.md"]},
    {"phase": "6. Evaluation & Write-up", "task": "Plagiarism/originality check run",
     "check_paths": ["report/plagiarism_report.pdf"]},
    {"phase": "6. Evaluation & Write-up", "task": "Final report drafted",
     "check_paths": ["report/final_report.docx"]},
    {"phase": "6. Evaluation & Write-up", "task": "Presentation deck built",
     "check_paths": ["report/presentation_deck.pptx"]},
]


def path_exists_and_nonempty(full_path):
    if not os.path.exists(full_path):
        return False
    if os.path.isdir(full_path):
        return any(os.scandir(full_path))  # dir exists but must have at least one file
    return os.path.getsize(full_path) > 0  # file exists and isn't a stub


def check_task(root, task):
    return all(
        path_exists_and_nonempty(os.path.join(root, p))
        for p in task["check_paths"]
    )


def build_report(root):
    phases = {}
    for t in TASKS:
        done = check_task(root, t)
        phases.setdefault(t["phase"], []).append((t["task"], done, t["check_paths"]))
    return phases


def print_report(phases):
    total_tasks = 0
    total_done = 0
    lines = []
    lines.append(f"# Project Progress Report")
    lines.append(f"_Generated: {datetime.now().isoformat(timespec='seconds')}_\n")

    for phase, tasks in phases.items():
        done_count = sum(1 for _, d, _ in tasks if d)
        pct = 100 * done_count / len(tasks)
        total_tasks += len(tasks)
        total_done += done_count
        lines.append(f"## {phase} — {done_count}/{len(tasks)} ({pct:.0f}%)")
        for name, done, paths in tasks:
            mark = "x" if done else " "
            lines.append(f"- [{mark}] {name}  `({', '.join(paths)})`")
        lines.append("")

    overall_pct = 100 * total_done / total_tasks if total_tasks else 0
    lines.insert(1, f"**Overall: {total_done}/{total_tasks} tasks complete ({overall_pct:.0f}%)**\n")

    report_text = "\n".join(lines)
    print(report_text)
    return report_text


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check IPC2BNS-Verify project progress against the WBS.")
    parser.add_argument("--root", default=".", help="Path to the project root folder (contains code/, data/, results/, report/)")
    parser.add_argument("--write-report", action="store_true", help="Also write results/progress_report.md")
    if argv is None and any("ipykernel" in a or "-f" in a or a.endswith(".json") for a in sys.argv):
        args, _ = parser.parse_known_args([])
    else:
        args = parser.parse_args(argv)

    root = os.path.abspath(args.root)
    phases = build_report(root)
    report_text = print_report(phases)

    if args.write_report:
        out_dir = os.path.join(root, "results")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "progress_report.md")
        with open(out_path, "w") as f:
            f.write(report_text)
        print(f"\nSaved report to {out_path}")


if __name__ == "__main__":
    main()
